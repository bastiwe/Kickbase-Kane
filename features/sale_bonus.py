"""Read-only transfer-profit achievement context for the local planner."""

from datetime import datetime, timezone
import math


RULES = [(700, 1_000_000, 'Glückliches Händchen'),
         (701, 3_000_000, 'Bronzenes Händchen'),
         (702, 5_000_000, 'Silbernes Händchen'),
         (703, 10_000_000, 'Goldenes Händchen'),
         (704, 25_000_000, 'Königstransfer')]


def amount(value):
    if isinstance(value, bool):
        return None
    try:
        number = float(value)
        return number if math.isfinite(number) and number >= 0 else None
    except (ValueError, TypeError):
        return None


def load_sale_bonus(client, report):
    base = '/leagues/' + str(report['league'])
    user = client.get('/user/settings').get('u', {})
    if str(user.get('i')) != str(report['user']):
        raise ValueError('Konto passt nicht zum Report')
    username = str(user.get('unm') or user.get('n') or '').strip().casefold()
    if not username:
        raise ValueError('Managername fehlt')
    rules = []
    for kind, threshold, name in RULES:
        detail = client.get(base + '/user/achievements/' + str(kind))
        reward = amount(detail.get('er'))
        if reward is None or not isinstance(detail.get('isrp'), bool):
            raise ValueError('Erfolgsdaten unvollständig')
        rules.append({'id': kind, 'name': name, 'threshold': threshold,
                      'reward': reward, 'repeatable': detail['isrp'],
                      'earned': detail.get('ise') is True or (amount(detail.get('ac')) or 0) > 0})
    events = client.get(base + '/activitiesFeed?max=5000')['af']
    now = datetime.now(timezone.utc)
    cutoff = f'{now.year if now.month >= 7 else now.year - 1}-07-01'
    purchases = {}
    for event in sorted(events, key=lambda e: e.get('dt', '')):
        if event.get('t') != 15:
            continue
        item = event.get('data', {})
        pid = str(item.get('pi', ''))
        if str(item.get('slr', '')).strip().casefold() == username:
            purchases.pop(pid, None)
        if str(item.get('byr', '')).strip().casefold() == username:
            purchases[pid] = {'price': amount(item.get('trp')),
                              'market': item.get('t') == 1 and not item.get('slr')
                                        and str(event.get('dt', '')) >= cutoff,
                              'date': event.get('dt')}
    return {'rules': rules, 'purchases': purchases,
            'fetchedAt': datetime.now(timezone.utc).isoformat()}


def calculate_sale_bonus(context, sales, enabled=False):
    """Conservative estimate: highest eligible tier per sale, once-only caps."""
    total, rows, used = 0, [], set()
    for player_id, price in sorted(sales.items()):
        purchase = context.get('purchases', {}).get(str(player_id), {})
        cost = amount(purchase.get('price'))
        sell_price = amount(price)
        gain = None if cost is None or sell_price is None else sell_price - cost
        eligible = enabled and purchase.get('market') is True and gain is not None
        choices = [r for r in context.get('rules', []) if eligible and gain >= r['threshold']
                   and (r['repeatable'] or (not r['earned'] and r['id'] not in used))]
        rule = max(choices, key=lambda r: r['reward'], default=None)
        bonus = rule['reward'] if rule else 0
        if rule and not rule['repeatable']:
            used.add(rule['id'])
        total += bonus
        rows.append({'id': str(player_id), 'gain': gain, 'bonus': bonus,
                     'achievement': rule['name'] if rule else None})
    return {'total': total, 'rows': rows}
