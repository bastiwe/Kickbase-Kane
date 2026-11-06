"""Read-only live matchday views using observed Kickbase v4 response fields."""
from copy import deepcopy
from datetime import datetime, timezone
import math
from pathlib import Path
import threading
import time
from urllib.parse import quote

import requests

from features.history_store import HistoryStore
from kickbase_api.config import get_cdn_url


def number(value):
    if isinstance(value, bool) or value in (None, ''):
        return None
    try:
        result = float(value)
        return result if math.isfinite(result) else None
    except (ValueError, TypeError):
        return None


def stamp(value):
    try:
        date = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
        return date.replace(tzinfo=timezone.utc) if date.tzinfo is None else date
    except (ValueError, TypeError):
        return None


def fixture(row):
    return {'id': str(row.get('mi', '')), 'home': row.get('t1sy') or row.get('t1n') or 'Heim',
            'away': row.get('t2sy') or row.get('t2n') or 'Gast', 'kickoff': row.get('dt'),
            'homeImage': get_cdn_url(row.get('t1im')), 'awayImage': get_cdn_url(row.get('t2im')),
            'homeGoals': number(row.get('t1g')), 'awayGoals': number(row.get('t2g')),
            'live': row.get('il') is True, 'finished': row.get('st') == 2,
            'minute': row.get('mtd') or row.get('mt')}


# Display translations only. Event points always come from the actual API booking.
LABELS = {'Starting 11': 'Startelf', 'Played Minutes Bonus': 'Einsatzminuten-Bonus',
          'Possession lost': 'Ballverlust', 'Team Goal': 'Teamtor', 'Goal conceded': 'Gegentor',
          'Forward zone pass': 'Pass ins vordere Drittel', 'Accurate long Ball': 'Langer Ball angekommen',
          'Accurate pass': 'Pass gespielt', 'Pass': 'Pass gespielt',
          'Accurate Throw (GK)': 'Abwurf angekommen', 'Shot saved (GK)': 'Schuss gehalten',
          'Dive Save (GK)': 'Parade', 'Standing saved (GK)': 'Ball im Stehen gehalten',
          'Cleared (in the box)': 'Klärung im Strafraum'}


def action_data(payload, types):
    events = payload.get('events')
    available = isinstance(events, list)
    unique, rows = set(), []
    for index, event in enumerate(events if available else []):
        if not isinstance(event, dict):
            continue
        eid = str(event.get('ei') or f'row:{index}')
        if eid in unique:
            continue
        unique.add(eid)
        code = str(event.get('eti', ''))
        title = types.get(code) or f'Aktion {code or "unbekannt"}'
        rows.append({'id': eid, 'type': code, 'label': LABELS.get(title, title),
                     'points': number(event.get('p')), 'minute': number(event.get('mt')),
                     'correction': bool(event.get('cei')) or event.get('att') == 3,
                     'sequence': index})
    # The API includes retroactive corrections at the head of its feed. Keep them,
    # and order by their original match minute without subtracting them twice.
    rows.sort(key=lambda row: (row['minute'] if row['minute'] is not None else -1, -row['sequence']))
    groups = {}
    for row in rows:
        group = groups.setdefault(row['type'], {'type': row['type'], 'label': row['label'],
                                                'count': 0, 'corrections': 0, 'points': 0})
        group['count'] += 1
        group['corrections'] += int(row['correction'])
        if row['points'] is not None:
            group['points'] += row['points']
    booked = sum(row['points'] for row in rows if row['points'] is not None) if available else None
    total = number(payload.get('p'))
    complete = available and all(row['points'] is not None for row in rows)
    return {'playerId': str(payload.get('i', '')), 'name': payload.get('n') or 'Spieler',
            'image': get_cdn_url(payload.get('pim')), 'points': total, 'bookedPoints': booked,
            'difference': total - booked if total is not None and booked is not None else None,
            'available': available, 'complete': complete,
            'chronological': rows, 'grouped': sorted(groups.values(), key=lambda group: (-group['points'], group['label']))}


