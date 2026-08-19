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
    for manager in managers:
        try:
            manager_name, manager_id = manager
            info = get_manager_info(token, league_id, manager_id)
            team_value = info.get("tv", 0)

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
    average_overpay = calc_average_overpay_by_manager(activities_df, league_start_date, managers)

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

    return budget_df

def calc_average_overpay_by_manager(activities_df, league_start_date, managers=None):
    """Calculate average paid price above market value for current-season buys."""

    if activities_df.empty or not {"byr", "pi", "trp"}.issubset(activities_df.columns):
        print("Average overpay skipped: transfer activity fields are missing.")
        return {}

    market_values = load_market_values_for_overpay()
    if market_values.empty:
        print("Warning: Could not calculate average overpay because no market values are available.")
        return {}

    season_trades = activities_df.copy()
    season_trades = season_trades[season_trades["dt"].fillna("") >= league_start_date]
    season_trades = season_trades[season_trades["byr"].notna()]
    if season_trades.empty:
        print("Average overpay skipped: no current-season buys found in the activity feed.")
        return {}

    manager_lookup = build_manager_lookup(managers)
    rows = []
    missing_player_id = 0
    missing_price = 0
    missing_market_value = 0
    for _, trade in season_trades.iterrows():
        buyer = normalize_activity_name(trade.get("byr"), manager_lookup)
        player_id = trade.get("pi")
        price = first_number(trade.get("trp"), trade.get("prc"))
        market_value = first_number(trade.get("mv"), trade.get("mvo"))
        if market_value is None:
            market_value = lookup_market_value(
                market_values,
                player_id,
                trade.get("dt"),
                trade.get("pn"),
            )
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
        rows.append({"User": buyer, "Overpay": price - market_value})

    if not rows:
        print(
            "Average overpay skipped: no usable transfer rows. "
            f"Checked {len(season_trades)} buys, missing player id: {missing_player_id}, "
            f"missing price: {missing_price}, missing market value: {missing_market_value}."
        )
        return {}

    overpay_df = pd.DataFrame(rows)
    print(f"Average overpay calculated from {len(overpay_df)} usable buys.")
    return overpay_df.groupby("User")["Overpay"].mean().round(0).to_dict()

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
            return pd.read_sql_query(
                """
                SELECT player_id, date, mv
                     , first_name, last_name
                FROM player_data_1d
                WHERE mv IS NOT NULL
                """,
                conn,
                parse_dates=["date"],
            )
    except Exception as e:
        print(f"Warning: Could not load market values for overpay calculation: {e}")
        return pd.DataFrame(columns=["player_id", "date", "mv", "first_name", "last_name"])

def lookup_market_value(market_values, player_id, activity_date, player_name=None):
    if not activity_date:
        return None

    try:
        activity_date = pd.to_datetime(activity_date, utc=True).tz_convert(None).normalize()
    except Exception:
        return None

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
        return None

    player_values["date"] = pd.to_datetime(player_values["date"]).dt.normalize()
    values_until_trade = player_values[player_values["date"] <= activity_date].sort_values("date")
    if not values_until_trade.empty:
        value = values_until_trade.iloc[-1]["mv"]
    else:
        value = player_values.sort_values("date").iloc[0]["mv"]
    return None if pd.isna(value) else float(value)

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
