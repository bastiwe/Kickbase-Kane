from datetime import datetime
from zoneinfo import ZoneInfo
import json
import os

import pandas as pd
from dotenv import load_dotenv

from features.predictions.data_handler import (
    check_if_data_reload_needed,
    create_player_data_table,
    load_player_data_from_db,
    save_player_data_to_db,
)
from features.predictions.modeling import evaluate_model, train_model
from features.predictions.preprocessing import preprocess_player_data
from kickbase_api.user import login


load_dotenv()

SUMMARY_PATH = "model_backtest_summary.json"

competition_ids = [1]
last_mv_values = 365
last_pfm_values = 50
features = [
    "p",
    "mv",
    "days_to_next",
    "mv_change_1d",
    "mv_trend_1d",
    "mv_change_3d",
    "mv_vol_3d",
    "mv_trend_7d",
    "market_divergence",
]


def main():
    token = login(os.getenv("KICK_USER"), os.getenv("KICK_PASS"))
    print("\nLogged in to Kickbase for model backtest.")

    create_player_data_table()
    reload_data = check_if_data_reload_needed()
    save_player_data_to_db(token, competition_ids, last_mv_values, last_pfm_values, reload_data)
    player_df = load_player_data_from_db()

    processed_df, _ = preprocess_player_data(player_df)
    backtest_df = processed_df.dropna(subset=features + ["mv_target_clipped", "mv_target"]).copy()
    backtest_df["date"] = pd.to_datetime(backtest_df["date"])

    train_df, test_df = split_backtest_data(backtest_df)
    if train_df.empty or test_df.empty:
        raise RuntimeError("Not enough historical data for backtesting.")

    model = train_model(
        train_df[features],
        train_df["mv_target_clipped"],
        n_estimators=int(os.getenv("BACKTEST_MODEL_N_ESTIMATORS", "300")),
    )
    predictions = model.predict(test_df[features])
    test_df = test_df.copy()
    test_df["prediction"] = predictions

    signs_percent, rmse, mae, r2 = evaluate_model(
        model,
        test_df[features],
        test_df["mv_target_clipped"],
    )
    top_trade_summary = simulate_top_trades(test_df)

    generated_at = datetime.now(ZoneInfo("Europe/Berlin")).isoformat(timespec="seconds")
    summary = {
        "generated_at": generated_at,
        "target": "1T",
        "train_rows": int(len(train_df)),
        "test_rows": int(len(test_df)),
        "test_days": int(test_df["date"].dt.date.nunique()),
        "test_start": test_df["date"].min().date().isoformat(),
        "test_end": test_df["date"].max().date().isoformat(),
        "direction_accuracy_pct": round(float(signs_percent), 2),
        "mae": round(float(mae), 2),
        "rmse": round(float(rmse), 2),
        "r2": round(float(r2), 4),
        **top_trade_summary,
    }

    with open(SUMMARY_PATH, "w", encoding="utf-8") as file:
        json.dump(summary, file, ensure_ascii=False, indent=2)

    print("\n=== Model Backtest Summary ===")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


def split_backtest_data(df):
    backtest_days = int(os.getenv("BACKTEST_DAYS", "30"))
    min_test_rows = int(os.getenv("BACKTEST_MIN_TEST_ROWS", "500"))

    max_date = df["date"].max()
    cutoff = max_date - pd.Timedelta(days=backtest_days)
    train_df = df[df["date"] < cutoff]
    test_df = df[df["date"] >= cutoff]

    if len(test_df) < min_test_rows or train_df.empty:
        df = df.sort_values("date").reset_index(drop=True)
        split_idx = int(len(df) * 0.75)
        train_df = df.iloc[:split_idx]
        test_df = df.iloc[split_idx:]

    return train_df, test_df


def simulate_top_trades(test_df):
    positive_candidates = test_df[test_df["prediction"] > 0].copy()
    if positive_candidates.empty:
        return {
            "top_trades": 0,
            "top_trade_hit_rate_pct": 0,
            "top_trade_avg_profit": 0,
            "top_trade_total_profit": 0,
        }

    top_n = int(os.getenv("BACKTEST_TOP_N_PER_DAY", "10"))
    selected = (
        positive_candidates.sort_values(["date", "prediction"], ascending=[True, False])
        .groupby(positive_candidates["date"].dt.date, group_keys=False)
        .head(top_n)
    )
    actual_profit = selected["mv_target"]
    hit_rate = (actual_profit > 0).mean() * 100 if len(selected) else 0

    return {
        "top_trades": int(len(selected)),
        "top_trade_hit_rate_pct": round(float(hit_rate), 2),
        "top_trade_avg_profit": round(float(actual_profit.mean()), 2) if len(selected) else 0,
        "top_trade_total_profit": round(float(actual_profit.sum()), 2) if len(selected) else 0,
    }


if __name__ == "__main__":
    main()
