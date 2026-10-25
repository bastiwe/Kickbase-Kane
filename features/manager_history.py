"""Persistent, read-only league audit and explicitly estimated opponent cash.

SQLite records observations separately from derived events. Re-running an audit
replaces its current estimates, never adds the same achievement a second time.
Every observation/run is retained so changes remain reviewable.
"""
from datetime import datetime, timedelta
from html import escape
from itertools import combinations
import json
import math
from pathlib import Path
import sqlite3
import uuid

import pandas as pd

from features.cash_reconstruction import BERLIN, fetch_manager_transfers, reconstruct_cash, timestamp

PLAYER_TIERS = [(200, 100_000), (300, 500_000), (400, 1_000_000), (500, 2_000_000)]
UNRESOLVED = [
    'Teamwert-Erfolge', 'Liga- und Profil-Erfolge',
    'Saisonplatzierung', 'Admin-Gutschriften und Strafen',
]


def finite(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


class HistoryStore:
    def __init__(self, path):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path, timeout=60)
        self.db.executescript('''
            CREATE TABLE IF NOT EXISTS observations (
                scope TEXT, run TEXT, kind TEXT, subject TEXT, observed_at TEXT,
                payload TEXT, PRIMARY KEY(scope,run,kind,subject));
            CREATE TABLE IF NOT EXISTS events (
                scope TEXT, event_key TEXT, manager TEXT, kind TEXT, status TEXT,
                amount REAL, amount_max REAL, payload TEXT, updated_at TEXT,
                PRIMARY KEY(scope,event_key));
            CREATE TABLE IF NOT EXISTS cache (
                scope TEXT, cache_key TEXT, observed_at TEXT, payload TEXT,
                PRIMARY KEY(scope,cache_key));
        ''')

    def observe(self, scope, run, kind, subject, now, payload):
        self.db.execute('INSERT OR REPLACE INTO observations VALUES (?,?,?,?,?,?)',
                        (scope, run, kind, str(subject), now.isoformat(), json.dumps(payload, ensure_ascii=False)))

    def cached(self, scope, key, now, max_age):
        row = self.db.execute('SELECT observed_at,payload FROM cache WHERE scope=? AND cache_key=?',
                              (scope, key)).fetchone()
        if row and now - timestamp(row[0]) < max_age:
            return json.loads(row[1])
        return None

    def cache(self, scope, key, now, payload):
        self.db.execute('INSERT OR REPLACE INTO cache VALUES (?,?,?,?)',
                        (scope, key, now.isoformat(), json.dumps(payload, ensure_ascii=False)))

    def replace_events(self, scope, events, now):
        keys = [event['key'] for event in events]
        duplicates = sorted({key for key in keys if keys.count(key) > 1})
        if duplicates:
            raise ValueError('Doppelte Ereignisschlüssel: ' + ', '.join(duplicates))
        self.db.execute('DELETE FROM events WHERE scope=?', (scope,))
        for event in events:
            self.db.execute('INSERT INTO events VALUES (?,?,?,?,?,?,?,?,?)',
                            (scope, event['key'], event['manager'], event['kind'], event['status'],
                             event.get('amount'), event.get('amount_max'),
                             json.dumps(event, ensure_ascii=False), now.isoformat()))

    def kickoff_squad(self, scope, manager_id, day):
        row = self.db.execute(
            """SELECT payload FROM observations
               WHERE scope=? AND kind='kickoff_squad' AND subject=?
               ORDER BY observed_at DESC LIMIT 1""",
            (scope, f'{manager_id}:{day}')).fetchone()
        return json.loads(row[0]) if row else None

    def close(self):
        self.db.commit()
        self.db.close()


def current_season(performance):
    return max(performance.get('it', []), key=lambda s: int(s['sid']), default={})


def historical_roster(squad, transfers, kickoff):
    """Undo post-kickoff transfers, preserving contradictions as audit evidence."""
    owned = {str(p['pi']) for p in squad['it']}
    issues = []
    for row in sorted(transfers, key=lambda r: timestamp(r['dt']), reverse=True):
        if timestamp(row['dt']) < timestamp(kickoff):
            break
        pid = str(row['pi'])
        if row['tty'] == 1:
            if pid not in owned:
                issues.append(f'Kauf ohne Spieler im rückgerechneten Kader: {pid}')
            owned.discard(pid)
        elif row['tty'] == 2:
            if pid in owned:
                issues.append(f'Verkauf bei bereits vorhandenem Spieler: {pid}')
            owned.add(pid)
        else:
            issues.append(f'Unbekannte Transferart: {pid}')
    return {'players': sorted(owned), 'issues': issues, 'basis': 'aus Transfers rekonstruiert'}


