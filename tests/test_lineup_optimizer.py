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
        self.assertEqual(result['average'], 80)

    def test_history_averages_last_three_and_whole_season(self):
        today = pd.Timestamp.now()
        start = pd.Timestamp(year=today.year if today.month >= 7 else today.year - 1, month=7, day=1)
        rows = [
            {'player_id': '1', 'md': str((start + pd.Timedelta(days=i)).date()),
             'p': points, 'team_id': 1, 'team_name': 'A'}
            for i, points in enumerate([100, 0, 60, 120])
        ]
        rows.append(dict(rows[-1]))
        result = history_context(pd.DataFrame(rows), '1')
        self.assertEqual(result['l3'], 60)
        self.assertEqual(result['season'], 70)

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

    @patch('features.lineup_optimizer.get_player_performance', return_value=[])
    @patch('features.lineup_optimizer.get_player_info', return_value={'player_id': '1', 'team_name': 'A', 'team_id': 1})
    @patch('features.lineup_optimizer.render_optimizer')
    @patch('features.lineup_optimizer.get_budget', return_value=100)
    @patch('features.lineup_optimizer.get_json_with_token', return_value={'it': []})
    @patch('features.lineup_optimizer.get_players_in_squad', return_value={'it': [{'i': '1', 'pos': 1}]})
    def test_missing_cache_fetches_only_candidate_history(self, squad, market, budget, render, info, performance):
        write_lineup_optimizer('token', 'league', 'me', pd.DataFrame(), pd.DataFrame(columns=['player_id']),
                               refresh_missing_history=True, history_df=pd.DataFrame(columns=['player_id']))
        info.assert_called_once_with('token', 1, '1')
        performance.assert_called_once_with('token', 1, '1', 50, 1)
        self.assertEqual(render.call_args.args[0]['players'][0]['team'], 'A')

if __name__ == '__main__':
    unittest.main()
