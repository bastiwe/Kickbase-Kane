import os
from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from zoneinfo import ZoneInfo

import pandas as pd

from features.predictions import online_correction


class OnlineCorrectionTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = TemporaryDirectory()
        self.previous_db = online_correction.DB_PATH
        self.previous_model = online_correction.MODEL_PATH
        online_correction.DB_PATH = str(Path(self.temp_dir.name) / "forecast.db")
        online_correction.MODEL_PATH = str(Path(self.temp_dir.name) / "model.joblib")

    def tearDown(self):
        online_correction.DB_PATH = self.previous_db
        online_correction.MODEL_PATH = self.previous_model
        self.temp_dir.cleanup()

    def test_target_date_uses_next_market_update(self):
        berlin = ZoneInfo("Europe/Berlin")
        self.assertEqual(
            online_correction.forecast_target_date(datetime(2026, 10, 22, 21, 40, tzinfo=berlin)).isoformat(),
            "2026-10-22",
        )
        self.assertEqual(
            online_correction.forecast_target_date(datetime(2026, 10, 22, 22, 10, tzinfo=berlin)).isoformat(),
            "2026-10-23",
        )

    def test_forecast_is_only_settled_after_actual_market_value_exists(self):
        berlin = ZoneInfo("Europe/Berlin")
        predictions = pd.DataFrame(
            [{"player_id": 42, "predicted_mv_target": 100_000, "mv_change_1d": 50_000}]
        )
        online_correction.record_online_forecasts(
            predictions, datetime(2026, 10, 22, 21, 40, tzinfo=berlin)
        )
        history = pd.DataFrame(
            [
                {"player_id": 42, "date": "2026-10-21", "mv": 1_000_000},
                {"player_id": 42, "date": "2026-10-22", "mv": 1_200_000},
            ]
        )

        self.assertEqual(online_correction.settle_online_forecasts(history), 1)
        status = online_correction.online_correction_status()
        self.assertEqual(status["settled_forecasts"], 1)
        self.assertEqual(status["persistent_training_samples"], 1)
        self.assertFalse(status["ready"])


if __name__ == "__main__":
    unittest.main()
