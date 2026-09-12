"""Bounded, read-only Kickbase snapshots for the local adviser."""

from copy import deepcopy
from datetime import datetime, timezone
from urllib.parse import quote

import requests
import re
import time
import threading
from features.player_details import build_details

from kickbase_api.config import BASE_URL
from features.lineup_optimizer import market_context


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
        old = {str(p['id']): p for p in report['players'] + report.get('marketPlayers', [])}
        own_ids = {str(p['i']) for p in squad}
        name_lookups = 0

        def convert(items, owned):
            nonlocal name_lookups
            enriched = []
            for item in items:
                item = dict(item)
                previous = old.get(str(item.get('i')), {})
                known_name = previous.get('name', '')
                if re.fullmatch(r'Spieler\s+\d+', known_name):
                    known_name = ''
                # The squad endpoint often omits names; keep the report identity.
                if not item.get('ln') and not known_name and name_lookups < 8:
                    name_lookups += 1
                    try:
                        detail = self.get('/competitions/1/players/' + quote(str(item.get('i')), safe=''))
                        for field in ('fn', 'ln'):
                            if detail.get(field):
                                item[field] = detail[field]
                    except requests.RequestException:
                        pass
                enriched.append(item)
            parsed = market_context(enriched, set(), user_id if not owned else None, {}, None, None)
            raw = {str(item.get('i')): item for item in enriched}
            result = []
            for player in parsed:
                previous = old.get(player['id'], {})
                live_item = raw[player['id']]
                live_profile = live_item
                if not live_item.get('ap') or not live_item.get('ph'):
                    try:
                        live_profile = self.get('/competitions/1/players/' + quote(player['id'], safe=''))
                    except (requests.RequestException, KeyError, TypeError, RuntimeError):
                        live_profile = live_item
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
                if player['team'] == 'Unbekannt' and player['teamId'] == previous.get('teamId'):
                    player['team'] = previous.get('team', 'Unbekannt')
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
                   'maxNegative': -sum((p.get('mv') or 0) for p in owned) * 0.33}
        changes = {'addedOwnedIds': sorted(own_ids - {p['id'] for p in report['players'] if p['owned']}),
                   'removedPlanIds': sorted(set(previous_plans) - ids),
                   'cashBefore': raw_state.get('budget'), 'cashNow': budget}
        return current, state, {'source': 'Kickbase API', 'fetchedAt': datetime.now(timezone.utc).isoformat(),
                                'marketCount': len(available_ids), 'changes': changes,
                                'note': 'Live-Cash und Besitz ersetzen den Reportstand für diese Antwort. Manuelle Pläne bleiben soweit möglich erhalten. Punkte und Prognosen stammen weiterhin aus dem Report; Spielfeld nicht automatisch aktualisiert.'}
