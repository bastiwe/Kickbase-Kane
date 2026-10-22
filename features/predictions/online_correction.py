"""Persistent online calibration for the 1-day market-value forecast.

The batch Random Forest remains the primary model. This module records each
forecast before its target market-value update and learns a conservative
calibration only after the actual change is known.
"""

from __future__ import annotations

from datetime import datetime, timedelta
import math
import os
from pathlib import Path
import sqlite3
from zoneinfo import ZoneInfo

import joblib
import numpy as np
import pandas as pd
from sklearn.linear_model import SGDRegressor


DB_PATH = "player_data_total.db"
MODEL_PATH = "online_mv_correction.joblib"
BERLIN = ZoneInfo("Europe/Berlin")
VALUE_SCALE = 100_000.0
MIN_SAMPLES_FOR_PREDICTION = 1_500
MAX_CORRECTION_EUR = 75_000.0


def create_online_forecast_table() -> None:
    """Create the forecast journal independently of the player-history reload."""
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS online_forecast_observations (
                target_date TEXT NOT NULL,
                player_id TEXT NOT NULL,
                generated_at TEXT NOT NULL,
                base_prediction REAL NOT NULL,
                momentum_1d REAL,
                actual_change REAL,
                online_prediction REAL,
                settled_at TEXT,
                PRIMARY KEY (target_date, player_id)
            )
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_online_forecast_unsettled
            ON online_forecast_observations (settled_at, target_date)
            """
        )


def forecast_target_date(generated_at: datetime | None = None):
    """Return the calendar date of the next 22:00 market-value update."""
    generated_at = generated_at or datetime.now(BERLIN)
    if generated_at.tzinfo is None:
        generated_at = generated_at.replace(tzinfo=BERLIN)
    local_time = generated_at.astimezone(BERLIN)
    return local_time.date() if local_time.hour < 22 else (local_time + timedelta(days=1)).date()


def record_online_forecasts(predictions: pd.DataFrame, generated_at: datetime | None = None) -> int:
    """Save the latest pre-update base prediction for each player and target day."""
    if predictions is None or predictions.empty:
        return 0

    generated_at = generated_at or datetime.now(BERLIN)
    target_date = forecast_target_date(generated_at).isoformat()
    generated_text = generated_at.astimezone(BERLIN).isoformat(timespec="seconds")
    rows = []
    for row in predictions.to_dict("records"):
        try:
            player_id = str(int(row["player_id"]))
            base = float(row["predicted_mv_target"])
        except (KeyError, TypeError, ValueError, OverflowError):
            continue
        if not math.isfinite(base):
            continue
        momentum = pd.to_numeric(row.get("mv_change_1d"), errors="coerce")
        rows.append(
            (
                target_date,
                player_id,
                generated_text,
                base,
                float(momentum) if pd.notna(momentum) else None,
            )
        )

    if not rows:
        return 0

    create_online_forecast_table()
    with sqlite3.connect(DB_PATH) as conn:
        conn.executemany(
            """
            INSERT INTO online_forecast_observations (
                target_date, player_id, generated_at, base_prediction, momentum_1d
            ) VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(target_date, player_id) DO UPDATE SET
                generated_at = excluded.generated_at,
                base_prediction = excluded.base_prediction,
                momentum_1d = excluded.momentum_1d,
                actual_change = NULL,
                online_prediction = NULL,
                settled_at = NULL
            """,
            rows,
        )
    print(f"Online calibration: recorded {len(rows)} forecasts for {target_date}.")
    return len(rows)


def _feature_rows(base_predictions, momenta):
    """Normalise values so incremental SGD training is numerically stable."""
    base = np.asarray(base_predictions, dtype=float) / VALUE_SCALE
    momentum = np.asarray(momenta, dtype=float) / VALUE_SCALE
    return np.column_stack((base, momentum))


def _load_state():
    try:
        state = joblib.load(MODEL_PATH)
        if isinstance(state, dict) and "model" in state and "samples" in state:
            return state
    except (OSError, ValueError, EOFError):
        pass
    return {
        "model": SGDRegressor(
            loss="huber",
            penalty="l2",
            alpha=0.001,
            learning_rate="invscaling",
            eta0=0.03,
            power_t=0.25,
            random_state=42,
        ),
        "samples": 0,
    }


def _save_state(state) -> None:
    joblib.dump(state, MODEL_PATH)


def _actual_market_changes(player_df: pd.DataFrame) -> dict[tuple[str, str], float]:
    """Map (market date, player id) to a raw, un-clipped daily MV change."""
    required = {"player_id", "date", "mv"}
    if player_df is None or player_df.empty or not required.issubset(player_df.columns):
        return {}

    history = player_df[list(required)].copy()
    history["date"] = pd.to_datetime(history["date"], errors="coerce")
    history["mv"] = pd.to_numeric(history["mv"], errors="coerce")
    history = history.dropna(subset=["player_id", "date", "mv"])
    history = history.sort_values(["player_id", "date"]).drop_duplicates(["player_id", "date"], keep="last")
    history["previous_mv"] = history.groupby("player_id")["mv"].shift(1)
    history["actual_change"] = history["mv"] - history["previous_mv"]
    history = history.dropna(subset=["actual_change"])
    return {
        (stamp.date().isoformat(), str(int(player_id))): float(change)
        for player_id, stamp, change in history[["player_id", "date", "actual_change"]].itertuples(index=False)
    }


def _conservative_prediction(state, base_prediction: float, momentum: float) -> float | None:
    if state["samples"] < MIN_SAMPLES_FOR_PREDICTION:
        return None
    raw = float(state["model"].predict(_feature_rows([base_prediction], [momentum]))[0] * VALUE_SCALE)
    if not math.isfinite(raw):
        return None
    return float(np.clip(raw, base_prediction - MAX_CORRECTION_EUR, base_prediction + MAX_CORRECTION_EUR))


def settle_online_forecasts(player_df: pd.DataFrame, settled_at: datetime | None = None) -> int:
    """Learn only from forecasts whose target market day is now present locally."""
    create_online_forecast_table()
    changes = _actual_market_changes(player_df)
    if not changes:
        return 0

    with sqlite3.connect(DB_PATH) as conn:
        pending = pd.read_sql(
            """
            SELECT target_date, player_id, base_prediction, momentum_1d
            FROM online_forecast_observations
            WHERE settled_at IS NULL
            """,
            conn,
        )
    if pending.empty:
        return 0

    pending["actual_change"] = [
        changes.get((str(row.target_date), str(row.player_id)))
        for row in pending.itertuples(index=False)
    ]
    settled = pending.dropna(subset=["actual_change"]).copy()
    if settled.empty:
        return 0

    state = _load_state()
    momenta = pd.to_numeric(settled["momentum_1d"], errors="coerce").fillna(0.0)
    online_predictions = [
        _conservative_prediction(state, float(base), float(momentum))
        for base, momentum in zip(settled["base_prediction"], momenta)
    ]

    features = _feature_rows(settled["base_prediction"], momenta)
    target = settled["actual_change"].to_numpy(dtype=float) / VALUE_SCALE
    state["model"].partial_fit(features, target)
    state["samples"] += int(len(settled))
    _save_state(state)

    settled_at = settled_at or datetime.now(BERLIN)
    updates = [
        (
            float(actual),
            prediction,
            settled_at.astimezone(BERLIN).isoformat(timespec="seconds"),
            str(target_date),
            str(player_id),
        )
        for target_date, player_id, actual, prediction in settled[
            ["target_date", "player_id", "actual_change"]
        ].itertuples(index=False, name=None)
    ]
    with sqlite3.connect(DB_PATH) as conn:
        conn.executemany(
            """
            UPDATE online_forecast_observations
            SET actual_change = ?, online_prediction = ?, settled_at = ?
            WHERE target_date = ? AND player_id = ?
            """,
            updates,
        )

    print(
        "Online calibration: settled "
        f"{len(settled)} forecasts; persistent sample count {state['samples']}."
    )
    return int(len(settled))


def apply_online_correction(predictions: pd.DataFrame, mode: str | None = None) -> pd.DataFrame:
    """Add a shadow prediction, optionally blending it into the report forecast."""
    if predictions is None or predictions.empty:
        return predictions

    result = predictions.copy()
    state = _load_state()
    bases = pd.to_numeric(result.get("predicted_mv_target"), errors="coerce")
    momenta = pd.to_numeric(result.get("mv_change_1d"), errors="coerce").fillna(0.0)
    corrected = [
        _conservative_prediction(state, float(base), float(momentum))
        if pd.notna(base) else None
        for base, momentum in zip(bases, momenta)
    ]
    result["predicted_mv_target_online"] = corrected
    result["online_correction_eur"] = [
        corrected_value - base if corrected_value is not None and pd.notna(base) else None
        for corrected_value, base in zip(corrected, bases)
    ]

    usable = sum(value is not None for value in corrected)
    if usable:
        print(f"Online calibration shadow forecast available for {usable} players.")
    else:
        print(
            "Online calibration is collecting data "
            f"({state['samples']}/{MIN_SAMPLES_FOR_PREDICTION} settled forecasts)."
        )

    if (mode or os.getenv("ONLINE_CORRECTION_MODE", "shadow")).lower() == "blend":
        result["predicted_mv_target"] = [
            corrected_value if corrected_value is not None else base
            for corrected_value, base in zip(corrected, bases)
        ]
        print("Online calibration is active: blended into the 1T report forecast.")
    return result


def online_correction_status() -> dict:
    """Expose honest shadow-mode metrics for reports and backtests."""
    create_online_forecast_table()
    with sqlite3.connect(DB_PATH) as conn:
        observations = pd.read_sql(
            """
            SELECT base_prediction, online_prediction, actual_change
            FROM online_forecast_observations
            WHERE actual_change IS NOT NULL
            """,
            conn,
        )
    state = _load_state()
    status = {
        "mode": os.getenv("ONLINE_CORRECTION_MODE", "shadow").lower(),
        "settled_forecasts": int(len(observations)),
        "persistent_training_samples": int(state["samples"]),
        "minimum_samples_for_prediction": MIN_SAMPLES_FOR_PREDICTION,
        "ready": bool(state["samples"] >= MIN_SAMPLES_FOR_PREDICTION),
    }
    comparable = observations.dropna(subset=["online_prediction"])
    if not comparable.empty:
        actual = comparable["actual_change"]
        status["shadow_comparable_forecasts"] = int(len(comparable))
        status["base_mae"] = round(float((actual - comparable["base_prediction"]).abs().mean()), 2)
        status["online_mae"] = round(float((actual - comparable["online_prediction"]).abs().mean()), 2)
    return status
