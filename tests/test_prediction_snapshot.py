from datetime import datetime
from pathlib import Path
import tempfile
import unittest
from zoneinfo import ZoneInfo

import pandas as pd

from features.predictions.snapshot import read_prediction_snapshot, write_prediction_snapshot, project_to_matchday
from features.lineup_optimizer import forecast_horizon


class SnapshotTests(unittest.TestCase):
    def test_model_anchors_reduce_growth_and_expire_at_update(self):
        stamp = '2026-09-09T12:00:00+02:00'
        snapshot = {'generatedAt': stamp, 'predictions': {'1': 100000}, 'multiDay': {
            '7': {'generatedAt': stamp, 'predictions': {'1': 250000}}}}
        now = datetime.fromisoformat(stamp)
        self.assertEqual(project_to_matchday(snapshot, '1', 3, now), 150000)
        self.assertEqual(project_to_matchday(snapshot, '1', 7, now), 250000)
        self.assertIsNone(project_to_matchday(snapshot, '1', 8, now))
        self.assertIsNone(project_to_matchday(snapshot, '1', 3, now.replace(hour=22)))
        self.assertEqual(project_to_matchday(snapshot, '1', 0, now), 0)
        snapshot['multiDay'] = {}
        self.assertIsNone(project_to_matchday(snapshot, '1', 3, now))

    def test_fast_snapshot_preserves_separately_dated_week_model(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'forecast.json'
            write_prediction_snapshot(pd.DataFrame([{'player_id': 1, 'predicted_mv_target': 100,
                'predicted_mv_target_7d': -50}]), 'Spaet', path=path)
            write_prediction_snapshot(pd.DataFrame([{'player_id': 1, 'predicted_mv_target': 80}]), 'Fast 1T', path=path)
            result = read_prediction_snapshot(path)
            self.assertEqual(result['multiDay']['7']['predictions']['1'], -50)
            self.assertEqual(result['multiDay']['7']['source'], 'Spaet')

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
