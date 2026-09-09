from datetime import datetime
from pathlib import Path
import tempfile
import unittest
from zoneinfo import ZoneInfo

import pandas as pd

from features.predictions.snapshot import read_prediction_snapshot, write_prediction_snapshot
from features.lineup_optimizer import forecast_horizon


class SnapshotTests(unittest.TestCase):
    def test_roundtrip_keeps_negative_and_zero_and_skips_missing_values(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'forecast.json'
            df = pd.DataFrame({'player_id': [1, 2, 3, 4], 'predicted_mv_target': [100000, -50000, 0, float('nan')]})
            write_prediction_snapshot(df, 'Fast 1T', path=path)
            snapshot = read_prediction_snapshot(path)
            self.assertEqual(snapshot['predictions'], {'1': 100000, '2': -50000, '3': 0})
            self.assertEqual(snapshot['source'], 'Fast 1T')
            self.assertIsNone(read_prediction_snapshot(path, competition_id=2))

    def test_missing_snapshot_is_not_a_zero_forecast(self):
        with tempfile.TemporaryDirectory() as folder:
            self.assertIsNone(read_prediction_snapshot(Path(folder) / 'missing.json'))

    def test_updates_before_matchday_exclude_already_completed_update(self):
        history = pd.DataFrame({'md': ['2026-09-12', '2026-09-11', '2026-09-08'], 'p': [None, None, 100]})
        for hour, count in [(21, 2), (22, 1), (23, 1)]:
            result = forecast_horizon(history, datetime(2026, 9, 9, hour, tzinfo=ZoneInfo('Europe/Berlin')))
            self.assertEqual(result, {'date': '2026-09-11', 'updates': count})
        self.assertEqual(forecast_horizon(history, datetime(2026, 9, 11, 12, tzinfo=ZoneInfo('Europe/Berlin')))['updates'], 0)
        self.assertIsNone(forecast_horizon(pd.DataFrame()))
