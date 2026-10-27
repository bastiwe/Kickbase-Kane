"""Bounded, read-only Kickbase snapshots for the local adviser."""

from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import quote
from zoneinfo import ZoneInfo

import os
import sqlite3
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests
import re
import time
import threading
from features.player_details import build_details

from kickbase_api.config import BASE_URL, get_cdn_url
from features.cash_reconstruction import fetch_manager_transfers
from features.lineup_optimizer import forecast_horizon_from_matchdays, market_context
from features.predictions.predictions import normalize_player_status


BERLIN = ZoneInfo('Europe/Berlin')


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
                'team_image_url': 'team_image_url' if 'team_image_url' in columns else "''",
                'date': 'date' if 'date' in columns else "''",
            }
            placeholders = ','.join('?' for _ in ids)
            rows = connection.execute(
                f"""SELECT player_id, {select['first_name']}, {select['last_name']},
                           {select['team_name']}, {select['team_id']}, {select['image_url']},
                           {select['team_image_url']}
                    FROM player_data_1d
                    WHERE player_id IN ({placeholders})
                    ORDER BY {select['date']} DESC""",
                ids,
            ).fetchall()
    except sqlite3.Error:
        return {}
    result = {}
    for player_id, first_name, last_name, team_name, team_id, image_url, team_image_url in rows:
        result.setdefault(str(player_id), {
            'first_name': first_name or '',
            'last_name': last_name or '',
            'team_name': team_name or '',
            'team_id': team_id or '',
            'image_url': image_url or '',
            'team_image_url': team_image_url or '',
        })
    return result


def activity_field(value):
    """Return an id/name from the inconsistent activity-feed value shapes."""
    if isinstance(value, dict):
        for key in ('n', 'name', 'unm', 'username', 'i', 'id', 'ui', 'u', 'v', 'value'):
            if value.get(key) not in (None, ''):
                return activity_field(value[key])
        return ''
    return str(value or '').strip()


def activity_party_matches(value, user_id, user_name):
    if isinstance(value, dict):
        values = [activity_field(value.get(key)) for key in (
            'i', 'id', 'ui', 'u', 'n', 'name', 'unm', 'username'
        )]
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


def activity_market_value_day(value):
    """Return the market-value snapshot that was active when a transfer happened."""
    try:
        activity_time = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
        if activity_time.tzinfo is None:
            activity_time = activity_time.replace(tzinfo=timezone.utc)
        activity_time = activity_time.astimezone(BERLIN)
    except (TypeError, ValueError, OverflowError):
        return ''
    # Kickbase updates market values at 22:00 Berlin time. Until then the
    # previous calendar day's history entry is the value used for the trade.
    if activity_time.hour < 22:
        activity_time -= timedelta(days=1)
    return activity_time.date().isoformat()


