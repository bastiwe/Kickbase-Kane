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

    def test_unknown_job_rejected(self):
        jobs = ReportJobs(None, '.')
        with self.assertRaises(ValueError):
            jobs.start('../custom.py')
