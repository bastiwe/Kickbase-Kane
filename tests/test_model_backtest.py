import unittest

import pandas as pd

from model_backtest import evaluate_momentum_baseline, simulate_top_trades


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


if __name__ == "__main__":
    unittest.main()
