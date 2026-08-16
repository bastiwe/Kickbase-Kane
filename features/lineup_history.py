from datetime import datetime, timedelta, timezone
import os
import re
import unicodedata

import pandas as pd
import requests

BASE_URL = "https://api.bigballsdata.com/v1"

TEAM_ALIASES = {
    "bayern munich": "bayern munchen",
    "fc bayern munich": "bayern munchen",
    "fc bayern munchen": "bayern munchen",
    "bayer leverkusen": "bayer leverkusen",
    "borussia dortmund": "borussia dortmund",
    "dortmund": "borussia dortmund",
    "bvb": "borussia dortmund",
    "borussia monchengladbach": "borussia monchengladbach",
    "borussia moenchengladbach": "borussia monchengladbach",
    "monchengladbach": "borussia monchengladbach",
    "moenchengladbach": "borussia monchengladbach",
    "eintracht frankfurt": "eintracht frankfurt",
    "frankfurt": "eintracht frankfurt",
    "rb leipzig": "rb leipzig",
    "rasenballsport leipzig": "rb leipzig",
    "vfb stuttgart": "vfb stuttgart",
    "stuttgart": "vfb stuttgart",
    "sc freiburg": "sc freiburg",
    "freiburg": "sc freiburg",
    "werder bremen": "werder bremen",
    "sv werder bremen": "werder bremen",
    "union berlin": "union berlin",
    "1 fc union berlin": "union berlin",
    "fc union berlin": "union berlin",
    "mainz": "mainz 05",
    "mainz 05": "mainz 05",
    "1 fsv mainz 05": "mainz 05",
    "fsv mainz 05": "mainz 05",
    "augsburg": "fc augsburg",
    "fc augsburg": "fc augsburg",
    "hoffenheim": "tsg hoffenheim",
    "tsg hoffenheim": "tsg hoffenheim",
    "wolfsburg": "vfl wolfsburg",
    "vfl wolfsburg": "vfl wolfsburg",
    "heidenheim": "heidenheim",
    "1 fc heidenheim": "heidenheim",
    "fc heidenheim": "heidenheim",
    "st pauli": "st pauli",
    "fc st pauli": "st pauli",
    "hamburger sv": "hamburger sv",
    "hamburg": "hamburger sv",
    "koln": "koln",
    "cologne": "koln",
    "1 fc koln": "koln",
}


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
        entries = extract_lineup_entries(lineup_payload, match)
        per_match = {}

        for entry in entries:
            player_key = normalize_name(entry["name"])
            if not player_key:
                continue
            team_key = normalize_team_name(entry.get("team_name"))
            stat_key = (player_key, team_key)
            per_match.setdefault(stat_key, {"started": False, "team_name": entry.get("team_name")})
            per_match[stat_key]["started"] = per_match[stat_key]["started"] or entry["started"]

        for (player_key, team_key), stat in per_match.items():
            player_history = history.setdefault(player_key, {"total": {"starts": 0, "apps": 0}, "teams": {}})
            player_history["total"]["apps"] += 1
            if stat["started"]:
                player_history["total"]["starts"] += 1

            if team_key:
                team_history = player_history["teams"].setdefault(
                    team_key,
                    {"starts": 0, "apps": 0, "team_name": stat.get("team_name")},
                )
                team_history["apps"] += 1
                if stat["started"]:
                    team_history["starts"] += 1

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


def extract_lineup_entries(payload, match=None):
    data = payload.get("data", payload) if isinstance(payload, dict) else payload
    entries = []
    match = match or {}
    home_team = extract_team_name(match.get("home") or match.get("home_team"))
    away_team = extract_team_name(match.get("away") or match.get("away_team"))

    collect_lineup_entries(data, entries, home_team=home_team, away_team=away_team)
    return entries


