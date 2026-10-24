"""Compare individual starters with market players on the same points basis."""
import math


def number(value):
    try:
        result = float(value)
        return result if math.isfinite(result) else None
    except (TypeError, ValueError):
        return None


def player_upgrades(selected, market, canonical_position, owned_ids=()):
    blocked = {'Verletzt', 'Reha', 'Rotgesperrt', 'Gelb-Rot-Sperre',
               'Nicht im Kader', 'Nicht in Liga', 'Abwesend'}
    def identity(value):
        numeric = number(value)
        return str(int(numeric)) if numeric is not None else str(value)
    owned = {identity(value) for value in owned_ids}
    upgrades = []
    for _, candidate in market.iterrows():
        if identity(candidate.get('player_id')) in owned or candidate.get('player_status') in blocked:
            continue
        position = canonical_position(candidate.get('position'))
        duels = []
        for _, starter in selected.iterrows():
            if canonical_position(starter.get('position')) != position:
                continue
            if candidate.get('team_limit_warning') == 'Vereinslimit voll':
                if not candidate.get('team_name') or candidate.get('team_name') != starter.get('team_name'):
                    continue
            # Compare per-appearance averages, never sums across unequal samples.
            for column, label in [('kickbase_average_points', 'aktuelle Saison'),
                                  ('last_season_avg_points', 'Vorsaison')]:
                current, target = number(starter.get(column)), number(candidate.get(column))
                if current is None or target is None:
                    continue
                if target > current:
                    duels.append(dict(starter=starter, candidate=candidate, position=position,
                                      current=current, target=target, gain=target-current,
                                      basis=label))
                break
        if duels:
            upgrades.append(max(duels, key=lambda duel: duel['gain']))
    return sorted(upgrades, key=lambda duel: duel['gain'], reverse=True)
