from html.parser import HTMLParser
import os
import re
import time
import unicodedata
from urllib.parse import urljoin

import pandas as pd
import requests

BASE_URL = "https://www.ligainsider.de"
DEFAULT_SEASON = "2026-2027"
SIGNAL_COLUMNS = ["starter_rate", "lineup_scope", "li_status", "ligainsider_url"]

TEAM_ALIASES = {
    "bayern": "bayern munchen",
    "bayern munich": "bayern munchen",
    "fc bayern": "bayern munchen",
    "fc bayern munchen": "bayern munchen",
    "dortmund": "borussia dortmund",
    "bvb": "borussia dortmund",
    "frankfurt": "eintracht frankfurt",
    "leipzig": "rb leipzig",
    "leverkusen": "bayer leverkusen",
    "mainz": "mainz 05",
    "koln": "koln",
    "cologne": "koln",
    "gladbach": "borussia monchengladbach",
    "monchengladbach": "borussia monchengladbach",
    "moenchengladbach": "borussia monchengladbach",
    "union": "union berlin",
    "union berlin": "union berlin",
    "stuttgart": "vfb stuttgart",
    "freiburg": "sc freiburg",
    "hoffenheim": "tsg hoffenheim",
    "wolfsburg": "vfl wolfsburg",
    "augsburg": "fc augsburg",
    "bremen": "werder bremen",
    "werder": "werder bremen",
    "heidenheim": "heidenheim",
    "st pauli": "st pauli",
    "hamburg": "hamburger sv",
    "hamburger sv": "hamburger sv",
    "elversberg": "sv elversberg",
    "paderborn": "sc paderborn",
    "schalke": "schalke 04",
    "schalke 04": "schalke 04",
}


class LinkTextParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.links = []
        self.text_parts = []
        self._href_stack = []
        self._link_text = []

    def handle_starttag(self, tag, attrs):
        if tag != "a":
            return
        attrs = dict(attrs)
        href = attrs.get("href")
        self._href_stack.append(href)
        self._link_text.append([])

    def handle_endtag(self, tag):
        if tag != "a" or not self._href_stack:
            return
        href = self._href_stack.pop()
        text = clean_text(" ".join(self._link_text.pop()))
        if href and text:
            self.links.append((href, text))

    def handle_data(self, data):
        text = clean_text(data)
        if text:
            self.text_parts.append(text)
        if self._link_text:
            self._link_text[-1].append(data)


def enrich_reports_with_ligainsider_signals(market_df, squad_df):
    """Add public LigaInsider lineup signals to market and squad reports."""

    if os.getenv("LIGAINSIDER_ENABLED", "true").lower() in {"0", "false", "no"}:
        return add_empty_signal_columns(market_df, "Deaktiviert"), add_empty_signal_columns(squad_df, "Deaktiviert")

    try:
        signals = fetch_ligainsider_signals([market_df, squad_df])
    except Exception as e:
        print(f"\nWarning: Could not fetch LigaInsider signals: {e}")
        return add_empty_signal_columns(market_df, "LI-Fehler"), add_empty_signal_columns(squad_df, "LI-Fehler")

    if not signals:
        print("\nNo LigaInsider signals found.")
        return add_empty_signal_columns(market_df, "Keine LI-Daten"), add_empty_signal_columns(squad_df, "Keine LI-Daten")

    return add_signal_columns(market_df, signals), add_signal_columns(squad_df, signals)


def fetch_ligainsider_signals(dataframes):
    season = os.getenv("LIGAINSIDER_SEASON", DEFAULT_SEASON)
    players_by_team = collect_report_players_by_team(dataframes)
    if not players_by_team:
        return {}

    team_urls = discover_team_urls(season)
    signals = {}
    fetched = 0
    matched = 0
    starters = 0
    player_pages_checked = 0
    player_rates_found = 0

    for team_key, players in players_by_team.items():
        url = team_urls.get(team_key)
        if not url:
            continue

        parser = parse_page(url)
        fetched += 1
        page_signal = extract_page_signals(parser)
        for player in players:
            player_page_url = resolve_player_url(player, page_signal)
            player_rate = None
            if player_page_url:
                player_pages_checked += 1
                player_rate = fetch_player_starter_rate(player_page_url)
                if player_rate is not None:
                    player_rates_found += 1

            signal = resolve_player_signal(player, page_signal, player_rate, player_page_url)
            if signal:
                matched += 1
                if signal["li_status"] == "Startelf":
                    starters += 1
                signals[player["key"]] = signal
        time.sleep(float(os.getenv("LIGAINSIDER_REQUEST_DELAY", "0.4")))

    print(
        f"\nLigaInsider signals: {fetched} team pages checked, "
        f"{matched} report players matched, {starters} projected starters, "
        f"{player_rates_found}/{player_pages_checked} player Bundesliga starter rates found."
    )
    return signals


