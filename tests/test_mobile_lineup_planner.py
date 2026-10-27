from pathlib import Path
import unittest


class MobileLineupPlannerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.template = (Path(__file__).parents[1] / 'features' / 'mobile_lineup_planner.html').read_text(
            encoding='utf-8')

    def test_desktop_pitch_keeps_mobile_lines_flat(self):
        self.assertIn('.formation-line{display:contents}', self.template)
        self.assertIn('@media(min-width:900px)', self.template)
        self.assertIn('.formation-4{order:1}', self.template)
        self.assertIn('.formation-1{order:4}', self.template)
        self.assertIn('class="formation-line formation-', self.template)

    def test_bank_players_default_to_sale_and_lineup_removes_sale(self):
        self.assertIn('function syncBenchSales()', self.template)
        self.assertIn('!sel.includes(p.id)&&!locked.has(p.id)&&!purchases.has(p.id)', self.template)
        self.assertIn('sel[i]=id;sell.delete(id);pick=null;render()', self.template)
        self.assertIn('sel[sel.indexOf(id)]=null;if(!locked.has(id)&&!purchases.has(id))sell.add(id)',
                      self.template)
        self.assertIn('sel=Array(11).fill(null);syncBenchSales();render()', self.template)

    def test_empty_slot_offers_position_candidates_with_projected_budget(self):
        self.assertIn('id="candidate-dialog"', self.template)
        self.assertIn("P.filter(p=>p.position===position&&!sel.includes(p.id))", self.template)
        self.assertIn('Budget danach<strong', self.template)
        self.assertIn('function projectedBudget(p)', self.template)
        self.assertIn("if(s&&!sel[+s.dataset.slot]){openCandidates(+s.dataset.slot);return}", self.template)

    def test_formations_show_budget_status_and_selected_outline(self):
        self.assertIn("budget>=0?'form-green':'form-yellow'", self.template)
        self.assertIn("return{kind:'form-red'", self.template)
        self.assertIn('.forms button.active{outline:3px solid var(--form-color)', self.template)
        self.assertIn("if(f){selectFormation(f.dataset.form);return}", self.template)

    def test_starting_lineup_pins_are_available_on_desktop_and_long_press(self):
        self.assertIn('class="start-toggle ', self.template)
        self.assertIn('data-start="', self.template)
        self.assertIn('function toggleStarter(id)', self.template)
        self.assertIn('setTimeout(()=>{touch.long=true', self.template)
        self.assertIn('pool.filter(p=>forced.has(p.id))', self.template)

    def test_profit_loss_is_shown_on_cards_and_candidate_picker(self):
        self.assertGreaterEqual(self.template.count("' · G/V '+profit"), 1)
        self.assertIn("G/V '+profit", self.template)
        self.assertIn('MW-Prognose ', self.template)
        self.assertIn('.money small.green{color:var(--g)}', self.template)
        self.assertIn('.money small.red{color:var(--r)}', self.template)
        self.assertIn("trendClass=v=>Number.isFinite(v)?(v>=0?'green':'red'):''", self.template)

    def test_li_probability_is_shown_on_cards_and_in_candidate_picker(self):
        self.assertIn('function liChip(p)', self.template)
        self.assertGreaterEqual(self.template.count('+liChip(p)+'), 2)
        self.assertIn("value>=85?' li-high':value>=45?' li-medium':' li-low'", self.template)
        self.assertIn('.li-chip.li-high', self.template)
        self.assertIn('.li-chip.li-medium', self.template)
        self.assertIn('.li-chip.li-low', self.template)

    def test_status_swipes_can_return_to_neutral(self):
        self.assertIn("locked.delete(id);msg('Halte-Status aufgehoben.')", self.template)
        self.assertIn("sell.delete(id);msg('Verkauf aufgehoben · Status neutral.')", self.template)

    def test_dashboard_back_link_is_explicit(self):
        self.assertIn('aria-label="Zurück zum Trading Dashboard"', self.template)
        self.assertIn('← Trading Dashboard</a>', self.template)

    def test_player_cards_layer_cutout_over_transparent_club_crest(self):
        self.assertIn('function playerArt(p,position=true)', self.template)
        self.assertIn('class="club-crest"', self.template)
        self.assertIn('class="player-cutout"', self.template)
        self.assertIn('.club-crest{position:absolute;inset:0;width:100%;height:100%', self.template)
        self.assertIn('opacity:.18', self.template)
        self.assertIn('.player-cutout{position:relative;z-index:1', self.template)
        self.assertIn('height:67%', self.template)
        self.assertIn('border:0;border-radius:0;background:transparent', self.template)
        self.assertIn('.card{min-height:104px;grid-template-columns:92px minmax(0,1fr) auto',
                      self.template)
        self.assertIn('.card .player-art{position:relative', self.template)
        self.assertIn('grid-column:1;grid-row:1/3', self.template)
        self.assertIn('.card .player-cutout{position:absolute', self.template)
        self.assertIn('height:100%;max-width:94%', self.template)
        self.assertIn('.card-copy,.candidate-copy,.card .money,.candidate-budget{position:relative',
                      self.template)
        self.assertIn('opacity:.28', self.template)
        self.assertIn('background:#07101ea8', self.template)
        self.assertIn('.card-copy{grid-column:2;grid-row:1', self.template)
        self.assertIn('.card .money{grid-column:3;grid-row:1', self.template)

    def test_candidate_picker_uses_large_left_aligned_reference_artwork(self):
        self.assertIn('min-height:156px;grid-template-columns:clamp(124px,25%,174px)',
                      self.template)
        self.assertIn('.candidate-option .player-art{position:relative', self.template)
        self.assertIn('align-self:stretch;width:100%;height:100%;overflow:hidden', self.template)
        self.assertIn('.candidate-option .club-crest{position:absolute;left:-9%', self.template)
        self.assertIn('height:100%;object-fit:contain;object-position:left center;opacity:.38',
                      self.template)
        self.assertIn('.candidate-option .player-cutout{position:absolute;z-index:1;left:-5%;bottom:0',
                      self.template)
        self.assertIn('height:100%;max-width:92%;object-fit:contain;object-position:left bottom',
                      self.template)
        self.assertIn('grid-template-columns:106px minmax(0,1fr)', self.template)
        self.assertIn('.candidate-option .player-art{grid-row:1/3}', self.template)

    def test_all_planner_cards_share_half_cropped_lowered_crest_composition(self):
        self.assertIn('.card,.bank .card{min-height:200px;', self.template)
        self.assertIn('inset:auto auto 0 -120px;width:288px;height:200%', self.template)
        self.assertIn('top:auto;bottom:-26%;width:100%;height:100%', self.template)
        self.assertIn('left:56px;bottom:0;width:auto;height:100%;max-width:192px', self.template)
        self.assertIn('.candidate-option{min-height:210px;', self.template)
        self.assertIn('.slot .card .player-art{left:-82px;width:200px;height:200%}', self.template)
        self.assertIn('.slot .card .player-cutout{left:0;max-width:132px}', self.template)
        self.assertIn('@media(max-width:640px){.card,.bank .card{min-height:168px;',
                      self.template)
        self.assertIn('.card .player-art,.candidate-option .player-art{inset:auto auto 0 -100px;width:240px;height:180%',
                      self.template)
        self.assertIn('.card .player-cutout,.candidate-option .player-cutout{left:48px;',
                      self.template)
        self.assertIn('.candidate-option{min-height:168px;padding:12px 10px 10px 140px}',
                      self.template)


if __name__ == '__main__':
    unittest.main()