def lineup_estimate(players, points, actual_points, issues=()):
    """Conditional model bounds, not confidence bounds or confirmed lineups.

    Null/missing match points may stand for a non-playing footballer; treating
    those as zero is recorded explicitly. API fetch errors are handled outside.
    Position/formation legality and empty slots are not inferred.
    """
    zeros = [pid for pid in players if points.get(pid) is None]
    result = {'zero_assumption': zeros, 'issues': list(issues), 'solutions': 0,
              'bonus_min': None, 'bonus_max': None, 'always_selected': [],
              'possibly_selected': [], 'formation_checked': False}
    if issues or not 11 <= len(players) <= 20 or not finite(actual_points):
        return result
    always, possible, rewards = set(players), set(), []
    for chosen in combinations(players, 11):
        if sum(points.get(pid) or 0 for pid in chosen) != actual_points:
            continue
        result['solutions'] += 1
        always.intersection_update(chosen)
        possible.update(chosen)
        peak = max(points.get(pid) or 0 for pid in chosen)
        rewards.append(sum(bonus for threshold, bonus in PLAYER_TIERS if peak >= threshold))
    if rewards:
        result.update(bonus_min=min(rewards), bonus_max=max(rewards),
                      always_selected=sorted(always), possibly_selected=sorted(possible))
    return result


def mvp_events(day, entries):
    """User-specified rule: highest scorer among owned players at kickoff.

    Award only if this player is in all inferred lineups. Ties remain unresolved
    without the teams' kickoff values. Never substitute another manager's award.
    """
    candidates = [(p or 0, name, pid) for name, entry in entries.items()
                  for pid, p in entry['points'].items()]
    usable = candidates and all(not e['roster']['issues'] and e['lineup']['solutions']
                                and not e.get('fetch_errors') for e in entries.values())
    leaders = []
    if usable:
        top = max(p for p, _, _ in candidates)
        leaders = [(name, pid) for p, name, pid in candidates if p == top]
    events = []
    for name, entry in entries.items():
        amount = 0 if usable else None
        possible = amount
        own = [pid for manager, pid in leaders if manager == name]
        if own:
            possible = 1_000_000
            amount = (1_000_000 if len(leaders) == 1 and
                      own[0] in entry['lineup']['always_selected'] else 0)
        events.append({'key': f'{name}:md:{day}:mvp', 'manager': name, 'kind': 'MVP',
                       'status': 'geschätzt' if usable else 'offen', 'amount': amount,
                       'amount_max': possible, 'day': day, 'leaders': leaders,
                       'rule': 'punktbester Spieler in Managerkadern zum Anpfiff; aufgestellt',
                       'tie_unresolved': len(leaders) > 1})
    return events


def goal_machine_events(day, entries):
    """Award most squad goals; manager points break a goals tie."""
    usable = bool(entries) and all(
        not entry['roster']['issues'] and not entry.get('fetch_errors')
        and finite(entry.get('md', {}).get('mdp'))
        and all(finite(value) for value in entry.get('goals', {}).values())
        for entry in entries.values()
    )
    totals = {name: sum(entry.get('goals', {}).values()) for name, entry in entries.items()} if usable else {}
    finalists = []
    if usable and max(totals.values(), default=0) > 0:
        most_goals = max(totals.values())
        leaders = [name for name, total in totals.items() if total == most_goals]
        most_points = max(entries[name]['md']['mdp'] for name in leaders)
        finalists = [name for name in leaders if entries[name]['md']['mdp'] == most_points]
    winner = finalists[0] if len(finalists) == 1 else None
    result = []
    for name in entries:
        unresolved_tie = len(finalists) > 1 and name in finalists
        amount = None if not usable else (250_000 if name == winner else 0)
        amount_max = 250_000 if unresolved_tie else amount
        result.append({
            'key': f'{name}:md:{day}:goal_machine', 'manager': name,
            'kind': 'Tormaschine', 'day': day,
            'status': 'offen' if not usable or unresolved_tie else 'geschätzt',
            'amount': amount, 'amount_max': amount_max,
            'goals_by_manager': totals, 'winner': winner,
            'rule': 'meiste Tore im Kader zum Anpfiff; bei Torgleichstand mehr Managerpunkte',
        })
    return result


