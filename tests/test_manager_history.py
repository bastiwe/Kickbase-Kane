from datetime import datetime
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from features.cash_reconstruction import BERLIN
from features.manager_history import (
    HistoryStore, audit_managers, goal_machine_events, historical_roster,
    lineup_estimate, mvp_events, settled_matchday_days, confirmed_lineup, teamcenter_entry,
)
from manager_history import kickoff_due


class ManagerHistoryTests(unittest.TestCase):
    def teamcenter(self):
        return {'us': [{'i': '1', 'lp': list(range(1, 12)), 'mdp': 1100}],
                'lp': [{'i': str(i), 'p': 100, 'k': []} for i in range(1, 12)],
                'nlp': [{'i': 'bench', 'p': 500, 'k': [1, 1, 1]}]}

    def test_teamcenter_uses_historical_starters_not_bench(self):
        entry = teamcenter_entry(self.teamcenter(), '1', 1100)
        self.assertEqual(len(entry['points']), 11)
        self.assertNotIn('bench', entry['points'])
        self.assertEqual(sum(entry['goals'].values()), 0)

    def test_teamcenter_rejects_mismatched_scores_and_player_sets(self):
        with self.assertRaises(ValueError):
            teamcenter_entry(self.teamcenter(), '1', 1200)
        payload = self.teamcenter()
        payload['lp'][0]['i'] = 'bench'
        with self.assertRaises(ValueError):
            teamcenter_entry(payload, '1', 1100)

    def test_known_historical_lineup_can_have_empty_slots_and_zero_appearances(self):
        payload = {'us': [{'i': '1', 'lp': [1, 2], 'mdp': 100}],
                   'lp': [{'i': '1', 'p': 100, 'k': []}, {'i': '2', 'k': []}]}
        entry = teamcenter_entry(payload, '1', 100)
        estimate = lineup_estimate(entry['roster']['players'], entry['points'], 100,
                                   goals=entry['goals'], fixed_lineup=True)
        self.assertEqual(estimate['solutions'], 1)
        self.assertEqual(estimate['goals_min'], 0)

    def test_audit_replaces_reconstruction_with_api_history_without_double_counting(self):
        now = datetime(2026, 9, 1, 20, 0, tzinfo=BERLIN)
        responses = {
            '/leagues/l/ranking': {'us': [{'i': '1', 'n': 'Anna'}]},
            '/leagues/l/managers/1/dashboard': {'tv': 100, 'prft': 0},
            '/leagues/l/managers/1/squad': {'it': []},
            '/leagues/l/managers/1/performance': {'it': [{'sid': '42', 'it': [
                {'day': 1, 'md': '2026-08-28T18:30:00Z', 'mdp': 1100,
                 'cur': False, 'tw': True}]}]},
            '/user/settings': {'u': {'unm': 'Anna'}},
            '/leagues/l/me/budget': {'b': 123},
            '/leagues/l/settings': {}, '/leagues/l/user/achievements': {},
            '/leagues/l/activitiesFeed?max=5000': {'af': []},
            '/leagues/l/users/1/teamcenter?dayNumber=1': self.teamcenter(),
        }
        def get(url):
            return responses[url]
        with tempfile.TemporaryDirectory() as folder, patch(
                'features.manager_history.fetch_manager_transfers', return_value=[]):
            args = dict(history_path=Path(folder) / 'history.sqlite3',
                        output_dir=Path(folder) / 'output', now=now)
            first = audit_managers(get, 'l', '2026-08-15', **args).attrs['manager_audit']
            second = audit_managers(get, 'l', '2026-08-15', **args).attrs['manager_audit']
            self.assertEqual(first['errors']['teamcenter'], {})
            self.assertEqual(first['errors']['player_performance'], {})
            self.assertEqual(first['managers']['Anna']['additional_bonus_min'], 0)
            self.assertEqual(first['managers']['Anna']['matchday_wins'], 1_000_000)
            self.assertEqual(first['managers']['Anna']['matchday_thresholds'], 250_000)
            self.assertEqual(first['managers']['Anna']['estimated_cash'],
                             second['managers']['Anna']['estimated_cash'])
            self.assertEqual(len(first['events']), len(second['events']))
            db = sqlite3.connect(args['history_path'])
            try:
                raw = db.execute("SELECT COUNT(*) FROM observations WHERE kind='teamcenter'").fetchone()[0]
                self.assertEqual(raw, 2)
            finally:
                db.close()

    def test_ranking_event_finalizes_current_matchday(self):
        feed = {'af': [
            {'t': 17, 'dt': '2026-10-26T17:57:50Z', 'data': {'day': 7, 'pl': 1}},
            {'t': 22, 'dt': '2026-10-27T05:45:33Z', 'data': {'day': 74}},
        ]}
        self.assertEqual(settled_matchday_days(feed, '2026-08-15'), {7})

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

    def test_confirmed_bench_excludes_player_bonuses_and_goals(self):
        players = [str(i) for i in range(12)]
        points = {pid: 10 for pid in players}
        points['0'], points['11'] = 229, 500
        goals = {pid: 0 for pid in players}
        goals['0'], goals['11'] = 1, 3
        roster = confirmed_lineup({'players': players, 'issues': []},
                                  {'bench': ['11'], 'source': 'Nutzerbestätigung'})
        estimate = lineup_estimate(roster['locked_lineup'], points, 329, goals=goals)
        self.assertEqual(estimate['solutions'], 1)
        self.assertEqual(estimate['bonus_min'], 100_000)
        self.assertEqual(estimate['goals_min'], 1)
        self.assertNotIn('11', estimate['possibly_selected'])

    def test_player_point_tiers_are_awarded_once_per_manager(self):
        players = [str(i) for i in range(11)]
        points = {pid: 0 for pid in players}
        points['0'], points['1'] = 365, 221
        estimate = lineup_estimate(players, points, 586)
        self.assertEqual(estimate['bonus_min'], 600_000)

    def test_mvp_ignores_bench_player_with_higher_points(self):
        base = {'roster': {'issues': []}, 'fetch_errors': []}
        entries = {
            'A': {**base, 'points': {'bench': 500, 'starter': 229},
                  'lineup': {'solutions': 1, 'always_selected': ['starter'],
                             'possibly_selected': ['starter']}},
            'B': {**base, 'points': {'star': 365},
                  'lineup': {'solutions': 1, 'always_selected': ['star'],
                             'possibly_selected': ['star']}},
        }
        events = {event['manager']: event for event in mvp_events(7, entries)}
        self.assertEqual(events['B']['amount'], 1_000_000)
        self.assertEqual(events['A']['amount'], 0)

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

    def test_goal_machine_uses_starting_goals_and_manager_points_as_tiebreaker(self):
        base = {'roster': {'issues': []}, 'fetch_errors': []}
        entries = {
            'A': {**base, 'goals': {'one': 2, 'bench': 3}, 'md': {'mdp': 1_000},
                  'lineup': {'goals_min': 2, 'goals_max': 2}},
            'B': {**base, 'goals': {'two': 1, 'three': 1}, 'md': {'mdp': 1_200},
                  'lineup': {'goals_min': 2, 'goals_max': 2}},
            'C': {**base, 'goals': {'four': 1}, 'md': {'mdp': 1_500},
                  'lineup': {'goals_min': 1, 'goals_max': 1}},
        }
        events = {event['manager']: event for event in goal_machine_events(3, entries)}
        self.assertEqual(events['B']['amount'], 250_000)
        self.assertEqual(events['A']['amount'], 0)
        self.assertEqual(events['C']['amount'], 0)

    def test_goal_machine_keeps_equal_goals_and_points_open(self):
        base = {'roster': {'issues': []}, 'fetch_errors': [], 'md': {'mdp': 1_000},
                'lineup': {'goals_min': 1, 'goals_max': 1}}
        entries = {
            'A': {**base, 'goals': {'one': 1}},
            'B': {**base, 'goals': {'two': 1}},
        }
        events = {event['manager']: event for event in goal_machine_events(3, entries)}
        self.assertEqual(events['A']['status'], 'offen')
        self.assertEqual(events['A']['amount'], 0)
        self.assertEqual(events['A']['amount_max'], 250_000)

    def test_goal_machine_does_not_award_uncertain_lineup_goals(self):
        entry = {'roster': {'issues': []}, 'fetch_errors': [], 'md': {'mdp': 1_000},
                 'lineup': {'goals_min': 1, 'goals_max': 3}}
        event = goal_machine_events(7, {'A': entry})[0]
        self.assertEqual(event['status'], 'offen')
        self.assertIsNone(event['amount'])

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
