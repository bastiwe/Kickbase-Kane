from datetime import datetime
import os
from pathlib import Path
import unittest
from unittest.mock import patch, Mock
from contextlib import ExitStack
import tempfile

import numpy as np
import pandas as pd

from features.budgets import calc_manager_budgets
from features.fast_notifier import table_html
from features.notifier import send_mail
from features.predictions.predictions import (
    REMOVED_REPORT_COLUMNS, add_recommendation_columns, add_player_quality_signals,
    prepare_market_report, join_current_market, live_data_predictions,
)
from overpay_forecast import cached_predictions, refresh_market_players, main as overpay_main
from features.overpay_tool import write_overpay_tool


def players():
    return pd.DataFrame([dict(player_id=i, first_name='Test', last_name=f'Spieler{i}',
        image_url='', team_name=f'Team{i}', position=(i % 4) + 1, player_status='Fit',
        mv=10_000_000, predicted_mv_target=100_000 + i * 1000,
        mv_change_yesterday=50_000, last_season_avg_points=80,
        last_3_points=250, current_season_points=500, lineup_score=250,
        lineup_score_basis='Letzte 3 Spiele', starter_rate=75,
        expires_at=pd.Timestamp('2026-09-10T21:00:00+02:00') + pd.Timedelta(hours=i),
        expires_before_mv_update=True, expires_overnight=False,
        has_open_bid=i == 0, is_listed_for_sale=i == 1,
        purchase_price=9_000_000, squad_profit_loss=1_000_000,
        recommendation='Buy', risk='Before MV update') for i in range(12)])


