"""Persist finished forecasts for consumers that must never train a model."""

from datetime import datetime, timedelta
import json
import math
from pathlib import Path
from zoneinfo import ZoneInfo


SNAPSHOT_PATH = 'prediction_snapshot_1t.json'


def write_prediction_snapshot(predictions, source, competition_id=1, path=SNAPSHOT_PATH):
    values = {}
    longer = {}
    for row in predictions.to_dict('records'):
        try:
            value = float(row.get('predicted_mv_target'))
            player_id = str(int(row['player_id']))
        except (TypeError, ValueError, KeyError, OverflowError):
            continue
        if math.isfinite(value):
            values[player_id] = value
        for days in (3, 7):
            try:
                multi = float(row.get(f'predicted_mv_target_{days}d'))
                if math.isfinite(multi):
                    longer.setdefault(str(days), {})[player_id] = multi
            except (TypeError, ValueError):
                pass
    snapshot = {'version': 1, 'competitionId': competition_id, 'source': source,
                'generatedAt': datetime.now(ZoneInfo('Europe/Berlin')).isoformat(),
                'predictions': values}
    previous = read_prediction_snapshot(path, competition_id) if Path(path).is_file() else None
    snapshot['multiDay'] = dict((previous or {}).get('multiDay', {}))
    for days, forecasts in longer.items():
        snapshot['multiDay'][days] = {'generatedAt': snapshot['generatedAt'], 'source': source,
                                     'predictions': forecasts}
    Path(path).write_text(json.dumps(snapshot, allow_nan=False), encoding='utf-8')
    print(f'1T forecast snapshot saved: {len(values)} players ({source}).')
    return snapshot


def read_prediction_snapshot(path=SNAPSHOT_PATH, competition_id=1):
    try:
        snapshot = json.loads(Path(path).read_text(encoding='utf-8'))
        if not isinstance(snapshot, dict):
            raise ValueError('Invalid prediction snapshot')
        if snapshot.get('version') != 1 or snapshot.get('competitionId') != competition_id:
            raise ValueError('Incompatible prediction snapshot')
        stamp = datetime.fromisoformat(snapshot['generatedAt'])
        if stamp.tzinfo is None or not isinstance(snapshot.get('predictions'), dict):
            raise ValueError('Invalid prediction snapshot')
        snapshot['predictions'] = {
            str(key): float(value) for key, value in snapshot['predictions'].items()
            if isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)
        }
        return snapshot
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(f'1T forecast snapshot unavailable: {exc}. No forecasts will be calculated.')
        return None


def market_cycle(stamp):
    """Forecasts on opposite sides of the daily update cannot share anchors."""
    time = datetime.fromisoformat(stamp) if isinstance(stamp, str) else stamp
    if time.tzinfo is None:
        raise ValueError('Forecast time needs a timezone')
    return (time.astimezone(ZoneInfo('Europe/Berlin')) - timedelta(hours=22)).date()


def project_to_matchday(snapshot, player_id, updates, now=None):
    """Interpolate cumulative model targets; never extrapolate beyond them."""
    if updates == 0:
        return 0.0
    if not snapshot or updates is None or updates < 0:
        return None
    now = now or datetime.now(ZoneInfo('Europe/Berlin'))
    try:
        cycle = market_cycle(now)
        if market_cycle(snapshot['generatedAt']) != cycle:
            return None
        day = snapshot['predictions'].get(str(player_id))
        if not isinstance(day, (int, float)) or isinstance(day, bool) or not math.isfinite(day):
            return None
        anchors = [(1, float(day))]
        for days in (3, 7):
            entry = snapshot.get('multiDay', {}).get(str(days), {})
            if not entry or market_cycle(entry['generatedAt']) != cycle:
                continue
            value = entry['predictions'].get(str(player_id))
            if isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value):
                anchors.append((days, float(value)))
        if updates == 1:
            return day
        for (left, a), (right, b) in zip(anchors, anchors[1:]):
            if left <= updates <= right:
                return a + (b - a) * (updates - left) / (right - left)
        return None
    except (KeyError, TypeError, ValueError):
        return None
