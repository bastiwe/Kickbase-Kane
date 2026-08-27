from kickbase_api.league import get_league_activities, get_league_players_on_market
from kickbase_api.user import get_players_in_squad, get_username
from kickbase_api.config import get_cdn_url
from kickbase_api.player import get_player_info
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


FORMATIONS = [
    ("4-4-2", {1: 1, 2: 4, 3: 4, 4: 2}),
    ("3-4-3", {1: 1, 2: 3, 3: 4, 4: 3}),
    ("5-3-2", {1: 1, 2: 5, 3: 3, 4: 2}),
    ("5-4-1", {1: 1, 2: 5, 3: 4, 4: 1}),
    ("3-6-1", {1: 1, 2: 3, 3: 6, 4: 1}),
    ("4-2-4", {1: 1, 2: 4, 3: 2, 4: 4}),
    ("4-3-3", {1: 1, 2: 4, 3: 3, 4: 3}),
    ("3-5-2", {1: 1, 2: 3, 3: 5, 4: 2}),
    ("4-5-1", {1: 1, 2: 4, 3: 5, 4: 1}),
    ("5-2-3", {1: 1, 2: 5, 3: 2, 4: 3}),
]

def add_recommendation_columns(df, is_market):
    """Add trading-oriented columns to make the predictions easier to act on."""

    df = df.copy()
    for column in ["predicted_mv_target", "predicted_mv_target_3d", "predicted_mv_target_7d", "mv"]:
        if column not in df:
            df[column] = np.nan
    if "top_player_tag" not in df:
        df["top_player_tag"] = ""
    df["expected_change_pct"] = np.where(
        df["mv"] > 0,
        np.round((df["predicted_mv_target"] / df["mv"]) * 100, 2),
        0
    )
    df["expected_change_pct_3d"] = np.where(
        df["mv"] > 0,
        np.round((df["predicted_mv_target_3d"] / df["mv"]) * 100, 2),
        0
    )
    df["expected_change_pct_7d"] = np.where(
        df["mv"] > 0,
        np.round((df["predicted_mv_target_7d"] / df["mv"]) * 100, 2),
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
        df["sell_advice"] = np.select(
            [
                (df["predicted_mv_target"] <= -200_000) | (df["expected_change_pct"] <= -2.0),
                (df["predicted_mv_target"] <= -75_000) | (df["expected_change_pct"] <= -0.75),
                df["top_player_tag"].fillna("").astype(str).ne("")
                | (df["predicted_mv_target"] >= 100_000)
                | (df["expected_change_pct"] >= 1.0),
            ],
            ["Vor 22 Uhr verkaufen", "Verkauf prüfen", "Kaderkern/Halten"],
            default="Halten"
        )

    df = add_prediction_confidence(df)

    return df


def add_prediction_confidence(df):
    """Classify how much context the report has for a player's 1-day prediction."""

    result = df.copy()
    score = pd.Series(0, index=result.index, dtype="float64")

    if "predicted_mv_target" in result:
        score += result["predicted_mv_target"].notna().astype(int) * 35
    if "mv_change_1d" in result:
        score += result["mv_change_1d"].notna().astype(int) * 20
    if "mv_change_yesterday" in result:
        score += result["mv_change_yesterday"].notna().astype(int) * 20
    if "mv" in result:
        score += result["mv"].notna().astype(int) * 15
    if "last_season_points" in result:
        score += result["last_season_points"].notna().astype(int) * 12
    if "last_season_avg_points" in result:
        score += result["last_season_avg_points"].notna().astype(int) * 8
    if "top_player_tag" in result:
        score += result["top_player_tag"].fillna("").astype(str).ne("").astype(int) * 8
    if "starter_rate" in result:
        score += pd.to_numeric(result["starter_rate"], errors="coerce").notna().astype(int) * 8

    if "player_status" in result:
        critical_status = result["player_status"].isin([
            "Verletzt",
            "Reha",
            "Rotgesperrt",
            "Gelb-Rot-Sperre",
            "Nicht im Kader",
            "Nicht in Liga",
            "Abwesend",
        ])
        warning_status = result["player_status"].isin(["Angeschlagen", "Gelbsperre"])
        score -= critical_status.astype(int) * 22
        score -= warning_status.astype(int) * 10

    no_prediction = result["predicted_mv_target"].isna() if "predicted_mv_target" in result else pd.Series(True, index=result.index)
    result["prediction_confidence"] = np.select(
        [
            no_prediction,
            score >= 70,
            score >= 45,
        ],
        ["Niedrig", "Hoch", "Mittel"],
        default="Niedrig",
    )
    return result

def live_data_predictions(today_df, models, features, history_df=None, season_start_date=None):
    """Make live data predictions for today_df using the trained model"""

    # Set features and copy df
    today_df_features = today_df[features]
    today_df_results = today_df.copy()

    # Predict market value changes for all configured horizons
    for column, model in models.items():
        today_df_results[column] = np.round(model.predict(today_df_features), 2)
    for optional_column in ["predicted_mv_target_3d", "predicted_mv_target_7d"]:
        if optional_column not in today_df_results:
            today_df_results[optional_column] = 0

    today_df_results = add_player_quality_signals(today_df_results, history_df, season_start_date)

    # Sort by predicted_mv_target descending
    today_df_results = today_df_results.sort_values("predicted_mv_target", ascending=False)

    # Drop rows where NaN mv and keep the latest usable entry for each player.
    today_df_results = today_df_results.dropna(subset=["mv"])
    today_df_results["date"] = pd.to_datetime(today_df_results["date"])
    today_df_results = today_df_results.sort_values(["player_id", "date"]).drop_duplicates("player_id", keep="last")

    # Keep only relevant columns
    today_df_results = today_df_results[[
        "player_id",
        "first_name",
        "last_name",
        "image_url",
        "position",
        "team_name",
        "date",
        "mv_change_1d",
        "mv_trend_1d",
        "mv",
        "predicted_mv_target",
        "predicted_mv_target_3d",
        "predicted_mv_target_7d",
        "last_season_points",
        "last_season_avg_points",
        "top_player_tag",
    ]]

    return today_df_results


def add_player_quality_signals(today_df_results, history_df=None, season_start_date=None):
    """Add last-season quality markers based on deduplicated matchday points."""

    result = today_df_results.copy()
    result["last_season_points"] = np.nan
    result["last_season_avg_points"] = np.nan
    result["top_player_tag"] = ""

    if history_df is None or history_df.empty or not {"player_id", "md", "p"}.issubset(history_df.columns):
        return result

    history = history_df.copy()
    history["md"] = pd.to_datetime(history["md"], errors="coerce")
    history = history.dropna(subset=["player_id", "md", "p"])
    if season_start_date:
        season_start = pd.to_datetime(season_start_date)
        history = history[(history["md"] < season_start) & (history["md"] >= season_start - pd.Timedelta(days=370))]

    history = history.sort_values("md").drop_duplicates(["player_id", "md"], keep="last")
    if history.empty:
        return result

    quality = (
        history.groupby("player_id")
        .agg(
            last_season_points=("p", "sum"),
            last_season_avg_points=("p", "mean"),
            last_season_games=("p", "count"),
        )
        .reset_index()
    )
    quality = quality[quality["last_season_games"] >= 10]
    if quality.empty:
        return result

    quality["quality_rank"] = quality["last_season_points"].rank(method="min", ascending=False)
    enough_players_for_rank = len(quality) >= 50
    quality["top_player_tag"] = np.select(
        [
            (quality["last_season_points"] >= 3000) | (enough_players_for_rank & (quality["quality_rank"] <= 10)),
            (quality["last_season_points"] >= 2200)
            | (enough_players_for_rank & (quality["quality_rank"] <= 30))
            | ((quality["last_season_avg_points"] >= 110) & (quality["last_season_games"] >= 15)),
        ],
        ["Elite-Spieler", "Top-Spieler"],
        default="",
    )

    quality = quality[[
        "player_id",
        "last_season_points",
        "last_season_avg_points",
        "top_player_tag",
    ]]
    result = result.drop(columns=["last_season_points", "last_season_avg_points", "top_player_tag"])
    result = result.merge(quality, on="player_id", how="left")
    result["top_player_tag"] = result["top_player_tag"].fillna("")
    return result


def squad_position_needs(squad_df):
    """Return positions missing for the nearest playable formation."""

    if squad_df is None or squad_df.empty or "position" not in squad_df:
        return set()

    counts = {pos: int((squad_df["position"].astype(str) == str(pos)).sum()) for pos in [1, 2, 3, 4]}
    missing_by_formation = []
    for _, required in FORMATIONS:
        missing = {pos: max(0, required[pos] - counts.get(pos, 0)) for pos in required}
        missing_by_formation.append((sum(missing.values()), missing))

    _, best_missing = sorted(missing_by_formation, key=lambda item: item[0])[0]
    return {pos for pos, amount in best_missing.items() if amount > 0}


def enrich_market_decisions_with_context(market_df, squad_df, manager_budgets_df=None):
    """Add buy type, priority, team-limit warnings, overpay pressure and strategic max bids."""

    if market_df is None or market_df.empty:
        return market_df

    result = market_df.copy()
    needed_positions = squad_position_needs(squad_df)
    team_counts = (
        squad_df["team_name"].dropna().astype(str).value_counts().to_dict()
        if squad_df is not None and not squad_df.empty and "team_name" in squad_df
        else {}
    )

    for col, default in [
        ("starter_rate", np.nan),
        ("top_player_tag", ""),
        ("predicted_mv_target_7d", 0),
        ("expected_change_pct_7d", 0),
        ("predicted_mv_target_3d", 0),
        ("predicted_mv_target", 0),
        ("has_open_bid", False),
        ("player_status", "Fit"),
    ]:
        if col not in result:
            result[col] = default

    def team_warning(team_name):
        team = "" if team_name != team_name else str(team_name)
        count = team_counts.get(team, 0)
        if count >= 3:
            return "Vereinslimit voll"
        if count == 2:
            return "füllt 3/3"
        return ""

    result["team_limit_warning"] = result["team_name"].map(team_warning) if "team_name" in result else ""
    result["position_needed"] = result["position"].astype(str).isin([str(pos) for pos in needed_positions])
    result = add_prediction_confidence(result)

    def priority_score(row):
        score = 0
        tag = str(row.get("top_player_tag", "") or "")
        starter_rate = row.get("starter_rate")
        seven_day_pct = row.get("expected_change_pct_7d", 0)
        seven_day_abs = row.get("predicted_mv_target_7d", 0)

        if tag == "Elite-Spieler":
            score += 40
        elif tag == "Top-Spieler":
            score += 26

        if pd.notna(starter_rate):
            starter_rate = float(starter_rate)
            if starter_rate >= 80:
                score += 25
            elif starter_rate >= 60:
                score += 18
            elif starter_rate >= 40:
                score += 10
            elif starter_rate >= 25:
                score += 5

        if pd.notna(seven_day_pct):
            seven_day_pct = float(seven_day_pct)
            if seven_day_pct >= 5:
                score += 25
            elif seven_day_pct >= 2:
                score += 16
            elif seven_day_pct > 0:
                score += 7
        if pd.notna(seven_day_abs) and float(seven_day_abs) >= 500_000:
            score += 8

        if bool(row.get("position_needed", False)):
            score += 18
        if bool(row.get("has_open_bid", False)):
            score += 8

        status = str(row.get("player_status", "Fit") or "Fit")
        if status in {"Verletzt", "Reha", "Rotgesperrt", "Gelb-Rot-Sperre", "Nicht im Kader", "Nicht in Liga", "Abwesend"}:
            score -= 35
        elif status in {"Angeschlagen", "Gelbsperre"}:
            score -= 15

        warning = row.get("team_limit_warning", "")
        if warning == "Vereinslimit voll":
            score -= 35
        elif warning == "füllt 3/3":
            score -= 8

        return int(max(0, score))

    result["buy_priority_score"] = result.apply(priority_score, axis=1)
    result["buy_priority"] = np.select(
        [
            result["buy_priority_score"] >= 65,
            result["buy_priority_score"] >= 40,
        ],
        ["Hoch", "Mittel"],
        default="Niedrig",
    )
    result["buy_type"] = np.where(
        result["top_player_tag"].fillna("").astype(str).ne("")
        | (pd.to_numeric(result["starter_rate"], errors="coerce").fillna(0) >= 65)
        | (result["position_needed"] & result["buy_priority"].isin(["Hoch", "Mittel"])),
        "Kader-Kauf",
        "Trading-Kauf",
    )
    result = add_opponent_overpay_forecast(result, manager_budgets_df)

    def strategic_max_bid(row):
        mv = row.get("mv", 0)
        if pd.isna(mv):
            return 0
        mv = float(mv)

        upside_1d = max(float(row.get("predicted_mv_target", 0) or 0), 0)
        upside_3d = max(float(row.get("predicted_mv_target_3d", 0) or 0), 0)
        upside_7d = max(float(row.get("predicted_mv_target_7d", 0) or 0), 0)
        tag = str(row.get("top_player_tag", "") or "")

        if row.get("team_limit_warning") == "Vereinslimit voll":
            raw_bid = mv + max(upside_1d * 0.45, upside_3d * 0.25)
        elif row.get("buy_type") == "Kader-Kauf":
            if tag == "Elite-Spieler":
                raw_bid = mv + max(upside_1d * 1.00, upside_3d * 0.65, upside_7d * 0.45)
            elif tag == "Top-Spieler" or row.get("buy_priority") == "Hoch":
                raw_bid = mv + max(upside_1d * 0.90, upside_3d * 0.58, upside_7d * 0.38)
            else:
                raw_bid = mv + max(upside_1d * 0.78, upside_3d * 0.50, upside_7d * 0.32)
        else:
            raw_bid = mv + max(upside_1d * 0.65, upside_3d * 0.30, upside_7d * 0.18)

        status = str(row.get("player_status", "Fit") or "Fit")
        if status in {"Verletzt", "Reha", "Rotgesperrt", "Gelb-Rot-Sperre", "Nicht im Kader", "Nicht in Liga", "Abwesend"}:
            raw_bid = min(raw_bid, mv + (max(upside_1d, 0) * 0.20))
        elif status in {"Angeschlagen", "Gelbsperre"}:
            raw_bid = min(raw_bid, mv + (max(upside_1d, 0) * 0.45))

        return int(psychological_bid(raw_bid))

    result["max_bid"] = result.apply(strategic_max_bid, axis=1)
    result["winning_bid"] = result.apply(estimated_winning_bid, axis=1)
    result["bid_gap"] = result["max_bid"] - result["winning_bid"]

    status_ok = ~result["player_status"].isin(["Verletzt", "Reha", "Rotgesperrt", "Gelb-Rot-Sperre", "Nicht im Kader", "Nicht in Liga", "Abwesend"])
    keep_rows = (
        (result["recommendation"] != "Watch")
        | result["has_open_bid"].fillna(False).astype(bool)
        | result["top_player_tag"].fillna("").astype(str).ne("")
        | result["buy_priority"].isin(["Hoch", "Mittel"])
    )
    keep_rows = keep_rows & (status_ok | result["has_open_bid"].fillna(False).astype(bool) | result["top_player_tag"].fillna("").astype(str).ne(""))
    result = result[keep_rows]

    if "hours_to_exp" in result:
        result["expiry_rank"] = pd.to_numeric(result["hours_to_exp"], errors="coerce").fillna(float("inf"))
    else:
        result["expiry_rank"] = float("inf")
    result["own_bid_rank"] = np.where(result["has_open_bid"].fillna(False).astype(bool), 0, 1)
    result["priority_rank"] = result["buy_priority"].map({"Hoch": 0, "Mittel": 1, "Niedrig": 2}).fillna(3)
    result["top_player_rank"] = np.where(result["top_player_tag"].fillna("").astype(str).ne(""), 0, 1)
    result["limit_rank"] = result["team_limit_warning"].map({"Vereinslimit voll": 2, "füllt 3/3": 1}).fillna(0)
    result["risk_rank"] = result["risk"].map({"Night expiry": 0, "Before MV update": 1}).fillna(2)
    result = result.sort_values(
        [
            "expiry_rank",
            "own_bid_rank",
            "priority_rank",
            "limit_rank",
            "top_player_rank",
            "risk_rank",
            "predicted_mv_target_7d",
            "predicted_mv_target",
        ],
        ascending=[True, True, True, True, True, True, False, False],
    )

    result = result.drop(
        columns=["expiry_rank", "own_bid_rank", "priority_rank", "top_player_rank", "limit_rank", "risk_rank"],
        errors="ignore",
    )
    ordered_columns = [
        "recommendation",
        "buy_type",
        "buy_priority",
        "prediction_confidence",
        "team_limit_warning",
        "opponent_pressure",
        "opponent_overpay_forecast",
        "winning_bid",
        "bid_gap",
        "opponent_overpay_details",
    ]
    remaining_columns = [col for col in result.columns if col not in ordered_columns]
    return result[ordered_columns + remaining_columns]


def estimated_winning_bid(row):
    mv = row.get("mv")
    opponent_overpay = row.get("opponent_overpay_forecast")
    if mv is None or pd.isna(mv) or opponent_overpay is None or pd.isna(opponent_overpay):
        return np.nan
    return int(psychological_bid(float(mv) + max(float(opponent_overpay), 0)))


def add_opponent_overpay_forecast(market_df, manager_budgets_df=None):
    result = market_df.copy()
    result["opponent_overpay_forecast"] = np.nan
    result["opponent_overpay_details"] = ""
    result["opponent_pressure"] = "Unklar"
    result["opponent_overpay_breakdown"] = [[] for _ in range(len(result))]

    if manager_budgets_df is None or not hasattr(manager_budgets_df, "attrs"):
        return result

    profiles = manager_budgets_df.attrs.get("overpay_profiles") or {}
    if not profiles:
        return result

    roster_profiles = manager_budgets_df.attrs.get("roster_profiles") or {}
    own_user = manager_budgets_df.attrs.get("own_user")
    manager_rows = manager_budgets_df.to_dict("records") if not manager_budgets_df.empty else []

    def row_forecast(row):
        forecasts = []
        target_team_key = normalize_forecast_team_key(row.get("team_name"))
        for manager in manager_rows:
            name = manager.get("User")
            if not name or name == own_user:
                continue
            available_budget = manager.get("Available Budget")
            if pd.notna(available_budget) and pd.notna(row.get("mv")) and float(available_budget) < float(row.get("mv")):
                continue
            roster_block = opponent_roster_block(roster_profiles.get(name), target_team_key)
            if roster_block["blocked"]:
                continue

            forecast = forecast_manager_overpay(
                profiles.get(name),
                profiles.get("__league__", {}),
                row.get("mv"),
                row.get("top_player_tag"),
                row.get("buy_type"),
                row.get("position"),
                row.get("predicted_mv_target"),
                explain=True,
            )
            if not forecast:
                continue
            overpay = forecast["overpay"]
            profile = profiles.get(name) or {}
            forecasts.append({
                "name": name,
                "overpay": max(0, round(float(overpay), 0)),
                "available_budget": float(available_budget) if pd.notna(available_budget) else None,
                "roster_note": roster_block["note"],
                "squad_size": roster_block["squad_size"],
                "team_count": roster_block["team_count"],
                "aggression_score": profile.get("aggression_score"),
                "archetype": profile.get("archetype", ""),
                "pattern": manager_pattern_summary(
                    profile,
                    row.get("position"),
                    row.get("predicted_mv_target"),
                    row.get("top_player_tag"),
                    row.get("buy_type"),
                ),
                "explain": forecast,
            })

        if not forecasts:
            return pd.Series({
                "opponent_overpay_forecast": np.nan,
                "opponent_overpay_details": "",
                "opponent_pressure": "Unklar",
                "opponent_overpay_breakdown": [],
            })

        forecasts = sorted(forecasts, key=lambda item: item["overpay"], reverse=True)
        top_overpay = forecasts[0]["overpay"]
        details = ", ".join(f"{item['name']}: +{format_short_money(item['overpay'])}" for item in forecasts[:3])
        mv = row.get("mv")
        mv = 0 if mv is None or pd.isna(mv) else float(mv)
        pressure = overpay_pressure(top_overpay, mv)
        return pd.Series({
            "opponent_overpay_forecast": top_overpay,
            "opponent_overpay_details": details,
            "opponent_pressure": pressure,
            "opponent_overpay_breakdown": forecasts,
        })

    forecast_columns = [
        "opponent_overpay_forecast",
        "opponent_overpay_details",
        "opponent_pressure",
        "opponent_overpay_breakdown",
    ]
    result[forecast_columns] = result.apply(row_forecast, axis=1)
    return result


def forecast_manager_overpay(
    manager_profile,
    league_profile,
    market_value,
    top_player_tag="",
    buy_type="",
    position=None,
    predicted_change=None,
    explain=False,
):
    if market_value is None or pd.isna(market_value):
        return None

    manager_profile = manager_profile or {}
    league_profile = league_profile or {}
    bucket = market_value_bucket_for_forecast(market_value)
    manager_samples = int(manager_profile.get("samples") or 0)
    league_avg = profile_avg(league_profile)
    manager_avg = profile_avg(manager_profile)
    league_segment = segment_avg(league_profile, bucket)
    manager_segment = segment_avg(manager_profile, bucket)

    if league_avg is None and manager_avg is None:
        return None

    base = first_valid(manager_segment, manager_avg, league_segment, league_avg, 0)
    if manager_segment is not None:
        segment_samples = int(manager_profile.get("segments", {}).get(bucket, {}).get("samples") or 0)
        segment_weight = min(segment_samples / 4, 0.75)
        fallback = first_valid(manager_avg, league_segment, league_avg, 0)
        base = (manager_segment * segment_weight) + (fallback * (1 - segment_weight))
    else:
        manager_weight = min(manager_samples / 8, 0.65)
        base = (first_valid(manager_avg, 0) * manager_weight) + (first_valid(league_segment, league_avg, 0) * (1 - manager_weight))

    quality_factor = overpay_quality_factor(market_value, top_player_tag, buy_type)
    pattern_factor = overpay_pattern_factor(manager_profile, position, predicted_change, market_value, top_player_tag)
    escalation_factor = overpay_escalation_factor(manager_profile)
    overpay = max(0, base * quality_factor * pattern_factor * escalation_factor)
    if not explain:
        return overpay
    return {
        "overpay": overpay,
        "base": base,
        "bucket": bucket,
        "manager_avg": manager_avg,
        "manager_segment": manager_segment,
        "league_avg": league_avg,
        "league_segment": league_segment,
        "segment_weight": segment_weight if manager_segment is not None else None,
        "manager_weight": manager_weight if manager_segment is None else None,
        "quality_factor": quality_factor,
        "pattern_factor": pattern_factor,
        "escalation_factor": escalation_factor,
        "position_factor": profile_bias_factor(manager_profile, "position_bias", position_label_key(position), sample_target=4),
        "momentum_factor": profile_bias_factor(manager_profile, "momentum_bias", forecast_momentum_key(predicted_change), sample_target=5),
        "class_factor": profile_bias_factor(manager_profile, "quality_bias", forecast_quality_key(market_value, top_player_tag), sample_target=4),
        "position_key": position_label_key(position),
        "momentum_key": forecast_momentum_key(predicted_change),
        "quality_key": forecast_quality_key(market_value, top_player_tag),
    }


def overpay_pattern_factor(manager_profile, position=None, predicted_change=None, market_value=None, top_player_tag=""):
    if not manager_profile:
        return 1.0
    position_key = position_label_key(position)
    momentum_key = forecast_momentum_key(predicted_change)
    quality_key = forecast_quality_key(market_value, top_player_tag)
    factors = [
        profile_bias_factor(manager_profile, "position_bias", position_key, sample_target=4),
        profile_bias_factor(manager_profile, "momentum_bias", momentum_key, sample_target=5),
        profile_bias_factor(manager_profile, "quality_bias", quality_key, sample_target=4),
    ]
    factor = 1.0
    for item in factors:
        factor *= item
    return min(max(factor, 0.70), 1.45)


def profile_bias_factor(profile, group_name, key, sample_target=4):
    if not key:
        return 1.0
    group = (profile.get(group_name) or {}).get(key)
    avg = profile_avg(profile)
    if not group or avg is None or avg <= 0:
        return 1.0
    samples = int(group.get("samples") or 0)
    if samples <= 0:
        return 1.0
    raw = float(group.get("avg_overpay") or avg) / avg
    weight = min(samples / sample_target, 1.0)
    return 1 + ((min(max(raw, 0.55), 1.75) - 1) * weight)


def overpay_escalation_factor(profile):
    if not profile:
        return 1.0
    avg = profile_avg(profile)
    if avg is None or avg <= 0:
        return 1.0
    p75 = profile.get("p75_overpay")
    stdev = profile.get("stdev_overpay")
    if p75 is None or stdev is None:
        return 1.0
    spread = max(float(p75) - avg, 0) + (float(stdev) * 0.25)
    return min(1.18, 1 + min(spread / max(avg * 3, 1), 0.18))


def manager_pattern_summary(profile, position=None, predicted_change=None, top_player_tag="", buy_type=""):
    if not profile:
        return ""
    parts = []
    archetype = profile.get("archetype")
    if archetype:
        parts.append(str(archetype))
    aggression = profile.get("aggression_score")
    if aggression is not None:
        parts.append(f"Aggro {int(aggression)}/100")

    position_key = position_label_key(position)
    position_text = bias_text(profile, "position_bias", position_key, "Pos")
    if position_text:
        parts.append(position_text)

    momentum_text = bias_text(profile, "momentum_bias", forecast_momentum_key(predicted_change), "Trend")
    if momentum_text:
        parts.append(momentum_text)

    quality_text = bias_text(profile, "quality_bias", forecast_quality_key(None, top_player_tag), "Klasse")
    if quality_text:
        parts.append(quality_text)
    if buy_type == "Kader-Kauf":
        parts.append("Kader-Kauf")
    return " · ".join(parts[:5])


def bias_text(profile, group_name, key, label):
    if not key:
        return ""
    factor = profile_bias_factor(profile, group_name, key)
    samples = int((profile.get(group_name) or {}).get(key, {}).get("samples") or 0)
    if samples < 2:
        return ""
    if factor >= 1.15:
        return f"{label} +{int(round((factor - 1) * 100, 0))}%"
    if factor <= 0.88:
        return f"{label} -{int(round((1 - factor) * 100, 0))}%"
    return ""


def opponent_roster_block(roster_profile, target_team_key):
    if not roster_profile or not roster_profile.get("has_roster_data"):
        return {"blocked": False, "note": "", "squad_size": None, "team_count": None}

    squad_size = int(roster_profile.get("squad_size") or 0)
    team_counts = roster_profile.get("team_counts") or {}
    team_count = int(team_counts.get(target_team_key, 0)) if target_team_key else 0

    if squad_size >= 16:
        return {
            "blocked": True,
            "note": "Kaderlimit 16/16",
            "squad_size": squad_size,
            "team_count": team_count,
        }
    if target_team_key and team_count >= 3:
        return {
            "blocked": True,
            "note": "Vereinslimit 3/3",
            "squad_size": squad_size,
            "team_count": team_count,
        }
    if target_team_key and team_count == 2:
        return {
            "blocked": False,
            "note": "würde 3/3 füllen",
            "squad_size": squad_size,
            "team_count": team_count,
        }
    return {"blocked": False, "note": "", "squad_size": squad_size, "team_count": team_count}


def normalize_forecast_team_key(value):
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    normalized = str(value).lower().replace("ß", "ss")
    normalized = "".join(char if char.isalnum() else " " for char in normalized)
    return " ".join(normalized.split())


def profile_avg(profile):
    value = (profile or {}).get("avg_overpay")
    return None if value is None or pd.isna(value) else float(value)


def segment_avg(profile, bucket):
    value = (profile or {}).get("segments", {}).get(bucket, {}).get("avg_overpay")
    return None if value is None or pd.isna(value) else float(value)


def first_valid(*values):
    for value in values:
        if value is not None and not pd.isna(value):
            return float(value)
    return None


def overpay_quality_factor(market_value, top_player_tag="", buy_type=""):
    tag = str(top_player_tag or "")
    buy_type = str(buy_type or "")
    market_value = float(market_value or 0)
    factor = 1.0
    if market_value >= 30_000_000:
        factor += 0.35
    elif market_value >= 15_000_000:
        factor += 0.18
    if tag == "Elite-Spieler":
        factor += 0.30
    elif tag == "Top-Spieler":
        factor += 0.18
    if buy_type == "Kader-Kauf":
        factor += 0.10
    return factor


def position_label_key(value):
    labels = {1: "TW", 2: "ABW", 3: "MIT", 4: "ST", "1": "TW", "2": "ABW", "3": "MIT", "4": "ST"}
    return labels.get(value, labels.get(str(value), str(value) if value is not None else ""))


PLAYER_STATUS_LABELS = {
    0: "Fit",
    1: "Verletzt",
    2: "Angeschlagen",
    4: "Reha",
    8: "Rotgesperrt",
    16: "Gelb-Rot-Sperre",
    32: "Gelbsperre",
    64: "Nicht im Kader",
    128: "Nicht in Liga",
    256: "Abwesend",
}


def normalize_player_status(value):
    if value is None:
        return "Fit"
    try:
        if pd.isna(value):
            return "Fit"
    except (TypeError, ValueError):
        pass

    if isinstance(value, dict):
        value = value.get("st") or value.get("status") or value.get("v") or value.get("value") or value.get("n")

    if isinstance(value, str):
        cleaned = value.strip()
        if cleaned == "":
            return "Fit"
        normalized = cleaned.lower()
        string_map = {
            "none": "Fit",
            "fit": "Fit",
            "healthy": "Fit",
            "injured": "Verletzt",
            "verletzt": "Verletzt",
            "stricken": "Angeschlagen",
            "angeschlagen": "Angeschlagen",
            "rehab": "Reha",
            "reha": "Reha",
            "absent": "Abwesend",
            "abwesend": "Abwesend",
            "not_in_team": "Nicht im Kader",
            "not in team": "Nicht im Kader",
            "not_in_league": "Nicht in Liga",
            "not in league": "Nicht in Liga",
        }
        if normalized in string_map:
            return string_map[normalized]
        try:
            value = int(float(cleaned))
        except ValueError:
            return cleaned

    try:
        value = int(value)
    except (TypeError, ValueError):
        return str(value)

    if value in PLAYER_STATUS_LABELS:
        return PLAYER_STATUS_LABELS[value]

    labels = [label for bit, label in PLAYER_STATUS_LABELS.items() if bit and value & bit]
    return " + ".join(labels) if labels else "Unbekannt"


def add_player_status_column(df):
    result = df.copy()
    status_sources = [
        "player_status",
        "status",
        "st",
        "playerStatus",
        "player_status_x",
        "player_status_y",
        "status_x",
        "status_y",
        "st_x",
        "st_y",
        "prob",
    ]
    source = None
    for column in status_sources:
        if column in result:
            source = column
            break

    if source is None:
        result["player_status"] = "Fit"
    else:
        result["player_status"] = result[source].map(normalize_player_status)
    return result


def forecast_momentum_key(predicted_change):
    if predicted_change is None or pd.isna(predicted_change):
        return "unknown"
    predicted_change = float(predicted_change)
    if predicted_change >= 50_000:
        return "rising"
    if predicted_change <= -50_000:
        return "falling"
    return "flat"


def forecast_quality_key(market_value=None, top_player_tag=""):
    tag = str(top_player_tag or "")
    if tag == "Elite-Spieler":
        return "elite"
    if tag == "Top-Spieler":
        return "top"
    if market_value is not None and not pd.isna(market_value):
        market_value = float(market_value)
        if market_value >= 30_000_000:
            return "elite"
        if market_value >= 15_000_000:
            return "top"
    return "normal"


def overpay_pressure(overpay, market_value):
    pct = (overpay / market_value) * 100 if market_value else 0
    if overpay >= 1_000_000 or pct >= 5:
        return "Hoch"
    if overpay >= 350_000 or pct >= 2:
        return "Mittel"
    return "Niedrig"


def market_value_bucket_for_forecast(market_value):
    if market_value is None or pd.isna(market_value):
        return "unknown"
    market_value = float(market_value)
    if market_value >= 30_000_000:
        return "30m_plus"
    if market_value >= 15_000_000:
        return "15m_30m"
    if market_value >= 5_000_000:
        return "5m_15m"
    return "under_5m"


def format_short_money(value):
    if value is None or pd.isna(value):
        return "-"
    value = float(value)
    if value >= 1_000_000:
        return f"{value / 1_000_000:.1f} Mio"
    return f"{value / 1_000:.0f}k"


def join_current_squad(token, league_id, today_df_results, current_user_id=None, league_start_date=None, competition_id=1):
    squad_players = get_players_in_squad(token, league_id)
    players_on_market = get_league_players_on_market(token, league_id, current_user_id)
    listed_player_ids = {
        str(player.get("id"))
        for player in players_on_market
        if player.get("is_own_listing") and player.get("id") is not None
    }

    squad_df = pd.DataFrame(squad_players["it"])
    if "i" in squad_df:
        squad_df["squad_player_id"] = squad_df["i"]
    squad_df["purchase_price"] = extract_purchase_price_column(squad_df)
    if "i" in squad_df:
        fallback_purchase_prices = load_own_purchase_prices_from_activities(token, league_id, league_start_date)
        if fallback_purchase_prices:
            activity_prices = squad_df["i"].astype(str).map(fallback_purchase_prices)
            squad_df["purchase_price"] = squad_df["purchase_price"].fillna(activity_prices)
            print(f"Kickbase activity purchase prices matched for squad: {int(activity_prices.notna().sum())}/{len(squad_df)}.")
    if not squad_df.empty and "i" in squad_df:
        squad_df["is_listed_for_sale"] = squad_df["i"].astype(str).isin(listed_player_ids)
    else:
        squad_df["is_listed_for_sale"] = False

    squad_count_before_join = len(squad_df)

    # Keep every current squad player. Some newly bought players can be missing from
    # today's prediction rows or use a player id that does not match our historical data.
    squad_df = (
        pd.merge(
            squad_df,
            today_df_results,
            left_on="i",
            right_on="player_id",
            how="left",
            suffixes=("_squad", ""),
        )
        .drop(columns=["i"], errors="ignore")
    )
    squad_df = hydrate_squad_columns_from_kickbase_payload(squad_df)
    squad_df = hydrate_missing_squad_details(token, competition_id, squad_df)
    squad_df = fill_missing_squad_predictions_by_full_name(squad_df, today_df_results)
    missing_predictions = squad_df["predicted_mv_target"].isna() if "predicted_mv_target" in squad_df else pd.Series(True, index=squad_df.index)
    missing_count = int(missing_predictions.sum())
    if missing_count:
        missing_names = squad_df.loc[missing_predictions].apply(report_player_name, axis=1).head(8).tolist()
        print(
            "Kickbase squad players without prediction match: "
            f"{missing_count}/{squad_count_before_join} ({', '.join(missing_names)})."
        )
    squad_df = add_player_status_column(squad_df)

    # Rename mv_change_1d to mv_change_yesterday for better understanding
    squad_df = squad_df.rename(columns={"mv_change_1d": "mv_change_yesterday"})

    # Rename "mv_x" to "mv" for better understanding
    squad_df = squad_df.rename(columns={"mv_x": "mv"})
    squad_df["squad_profit_loss"] = squad_df["mv"] - squad_df["purchase_price"]

    squad_df = add_recommendation_columns(squad_df, is_market=False)
    squad_df = squad_df.sort_values(
        ["mv_change_yesterday", "predicted_mv_target"],
        ascending=[True, True],
    )

    # Keep only relevant columns
    squad_df = squad_df[[
        "recommendation",
        "first_name",
        "last_name",
        "image_url",
        "position",
        "team_name",
        "player_status",
        "mv",
        "purchase_price",
        "squad_profit_loss",
        "mv_change_yesterday",
        "predicted_mv_target",
        "predicted_mv_target_3d",
        "predicted_mv_target_7d",
        "last_season_points",
        "last_season_avg_points",
        "top_player_tag",
        "prediction_confidence",
        "expected_change_pct",
        "expected_change_pct_3d",
        "expected_change_pct_7d",
        "sell_advice",
        "is_listed_for_sale",
    ]]
    purchase_prices_found = int(squad_df["purchase_price"].notna().sum())
    print(f"Kickbase purchase prices detected for squad: {purchase_prices_found}/{len(squad_df)}.")
    print(f"Kickbase own transfer listings detected: {int(squad_df['is_listed_for_sale'].sum())}.")

    return squad_df 


def hydrate_squad_columns_from_kickbase_payload(df):
    result = df.copy()
    fallback_columns = {
        "player_id": ["player_id", "squad_player_id", "player_id_squad", "id", "pi"],
        "first_name": ["first_name", "first_name_squad", "fn"],
        "last_name": ["last_name", "last_name_squad", "ln", "n"],
        "team_name": ["team_name", "team_name_squad", "tn", "teamName", "clubName", "team"],
        "position": ["position", "position_squad", "pos"],
        "mv": ["mv", "mv_squad", "marketValue", "market_value", "market_value_squad", "mvo", "marketValueOld"],
    }
    for target, candidates in fallback_columns.items():
        result[target] = coalesce_columns(result, candidates)

    if "image_url" not in result or result["image_url"].isna().all():
        result["image_url"] = coalesce_columns(result, ["image_url", "image_url_squad"])
    if "pim" in result:
        image_from_payload = result["pim"].map(lambda value: get_cdn_url(value) if value == value and value else np.nan)
        result["image_url"] = result["image_url"].fillna(image_from_payload)

    numeric_columns = [
        "player_id",
        "position",
        "mv",
        "mv_change_1d",
        "predicted_mv_target",
        "predicted_mv_target_3d",
        "predicted_mv_target_7d",
        "expected_change_pct",
        "expected_change_pct_3d",
        "expected_change_pct_7d",
        "last_season_points",
        "last_season_avg_points",
    ]
    for column in numeric_columns:
        if column in result:
            result[column] = pd.to_numeric(result[column], errors="coerce")

    string_defaults = {
        "first_name": "",
        "last_name": "",
        "image_url": "",
        "team_name": "-",
        "top_player_tag": "",
    }
    for column, default in string_defaults.items():
        if column not in result:
            result[column] = default
        else:
            result[column] = result[column].fillna(default)

    return result


def hydrate_missing_squad_details(token, competition_id, squad_df):
    if squad_df.empty or "player_id" not in squad_df:
        return squad_df

    result = squad_df.copy()
    detail_rows = result[result.apply(needs_player_detail_hydration, axis=1)]
    if detail_rows.empty:
        return result

    enriched = 0
    failed = 0
    for index, row in detail_rows.iterrows():
        player_id = numeric_value(row.get("player_id"))
        if player_id is None:
            continue
        try:
            info = get_player_info(token, competition_id, int(player_id))
        except Exception as exc:
            failed += 1
            print(f"Warning: Could not fetch squad player details for {report_player_name(row)} ({int(player_id)}): {exc}")
            continue

        fill_missing_value(result, index, "first_name", info.get("first_name"))
        fill_missing_value(result, index, "last_name", info.get("last_name"))
        fill_missing_value(result, index, "team_name", info.get("team_name"))
        fill_missing_value(result, index, "position", info.get("position"))
        fill_missing_value(result, index, "image_url", info.get("image_url"))
        enriched += 1

    if enriched or failed:
        print(f"Kickbase squad detail fallback: {enriched} enriched, {failed} failed.")
    return result


def needs_player_detail_hydration(row):
    return (
        is_missing_display_value(row.get("first_name"))
        or is_missing_display_value(row.get("team_name"))
        or is_missing_display_value(row.get("last_name"))
    )


def fill_missing_value(df, index, column, value):
    if value is None:
        return
    if column not in df or is_missing_display_value(df.at[index, column]):
        df.at[index, column] = value


def is_missing_display_value(value):
    if value is None:
        return True
    try:
        if pd.isna(value):
            return True
    except (TypeError, ValueError):
        pass
    return str(value).strip() in {"", "-", "nan", "NaN", "None"}


def fill_missing_squad_predictions_by_full_name(squad_df, today_df_results):
    if squad_df.empty or today_df_results is None or today_df_results.empty:
        return squad_df

    if "predicted_mv_target" not in squad_df:
        squad_df["predicted_mv_target"] = np.nan

    prediction_columns = [
        "first_name",
        "last_name",
        "image_url",
        "position",
        "team_name",
        "date",
        "mv_change_1d",
        "mv_trend_1d",
        "mv",
        "predicted_mv_target",
        "predicted_mv_target_3d",
        "predicted_mv_target_7d",
        "last_season_points",
        "last_season_avg_points",
        "top_player_tag",
    ]

    missing_mask = squad_df["predicted_mv_target"].isna()
    if not missing_mask.any():
        return squad_df

    predictions = today_df_results.copy()
    predictions["_full_name_key"] = predictions.apply(
        lambda row: player_full_name_key(row.get("first_name"), row.get("last_name")),
        axis=1,
    )
    prediction_counts = predictions["_full_name_key"].value_counts()
    predictions = predictions[
        predictions["_full_name_key"].ne("")
        & predictions["_full_name_key"].map(prediction_counts).eq(1)
    ].drop_duplicates("_full_name_key", keep="last")
    if predictions.empty:
        return fill_missing_squad_predictions_by_identity(squad_df, today_df_results, prediction_columns)

    prediction_by_name = predictions.set_index("_full_name_key")

    matched = 0
    for index in squad_df[missing_mask].index:
        key = player_full_name_key(squad_df.at[index, "first_name"], squad_df.at[index, "last_name"])
        if not key or key not in prediction_by_name.index:
            continue
        prediction = prediction_by_name.loc[key]
        for column in prediction_columns:
            if column in prediction:
                squad_df.at[index, column] = prediction[column]
        matched += 1

    if matched:
        print(f"Kickbase squad prediction name fallback matched: {matched}.")
    return fill_missing_squad_predictions_by_identity(squad_df, today_df_results, prediction_columns)


def fill_missing_squad_predictions_by_identity(squad_df, today_df_results, prediction_columns):
    missing_mask = squad_df["predicted_mv_target"].isna()
    if not missing_mask.any():
        return squad_df

    predictions = today_df_results.copy()
    predictions["_last_name_key"] = predictions["last_name"].map(normalize_text_key) if "last_name" in predictions else ""
    predictions["_position_key"] = pd.to_numeric(predictions.get("position"), errors="coerce")
    predictions["_mv_key"] = pd.to_numeric(predictions.get("mv"), errors="coerce")

    matched = 0
    for index in squad_df[missing_mask].index:
        last_name_key = normalize_text_key(squad_df.at[index, "last_name"])
        position = numeric_value(squad_df.at[index, "position"])
        market_value = numeric_value(squad_df.at[index, "mv"])
        if not last_name_key or position is None or market_value is None:
            continue

        candidates = predictions[
            predictions["_last_name_key"].eq(last_name_key)
            & predictions["_position_key"].eq(position)
            & predictions["_mv_key"].notna()
        ].copy()
        if candidates.empty:
            continue

        candidates["_mv_distance"] = (candidates["_mv_key"] - market_value).abs()
        max_distance = max(150_000, market_value * 0.03)
        candidates = candidates[candidates["_mv_distance"] <= max_distance].sort_values("_mv_distance")
        if len(candidates) != 1:
            continue

        prediction = candidates.iloc[0]
        for column in prediction_columns:
            if column in prediction:
                squad_df.at[index, column] = prediction[column]
        matched += 1

    if matched:
        print(f"Kickbase squad prediction identity fallback matched: {matched}.")
    return squad_df


def player_full_name_key(first_name, last_name):
    return normalize_text_key(f"{clean_report_value(first_name)} {clean_report_value(last_name)}")


def normalize_text_key(value):
    return " ".join(
        "".join(char.lower() if char.isalnum() else " " for char in str(value).replace("ß", "ss")).split()
    )


def coalesce_columns(df, candidates):
    values = pd.Series(np.nan, index=df.index)
    for column in candidates:
        if column in df:
            values = values.fillna(df[column])
    return values


def report_player_name(row):
    first_name = first_clean_report_value(row, ["first_name", "fn"])
    last_name = first_clean_report_value(row, ["last_name", "ln", "n"])
    return f"{first_name} {last_name}".strip() or str(row.get("player_id") or "Unbekannt")


def first_clean_report_value(row, columns):
    for column in columns:
        value = clean_report_value(row.get(column))
        if value:
            return value
    return ""


def clean_report_value(value):
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except (TypeError, ValueError):
        pass
    return str(value)


def extract_purchase_price_column(squad_df):
    if squad_df is None or squad_df.empty:
        return pd.Series(dtype="float64")

    candidates = [
        "purchase_price",
        "purchasePrice",
        "buy_price",
        "buyPrice",
        "paid_price",
        "paidPrice",
        "acquisition_price",
        "acquisitionPrice",
        "trp",
        "prc",
        "bp",
        "bpr",
        "cp",
        "op",
    ]
    for column in candidates:
        if column in squad_df:
            values = pd.to_numeric(squad_df[column], errors="coerce")
            if values.notna().any():
                print(f"Kickbase squad purchase price source column: {column}.")
                return values

    print("Kickbase squad purchase price source column: none found.")
    return pd.Series(np.nan, index=squad_df.index, dtype="float64")


def load_own_purchase_prices_from_activities(token, league_id, league_start_date):
    if not league_start_date:
        print("Kickbase activity purchase price fallback skipped: league_start_date is not configured.")
        return {}

    try:
        own_username = get_username(token)
        activities, _, _ = get_league_activities(token, league_id, league_start_date)
    except Exception as exc:
        print(f"Warning: Could not load own purchase prices from activities: {exc}")
        return {}

    if not activities:
        print("Kickbase activity purchase price fallback: no transfer activities found.")
        return {}

    own_key = normalize_name_key(own_username)
    purchases = []
    for activity in activities:
        buyer = normalize_name_key(activity.get("byr"))
        player_id = activity.get("pi")
        price = numeric_value(activity.get("trp"), activity.get("prc"))
        if buyer != own_key or player_id is None or price is None:
            continue
        purchases.append({
            "player_id": str(player_id),
            "price": price,
            "date": activity.get("dt") or "",
        })

    if not purchases:
        print("Kickbase activity purchase price fallback: no own buys matched.")
        return {}

    purchases_df = pd.DataFrame(purchases).sort_values("date")
    latest_prices = purchases_df.groupby("player_id")["price"].last().to_dict()
    print(f"Kickbase activity purchase price fallback: {len(latest_prices)} own player prices found.")
    return latest_prices


def normalize_name_key(value):
    if value is None or pd.isna(value):
        return ""
    return str(value).strip().casefold()


def numeric_value(*values):
    for value in values:
        if value is None:
            continue
        try:
            numeric = pd.to_numeric(value, errors="coerce")
            if pd.notna(numeric):
                return float(numeric)
        except (TypeError, ValueError):
            continue
    return None


def join_current_market(token, league_id, today_df_results, current_user_id=None):
    """Join the live predictions with the current market data to get bid recommendations"""

    players_on_market = get_league_players_on_market(token, league_id, current_user_id)

    # players_on_market to DataFrame
    market_df = pd.DataFrame(players_on_market)

    # Join market_df ("id") with today_df ("player_id")
    bid_df = (
        pd.merge(today_df_results, market_df, left_on="player_id", right_on="id")
        .drop(columns=["id"])
    )
    bid_df = add_player_status_column(bid_df)

    # exp contains seconds until expiration. Kickbase can occasionally omit it.
    exp_values = bid_df["exp"] if "exp" in bid_df else pd.Series(np.nan, index=bid_df.index)
    bid_df["exp"] = pd.to_numeric(exp_values, errors="coerce")
    bid_df["hours_to_exp"] = np.round((bid_df["exp"] / 3600), 2)
    now = datetime.now(ZoneInfo("Europe/Berlin"))
    bid_df["expires_at"] = bid_df["exp"].map(lambda seconds: expiry_from_seconds(seconds, now))

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
    own_open_bids_total = int(bid_df["has_open_bid"].sum())

    # Sort broadly here; the final strategic filtering happens after LigaInsider and squad context are available.
    bid_df["own_bid_rank"] = np.where(bid_df["has_open_bid"], 0, 1)
    bid_df["top_player_rank"] = np.where(bid_df["top_player_tag"].fillna("").astype(str).ne(""), 0, 1)
    bid_df["risk_rank"] = bid_df["risk"].map({"Night expiry": 0, "Before MV update": 1}).fillna(2)
    bid_df = bid_df.sort_values(
        ["own_bid_rank", "top_player_rank", "risk_rank", "predicted_mv_target", "expected_change_pct"],
        ascending=[True, True, True, False, False],
    )

    # Keep only relevant columns
    bid_df = bid_df[[
        "recommendation",
        "first_name",
        "last_name",
        "image_url",
        "position",
        "team_name",
        "player_status",
        "mv",
        "max_bid",
        "mv_change_yesterday",
        "predicted_mv_target",
        "predicted_mv_target_3d",
        "predicted_mv_target_7d",
        "last_season_points",
        "last_season_avg_points",
        "top_player_tag",
        "prediction_confidence",
        "expected_change_pct",
        "expected_change_pct_3d",
        "expected_change_pct_7d",
        "hours_to_exp",
        "expires_at",
        "risk",
        "has_open_bid",
    ]]
    print(
        f"Kickbase own open bids detected: {own_open_bids_total} total, "
        "final market recommendations are filtered after squad and LigaInsider context."
    )

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


def expiry_from_seconds(seconds, now):
    if pd.isna(seconds):
        return pd.NaT

    try:
        seconds = float(seconds)
    except (TypeError, ValueError):
        return pd.NaT

    if not np.isfinite(seconds):
        return pd.NaT

    return now + timedelta(seconds=seconds)
