import threading
import unittest
from datetime import date
from types import SimpleNamespace
from unittest.mock import Mock

from advisor_server import AdvisorHandler
from features.advisor_live import LiveKickbase


class PlannerDetailsApiTests(unittest.TestCase):
    def handler(self, path):
        handler = AdvisorHandler.__new__(AdvisorHandler)
        handler.path = path
        handler.valid_host = Mock(return_value=True)
        handler.reply = Mock()
        handler.server = SimpleNamespace(lock=threading.Lock(), kickbase=Mock(),
                                         report={'players': [{'id': '7'}]}, log_event=Mock())
        return handler

    def test_market_history_retains_default_and_allows_longer_bounded_range(self):
        for suffix, limit in [('', 4), ('?limit=365', 365), ('?limit=7', 7)]:
            handler = self.handler('/api/player-market-history/7' + suffix)
            handler.server.kickbase.player_daily_market_changes.return_value = {'changes': []}
            handler.do_GET()
            handler.server.kickbase.player_daily_market_changes.assert_called_once_with('7', limit=limit)
            self.assertEqual(handler.reply.call_args.args[0], 200)

    def test_history_rejects_invalid_limits_and_unknown_players(self):
        for limit in ['0', '366', '-1', 'invalid', '1.5']:
            handler = self.handler('/api/player-market-history/7?limit=' + limit)
            handler.do_GET()
            self.assertEqual(handler.reply.call_args.args[0], 400)
            handler.server.kickbase.player_daily_market_changes.assert_not_called()
        handler = self.handler('/api/player-market-history/other?limit=365')
        handler.do_GET()
        self.assertEqual(handler.reply.call_args.args[0], 404)

    def test_details_assets_are_served_with_expected_content_types(self):
        for path, expected in [('/planner_details.js', 'text/javascript'), ('/planner_details.css', 'text/css')]:
            handler = self.handler(path)
            handler.do_GET()
            status, content, content_type = handler.reply.call_args.args
            self.assertEqual(status, 200)
            self.assertTrue(content)
            self.assertTrue(content_type.startswith(expected))

    def test_full_market_history_is_chronological_and_preserves_zero(self):
        client = LiveKickbase('test', 'test')
        epoch = date(1970, 1, 1)
        first_day = (date(2026, 9, 1) - epoch).days
        client.player_market_histories = Mock(return_value={'7': [
            {'dt': first_day + i, 'mv': 10000000 + i * 1000} for i in range(40)
        ] + [{'dt': first_day + 39, 'mv': 10038000}]})
        all_changes = client.player_daily_market_changes('7', limit=365)['changes']
        self.assertEqual(len(all_changes), 39)
        self.assertEqual(all_changes[0]['change'], 0)
        self.assertEqual(all_changes[0]['percent'], 0)
        self.assertEqual(all_changes[-1]['date'], '2026-09-02')
        self.assertEqual(len(client.player_daily_market_changes('7')['changes']), 4)


if __name__ == '__main__':
    unittest.main()
