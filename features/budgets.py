from kickbase_api.user import get_budget, get_username
from kickbase_api.league import (
    get_league_activities,
    get_league_ranking
)
from kickbase_api.manager import (
    get_managers,
    get_manager_performance,
    get_manager_info,
)
from kickbase_api.others import get_achievement_reward
import pandas as pd
import sqlite3
import unicodedata
import re
from datetime import timedelta

def calc_manager_budgets(token, league_id, league_start_date, start_budget):
    """Calculate manager budgets based on activities, bonuses, and team performance."""

    try:
        activities, login_bonus, achievement_bonus = get_league_activities(token, league_id, league_start_date)
    except Exception as e:
        raise RuntimeError(f"Failed to fetch activities: {e}")

    activities_df = pd.DataFrame(activities)

    # Bonuses
    total_login_bonus = sum(entry.get("data", {}).get("bn", 0) for entry in login_bonus)

    total_achievement_bonus = 0
    for item in achievement_bonus:
        try:
            a_id = item.get("data", {}).get("t")
            if a_id is None:
                continue
            amount, reward = get_achievement_reward(token, league_id, a_id)
            total_achievement_bonus += amount * reward
        except Exception as e:
            print(f"Warning: Failed to process achievement bonus {item}: {e}")

    # Manager performances
    try:
        managers = get_managers(token, league_id)
    except Exception as e:
        raise RuntimeError(f"Failed to fetch managers: {e}")

    performances = []
    roster_profiles = {}
    for manager in managers:
        try:
            manager_name, manager_id = manager
            info = get_manager_info(token, league_id, manager_id)
            team_value = info.get("tv", 0)
            roster_profiles[manager_name] = extract_roster_profile(info)

            perf = get_manager_performance(token, league_id, manager_id, manager_name)
            perf["Team Value"] = team_value
            performances.append(perf)
        except Exception as e:
            print(f"Warning: Skipping manager {manager}: {e}")

    perf_df = pd.DataFrame(performances)
    if not perf_df.empty:
        perf_df["point_bonus"] = perf_df["tp"].fillna(0) * 1000
    else:
        perf_df["name"] = []
        perf_df["point_bonus"] = []
        perf_df["Team Value"] = []

    # Initial cash budgets. Use all managers, not only users that already have transfer activities.
    budgets = {manager_name: start_budget for manager_name, _ in managers}
    manager_lookup = build_manager_lookup(managers)
    average_overpay, overpay_profiles, overpay_rows = calc_overpay_analysis_by_manager(
        activities_df,
        league_start_date,
        managers,
    )

    for _, row in activities_df.iterrows():
        byr = normalize_activity_name(row.get("byr"), manager_lookup)
        slr = normalize_activity_name(row.get("slr"), manager_lookup)
        trp = first_number(row.get("trp"), row.get("prc")) or 0
        try:
            if pd.isna(byr) and pd.notna(slr):
                budgets.setdefault(slr, start_budget)
                budgets[slr] += trp
            elif pd.isna(slr) and pd.notna(byr):
                budgets.setdefault(byr, start_budget)
                budgets[byr] -= trp
            elif pd.notna(byr) and pd.notna(slr):
                budgets.setdefault(byr, start_budget)
                budgets.setdefault(slr, start_budget)
                budgets[byr] -= trp
                budgets[slr] += trp
        except KeyError as e:
            print(f"Warning: Skipping invalid activity row {row}: {e}")

    budget_df = pd.DataFrame(list(budgets.items()), columns=["User", "Budget"])
    overpay_df = pd.DataFrame(
        list(average_overpay.items()),
        columns=["User", "Avg Overpay"]
    )
    budget_df = budget_df.merge(overpay_df, on="User", how="left")

    # Merge performance bonuses
    budget_df = budget_df.merge(
        perf_df[["name", "point_bonus", "Team Value"]],
        left_on="User",
        right_on="name",
        how="left"
    ).drop(columns=["name"], errors="ignore")

    budget_df["Budget"] = budget_df["Budget"] + budget_df["point_bonus"].fillna(0)
    budget_df.drop(columns=["point_bonus"], inplace=True, errors="ignore")

    # add total login bonus equally to everyone (100% estimation, if the user logged in every day)
    budget_df["Budget"] += total_login_bonus

    # Ensure consistent float format
    budget_df["Budget"] = budget_df["Budget"].astype(float)

    # add total achievement bonus based on anchor value and current ranking (estimation approach)
    for user in budget_df["User"]:
        achievement_bonus = calc_achievement_bonus_by_points(token, league_id, user, total_achievement_bonus)
        budget_df.loc[budget_df["User"] == user, "Budget"] += achievement_bonus

    # Sync with own actual budget
    try:
        own_budget = get_budget(token, league_id)
        own_username = get_username(token)
        mask = budget_df["User"] == own_username
        if not budget_df.loc[mask, "Budget"].eq(own_budget).all():
            budget_df.loc[mask, "Budget"] = own_budget
    except Exception as e:
        print(f"Warning: Could not sync own budget: {e}")

    # Kickbase buying power is cash plus the amount a manager may go into debt.
    budget_df["Max Negative"] = budget_df["Team Value"].fillna(0) * -0.33

    # Calculate available budget
    budget_df["Available Budget"] = budget_df["Budget"] - budget_df["Max Negative"].fillna(0)

    # Sort by available budget ascending
    budget_df.sort_values("Available Budget", ascending=False, inplace=True, ignore_index=True)
    budget_df.attrs["overpay_profiles"] = overpay_profiles
    budget_df.attrs["overpay_rows"] = overpay_rows
    budget_df.attrs["roster_profiles"] = roster_profiles
    budget_df.attrs["own_user"] = own_username if "own_username" in locals() else None

    return budget_df

