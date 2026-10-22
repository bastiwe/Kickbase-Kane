import os
import unittest
from unittest.mock import patch

import pandas as pd

from model_backtest import (
    build_walk_forward_summary,
    evaluate_momentum_baseline,
    evaluate_saved_market_snapshots,
    simulate_top_trades,
)


class ModelBacktestTests(unittest.TestCase):
    def setUp(self):
        self.rows = pd.DataFrame([
            {"date": "2026-10-01", "prediction": 120_000, "mv_target": 100_000,
             "mv_target_clipped": 100_000, "mv_change_1d": 90_000},
            {"date": "2026-10-01", "prediction": 80_000, "mv_target": 40_000,
             "mv_target_clipped": 40_000, "mv_change_1d": -20_000},
            {"date": "2026-10-02", "prediction": 70_000, "mv_target": 60_000,
             "mv_target_clipped": 60_000, "mv_change_1d": 50_000},
        ])
        self.rows["date"] = pd.to_datetime(self.rows["date"])

    def test_daily_best_pick_uses_one_highest_positive_prediction_per_day(self):
        result = simulate_top_trades(self.rows, top_n=1)
        self.assertEqual(result["top_trades"], 2)
        self.assertEqual(result["top_trade_hit_rate_pct"], 100.0)
        self.assertEqual(result["top_trade_total_profit"], 160_000.0)

    def test_momentum_baseline_reports_same_target_metrics(self):
        result = evaluate_momentum_baseline(self.rows)
        self.assertEqual(result["strategy"], "Tagesdynamik fortschreiben")
        self.assertEqual(result["direction_accuracy_pct"], 66.67)
        self.assertEqual(result["mae"], 26_666.67)


    def test_snapshot_validation_uses_only_proven_market_player_days(self):
        snapshots = pd.DataFrame([
            {"market_value_date": "2026-10-01", "player_id": "1", "observed_at": "2026-10-01T21:40:00+02:00"},
        ])
        rows = self.rows.copy()
        rows["player_id"] = [1, 2, 1]
        result = evaluate_saved_market_snapshots(rows, snapshots)
        self.assertEqual(result["status"], "complete")
        self.assertEqual(result["matched_player_days"], 1)
        self.assertEqual(result["model"]["daily_best_pick"]["top_trades"], 1)

    def test_walk_forward_trains_only_on_earlier_days(self):
        rows = []
        for day in range(1, 8):
            for player_id in range(1, 5):
                rows.append({
                    "player_id": player_id,
                    "date": pd.Timestamp("2026-09-01") + pd.Timedelta(days=day),
                    "mv_target_clipped": 10_000 * player_id,
                    "mv_target": 10_000 * player_id,
                    "mv_change_1d": 8_000 * player_id,
                    "p": 50,
                    "mv": 1_000_000 + player_id,
                    "days_to_next": 5,
                    "mv_trend_1d": 0.01,
                    "mv_change_3d": 15_000,
                    "mv_vol_3d": 5_000,
                    "mv_trend_7d": 0.03,
                    "market_divergence": 1.0,
                })
        data = pd.DataFrame(rows)
        test = data[data["date"] >= pd.Timestamp("2026-09-05")].copy()
        with patch.dict(os.environ, {
            "BACKTEST_WALK_FORWARD_WINDOW_DAYS": "30",
            "BACKTEST_WALK_FORWARD_ESTIMATORS": "1",
        }):
            result = build_walk_forward_summary(data, test)
        self.assertEqual(result["status"], "complete")
        self.assertEqual(result["model"]["days"], 4)
        self.assertIn("ensemble", result)


if __name__ == "__main__":
    unittest.main()
