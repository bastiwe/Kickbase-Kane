"""Bounded, read-only Kickbase snapshots for the local adviser."""

from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote

import os
import sqlite3
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests
import re
import time
import threading
from features.player_details import build_details

from kickbase_api.config import BASE_URL
from features.lineup_optimizer import forecast_horizon_from_matchdays, market_context


def local_player_metadata(player_ids):
    """Fill sparse live market records from the local historical player cache."""
    ids = [str(player_id) for player_id in player_ids if str(player_id).isdigit()]
    database = Path(os.getenv('KICKBASE_DATA_DIR', '.')) / 'player_data_total.db'
    if not ids or not database.exists():
        return {}
    try:
        with sqlite3.connect(database) as connection:
            columns = {row[1] for row in connection.execute('PRAGMA table_info(player_data_1d)')}
            if 'player_id' not in columns:
                return {}
            select = {
                'first_name': 'first_name' if 'first_name' in columns else "''",
                'last_name': 'last_name' if 'last_name' in columns else "''",
                'team_name': 'team_name' if 'team_name' in columns else "''",
                'team_id': 'team_id' if 'team_id' in columns else "''",
                'image_url': 'image_url' if 'image_url' in columns else "''",
                'date': 'date' if 'date' in columns else "''",
            }
            placeholders = ','.join('?' for _ in ids)
            rows = connection.execute(
                f"""SELECT player_id, {select['first_name']}, {select['last_name']},
                           {select['team_name']}, {select['team_id']}, {select['image_url']}
                    FROM player_data_1d
                    WHERE player_id IN ({placeholders})
                    ORDER BY {select['date']} DESC""",
                ids,
            ).fetchall()
    except sqlite3.Error:
        return {}
    result = {}
    for player_id, first_name, last_name, team_name, team_id, image_url in rows:
        result.setdefault(str(player_id), {
            'first_name': first_name or '',
            'last_name': last_name or '',
            'team_name': team_name or '',
            'team_id': team_id or '',
            'image_url': image_url or '',
        })
    return result


def activity_field(value):
    """Return an id/name from the inconsistent activity-feed value shapes."""
    if isinstance(value, dict):
        for key in ('i', 'id', 'ui', 'u', 'n', 'name', 'v', 'value'):
            if value.get(key) not in (None, ''):
                return activity_field(value[key])
        return ''
    return str(value or '').strip()


def activity_party_matches(value, user_id, user_name):
    if isinstance(value, dict):
        values = [activity_field(value.get(key)) for key in ('i', 'id', 'ui', 'u', 'n', 'name')]
    else:
        values = [activity_field(value)]
    normalized = {value.casefold() for value in values if value}
    return str(user_id).casefold() in normalized or str(user_name).casefold() in normalized


def activity_player_id(data):
    for key in ('pi', 'player', 'p', 'playerId', 'player_id', 'id'):
        value = data.get(key)
        if isinstance(value, dict):
            value = value.get('i') or value.get('id') or value.get('pi')
        if value is not None and str(value).isdigit():
            return str(value)
    return None


def activity_day(value):
    try:
        return datetime.fromisoformat(str(value).replace('Z', '+00:00')).date().isoformat()
    except (TypeError, ValueError):
        return ''


def normalize_lineup(payload):
    """Normalize the v4 slot-based lineup, including empty starting slots."""
    if not isinstance(payload, dict):
        raise ValueError('Ungültige Aufstellungsdaten.')
    if 'it' in payload:
        entries = payload['it']
        if not isinstance(entries, list):
            raise ValueError('Ungültige Spielerliste.')
        starters = [p for p in entries if isinstance(p, dict)
                    and isinstance(p.get('lo'), int) and 0 <= p['lo'] < 11]
        from features.predictions.predictions import FORMATIONS
        candidates = []
        for name, counts in FORMATIONS:
            positions = [pos for pos in (1, 2, 3, 4) for _ in range(counts[pos])]
            if all(positions[p['lo']] == p.get('pos') for p in starters):
                candidates.append(name)
        return {'formation': candidates[0] if candidates else '',
                'players': [str(p['i']) for p in sorted(starters, key=lambda p: p['lo'])],
                'slots': {str(p['lo']): str(p['i']) for p in starters}}
    entries = payload.get('players', payload.get('p'))
    if not isinstance(entries, list):
        raise ValueError('Aufstellung enthält keine Spielerliste.')
    return {'formation': str(payload.get('type') or payload.get('t') or ''),
            'players': [str(p.get('i') or p.get('id')) if isinstance(p, dict) else str(p)
                        for p in entries if p is not None]}


