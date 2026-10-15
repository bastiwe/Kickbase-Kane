from datetime import datetime, timedelta
from itertools import combinations
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from zoneinfo import ZoneInfo

import pandas as pd

from features.ai_advisor import FORMATIONS
from s11_strategy_report import send_strategy_mail
from features.lineup_optimizer import build_lineup_payload
from features.strategy_report import build_strategy_report, prepare_players, solve, strategy_html, write_strategy_report


NOW = datetime(2026, 10, 15, 18, tzinfo=ZoneInfo('Europe/Berlin'))


def player(pid, position, score=100, mv=1_000_000, owned=True, **extra):
    return dict(id=str(pid), name=f'Spieler {pid}', position=position, team=f'Team {pid}',
                teamId=str(pid), owned=owned, mv=mv, change=100_000, l3=score,
                status='Fit', expiresAt=(NOW + timedelta(hours=3)).isoformat(), **extra)


def payload():
    positions = [1, 2, 2, 2, 2, 3, 3, 3, 3, 4, 4, 2]
    return dict(budget=-500_000, players=[player(i, p, score=100+i) for i, p in enumerate(positions)],
                marketPlayers=[player('new', 2, score=180, mv=500_000, owned=False)])


class StrategyTests(unittest.TestCase):
    def test_shared_payload_preserves_live_points_and_market_li_context(self):
        with patch('features.lineup_optimizer.get_players_in_squad', return_value={'it': [
                dict(i=1, fn='Own', ln='Player', pos=1, mv=1000000, tid='A')]}), \
                patch('features.lineup_optimizer.get_json_with_token', return_value={'it': [
                    dict(i=2, fn='Market', ln='Player', pos=2, mv=500000, tid='B', exs=100)]}), \
                patch('features.lineup_optimizer.get_budget', return_value=0):
            result = build_lineup_payload('token', 'league', 'user',
                pd.DataFrame([dict(player_id=1, first_name='Own', last_name='Player', kickbase_average_points=90)]),
                pd.DataFrame(columns=['player_id']),
                market_df=pd.DataFrame([dict(player_id=2, kickbase_average_points=80, starter_rate=75)]))
        self.assertEqual(result['players'][0]['season'], 90)
        self.assertEqual(result['marketPlayers'][0]['season'], 80)
        self.assertEqual(result['marketPlayers'][0]['li'], 75)

    def test_big_boy_stays_on_bench_instead_of_being_sold_in_every_plan(self):
        data = payload()
        data['players'][1].update(mv=26_000_000, l3=-100)
        report = build_strategy_report(data, now=NOW)
        plans = [report['baseline'], report['ownFeasible'], *report['scenarios'].values()]
        plans += [check['plan'] for check in report['marketChecks'] if 'plan' in check]
        optimal = [plan for plan in plans if plan['status'] == 'optimal']
        self.assertTrue(optimal)
        for plan in optimal:
            self.assertNotIn('1', plan['sell'])
            self.assertIn('1', plan['lineup'] + plan['retainedBench'])
            self.assertLess(plan['sales'], 26_000_000)
            self.assertEqual(plan['rosterSize'], 11 + len(plan['retainedBench']))
        self.assertIn('1', report['scenarios']['Maximale Punkte']['retainedBench'])

    def test_protection_uses_strict_current_25m_threshold_not_forecast(self):
        data = payload()
        data['players'][1].update(mv=25_000_000, change=2_000_000, l3=-100)
        report = build_strategy_report(data, now=NOW)
        self.assertFalse(report['players'][1]['saleProtected'])
        self.assertIn('1', report['scenarios']['Maximale Punkte']['sell'])
        data['players'][1].update(mv=25_000_001, change=-2_000_000)
        report = build_strategy_report(data, now=NOW)
        self.assertTrue(report['players'][1]['saleProtected'])
        self.assertNotIn('1', report['scenarios']['Maximale Punkte']['sell'])

    def test_injured_big_boy_cannot_finance_replacement(self):
        data = payload()
        data['players'] = data['players'][:11]
        data['players'][1].update(mv=30_000_000, status='Verletzt')
        report = build_strategy_report(data, now=NOW)
        self.assertTrue(report['players'][1]['saleProtected'])
        self.assertEqual(report['scenarios']['Maximale Punkte']['status'], 'infeasible')

    def test_protected_bench_counts_against_club_limit(self):
        data = payload()
        data['players'][0]['teamId'] = 'A'
        data['players'] += [player('star'+str(i), 2, mv=30_000_000) for i in range(3)]
        for p in data['players'][-3:]:
            p.update(teamId='A', status='Verletzt')
        report = build_strategy_report(data, now=NOW)
        self.assertEqual(report['scenarios']['Maximale Punkte']['status'], 'infeasible')

    def test_protected_bench_counts_against_roster_limit(self):
        data = payload()
        data['players'] += [player('star'+str(i), 2, mv=30_000_000) for i in range(6)]
        for p in data['players'][-6:]:
            p['status'] = 'Verletzt'
        report = build_strategy_report(data, now=NOW)
        self.assertEqual(report['scenarios']['Maximale Punkte']['status'], 'infeasible')

    def test_protected_starter_counts_once_and_expensive_market_player_is_not_locked(self):
        data = payload()
        data['players'][0].update(mv=30_000_000, teamId='A')
        data['players'][1]['teamId'] = 'A'
        data['players'][2]['teamId'] = 'A'
        data['marketPlayers'][0]['mv'] = 30_000_000
        report = build_strategy_report(data, now=NOW)
        self.assertFalse(report['players'][-1]['saleProtected'])
        best = report['scenarios']['Maximale Punkte']
        self.assertEqual(best['status'], 'optimal')
        self.assertIn('0', best['lineup'])
        self.assertNotIn('0', best['retainedBench'])

    def test_solver_matches_exhaustive_search_for_points_and_buffer(self):
        data = payload()
        rows, _ = prepare_players(data, NOW, NOW + timedelta(hours=12))
        total = data['budget'] + sum(p['projectedValue'] for p in rows if p['owned'])
        feasible = []
        for lineup in combinations(rows, 11):
            counts = [sum(p['position'] == pos for p in lineup) for pos in (1, 2, 3, 4)]
            if counts[0] != 1 or '-'.join(map(str, counts[1:])) not in FORMATIONS:
                continue
            cash = total - sum(p['cost'] for p in lineup)
            if cash >= 0:
                feasible.append((sum(p['expectedPoints'] for p in lineup), cash))
        best = solve(rows, data['budget'])
        safe = solve(rows, data['budget'], objective='buffer')
        self.assertEqual(best['points'], max(p for p, c in feasible))
        self.assertEqual(safe['budget'], max(c for p, c in feasible))

    def test_cash_not_increased_by_unsold_gains_and_swaps_finance_team(self):
        report = build_strategy_report(payload(), now=NOW)
        self.assertEqual(report['budgetWithoutTrades'], -500_000)
        best = report['scenarios']['Maximale Punkte']
        self.assertIn('new', best['buy'])
        self.assertGreaterEqual(best['budget'], 0)
        self.assertEqual(best['budget'], best['cashBefore'] + best['sales'] - best['purchases'])
        self.assertEqual(best['sales'], 1_100_000 * len(best['sell']))
        self.assertEqual(len(best['lineup']), 11)
        self.assertGreaterEqual(report['scenarios']['Ausgewogen']['budget'], 1_000_000)
        self.assertTrue(report['marketChecks'][0]['relevant'])

    def test_no_update_after_22_or_exactly_22_double_counted(self):
        for hour in (22, 23):
            report = build_strategy_report(payload(), now=NOW.replace(hour=hour))
            self.assertEqual(report['updates'], 0)
            self.assertEqual(report['players'][0]['projectedValue'], 1_000_000)

    def test_falling_market_player_is_still_a_sporting_upgrade(self):
        data = payload()
        data['marketPlayers'][0]['change'] = -100_000
        report = build_strategy_report(data, now=NOW)
        self.assertIn('new', report['scenarios']['Maximale Punkte']['buy'])
        self.assertTrue(report['marketChecks'][0]['relevant'])

    def test_expired_late_and_unknown_expiry_never_finance_lineup(self):
        data = payload()
        for expiry in (None, NOW.isoformat(), (NOW + timedelta(days=1)).isoformat(), 'invalid'):
            data['marketPlayers'][0]['expiresAt'] = expiry
            report = build_strategy_report(data, now=NOW)
            self.assertTrue(report['marketChecks'][0]['excluded'])
            self.assertNotIn('new', report['scenarios']['Maximale Punkte']['lineup'])

    def test_club_limit_is_hard_constraint(self):
        data = payload()
        for p in data['players'][:6]:
            p['teamId'] = 'same'
        report = build_strategy_report(data, now=NOW)
        plan = report['scenarios']['Maximale Punkte']
        self.assertEqual(plan['status'], 'infeasible')

    def test_unknown_cash_mv_and_points_do_not_create_fake_optimum(self):
        for field in ('budget', 'mv'):
            data = payload()
            if field == 'budget':
                data['budget'] = None
            else:
                data['players'][0]['mv'] = None
            report = build_strategy_report(data, now=NOW)
            self.assertEqual(report['scenarios']['Maximale Punkte']['status'], 'incomplete')
        data = payload()
        data['players'][0]['l3'] = None
        self.assertEqual(build_strategy_report(data, now=NOW)['scenarios']['Maximale Punkte']['status'], 'infeasible')

    def test_zero_negative_points_and_missing_forecast_are_preserved(self):
        data = payload()
        data['players'][0].update(l3=0, change=float('nan'))
        data['players'][1]['l3'] = -10
        report = build_strategy_report(data, now=NOW)
        self.assertEqual(report['players'][0]['expectedPoints'], 0)
        self.assertEqual(report['players'][1]['expectedPoints'], -10)
        self.assertTrue(any('MW-Prognosen fehlen' in w for w in report['warnings']))

    def test_unfundable_squad_can_be_rescued_by_cheaper_market_replacement(self):
        data = payload()
        data['players'] = data['players'][:11]
        data['players'][1]['mv'] = 5_000_000
        report = build_strategy_report(data, now=NOW)
        self.assertEqual(report['ownFeasible']['status'], 'infeasible')
        self.assertEqual(report['scenarios']['Maximale Punkte']['status'], 'optimal')
        self.assertTrue(report['marketChecks'][0]['relevant'])

    def test_li_status_and_own_listing_deduplication(self):
        data = payload()
        data['players'][1]['li'] = 50
        data['marketPlayers'].append(dict(data['players'][1], owned=False))
        data['marketPlayers'][0]['status'] = 'Verletzt'
        report = build_strategy_report(data, now=NOW)
        self.assertEqual(len(report['players']), 13)
        self.assertEqual(report['players'][1]['expectedPoints'], 50.5)
        self.assertTrue(report['marketChecks'][0]['excluded'])

    def test_reports_are_escaped_serializable_and_mail_uses_existing_sender(self):
        data = payload()
        data['players'][0]['name'] = '<script>unsafe</script>'
        report = build_strategy_report(data, now=NOW)
        html = strategy_html(report)
        self.assertNotIn('<script>', html)
        with tempfile.TemporaryDirectory() as tmp:
            path = write_strategy_report(report, str(Path(tmp) / 'report'))
            self.assertIn('S11-Strategie', path.read_text(encoding='utf-8'))
            self.assertEqual(json.loads(path.with_suffix('.json').read_text(encoding='utf-8'))['updates'], 1)
            with patch.dict('os.environ', EMAIL_USER='test@example.com', EMAIL_PASS='test'), \
                    patch('features.fast_notifier.smtplib.SMTP_SSL') as smtp:
                send_strategy_mail(report, path)
                message = smtp.return_value.__enter__.return_value.send_message.call_args.args[0]
            self.assertIn('S11-Strategie', message.get_body(preferencelist=('html',)).get_content())

    def test_timeout_is_reported_instead_of_claiming_optimality(self):
        rows, _ = prepare_players(payload(), NOW, NOW + timedelta(hours=12))
        with patch('features.strategy_report.milp') as milp:
            milp.return_value.status = 1
            self.assertEqual(solve(rows, 0)['status'], 'unresolved')


if __name__ == '__main__':
    unittest.main()
