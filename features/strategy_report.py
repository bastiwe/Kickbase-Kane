"""Exact, read-only S11 planning using the existing planner's live payload.

Unselected owned players are sold unless their current MW exceeds 25m euros.
Protected players can stay on the bench. No speculative market bench purchases.
Cash is never increased by an unrealised market-value change.
"""

from datetime import datetime, timedelta
from html import escape
import json
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
from scipy.optimize import Bounds, LinearConstraint, milp

from features.ai_advisor import FORMATIONS, numeric, points
from features.fast_notifier import format_number


BERLIN = ZoneInfo('Europe/Berlin')
SALE_PROTECTION_THRESHOLD = 25_000_000


def prepare_players(payload, now, deadline):
    update = now.replace(hour=22, minute=0, second=0, microsecond=0)
    if update <= now:
        update += timedelta(days=1)
    updates = int(update < deadline)
    own = {str(p['id']): p for p in payload['players'] if p.get('owned')}
    rows = list(own.values()) + [p for p in payload.get('marketPlayers', [])
                                 if str(p['id']) not in own]
    result, seen = [], set()
    for source in rows:
        pid = str(source['id'])
        if pid in seen:
            continue
        seen.add(pid)
        p = dict(source, id=pid, owned=pid in own)
        for field in ('mv', 'change', 'l3', 'season', 'average', 'li', 'bid', 'askingPrice'):
            p[field] = numeric(p.get(field))
        mv, change = numeric(p.get('mv')), numeric(p.get('change'))
        p['saleProtected'] = p['owned'] and mv is not None and mv > SALE_PROTECTION_THRESHOLD
        p['projectedValue'] = max(0, mv + updates * (change or 0)) if mv is not None else None
        p['forecastMissing'] = change is None
        score, basis = points(p, 'l3' if numeric(p.get('l3')) is not None else 'season')
        score = numeric(score)
        li = numeric(p.get('li'))
        p['expectedPoints'] = score * min(1, max(0, li / 100)) if score is not None and li is not None else score
        p['pointsBasis'] = basis + (' × LI-Quote' if li is not None else '; Einsatzquote unbekannt')
        p['cost'] = p['projectedValue'] if p['owned'] else next(
            (numeric(p.get(k)) for k in ('bid', 'askingPrice', 'mv')
             if numeric(p.get(k)) is not None), None)
        p['priceBasis'] = 'Prognostizierter Verkaufserlös' if p['owned'] else (
            'Eigenes Gebot' if numeric(p.get('bid')) is not None else 'Angebotspreis/MW; Zuschlag ungewiss')
        reasons = []
        if p.get('position') not in (1, 2, 3, 4):
            reasons.append('Kickbase-Position fehlt')
        if not (p.get('teamId') or p.get('team')) or p.get('team') == 'Unbekannt' and not p.get('teamId'):
            reasons.append('Verein fehlt')
        if score is None:
            reasons.append('Punktdaten fehlen')
        if p['cost'] is None or p['cost'] < 0:
            reasons.append('Preis fehlt oder ungültig')
        if p.get('status') not in ('Fit', 'Angeschlagen', 'Unbekannt', None, ''):
            reasons.append('Ausfallstatus: ' + str(p['status']))
        if not p['owned']:
            try:
                expiry = datetime.fromisoformat(p.get('expiresAt') or '')
                if expiry.tzinfo is None or not now < expiry <= deadline:
                    reasons.append('Angebot nicht bis morgen früh verfügbar')
            except (TypeError, ValueError):
                reasons.append('Angebotsende unbekannt')
        p['excluded'] = reasons
        result.append(p)
    return result, updates


