from datetime import datetime
from pathlib import Path
import sqlite3
import tempfile
import unittest

from features.cash_reconstruction import BERLIN
from features.manager_history import (
    HistoryStore, audit_managers, goal_machine_events, historical_roster,
    lineup_estimate, mvp_events,
)
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

    def test_goal_machine_uses_squad_goals_and_manager_points_as_tiebreaker(self):
        base = {'roster': {'issues': []}, 'fetch_errors': []}
        entries = {
            'A': {**base, 'goals': {'one': 2}, 'md': {'mdp': 1_000}},
            'B': {**base, 'goals': {'two': 1, 'three': 1}, 'md': {'mdp': 1_200}},
            'C': {**base, 'goals': {'four': 1}, 'md': {'mdp': 1_500}},
        }
        events = {event['manager']: event for event in goal_machine_events(3, entries)}
        self.assertEqual(events['B']['amount'], 250_000)
        self.assertEqual(events['A']['amount'], 0)
        self.assertEqual(events['C']['amount'], 0)

    def test_goal_machine_keeps_equal_goals_and_points_open(self):
        base = {'roster': {'issues': []}, 'fetch_errors': [], 'md': {'mdp': 1_000}}
        entries = {
            'A': {**base, 'goals': {'one': 1}},
            'B': {**base, 'goals': {'two': 1}},
        }
        events = {event['manager']: event for event in goal_machine_events(3, entries)}
        self.assertEqual(events['A']['status'], 'offen')
        self.assertEqual(events['A']['amount'], 0)
        self.assertEqual(events['A']['amount_max'], 250_000)

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