def calc_average_overpay_by_manager(activities_df, league_start_date, managers=None):
    """Calculate average paid price above market value for current-season buys."""

    average_overpay, _, _ = calc_overpay_analysis_by_manager(activities_df, league_start_date, managers)
    return average_overpay

def calc_overpay_analysis_by_manager(activities_df, league_start_date, managers=None):
    """Calculate average overpay and context profiles for current-season buys."""

    overpay_rows = build_overpay_rows(activities_df, league_start_date, managers)
    if overpay_rows.empty:
        return {}, {}, overpay_rows

    average_overpay = overpay_rows.groupby("User")["Overpay"].mean().round(0).to_dict()
    return average_overpay, build_overpay_profiles(overpay_rows, managers), overpay_rows

def build_overpay_rows(activities_df, league_start_date, managers=None):
    """Return usable transfer rows with paid overpay and market-value context."""

    if activities_df.empty or not {"byr", "pi", "trp"}.issubset(activities_df.columns):
        print("Average overpay skipped: transfer activity fields are missing.")
        return pd.DataFrame()

    market_values = load_market_values_for_overpay()
    if market_values.empty:
        print("Warning: Could not calculate average overpay because no market values are available.")
        return pd.DataFrame()

    season_trades = activities_df.copy()
    season_trades = season_trades[season_trades["dt"].fillna("") >= league_start_date]
    season_trades = season_trades[season_trades["byr"].notna()]
    if season_trades.empty:
        print("Average overpay skipped: no current-season buys found in the activity feed.")
        return pd.DataFrame()

    manager_lookup = build_manager_lookup(managers)
    rows = []
    missing_player_id = 0
    missing_price = 0
    missing_market_value = 0
    for _, trade in season_trades.iterrows():
        buyer = normalize_activity_name(trade.get("byr"), manager_lookup)
        player_id = trade.get("pi")
        price = first_number(trade.get("trp"), trade.get("prc"))
        market_context = lookup_market_context(
            market_values,
            player_id,
            trade.get("dt"),
            trade.get("pn"),
        )
        # Prefer our historical market value for the activity timestamp. Kickbase activity
        # fields can reflect a later/current value and create impossible underpays.
        market_value = market_context.get("mv")
        if market_value is None:
            market_value = first_number(trade.get("mv"), trade.get("mvo"))
        if not buyer:
            continue
        if player_id is None:
            missing_player_id += 1
            continue
        if price is None:
            missing_price += 1
            continue
        if market_value is None:
            missing_market_value += 1
            continue
        rows.append({
            "Date": trade.get("dt"),
            "User": buyer,
            "Player": trade.get("pn"),
            "PlayerId": player_id,
            "Price": price,
            "MarketValue": market_value,
            "Overpay": price - market_value,
            "OverpayPct": ((price - market_value) / market_value) * 100 if market_value else 0,
            "MarketValueBucket": market_value_bucket(market_value),
            "Position": normalize_position(market_context.get("position")),
            "MomentumBucket": momentum_bucket(market_context.get("mv_change_1d")),
            "QualityBucket": quality_bucket(market_value, market_context.get("p")),
        })

    if not rows:
        print(
            "Average overpay skipped: no usable transfer rows. "
            f"Checked {len(season_trades)} buys, missing player id: {missing_player_id}, "
            f"missing price: {missing_price}, missing market value: {missing_market_value}."
        )
        return pd.DataFrame()

    overpay_df = pd.DataFrame(rows)
    print(f"Average overpay calculated from {len(overpay_df)} usable buys.")
    return overpay_df

