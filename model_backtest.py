from datetime import datetime
from zoneinfo import ZoneInfo
import json
import os

import numpy as np
import pandas as pd
from dotenv import load_dotenv

from features.predictions.data_handler import (
    check_if_data_reload_needed,
    create_player_data_table,
    load_player_data_from_db,
    load_market_snapshots,
    save_player_data_to_db,
    create_market_snapshot_table,
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
    create_market_snapshot_table()
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
    daily_best_pick_summary = simulate_top_trades(test_df, top_n=1)
    momentum_baseline = evaluate_momentum_baseline(test_df)
    phase_summaries = build_phase_summaries(test_df)
    walk_forward_summary = build_walk_forward_summary(backtest_df, test_df)
    market_snapshot_summary = evaluate_saved_market_snapshots(test_df, load_market_snapshots())

    generated_at = datetime.now(ZoneInfo("Europe/Berlin")).isoformat(timespec="seconds")
    summary = {
        "generated_at": generated_at,
        "target": "1T",
        "current_market_phase": current_market_phase(test_df),
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
        "daily_best_pick": daily_best_pick_summary,
        "momentum_baseline": momentum_baseline,
        "top_trade_assumptions": {
            "selection": "Model's highest positive 1T predictions per day",
            "historical_market_availability": "Only verified after market snapshots have been collected",
            "budget_and_roster_limits": "not simulated in the historical model test",
        },
        "walk_forward": walk_forward_summary,
        "market_snapshot_validation": market_snapshot_summary,
        "phases": phase_summaries,
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


def simulate_top_trades(test_df, top_n=None, prediction_column="prediction"):
    positive_candidates = test_df[test_df[prediction_column] > 0].copy()
    if positive_candidates.empty:
        return {
            "top_trades": 0,
            "top_trade_hit_rate_pct": 0,
            "top_trade_avg_profit": 0,
            "top_trade_total_profit": 0,
        }

    top_n = top_n or int(os.getenv("BACKTEST_TOP_N_PER_DAY", "10"))
    selected = (
        positive_candidates.sort_values(["date", prediction_column], ascending=[True, False])
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


def summarize_prediction(df, prediction_column):
    """Evaluate one prediction method against the common, clipped 1T target."""

    if df.empty:
        return {"rows": 0, "days": 0}
    actual = df["mv_target_clipped"]
    predicted = df[prediction_column].fillna(0)
    errors = actual - predicted
    direction_accuracy = (actual.apply(sign) == predicted.apply(sign)).mean() * 100
    total_variation = ((actual - actual.mean()) ** 2).sum()
    r2 = 0.0 if total_variation == 0 else 1 - (errors.pow(2).sum() / total_variation)
    return {
        "rows": int(len(df)),
        "days": int(pd.to_datetime(df["date"]).dt.date.nunique()),
        "direction_accuracy_pct": round(float(direction_accuracy), 2),
        "mae": round(float(errors.abs().mean()), 2),
        "rmse": round(float((errors.pow(2).mean()) ** 0.5), 2),
        "r2": round(float(r2), 4),
        "daily_best_pick": simulate_top_trades(df, top_n=1, prediction_column=prediction_column),
    }


def build_walk_forward_summary(backtest_df, test_df):
    """Retest every day with a model that has only seen earlier market values."""

    rows = []
    window_days = int(os.getenv("BACKTEST_WALK_FORWARD_WINDOW_DAYS", "180"))
    estimators = int(os.getenv("BACKTEST_WALK_FORWARD_ESTIMATORS", "120"))
    for date, day_df in test_df.groupby(test_df["date"].dt.normalize(), sort=True):
        history = backtest_df[backtest_df["date"] < date]
        if window_days > 0:
            history = history[history["date"] >= date - pd.Timedelta(days=window_days)]
        history = history.dropna(subset=features + ["mv_target_clipped"])
        if history.empty:
            continue

        model = train_model(history[features], history["mv_target_clipped"], n_estimators=estimators)
        current = day_df.copy()
        current["model_prediction"] = model.predict(current[features])
        current["momentum_prediction"] = current["mv_change_1d"].fillna(0)
        momentum_sign = np.sign(current["momentum_prediction"])
        current["ensemble_prediction"] = np.where(
            momentum_sign != 0,
            momentum_sign * current["model_prediction"].abs(),
            current["model_prediction"],
        )
        rows.append(current)

    if not rows:
        return {"status": "not_enough_history", "rows": 0, "days": 0}

    result = pd.concat(rows, ignore_index=True)
    return {
        "status": "complete",
        "validation": "walk_forward",
        "training_window_days": window_days,
        "trees_per_daily_model": estimators,
        "model": summarize_prediction(result, "model_prediction"),
        "momentum": summarize_prediction(result, "momentum_prediction"),
        "ensemble": summarize_prediction(result, "ensemble_prediction"),
    }


def evaluate_saved_market_snapshots(test_df, snapshots):
    """Evaluate only player-days proven to have been on the live market."""

    if snapshots is None or snapshots.empty:
        return {
            "status": "collecting",
            "message": "No saved market snapshots yet; future reports will build this sample.",
            "snapshot_days": 0,
            "matched_player_days": 0,
        }

    saved = snapshots.copy()
    saved["market_value_date"] = pd.to_datetime(saved["market_value_date"], errors="coerce").dt.date
    saved["player_id"] = pd.to_numeric(saved["player_id"], errors="coerce")
    saved = saved.dropna(subset=["market_value_date", "player_id"])
    saved = saved.sort_values("observed_at").drop_duplicates(["market_value_date", "player_id"], keep="last")

    candidates = test_df.copy()
    candidates["market_value_date"] = pd.to_datetime(candidates["date"]).dt.date
    candidates["player_id"] = pd.to_numeric(candidates["player_id"], errors="coerce")
    candidates = candidates.merge(
        saved[["market_value_date", "player_id"]],
        on=["market_value_date", "player_id"],
        how="inner",
    )
    if candidates.empty:
        return {
            "status": "collecting",
            "message": "Snapshots exist, but none overlap with the current backtest period yet.",
            "snapshot_days": int(saved["market_value_date"].nunique()),
            "matched_player_days": 0,
        }

    candidates["momentum_prediction"] = candidates["mv_change_1d"].fillna(0)
    momentum_sign = np.sign(candidates["momentum_prediction"])
    candidates["ensemble_prediction"] = np.where(
        momentum_sign != 0,
        momentum_sign * candidates["prediction"].abs(),
        candidates["prediction"],
    )
    return {
        "status": "complete",
        "snapshot_days": int(saved["market_value_date"].nunique()),
        "matched_player_days": int(len(candidates)),
        "model": summarize_prediction(candidates, "prediction"),
        "momentum": summarize_prediction(candidates, "momentum_prediction"),
        "ensemble": summarize_prediction(candidates, "ensemble_prediction"),
    }


def build_phase_summaries(test_df):
    phased_df = test_df.copy()
    phased_df["market_phase"] = phased_df["date"].map(market_phase)

    summaries = {
        "gesamt": summarize_phase(test_df),
    }
    for phase in ["saisonstart", "saisonbetrieb"]:
        phase_df = phased_df[phased_df["market_phase"] == phase]
        if not phase_df.empty:
            summaries[phase] = summarize_phase(phase_df)
    return summaries


def summarize_phase(df):
    actual = df["mv_target_clipped"]
    predicted = df["prediction"]
    direction_accuracy = (actual.apply(sign) == predicted.apply(sign)).mean() * 100
    errors = (actual - predicted).abs()
    top_trade_summary = simulate_top_trades(df)
    daily_best_pick_summary = simulate_top_trades(df, top_n=1)

    return {
        "rows": int(len(df)),
        "days": int(df["date"].dt.date.nunique()),
        "start": df["date"].min().date().isoformat(),
        "end": df["date"].max().date().isoformat(),
        "direction_accuracy_pct": round(float(direction_accuracy), 2),
        "mae": round(float(errors.mean()), 2),
        **top_trade_summary,
        "daily_best_pick": daily_best_pick_summary,
        "momentum_baseline": evaluate_momentum_baseline(df),
    }


def evaluate_momentum_baseline(df):
    """Evaluate a transparent no-model baseline against the same test target.

    The baseline simply assumes that tomorrow\'s change equals today\'s change.
    A model is only useful when it meaningfully outperforms this simple
    momentum rule on unseen dates.
    """
    actual = df["mv_target_clipped"]
    predicted = df["mv_change_1d"].fillna(0)
    errors = actual - predicted
    direction_accuracy = (actual.apply(sign) == predicted.apply(sign)).mean() * 100
    return {
        "strategy": "Tagesdynamik fortschreiben",
        "direction_accuracy_pct": round(float(direction_accuracy), 2),
        "mae": round(float(errors.abs().mean()), 2),
        "rmse": round(float((errors.pow(2).mean()) ** 0.5), 2),
    }


def current_market_phase(test_df):
    return market_phase(test_df["date"].max())


def market_phase(date_value):
    date = pd.Timestamp(date_value)
    season_start = pd.Timestamp(os.getenv("BACKTEST_SEASON_START", "2026-08-15"))
    start_days = int(os.getenv("BACKTEST_START_PHASE_DAYS", "30"))

    if season_start <= date <= season_start + pd.Timedelta(days=start_days):
        return "saisonstart"
    return "saisonbetrieb"


def sign(value):
    if value > 0:
        return 1
    if value < 0:
        return -1
    return 0


if __name__ == "__main__":
    main()