def solve(players, cash, floor=0, club_limit=3, objective='points', forced=None):
    """One MILP covers every existing planner formation, without candidate pruning."""
    own = [p for p in players if p['owned']]
    if cash is None or any(p['projectedValue'] is None or p['mv'] < 0 for p in own):
        return {'status': 'incomplete', 'reason': 'Cash oder eigener Marktwert fehlt.'}
    protected = [p for p in own if p.get('saleProtected')]
    if any(not p.get('teamId') and p.get('team') in (None, '', 'Unbekannt') for p in protected):
        return {'status': 'incomplete', 'reason': 'Verein eines verkaufsgeschützten Spielers fehlt.'}
    pool = [p for p in players if not p['excluded']]
    if len(pool) < 11:
        return {'status': 'infeasible', 'reason': 'Weniger als elf bewertbare Spieler.'}
    formations = sorted(FORMATIONS)
    n, f = len(pool), len(formations)
    size = n + f
    liquidation = cash + sum(p['projectedValue'] for p in own if not p.get('saleProtected'))
    costs = np.array([0 if p.get('saleProtected') else p['cost'] for p in pool] + [0] * f)
    scores = np.array([p['expectedPoints'] for p in pool] + [0] * f)
    rows, lower, upper = [], [], []

    def constraint(row, lo, hi):
        rows.append(row)
        lower.append(lo)
        upper.append(hi)

    constraint([0] * n + [1] * f, 1, 1)
    for position in (1, 2, 3, 4):
        counts = [1 if position == 1 else int(form.split('-')[position - 2]) for form in formations]
        constraint([int(p['position'] == position) for p in pool] + [-v for v in counts], 0, 0)
    teams = {p.get('teamId') or p['team'] for p in pool + protected}
    for team in sorted(teams):
        retained_count = sum((p.get('teamId') or p['team']) == team for p in protected)
        constraint([int(not p.get('saleProtected') and (p.get('teamId') or p['team']) == team)
                    for p in pool] + [0] * f, -np.inf, club_limit - retained_count)
    # Protected reserves remain in the roster and count against the existing
    # planner's 16-player limit, even when injured or not selected in the S11.
    constraint([int(not p.get('saleProtected')) for p in pool] + [0] * f,
               -np.inf, 16 - len(protected))
    # Scale euro amounts for numerical conditioning.
    constraint(costs / 1_000_000, -np.inf, (liquidation - floor) / 1_000_000)
    if forced is not None:
        constraint([int(p['id'] == forced) for p in pool] + [0] * f, 1, 1)
    result = milp(costs / 1_000_000 if objective == 'buffer' else -scores,
                  integrality=np.ones(size), bounds=Bounds(np.zeros(size), np.ones(size)),
                  constraints=LinearConstraint(np.array(rows), lower, upper),
                  options={'time_limit': 15, 'mip_rel_gap': 0})
    if result.status != 0:
        return {'status': 'infeasible' if result.status == 2 else 'unresolved',
                'reason': 'Keine zulässige Elf.' if result.status == 2 else 'Optimierung nicht abgeschlossen.'}
    selected = [p for i, p in enumerate(pool) if result.x[i] > .5]
    selected_ids = {p['id'] for p in selected}
    sales = [p for p in own if p['id'] not in selected_ids and not p.get('saleProtected')]
    retained_bench = [p['id'] for p in protected if p['id'] not in selected_ids]
    buys = [p for p in selected if not p['owned']]
    proceeds = sum(p['projectedValue'] for p in sales)
    spending = sum(p['cost'] for p in buys)
    end = cash + proceeds - spending
    if len(selected) != 11 or end < floor - .01:
        return {'status': 'unresolved', 'reason': 'Numerische Budgetprüfung fehlgeschlagen.'}
    return {'status': 'optimal', 'formation': formations[int(np.argmax(result.x[n:]))],
            'lineup': [p['id'] for p in selected], 'sell': [p['id'] for p in sales],
            'retainedBench': retained_bench, 'rosterSize': 11 + len(retained_bench),
            'buy': [p['id'] for p in buys], 'points': sum(p['expectedPoints'] for p in selected),
            'cashBefore': cash, 'sales': proceeds, 'purchases': spending, 'budget': end,
            'saleMwEffect': sum(p['projectedValue'] - p['mv'] for p in sales)}


