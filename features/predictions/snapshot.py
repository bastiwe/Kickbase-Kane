"""Persist finished forecasts for consumers that must never train a model."""

from datetime import datetime
import json
import math
from pathlib import Path
from zoneinfo import ZoneInfo


SNAPSHOT_PATH = 'prediction_snapshot_1t.json'


def write_prediction_snapshot(predictions, source, competition_id=1, path=SNAPSHOT_PATH):
    values = {}
    for row in predictions.to_dict('records'):
        try:
            value = float(row.get('predicted_mv_target'))
            player_id = str(int(row['player_id']))
        except (TypeError, ValueError, KeyError, OverflowError):
            continue
        if math.isfinite(value):
            values[player_id] = value
    snapshot = {'version': 1, 'competitionId': competition_id, 'source': source,
                'generatedAt': datetime.now(ZoneInfo('Europe/Berlin')).isoformat(),
                'predictions': values}
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