class LiveKickbase:
    def __init__(self, username, password):
        self.username, self.password = username, password
        self.token = None
        self.detail_cache = {}
        self.detail_lock = threading.Lock()
        self.profile_cache = {}
        self.profile_lock = threading.Lock()

    def player_profiles(self, player_ids):
        """Read current player facts directly from Kickbase, with a short cache."""
        now = time.monotonic()
        wanted = [str(player_id) for player_id in player_ids if str(player_id).isdigit()]
        profiles = {}
        missing = []
        with self.profile_lock:
            for player_id in wanted:
                cached = self.profile_cache.get(player_id)
                if cached and now - cached[0] < 600:
                    profiles[player_id] = cached[1]
                else:
                    missing.append(player_id)
        if missing:
            def load(player_id):
                return player_id, self.get('/competitions/1/players/' + quote(player_id, safe=''))
            with ThreadPoolExecutor(max_workers=min(6, len(missing))) as executor:
                futures = [executor.submit(load, player_id) for player_id in missing]
                for future in as_completed(futures):
                    try:
                        player_id, profile = future.result()
                    except requests.RequestException:
                        continue
                    profiles[player_id] = profile
                    with self.profile_lock:
                        self.profile_cache[player_id] = (now, profile)
        return profiles

    def player_details(self, player_id):
        with self.detail_lock:
            def cached(path):
                entry = self.detail_cache.get(path)
                if entry and time.monotonic() - entry[0] < 300:
                    return entry[1]
                value = self.get(path)
                self.detail_cache[path] = (time.monotonic(), value)
                return value
            base = '/competitions/1/players/' + quote(str(player_id), safe='')
            return build_details(cached(base), cached(base + '/performance'), cached('/competitions/1/table'))

    def get(self, path):
        if not self.token:
            response = requests.post(BASE_URL + '/user/login', json={
                'em': self.username, 'pass': self.password, 'loy': False, 'rep': {}}, timeout=(5, 10))
            response.raise_for_status()
            self.token = response.json().get('tkn')
            if not self.token:
                raise RuntimeError('Kickbase-Anmeldung ohne Token. Zugangsdaten prüfen.')
        response = requests.get(BASE_URL + path, headers={'Authorization': 'Bearer ' + self.token}, timeout=(5, 10))
        if response.status_code == 401:
            self.token = None
        response.raise_for_status()
        return response.json()

    def post(self, path, payload):
        if not self.token:
            self.get('/user/settings')
        response = requests.post(BASE_URL + path, headers={'Authorization': 'Bearer ' + self.token}, json=payload, timeout=(5, 15))
        if response.status_code == 401:
            self.token = None
        if response.status_code >= 400:
            detail = response.text.strip().replace('\n', ' ')
            if len(detail) > 240:
                detail = detail[:237] + '...'
            raise RuntimeError(f'Kickbase-Aufstellung abgelehnt ({response.status_code}): {detail or "keine Detailmeldung"}')
        return response.json() if response.content else {}

    def lineup(self, league_id):
        return self.get('/leagues/' + quote(str(league_id), safe='') + '/lineup')

    def squad_value_history(self, league_id, player_ids):
        """Reconstruct the real squad-value path from own transfer activities."""
        database = Path(os.getenv('KICKBASE_DATA_DIR', '.')) / 'player_data_total.db'
        current_ids = {str(player_id) for player_id in player_ids if str(player_id).isdigit()}
        if not current_ids or not database.exists():
            return {'series': [], 'note': 'Historische Kaderwerte sind noch nicht verfügbar.'}

        user = self.get('/user/settings').get('u', {})
        user_id = str(user.get('i') or user.get('id') or user.get('ui') or '')
        user_name = str(user.get('n') or user.get('name') or '')
        feed = self.get('/leagues/' + quote(str(league_id), safe='') + '/activitiesFeed?max=5000')
        own_trades = []
        all_ids = set(current_ids)
        for entry in feed.get('af', []):
            if entry.get('t') != 15:
                continue
            data = entry.get('data') or {}
            day = activity_day(entry.get('dt'))
            player_id = activity_player_id(data)
            if not day or not player_id:
                continue
            bought = activity_party_matches(data.get('byr') or data.get('buyer'), user_id, user_name)
            sold = activity_party_matches(data.get('slr') or data.get('seller'), user_id, user_name)
            if bought == sold:
                continue
            own_trades.append((day, player_id, bought))
            all_ids.add(player_id)
        if not own_trades:
            return {'series': [], 'note': 'Eigene Transferhistorie konnte über die Kickbase-API nicht zugeordnet werden.'}

        today = datetime.now(timezone.utc).date()
        season_year = today.year if today.month >= 7 else today.year - 1
        season_start = f'{season_year}-08-01'
        placeholders = ','.join('?' for _ in all_ids)
        try:
            with sqlite3.connect(database) as connection:
                rows = connection.execute(
                    f"""SELECT substr(date, 1, 10) AS day, player_id, MAX(mv)
                         FROM player_data_1d
                         WHERE player_id IN ({placeholders})
                           AND substr(date, 1, 10) >= ?
                           AND mv IS NOT NULL
                         GROUP BY substr(date, 1, 10), player_id
                         ORDER BY day DESC""",
                    [*sorted(all_ids), season_start],
                ).fetchall()
        except sqlite3.Error:
            return {'series': [], 'note': 'Historische Marktwerte sind derzeit nicht lesbar.'}

        values = {}
        for day, player_id, market_value in rows:
            if day and market_value is not None:
                values.setdefault(day, {})[str(player_id)] = float(market_value)
        if len(values) < 2:
            return {'series': [], 'note': 'Noch nicht genügend historische Marktwerte verfügbar.'}

        reverse_trades = sorted(own_trades, key=lambda item: item[0], reverse=True)
        roster = set(current_ids)
        index = 0
        series = []
        for day in sorted(values, reverse=True):
            # Apply all transfers that happened after this day's final value.
            while index < len(reverse_trades) and reverse_trades[index][0] > day:
                _, player_id, bought = reverse_trades[index]
                if bought:
                    roster.discard(player_id)
                else:
                    roster.add(player_id)
                index += 1
            day_values = values[day]
            total = sum(day_values.get(player_id, 0) for player_id in roster)
            covered = sum(1 for player_id in roster if player_id in day_values)
            if covered:
                series.append({'date': day, 'value': round(total), 'players': covered})

        series.reverse()
        first_trade = min(day for day, _, _ in own_trades)
        return {
            'series': series,
            'note': (
                'Kaderwert aus deinem Kickbase-Transferverlauf und den historischen Marktwerten rekonstruiert.'
                + (f' Transferfeed ab {first_trade} verfügbar.' if first_trade > season_start else '')
            ),
        }

    def apply_lineup(self, league_id, formation, player_ids):
        league_path = '/leagues/' + quote(str(league_id), safe='') + '/lineup'
        expected = [str(player_id) for player_id in player_ids]
        response = self.post(league_path, {
            'type': formation,
            'players': expected,
        })
        # Kickbase can return an empty 200 response. Read the resource again so
        # the UI only reports success when the server actually stored the XI.
        stored = self.get(league_path)
        stored_type = str(stored.get('type') or stored.get('t') or '')
        stored_players = stored.get('players') or stored.get('p')
        if isinstance(stored_players, list):
            stored_players = [str(
                item.get('i') or item.get('id') if isinstance(item, dict) else item
            ) for item in stored_players]
        if not isinstance(stored_players, list) or set(stored_players) != set(expected):
            raise RuntimeError('Kickbase hat die Aufstellung nicht wie angefordert gespeichert. Bitte Formation und Spieler prüfen.')
        verification_warning = None if stored_type in ('', str(formation)) else (
            f'Kickbase meldete die Formation als {stored_type}; die elf Spieler wurden korrekt gespeichert.'
        )
        return {'response': response, 'stored': stored, 'verificationWarning': verification_warning}


    def refresh(self, report, raw_state):
        try:
            return self._refresh(report, raw_state)
        except requests.RequestException as exc:
            code = getattr(exc.response, 'status_code', None)
            if code == 429:
                raise RuntimeError('Kickbase-Anfragelimit erreicht. Bitte später erneut versuchen.') from None
            raise RuntimeError('Kickbase-Liveabruf fehlgeschlagen. Zugangsdaten und Verbindung prüfen; keine veraltete Live-Beratung erstellt.') from None

    def _refresh(self, report, raw_state):
        user = self.get('/user/settings').get('u', {})
        user_id = str(user.get('i') or user.get('id') or user.get('ui') or '')
        league_id = str(report.get('league') or '')
        leagues = self.get('/leagues/selection').get('it', [])
        if user_id != str(report.get('user')) or not any(str(p.get('i')) == league_id for p in leagues):
            raise RuntimeError('Kickbase-Konto oder Liga passt nicht zum Report. Bitte den passenden Report laden.')
        base = '/leagues/' + quote(league_id, safe='')
        squad = self.get(base + '/squad')['it']
        market = self.get(base + '/market')['it']
        budget = self.get(base + '/me/budget')['b']
        if not isinstance(squad, list) or not isinstance(market, list):
            raise RuntimeError('Kickbase lieferte unvollständige Kader-/Marktdaten.')
        profile_ids = [item.get('i') for item in squad] + [item.get('i') for item in market]
        live_profiles = self.player_profiles(profile_ids)
        forecast_horizon = None
        if squad:
            first_profile = live_profiles.get(str(squad[0].get('i')), {})
            forecast_horizon = forecast_horizon_from_matchdays(first_profile.get('mdsum', []))
        old = {str(p['id']): p for p in report['players'] + report.get('marketPlayers', [])}
        own_ids = {str(p['i']) for p in squad}
        cached_metadata = local_player_metadata(profile_ids)

        def convert(items, owned):
            enriched = []
            for item in items:
                item = dict(item)
                player_id = str(item.get('i'))
                profile = live_profiles.get(player_id, {})
                # Market and squad payloads are sparse. Current profile values
                # are authoritative; the local cache is only a last fallback.
                for field in ('fn', 'ln', 'tn', 'tid', 'pim', 'ap', 'ph'):
                    if profile.get(field) not in (None, ''):
                        item[field] = profile[field]
                stored = cached_metadata.get(player_id, {})
                if not item.get('fn') and stored.get('first_name'):
                    item['fn'] = stored['first_name']
                if not item.get('ln') and stored.get('last_name'):
                    item['ln'] = stored['last_name']
                if not item.get('tn') and stored.get('team_name'):
                    item['tn'] = stored['team_name']
                if not item.get('tid') and stored.get('team_id'):
                    item['tid'] = stored['team_id']
                if not item.get('image_url') and stored.get('image_url'):
                    item['image_url'] = stored['image_url']
                enriched.append(item)
            parsed = market_context(enriched, set(), user_id if not owned else None, {}, None, None)
            raw = {str(item.get('i')): item for item in enriched}
            result = []
            for player in parsed:
                previous = old.get(player['id'], {})
                live_item = raw[player['id']]
                live_profile = live_profiles.get(player['id'], live_item)
                live_ph = [entry.get('p') for entry in live_profile.get('ph', [])
                           if isinstance(entry, dict) and entry.get('p') is not None]
                if live_ph:
                    player['recent'] = [float(value) for value in live_ph[-3:]]
                    player['l3'] = sum(player['recent']) / len(player['recent'])
                if live_profile.get('ap') is not None:
                    player['season'] = float(live_profile['ap'])
                if live_profile.get('mv') is not None:
                    player['mv'] = float(live_profile['mv'])
                if live_profile.get('pim'):
                    from kickbase_api.config import get_cdn_url
                    player['image'] = get_cdn_url(live_profile['pim'])
                if not player.get('image'):
                    player['image'] = previous.get('image', '')
                if not raw[player['id']].get('ln') and previous.get('name') and not re.fullmatch(r'Spieler\s+\d+', previous['name']):
                    player['name'] = previous['name']
                for field in ('l3', 'season', 'average', 'li', 'change', 'opponent',
                              'matchdayChange', 'recent', 'previous', 'history', 'fixtures',
                              'minutes', 'cards', 'goals', 'assists'):
                    if player.get(field) is None and previous.get(field) is not None:
                        player[field] = previous[field]
                if player['team'] == 'Unbekannt' and previous.get('team') not in (None, '', 'Unbekannt'):
                    player['team'] = previous['team']
                player['owned'] = owned
                result.append(player)
            return result

        # Squad entries may carry listing flags; these are irrelevant for ownership.
        clean_squad = [{k: v for k, v in item.items() if k not in (
            'isOwn', 'is_own', 'own', 'mine', 'isMine', 'selling')} for item in squad]
        owned = convert(clean_squad, True)
        available = [p for p in convert(market, False) if p['id'] not in own_ids]
        available_ids = {p['id'] for p in available}
        state = deepcopy(raw_state)
        previous_plans = state['plans']
        planned = [p for p in available if p['id'] in previous_plans
                   and not old.get(p['id'], {}).get('owned')]
        current_players = owned + planned
        plans = {}
        for p in current_players:
            prior = previous_plans.get(p['id'], {})
            was_owned = old.get(p['id'], {}).get('owned') is True
            action = prior.get('action', 'keep') if p['owned'] and was_owned else 'keep' if p['owned'] else prior.get('action', 'skip')
            if action not in (('keep', 'sell') if p['owned'] else ('buy', 'skip')):
                action = 'keep' if p['owned'] else 'skip'
            price = prior.get('price')
            if not prior or price == old.get(p['id'], {}).get('mv') or p['owned'] != was_owned:
                price = p['mv'] if p['owned'] else p['bid']
            plans[p['id']] = {'action': action, 'price': price, 'locked': prior.get('locked') is True}
        ids = {p['id'] for p in current_players}
        state['selection'] = [p if p in ids else None for p in state['selection']]
        state['plans'] = plans
        state['budget'] = budget
        current = {**report, 'players': current_players, 'marketPlayers': available, 'budget': budget,
                   'maxNegative': -sum((p.get('mv') or 0) for p in owned) * 0.33,
                   'forecastHorizon': forecast_horizon or report.get('forecastHorizon')}
        changes = {'addedOwnedIds': sorted(own_ids - {p['id'] for p in report['players'] if p['owned']}),
                   'removedPlanIds': sorted(set(previous_plans) - ids),
                   'cashBefore': raw_state.get('budget'), 'cashNow': budget}
        return current, state, {'source': 'Kickbase API', 'fetchedAt': datetime.now(timezone.utc).isoformat(),
                                'marketCount': len(available_ids), 'changes': changes,
                                'note': 'Kader, Cash, Marktwerte, Spielerstatus und Punkte stammen live aus der Kickbase-API. Nur Marktwertprognosen kommen aus dem letzten Prognose-Snapshot.'}
