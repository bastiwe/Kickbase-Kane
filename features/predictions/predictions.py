from kickbase_api.league import get_league_players_on_market
from kickbase_api.user import get_players_in_squad
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import pandas as pd
import numpy as np

def psychological_bid(value):
    """Round a bid up to common thresholds and add a small overbid amount."""

    if pd.isna(value) or value <= 0:
        return 0

    if value < 1_000_000:
        step, overbid = 10_000, 1_000
    elif value < 5_000_000:
        step, overbid = 50_000, 1_000
    elif value < 15_000_000:
        step, overbid = 100_000, 11_000
    elif value < 30_000_000:
        step, overbid = 250_000, 11_000
    else:
        step, overbid = 500_000, 11_000

    return (np.ceil(value / step) * step) + overbid

def add_recommendation_columns(df, is_market):
    """Add trading-oriented columns to make the predictions easier to act on."""

    df = df.copy()
    df["expected_change_pct"] = np.where(
        df["mv"] > 0,
        np.round((df["predicted_mv_target"] / df["mv"]) * 100, 2),
        0
    )

    if is_market:
        df["recommendation"] = np.select(
            [
                (df["expected_change_pct"] >= 2.0) | (df["predicted_mv_target"] >= 200_000),
                (df["expected_change_pct"] >= 0.75) | (df["predicted_mv_target"] >= 75_000),
            ],
            ["Strong buy", "Buy"],
            default="Watch"
        )
        raw_max_bid = df["mv"] + (df["predicted_mv_target"].clip(lower=0) * 0.65)
        df["max_bid"] = raw_max_bid.map(psychological_bid).astype(int)
        df["risk"] = np.select(
            [
                df["expires_overnight"],
                df["expires_before_mv_update"],
            ],
            ["Night expiry", "Before MV update"],
            default="Normal"
        )
    else:
        df["recommendation"] = np.select(
            [
                (df["expected_change_pct"] <= -2.0) | (df["predicted_mv_target"] <= -200_000),
                (df["expected_change_pct"] <= -0.75) | (df["predicted_mv_target"] <= -75_000),
                (df["expected_change_pct"] >= 1.0) | (df["predicted_mv_target"] >= 100_000),
            ],
            ["Sell", "Consider sell", "Keep"],
            default="Hold"
        )

    return df

def live_data_predictions(today_df, model, features):
    """Make live data predictions for today_df using the trained model"""

    # Set features and copy df
    today_df_features = today_df[features]
    today_df_results = today_df.copy()

    # Predict mv_target
    today_df_results["predicted_mv_target"] = np.round(model.predict(today_df_features), 2)

    # Sort by predicted_mv_target descending
    today_df_results = today_df_results.sort_values("predicted_mv_target", ascending=False)

    # Filter date to today or yesterday if before 22:15, because mv is updated around 22:15
    now = datetime.now(ZoneInfo("Europe/Berlin"))
    cutoff_time = now.replace(hour=22, minute=15, second=0, microsecond=0)
    date = (now - timedelta(days=1)) if now <= cutoff_time else now
    date = date.date()

    # Drop rows where NaN mv
    today_df_results = today_df_results.dropna(subset=["mv"])

    # Keep only relevant columns
    today_df_results = today_df_results[["player_id", "first_name", "last_name", "image_url", "position", "team_name", "date", "mv_change_1d", "mv_trend_1d", "mv", "predicted_mv_target"]]

    return today_df_results


