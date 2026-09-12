from datetime import datetime, timezone
import unittest
from features.player_details import build_details


class PlayerDetailTests(unittest.TestCase):
    def test_live_fields_minutes_events_and_schedule(self):
        now = datetime(2026, 9, 12, tzinfo=timezone.utc)
        profile = {'tid': '2', 'sec': 11508, 'g': 0, 'a': 2, 'y': 0, 'r': 0, 'ap': 279}
        games = [
            {'mi': '1', 'md': '2026-09-05T16:30:00Z', 'mdst': 2, 'p': 254, 'mp': "96'", 'pt': '2', 't1': '8', 't2': '2', 'k': [3, 3]},
            {'mi': '2', 'md': '2026-09-13T15:30:00Z', 'mdst': 0, 't1': '8', 't2': '2'},
            {'mi': '3', 'md': '2026-09-19T15:30:00Z', 'mdst': 0, 't1': '2', 't2': '8'},
        ]
        result = build_details(profile, {'it': [{'n': 'Bundesliga', 'ph': games}]},
                               {'it': [{'tid': '8', 'tn': 'Hamburg', 'cpl': 10}]}, now)
        self.assertEqual(result['minutes'], 191.8)
        self.assertEqual(result['goals'], 0)
        self.assertEqual(result['assists'], 2)
        self.assertEqual(result['history'][0]['minutes'], 96)
        self.assertIsNone(result['history'][0]['cards'])
        self.assertIsNone(result['history'][0]['goals'])
        self.assertEqual(result['fixtures'][0]['venue'], 'Auswärts')
        self.assertEqual(result['fixtures'][0]['date'], '13.09.2026, 17:30')
        self.assertEqual(result['fixtures'][1]['venue'], 'Heim')
        self.assertEqual(result['l3'], 254)

    def test_missing_values_not_zero(self):
        result = build_details({}, {'it': []}, {'it': []})
        self.assertIsNone(result['minutes'])
        self.assertIsNone(result['goals'])
        self.assertIsNone(result['cards'])
        self.assertEqual(result['history'], [])
