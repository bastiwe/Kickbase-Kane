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
        self.assertIn("const playerLabel = (p,includeArt=true) =>", self.javascript)
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

    def test_recent_live_transfers_show_route_price_overpay_and_relative_time(self):
        html = (Path(__file__).parents[1] / 'features' / 'trading_dashboard.html').read_text(encoding='utf-8')
        self.assertIn('id="recent-transfers"', html)
        self.assertIn("fetch(apiPath('/api/recent-transfers')", self.javascript)
        self.assertIn("const relativeTime = value =>", self.javascript)
        self.assertIn("transfer.from||'Kickbase'", self.javascript)
        self.assertIn('transfer.overpay', self.javascript)
        self.assertIn('.recent-transfer-grid', self.styles)

    def test_top_chances_and_recent_transfers_use_half_cropped_artwork(self):
        self.assertIn("<summary>'+avatar(p)+'<div class=\"chance-content\">", self.javascript)
        self.assertIn("<article class=\"recent-transfer-card\">'+avatar(", self.javascript)
        self.assertIn('.chance>summary>.player-art,.recent-transfer-card>.player-art{position:absolute',
                      self.styles)
        self.assertIn('inset:auto auto 0 -164px;width:328px;height:200%', self.styles)
        self.assertIn('transform:scale(1.28)', self.styles)
        self.assertIn('left:64px;bottom:0;width:auto;height:100%;max-width:216px', self.styles)
        self.assertIn('left:-144px;width:288px;height:200%', self.styles)
        self.assertIn('left:56px;max-width:192px', self.styles)
        self.assertIn('.chance-content,.recent-transfer-content{position:relative;z-index:1',
                      self.styles)
        self.assertIn('.recent-transfer-grid{grid-template-columns:repeat(3,minmax(0,1fr))}',
                      self.styles)
        self.assertIn('@media(max-width:680px){.recent-transfer-grid{grid-template-columns:1fr}}',
                      self.styles)

    def test_large_artwork_is_shared_by_roster_risks_and_market_cards(self):
        self.assertIn('bottom:-38%;width:100%;height:100%', self.styles)
        self.assertIn('.roster-player .list-row,.risk-player .list-row{min-height:210px;',
                      self.styles)
        self.assertIn('.risk-player .list-row .player-art,.table-player .player-art{position:absolute',
                      self.styles)
        self.assertIn('.table-player{min-height:210px;padding:16px 14px 16px 176px}',
                      self.styles)

    def test_mobile_transfer_market_never_forces_horizontal_scrolling(self):
        self.assertIn('.table-wrap table{display:block;width:100%;min-width:0!important', self.styles)
        self.assertIn('.table-wrap tr.market-row{display:grid;width:100%', self.styles)
        self.assertIn('.table-wrap tr.market-history-row[hidden]{display:none!important}', self.styles)
        self.assertIn('html,body{max-width:100%;overflow-x:hidden}', self.styles)

    def test_player_art_layers_cutout_over_club_crest(self):
        self.assertIn("const teamImage = p =>", self.javascript)
        self.assertIn('class="club-crest"', self.javascript)
        self.assertIn('class="player-cutout"', self.javascript)
        self.assertIn('.club-crest{position:absolute;inset:0;width:100%;height:100%', self.styles)
        self.assertIn('opacity:.18', self.styles)
        self.assertIn('.player-cutout{position:relative;z-index:1', self.styles)
        self.assertIn('.chance .player-art,.list-row .player-art,.recent-transfer-card .player-art,.table-player .player-art{position:absolute', self.styles)
        self.assertIn('width:min(54%,190px);height:100%', self.styles)
        self.assertIn('left:9%;bottom:0;height:50%', self.styles)
        self.assertIn('opacity:.28', self.styles)
        self.assertIn('background:rgba(7,16,29,.64)', self.styles)
        self.assertIn('.chance{padding-left:128px;min-height:190px}', self.styles)
        self.assertIn('.list-row{padding-left:108px;min-height:106px}', self.styles)
        self.assertIn('.recent-transfer-card{padding-left:128px;min-height:190px}', self.styles)
        self.assertIn('.table-player{min-height:62px;padding-left:64px}', self.styles)
        self.assertIn('height:100%;max-width:94%;object-fit:contain', self.styles)
        self.assertIn('background:transparent;box-shadow:none;backdrop-filter:none', self.styles)


if __name__ == '__main__':
    unittest.main()