def build_overpay_profiles(overpay_df, managers=None):
    if overpay_df.empty:
        return {}

    profiles = {}
    league_profile = summarize_overpay_profile(overpay_df)
    profiles["__league__"] = league_profile

    manager_names = [manager_name for manager_name, _ in managers or []]
    for manager_name in manager_names:
        manager_rows = overpay_df[overpay_df["User"] == manager_name]
        profiles[manager_name] = summarize_overpay_profile(manager_rows)

    for manager_name, manager_rows in overpay_df.groupby("User"):
        profiles.setdefault(manager_name, summarize_overpay_profile(manager_rows))

    print(f"Overpay profiles built for {max(len(profiles) - 1, 0)} managers.")
    return profiles

def summarize_overpay_profile(rows):
    if rows is None or rows.empty:
        return {
            "samples": 0,
            "avg_overpay": None,
            "avg_overpay_pct": None,
            "segments": {},
        }

    segments = {}
    for bucket, bucket_rows in rows.groupby("MarketValueBucket"):
        segments[bucket] = summarize_group(bucket_rows)

    position_bias = summarize_group_map(rows, "Position")
    momentum_bias = summarize_group_map(rows, "MomentumBucket")
    quality_bias = summarize_group_map(rows, "QualityBucket")
    avg_overpay = round(float(rows["Overpay"].mean()), 0)
    stdev_overpay = round(float(rows["Overpay"].std(ddof=0)), 0) if len(rows) > 1 else 0
    p75_overpay = round(float(rows["Overpay"].quantile(0.75)), 0)
    max_overpay = round(float(rows["Overpay"].max()), 0)

    return {
        "samples": int(len(rows)),
        "avg_overpay": avg_overpay,
        "avg_overpay_pct": round(float(rows["OverpayPct"].mean()), 2),
        "stdev_overpay": stdev_overpay,
        "p75_overpay": p75_overpay,
        "max_overpay": max_overpay,
        "aggression_score": aggression_score(avg_overpay, p75_overpay, max_overpay, stdev_overpay),
        "archetype": overpay_archetype(rows, avg_overpay, stdev_overpay, quality_bias, momentum_bias),
        "segments": segments,
        "position_bias": position_bias,
        "momentum_bias": momentum_bias,
        "quality_bias": quality_bias,
    }

def summarize_group(rows):
    return {
        "samples": int(len(rows)),
        "avg_overpay": round(float(rows["Overpay"].mean()), 0),
        "avg_overpay_pct": round(float(rows["OverpayPct"].mean()), 2),
    }