def build_strategy_report(payload, now=None, buffer=1_000_000, club_limit=3):
    now = (now or datetime.now(BERLIN)).astimezone(BERLIN)
    deadline = (now + timedelta(days=1)).replace(hour=6, minute=0, second=0, microsecond=0)
    players, updates = prepare_players(payload, now, deadline)
    cash = numeric(payload.get('budget'))
    own = [p for p in players if p['owned']]
    baseline = solve(own, cash, floor=-np.inf, club_limit=club_limit)
    scenarios = {
        'Maximale Punkte': solve(players, cash, club_limit=club_limit),
        'Ausgewogen': solve(players, cash, floor=buffer, club_limit=club_limit),
        'Maximaler Budgetpuffer': solve(players, cash, club_limit=club_limit, objective='buffer'),
    }
    own_feasible = solve(own, cash, club_limit=club_limit)
    market_checks = []
    for p in players:
        if p['owned']:
            continue
        check = {'id': p['id'], 'excluded': p['excluded']}
        if not p['excluded']:
            plan = solve(players, cash, club_limit=club_limit, forced=p['id'])
            check['plan'] = plan
            if plan['status'] == 'optimal':
                check['pointsGain'] = plan['points'] - baseline['points'] if baseline['status'] == 'optimal' else None
                check['budgetGain'] = plan['budget'] - baseline['budget'] if baseline['status'] == 'optimal' else None
                check['relevant'] = (own_feasible['status'] == 'infeasible' or
                                     own_feasible['status'] == 'optimal' and plan['points'] > own_feasible['points'] + .01)
        market_checks.append(check)
    warnings = [
        'Eigene Spieler mit aktuellem MW über 25 Mio. € sind vor Verkauf geschützt, auch bei Verletzung oder schwachen Punktwerten. Sie können auf der Bank bleiben.',
        'Nur ungeschützte Spieler außerhalb der Elf werden verkauft. Geschützte Bankspieler zählen zum Vereinslimit und zum 16er-Kaderlimit; ihr MW wird nicht als Verkaufserlös eingeplant.',
        'Punkte sind historische Vergleichswerte, gegebenenfalls mit LI-Quote gewichtet; keine sichere Spieltagsprognose.',
        'Verkauf zum prognostizierten MW und Kauf zum Gebot/Angebotspreis/MW sind Annahmen. Zuschlag, Verkaufszeitpunkt und sofortige Kaufkraft sind nicht garantiert.',
        'Offene Gebote werden nur bei Auswahl eingerechnet. Andere Gebote vor Umsetzung zurückziehen; Szenarien sind Alternativen.',
        'Login- und Transferboni werden ohne bestätigte Auszahlung nicht als verfügbares Geld eingeplant.',
    ]
    if any(p['forecastMissing'] for p in own):
        warnings.append('MW-Prognosen fehlen bei eigenen Spielern: für diese gilt unveränderter MW als ausdrücklich unsichere Ersatzannahme.')
    if not updates:
        warnings.append('Bis morgen 06:00 liegt kein weiteres 22-Uhr-Update; 1T-Prognosen werden erst danach relevant.')
    return {'generated': now.isoformat(), 'deadline': deadline.isoformat(), 'updates': updates,
            'forecast': payload.get('forecast'), 'budget': cash, 'budgetWithoutTrades': cash,
            'bufferTarget': buffer, 'clubLimit': club_limit, 'players': players,
            'baseline': baseline, 'ownFeasible': own_feasible, 'scenarios': scenarios,
            'marketChecks': market_checks, 'warnings': warnings}


