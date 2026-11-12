from io import BytesIO
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from zipfile import ZipFile

from advisor_server import add_live_manager_rosters, read_manager_budgets
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