def recent_form_points(profile, limit=3):
    """Return the latest Kickbase matchdays, including non-appearances as zero."""
    values = []
    entries = profile.get('ph', []) if isinstance(profile, dict) else []
    for entry in entries[:limit] if isinstance(entries, list) else []:
        if not isinstance(entry, dict):
            continue
        try:
            values.append(float(entry.get('p') or 0))
        except (TypeError, ValueError):
            values.append(0.0)
    return values


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
        self.market_change_cache = {}
        self.market_change_lock = threading.Lock()
        self.market_history_cache = {}
        self.market_history_lock = threading.Lock()
        self.purchase_price_cache = {}
        self.purchase_price_lock = threading.Lock()
        self.recent_transfers_cache = {}
        self.recent_transfer_values = {}
        self.recent_transfers_lock = threading.Lock()

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
                    except (requests.RequestException, RuntimeError, ValueError):
                        continue
                    profiles[player_id] = profile
                    with self.profile_lock:
                        self.profile_cache[player_id] = (now, profile)
        return profiles

    def player_purchase_prices(self, league_id, player_ids, user_id, user_name):
        """Read each current owner's paid price from the league transfer history."""
        now = time.monotonic()
        ids = [str(player_id) for player_id in player_ids if str(player_id).isdigit()]
        prices = {}
        missing = []
        with self.purchase_price_lock:
            for player_id in ids:
                key = (str(league_id), player_id, str(user_id))
                cached = self.purchase_price_cache.get(key)
                if cached and now - cached[0] < 3600:
                    prices[player_id] = cached[1]
                else:
                    missing.append(player_id)
        if missing:
            def load(player_id):
                payload = self.get(
                    '/leagues/' + quote(str(league_id), safe='') + '/players/'
                    + quote(player_id, safe='') + '/transferHistory?start=0'
                )
                entries = payload.get('it', [])
                if not isinstance(entries, list):
                    return player_id, None
                for entry in sorted(entries, key=lambda item: str(item.get('dt') or ''), reverse=True):
                    if not isinstance(entry, dict):
                        continue
                    buyer = entry.get('u') or entry.get('buyer') or entry.get('byr')
                    if not activity_party_matches(buyer, user_id, user_name):
                        continue
                    value = entry.get('trp', entry.get('price', entry.get('prc')))
                    try:
                        return player_id, float(value)
                    except (TypeError, ValueError):
                        return player_id, None
                return player_id, None
            with ThreadPoolExecutor(max_workers=min(4, len(missing))) as executor:
                futures = [executor.submit(load, player_id) for player_id in missing]
                for future in as_completed(futures):
                    try:
                        player_id, price = future.result()
                    except (requests.RequestException, RuntimeError, ValueError, KeyError, TypeError):
                        continue
                    prices[player_id] = price
                    with self.purchase_price_lock:
                        self.purchase_price_cache[(str(league_id), player_id, str(user_id))] = (now, price)
        return prices

    def player_purchase_price_before(self, league_id, player_id, manager_name, transferred_at):
        """Find what a manager paid before a later sale back to Kickbase."""
        payload = self.get(
            '/leagues/' + quote(str(league_id), safe='') + '/players/'
            + quote(str(player_id), safe='') + '/transferHistory?start=0'
        )
        entries = payload.get('it', [])
        if not isinstance(entries, list):
            return None
        try:
            cutoff = datetime.fromisoformat(str(transferred_at).replace('Z', '+00:00'))
            if cutoff.tzinfo is None:
                cutoff = cutoff.replace(tzinfo=timezone.utc)
            cutoff = cutoff.astimezone(timezone.utc)
        except (TypeError, ValueError, OverflowError):
            cutoff = None
        for entry in sorted(entries, key=lambda item: str(item.get('dt') or ''), reverse=True):
            if not isinstance(entry, dict):
                continue
            try:
                entry_time = datetime.fromisoformat(str(entry.get('dt')).replace('Z', '+00:00'))
                if entry_time.tzinfo is None:
                    entry_time = entry_time.replace(tzinfo=timezone.utc)
                if cutoff is not None and entry_time.astimezone(timezone.utc) >= cutoff:
                    continue
            except (TypeError, ValueError, OverflowError):
                if cutoff is not None:
                    continue
            # Transfer history exposes the manager id as ``u`` and the visible
            # manager name separately as ``unm``. Match against the full row.
            buyer = entry
            if not activity_party_matches(buyer, '', manager_name):
                continue
            price = entry.get('trp', entry.get('price', entry.get('prc')))
            try:
                return float(price)
            except (TypeError, ValueError):
                return None
        return None

    def player_market_changes(self, player_ids):
        """Read the last completed market-value movement for players."""
        now = time.monotonic()
        wanted = [str(player_id) for player_id in player_ids if str(player_id).isdigit()]
        changes = {}
        missing = []
        with self.market_change_lock:
            for player_id in wanted:
                cached = self.market_change_cache.get(player_id)
                if cached and now - cached[0] < 600:
                    changes[player_id] = cached[1]
                else:
                    missing.append(player_id)
        if missing:
            def load(player_id):
                payload = self.get(
                    '/competitions/1/players/' + quote(player_id, safe='') + '/marketvalue/92'
                )
                values = [
                    entry.get('mv') for entry in payload.get('it', [])
                    if isinstance(entry, dict) and entry.get('mv') is not None
                ]
                change = None
                if len(values) >= 2:
                    change = float(values[-1]) - float(values[-2])
                return player_id, change
            with ThreadPoolExecutor(max_workers=min(6, len(missing))) as executor:
                futures = [executor.submit(load, player_id) for player_id in missing]
                for future in as_completed(futures):
                    try:
                        player_id, change = future.result()
                    except (requests.RequestException, RuntimeError, ValueError, KeyError, TypeError):
                        continue
                    changes[player_id] = change
                    with self.market_change_lock:
                        self.market_change_cache[player_id] = (now, change)
        return changes

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

    def player_market_histories(self, player_ids):
        """Load historical player market values directly from Kickbase, cached for an hour."""
        now = time.monotonic()
        wanted = sorted({str(player_id) for player_id in player_ids if str(player_id).isdigit()})
        histories = {}
        missing = []
        with self.market_history_lock:
            for player_id in wanted:
                cached = self.market_history_cache.get(player_id)
                if cached and now - cached[0] < 3600:
                    histories[player_id] = cached[1]
                else:
                    missing.append(player_id)
        if missing:
            def load(player_id):
                payload = self.get(
                    '/competitions/1/players/' + quote(player_id, safe='') + '/marketvalue/365'
                )
                return player_id, payload.get('it', [])
            # A history request is intentionally throttled: it runs only for
            # the chart and must not compete with normal dashboard data.
            with ThreadPoolExecutor(max_workers=min(4, len(missing))) as executor:
                futures = [executor.submit(load, player_id) for player_id in missing]
                for future in as_completed(futures):
                    try:
                        player_id, history = future.result()
                    except (requests.RequestException, RuntimeError, ValueError, KeyError, TypeError):
                        continue
                    if not isinstance(history, list):
                        continue
                    histories[player_id] = history
                    with self.market_history_lock:
                        self.market_history_cache[player_id] = (now, history)
        return histories

    def player_daily_market_changes(self, player_id, limit=4):
        """Return the last completed daily market-value movements for one player."""
        raw_history = self.player_market_histories([player_id]).get(str(player_id), [])
        epoch = datetime(1970, 1, 1, tzinfo=timezone.utc)
        values = {}
        for entry in raw_history:
            if not isinstance(entry, dict) or entry.get('dt') is None or entry.get('mv') is None:
                continue
            try:
                day = (epoch + timedelta(days=int(entry['dt']))).date().isoformat()
                values[day] = float(entry['mv'])
            except (TypeError, ValueError, OverflowError):
                continue
        timeline = sorted(values.items())
        changes = []
        for index in range(1, len(timeline)):
            day, value = timeline[index]
            previous = timeline[index - 1][1]
            changes.append({
                'date': day,
                'change': round(value - previous),
                'marketValue': round(value),
                'previousMarketValue': round(previous),
                'percent': ((value - previous) / previous * 100) if previous else None,
            })
        return {'changes': list(reversed(changes[-max(1, limit):]))}

    def recent_transfers(self, league_id, limit=5):
        """Return the newest league transfers directly from Kickbase."""
        cache_key = str(league_id)
        now = time.monotonic()
        with self.recent_transfers_lock:
            cached = self.recent_transfers_cache.get(cache_key)
            if cached and now - cached[0] < 60:
                return deepcopy(cached[1])

        payload = self.get(
            '/leagues/' + quote(cache_key, safe='') + '/activitiesFeed?max=100'
        )
        activities = payload.get('af', [])
        if not isinstance(activities, list):
            raise ValueError('Ungültiger Kickbase-Aktivitätenfeed.')
        raw_transfers = [
            entry for entry in activities
            if isinstance(entry, dict) and str(entry.get('t')) == '15'
            and isinstance(entry.get('data'), dict)
        ]
        raw_transfers.sort(key=lambda entry: str(entry.get('dt') or ''), reverse=True)
        raw_transfers = raw_transfers[:max(1, int(limit))]

        def value(data, *keys):
            for key in keys:
                candidate = data.get(key)
                if candidate in (None, ''):
                    continue
                if isinstance(candidate, dict):
                    for nested in ('v', 'value', 'amount', 'price', 'trp', 'mv', 'mvo',
                                   'n', 'name', 'unm', 'i', 'id'):
                        if candidate.get(nested) not in (None, ''):
                            return candidate[nested]
                    continue
                return candidate
            return None

        parsed = []
        for entry in raw_transfers:
            data = entry['data']
            player_id = activity_player_id(data)
            price = value(data, 'trp', 'prc', 'price', 'amount', 'bid', 'value')
            market_value = value(data, 'mv', 'marketValue', 'market_value',
                                 'mvo', 'marketValueOld', 'market_value_old')
            try:
                price = float(price)
            except (TypeError, ValueError):
                price = None
            try:
                market_value = float(market_value)
            except (TypeError, ValueError):
                market_value = None
            seller = activity_field(value(
                data, 'slr', 'seller', 'sellerName', 'seller_name', 'su'))
            buyer = activity_field(value(
                data, 'byr', 'buyer', 'buyerName', 'buyer_name', 'bu'))
            parsed.append({
                'playerId': player_id,
                'playerName': activity_field(value(
                    data, 'pn', 'playerName', 'player_name', 'name', 'n', 'player')),
                'image': activity_field(value(
                    data, 'pim', 'image', 'imageUrl', 'image_url')),
                'teamImage': activity_field(value(
                    data, 'tim', 'teamImage', 'teamImageUrl', 'team_image_url')),
                'from': seller or 'Kickbase',
                'to': buyer or 'Kickbase',
                'isKickbaseSale': bool(seller and not buyer),
                'price': round(price) if price is not None else None,
                'marketValue': market_value,
                'transferredAt': entry.get('dt'),
            })

        player_ids = {item['playerId'] for item in parsed if item['playerId']}
        profiles = self.player_profiles(player_ids) if player_ids else {}
        local_metadata = local_player_metadata(player_ids)
        # The activity feed's ``mv`` field is live and can change retroactively
        # at 22:00. Always prefer the dated history entry for the transfer time.
        histories = self.player_market_histories(player_ids) if player_ids else {}
        epoch = datetime(1970, 1, 1, tzinfo=timezone.utc)

        for item in parsed:
            player_id = item['playerId'] or ''
            profile = profiles.get(player_id, {})
            stored = local_metadata.get(player_id, {})
            if not item['playerName']:
                item['playerName'] = ' '.join(filter(None, (
                    profile.get('fn') or stored.get('first_name'),
                    profile.get('ln') or stored.get('last_name'),
                ))).strip() or ('Spieler ' + player_id if player_id else 'Unbekannter Spieler')
            image_path = item['image'] or profile.get('pim') or stored.get('image_url') or ''
            item['image'] = get_cdn_url(image_path) or ''
            team_image_path = (
                item['teamImage'] or profile.get('tim') or stored.get('team_image_url') or ''
            )
            item['teamImage'] = get_cdn_url(team_image_path) or ''
            snapshot_key = (cache_key, str(item['transferredAt']), player_id,
                            item['price'], item['from'], item['to'])
            with self.recent_transfers_lock:
                snapshot = self.recent_transfer_values.get(snapshot_key)
            if snapshot is not None:
                item['marketValue'] = snapshot
            elif player_id in histories:
                transfer_day = activity_market_value_day(item['transferredAt'])
                candidates = []
                for history_entry in histories[player_id]:
                    if not isinstance(history_entry, dict):
                        continue
                    try:
                        day = (epoch + timedelta(days=int(history_entry['dt']))).date().isoformat()
                        market_value = float(history_entry['mv'])
                    except (KeyError, TypeError, ValueError, OverflowError):
                        continue
                    if day <= transfer_day:
                        candidates.append((day, market_value))
                if candidates:
                    item['marketValue'] = max(candidates, key=lambda candidate: candidate[0])[1]
            item['marketValue'] = (
                round(item['marketValue']) if item['marketValue'] is not None else None
            )
            item['overpay'] = (
                item['price'] - item['marketValue']
                if item['price'] is not None and item['marketValue'] is not None else None
            )
            if item['marketValue'] is not None:
                with self.recent_transfers_lock:
                    self.recent_transfer_values.setdefault(snapshot_key, item['marketValue'])
            item['profitLoss'] = None
            if item['isKickbaseSale'] and player_id and item['price'] is not None:
                try:
                    purchase_price = self.player_purchase_price_before(
                        cache_key, player_id, item['from'], item['transferredAt']
                    )
                except (requests.RequestException, RuntimeError, ValueError, KeyError, TypeError):
                    purchase_price = None
                if purchase_price is not None:
                    item['profitLoss'] = item['price'] - round(purchase_price)

        result = {
            'transfers': parsed,
            'fetchedAt': datetime.now(timezone.utc).isoformat(),
            'note': 'Live aus dem Kickbase-Aktivitätenfeed',
        }
        with self.recent_transfers_lock:
            self.recent_transfers_cache[cache_key] = (now, deepcopy(result))
        return result

    def squad_value_history(self, league_id, player_ids):
        """Reconstruct the app's daily squad value from complete manager trades.

        The current value is anchored to the live squad response. Historical
        values use the manager-specific, paginated transfer endpoint rather
        than the truncated league activity feed.
        """
        league = quote(str(league_id), safe='')
        squad = self.get(f'/leagues/{league}/squad')
        squad_items = [item for item in squad.get('it', []) if isinstance(item, dict)]
        current_ids = {
            str(item.get('i') or item.get('pi')) for item in squad_items
            if str(item.get('i') or item.get('pi') or '').isdigit()
        }
        if not current_ids:
            current_ids = {str(player_id) for player_id in player_ids if str(player_id).isdigit()}
        if not current_ids:
            return {'series': [], 'note': 'Kein Kader für den historischen Verlauf verfügbar.'}
        live_value = sum(float(item.get('mv') or 0) for item in squad_items)

        user = self.get('/user/settings').get('u', {})
        user_id = str(user.get('i') or user.get('id') or user.get('ui') or '')
        configured_start = os.getenv('KICK_LEAGUE_START_DATE', '2026-08-15')
        transfers = fetch_manager_transfers(self.get, str(league_id), user_id, configured_start)
        own_trades = [
            (activity_day(entry.get('dt')), str(entry.get('pi')), entry.get('tty') == 1)
            for entry in transfers
            if activity_day(entry.get('dt')) and str(entry.get('pi') or '').isdigit()
            and entry.get('tty') in (1, 2)
        ]
        all_ids = current_ids | {player_id for _, player_id, _ in own_trades}

        raw_histories = self.player_market_histories(all_ids)
        values = {}
        epoch = datetime(1970, 1, 1, tzinfo=timezone.utc)
        for player_id, history in raw_histories.items():
            for entry in history:
                if not isinstance(entry, dict) or entry.get('dt') is None or entry.get('mv') is None:
                    continue
                try:
                    day = (epoch + timedelta(days=int(entry['dt']))).date().isoformat()
                    market_value = float(entry['mv'])
                except (TypeError, ValueError, OverflowError):
                    continue
                values.setdefault(day, {})[player_id] = market_value
        if len(values) < 2:
            return {'series': [], 'note': 'Kickbase lieferte noch nicht genügend historische Marktwerte.'}

        try:
            league_start = datetime.fromisoformat(configured_start).date().isoformat()
        except (TypeError, ValueError):
            league_start = min(values)
        reverse_trades = sorted(own_trades, key=lambda item: item[0], reverse=True)
        roster = set(current_ids)
        index = 0
        series = []
        for day in sorted(values, reverse=True):
            # Walk backwards from today's squad through the documented own transfers.
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
            # A partial squad sum looks plausible but is materially wrong.
            # Only publish fully covered historical days.
            if roster and covered == len(roster) and day >= league_start:
                series.append({'date': day, 'value': round(total), 'players': covered})

        series.reverse()
        today = datetime.now(BERLIN).date().isoformat()
        current_point = {'date': today, 'value': round(live_value), 'players': len(current_ids)}
        if series and series[-1]['date'] == today:
            series[-1] = current_point
        else:
            series.append(current_point)
        if len(series) < 2:
            return {'series': [], 'note': 'Kickbase lieferte für deinen Kader keine ausreichende Historie.'}
        note = (
            f'Aktueller Kaderwert direkt aus Kickbase: {round(live_value):,} €. '
            f'Tagesverlauf ab {league_start} aus vollständiger Manager-Transferhistorie '
            'und den Kickbase-Marktwertverläufen rekonstruiert.'
        ).replace(',', '.')
        return {'series': series, 'note': note}

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
        # The current v4 API replies with `it` entries and their lineup slots
        # (`lo`), while older versions returned `players`/`type`. Normalize
        # both formats before confirming the saved XI.
        verified = normalize_lineup(stored)
        stored_players = verified.get('players', [])
        if set(stored_players) != set(expected) or len(stored_players) != len(expected):
            raise RuntimeError('Kickbase hat die Aufstellung nicht wie angefordert gespeichert. Bitte Formation und Spieler prüfen.')
        stored_type = verified.get('formation', '')
        verification_warning = None if stored_type in ('', str(formation)) else (
            f'Kickbase meldete die Formation als {stored_type}; die elf Spieler wurden korrekt gespeichert.'
        )
        return {'response': response, 'stored': stored, 'verificationWarning': verification_warning}


    def bootstrap(self, league_name):
        """Create a live dashboard context without requiring a local report."""
        user = self.get('/user/settings').get('u', {})
        user_id = str(user.get('i') or user.get('id') or user.get('ui') or '')
        leagues = self.get('/leagues/selection').get('it', [])
        selected = next((league for league in leagues if league.get('n') == league_name), None)
        if selected is None and leagues:
            selected = leagues[0]
        if not selected:
            raise RuntimeError('Im Kickbase-Konto wurde keine Liga gefunden.')
        report = {
            'players': [], 'marketPlayers': [], 'budget': None,
            'league': str(selected.get('i')), 'user': user_id,
            'generated': 'Live aus Kickbase',
        }
        return self._refresh(report, {'selection': [], 'plans': {}, 'budget': None})

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
        live_market_changes = self.player_market_changes(profile_ids)
        purchase_prices = self.player_purchase_prices(league_id, [item.get('i') for item in squad], user_id, str(user.get('n') or user.get('name') or ''))
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
                for field in ('fn', 'ln', 'tn', 'tid', 'pim', 'tim', 'pos', 'st', 'prob', 'tp', 'sec', 'mv', 'ap', 'ph'):
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
                if not item.get('team_image_url') and stored.get('team_image_url'):
                    item['team_image_url'] = stored['team_image_url']
                enriched.append(item)
            parsed = market_context(enriched, set(), user_id if not owned else None, {}, None, None)
            raw = {str(item.get('i')): item for item in enriched}
            result = []
            for player in parsed:
                previous = old.get(player['id'], {})
                live_item = raw[player['id']]
                live_profile = live_profiles.get(player['id'], live_item)
                live_ph = recent_form_points(live_profile)
                if live_ph:
                    player['recentForm'] = live_ph
                    player['l3'] = sum(live_ph) / len(live_ph)
                if live_profile.get('ap') is not None:
                    player['season'] = float(live_profile['ap'])
                if live_profile.get('tp') is not None:
                    player['totalPoints'] = float(live_profile['tp'])
                if live_profile.get('sec') is not None:
                    player['minutes'] = round(float(live_profile['sec']) / 60)
                status = live_profile.get('st', live_profile.get('status'))
                if status is not None:
                    player['status'] = normalize_player_status(status)
                # The market/squad endpoint is refreshed for every page load
                # and therefore remains the source of truth for current MV.
                if live_profile.get('pim'):
                    player['image'] = get_cdn_url(live_profile['pim'])
                if not player.get('image'):
                    player['image'] = previous.get('image', '')
                team_image = live_profile.get('tim') or live_item.get('team_image_url')
                if team_image:
                    player['teamImage'] = get_cdn_url(team_image)
                if not player.get('teamImage'):
                    player['teamImage'] = previous.get('teamImage', '')
                if not raw[player['id']].get('ln') and previous.get('name') and not re.fullmatch(r'Spieler\s+\d+', previous['name']):
                    player['name'] = previous['name']
                for field in ('l3', 'season', 'average', 'li', 'change', 'lastMvChange', 'opponent',
                              'matchdayChange', 'recent', 'recentForm', 'previous', 'history', 'fixtures',
                              'minutes', 'cards', 'goals', 'assists', 'purchasePrice', 'profitLoss',
                              'teamImage'):
                    if player.get(field) is None and previous.get(field) is not None:
                        player[field] = previous[field]
                if player['id'] in live_market_changes:
                    player['lastMvChange'] = live_market_changes[player['id']]
                if owned and purchase_prices.get(player['id']) is not None:
                    player['purchasePrice'] = purchase_prices[player['id']]
                    player['profitLoss'] = (player.get('mv') or 0) - purchase_prices[player['id']]
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
        roster_value = sum((p.get('mv') or 0) for p in owned)
        # Official rule: the permitted debt equals 33% of the effective team
        # value (team value plus an already negative cash balance).
        debt_base = max(0, roster_value + min(float(budget), 0))
        max_negative = -debt_base * 0.33
        open_bid_total = sum(float(p.get('bid') or 0) for p in available if p.get('bid') is not None)
        buying_power = float(budget) - max_negative - open_bid_total
        current = {**report, 'players': current_players, 'marketPlayers': available, 'budget': budget,
                   'maxNegative': max_negative, 'openBidTotal': open_bid_total,
                   'buyingPower': buying_power,
                   'forecastHorizon': forecast_horizon or report.get('forecastHorizon')}
        changes = {'addedOwnedIds': sorted(own_ids - {p['id'] for p in report['players'] if p['owned']}),
                   'removedPlanIds': sorted(set(previous_plans) - ids),
                   'cashBefore': raw_state.get('budget'), 'cashNow': budget}
        return current, state, {'source': 'Kickbase API', 'fetchedAt': datetime.now(timezone.utc).isoformat(),
                                'marketCount': len(available_ids), 'changes': changes,
                                'note': 'Kader, Cash, Kaufkraft, offene Gebote, Marktwerte, Positionen, Status, Punkte und Minuten stammen live aus der Kickbase-API. Nur Marktwertprognosen und LigaInsider-Werte kommen aus dem letzten Prognose-Snapshot.'}