def summarize_group_map(rows, column):
    if column not in rows:
        return {}
    result = {}
    usable = rows.dropna(subset=[column])
    usable = usable[usable[column].astype(str).ne("")]
    for key, group_rows in usable.groupby(column):
        result[str(key)] = summarize_group(group_rows)
    return result

def aggression_score(avg_overpay, p75_overpay, max_overpay, stdev_overpay):
    score = 0
    score += min(max(avg_overpay, 0) / 25_000, 40)
    score += min(max(p75_overpay, 0) / 40_000, 25)
    score += min(max(max_overpay, 0) / 100_000, 20)
    score += min(max(stdev_overpay, 0) / 75_000, 15)
    return int(round(min(score, 100), 0))

def overpay_archetype(rows, avg_overpay, stdev_overpay, quality_bias, momentum_bias):
    if rows.empty:
        return "Keine Daten"
    if avg_overpay >= 900_000:
        base = "Aggressiver Überbieter"
    elif avg_overpay >= 350_000:
        base = "Aktiver Überbieter"
    elif avg_overpay >= 75_000:
        base = "Kontrollierter Bieter"
    else:
        base = "Marktwertnah"

    quality_note = ""
    if relative_group_avg(quality_bias, "elite") >= 1.25:
        quality_note = " · Big-Boy-Fokus"
    elif relative_group_avg(quality_bias, "top") >= 1.20:
        quality_note = " · Topspieler-Fokus"

    momentum_note = ""
    if relative_group_avg(momentum_bias, "rising") >= 1.20:
        momentum_note = " · Trendjäger"

    variance_note = " · hohe Varianz" if stdev_overpay >= max(avg_overpay, 1) * 1.25 and stdev_overpay >= 500_000 else ""
    return f"{base}{quality_note}{momentum_note}{variance_note}"

def relative_group_avg(group_map, key):
    values = [group.get("avg_overpay") for group in (group_map or {}).values() if group.get("avg_overpay") is not None]
    target = (group_map or {}).get(key, {}).get("avg_overpay")
    if not values or target is None:
        return 0
    baseline = sum(values) / len(values)
    if baseline <= 0:
        return 0
    return target / baseline

def market_value_bucket(market_value):
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

def normalize_position(value):
    if value is None or pd.isna(value):
        return ""
    labels = {1: "TW", 2: "ABW", 3: "MIT", 4: "ST", "1": "TW", "2": "ABW", "3": "MIT", "4": "ST"}
    return labels.get(value, labels.get(str(value), str(value)))

def momentum_bucket(mv_change):
    if mv_change is None or pd.isna(mv_change):
        return "unknown"
    mv_change = float(mv_change)
    if mv_change >= 50_000:
        return "rising"
    if mv_change <= -50_000:
        return "falling"
    return "flat"

def quality_bucket(market_value, points=None):
    points = 0 if points is None or pd.isna(points) else float(points)
    market_value = 0 if market_value is None or pd.isna(market_value) else float(market_value)
    if market_value >= 30_000_000 or points >= 160:
        return "elite"
    if market_value >= 15_000_000 or points >= 100:
        return "top"
    return "normal"

def extract_roster_profile(manager_info):
    players = find_player_list(manager_info)
    team_counts = {}
    for player in players:
        team_key = player_team_key(player)
        if team_key:
            team_counts[team_key] = team_counts.get(team_key, 0) + 1

    return {
        "squad_size": len(players),
        "team_counts": team_counts,
        "has_roster_data": bool(players),
    }

def find_player_list(value):
    candidates = []

    def walk(node):
        if isinstance(node, list):
            player_like = [item for item in node if is_player_like(item)]
            if player_like:
                candidates.append(player_like)
            for item in node:
                walk(item)
        elif isinstance(node, dict):
            for child in node.values():
                walk(child)

    walk(value)
    if not candidates:
        return []
    return max(candidates, key=len)

