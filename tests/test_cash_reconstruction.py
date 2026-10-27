import unittest
from unittest.mock import Mock

from features.cash_reconstruction import fetch_manager_transfers, reconstruct_cash


class CashReconstructionTests(unittest.TestCase):
    def calculate(self, rows, performance=None, squad=None):
        return reconstruct_cash(rows, performance or {'it': []}, squad or {'it': []}, 0,
                                start_date='2026-08-15', as_of='2026-10-24T12:00:00+02:00')

    def trade(self, date, kind, price, pid='1', **extra):
        return {'dt': date, 'tty': kind, 'trp': price, 'pi': pid, **extra}

    def test_reset_boundary_is_berlin_and_assigned_sales_are_cash_not_bonus(self):
        result = self.calculate([
            self.trade('2026-08-14T21:59:59Z', 1, 99_000_000),
            self.trade('2026-08-14T22:00:00Z', 2, 10_000_000),
        ])
        self.assertEqual(result['cash_partial_estimate'], 96_750_000)
        self.assertEqual(result['transfer_bonuses'], 0)
        self.assertEqual(result['transfer_count'], 1)

    def test_profit_tiers_stack_but_manager_transfers_do_not_qualify(self):
        rows = []
        for pid, extra in [('1', {}), ('2', {'othnm': 'Other'})]:
            rows.extend([self.trade('2026-08-16T00:00:00Z', 1, 1_000_000, pid, **extra),
                         self.trade('2026-08-17T00:00:00Z', 2, 6_000_000, pid)])
        result = self.calculate(rows)
        self.assertEqual(result['transfer_net'], 10_000_000)
        self.assertEqual(result['transfer_bonuses'], 750_000)

    def test_lucky_hand_ignores_qualifying_sales_before_season_start(self):
        rows = [
            self.trade('2025-08-01', 1, 1_000_000),
            self.trade('2025-08-02', 2, 2_000_000),
            self.trade('2026-08-16', 1, 1_000_000, '2'),
            self.trade('2026-08-17', 2, 3_000_000, '2'),
        ]
        result = self.calculate(rows)
        self.assertEqual(result['lucky_hand_bonus'], 100_000)
        self.assertEqual(result['lucky_hand_event']['evidence']['sale_date'], '2026-08-17')

    def test_lucky_hand_is_awarded_for_every_qualifying_sale(self):
        rows = [
            self.trade('2026-08-16', 1, 1_000_000),
            self.trade('2026-08-17', 2, 2_000_000),
            self.trade('2026-08-18', 1, 1_000_000, '2'),
            self.trade('2026-08-19', 2, 4_000_000, '2'),
        ]
        result = self.calculate(rows)
        self.assertEqual(result['lucky_hand_bonus'], 200_000)
        self.assertEqual(result['lucky_hand_event']['count'], 2)
        self.assertEqual(result['cash_partial_estimate'], 91_200_000)

    def test_lucky_hand_ignores_manager_to_manager_transfer(self):
        rows = [
            self.trade('2026-08-16', 1, 1_000_000, othnm='Other'),
            self.trade('2026-08-17', 2, 5_000_000),
        ]
        self.assertEqual(self.calculate(rows)['lucky_hand_bonus'], 0)

    def test_live_and_previous_season_points_are_excluded(self):
        performance = {'it': [
            {'sid': '1', 'it': [{'md': '2025-09-01', 'mdp': 5000, 'cur': False, 'tw': True}]},
            {'sid': '2', 'it': [
                {'md': '2026-09-01', 'mdp': 1600, 'cur': False, 'tw': True},
                {'md': '2026-10-23', 'mdp': 2100, 'cur': True, 'tw': True},
                {'md': '2026-10-30', 'cur': False},
            ]},
        ]}
        result = self.calculate([], performance)
        self.assertEqual(result['settled_points_reward'], 1_600_000)
        self.assertEqual(result['matchday_wins'], 1_000_000)
        self.assertEqual(result['matchday_thresholds'], 750_000)
        self.assertEqual(result['season_milestone_bonus'], 100_000)

    def test_ranking_event_can_settle_current_matchday(self):
        performance = {'it': [{'sid': '2', 'it': [
            {'day': 7, 'md': '2026-10-23', 'mdp': 2100, 'cur': True, 'tw': True},
        ]}]}
        result = reconstruct_cash([], performance, {'it': []}, 0,
                                  start_date='2026-08-15',
                                  as_of='2026-10-27T12:00:00+01:00', settled_days={7})
        self.assertEqual(result['settled_points_reward'], 2_100_000)
        self.assertEqual(result['matchday_wins'], 1_000_000)
        self.assertEqual(result['matchday_thresholds'], 1_750_000)

    def test_cumulative_win_and_season_point_milestones_stack(self):
        matchdays = [{'md': f'2026-09-{day:02d}', 'day': day, 'mdp': 1000,
                      'cur': False, 'tw': True} for day in range(1, 6)]
        matchdays.append({'md': '2026-09-06', 'day': 6, 'mdp': 100,
                          'cur': False, 'tw': False})
        result = self.calculate([], {'it': [{'sid': '2', 'it': matchdays}]})
        self.assertEqual(result['season_milestone_bonus'], 1_850_000)
        self.assertEqual([event['code'] for event in result['season_milestone_events']],
                         ['season_points_1000', 'matchday_wins_3',
                          'matchday_wins_5', 'season_points_5000'])

    def test_transfer_count_milestones_and_long_bench_are_reconstructed(self):
        rows = []
        for index in range(25):
            rows.extend([self.trade(f'2026-09-{index + 1:02d}T10:00:00', 1, 100, str(index)),
                         self.trade(f'2026-09-{index + 1:02d}T11:00:00', 2, 100, str(index))])
        squad = {'it': [{'pi': str(index + 100), 'mv': 100, 'mvgl': 0} for index in range(24)]}
        result = self.calculate(rows, squad=squad)
        self.assertEqual(result['season_milestone_bonus'], 450_000)
        self.assertEqual(result['season_milestone_state']['transfer_count'], 50)
        self.assertEqual(result['season_milestone_state']['max_roster_size'], 25)

    def test_pages_are_loaded_until_reset_is_crossed(self):
        page = [self.trade('2026-08-18T10:00:00Z', 1, i, str(i)) for i in range(25)]
        get = Mock(side_effect=[{'it': page}, {'it': [self.trade('2025-09-01', 1, 1)]}])
        rows = fetch_manager_transfers(get, 'league', 'manager', '2026-08-15')
        self.assertEqual(len(rows), 25)
        self.assertTrue(get.call_args.args[0].endswith('start=25'))

    def test_repeated_page_cannot_claim_complete_history(self):
        page = [self.trade('2026-08-18', 1, i, str(i)) for i in range(25)]
        with self.assertRaises(ValueError):
            fetch_manager_transfers(Mock(return_value={'it': page}), 'l', 'm', '2026-08-15')

    def test_current_purchase_prices_are_independent_cross_check(self):
        result = self.calculate([self.trade('2026-08-18', 1, 123)],
                                squad={'it': [{'pi': '1', 'mv': 150, 'mvgl': 27, 'prc': 124}]})
        self.assertEqual(result['purchase_price_mismatches'], ['1'])
        self.assertEqual(result['cash_partial_estimate'], 86_749_877)

    def test_initial_squad_assumption_changes_only_profile_scenario(self):
        args = dict(transfers=[], performance={'it': []},
                    squad={'it': [{'pi': '1', 'mv': 120_000_000, 'mvgl': 20_000_000}]},
                    profile_profit=0, start_date='2026-08-15',
                    as_of='2026-10-24T12:00:00+02:00')
        result = reconstruct_cash(**args)
        self.assertEqual(result['profile_cash_scenario'], 86_650_000)
        other = reconstruct_cash(**args, initial_squad_value=101_000_000)
        self.assertEqual(other['profile_cash_scenario'], 87_650_000)
        self.assertEqual(other['cash_partial_estimate'], result['cash_partial_estimate'])


if __name__ == '__main__':
    unittest.main()
