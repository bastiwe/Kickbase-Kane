from datetime import datetime
from pathlib import Path
import sqlite3
import tempfile
import unittest

from features.cash_reconstruction import BERLIN
from features.manager_history import HistoryStore, audit_managers, historical_roster, lineup_estimate, mvp_events
from manager_history import kickoff_due


class ManagerHistoryTests(unittest.TestCase):
    def test_capture_window_is_after_first_kickoff(self):
        payload = {'it': [{'day': 1, 'it': [{'dt': '2026-08-28T18:30:00Z'}]}]}
        self.assertFalse(kickoff_due(payload, datetime(2026, 8, 28, 20, 20, tzinfo=BERLIN)))
        self.assertTrue(kickoff_due(payload, datetime(2026, 8, 28, 20, 45, tzinfo=BERLIN)))
        self.assertFalse(kickoff_due(payload, datetime(2026, 8, 28, 21, 10, tzinfo=BERLIN)))

    def test_roster_is_reconstructed_at_kickoff(self):
        squad = {'it': [{'pi': 'new'}, {'pi': 'held'}]}
        transfers = [
            {'pi': 'old', 'tty': 2, 'dt': '2026-08-20T10:00:00Z'},
            {'pi': 'new', 'tty': 1, 'dt': '2026-08-21T10:00:00Z'},
        ]
        result = historical_roster(squad, transfers, '2026-08-19T18:30:00Z')
        self.assertEqual(result['players'], ['held', 'old'])
        self.assertEqual(result['issues'], [])

    def test_lineup_bounds_keep_ambiguity_visible(self):
        players = [str(i) for i in range(12)]
        points = {pid: 100 for pid in players}
        estimate = lineup_estimate(players, points, 1100)
        self.assertGreater(estimate['solutions'], 1)
        self.assertEqual(estimate['always_selected'], [])
        self.assertFalse(estimate['formation_checked'])

    def test_mvp_requires_unique_leader_in_every_matching_lineup(self):
        base = {'roster': {'issues': []}, 'fetch_errors': []}
        entries = {
            'A': {**base, 'points': {'star': 500},
                  'lineup': {'solutions': 2, 'always_selected': ['star']}},
            'B': {**base, 'points': {'other': 300},
                  'lineup': {'solutions': 1, 'always_selected': ['other']}},
        }
        events = {event['manager']: event for event in mvp_events(1, entries)}
        self.assertEqual(events['A']['amount'], 1_000_000)
        self.assertEqual(events['B']['amount'], 0)

    def test_observations_are_append_only_between_runs(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'history.sqlite3'
            store = HistoryStore(path)
            now = datetime(2026, 8, 28, 20, 0, tzinfo=BERLIN)
            store.observe('league', 'run-1', 'kickoff_squad', 'manager:1', now, {'players': ['a']})
            store.observe('league', 'run-2', 'kickoff_squad', 'manager:1', now, {'players': ['b']})
            store.close()
            database = sqlite3.connect(path)
            try:
                self.assertEqual(database.execute('SELECT COUNT(*) FROM observations').fetchone()[0], 2)
            finally:
                database.close()

    def test_capture_only_stores_exact_kickoff_squad(self):
        now = datetime(2026, 8, 28, 20, 45, tzinfo=BERLIN)
        responses = {
            '/leagues/l/ranking': {'us': [{'i': '1', 'n': 'Anna'}]},
            '/leagues/l/managers/1/dashboard': {'tv': 100},
            '/leagues/l/managers/1/squad': {'it': [{'pi': 'p1', 'lo': 0}]},
            '/leagues/l/managers/1/performance': {'it': []},
            '/competitions/1/matchdays': {'it': [{'day': 1, 'it': [
                {'dt': '2026-08-28T18:30:00Z'}]}]},
        }
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'history.sqlite3'
            result = audit_managers(lambda url: responses[url], 'l', '2026-08-15',
                                    history_path=path, now=now, capture_only=True)
            self.assertEqual(result['matchdays'][0]['day'], 1)
            database = sqlite3.connect(path)
            try:
                row = database.execute(
                    "SELECT payload FROM observations WHERE kind='kickoff_squad'").fetchone()
                self.assertIn('p1', row[0])
            finally:
                database.close()


if __name__ == '__main__':
    unittest.main()
