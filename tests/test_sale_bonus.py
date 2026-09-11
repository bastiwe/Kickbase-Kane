import unittest
from unittest.mock import Mock

from features.sale_bonus import calculate_sale_bonus, load_sale_bonus
from features.ai_advisor import prepare_context
from test_ai_advisor import fixture


def context():
    return {'rules': [
        {'id': 700, 'threshold': 100, 'reward': 10, 'repeatable': False, 'earned': False, 'name': 'Einmalig'},
        {'id': 701, 'threshold': 300, 'reward': 25, 'repeatable': True, 'earned': True, 'name': 'Bronze'},
        {'id': 702, 'threshold': 500, 'reward': 50, 'repeatable': True, 'earned': True, 'name': 'Silber'}],
        'purchases': {'a': {'price': 100, 'market': True}, 'b': {'price': 100, 'market': True}}}


class SaleBonusTests(unittest.TestCase):
    def test_thresholds_highest_tier_and_repeatability(self):
        c = context()
        self.assertEqual(calculate_sale_bonus(c, {'a': 399}, True)['total'], 10)
        self.assertEqual(calculate_sale_bonus(c, {'a': 400}, True)['total'], 25)
        self.assertEqual(calculate_sale_bonus(c, {'a': 600, 'b': 600}, True)['total'], 100)

    def test_once_only_and_previously_earned(self):
        c = context()
        self.assertEqual(calculate_sale_bonus(c, {'a': 200, 'b': 200}, True)['total'], 10)
        c['rules'][0]['earned'] = True
        self.assertEqual(calculate_sale_bonus(c, {'a': 200}, True)['total'], 0)

    def test_unknown_cost_nonmarket_and_disabled(self):
        c = context()
        c['purchases']['a']['market'] = False
        self.assertEqual(calculate_sale_bonus(c, {'a': 900, 'missing': 900}, True)['total'], 0)
        self.assertEqual(calculate_sale_bonus(c, {'b': 900})['total'], 0)
        self.assertEqual(calculate_sale_bonus(c, {'b': None}, True)['total'], 0)

    def test_adviser_budget_respects_lock_and_bonus_flag(self):
        report, state = fixture()
        report['saleBonus'] = context()
        report['saleBonus']['purchases']['bench'] = {'price': 0, 'market': True}
        state['sellbench'] = True
        state['bonusEnabled'] = True
        result = prepare_context(report, state)['checkedCurrentPlan']
        self.assertEqual(result['saleBonusEstimate'], 10)
        self.assertEqual(result['endBudget'], 160)
        state['plans']['bench']['locked'] = True
        result = prepare_context(report, state)['checkedCurrentPlan']
        self.assertEqual(result['saleBonusEstimate'], 0)
        self.assertEqual(result['endBudget'], 50)

    def test_loader_latest_purchase_and_seller_exclusion(self):
        client = Mock()
        def get(path):
            if path == '/user/settings':
                return {'u': {'i': 'u', 'unm': 'Owner'}}
            if 'achievements' in path:
                return {'er': 10, 'isrp': True}
            return {'af': [
                {'t': 15, 'dt': '2099-08-01', 'data': {'pi': 'a', 'byr': 'Owner', 't': 1, 'trp': 100}},
                {'t': 15, 'dt': '2099-08-02', 'data': {'pi': 'a', 'slr': 'Owner', 't': 2}},
                {'t': 15, 'dt': '2099-08-03', 'data': {'pi': 'a', 'byr': 'Owner', 'slr': 'Other', 't': 3, 'trp': 200}}]}
        client.get.side_effect = get
        result = load_sale_bonus(client, {'league': 'l', 'user': 'u'})
        self.assertEqual(result['purchases']['a']['price'], 200)
        self.assertFalse(result['purchases']['a']['market'])