class LeanReportTests(unittest.TestCase):
    def test_recommendations_do_not_call_removed_calculations(self):
        rows = players()
        rows.loc[0, 'predicted_mv_target'] = -250_000
        with patch('features.predictions.predictions.add_prediction_confidence', side_effect=AssertionError('confidence called')), patch('features.predictions.predictions.psychological_bid', side_effect=AssertionError('bid called')):
            for is_market in [True, False]:
                result = add_recommendation_columns(rows, is_market, report_only=True)
                self.assertFalse(set(REMOVED_REPORT_COLUMNS) & set(result.columns))
            self.assertEqual(result.iloc[0]['recommendation'], 'Sell')

    def test_average_points_retained_without_prior_season_totals(self):
        history = pd.DataFrame({'player_id': [1, 1, 1], 'md': ['2025-11-01', '2025-11-08', '2026-08-30'], 'p': [100, 200, 80]})
        result = add_player_quality_signals(pd.DataFrame({'player_id': [1]}), history, '2026-08-15', report_only=True)
        self.assertEqual(result.iloc[0]['last_season_avg_points'], 150)
        self.assertTrue(pd.isna(result.iloc[0]['last_season_points']))
        self.assertEqual(result.iloc[0]['last_3_points'], 80)

    def test_market_order_and_limits(self):
        market = players().iloc[::-1]
        squad = pd.DataFrame({'team_name': ['Team0'] * 3 + ['Team1'] * 2})
        result = prepare_market_report(market, squad)
        self.assertTrue(result['expires_at'].is_monotonic_increasing)
        self.assertEqual(result.iloc[0]['team_limit_warning'], 'Vereinslimit voll')
        self.assertEqual(result.iloc[1]['team_limit_warning'], 'füllt 3/3')
        self.assertTrue(result.iloc[0]['has_open_bid'])

    def test_budget_skips_overpay_history_and_profiles(self):
        prefix = 'features.budgets.'
        with patch(prefix + 'get_league_activities', return_value=([], [], [])), patch(prefix + 'get_managers', return_value=[('Me', '1')]), patch(prefix + 'get_manager_info', return_value={'tv': 100_000_000}), patch(prefix + 'get_manager_performance', return_value={'name': 'Me', 'tp': 0}), patch(prefix + 'calc_achievement_bonus_by_points', return_value=0), patch(prefix + 'get_budget', return_value=80_000_000), patch(prefix + 'get_username', return_value='Me'), patch(prefix + 'calc_overpay_analysis_by_manager', side_effect=AssertionError('overpay called')), patch(prefix + 'extract_roster_profile', side_effect=AssertionError('roster analysis called')):
            result = calc_manager_budgets('token', 'league', '2026-08-15', 80_000_000, include_overpay=False)
        self.assertNotIn('Avg Overpay', result)
        self.assertEqual(result.iloc[0]['Available Budget'], 113_000_000)

    def test_empty_market(self):
        with patch('features.predictions.predictions.get_league_players_on_market', return_value=[]), patch('features.predictions.predictions.get_players_in_squad', return_value={'it': []}):
            result = join_current_market('token', 'league', players(), report_only=True)
        self.assertTrue(prepare_market_report(result, players()).empty)

    def test_mail_has_no_removed_fields_including_cards_and_legend(self):
        market = prepare_market_report(add_recommendation_columns(players(), True, report_only=True), pd.DataFrame())
        squad = add_recommendation_columns(players(), False, report_only=True)
        hidden = ['player_id', 'expires_before_mv_update', 'expires_overnight']
        market = market.drop(columns=hidden + ['purchase_price', 'squad_profit_loss', 'is_listed_for_sale'])
        squad = squad.drop(columns=hidden + ['expires_at', 'risk', 'has_open_bid'])
        budget = pd.DataFrame([{'User': 'Testmanager', 'Budget': 1000000, 'Team Value': 120000000, 'Max Negative': -39600000, 'Available Budget': 40600000}])
        with patch.dict(os.environ, {'EMAIL_USER': 'test@example.com', 'EMAIL_PASS': 'fake'}), patch('features.notifier.smtplib.SMTP') as smtp:
            send_mail(budget, market, squad, 'test@example.com')
        message = smtp.return_value.__enter__.return_value.send_message.call_args.args[0]
        html = message.get_body(preferencelist=('html',)).get_content()
        for label in ['Kaufart', 'Vertrauen', 'Gegnerdruck', 'Max. Gebot', 'MW-Tendenz', 'Pkt. Vors.', 'Erw. %', 'Sieggebot', 'Overpay', 'Kaufpriorität']:
            self.assertFalse(label in html, f'Removed label still visible: {label}')
        self.assertIn('LI %', html)
        self.assertIn('Summe', html)
        self.assertIn('600.000', html)
        self.assertNotIn('min-width:2050px', html)
        self.assertEqual(list(message.iter_attachments()), [])
        output = Path('test-output/lean-report.html')
        output.parent.mkdir(exist_ok=True)
        output.write_text(html, encoding='utf-8')

    def test_fast_columns(self):
        html = table_html(players(), is_market=False)
        self.assertNotIn('Vertrauen', html)
        self.assertNotIn('Erw. %', html)
        self.assertIn('G/V', html)

    def test_cached_overpay_predictions_expire_without_training(self):
        now = datetime.fromisoformat('2026-09-10T12:00:00+02:00')
        history = pd.DataFrame({'player_id': ['1', '1'], 'date': ['2026-09-08', '2026-09-09'], 'md': ['2026-08-30'] * 2, 'p': [100, 100], 'mv': [1000000, 1100000]})
        snapshot = {'generatedAt': now.isoformat(), 'predictions': {'1': 75000}}
        result = cached_predictions(history, history.tail(1), snapshot, '2026-08-15', now)
        self.assertEqual(result.iloc[0]['predicted_mv_target'], 75000)
        self.assertEqual(result.iloc[0]['mv_change_1d'], 100000)
        stale = cached_predictions(history, history.tail(1), snapshot, '2026-08-15', now.replace(hour=22))
        self.assertTrue(pd.isna(stale.iloc[0]['predicted_mv_target']))
        with self.assertRaisesRegex(RuntimeError, 'Spielerdaten fehlen'):
            cached_predictions(pd.DataFrame(), pd.DataFrame(), None, '2026-08-15')

    def test_fast_model_does_not_invent_longer_forecasts(self):
        rows = players().assign(date='2026-09-10', mv_change_1d=50000, mv_trend_1d=1)
        model = Mock()
        model.predict.return_value = np.full(len(rows), 75000)
        result = live_data_predictions(rows, {'predicted_mv_target': model}, ['mv'], report_only=True)
        self.assertTrue(result['predicted_mv_target_3d'].isna().all())
        self.assertTrue(result['predicted_mv_target_7d'].isna().all())

    def test_live_market_refreshes_prices_and_keeps_uncached_players(self):
        payload = {'it': [{'i': 0, 'mv': 12000000},
                          {'i': 99, 'fn': 'New', 'ln': 'Player', 'mv': 1000000, 'pos': 2, 'tn': 'New Club'}]}
        with patch('overpay_forecast.get_json_with_token', return_value=payload):
            result = refresh_market_players('token', 'league', players()).set_index('player_id')
        self.assertEqual(result.loc[0, 'mv'], 12000000)
        self.assertEqual(result.loc[99, 'last_name'], 'Player')
        self.assertTrue(pd.isna(result.loc[99, 'predicted_mv_target']))

    def test_standalone_overpay_runs_without_forecasts_or_training(self):
        history = players().drop(columns=['mv_change_yesterday']).assign(
            date='2026-09-09', md='2026-08-30', p=100, team_id=1)
        market = [{'id': 3, 'has_open_bid': True, 'is_own_listing': False, 'exp': 3600, 'player_status': 0}]
        squad = {'it': [{'i': 0, 'mv': 10000000, 'fn': 'Test', 'ln': 'Spieler0', 'pos': 1, 'tn': 'Team0'}]}
        budgets = pd.DataFrame([{'User': 'Opponent', 'Budget': 80000000, 'Available Budget': 113000000, 'Team Value': 100000000, 'Avg Overpay': 50000}])
        with tempfile.TemporaryDirectory() as folder, ExitStack() as stack:
            output = Path(folder) / 'overpay.html'
            stack.enter_context(patch.dict(os.environ, {'KICK_USER': 'fake', 'KICK_PASS': 'fake'}))
            stack.enter_context(patch('sys.argv', ['overpay_forecast.py']))
            mocks = {
                'overpay_forecast.load_dotenv': None,
                'overpay_forecast.load_cached_players': (history, history, 'Testcache'),
                'overpay_forecast.read_prediction_snapshot': None,
                'overpay_forecast.login': 'token', 'overpay_forecast.get_league_id': 'league',
                'overpay_forecast.get_user_id': 'me',
                'overpay_forecast.get_json_with_token': {'it': [{'i': 3, 'mv': 10000000}]},
                'overpay_forecast.calc_manager_budgets': budgets,
                'features.predictions.predictions.get_league_players_on_market': market,
                'features.predictions.predictions.get_players_in_squad': squad,
                'features.predictions.predictions.load_own_purchase_prices_from_activities': {},
                'features.predictions.predictions.get_player_info': {},
            }
            for name, value in mocks.items():
                stack.enter_context(patch(name, return_value=value))
            stack.enter_context(patch('overpay_forecast.write_overpay_tool', side_effect=lambda market, budgets: write_overpay_tool(market, budgets, output)))
            overpay_main()
            html = output.read_text(encoding='utf-8')
            self.assertIn('Spieler3', html)
            self.assertNotIn('"expectedChange": 0', html)


if __name__ == '__main__':
    unittest.main()