def is_player_like(value):
    if not isinstance(value, dict):
        return False
    keys = set(value.keys())
    has_player_id = bool(keys & {"i", "id", "pi", "playerId", "player_id"})
    has_player_name = bool(keys & {"n", "name", "fn", "first_name", "ln", "last_name"})
    has_team = bool(keys & {"tid", "teamId", "team_id", "tn", "teamName", "team_name"})
    return (has_player_id or has_player_name) and has_team

def player_team_key(player):
    team_value = (
        player.get("tid")
        or player.get("teamId")
        or player.get("team_id")
        or player.get("tn")
        or player.get("teamName")
        or player.get("team_name")
    )
    return normalize_team_key(team_value)

def normalize_team_key(value):
    if isinstance(value, dict):
        value = value.get("n") or value.get("name") or value.get("tn") or value.get("id") or value.get("i")
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    normalized = unicodedata.normalize("NFKD", str(value))
    normalized = "".join(char for char in normalized if not unicodedata.combining(char))
    normalized = normalized.lower().replace("ß", "ss")
    normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
    return " ".join(normalized.split())

def normalize_activity_name(value, manager_lookup=None):
    if isinstance(value, dict):
        value = value.get("n") or value.get("name") or value.get("u") or value.get("id") or value.get("i")
    if value is None or pd.isna(value):
        return None
    value = str(value)
    return (manager_lookup or {}).get(value, value)

def build_manager_lookup(managers=None):
    lookup = {}
    for manager_name, manager_id in managers or []:
        lookup[str(manager_name)] = str(manager_name)
        lookup[str(manager_id)] = str(manager_name)
    return lookup

def load_market_values_for_overpay():
    try:
        with sqlite3.connect("player_data_total.db") as conn:
            market_values = pd.read_sql_query(
                """
                SELECT player_id, date, mv
                     , first_name, last_name, position, p
                FROM player_data_1d
                WHERE mv IS NOT NULL
                """,
                conn,
                parse_dates=["date"],
            )
            market_values = market_values.sort_values(["player_id", "date"])
            market_values["mv_change_1d"] = market_values["mv"] - market_values.groupby("player_id")["mv"].shift(1)
            return market_values
    except Exception as e:
        print(f"Warning: Could not load market values for overpay calculation: {e}")
        return pd.DataFrame(columns=["player_id", "date", "mv", "first_name", "last_name", "position", "p", "mv_change_1d"])

def lookup_market_value(market_values, player_id, activity_date, player_name=None):
    context = lookup_market_context(market_values, player_id, activity_date, player_name)
    return context.get("mv")

def lookup_market_context(market_values, player_id, activity_date, player_name=None):
    market_value_date = market_value_date_for_activity(activity_date)
    if market_value_date is None:
        return {}

    player_values = pd.DataFrame()
    if player_id is not None:
        try:
            player_id = int(player_id)
            player_values = market_values[market_values["player_id"] == player_id].copy()
        except Exception:
            player_values = pd.DataFrame()

    if player_values.empty and player_name:
        normalized_name = normalize_player_name(player_name)
        if normalized_name:
            values_with_names = market_values.copy()
            values_with_names["normalized_name"] = values_with_names.apply(
                lambda row: normalize_player_name(f"{row.get('first_name', '')} {row.get('last_name', '')}"),
                axis=1,
            )
            values_with_names["normalized_last_name"] = values_with_names["last_name"].map(normalize_player_name)
            player_values = values_with_names[
                (values_with_names["normalized_name"] == normalized_name)
                | (values_with_names["normalized_last_name"] == normalized_name)
            ].copy()

    if player_values.empty:
        return {}

    player_values["date"] = pd.to_datetime(player_values["date"]).dt.normalize()
    target_date = pd.Timestamp(market_value_date).normalize()
    exact_values = player_values[player_values["date"] == target_date].sort_values("date")
    if not exact_values.empty:
        return market_context_from_row(exact_values.iloc[-1])

    values_until_trade = player_values[player_values["date"] < target_date].sort_values("date")
    if values_until_trade.empty:
        return {}
    return market_context_from_row(values_until_trade.iloc[-1])

