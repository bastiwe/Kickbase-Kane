from pathlib import Path
import unittest


class DashboardUiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        root = Path(__file__).parents[1] / 'features'
        cls.javascript = (root / 'dashboard.js').read_text(encoding='utf-8')
        cls.styles = (root / 'dashboard.css').read_text(encoding='utf-8')

    def test_roster_and_market_show_comparison_arrow(self):
        self.assertIn('const trendArrow = p =>', self.javascript)
        self.assertGreaterEqual(self.javascript.count('trendArrow(p)'), 2)
        self.assertIn("expected>previous ? ['↑','positive'", self.javascript)
        self.assertIn("expected<previous ? ['↓','negative'", self.javascript)

    def test_action_cards_show_expiry_and_remaining_hours(self):
        self.assertIn('const expiryDetails = p =>', self.javascript)
        self.assertIn('Restlaufzeit '+"'+hours+'"+' Std.', self.javascript)
        self.assertIn('expiryDetails(player)', self.javascript)
        self.assertIn('.risk-expiry', self.styles)


if __name__ == '__main__':
    unittest.main()
