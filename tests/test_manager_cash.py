"""Missing history must not invent cash for any league member."""
from contextlib import ExitStack
import unittest
from unittest.mock import patch

import pandas as pd

from features.budgets import calc_manager_budgets
from features.overpay_tool import build_manager_payload


class ManagerCashTests(unittest.TestCase):
    names = ['Johannes', 'bastiwe', 'Stefan', 'danwe', 'Sebastian']

    def budgets(self, owner, activities):
        prefix = 'features.budgets.'
        with ExitStack() as stack:
            values = {
                'get_league_activities': (activities, [], []),
                'get_managers': [(name, str(i)) for i, name in enumerate(self.names)],
                'get_budget': 1_543_778 if owner else None,
                'get_username': owner,
                'daily_login_bonus_total': 0,
            }
            for name, value in values.items():
                stack.enter_context(patch(prefix + name, return_value=value))
            stack.enter_context(patch(prefix + 'get_manager_info', side_effect=[
                {'tv': 200_000_000 + i * 15_000_000, 'prft': i * 7_000_000}
                for i in range(len(self.names))
            ]))
            stack.enter_context(patch(prefix + 'get_manager_performance', side_effect=[
                {'name': name, 'tp': 0, 'matchdays': []} for name in self.names
            ]))
            return calc_manager_budgets(
                'token', 'league', '2026-08-15', 80_000_000, include_overpay=False)

    def test_every_manager_is_unknown_unless_own_api_balance_is_available(self):
        partial = [{'dt': '2026-09-01T12:00:00Z', 'byr': 'Sebastian',
                    'slr': None, 'pi': '1', 'trp': 110_000_000}]
        for owner in [None, *self.names]:
            for activities in [[], partial]:
                with self.subTest(owner=owner, empty_feed=not activities):
                    result = self.budgets(owner, activities)
                    self.assertEqual(set(result['User']), set(self.names))
                    payload = {row['name']: row for row in build_manager_payload(result)}
                    for _, row in result.iterrows():
                        if row['User'] == owner:
                            self.assertEqual(row['Budget'], 1_543_778)
                            self.assertEqual(row['Cash Basis'], 'API (eigener Kontostand)')
                        else:
                            self.assertTrue(pd.isna(row['Budget']))
                            self.assertTrue(pd.isna(row['Available Budget']))
                            self.assertEqual(row['Cash Basis'], 'Unbekannt (Historie unvollständig)')
                            self.assertIsNone(payload[row['User']]['availableBudget'])

    def test_full_ledger_preserves_negative_estimates_instead_of_clamping_to_zero(self):
        result = self.budgets(None, [
            {'dt': '2026-08-15T12:00:00Z', 'byr': name, 'slr': None,
             'pi': str(i), 'trp': 90_000_000}
            for i, name in enumerate(self.names)
        ])
        for _, row in result.iterrows():
            self.assertEqual(row['Budget'], -10_000_000)
            self.assertEqual(row['Cash Basis'], 'Aktivitätenfeed (Schätzung)')


if __name__ == '__main__':
    unittest.main()
