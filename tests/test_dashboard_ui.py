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

    def test_li_probability_badges_are_used_across_player_views(self):
        self.assertIn("const liBadge = (p,label='LI') =>", self.javascript)
        self.assertIn("value>=85?'high':value>=45?'medium':'low'", self.javascript)
        self.assertIn("const playerLabel = p =>", self.javascript)
        self.assertIn("+liBadge(p)+", self.javascript)
        self.assertIn("+liBadge(p,'')+", self.javascript)
        self.assertIn('.li-badge.high', self.styles)
        self.assertIn('.li-badge.medium', self.styles)
        self.assertIn('.li-badge.low', self.styles)

    def test_modern_responsive_dashboard_layout_is_present(self):
        self.assertIn('.dashboard-grid{grid-template-columns:repeat(12', self.styles)
        self.assertIn('.roster-panel{grid-column:span 7}', self.styles)
        self.assertIn('.action-panel{grid-column:span 5}', self.styles)
        self.assertIn('.brand-mark', self.styles)


if __name__ == '__main__':
    unittest.main()