def discover_team_urls(season):
    urls = fallback_team_urls(season)

    for overview_url in (
        f"{BASE_URL}/bundesliga/spieltage/saison-{season}/",
        f"{BASE_URL}/bundesliga/transfers/",
    ):
        try:
            parser = parse_page(overview_url)
        except requests.RequestException as e:
            status = getattr(getattr(e, "response", None), "status_code", "request failed")
            print(f"LigaInsider overview skipped: {overview_url} returned {status}.")
            continue

        for href, text in parser.links:
            if "/bundesliga/team/" not in href:
                continue
            if f"/saison-{season}/" not in href:
                continue
            url = urljoin(BASE_URL, href)
            candidates = {normalize_team_name(text), normalize_team_name(team_slug_from_url(url))}
            for candidate in candidates:
                if candidate:
                    urls[candidate] = url
    return urls


def fallback_team_urls(season):
    teams = {
        "fc-augsburg": 21,
        "bayer-04-leverkusen": 23,
        "fc-bayern-muenchen": 1,
        "borussia-dortmund": 14,
        "eintracht-frankfurt": 12,
        "sc-freiburg": 7,
        "hamburger-sv": 34,
        "tsg-hoffenheim": 10,
        "1-fc-koeln": 15,
        "rb-leipzig": 131,
        "1-fc-mainz-05": 18,
        "borussia-moenchengladbach": 5,
        "sc-paderborn-07": 29,
        "fc-schalke-04": 6,
        "fc-st-pauli": 32,
        "vfb-stuttgart": 16,
        "1-fc-union-berlin": 124,
        "sv-werder-bremen": 19,
        "sv-elversberg": 466,
    }
    return {
        normalize_team_name(slug): f"{BASE_URL}/bundesliga/team/{slug}/{team_id}/saison-{season}/"
        for slug, team_id in teams.items()
    }


def parse_page(url):
    response = requests.get(
        url,
        headers={"User-Agent": "Kickbase-Kane/1.0 (+https://github.com/bastiwe/Kickbase-Kane)"},
        timeout=20,
    )
    response.raise_for_status()
    parser = LinkTextParser()
    parser.feed(response.text)
    return parser


def extract_page_signals(parser):
    text = "\n".join(parser.text_parts)
    prediction_text = extract_prediction_section(text)
    normalized_prediction_text = normalize_name(prediction_text)

    predicted = set()
    known = set()
    player_urls = {}
    unavailable = set()

    for href, link_text in parser.links:
        if is_probable_player_name(link_text):
            aliases = player_name_aliases(link_text)
            known.update(aliases)
            player_url = ligainsider_player_url(href)
            if player_url:
                for alias in aliases:
                    player_urls.setdefault(alias, player_url)
            if any(contains_name_alias(normalized_prediction_text, alias) for alias in aliases):
                predicted.update(aliases)

    lowered = normalize_name(text)
    for status_word in ("verletzt", "gesperrt", "aufbautraining", "krank"):
        if status_word in lowered:
            unavailable.add(status_word)

    return {
        "predicted": predicted,
        "known": known,
        "player_urls": player_urls,
        "unavailable_markers": unavailable,
    }


def extract_prediction_section(text):
    start = find_marker(text, ["VORAUSSICHTLICHE AUFSTELLUNG", "TOPELF"])
    if start < 0:
        return before_marker(text, ["AKTUELLE THEMEN", "DEIN TIPP:", "ERGEBNISSE", "## KADER", "\nKADER "])

    section = text[start:]
    return before_marker(section, ["AKTUELLE THEMEN", "DEIN TIPP:", "ERGEBNISSE", "## KADER", "\nKADER "])


def player_name_aliases(name):
    normalized = normalize_name(name)
    aliases = {normalized} if normalized else set()
    parts = normalized.split()
    if len(parts) >= 2:
        for index in range(1, len(parts)):
            aliases.add(" ".join(parts[index:]))
    return aliases


def contains_name_alias(text, alias):
    if not alias:
        return False
    return re.search(rf"(^| ){re.escape(alias)}($| )", text) is not None


def ligainsider_player_url(href):
    if not href:
        return None
    if "/bundesliga/team/" in href:
        return None
    if not re.search(r"_\d+/?$", href):
        return None
    return urljoin(BASE_URL, href)


def resolve_player_url(player, page_signal):
    for candidate in player["aliases"]:
        url = page_signal.get("player_urls", {}).get(candidate)
        if url:
            return url
    return None


def fetch_player_starter_rate(url):
    try:
        parser = parse_page(url)
    except requests.RequestException:
        return None
    time.sleep(float(os.getenv("LIGAINSIDER_REQUEST_DELAY", "0.4")))
    return parse_bundesliga_starter_rate("\n".join(parser.text_parts))


def parse_bundesliga_starter_rate(text):
    section = after_marker(text, ["EINSATZQUOTE"])
    if not section:
        return None

    section = before_marker(section, ["LIGA-RANKING", "DATEN POWERED", "NEWS"])
    upper_section = section.upper()
    match = re.search(r"STARTELF\s*:?\s*(?:\n|\r|\s)*([0-9]+(?:[,.][0-9]+)?)\s*%", upper_section)
    if not match:
        return None

    return float(match.group(1).replace(",", "."))