def capture(get, league_id, start_date, store, now, run):
    scope = f'{league_id}:{start_date}'
    managers = get(f'/leagues/{league_id}/ranking')['us']
    result, errors = {}, {}
    for manager in managers:
        mid, name = str(manager['i']), manager['n']
        data = {'id': mid}
        for kind in ['dashboard', 'squad', 'performance']:
            try:
                data[kind] = get(f'/leagues/{league_id}/managers/{mid}/{kind}')
                store.observe(scope, run, kind, mid, now, data[kind])
            except Exception as error:
                errors[f'{name}:{kind}'] = type(error).__name__
        result[name] = data
    return result, errors


def audit_managers(get, league_id, start_date, *, start_cash=80_000_000,
                   initial_squad_value=100_000_000, history_path='manager_history.sqlite3',
                   now=None, capture_only=False, output_dir='manager-history-output'):
    now = now or datetime.now(BERLIN)
    scope, run = f'{league_id}:{start_date}', uuid.uuid4().hex
    store = HistoryStore(history_path)
    try:
        managers, errors = capture(get, league_id, start_date, store, now, run)
        if capture_only:
            matchdays = get('/competitions/1/matchdays')
            upcoming = []
            for day in matchdays.get('it', []):
                kickoffs = [timestamp(match['dt']) for match in day.get('it', []) if match.get('dt')]
                if kickoffs and timedelta(minutes=3) <= now - min(kickoffs) <= timedelta(minutes=35):
                    upcoming.append({'day': day.get('day'), 'kickoff': min(kickoffs).isoformat()})
            for name, data in managers.items():
                for matchday in upcoming:
                    if 'squad' in data:
                        store.observe(scope, run, 'kickoff_squad',
                                      f"{data['id']}:{matchday['day']}", now,
                                      {'manager': name, **matchday, 'squad': data['squad']})
            summary = {'captured_at': now.isoformat(), 'managers': list(managers),
                       'matchdays': upcoming, 'errors': errors}
            store.observe(scope, run, 'capture_summary', 'league', now, summary)
            return summary
        events, rows, audits, rounds = [], [], {}, {}
        own_name, own_cash = None, None
        try:
            own_name = get('/user/settings')['u']['unm']
            own_cash = get(f'/leagues/{league_id}/me/budget')['b']
        except Exception as error:
            errors['own_budget'] = type(error).__name__
        # Preserve raw account-only evidence. Never attribute it to opponents.
        for suffix in ['settings', 'user/achievements', 'activitiesFeed?max=5000']:
            try:
                payload = get(f'/leagues/{league_id}/{suffix}')
                store.observe(scope, run, suffix, own_name or 'account', now, payload)
                if suffix == 'activitiesFeed?max=5000':
                    for event in payload.get('af', []):
                        if event.get('t') == 26 and timestamp(event['dt']) >= timestamp(start_date):
                            evidence = {'key': 'observed:' + str(event['i']), 'manager': own_name or 'account',
                                        'kind': 'API-Erfolg', 'status': 'belegt',
                                        'raw': event, 'included_in_cash': False}
                            events.append(evidence)
            except Exception as error:
                errors[suffix] = type(error).__name__

        for name, data in managers.items():
            try:
                trades = fetch_manager_transfers(get, league_id, data['id'], start_date)
                store.observe(scope, run, 'transfers', data['id'], now, trades)
                audit = reconstruct_cash(trades, data['performance'], data['squad'],
                                         data['dashboard']['prft'], start_date=start_date,
                                         as_of=now.isoformat(), start_cash=start_cash,
                                         initial_squad_value=initial_squad_value)
                audits[name] = audit
                lucky = audit['lucky_hand_event']
                for index, evidence in enumerate(lucky['events'], 1):
                    events.append({
                        'key': f'{name}:lucky_hand:{evidence["sale_date"]}:{evidence["player_id"]}:{index}',
                        'manager': name, 'kind': 'Glückliches Händchen', 'status': 'geschätzt',
                        'amount': evidence['bonus'], 'amount_max': evidence['bonus'],
                        'evidence': evidence,
                    })
                for event in audit['transfer_bonus_events']:
                    events.append({'key': f"{name}:transfer:{event['date']}:{event['player']}",
                                   'manager': name, 'kind': 'Transfergewinn', 'status': 'geschätzt',
                                   'amount': event['bonus'], 'amount_max': event['bonus'], 'evidence': event})
                for event in audit['season_milestone_events']:
                    events.append({'key': f"{name}:milestone:{event['code']}",
                                   'manager': name, 'kind': event['kind'], 'status': 'geschätzt',
                                   'amount': event['bonus'], 'amount_max': event['bonus'],
                                   'evidence': event})
                for md in current_season(data['performance']).get('it', []):
                    if not md.get('md') or timestamp(md['md']) < timestamp(start_date):
                        continue
                    # Save future/current schedules as well as settled rosters.
                    if timestamp(md['md']) > now:
                        continue
                    snapshot = store.kickoff_squad(scope, data['id'], md['day'])
                    if snapshot:
                        squad_players = snapshot['squad']['it']
                        locked = sorted(str(player['pi']) for player in squad_players
                                        if isinstance(player.get('lo'), int) and 0 <= player['lo'] < 11)
                        roster = {'players': sorted(str(player['pi']) for player in squad_players),
                                  'locked_lineup': locked, 'issues': [],
                                  'basis': 'Snapshot kurz nach Spieltagsbeginn'}
                    else:
                        roster = historical_roster(data['squad'], trades, md['md'])
                    store.observe(scope, run, 'matchday_roster', f"{data['id']}:{md['day']}", now,
                                  dict(roster, kickoff=md['md'], day=md['day']))
                    if md.get('cur') is not False or 'mdp' not in md:
                        continue
                    rounds.setdefault(md['day'], {})[name] = {'md': md, 'roster': roster}
                    from features.budgets import MATCHDAY_POINT_BONUSES
                    for kind, amount in [('Spieltagssieg', 1_000_000 if md.get('tw') else 0),
                                         ('Spieltagspunkte', sum(b for t, b in MATCHDAY_POINT_BONUSES if md['mdp'] >= t))]:
                        events.append({'key': f'{name}:md:{md["day"]}:{kind}', 'manager': name,
                                       'kind': kind, 'status': 'geschätzt', 'day': md['day'],
                                       'amount': amount, 'amount_max': amount, 'evidence': md})
            except Exception as error:
                errors[name] = f'{type(error).__name__}: {error}'

        player_ids = {pid for entries in rounds.values() for e in entries.values() for pid in e['roster']['players']}
        performance, player_errors = {}, {}
        for pid in sorted(player_ids):
            key = 'player:' + pid
            payload = store.cached(scope, key, now, timedelta(hours=12))
            if payload is None:
                try:
                    raw = get(f'/competitions/1/players/{pid}/performance')
                    payload = [s for s in raw.get('it', []) if s.get('n') == 'Bundesliga'
                               and any(m.get('md') and timestamp(m['md']) >= timestamp(start_date)
                                       for m in s.get('ph', []))]
                    store.cache(scope, key, now, payload)
                except Exception as error:
                    player_errors[pid] = type(error).__name__
                    continue
            performance[pid] = payload
        for day, entries in rounds.items():
            for name, entry in entries.items():
                points = {}
                for pid in entry['roster']['players']:
                    matches = [m for s in performance.get(pid, []) for m in s.get('ph', [])
                               if m.get('day') == day and m.get('md')
                               and timestamp(m['md']) >= timestamp(start_date) and timestamp(m['md']) <= now]
                    points[pid] = sum(m['p'] for m in matches) if matches and all(finite(m.get('p')) for m in matches) else None
                entry['points'] = points
                entry['goals'] = {
                    pid: (None if pid in player_errors else sum(
                        1 for season in performance.get(pid, [])
                        for match in season.get('ph', [])
                        if match.get('day') == day and match.get('md')
                        and timestamp(match['md']) >= timestamp(start_date)
                        and timestamp(match['md']) <= now
                        for code in (match.get('k') or []) if str(code) == '1'
                    ))
                    for pid in entry['roster']['players']
                }
                entry['fetch_errors'] = [pid for pid in points if pid in player_errors]
                candidates = (entry['roster'].get('locked_lineup')
                              if len(entry['roster'].get('locked_lineup', [])) == 11
                              else entry['roster']['players'])
                entry['lineup'] = lineup_estimate(candidates, points, entry['md']['mdp'],
                                                  entry['roster']['issues'] + entry['fetch_errors'])
                entry['lineup']['basis'] = ('gesperrte Aufstellung aus API-Snapshot'
                                            if candidates is not entry['roster']['players']
                                            else 'aus Kader und Managerpunkten rekonstruiert')
                store.observe(scope, run, 'lineup_estimate', f"{managers[name]['id']}:{day}", now, entry)
                estimate = entry['lineup']
                events.append({'key': f'{name}:md:{day}:player_points', 'manager': name,
                               'kind': 'Spieler-Punkteerfolge', 'day': day,
                               'status': 'geschätzt' if estimate['solutions'] else 'offen',
                               'amount': estimate['bonus_min'], 'amount_max': estimate['bonus_max'],
                               'evidence': estimate})
            if set(entries) == set(managers):
                events.extend(mvp_events(day, entries))
                events.extend(goal_machine_events(day, entries))
            else:
                for name in managers:
                    for kind in ['MVP', 'Tormaschine']:
                        events.append({'key': f'{name}:md:{day}:{kind}', 'manager': name, 'kind': kind,
                                       'day': day, 'status': 'offen', 'reason': 'Managerdaten fehlen'})

        for name, data in managers.items():
            for kind in UNRESOLVED:
                events.append({'key': f'{name}:coverage:{kind}', 'manager': name, 'kind': kind,
                               'status': 'offen', 'reason': 'Keine vollständige zuordenbare Buchungshistorie'})
            audit = audits.get(name)
            budget = float('nan')
            basis = 'Unbekannt (Datenabruf unvollständig)'
            if audit:
                additional = [e for e in events if e['manager'] == name and e['kind'] in
                              ['MVP', 'Spieler-Punkteerfolge', 'Tormaschine']]
                low = sum(e.get('amount') or 0 for e in additional)
                high = sum(e.get('amount_max') or 0 for e in additional)
                audit.update(additional_bonus_min=low, additional_bonus_max=high,
                             estimated_cash=audit['profile_cash_scenario'] + low,
                             estimated_cash_model_max=audit['profile_cash_scenario'] + high,
                             ledger_cash_with_bonuses=audit['cash_partial_estimate'] + low,
                             unresolved_events=sum(e['status'] == 'offen' for e in additional))
                budget = audit['estimated_cash']
                basis = 'Schätzung: 80M Cash / 100M Startkader + Boni'
                if start_cash != 80_000_000 or initial_squad_value != 100_000_000:
                    basis = 'Schätzung: Startvermögen + Profilgewinn + Boni'
                if name == own_name and finite(own_cash):
                    audit['actual_cash'] = own_cash
                    audit['unexplained_difference'] = own_cash - budget
            if name == own_name and finite(own_cash):
                budget, basis = own_cash, 'API (eigener Kontostand)'
            team_value = data.get('dashboard', {}).get('tv', float('nan'))
            rows.append({'User': name, 'Budget': budget, 'Team Value': team_value,
                         'Cash Basis': basis, 'Max Negative': -0.33 * team_value,
                         'Available Budget': budget + 0.33 * team_value})

        summary = {'generated_at': now.isoformat(), 'league_id': str(league_id), 'start_date': start_date,
                   'start_cash': start_cash, 'initial_squad_value': initial_squad_value,
                   'assumptions': ['Täglicher Login', '1.000 € je abgeschlossenem Punkt',
                                   f'Erfolgsereignisse erst ab {start_date}',
                                   'Erfolgsboni aktiv', 'Profilgewinn = realisierter Gewinn seit Reset',
                                   'Sieg-, Saisonpunkt-, Transferanzahl- und Kadergrößen-Meilensteine',
                                   'MVP innerhalb der Liga; Aufstellungen rekonstruiert',
                                   'Tormaschine aus fixiertem Kader, Torcodes und Managerpunkten',
                                   'Fehlende Spielerpunkte als null; Formation nicht geprüft'],
                   'errors': dict(errors, player_performance=player_errors), 'managers': audits,
                   'events': events, 'unresolved_categories': UNRESOLVED}
        store.observe(scope, run, 'audit', 'league', now, summary)
        # Keep observed events from expired feeds in the current event index.
        old = store.db.execute("SELECT payload FROM events WHERE scope=? AND status='belegt'", (scope,)).fetchall()
        keys = {e['key'] for e in events}
        events.extend(json.loads(row[0]) for row in old if json.loads(row[0])['key'] not in keys)
        store.replace_events(scope, events, now)
        output = Path(output_dir)
        output.mkdir(parents=True, exist_ok=True)
        (output / 'latest.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
        (output / 'latest.html').write_text(render_audit(summary), encoding='utf-8')
        frame = pd.DataFrame(rows).sort_values('Available Budget', ascending=False, ignore_index=True)
        frame.attrs['manager_audit'] = summary
        frame.attrs['own_user'] = own_name
        return frame
    finally:
        store.close()


def render_audit(summary):
    def money(value):
        return f'{value:,.0f}'.replace(',', '.') + ' €' if finite(value) else 'offen'
    header = '<h3>Cash-Rekonstruktion &amp; Erfolgsprotokoll</h3>'
    notes = ('<p>Fremde Cash-Werte sind Schätzungen, keine bestätigten Kontostände. '
             'Startcash: ' + money(summary['start_cash']) + '; Anfangskader: ' + money(summary['initial_squad_value']) + '. '
             'Profilrechnung: Startvermögen + realisierter Profilgewinn − Anschaffungskosten des aktuellen Kaders + Boni. '
             'Die Transferrechnung bleibt als Gegenprobe erhalten. Zusätzliche, nicht zuordenbare Boni können fehlen.</p>'
             '<p>Annahmen: ' + escape('; '.join(summary['assumptions'])) + '.</p>')
    columns = ['Manager', 'Transfernetto (Verkäufe − Käufe)', 'Profil-Transfergewinn',
               'Anschaffungskosten aktueller Kader', 'Login', 'Punkteprämie',
               'Siege / Punkte-Erfolge', 'Transferboni inkl. Glückliches Händchen',
               'Saison-Meilensteine',
               'Spielerboni + MVP + Tormaschine (Modellspanne)',
               'Kontostand aus Transferledger + Boni', 'Kontostand aus Profilmodell', 'API-Abweichung']
    table = '<table style="border-collapse:collapse;font-size:12px"><thead><tr>' + ''.join('<th style="padding:6px">'+c+'</th>' for c in columns) + '</tr></thead><tbody>'
    for name, a in summary['managers'].items():
        values = [escape(name), money(a['transfer_net']), money(a['profile_transfer_profit']),
                  money(a['current_acquisition_cost']), money(a['login_assumption']), money(a['settled_points_reward']),
                  money(a['matchday_wins'] + a['matchday_thresholds']),
                  money(a['transfer_bonuses'] + a.get('lucky_hand_bonus', 0)),
                  money(a.get('season_milestone_bonus', 0)),
                  money(a['additional_bonus_min']) + ' – ' + money(a['additional_bonus_max']),
                  money(a['ledger_cash_with_bonuses']), money(a['estimated_cash']), money(a.get('unexplained_difference'))]
        table += '<tr>' + ''.join('<td style="padding:6px;border-bottom:1px solid #ddd">'+v+'</td>' for v in values) + '</tr>'
    table += '</tbody></table>'
    grouped = {}
    for event in summary.get('events', []):
        if event.get('kind') == 'API-Erfolg':
            continue
        key = (event.get('manager', '-'), event.get('kind', '-'), event.get('status', '-'))
        item = grouped.setdefault(key, {'count': 0, 'amount': 0, 'amount_max': 0, 'unknown': False})
        item['count'] += 1
        if finite(event.get('amount')):
            item['amount'] += event['amount']
        else:
            item['unknown'] = True
        if finite(event.get('amount_max')):
            item['amount_max'] += event['amount_max']
        else:
            item['unknown'] = True
    log = ('<h4>Erfolgsprotokoll</h4><table style="border-collapse:collapse;font-size:12px">'
           '<thead><tr><th style="padding:6px">Manager</th><th style="padding:6px">Kategorie</th>'
           '<th style="padding:6px">Status</th><th style="padding:6px">Ereignisse</th>'
           '<th style="padding:6px">Betrag / Modellspanne</th></tr></thead><tbody>')
    for (manager, kind, status), item in sorted(grouped.items()):
        value = ('offen' if item['unknown'] else money(item['amount']) +
                 ((' – ' + money(item['amount_max'])) if item['amount_max'] != item['amount'] else ''))
        cells = [escape(str(manager)), escape(str(kind)), escape(str(status)),
                 str(item['count']), value]
        log += '<tr>' + ''.join('<td style="padding:6px;border-bottom:1px solid #ddd">'+cell+'</td>' for cell in cells) + '</tr>'
    log += '</tbody></table>'
    pending = '<p>Weiterhin offen: ' + escape('; '.join(summary['unresolved_categories'])) + '. Modellspannen decken diese fehlenden Kategorien nicht ab.</p>'
    failures = {k: v for k, v in summary['errors'].items() if v}
    if failures:
        pending += '<p>Datenlücken: ' + escape(json.dumps(failures, ensure_ascii=False)) + '</p>'
    return header + notes + table + log + pending