def strategy_html(report):
    players = {p['id']: p for p in report['players']}

    def names(ids):
        return ', '.join(escape(players[i]['name'] + ' (' + players[i].get('team', '?') + ')') for i in ids) or 'Keine'

    sections = ['<h2>S11-Strategie bis morgen früh</h2>',
                '<p>Stand: ' + escape(report['generated']) + '; Ziel: ' + escape(report['deadline']) + '</p>',
                '<p>Cash ohne Transfers morgen: ' + format_number(report['budgetWithoutTrades']) + ' €.</p>']
    baseline = report['baseline']
    if baseline['status'] == 'optimal':
        sections.append(f'<p>Vergleich: stärkste eigene Elf ohne Budgetzwang: {baseline["points"]:.1f} Punkte, '
                        f'{format_number(baseline["budget"])} € nach Bankverkäufen.</p>')
    for title, plan in report['scenarios'].items():
        sections.append('<h3>' + escape(title) + '</h3>')
        if plan['status'] != 'optimal':
            sections.append('<p>' + escape(plan['reason']) + '</p>')
            continue
        sections += [f'<p>{plan["formation"]}: {plan["points"]:.1f} Vergleichspunkte. '
                     f'Cash {format_number(plan["cashBefore"])} + Verkäufe {format_number(plan["sales"])} '
                     f'− Käufe {format_number(plan["purchases"])} = <b>{format_number(plan["budget"])} €</b>. '
                     f'Davon Verkaufserlös durch MW-Änderung: {format_number(plan["saleMwEffect"])} €.</p>',
                     '<p><b>Startelf:</b> ' + names(plan['lineup']) + '</p>',
                     '<p><b>Geschützte Bank:</b> ' + names(plan['retainedBench']) + '</p>',
                     '<p><b>Verkaufen:</b> ' + names(plan['sell']) + '</p>',
                     '<p><b>Kaufen:</b> ' + names(plan['buy']) + '</p>']
        if baseline['status'] == 'optimal':
            sections.append(f'<p>Gegenüber eigener Elf ohne Budgetzwang: '
                            f'{plan["points"] - baseline["points"]:+.1f} Punkte, '
                            f'{format_number(plan["budget"] - baseline["budget"])} € Budgetänderung.</p>')
    sections.append('<h3>Transfermarkt und Tauschalternativen</h3>')
    for check in report['marketChecks']:
        p = players[check['id']]
        detail = '; '.join(check['excluded'])
        plan = check.get('plan', {})
        if plan.get('status') == 'optimal':
            detail = ('S11-relevant' if check.get('relevant') else 'Kein Punktegewinn gegenüber finanzierbarer eigener Elf')
            detail += f'; {plan["points"]:.1f} Punkte; Restbudget {format_number(plan["budget"])} €'
            if check.get('pointsGain') is not None:
                detail += f'; Δ Punkte {check["pointsGain"]:+.1f}, Δ Budget {format_number(check["budgetGain"])} € gegenüber eigener Elf ohne Budgetzwang'
            sections.append('<p><b>' + escape(p['name']) + '</b>: ' + escape(detail) +
                            '. Kaufen: ' + names(plan['buy']) + '; verkaufen: ' + names(plan['sell']) +
                            '; geschützte Bank: ' + names(plan['retainedBench']) + '</p>')
        else:
            sections.append('<p>' + escape(p['name'] + ': ' + (detail or plan.get('reason', 'Ungeprüft'))) + '</p>')
    sections.append('<h3>Spielerwerte und Annahmen</h3><table><tr><th>Spieler</th><th>Status / Basis</th><th>MW</th><th>1T</th><th>MW morgen</th><th>Punkte</th><th>Planpreis</th><th>Preisannahme / Ablauf</th></tr>')
    for p in report['players']:
        sections.append('<tr><td>' + escape(p['name']) + (' (eigen)' if p['owned'] else ' (Markt)') +
                        (' – Verkaufsschutz über 25 Mio. €' if p.get('saleProtected') else '') +
                        '</td><td>' + escape(str(p.get('status')) + '; ' + p['pointsBasis']) +
                        '</td>' + ''.join('<td>' + format_number(p.get(k)) + '</td>' for k in
                                         ('mv', 'change', 'projectedValue', 'expectedPoints', 'cost')) +
                        '<td>' + escape(p['priceBasis'] + ('; ' + str(p.get('expiresAt') or 'Ablauf unbekannt') if not p['owned'] else '')) + '</td></tr>')
    sections.append('</table><ul>' + ''.join('<li>' + escape(w) + '</li>' for w in report['warnings']) + '</ul>')
    return '\n'.join(sections)


def write_strategy_report(report, prefix='s11_strategy_report'):
    Path(prefix + '.json').write_text(json.dumps(report, ensure_ascii=False, allow_nan=False, indent=2), encoding='utf-8')
    path = Path(prefix + '.html')
    path.write_text('<!doctype html><meta charset="utf-8"><title>Kickbase S11-Strategie</title>' + strategy_html(report), encoding='utf-8')
    return path