def resolve_player_signal(player, page_signal, player_rate=None, player_url=None):
    candidates = player["aliases"]
    if player_rate is not None:
        return {
            "starter_rate": player_rate,
            "lineup_scope": "LI-Spielerseite",
            "li_status": "Startelfquote",
            "ligainsider_url": player_url,
        }
    if any(candidate in page_signal["predicted"] for candidate in candidates):
        return {
            "starter_rate": None,
            "lineup_scope": "LI-Startelf",
            "li_status": "Startelf",
            "ligainsider_url": player_url,
        }
    if any(candidate in page_signal["known"] for candidate in candidates):
        return {
            "starter_rate": None,
            "lineup_scope": "LI-Kader",
            "li_status": "Kader",
            "ligainsider_url": player_url,
        }
    return {
        "starter_rate": None,
        "lineup_scope": "Nicht gefunden",
        "li_status": "Kein Treffer",
        "ligainsider_url": player_url,
    }


def collect_report_players_by_team(dataframes):
    result = {}
    seen = set()
    for df in dataframes:
        if df.empty or not {"first_name", "last_name", "team_name"}.issubset(df.columns):
            continue
        for _, row in df.iterrows():
            full_name = f"{row.get('first_name', '')} {row.get('last_name', '')}".strip()
            player_key = normalize_name(full_name)
            team_key = normalize_team_name(row.get("team_name"))
            if not player_key or not team_key or player_key in seen:
                continue
            seen.add(player_key)
            aliases = {player_key, normalize_name(row.get("last_name"))}
            result.setdefault(team_key, []).append({"key": player_key, "aliases": aliases})
    return result


def add_signal_columns(df, signals):
    if df.empty or not {"first_name", "last_name"}.issubset(df.columns):
        return df

    result = df.copy()
    keys = result.apply(lambda row: normalize_name(f"{row.get('first_name', '')} {row.get('last_name', '')}"), axis=1)
    result["starter_rate"] = keys.map(lambda key: signals.get(key, {}).get("starter_rate"))
    result["lineup_scope"] = keys.map(lambda key: signals.get(key, {}).get("lineup_scope", "Nicht gefunden"))
    result["li_status"] = keys.map(lambda key: signals.get(key, {}).get("li_status", "Kein Treffer"))
    result["ligainsider_url"] = keys.map(lambda key: signals.get(key, {}).get("ligainsider_url"))
    return order_signal_columns(result)


def add_empty_signal_columns(df, scope):
    if df.empty:
        return df

    result = df.copy()
    result["starter_rate"] = None
    result["lineup_scope"] = scope
    result["li_status"] = scope
    result["ligainsider_url"] = None
    return order_signal_columns(result)


def order_signal_columns(result):
    other_cols = [col for col in result.columns if col not in SIGNAL_COLUMNS]
    if "expected_change_pct" in other_cols:
        insert_at = other_cols.index("expected_change_pct") + 1
        return result[other_cols[:insert_at] + SIGNAL_COLUMNS + other_cols[insert_at:]]
    return result


def before_marker(text, markers):
    upper_text = text.upper()
    positions = [upper_text.find(marker) for marker in markers if upper_text.find(marker) > 0]
    return text[: min(positions)] if positions else text


def after_marker(text, markers):
    start = find_marker(text, markers)
    return text[start:] if start >= 0 else ""


def find_marker(text, markers):
    upper_text = text.upper()
    positions = [upper_text.find(marker) for marker in markers if upper_text.find(marker) >= 0]
    return min(positions) if positions else -1


def is_probable_player_name(text):
    words = clean_text(text).split()
    if not 1 <= len(words) <= 4:
        return False
    blocked = {"news", "fragen", "transfers", "aufstellung", "kader", "kaderanalyse", "registrieren", "login"}
    return normalize_name(text) not in blocked and any(char.isalpha() for char in text)


def team_slug_from_url(url):
    match = re.search(r"/team/([^/]+)/", url)
    return match.group(1).replace("-", " ") if match else ""


def normalize_team_name(name):
    key = normalize_name(name)
    key = re.sub(r"\b(fc|sc|sv|vfl|vfb|tsg|fsv|sport club|1|04|07)\b", " ", key)
    key = " ".join(key.split())
    return TEAM_ALIASES.get(key, TEAM_ALIASES.get(normalize_name(name), key))


def normalize_name(name):
    if not name:
        return ""
    normalized = unicodedata.normalize("NFKD", str(name))
    normalized = "".join(char for char in normalized if not unicodedata.combining(char))
    normalized = normalized.lower()
    normalized = normalized.replace("ß", "ss")
    normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
    return " ".join(normalized.split())


def clean_text(text):
    return " ".join(str(text).split())
