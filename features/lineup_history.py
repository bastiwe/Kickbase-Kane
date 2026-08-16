from datetime import datetime, timedelta, timezone
import os
import re
import unicodedata

import pandas as pd
import requests

BASE_URL = "https://api.bigballsdata.com/v1"
LINEUP_COLUMNS = ["starter_rate", "recent_starts", "recent_apps", "lineup_scope"]

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
        return add_empty_history_columns(market_df, "Kein API-Key"), add_empty_history_columns(squad_df, "Kein API-Key")

    try:
        history = fetch_recent_starter_history(api_key)
    except Exception as e:
        print(f"\nWarning: Could not fetch Big Balls lineup history: {e}")
        return add_empty_history_columns(market_df, "API-Fehler"), add_empty_history_columns(squad_df, "API-Fehler")

    if not history:
        print("\nNo Big Balls lineup history found, skipping lineup history.")
        try:
            history = fetch_club_form_history_for_reports(api_key, [market_df, squad_df])
        except Exception as e:
            print(f"\nWarning: Could not fetch Big Balls club-form fallback: {e}")
            return add_empty_history_columns(market_df, "API-Fehler"), add_empty_history_columns(squad_df, "API-Fehler")

    if not history:
        print("\nNo Big Balls club-form fallback found, skipping lineup history.")
        return add_empty_history_columns(market_df, "Keine Daten"), add_empty_history_columns(squad_df, "Keine Daten")

    return add_history_columns(market_df, history), add_history_columns(squad_df, history)


def fetch_recent_starter_history(api_key):
    league = os.getenv("BIGBALLS_LEAGUE", "bundesliga")
    lookback_days = positive_int_env("BIGBALLS_LOOKBACK_DAYS", 430)
    match_limit = positive_int_env("BIGBALLS_MATCH_LIMIT", 80)
    now = datetime.now(timezone.utc)
    since = now - timedelta(days=lookback_days)

    matches = get_finished_matches(api_key, league, match_limit)
    if not matches:
        discovered_league = discover_league_key(api_key, league)
        if discovered_league and discovered_league != league:
            print(f"\nBig Balls: using discovered league key '{discovered_league}' instead of '{league}'.")
            matches = get_finished_matches(api_key, discovered_league, match_limit)

    history = {}
    lineup_match_count = 0
    lineup_payload_count = 0
    first_payload_keys = None

    for match in matches:
        kickoff = parse_datetime(match.get("kickoff_utc") or match.get("date") or match.get("start_time"))
        if kickoff and kickoff < since:
            continue
        if kickoff and kickoff > now:
            continue

        match_id = match.get("id")
        if not match_id:
            continue

        lineup_payload = get_lineups(api_key, match_id)
        if not lineup_payload:
            continue
        lineup_payload_count += 1
        if first_payload_keys is None:
            first_payload_keys = summarize_payload_keys(lineup_payload)
        entries = extract_lineup_entries(lineup_payload, match)
        if entries:
            lineup_match_count += 1
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

    print(
        f"\nBig Balls lineup history: {len(matches)} matches checked, "
        f"{lineup_payload_count} with lineup payloads, "
        f"{lineup_match_count} with lineup entries, {len(history)} players matched by name."
    )
    if first_payload_keys:
        print(f"Big Balls first lineup payload keys: {first_payload_keys}")
    return history


def get_finished_matches(api_key, league, limit):
    matches = get_last_season_stored_matches(api_key, league, limit)
    if matches:
        return matches

    matches = get_stored_finished_matches(api_key, league, limit)
    if matches:
        return matches

    matches = get_sdk_style_matches(api_key, league, limit)
    if matches:
        return matches

    return []


def get_last_season_stored_matches(api_key, league, limit):
    matches = []
    for season in get_history_seasons():
        remaining = limit - len(matches)
        if remaining <= 0:
            break
        matches.extend(get_stored_finished_matches(api_key, league, remaining, season=season))
    return matches[:limit]


