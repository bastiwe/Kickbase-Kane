"""Budget-constrained mail lineup using the HA planner's default scoring."""
from html.parser import HTMLParser
from itertools import combinations
import json
import math
from pathlib import Path


FORMATIONS = [('4-4-2', (1, 4, 4, 2)), ('4-3-3', (1, 4, 3, 3)),
              ('3-4-3', (1, 3, 4, 3)), ('3-5-2', (1, 3, 5, 2)),
              ('5-3-2', (1, 5, 3, 2)), ('4-5-1', (1, 4, 5, 1)),
              ('5-4-1', (1, 5, 4, 1)), ('4-2-4', (1, 4, 2, 4)),
              ('5-2-3', (1, 5, 2, 3)), ('3-6-1', (1, 3, 6, 1))]


def number(value):
    try:
        value = float(value)
        return value if math.isfinite(value) else None
    except (ValueError, TypeError):
        return None


def planner_score(player):
    # Match the planner's numeric conversion: explicit null season/l3 becomes 0.
    def metric(key):
        return 0 if key in player and player[key] is None else number(player.get(key))
    season, recent = metric('season'), metric('l3')
    base = season * .7 + recent * .3 if season is not None and recent is not None else (
        season if season is not None else recent or 0)
    li = number(player.get('li'))
    probability = max(.25, min(1, li / 100)) if li is not None else 1
    fixture = (player.get('fixtures') or [{}])[0]
    rank = 0 if 'rank' in fixture and fixture['rank'] is None else number(fixture.get('rank'))
    fixture_factor = 1 + max(-.06, min(.06, (rank - 9) / 150)) if rank is not None else 1
    change = number(player.get('change'))
    trend = max(-1.5, min(1.5, change / 500000)) if change is not None else 0
    return base * probability * fixture_factor + trend


def best_budget_lineup(players, cash):
    """Maximize planner score; sell all unselected owned players at market value."""
    cash = number(cash)
    pool = [p for p in players if p.get('owned') is not False]
    if cash is None or any(number(p.get('mv')) is None for p in pool):
        return None
    total_value = sum(number(p['mv']) for p in pool)
    limit = cash + total_value

    def frontier(options):
        kept, high = [], -math.inf
        for cost, score, ids in sorted(options, key=lambda x: (x[0], -x[1])):
            if cost <= limit and score > high:
                kept.append((cost, score, ids))
                high = score
        return kept

    best, option_cache = None, {}
    for formation, required in FORMATIONS:
        states = [(0, 0, ())]
        for position, amount in enumerate(required, 1):
            key = (position, amount)
            if key not in option_cache:
                options = []
                for chosen in combinations([i for i, p in enumerate(pool)
                                            if number(p.get('position')) == position], amount):
                    options.append((sum(number(pool[i]['mv']) for i in chosen),
                                    sum(planner_score(pool[i]) for i in chosen), chosen))
                option_cache[key] = frontier(options)
            states = frontier((cost + c, score + s, ids + selected)
                              for cost, score, ids in states
                              for c, s, selected in option_cache[key])
            if not states:
                break
        if states:
            cost, score, ids = max(states, key=lambda x: x[1])
            if best is None or score > best['score']:
                best = {'formation': formation, 'score': score,
                        'players': [pool[i] for i in ids],
                        'sales': [p for i, p in enumerate(pool) if i not in ids],
                        'budget': cash + total_value - cost}
    return best


def attachment_payload(attachment):
    class Parser(HTMLParser):
        def __init__(self):
            super().__init__()
            self.active, self.parts = False, []
        def handle_starttag(self, tag, attrs):
            if tag == 'script' and dict(attrs).get('id') == 'data':
                self.active = True
        def handle_endtag(self, tag):
            if tag == 'script':
                self.active = False
        def handle_data(self, data):
            if self.active:
                self.parts.append(data)
    paths = attachment if isinstance(attachment, (list, tuple)) else [attachment]
    for path in paths:
        if not path:
            continue
        try:
            parser = Parser()
            parser.feed(Path(path).read_text(encoding='utf-8'))
            payload = json.loads(''.join(parser.parts))
            if isinstance(payload, dict) and isinstance(payload.get('players'), list):
                return payload
        except (OSError, ValueError, TypeError):
            continue
    return None
