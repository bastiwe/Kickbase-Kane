from datetime import datetime, timedelta
import json
from pathlib import Path
import sqlite3
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from features.cash_reconstruction import BERLIN
from features.history_store import HistoryStore
from features.manager_monitor import ManagerMonitor


class ManagerMonitorTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.now = datetime(2026, 11, 6, 20, 34, tzinfo=BERLIN)
        self.responses = {
            '/competitions/1/matchdays': {'it': [{'day': 10, 'it': [{'dt': '2026-11-06T19:30:00Z'}]}]},
            '/leagues/l/ranking': {'us': [{'i': '1', 'n': 'Anna'}, {'i': '2', 'n': 'Ben'}]},
            '/leagues/l/managers/1/squad': {'it': [{'pi': 'p1', 'lo': 0}, {'pi': 'p2', 'lo': 11}]},
            '/leagues/l/managers/2/squad': {'it': [{'pi': 'p3', 'lo': 0}]},
            '/leagues/l/activitiesFeed?max=5000': {'af': []},
        }
        self.get = Mock(side_effect=lambda path: self.responses[path])
        self.audit = Mock(return_value=SimpleNamespace(attrs={'manager_audit': {
            'errors': {'teamcenter': {}}, 'manager_budgets': [{'name': 'Anna'}, {'name': 'Ben'}],
            'events': [{'manager': name, 'day': 10, 'kind': 'Spieltagspunkte'} for name in ['Anna', 'Ben']],
        }}))
        self.monitor = ManagerMonitor(self.get, 'l', '2026-08-15', self.tmp.name, audit=self.audit)

    def test_kickoff_partial_failure_retries_only_missing_manager_after_restart(self):
        self.monitor.schedule()
        squad = self.responses.pop('/leagues/l/managers/2/squad')
        self.monitor.task('kickoff', self.now, 60, lambda: self.monitor.capture_kickoff(self.now))
        self.assertEqual(self.monitor.state['tasks']['kickoff']['status'], 'retry')
        restarted = ManagerMonitor(self.get, 'l', '2026-08-15', self.tmp.name, audit=self.audit)
        self.responses['/leagues/l/managers/1/squad'] = {'it': [{'pi': 'changed_after_lock', 'lo': 0}]}
        self.responses['/leagues/l/managers/2/squad'] = squad
        restarted.task('kickoff', self.now + timedelta(minutes=2), 60,
                       lambda: restarted.capture_kickoff(self.now + timedelta(minutes=2)))
        store = HistoryStore(restarted.history)
        try:
            self.assertEqual(store.kickoff_squad(restarted.scope, '1', 10)['squad']['it'][0]['pi'], 'p1')
            self.assertIsNotNone(store.kickoff_squad(restarted.scope, '2', 10))
        finally:
            store.close()

    def test_transfer_retries_are_deduplicated_and_do_not_need_forecasts(self):
        trade = {'pi': 'p', 'dt': '2026-11-06T12:00:00Z', 'tty': 1, 'trp': 1000}
        with patch('features.manager_monitor.fetch_manager_transfers', return_value=[trade]):
            first = self.monitor.transfers(self.now)
            second = self.monitor.transfers(self.now + timedelta(minutes=30))
        self.assertEqual(first['new_transfers'], 2)  # Same player, distinct manager ledgers.
        self.assertEqual(second['new_transfers'], 0)
        self.audit.assert_not_called()

    def test_missing_lineup_positions_are_not_marked_as_a_successful_snapshot(self):
        self.monitor.schedule()
        self.responses['/leagues/l/managers/1/squad'] = {'it': [{'pi': 'p1'}]}
        self.monitor.task('kickoff', self.now, 60, lambda: self.monitor.capture_kickoff(self.now))
        self.assertNotIn('10', self.monitor.state.get('captured_days', []))
        self.assertEqual(self.monitor.state['tasks']['kickoff']['status'], 'retry')

    def test_changing_league_resets_completion_markers_but_keeps_archive(self):
        self.monitor.state['captured_days'] = ['10']
        from features.history_sync import atomic_json
        atomic_json(self.monitor.state_path, self.monitor.state)
        other = ManagerMonitor(self.get, 'different', '2026-08-15', self.tmp.name)
        self.assertNotIn('captured_days', other.state)

    def test_settlement_on_any_weekday_runs_audit_and_restart_does_not_repeat_it(self):
        self.responses['/leagues/l/activitiesFeed?max=5000'] = {'af': [
            {'t': '17', 'dt': self.now.isoformat(), 'data': {'day': 10}}]}
        with patch('features.manager_monitor.fetch_manager_transfers', return_value=[]):
            self.monitor.tick(self.now)
        self.assertEqual(self.monitor.state['settled_processed'], [10])
        self.audit.assert_called_once()
        restarted = ManagerMonitor(self.get, 'l', '2026-08-15', self.tmp.name, audit=self.audit)
        with patch('features.manager_monitor.fetch_manager_transfers', return_value=[]):
            restarted.tick(self.now + timedelta(minutes=1))
        self.audit.assert_called_once()

    def test_incomplete_final_scores_remain_pending_then_retry(self):
        self.monitor.state['settled_seen'] = [10]
        self.audit.return_value.attrs['manager_audit']['events'] = []
        self.monitor.task('audit', self.now, 21600, lambda: self.monitor.reconcile(self.now))
        self.assertNotIn(10, self.monitor.state['settled_processed'])
        self.assertEqual(self.monitor.state['tasks']['audit']['status'], 'retry')
        self.audit.return_value.attrs['manager_audit']['events'] = [
            {'manager': name, 'day': 10, 'kind': 'Spieltagspunkte'} for name in ['Anna', 'Ben']]
        later = self.now + timedelta(minutes=5)
        self.monitor.task('audit', later, 21600, lambda: self.monitor.reconcile(later))
        self.assertEqual(self.monitor.state['settled_processed'], [10])

    def test_github_failure_does_not_block_local_capture_or_audit(self):
        with patch('features.manager_monitor.sync_history', side_effect=ConnectionError), \
                patch('features.manager_monitor.fetch_manager_transfers', return_value=[]):
            self.monitor.tick(self.now)
        self.assertEqual(self.monitor.state['tasks']['sync']['status'], 'retry')
        self.assertEqual(self.monitor.state['captured_days'], ['10'])
        self.audit.assert_called_once()
        self.assertTrue(Path(self.tmp.name, 'manager-monitor.log').is_file())


if __name__ == '__main__':
    unittest.main()