def market_context_from_row(row):
    result = {}
    for key in ["mv", "position", "p", "mv_change_1d"]:
        value = row.get(key)
        if value is not None and not pd.isna(value):
            result[key] = float(value) if key in {"mv", "p", "mv_change_1d"} else value
    return result

def market_value_date_for_activity(activity_date):
    try:
        activity_time = pd.to_datetime(activity_date, utc=True).tz_convert("Europe/Berlin")
    except Exception:
        return None

    # Before the 22:00 market update, the active market value is still yesterday's value.
    if activity_time.hour < 22:
        activity_time = activity_time - timedelta(days=1)
    return activity_time.date()

def normalize_player_name(value):
    if value is None or pd.isna(value):
        return ""
    normalized = unicodedata.normalize("NFKD", str(value))
    normalized = "".join(char for char in normalized if not unicodedata.combining(char))
    normalized = normalized.lower().replace("ß", "ss")
    normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
    return " ".join(normalized.split())

def first_number(*values):
    for value in values:
        if isinstance(value, dict):
            value = value.get("v") or value.get("value") or value.get("amount") or value.get("price")
        if value is None:
            continue
        try:
            if pd.isna(value):
                continue
        except (TypeError, ValueError):
            continue
        try:
            return float(value)
        except (TypeError, ValueError):
            continue
    return None

def calc_achievement_bonus_by_points(token, league_id, username, anchor_achievement_bonus):
    """Estimate achievement bonus for a user based on their total points compared to anchor user."""

    ranking = get_league_ranking(token, league_id)
    ranking_df = pd.DataFrame(ranking, columns=["Name", "Total Points"])

    # Total number of users
    num_users = len(ranking_df)
    if num_users == 0:
        return 0

    # Get anchor user's name and points
    anchor_user = get_username(token)
    anchor_row = ranking_df[ranking_df["Name"] == anchor_user]
    if anchor_row.empty:
        return 0
    anchor_points = anchor_row["Total Points"].values[0]

    # If the user is the anchor, return exactly the anchor achievement bonus
    if username == anchor_user:
        return anchor_achievement_bonus

    # Get target user's points
    user_row = ranking_df[ranking_df["Name"] == username]
    if user_row.empty:
        return 0
    user_points = user_row["Total Points"].values[0]

    # Calculate bonus scaling based on points ratio
    if anchor_points == 0:
        scale = 1.0
    else:
        scale = user_points / anchor_points

    estimated_bonus = anchor_achievement_bonus * scale
    return estimated_bonus

def calc_achievement_bonus_by_rank(token, league_id, username, anchor_achievement_bonus):
    """Estimate achievement bonus for a user based on their ranking."""
    """Currently not used, kept for reference."""

    ranking = get_league_ranking(token, league_id)
    ranking_df = pd.DataFrame(ranking, columns=["Name", "Total Points"])

    # Total number of users
    num_users = len(ranking_df)
    if num_users == 0:
        return 0

    # Get anchor user's name and rank
    anchor_user = get_username(token)
    anchor_row = ranking_df[ranking_df["Name"] == anchor_user]
    if anchor_row.empty:
        return 0
    anchor_rank = anchor_row.index[0] + 1

    # If the user is the anchor, return exactly the anchor achievement bonus
    if username == anchor_user:
        return anchor_achievement_bonus

    # Get target user's rank and points
    user_row = ranking_df[ranking_df["Name"] == username]
    if user_row.empty:
        return 0
    user_rank = user_row.index[0] + 1

    # Calculate bonus scaling based on rank difference
    # If user is ranked lower (higher number): scale down
    # If user is ranked higher (lower number): scale up
    rank_diff = anchor_rank - user_rank
    scale = 1.0 + (rank_diff * 0.1)

    # Calculate estimated achievement bonus
    estimated_bonus = anchor_achievement_bonus * scale
    return estimated_bonus
