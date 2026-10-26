from io import BytesIO
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch
from zipfile import ZipFile

from features.github_forecast_sync import sync_latest_dashboard_report


class GithubDashboardSyncTests(unittest.TestCase):
    def test_full_report_artifact_updates_persisted_dashboard_data(self):
        report = {
            'players': [{'id': '1', 'owned': True, 'li': 99}],
            'marketPlayers': [{'id': '2', 'owned': False, 'li': 75}],
            'user': 'u', 'league': 'l', 'budget': 100,
        }
        html = '<script id="data" type="application/json">' + json.dumps(report) + '</script>'
        archive_data = BytesIO()
        with ZipFile(archive_data, 'w') as zipped:
            zipped.writestr('startelf_optimizer.html', html)

        listing = Mock()
        listing.raise_for_status.return_value = None
        listing.json.return_value = {'artifacts': [{
            'id': 42, 'name': 'startelf-optimizer', 'expired': False,
            'updated_at': '2026-10-26T12:00:00Z', 'archive_download_url': 'https://artifact',
        }]}
        archive = Mock(content=archive_data.getvalue())
        archive.raise_for_status.return_value = None

        with tempfile.TemporaryDirectory() as folder, \
                patch('features.github_forecast_sync.requests.get', side_effect=[listing, archive]):
            result = sync_latest_dashboard_report('token', 'owner/repo', folder)
            saved = json.loads(Path(folder, '.advisor-report.json').read_text(encoding='utf-8'))
            marker = json.loads(Path(folder, '.github-dashboard-sync.json').read_text(encoding='utf-8'))

        self.assertEqual(result['status'], 'updated')
        self.assertEqual(saved['players'][0]['li'], 99)
        self.assertEqual(saved['marketPlayers'][0]['li'], 75)
        self.assertEqual(marker['artifactId'], 42)


if __name__ == '__main__':
    unittest.main()