class LiveMatchday:
    def __init__(self, client_provider, history_path=None, start_date='2026-08-15'):
        self.client_provider = client_provider
        self.history_path = Path(history_path) if history_path else None
        self.start_date = start_date
        self.client = None
        self.cache = {}
        self.lock = threading.RLock()
        self.allowed = {}
        self.match_ids = {}
        self.players = {}
        self.started = {}

    def get(self, path, ttl=20):
        client = self.client_provider()
        if client is None:
            raise RuntimeError('Kickbase-Livezugriff ist nicht aktiviert.')
        if self.client is not client:
            self.cache.clear()
            self.allowed.clear()
            self.match_ids.clear()
            self.players.clear()
            self.started.clear()
            self.client = client
        now = time.monotonic()
        cached = self.cache.get(path)
        if cached and now - cached[0] < ttl:
            return deepcopy(cached[1])
        try:
            payload = client.get(path)
        except requests.HTTPError as error:
            if error.response is None or error.response.status_code != 401:
                raise
            payload = client.get(path)
        if not isinstance(payload, dict):
            raise ValueError('Ungültige Kickbase-Antwort')
        self.cache[path] = (now, deepcopy(payload))
        return payload

    def optional(self, path, notes, label, ttl=300):
        try:
            return self.get(path, ttl)
        except (requests.RequestException, RuntimeError, ValueError, KeyError, TypeError):
            notes.append(label + ' derzeit nicht abrufbar.')
            return {}

    def snapshot(self, league_id, day=None, now=None):
        with self.lock:
            return self._snapshot(str(league_id), day, now or datetime.now(timezone.utc))

    def _snapshot(self, league, day, now):
        league_path = '/leagues/' + quote(league, safe='')
        schedule = self.get('/competitions/1/matchdays')
        days = [row for row in schedule.get('it', []) if isinstance(row, dict) and number(row.get('day')) is not None]
        if not days:
            raise ValueError('Kein Spielplan verfügbar')
        selected_day = int(day if day is not None else schedule.get('day') or days[0]['day'])
        selected = next((row for row in days if int(row['day']) == selected_day), None)
        if selected is None:
            raise ValueError('Spieltag nicht im Spielplan')
        games = [fixture(row) for row in selected.get('it', []) if isinstance(row, dict)]
        dates = [stamp(game['kickoff']) for game in games if stamp(game['kickoff'])]
        started = bool(dates and min(dates) <= now)
        upcoming = bool(dates and min(dates) > now)
        ranking = self.get(league_path + f'/ranking?dayNumber={selected_day}')
        if not isinstance(ranking.get('us'), list):
            raise ValueError('Ligatabelle fehlt')
        notes, managers, player_ids = [], [], set()
        for manager in ranking['us']:
            mid = str(manager['i'])
            base = league_path + '/managers/' + quote(mid, safe='')
            name = manager.get('n') or 'Manager'
            squad = self.optional(base + '/squad', notes, 'Kader von ' + name)
            dashboard = self.optional(base + '/dashboard', notes, 'Kennzahlen von ' + name)
            center = self.optional(league_path + '/users/' + quote(mid, safe='') + f'/teamcenter?dayNumber={selected_day}',
                                   notes, 'Startelf von ' + name, ttl=20)
            user = next((row for row in center.get('us', []) if str(row.get('i')) == mid), {})
            entries = center.get('lp')
            ids = [str(pid) for pid in user.get('lp', [])]
            provisional = False
            if upcoming:
                provisional = True
                lineup = [dict(row, i=str(row.get('pi')), n=row.get('pn'), p=None)
                          for row in squad.get('it', []) if isinstance(row.get('lo'), int) and 0 <= row['lo'] < 11]
            elif isinstance(entries, list) and (entries or ids):
                by_id = {str(row['i']): row for row in entries if isinstance(row, dict) and row.get('i') is not None}
                # The requested manager's lp is authoritative; never include nlp.
                lineup = [by_id.get(pid, {'i': pid}) for pid in ids]
            else:
                lineup = self.archived_lineup(league, mid, selected_day)
                if lineup:
                    notes.append('Startelf von ' + name + ': archivierter Anpfiff-Kader, Livepunkte fehlen.')
                else:
                    notes.append('Startelf von ' + name + ' für diesen Spieltag nicht verfügbar.')
            if provisional:
                day_points = None
            else:
                day_points = number(user.get('mdp', manager.get('mdp')))
            own_squad = {str(row.get('pi')): row for row in squad.get('it', [])}
            normalized = []
            for row in lineup:
                pid = str(row.get('i'))
                player_ids.add(pid)
                metadata = own_squad.get(pid, {})
                profile = self.optional('/competitions/1/players/' + quote(pid, safe=''), notes,
                                        'Spielerprofil ' + pid, ttl=3600) if metadata.get('ap') is None or row.get('pos', metadata.get('pos')) is None else {}
                normalized.append({'id': pid, 'name': row.get('n') or metadata.get('pn') or profile.get('ln') or 'Spieler ' + pid,
                                   'image': get_cdn_url(row.get('pim') or metadata.get('pim') or profile.get('pim')),
                                   'points': None if provisional else number(row.get('p')),
                                   'position': number(row.get('pos', metadata.get('pos', profile.get('pos')))),
                                   'average': number(metadata.get('ap', profile.get('ap'))),
                                   'matchId': str(row.get('mi') or ''), 'matchStatus': row.get('mst')})
            normalized.sort(key=lambda row: (row['points'] is None, -(row['points'] or 0), row['name'], row['id']))
            if started and normalized and any(row['points'] is None for row in normalized):
                notes.append('Livepunkte von ' + name + ' teilweise nicht verfügbar.')
            positions = [row['position'] for row in normalized]
            formation = '-'.join(str(positions.count(pos)) for pos in [2, 3, 4]) if len(positions) == 11 and all(positions) else None
            averages = [row['average'] for row in normalized]
            delta = [number(row.get('tfhmvt')) for row in squad.get('it', [])]
            managers.append({'id': mid, 'name': name, 'image': None,
                             'seasonPoints': number(manager.get('sp')), 'seasonRank': number(manager.get('spl')),
                             'dayPoints': day_points, 'lineup': normalized, 'provisional': provisional,
                             'formation': formation, 'squadSize': len(squad['it']) if isinstance(squad.get('it'), list) else None,
                             'squadValue': number(dashboard.get('tv')), 'valueChange': sum(delta) if delta and all(v is not None for v in delta) else None,
                             'lineupAverage': sum(averages) if averages and all(v is not None for v in averages) else None,
                             'wins': number(dashboard.get('mdw')), 'seasonAverage': number(dashboard.get('ap'))})
        self.allowed[(league, selected_day)] = player_ids
        self.match_ids[(league, selected_day)] = {game['id'] for game in games}
        self.players[(league, selected_day)] = {row['id']: row for manager in managers for row in manager['lineup']}
        self.started[(league, selected_day)] = started
        managers.sort(key=lambda manager: (manager['dayPoints'] is None, -(manager['dayPoints'] or 0), manager['name']))
        return {'day': selected_day, 'days': [int(row['day']) for row in days], 'league': ranking.get('ti') or 'Liga',
                'started': started, 'managers': managers, 'fixtures': games, 'notes': list(dict.fromkeys(notes)),
                'fetchedAt': now.isoformat(), 'refreshSeconds': 20}

    def archived_lineup(self, league, manager, day):
        if self.history_path is None or not self.history_path.exists():
            return []
        store = HistoryStore(self.history_path)
        try:
            snapshot = store.kickoff_squad(f'{league}:{self.start_date}', manager, day)
            return [dict(row, i=str(row.get('pi')), n=row.get('pn'), p=None)
                    for row in (snapshot or {}).get('squad', {}).get('it', [])
                    if isinstance(row.get('lo'), int) and 0 <= row['lo'] < 11]
        finally:
            store.close()

    def player(self, league_id, day, player_id):
        with self.lock:
            league, pid = str(league_id), str(player_id)
            # Validate membership even if the user switched the Kickbase account.
            client = self.client_provider()
            if client is not self.client or (league, day) not in self.allowed:
                self._snapshot(league, day, datetime.now(timezone.utc))
            if pid not in self.allowed.get((league, day), set()):
                raise PermissionError('Spieler nicht in einer Startelf dieses Spieltags')
            metadata = self.players.get((league, day), {}).get(pid, {})
            if not self.started.get((league, day)):
                return {**action_data({'i': pid, 'n': metadata.get('name')}, {}), 'day': day,
                        'fetchedAt': datetime.now(timezone.utc).isoformat()}
            payload = self.get('/competitions/1/playercenter/' + quote(pid, safe='') + f'?dayNumber={day}&leagueId=' + quote(league, safe=''), ttl=10)
            if str(payload.get('i')) != pid:
                raise ValueError('Spielerantwort passt nicht zur Anfrage')
            if str(payload.get('mi')) not in self.match_ids.get((league, day), set()):
                # Some upcoming playercenter requests return the previous match.
                return {**action_data({'i': pid, 'n': metadata.get('name')}, {}), 'day': day,
                        'fetchedAt': datetime.now(timezone.utc).isoformat()}
            types_payload = self.get('/live/eventtypes', ttl=86400)
            types = {str(row['i']): row.get('ti') or '' for row in types_payload.get('it', []) if isinstance(row, dict) and 'i' in row}
            return {**action_data(payload, types), 'day': day, 'fetchedAt': datetime.now(timezone.utc).isoformat()}
