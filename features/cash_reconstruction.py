"""Auditable cash reconstruction; never calibrate opponents to the owner's cash."""
from datetime import datetime
from zoneinfo import ZoneInfo

from features.budgets import (
    daily_login_bonus_total, MATCHDAY_POINT_BONUSES, TRANSFER_PROFIT_BONUSES,
)

BERLIN = ZoneInfo('Europe/Berlin')
LUCKY_HAND_THRESHOLD = 1_000_000
LUCKY_HAND_REWARD = 100_000


def timestamp(value):
    result = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
    return result.replace(tzinfo=BERLIN) if result.tzinfo is None else result.astimezone(BERLIN)


def fetch_manager_transfers(get, league_id, manager_id, start_date, max_pages=100):
    """Read descending pages until crossing the reset or exhausting the endpoint.

    Exhaustion, not the date of the first trade, establishes coverage. Fail
    closed on repeated pages, malformed responses or an exhausted page budget.
    """
    cutoff = timestamp(start_date)
    rows, seen, previous_date = [], set(), None
    for page_number in range(max_pages):
        payload = get(f'/leagues/{league_id}/managers/{manager_id}/transfer?start={page_number * 25}')
        page = payload.get('it')
        if not isinstance(page, list):
            raise ValueError('Transferliste fehlt')
        signature = repr(page)
        if page and signature in seen:
            raise ValueError('Transferseite wiederholt sich')
        seen.add(signature)
        crossed = False
        for row in page:
            date = timestamp(row['dt'])
            if previous_date is not None and date > previous_date:
                raise ValueError('Transferhistorie ist nicht absteigend sortiert')
            previous_date = date
            if date < cutoff:
                crossed = True
            else:
                rows.append(row)
        if crossed or len(page) < 25:
            return rows
    raise ValueError('Transferhistorie überschreitet das Seitenlimit')


def reconstruct_lucky_hand(transfers, *, start_date, as_of):
    """Evaluate every qualifying sale within the configured season."""
    cutoff, end = timestamp(start_date), timestamp(as_of)
    purchases, qualifying = {}, []
    rows = sorted((row for row in transfers if cutoff <= timestamp(row['dt']) <= end),
                  key=lambda row: timestamp(row['dt']))
    for row in rows:
        kind, player_id, price = row.get('tty'), str(row.get('pi')), row.get('trp')
        if kind not in (1, 2) or not isinstance(price, (int, float)) or price < 0:
            continue
        market_transfer = not bool(row.get('othnm'))
        if kind == 1:
            # A reset can remove an unsold player. A later purchase is the new
            # relevant acquisition for the next completed sale.
            purchases[player_id] = (price, market_transfer, row.get('dt'))
            continue
        purchase = purchases.pop(player_id, None)
        if not purchase or not purchase[1] or not market_transfer:
            continue
        gain = price - purchase[0]
        if gain >= LUCKY_HAND_THRESHOLD:
            qualifying.append({'player': row.get('pn', player_id), 'player_id': player_id,
                               'purchase_date': purchase[2], 'sale_date': row.get('dt'),
                               'gain': gain})
    events = [dict(event, bonus=LUCKY_HAND_REWARD) for event in qualifying]
    return {'bonus': len(events) * LUCKY_HAND_REWARD,
            'count': len(events), 'qualified_in_season': bool(events),
            'events': events, 'evidence': events[0] if events else None,
            'reason': None,
            'rule': ('Nur Transfers ab Saisonstart; beliebig wiederholbar; '
                     'mindestens 1 Mio. Gewinn; keine Managertransfers')}