def get_history_seasons():
    configured = os.getenv("BIGBALLS_HISTORY_SEASONS")
    if configured:
        return [int(value.strip()) for value in configured.split(",") if value.strip().isdigit()]

    today = datetime.now(timezone.utc)
    season_start_year = today.year - 1 if today.month >= 7 else today.year - 2
    return [season_start_year + 1, season_start_year]


def get_sdk_style_matches(api_key, league, limit):
    """Mirror Big Balls SDK client.matches.list({ sport, league, limit })."""

    params = {
        "sport": "football",
        "league": league,
        "limit": min(limit, 200),
    }
    data = request_json(api_key, "/matches", params=params)
    return data.get("data", []) if isinstance(data, dict) else []


def get_stored_finished_matches(api_key, league, limit, season=None):
    params = {
        "sport": "football",
        "league": league,
        "status": "finished",
        "limit": min(limit, 200),
        "sort": "desc",
    }
    if season:
        params["season"] = season
    data = request_json(api_key, "/stored/matches", params=params)
    return data.get("data", []) if isinstance(data, dict) else []


def discover_league_key(api_key, preferred_league):
    data = request_json(api_key, "/leagues", params={"sport": "football"})
    leagues = data.get("data", []) if isinstance(data, dict) else []
    preferred = normalize_name(preferred_league)

    candidates = []
    for league in leagues:
        if not isinstance(league, dict):
            continue
        values = [
            league.get("key"),
            league.get("slug"),
            league.get("id"),
            league.get("name"),
            league.get("display_name"),
            league.get("displayName"),
        ]
        text = " ".join(normalize_name(value) for value in values if value)
        if preferred and preferred in text:
            return league.get("key") or league.get("slug") or league.get("id")
        if "bundesliga" in text and "2 bundesliga" not in text:
            candidates.append(league.get("key") or league.get("slug") or league.get("id"))

    return next((candidate for candidate in candidates if candidate), None)


def get_lineups(api_key, match_id):
    try:
        return request_json(api_key, f"/stored/matches/{match_id}/lineups")
    except requests.HTTPError as e:
        status_code = e.response.status_code if e.response is not None else None
        if status_code not in {404, 422}:
            raise

    try:
        return request_json(api_key, f"/matches/{match_id}", params={"fields": "lineups"})
    except requests.HTTPError as e:
        status_code = e.response.status_code if e.response is not None else None
        if status_code in {404, 422}:
            return None
        raise


def fetch_club_form_history_for_reports(api_key, dataframes):
    players = collect_report_players(dataframes)
    limit = positive_int_env("BIGBALLS_PLAYER_FORM_LIMIT", 40)
    history = {}
    searched_count = 0
    form_count = 0

    for player in players[:limit]:
        searched_count += 1
        try:
            candidates = search_players(api_key, player["full_name"])
        except requests.HTTPError as e:
            if e.response is not None and e.response.status_code == 429:
                print("Big Balls club-form fallback stopped early because of rate limiting.")
                break
            raise
        candidate = select_player_candidate(candidates, player)
        if not candidate:
            continue

        try:
            form = get_player_club_form(api_key, candidate.get("id"))
        except requests.HTTPError as e:
            if e.response is not None and e.response.status_code == 429:
                print("Big Balls club-form fallback stopped early because of rate limiting.")
                break
            raise
        stats = extract_club_form_stats(form)
        if not stats:
            continue

        form_count += 1
        player_key = normalize_name(player["full_name"])
        team_key = normalize_team_name(player.get("team_name"))
        player_history = {
            "total": stats,
            "teams": {},
        }
        if team_key:
            player_history["teams"][team_key] = stats
        history[player_key] = player_history

    print(
        f"Big Balls club-form fallback: {searched_count} report players checked, "
        f"{form_count} with usable form stats."
    )
    return history


def collect_report_players(dataframes):
    players = []
    seen = set()
    for df in dataframes:
        if df.empty or not {"first_name", "last_name"}.issubset(df.columns):
            continue
        for _, row in df.iterrows():
            full_name = f"{row.get('first_name', '')} {row.get('last_name', '')}".strip()
            key = normalize_name(full_name)
            if not key or key in seen:
                continue
            seen.add(key)
            players.append({"full_name": full_name, "team_name": row.get("team_name")})
    return players