def collect_lineup_entries(
    node,
    entries,
    current_team=None,
    home_team=None,
    away_team=None,
    in_starters=False,
    in_squad=False,
):
    if isinstance(node, dict):
        node_team = extract_team_name(node) or current_team
        local_home = extract_team_name(node.get("home") or node.get("home_team")) or home_team
        local_away = extract_team_name(node.get("away") or node.get("away_team")) or away_team

        name = extract_player_name(node)
        if name:
            team_name = extract_player_team_name(node) or node_team
            is_starter = in_starters or node.get("is_starter") is True or node.get("starter") is True
            if in_squad or is_starter:
                entries.append({"name": name, "team_name": team_name, "started": is_starter})

        for key, value in node.items():
            key_lower = str(key).lower()
            child_team = node_team
            if key_lower in {"home", "hometeam", "home_team", "homelineup", "home_lineup", "homebench", "home_bench"}:
                child_team = local_home or node_team
            elif key_lower in {"away", "awayteam", "away_team", "awaylineup", "away_lineup", "awaybench", "away_bench"}:
                child_team = local_away or node_team

            collect_lineup_entries(
                value,
                entries,
                current_team=child_team,
                home_team=local_home,
                away_team=local_away,
                in_starters=in_starters or key_lower in {
                    "starting_xi",
                    "startingxi",
                    "starters",
                    "lineup",
                    "homelineup",
                    "home_lineup",
                    "awaylineup",
                    "away_lineup",
                },
                in_squad=in_squad or key_lower in {
                    "players",
                    "squad",
                    "bench",
                    "substitutes",
                    "subs",
                    "homebench",
                    "home_bench",
                    "awaybench",
                    "away_bench",
                },
            )
    elif isinstance(node, list):
        for item in node:
            collect_lineup_entries(
                item,
                entries,
                current_team=current_team,
                home_team=home_team,
                away_team=away_team,
                in_starters=in_starters,
                in_squad=in_squad,
            )


def extract_player_name(node):
    return node.get("name") or node.get("player_name") or node.get("playerName")


def extract_team_name(node):
    if isinstance(node, str):
        return node
    if not isinstance(node, dict):
        return None
    value = (
        node.get("team_name")
        or node.get("teamName")
        or node.get("club_name")
        or node.get("clubName")
        or node.get("short_name")
        or node.get("shortName")
    )
    if value:
        return value
    for key in ("team", "club"):
        nested = node.get(key)
        if isinstance(nested, dict):
            nested_name = nested.get("name") or nested.get("display_name") or nested.get("displayName")
            if nested_name:
                return nested_name
    return None


def extract_player_team_name(node):
    for key in ("team", "club"):
        nested = node.get(key)
        if isinstance(nested, dict):
            nested_name = extract_team_name(nested) or nested.get("name")
            if nested_name:
                return nested_name
    return node.get("team_name") or node.get("teamName") or node.get("club_name") or node.get("clubName")


def add_history_columns(df, history):
    if df.empty or not {"first_name", "last_name"}.issubset(df.columns):
        return df

    result = df.copy()
    aliases = build_history_aliases(history)
    rows = result.apply(lambda row: resolve_player_history(row, history, aliases), axis=1)

    result["recent_starts"] = rows.map(lambda item: item["starts"])
    result["recent_apps"] = rows.map(lambda item: item["apps"])
    result["starter_rate"] = rows.map(lambda item: item["starter_rate"])
    result["lineup_scope"] = rows.map(lambda item: item["scope"])

    lineup_cols = ["starter_rate", "recent_starts", "recent_apps", "lineup_scope"]
    other_cols = [col for col in result.columns if col not in lineup_cols]
    if "expected_change_pct" in other_cols:
        insert_at = other_cols.index("expected_change_pct") + 1
        ordered_cols = other_cols[:insert_at] + lineup_cols + other_cols[insert_at:]
        return result[ordered_cols]

    return result


def resolve_player_history(row, history, aliases):
    player_key = resolve_player_key(row.get("first_name", ""), row.get("last_name", ""), history, aliases)
    player_history = history.get(player_key)
    if not player_history:
        return empty_history()

    team_key = normalize_team_name(row.get("team_name"))
    team_history = player_history.get("teams", {}).get(team_key) if team_key else None
    if team_history:
        return format_history(team_history, "Aktueller Verein")

    total_history = player_history.get("total")
    if total_history and total_history.get("apps"):
        return format_history(total_history, "Gesamt")

    return empty_history()


def format_history(history, scope):
    starts = history.get("starts")
    apps = history.get("apps")
    starter_rate = round((starts / apps) * 100, 0) if apps else None
    return {"starts": starts, "apps": apps, "starter_rate": starter_rate, "scope": scope}


def empty_history():
    return {"starts": None, "apps": None, "starter_rate": None, "scope": None}


def normalize_name(name):
    if not name:
        return ""
    normalized = unicodedata.normalize("NFKD", str(name))
    normalized = "".join(char for char in normalized if not unicodedata.combining(char))
    normalized = normalized.lower()
    normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
    return " ".join(normalized.split())


def normalize_team_name(name):
    key = normalize_name(name)
    key = re.sub(r"\b(fc|sc|sv|vfl|vfb|tsg|1)\b", " ", key)
    key = " ".join(key.split())
    return TEAM_ALIASES.get(key, TEAM_ALIASES.get(normalize_name(name), key))


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