def join_current_squad(token, league_id, today_df_results):
    squad_players = get_players_in_squad(token, league_id)

    squad_df = pd.DataFrame(squad_players["it"])

    # Join squad_df ("i") with today_df ("player_id")
    squad_df = (
        pd.merge(today_df_results, squad_df, left_on="player_id", right_on="i")
        .drop(columns=["i"])
    )

    # Rename mv_change_1d to mv_change_yesterday for better understanding
    squad_df = squad_df.rename(columns={"mv_change_1d": "mv_change_yesterday"})

    # Rename "mv_x" to "mv" for better understanding
    squad_df = squad_df.rename(columns={"mv_x": "mv"})

    squad_df = add_recommendation_columns(squad_df, is_market=False)
    squad_df = squad_df.sort_values("predicted_mv_target", ascending=True)

    # Keep only relevant columns
    squad_df = squad_df[["recommendation", "first_name", "last_name", "image_url", "position", "team_name", "mv", "mv_change_yesterday", "predicted_mv_target", "expected_change_pct"]]

    return squad_df 


def join_current_market(token, league_id, today_df_results):
    """Join the live predictions with the current market data to get bid recommendations"""

    players_on_market = get_league_players_on_market(token, league_id)

    # players_on_market to DataFrame
    market_df = pd.DataFrame(players_on_market)

    # Join market_df ("id") with today_df ("player_id")
    bid_df = (
        pd.merge(today_df_results, market_df, left_on="player_id", right_on="id")
        .drop(columns=["id"])
    )

    # exp contains seconds until expiration
    bid_df["hours_to_exp"] = np.round((bid_df["exp"] / 3600), 2)
    now = datetime.now(ZoneInfo("Europe/Berlin"))
    bid_df["expires_at"] = bid_df["exp"].map(lambda seconds: now + timedelta(seconds=float(seconds)))

    # check if current sysdate + hours_to_exp is after the next 22:00
    next_22 = now.replace(hour=22, minute=0, second=0, microsecond=0)
    if now >= next_22:
        next_22 += timedelta(days=1)
    diff = np.round((next_22 - now).total_seconds() / 3600, 2)

    bid_df["expires_before_mv_update"] = bid_df["hours_to_exp"] < diff
    bid_df["expires_overnight"] = bid_df["expires_at"].map(lambda expires_at: is_night_expiry(expires_at, now))

    # Rename mv_change_1d to mv_change_yesterday for better understanding
    bid_df = bid_df.rename(columns={"mv_change_1d": "mv_change_yesterday"})

    bid_df = add_recommendation_columns(bid_df, is_market=True)

    # Drop weak recommendations from the market overview.
    bid_df = bid_df[bid_df["recommendation"] != "Watch"]

    # Sort urgent expiring offers first, then by expected absolute profit and relative upside.
    bid_df["risk_rank"] = bid_df["risk"].map({"Night expiry": 0, "Before MV update": 1}).fillna(2)
    bid_df = bid_df.sort_values(
        ["risk_rank", "predicted_mv_target", "expected_change_pct"],
        ascending=[True, False, False],
    )

    # Keep only relevant columns
    bid_df = bid_df[["recommendation", "first_name", "last_name", "image_url", "position", "team_name", "mv", "max_bid", "mv_change_yesterday", "predicted_mv_target", "expected_change_pct", "hours_to_exp", "expires_at", "risk"]]

    return bid_df


def is_night_expiry(expires_at, now=None):
    """Return True when an offer expires in the next 22:00-09:00 sleep window."""

    if pd.isna(expires_at):
        return False

    berlin = ZoneInfo("Europe/Berlin")
    current_time = (now or datetime.now(berlin)).astimezone(berlin)
    expiry_time = expires_at.astimezone(berlin)

    today_nine = current_time.replace(hour=9, minute=0, second=0, microsecond=0)
    today_twenty_two = current_time.replace(hour=22, minute=0, second=0, microsecond=0)

    if current_time < today_nine:
        sleep_start = current_time
        sleep_end = today_nine
    elif current_time < today_twenty_two:
        sleep_start = today_twenty_two
        sleep_end = today_twenty_two + timedelta(hours=11)
    else:
        sleep_start = current_time
        sleep_end = today_nine + timedelta(days=1)

    return sleep_start <= expiry_time < sleep_end
