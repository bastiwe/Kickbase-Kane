from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch

from kickbase_kane import schedule_reports as scheduler


class AddonScheduleTests(unittest.TestCase):
    def test_defaults_and_custom_times(self):
        expected = ((6, 30), (14, 0), (22, 10))
        self.assertEqual(scheduler.parse_report_times(None), expected)
        self.assertEqual(scheduler.parse_report_times('invalid'), expected)
        self.assertEqual(scheduler.parse_report_times('14:00,06:30,14:00,25:00'),
                         ((6, 30), (14, 0)))

    def test_next_slot_and_next_day(self):
        slots = scheduler.parse_report_times(None)
        now = datetime(2026, 10, 27, 6, 0, tzinfo=scheduler.BERLIN)
        self.assertEqual(scheduler.next_run(now, slots).strftime('%H:%M'), '06:30')
        now = now.replace(hour=23)
        self.assertEqual(scheduler.next_run(now, slots),
                         datetime(2026, 10, 28, 6, 30, tzinfo=scheduler.BERLIN))

    def test_slot_runs_once_and_remains_recorded_after_restart(self):
        now = datetime(2026, 10, 27, 22, 10, tzinfo=scheduler.BERLIN)
        with tempfile.TemporaryDirectory() as folder, patch.object(
                scheduler, 'DATA_ROOT', Path(folder)), patch.object(
                scheduler, 'run_report', return_value=True) as run:
            self.assertTrue(scheduler.run_due_report(now, ((22, 10),)))
            self.assertFalse(scheduler.run_due_report(now + timedelta(minutes=1), ((22, 10),)))
            run.assert_called_once()

    def test_short_restart_catches_up_but_long_downtime_does_not(self):
        now = datetime(2026, 10, 27, 14, 8, tzinfo=scheduler.BERLIN)
        with tempfile.TemporaryDirectory() as folder, patch.object(
                scheduler, 'DATA_ROOT', Path(folder)), patch.object(
                scheduler, 'run_report', return_value=True) as run:
            self.assertTrue(scheduler.run_due_report(now, ((14, 0),)))
            run.assert_called_once()
        with patch.object(scheduler, 'run_report') as run:
            self.assertFalse(scheduler.run_due_report(now.replace(minute=16), ((14, 0),)))
            run.assert_not_called()

    def test_failed_requests_retry_at_five_minute_intervals_at_most_three_times(self):
        now = datetime(2026, 10, 27, 6, 30, tzinfo=scheduler.BERLIN)
        with tempfile.TemporaryDirectory() as folder, patch.object(
                scheduler, 'DATA_ROOT', Path(folder)), patch.object(
                scheduler, 'run_report', return_value=False) as run:
            for minutes in (0, 1, 5, 10, 15):
                self.assertFalse(scheduler.run_due_report(now + timedelta(minutes=minutes), ((6, 30),)))
            self.assertEqual(run.call_count, 3)

    def test_berlin_slots_remain_local_after_dst_changes(self):
        for month, day in ((3, 29), (10, 25)):
            now = datetime(2026, month, day, 6, 30, tzinfo=scheduler.BERLIN)
            with tempfile.TemporaryDirectory() as folder, patch.object(
                    scheduler, 'DATA_ROOT', Path(folder)), patch.object(
                    scheduler, 'run_report', return_value=True) as run:
                self.assertTrue(scheduler.run_due_report(now, ((6, 30),)))
                run.assert_called_once()

    def test_github_mode_requests_full_workflow_without_local_training(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(
                scheduler, 'DATA_ROOT', Path(folder)), patch.dict(
                'os.environ', {'GITHUB_FORECAST_TOKEN': 'test-token',
                               'GITHUB_FORECAST_REPOSITORY': 'owner/repo'}), patch.object(
                scheduler, 'dispatch_workflow') as dispatch, patch.object(
                scheduler.subprocess, 'run') as local:
            self.assertTrue(scheduler.run_report())
            dispatch.assert_called_once_with('test-token', 'owner/repo', 'actions_spaet.yml')
            local.assert_not_called()

    def test_dispatch_failure_is_logged_without_claiming_report_success(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(
                scheduler, 'DATA_ROOT', Path(folder)), patch.dict(
                'os.environ', {'GITHUB_FORECAST_TOKEN': 'test-token'}), patch.object(
                scheduler, 'dispatch_workflow', side_effect=RuntimeError('Actions: Read and write')):
            self.assertFalse(scheduler.run_report())
            self.assertIn('Actions: Read and write',
                          (Path(folder) / 'scheduled-report.log').read_text(encoding='utf-8'))

    def test_without_token_runs_existing_full_report_locally(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(
                scheduler, 'DATA_ROOT', Path(folder)), patch.dict(
                'os.environ', {'GITHUB_FORECAST_TOKEN': ''}), patch.object(
                scheduler.subprocess, 'run', return_value=SimpleNamespace(returncode=0)) as run:
            self.assertTrue(scheduler.run_report())
            self.assertTrue(run.call_args.args[0][-1].endswith('daily_predictions_spaet.py'))
            self.assertEqual(run.call_args.kwargs['cwd'], Path(folder))


if __name__ == '__main__':
    unittest.main()
