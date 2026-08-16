from datetime import datetime, timedelta, timezone
import os
import re
import unicodedata

import pandas as pd
import requests

BASE_URL = "https://api.bigballsdata.com/v1"


def enrich_reports_with_bigballs_lineups(market_df, squad_df):
    """Add historical starter rates from Big Balls Sports Data when configured."""

    api_key = os.getenv("BIGBALLS_API_KEY") or os.getenv("BBS_API_KEY")
    if not api_key:
        print("\nNo BIGBALLS_API_KEY or BBS_API_KEY provided, skipping lineup history.")
        return market_df, squad_df

    try:
        history = fetch_recent_starter_history(api_key)
    except Exception as e:
        print(f"\nWarning: Could not fetch Big Balls lineup history: {e}")
        return market_df, squad_df

    if not history:
        print("\nNo Big Balls lineup history found, skipping lineup history.")
        return market_df, squad_df

    return add_history_columns(market_df, history), add_history_columns(squad_df, history)


def fetch_recent_starter_history(api_key):
    league = os.getenv("BIGBALLS_LEAGUE", "bundesliga")
    lookback_days = positive_int_env("BIGBALLS_LOOKBACK_DAYS", 120)
    match_limit = positive_int_env("BIGBALLS_MATCH_LIMIT", 80)
    since = datetime.now(timezone.utc) - timedelta(days=lookback_days)

    matches = get_finished_matches(api_key, league, match_limit)
    history = {}

    for match in matches:
        kickoff = parse_datetime(match.get("kickoff_utc") or match.get("date") or match.get("start_time"))
        if kickoff and kickoff < since:
            continue

        match_id = match.get("id")
        if not match_id:
            continue

        lineup_payload = get_lineups(api_key, match_id)
        starters, squad_players = extract_lineup_names(lineup_payload)
        squad_keys = {normalize_name(player) for player in squad_players}

        for name in squad_players:
            key = normalize_name(name)
            if not key:
                continue
            history.setdefault(key, {"starts": 0, "apps": 0})
            history[key]["apps"] += 1

        for name in starters:
            key = normalize_name(name)
            if not key:
                continue
            history.setdefault(key, {"starts": 0, "apps": 0})
            history[key]["starts"] += 1
            if key not in squad_keys:
                history[key]["apps"] += 1

    return history


def get_finished_matches(api_key, league, limit):
    params = {
        "sport": "football",
        "league": league,
        "status": "finished",
        "limit": min(limit, 200),
    }
    data = request_json(api_key, "/stored/matches", params=params)
    return data.get("data", []) if isinstance(data, dict) else []


def get_lineups(api_key, match_id):
    return request_json(api_key, f"/stored/matches/{match_id}/lineups")


def request_json(api_key, path, params=None):
    response = requests.get(
        f"{BASE_URL}{path}",
        headers={"Authorization": f"Bearer {api_key}"},
        params=params,
        timeout=20,
    )
    response.raise_for_status()
    return response.json()


def extract_lineup_names(payload):
    data = payload.get("data", payload) if isinstance(payload, dict) else payload
    starters = set()
    squad_players = set()

    collect_named_players(data, starters, squad_players)
    return starters, squad_players


def collect_named_players(node, starters, squad_players, in_starters=False, in_squad=False):
    if isinstance(node, dict):
        current_in_starters = in_starters or any(
            key in node for key in ("starting_xi", "startingXI", "starters", "homeLineup", "awayLineup")
        )
        current_in_squad = in_squad or current_in_starters or any(
            key in node for key in ("bench", "substitutes", "subs", "homeBench", "awayBench")
        )

        name = node.get("name") or node.get("player_name") or node.get("playerName")
        is_starter = current_in_starters or node.get("is_starter") is True or node.get("starter") is True
        if name:
            if current_in_squad or is_starter:
                squad_players.add(name)
            if is_starter:
                starters.add(name)

        for key, value in node.items():
            key_lower = str(key).lower()
            collect_named_players(
                value,
                starters,
                squad_players,
                in_starters=current_in_starters or key_lower in {"starting_xi", "startingxi", "starters", "homelineup", "awaylineup"},
                in_squad=current_in_squad or key_lower in {"bench", "substitutes", "subs", "homebench", "awaybench"},
            )
    elif isinstance(node, list):
        for item in node:
            collect_named_players(item, starters, squad_players, in_starters=in_starters, in_squad=in_squad)


def add_history_columns(df, history):
    if df.empty or not {"first_name", "last_name"}.issubset(df.columns):
        return df

    result = df.copy()
    aliases = build_history_aliases(history)
    keys = result.apply(
        lambda row: resolve_player_key(row.get("first_name", ""), row.get("last_name", ""), history, aliases),
        axis=1,
    )
    result["recent_starts"] = keys.map(lambda key: history.get(key, {}).get("starts") if key else None)
    result["recent_apps"] = keys.map(lambda key: history.get(key, {}).get("apps") if key else None)
    result["starter_rate"] = result.apply(
        lambda row: round((row["recent_starts"] / row["recent_apps"]) * 100, 0)
        if pd.notna(row["recent_starts"]) and pd.notna(row["recent_apps"]) and row["recent_apps"] > 0
        else None,
        axis=1,
    )

    lineup_cols = ["starter_rate", "recent_starts", "recent_apps"]
    other_cols = [col for col in result.columns if col not in lineup_cols]
    if "expected_change_pct" in other_cols:
        insert_at = other_cols.index("expected_change_pct") + 1
        ordered_cols = other_cols[:insert_at] + lineup_cols + other_cols[insert_at:]
        return result[ordered_cols]

    return result


def normalize_name(name):
    if not name:
        return ""
    normalized = unicodedata.normalize("NFKD", str(name))
    normalized = "".join(char for char in normalized if not unicodedata.combining(char))
    normalized = normalized.lower()
    normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
    return " ".join(normalized.split())


def resolve_player_key(first_name, last_name, history, aliases):
    full_key = normalize_name(f"{first_name or ''} {last_name or ''}")
    if full_key in history:
        return full_key
    last_key = normalize_name(last_name)
    if last_key in aliases:
        return aliases[last_key]
    return full_key


def build_history_aliases(history):
    by_last_name = {}
    duplicates = set()
    for key in history:
        parts = key.split()
        if not parts:
            continue
        last_name = parts[-1]
        if last_name in by_last_name and by_last_name[last_name] != key:
            duplicates.add(last_name)
        else:
            by_last_name[last_name] = key
    return {last_name: key for last_name, key in by_last_name.items() if last_name not in duplicates}


def positive_int_env(name, default):
    try:
        value = int(os.getenv(name, str(default)))
    except ValueError:
        return default
    return value if value > 0 else default


def parse_datetime(value):
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
