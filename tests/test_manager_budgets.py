from io import BytesIO
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from zipfile import ZipFile

from advisor_server import read_manager_budgets
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
