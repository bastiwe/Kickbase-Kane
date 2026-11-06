from datetime import datetime, timezone
from http.client import HTTPConnection
import json
import threading
import unittest
from unittest.mock import Mock

import requests

from advisor_server import create_server
from features.live_matchday import LiveMatchday, action_data


def fixture():
    user1 = {'i': 'a', 'n': 'Anna', 'sp': 100, 'spl': 2, 'mdp': 9}
    user2 = {'i': 'b', 'n': 'Ben', 'sp': 200, 'spl': 1, 'mdp': 50}
    responses = {
        '/competitions/1/matchdays': {'day': 1, 'it': [
            {'day': 1, 'it': [{'mi': '100', 'dt': '2026-08-28T18:30:00Z', 't1sy': 'AAA', 't2sy': 'BBB', 'st': 2, 't1g': 2, 't2g': 1}]},
            {'day': 2, 'it': [{'mi': '200', 'dt': '2030-08-28T18:30:00Z', 'st': 0}]}]},
        '/leagues/l/ranking?dayNumber=1': {'ti': 'Testliga', 'us': [user1, user2]},
        '/leagues/l/ranking?dayNumber=2': {'ti': 'Testliga', 'us': [user1, user2]},
        '/live/eventtypes': {'it': [{'i': 1, 'ti': 'Pass'}, {'i': 2, 'ti': 'Possession lost'}]},
    }
    for mid, ids in [('a', ['1', '2']), ('b', ['3'])]:
        responses[f'/leagues/l/managers/{mid}/squad'] = {'it': [
            {'pi': pid, 'pn': 'Spieler ' + pid, 'lo': index, 'pos': 3, 'ap': 100, 'tfhmvt': 1000}
            for index, pid in enumerate(ids)]}
        responses[f'/leagues/l/managers/{mid}/dashboard'] = {'tv': 12300000, 'mdw': 1, 'ap': 1100}
        for day in [1, 2]:
            responses[f'/leagues/l/users/{mid}/teamcenter?dayNumber={day}'] = {
                'us': [{'i': 'a', 'lp': [1, 2], 'mdp': 9}, {'i': 'b', 'lp': [3], 'mdp': 50}],
                'lp': [{'i': pid, 'n': 'Spieler ' + pid, 'p': {'1': 10, '2': -1, '3': 50}[pid], 'mi': 100}
                       for pid in ids] if day == 1 else [],
                'nlp': [{'i': '99', 'n': 'Bankspieler', 'p': 9999}]}
    responses['/competitions/1/playercenter/1?dayNumber=1&leagueId=l'] = {
        'i': '1', 'n': 'Spieler 1', 'mi': 100, 'p': 10, 'events': [
            {'ei': 'correction', 'eti': 1, 'p': -1, 'mt': 20, 'cei': 'pass', 'att': 3},
            {'ei': 'late', 'eti': 2, 'p': -1, 'mt': 80},
            {'ei': 'pass', 'eti': 1, 'p': 12, 'mt': 20}]}
    client = Mock()
    client.get.side_effect = lambda path: responses[path]
    return responses, client


class LiveMatchdayTests(unittest.TestCase):
    def setUp(self):
        self.responses, self.client = fixture()
        self.service = LiveMatchday(lambda: self.client)

    def test_starters_are_manager_specific_sorted_and_bench_is_excluded(self):
        snapshot = self.service.snapshot('l', 1)
        self.assertEqual([m['id'] for m in snapshot['managers']], ['b', 'a'])
        anna = snapshot['managers'][1]
        self.assertEqual([p['id'] for p in anna['lineup']], ['1', '2'])
        self.assertEqual(anna['dayPoints'], 9)
        self.assertEqual(anna['valueChange'], 2000)
        self.assertFalse(any(p['id'] == '99' for m in snapshot['managers'] for p in m['lineup']))

    def test_cache_reuses_bulk_teamcenter_without_per_player_live_polling(self):
        self.service.snapshot('l', 1)
        count = self.client.get.call_count
        self.service.snapshot('l', 1)
        self.assertEqual(self.client.get.call_count, count)
        self.assertFalse(any('playercenter' in call.args[0] for call in self.client.get.call_args_list))

    def test_actions_keep_corrections_and_group_to_the_actual_total(self):
        self.service.snapshot('l', 1)
        result = self.service.player('l', 1, '1')
        self.assertEqual(result['bookedPoints'], 10)
        self.assertEqual(result['difference'], 0)
        self.assertEqual(sum(group['points'] for group in result['grouped']), 10)
        passes = next(group for group in result['grouped'] if group['type'] == '1')
        self.assertEqual(passes['points'], 11)
        self.assertEqual(passes['corrections'], 1)
        self.assertEqual([event['id'] for event in result['chronological']], ['pass', 'correction', 'late'])

    def test_unknown_player_is_rejected_before_playercenter_request(self):
        with self.assertRaises(PermissionError):
            self.service.player('l', 1, '99')
        self.assertFalse(any('playercenter' in call.args[0] for call in self.client.get.call_args_list))

    def test_future_preview_has_no_previous_match_points_or_actions(self):
        result = self.service.snapshot('l', 2)
        self.assertTrue(all(m['provisional'] for m in result['managers']))
        self.assertTrue(all(p['points'] is None for m in result['managers'] for p in m['lineup']))
        actions = self.service.player('l', 2, '1')
        self.assertIsNone(actions['points'])
        self.assertFalse(actions['available'])

    def test_previous_match_returned_by_api_cannot_leak_into_selected_day(self):
        self.responses['/competitions/1/playercenter/1?dayNumber=1&leagueId=l']['mi'] = 999
        result = self.service.player('l', 1, '1')
        self.assertIsNone(result['points'])
        self.assertEqual(result['chronological'], [])

    def test_duplicate_events_missing_points_and_mismatch_remain_visible(self):
        result = action_data({'i': '1', 'p': 100, 'events': [
            {'ei': '1', 'eti': 1, 'p': 5}, {'ei': '1', 'eti': 1, 'p': 5}, {'ei': '2', 'eti': 1}]}, {})
        self.assertEqual(result['bookedPoints'], 5)
        self.assertEqual(result['difference'], 95)
        self.assertFalse(result['complete'])
        self.assertEqual(len(result['chronological']), 2)

    def test_expired_token_is_retried_once_and_optional_failure_is_marked(self):
        response = requests.Response()
        response.status_code = 401
        self.client.get.side_effect = [requests.HTTPError(response=response), {'it': []}]
        self.assertEqual(self.service.get('/test'), {'it': []})
        self.assertEqual(self.client.get.call_count, 2)
        self.client.get.side_effect = requests.ConnectionError()
        notes = []
        self.assertEqual(self.service.optional('/missing', notes, 'Kader'), {})
        self.assertEqual(notes, ['Kader derzeit nicht abrufbar.'])

    def test_routes_assets_and_invalid_queries(self):
        server = create_server(0, {'players': [], 'league': 'l'})
        server.kickbase = self.client
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            for path, expected in [('/matchday', 200), ('/live_matchday.css', 200), ('/live_matchday.js', 200),
                                   ('/api/live-matchday?day=1', 200), ('/api/live-matchday?day=bad', 400),
                                   ('/api/live-matchday/player/99?day=1', 404), ('/api/live-matchday?day=35', 400)]:
                connection = HTTPConnection('127.0.0.1', server.server_port)
                connection.request('GET', path)
                response = connection.getresponse()
                response.read()
                self.assertEqual(response.status, expected, path)
                connection.close()
        finally:
            server.shutdown(); server.server_close(); thread.join()


if __name__ == '__main__':
    unittest.main()
