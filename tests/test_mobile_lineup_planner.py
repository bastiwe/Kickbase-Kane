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


if __name__ == '__main__':
    unittest.main()