def search_players(api_key, name):
    data = request_json(api_key, "/players", params={"name": name, "sport": "football"})
    return data.get("data", []) if isinstance(data, dict) else []


def select_player_candidate(candidates, player):
    target_name = normalize_name(player["full_name"])
    target_last_name = normalize_name(player["full_name"]).split()[-1]
    target_team = normalize_team_name(player.get("team_name"))

    fallback = None
    for candidate in candidates:
        if not isinstance(candidate, dict):
            continue
        candidate_name = normalize_name(extract_player_name(candidate))
        candidate_team = normalize_team_name(extract_player_team_name(candidate))
        if candidate_name == target_name and (not target_team or not candidate_team or candidate_team == target_team):
            return candidate
        if candidate_name.split()[-1:] == [target_last_name] and fallback is None:
            fallback = candidate

    return fallback


def get_player_club_form(api_key, player_id):
    if not player_id:
        return None
    try:
        return request_json(api_key, f"/players/{player_id}/club-form", params={"sport": "football"})
    except requests.HTTPError as e:
        status_code = e.response.status_code if e.response is not None else None
        if status_code in {404, 422}:
            return None
        raise


def extract_club_form_stats(payload):
    if not payload:
        return None

    data = payload.get("data", payload) if isinstance(payload, dict) else payload

    best = None
    for node in walk_nodes(data):
        if not isinstance(node, dict):
            continue
        apps = first_number(node, ["appearances", "apps", "matches", "games", "played"])
        starts = first_number(node, ["starts", "started", "starting_appearances", "lineups"])
        minutes = first_number(node, ["minutes", "mins", "minutes_played", "playing_time"])
        if not apps:
            continue
        if starts is None and minutes is not None:
            starts = min(apps, round(minutes / 90))
        if starts is None:
            continue
        starter_rate = round((starts / apps) * 100, 0) if apps else None
        best = {"starts": starts, "apps": apps, "starter_rate": starter_rate, "scope": "Club-Form"}
        break

    return best


def walk_nodes(node):
    yield node
    if isinstance(node, dict):
        for value in node.values():
            yield from walk_nodes(value)
    elif isinstance(node, list):
        for item in node:
            yield from walk_nodes(item)


def first_number(node, keys):
    for key in keys:
        value = node.get(key)
        if isinstance(value, dict):
            value = value.get("value")
        if isinstance(value, (int, float)):
            return value
        if isinstance(value, str):
            try:
                return float(value)
            except ValueError:
                continue
    return None


def request_json(api_key, path, params=None):
    response = requests.get(
        f"{BASE_URL}{path}",
        headers={"Authorization": f"Bearer {api_key}", "x-api-key": api_key},
        params=params,
        timeout=20,
    )
    response.raise_for_status()
    return response.json()


def extract_lineup_entries(payload, match=None):
    data = payload.get("data", payload) if isinstance(payload, dict) else payload
    if isinstance(data, dict) and "lineups" in data:
        data = unwrap_field_result(data["lineups"])
    entries = []
    match = match or {}
    home_team = extract_team_name(match.get("home") or match.get("home_team"))
    away_team = extract_team_name(match.get("away") or match.get("away_team"))

    collect_lineup_entries(data, entries, home_team=home_team, away_team=away_team)
    return entries


def summarize_payload_keys(payload):
    data = payload.get("data", payload) if isinstance(payload, dict) else payload
    if isinstance(data, dict):
        keys = list(data.keys())[:12]
        if "lineups" in data and isinstance(data["lineups"], dict):
            keys.append(f"lineups:{list(data['lineups'].keys())[:12]}")
        for side in ("home", "away"):
            if side in data:
                keys.append(f"{side}:{summarize_node(data[side])}")
        return keys
    if isinstance(data, list):
        return [f"list[{len(data)}]"]
    return [type(data).__name__]


def summarize_node(node):
    node = unwrap_field_result(node)
    if isinstance(node, dict):
        return list(node.keys())[:12]
    if isinstance(node, list):
        first_type = type(node[0]).__name__ if node else "empty"
        if node and isinstance(node[0], dict):
            return f"list[{len(node)}]:{list(node[0].keys())[:12]}"
        return f"list[{len(node)}]:{first_type}"
    return type(node).__name__