def reconstruct_cash(transfers, performance, squad, profile_profit, *,
                     start_date, as_of, start_cash=80_000_000,
                     points_reward=1000, achievements_enabled=True,
                     initial_squad_value=100_000_000):
    """Return a partial estimate with explicit assumptions and omitted bonuses.

    Transfers are cash movements. Initial allocation has no purchase entry;
    its sales count as income but never earn market-transfer achievements.
    ``points_reward`` is an explicit model assumption, not an API cash fact.
    Missing MVP/lineup/once-only rewards are not filled using another account.
    """
    cutoff, end = timestamp(start_date), timestamp(as_of)
    lucky_hand = reconstruct_lucky_hand(transfers, start_date=start_date, as_of=as_of)
    rows = sorted((r for r in transfers if cutoff <= timestamp(r['dt']) <= end),
                  key=lambda r: timestamp(r['dt']))
    purchases, sold_initial = {}, []
    buys = sales = realized = transfer_bonus = 0
    bonus_events = []
    for row in rows:
        price, kind, pid = row['trp'], row['tty'], str(row['pi'])
        if kind not in (1, 2) or not isinstance(price, (int, float)) or price < 0:
            raise ValueError('Unbekannte Transferart oder ungültiger Preis')
        if kind == 1:
            if pid in purchases:
                raise ValueError('Erneuter Kauf ohne vorherigen Verkauf')
            buys += price
            purchases[pid] = (price, not bool(row.get('othnm')))
        else:
            sales += price
            purchase = purchases.pop(pid, None)
            if purchase is None:
                sold_initial.append(row)
                continue
            gain = price - purchase[0]
            realized += gain
            if purchase[1] and not row.get('othnm') and achievements_enabled:
                reward = sum(b for threshold, b in TRANSFER_PROFIT_BONUSES if gain >= threshold)
                transfer_bonus += reward
                if reward:
                    bonus_events.append({'player': row.get('pn', pid), 'date': row['dt'],
                                         'gain': gain, 'bonus': reward})

    seasons = performance.get('it', [])
    season = max(seasons, key=lambda s: int(s['sid'])) if seasons else {}
    matchdays = [m for m in season.get('it', [])
                 if m.get('cur') is False and 'mdp' in m and m.get('md')
                 and cutoff <= timestamp(m['md']) <= end]
    points = sum(m['mdp'] for m in matchdays) * points_reward
    wins = sum(m.get('tw') is True for m in matchdays) * 1_000_000 if achievements_enabled else 0
    matchday_bonus = sum(b for m in matchdays for t, b in MATCHDAY_POINT_BONUSES
                         if m['mdp'] >= t) if achievements_enabled else 0
    login = daily_login_bonus_total(start_date, end)
    estimate = (start_cash + sales - buys + login + points + wins
                + matchday_bonus + transfer_bonus + lucky_hand['bonus'])

    current = {str(p['pi']): p for p in squad.get('it', [])}
    missing = sorted(set(purchases) - set(current))
    mismatches = [pid for pid, (price, _) in purchases.items()
                  if pid in current and 'prc' in current[pid] and current[pid]['prc'] != price]
    remaining_initial_cost = sum(p['mv'] - p['mvgl'] for pid, p in current.items()
                                 if pid not in purchases)
    # Hypothesis to test, not a cash correction: prft is realized P/L including
    # assigned players. Infer their sold cost, then add any still held players.
    inferred_initial_cost = (sum(r['trp'] for r in sold_initial)
                             - (profile_profit - realized) + remaining_initial_cost)
    # Separate scenario under the user's fixed starting-squad assumption.
    # If prft is realized profit, subtract current acquisition cost, NOT current
    # market value. Unrealized market changes are not cash movements.
    current_acquisition_cost = sum(p['mv'] - p['mvgl'] for p in current.values())
    bonus_total = login + points + wins + matchday_bonus + transfer_bonus + lucky_hand['bonus']
    profile_estimate = (start_cash + initial_squad_value + profile_profit
                        - current_acquisition_cost + bonus_total)
    return {
        'start_cash': start_cash, 'buys': buys, 'sales': sales,
        'transfer_net': sales - buys, 'transfer_count': len(rows),
        'login_assumption': login, 'points_reward_assumption': points_reward,
        'settled_points_reward': points, 'matchday_wins': wins,
        'matchday_thresholds': matchday_bonus, 'transfer_bonuses': transfer_bonus,
        'lucky_hand_bonus': lucky_hand['bonus'], 'lucky_hand_event': lucky_hand,
        'cash_partial_estimate': estimate, 'transfer_bonus_events': bonus_events,
        'profile_transfer_profit': profile_profit, 'realized_profit_known_buys': realized,
        'inferred_initial_squad_cost': inferred_initial_cost,
        'initial_squad_value_assumption': initial_squad_value,
        'current_acquisition_cost': current_acquisition_cost,
        'profile_cash_scenario': profile_estimate,
        'profile_vs_ledger_difference': profile_estimate - estimate,
        'current_squad_unrealized_gain': sum(p['mvgl'] for p in current.values()),
        'missing_current_players': missing, 'purchase_price_mismatches': mismatches,
        'omitted': ['MVP', 'individual player point awards',
                    'other once-only achievements', 'admin adjustments', 'initial cash adjustment'],
    }
