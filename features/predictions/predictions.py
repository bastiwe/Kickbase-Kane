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

    return df

def live_data_predictions(today_df, models, features, history_df=None, season_start_date=None):
    """Make live data predictions for today_df using the trained model"""

    # Set features and copy df
    today_df_features = today_df[features]
    today_df_results = today_df.copy()

    # Predict market value changes for all configured horizons
    for column, model in models.items():
        today_df_results[column] = np.round(model.predict(today_df_features), 2)

    today_df_results = add_player_quality_signals(today_df_results, history_df, season_start_date)

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


def enrich_market_decisions_with_context(market_df, squad_df):
    """Add buy type, priority, team-limit warnings and strategic max bids."""

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

        return int(psychological_bid(raw_bid))

    result["max_bid"] = result.apply(strategic_max_bid, axis=1)

    keep_rows = (
        (result["recommendation"] != "Watch")
        | result["has_open_bid"].fillna(False).astype(bool)
        | result["top_player_tag"].fillna("").astype(str).ne("")
        | result["buy_priority"].isin(["Hoch", "Mittel"])
    )
    result = result[keep_rows]

    result["own_bid_rank"] = np.where(result["has_open_bid"].fillna(False).astype(bool), 0, 1)
    result["priority_rank"] = result["buy_priority"].map({"Hoch": 0, "Mittel": 1, "Niedrig": 2}).fillna(3)
    result["top_player_rank"] = np.where(result["top_player_tag"].fillna("").astype(str).ne(""), 0, 1)
    result["limit_rank"] = result["team_limit_warning"].map({"Vereinslimit voll": 2, "füllt 3/3": 1}).fillna(0)
    result["risk_rank"] = result["risk"].map({"Night expiry": 0, "Before MV update": 1}).fillna(2)
    result = result.sort_values(
        [
            "own_bid_rank",
            "priority_rank",
            "limit_rank",
            "top_player_rank",
            "risk_rank",
            "predicted_mv_target_7d",
            "predicted_mv_target",
        ],
        ascending=[True, True, True, True, True, False, False],
    )

    result = result.drop(
        columns=["own_bid_rank", "priority_rank", "top_player_rank", "limit_rank", "risk_rank"],
        errors="ignore",
    )
    ordered_columns = [
        "recommendation",
        "buy_type",
        "buy_priority",
        "team_limit_warning",
    ]
    remaining_columns = [col for col in result.columns if col not in ordered_columns]
    return result[ordered_columns + remaining_columns]


def join_current_squad(token, league_id, today_df_results, current_user_id=None):
    squad_players = get_players_in_squad(token, league_id)
    players_on_market = get_league_players_on_market(token, league_id, current_user_id)
    listed_player_ids = {
        str(player.get("id"))
        for player in players_on_market
        if player.get("is_own_listing") and player.get("id") is not None
    }

    squad_df = pd.DataFrame(squad_players["it"])
    if not squad_df.empty and "i" in squad_df:
        squad_df["is_listed_for_sale"] = squad_df["i"].astype(str).isin(listed_player_ids)
    else:
        squad_df["is_listed_for_sale"] = False

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
    squad_df = squad_df[[
        "recommendation",
        "first_name",
        "last_name",
        "image_url",
        "position",
        "team_name",
        "mv",
        "mv_change_yesterday",
        "predicted_mv_target",
        "predicted_mv_target_3d",
        "predicted_mv_target_7d",
        "last_season_points",
        "last_season_avg_points",
        "top_player_tag",
        "expected_change_pct",
        "expected_change_pct_3d",
        "expected_change_pct_7d",
        "is_listed_for_sale",
    ]]
    print(f"Kickbase own transfer listings detected: {int(squad_df['is_listed_for_sale'].sum())}.")

    return squad_df 


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
        "mv",
        "max_bid",
        "mv_change_yesterday",
        "predicted_mv_target",
        "predicted_mv_target_3d",
        "predicted_mv_target_7d",
        "last_season_points",
        "last_season_avg_points",
        "top_player_tag",
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
