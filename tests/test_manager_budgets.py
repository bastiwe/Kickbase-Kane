from io import BytesIO
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch
from zipfile import ZipFile

from advisor_server import AdvisorHandler, add_live_manager_rosters, create_server, read_manager_budgets
from features.github_forecast_sync import sync_latest_manager_audit


class Response:
    def __init__(self, *, payload=None, content=b''):
        self.payload = payload
        self.content = content

    def json(self):
        return self.payload

    def raise_for_status(self):
        return None


class ManagerBudgetTests(unittest.TestCase):
    def test_planner_uses_estimate_for_selected_manager_and_rejects_its_save(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            budget_file = root / 'manager-history-output' / 'latest.json'
            budget_file.parent.mkdir()
            report = {'league_id': 'league', 'manager_budgets': [
                {'id': 'other', 'name': 'Alter Name', 'cash': -2_000_000,
                 'squadValue': 100_000_000, 'buyingPower': 31_000_000},
            ]}
            budget_file.write_text(json.dumps(report))
            with create_server(0, {'league': 'league', 'user': 'own', 'players': []}) as server:
                server.kickbase = Mock()
                server.kickbase.league_managers.return_value = [
                    {'id': 'own', 'name': 'Ich'}, {'id': 'other', 'name': 'Mitmanager'},
                ]
                server.kickbase.manager_squad.return_value = ([{'id': '101'}], {'players': ['101']})
                handler = AdvisorHandler.__new__(AdvisorHandler)
                handler.server = server
                handler.reply = Mock()
                with (patch('advisor_server.DATA_ROOT', root),
                      patch('advisor_server.read_prediction_snapshot', return_value=None)):
                    handler.planner_managers(None)
                    handler.reply.assert_called_with(200, {'managers': [{'id': 'other', 'name': 'Mitmanager'}]})
                    handler.planner_managers('other')
                    self.assertEqual(handler.reply.call_args.args[1]['budget'], -2_000_000)
                    self.assertTrue(handler.is_planner_player('101', server.report))
                    self.assertFalse(handler.is_planner_player('101', {**server.report, 'league': 'another'}))
                    budget_file.write_text(json.dumps({**report, 'league_id': 'another'}))
                    handler.planner_managers('other')
                    self.assertIsNone(handler.reply.call_args.args[1]['budget'])
                with self.assertRaisesRegex(ValueError, 'nur simuliert'):
                    handler.apply_lineup({'state': {'manager': 'other', 'selection': []}})
                server.kickbase.apply_lineup.assert_not_called()

    def test_live_members_merge_by_id_or_legacy_name_even_without_a_budget(self):
        budgets = {'note': '', 'managers': [
            {'id': 'a', 'name': 'Alter Name', 'cash': 1, 'buyingPower': 10},
            {'name': 'Ben', 'cash': 2, 'buyingPower': 20},
            {'id': 'left', 'name': 'Chris', 'cash': 3, 'buyingPower': 30},
        ]}
        rosters = [
            {'id': 'a', 'name': 'Anna', 'squadSize': 16},
            {'id': 'b', 'name': 'Ben', 'squadSize': 14},
            {'id': 'c', 'name': 'Chris', 'squadSize': 0},
        ]
        result = add_live_manager_rosters(budgets, rosters)['managers']
        self.assertEqual([(row['id'], row['squadSize'], row.get('cash')) for row in result],
                         [('b', 14, 2), ('a', 16, 1), ('c', 0, None)])

    def test_reader_exposes_only_valid_budget_rows(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'latest.json'
            path.write_text(json.dumps({
                'generated_at': '2026-10-25T14:00:00+01:00',
                'manager_budgets': [
                    {'name': 'Johannes', 'cash': 10, 'squadValue': 100, 'buyingPower': 43,
                     'basis': 'Schätzung'},
                    {'name': 'Defekt', 'cash': 'offen', 'squadValue': 100, 'buyingPower': 0},
                ],
            }), encoding='utf-8')
            result = read_manager_budgets(path)
            self.assertEqual([item['name'] for item in result['managers']], ['Johannes'])
            self.assertEqual(result['managers'][0]['buyingPower'], 43)
            self.assertIn('geschätzt', result['note'])

    def test_missing_summary_has_helpful_empty_state(self):
        result = read_manager_budgets('does-not-exist.json')
        self.assertEqual(result['managers'], [])
        self.assertIn('Vollreport', result['note'])

    def test_live_own_cash_replaces_stale_report_value_and_updates_buying_power(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'latest.json'
            path.write_text(json.dumps({
                'generated_at': '2026-10-25T14:00:00+01:00',
                'manager_budgets': [
                    {'name': 'Anna', 'cash': 1_000_000, 'squadValue': 90_000_000,
                     'buyingPower': 30_700_000, 'basis': 'API (eigener Kontostand)'},
                    {'name': 'Ben', 'cash': 2_000_000, 'squadValue': 80_000_000,
                     'buyingPower': 28_400_000, 'basis': 'Schätzung'},
                ],
            }), encoding='utf-8')
            result = read_manager_budgets(
                path, own_cash=4_000_000, own_name='Anna',
                cash_fetched_at='2026-10-26T10:00:00+01:00')
        anna = next(row for row in result['managers'] if row['name'] == 'Anna')
        ben = next(row for row in result['managers'] if row['name'] == 'Ben')
        self.assertEqual(anna['cash'], 4_000_000)
        self.assertEqual(anna['buyingPower'], 33_700_000)
        self.assertEqual(anna['basis'], 'API live (eigener Kontostand)')
        self.assertEqual(ben['cash'], 2_000_000)
        self.assertEqual(result['cashFetchedAt'], '2026-10-26T10:00:00+01:00')

    def test_manager_audit_artifact_is_saved_for_dashboard(self):
        payload = {
            'generated_at': '2026-10-25T14:00:00+01:00',
            'manager_budgets': [{'name': 'Anna', 'cash': 1, 'squadValue': 2, 'buyingPower': 3}],
        }
        archive = BytesIO()
        with ZipFile(archive, 'w') as zipped:
            # upload-artifact stores the contents of an uploaded directory at
            # archive root rather than retaining that directory's own name.
            zipped.writestr('latest.json', json.dumps(payload))
            zipped.writestr('latest.html', '<html></html>')
        listing = Response(payload={'artifacts': [{
            'id': 7, 'name': 'manager-audit', 'expired': False,
            'archive_download_url': 'https://example.invalid/audit.zip',
            'updated_at': '2026-10-25T14:05:00Z',
        }]})
        download = Response(content=archive.getvalue())
        with tempfile.TemporaryDirectory() as folder, patch(
                'features.github_forecast_sync.requests.get', side_effect=[listing, download]):
            result = sync_latest_manager_audit('token', 'owner/repo', folder)
            saved = json.loads(Path(folder, 'manager-history-output', 'latest.json').read_text(encoding='utf-8'))
        self.assertEqual(result['status'], 'updated')
        self.assertEqual(saved['manager_budgets'][0]['name'], 'Anna')


if __name__ == '__main__':
    unittest.main()
