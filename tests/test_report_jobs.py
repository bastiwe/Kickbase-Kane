import json
from pathlib import Path
import tempfile
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from features.report_jobs import ReportJobs


class ReportJobTests(unittest.TestCase):
    def test_success_merges_only_forecasts(self):
        with tempfile.TemporaryDirectory() as folder:
            player = {'id': '1', 'owned': True, 'mv': 100, 'li': 99, 'change': -5}
            report = {'players': [player], 'user': 'u', 'league': 'l'}
            server = SimpleNamespace(lock=threading.Lock(), report=report)
            jobs = ReportJobs(server, folder)
            def finish(*args, **kwargs):
                Path(folder, 'prediction_snapshot_1t.json').write_text(json.dumps({
                    'version': 1, 'competitionId': 1, 'generatedAt': '2026-09-12T12:00:00+02:00',
                    'source': 'Fast 1T', 'predictions': {'1': 25}}))
                return SimpleNamespace(returncode=0)
            with patch('features.report_jobs.subprocess.run', side_effect=finish):
                jobs.run('daily_predictions_fast.py', {}, report, 'fast')
            self.assertEqual(jobs.read()['status'], 'done')
            self.assertEqual(player['change'], 25)
            self.assertEqual(player['mv'], 100)
            self.assertEqual(player['li'], 99)

    def test_failure_does_not_apply_old_snapshot(self):
        with tempfile.TemporaryDirectory() as folder:
            player = {'id': '1', 'change': 5}
            report = {'players': [player], 'user': 'u', 'league': 'l'}
            jobs = ReportJobs(SimpleNamespace(lock=threading.Lock(), report=report), folder)
            with patch('features.report_jobs.subprocess.run', return_value=SimpleNamespace(returncode=1)):
                jobs.run('daily_predictions_fast.py', {}, report, 'fast')
            self.assertEqual(jobs.read()['status'], 'failed')
            self.assertEqual(player['change'], 5)

    def test_generated_report_keeps_existing_li_and_is_persisted(self):
        with tempfile.TemporaryDirectory() as folder:
            persisted = Path(folder, '.advisor-report.json')
            report = {
                'players': [{'id': '1', 'owned': True, 'mv': 100, 'li': 85}],
                'marketPlayers': [{'id': '2', 'owned': False, 'mv': 200, 'li': 65}],
                'user': 'u', 'league': 'l',
            }
            server = SimpleNamespace(
                lock=threading.Lock(), report=report, persist_path=persisted,
            )
            jobs = ReportJobs(server, folder)
            generated = {
                'players': [{'id': '1', 'owned': True, 'mv': 101, 'li': None}],
                'marketPlayers': [{'id': '2', 'owned': False, 'mv': 201, 'li': None}],
                'user': 'u', 'league': 'l',
            }

            def finish(*args, **kwargs):
                Path(folder, 'prediction_snapshot_1t.json').write_text(json.dumps({
                    'version': 1, 'competitionId': 1, 'generatedAt': '2026-09-12T12:00:00+02:00',
                    'source': 'Fast 1T', 'predictions': {'1': 25, '2': 30},
                }))
                Path(folder, 'startelf_optimizer.html').write_text('new report')
                return SimpleNamespace(returncode=0)

            with patch('features.report_jobs.subprocess.run', side_effect=finish), \
                    patch('advisor_server.read_report', return_value=generated):
                jobs.run('daily_predictions_fast.py', {}, report, 'fast')

            self.assertEqual(jobs.read()['status'], 'done')
            self.assertEqual(server.report['players'][0]['li'], 85)
            self.assertEqual(server.report['marketPlayers'][0]['li'], 65)
            saved = json.loads(persisted.read_text(encoding='utf-8'))
            self.assertEqual(saved['players'][0]['li'], 85)
            self.assertEqual(saved['marketPlayers'][0]['li'], 65)

    def test_unknown_job_rejected(self):
        jobs = ReportJobs(None, '.')
        with self.assertRaises(ValueError):
            jobs.start('../custom.py')
