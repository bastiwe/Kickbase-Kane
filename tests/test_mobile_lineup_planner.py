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


if __name__ == '__main__':
    unittest.main()