def unwrap_field_result(value):
    if isinstance(value, dict) and "value" in value:
        return value["value"]
    return value


def collect_lineup_entries(
    node,
    entries,
    current_team=None,
    home_team=None,
    away_team=None,
    in_starters=False,
    in_squad=False,
):
    node = unwrap_field_result(node)

    if isinstance(node, dict):
        node_team = extract_team_name(node) or current_team
        local_home = extract_team_name(node.get("home") or node.get("home_team")) or home_team
        local_away = extract_team_name(node.get("away") or node.get("away_team")) or away_team

        name = extract_player_name(node)
        if name:
            team_name = extract_player_team_name(node) or node_team
            is_starter = (
                in_starters
                or node.get("is_starter") is True
                or node.get("isStarting") is True
                or node.get("starter") is True
                or str(node.get("role", "")).lower() in {"starter", "starting", "starting_xi"}
            )
            if in_squad or is_starter:
                entries.append({"name": name, "team_name": team_name, "started": is_starter})

        for key, value in node.items():
            key_lower = str(key).lower()
            if name and key_lower in {"player", "athlete"}:
                continue
            child_team = node_team
            is_home_lineup = key_lower in {"home", "hometeam", "home_team", "homelineup", "home_lineup"}
            is_away_lineup = key_lower in {"away", "awayteam", "away_team", "awaylineup", "away_lineup"}
            is_top_level_lineup_side = key_lower in {"home", "away"}
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
                in_starters=in_starters or is_top_level_lineup_side or key_lower in {
                    "starting_xi",
                    "startingxi",
                    "starters",
                    "lineup",
                    "lineups",
                    "homelineup",
                    "home_lineup",
                    "awaylineup",
                    "away_lineup",
                },
                in_squad=in_squad or is_top_level_lineup_side or is_home_lineup or is_away_lineup or key_lower in {
                    "players",
                    "squad",
                    "bench",
                    "substitutes",
                    "substitute",
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
    elif isinstance(node, str) and (in_squad or in_starters):
        name = node.strip()
        if name:
            entries.append({"name": name, "team_name": current_team, "started": in_starters})


def looks_like_lineup_side(value):
    if isinstance(value, list):
        return True
    if not isinstance(value, dict):
        return False
    lineup_keys = {
        "players",
        "squad",
        "lineup",
        "lineups",
        "starting_xi",
        "startingxi",
        "starters",
        "bench",
        "substitutes",
        "subs",
    }
    return any(str(key).lower() in lineup_keys for key in value)


def extract_player_name(node):
    direct_name = node.get("name") or node.get("player_name") or node.get("playerName") or node.get("full_name") or node.get("fullName")
    if direct_name:
        return direct_name

    first_name = node.get("first_name") or node.get("firstName") or node.get("given_name") or node.get("givenName")
    last_name = node.get("last_name") or node.get("lastName") or node.get("family_name") or node.get("familyName")
    if first_name or last_name:
        return f"{first_name or ''} {last_name or ''}".strip()

    for key in ("player", "athlete"):
        nested = node.get(key)
        if isinstance(nested, dict):
            nested_name = extract_player_name(nested)
            if nested_name:
                return nested_name
    return None


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

    return order_lineup_columns(result)


def add_empty_history_columns(df, scope):
    if df.empty:
        return df

    result = df.copy()
    result["starter_rate"] = None
    result["recent_starts"] = None
    result["recent_apps"] = None
    result["lineup_scope"] = scope
    return order_lineup_columns(result)


def order_lineup_columns(result):
    other_cols = [col for col in result.columns if col not in LINEUP_COLUMNS]
    if "expected_change_pct" in other_cols:
        insert_at = other_cols.index("expected_change_pct") + 1
        ordered_cols = other_cols[:insert_at] + LINEUP_COLUMNS + other_cols[insert_at:]
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
    return {"starts": starts, "apps": apps, "starter_rate": starter_rate, "scope": history.get("scope", scope)}


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
