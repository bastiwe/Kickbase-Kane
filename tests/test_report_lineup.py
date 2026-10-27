from itertools import combinations
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import pandas as pd

from features.report_lineup import FORMATIONS, best_budget_lineup, planner_score
from features.notifier import send_mail


def squad():
    positions = [1] + [2] * 4 + [3] * 4 + [4] * 3
    return [dict(id=str(i), name=f'Player{i}', position=pos, mv=10,
                 season=100 + i, l3=80 + i, owned=True, li=90)
            for i, pos in enumerate(positions)]


class ReportLineupTests(unittest.TestCase):
    def test_scoring_matches_dashboard_weights(self):
        player = dict(season=100, l3=200, li=50, fixtures=[{'rank': 18}], change=500000)
        self.assertAlmostEqual(planner_score(player), 130 * .5 * 1.06 + 1)

    def test_expensive_star_must_be_sold_to_reach_zero_budget(self):
        players = squad()
        players[-1].update(mv=150, season=1000, l3=1000)
        result = best_budget_lineup(players, -150)
        self.assertIsNotNone(result)
        self.assertEqual(result['budget'], 0)
        self.assertEqual([p['id'] for p in result['sales']], ['11'])
        self.assertEqual(len(result['players']), 11)

    def test_no_formation_is_invented_when_cash_or_positions_are_insufficient(self):
        self.assertIsNone(best_budget_lineup(squad(), -500))
        self.assertIsNone(best_budget_lineup(squad(), None))
        self.assertIsNone(best_budget_lineup(squad()[1:], 100))
        players = squad()
        players[0]['mv'] = None
        self.assertIsNone(best_budget_lineup(players, 100))

    def test_optimizer_matches_exhaustive_search_across_all_formations(self):
        players = squad() + [dict(id='12', name='Mid', position=3, mv=9,
                                 season=130, l3=150, li=75, owned=True)]
        players[-2]['mv'] = 40
        cash = -20
        result = best_budget_lineup(players, cash)
        scores = []
        for chosen in combinations(players, 11):
            counts = tuple(sum(p['position'] == pos for p in chosen) for pos in range(1, 5))
            remaining = cash + sum(p['mv'] for p in players) - sum(p['mv'] for p in chosen)
            if counts in [need for _, need in FORMATIONS] and remaining >= 0:
                scores.append(sum(planner_score(p) for p in chosen))
        self.assertAlmostEqual(result['score'], max(scores))

    def test_full_mail_uses_optimizer_data_but_sends_no_optimizer_attachment(self):
        players = squad()
        players[-1].update(mv=150, season=1000, l3=1000)
        payload = {'players': players, 'budget': -150}
        rows = pd.DataFrame([dict(player_id=p['id'], first_name='', last_name=p['name'],
                                  position=p['position'], mv=p['mv'], player_status='Fit',
                                  starter_rate=p['li']) for p in players])
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'startelf_optimizer.html'
            path.write_text('<script type="application/json" id="data">'
                            + json.dumps(payload) + '</script>', encoding='utf-8')
            with patch.dict(os.environ, {'EMAIL_USER': 'test@example.com', 'EMAIL_PASS': 'test'}), \
                    patch('features.notifier.smtplib.SMTP') as smtp:
                send_mail(pd.DataFrame(), pd.DataFrame(), rows, 'test@example.com', [path])
            message = smtp.return_value.__enter__.return_value.send_message.call_args.args[0]
            html = message.get_body(preferencelist=('html',)).get_content()
            analysis = html.split('Kaderanalyse</h3>', 1)[1].split('Manager-Budgets', 1)[0]
            starters = analysis.split('Eingeplante Verkäufe', 1)[0]
            self.assertIn('Beste Elf: 4-4-2', analysis)
            self.assertIn('Restbudget nach Bankverkäufen: 0 €', analysis)
            self.assertNotIn('Player11', starters)
            self.assertIn('Player11', analysis)
            self.assertEqual(list(message.iter_attachments()), [])
            self.assertTrue(path.exists())
            output = Path('test-output/mail-budget-lineup.html')
            output.parent.mkdir(exist_ok=True)
            output.write_text(html, encoding='utf-8')


if __name__ == '__main__':
    unittest.main()
