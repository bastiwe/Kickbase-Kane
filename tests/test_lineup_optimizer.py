import unittest
from unittest.mock import patch

import pandas as pd

from features.lineup_optimizer import history_context, own_bid_amount, write_lineup_optimizer


class OptimizerTests(unittest.TestCase):
    def test_history_deduplicates_matchdays_and_preserves_zero_points(self):
        today = pd.Timestamp.now()
        start = pd.Timestamp(year=today.year if today.month >= 7 else today.year - 1, month=7, day=1)
        history = pd.DataFrame([
            {'player_id': '1', 'md': str(start.date()), 'p': 0, 'team_id': 1, 'team_name': 'A'},
            {'player_id': '1', 'md': str(start.date()), 'p': 0, 'team_id': 1, 'team_name': 'A'},
            {'player_id': '1', 'md': str((start-pd.Timedelta(days=30)).date()), 'p': 80, 'team_id': 1, 'team_name': 'A'},
        ])
        result = history_context(history, '1')
        self.assertEqual(result['recent'], [0])
        self.assertEqual(result['season'], 0)
        self.assertEqual(result['previous'], 80)

    def test_bid_is_not_asking_price_or_another_managers_bid(self):
        item = {'prc': 12000000, 'ownBid': True,
                'offers': [{'ui': 'other', 'price': 15000000}]}
        self.assertIsNone(own_bid_amount(item, 'me'))
        item['offers'].append({'ui': 'me', 'price': 13000001})
        self.assertEqual(own_bid_amount(item, 'me'), 13000001)

    @patch('features.lineup_optimizer.render_optimizer')
    @patch('features.lineup_optimizer.get_budget', return_value=-1000000)
    @patch('features.lineup_optimizer.get_json_with_token')
    @patch('features.lineup_optimizer.get_players_in_squad')
    def test_own_listing_is_deduplicated_and_unmatched_bid_retained(self, squad, market, budget, render):
        squad.return_value = {'it': [{'i': '1', 'fn': 'Own', 'ln': 'Player', 'pos': 1, 'mv': 1000000}]}
        market.return_value = {'it': [
            {'i': '1', 'hasBid': True},
            {'i': '2', 'fn': 'New', 'ln': 'Player', 'pos': 4, 'hasBid': True},
            {'i': '3', 'hasBid': False},
        ]}
        write_lineup_optimizer('token', 'league', 'me', pd.DataFrame(), pd.DataFrame(columns=['player_id']))
        payload = render.call_args.args[0]
        self.assertEqual([p['id'] for p in payload['players']], ['1', '2'])
        self.assertIsNone(payload['players'][1]['bid'])
        self.assertEqual(payload['budget'], -1000000)


if __name__ == '__main__':
    unittest.main()
