"""Bounded, read-only Kickbase snapshots for the local adviser."""

from copy import deepcopy
from datetime import datetime, timezone
from urllib.parse import quote

import requests

from kickbase_api.config import BASE_URL
from features.lineup_optimizer import market_context


class LiveKickbase:
    def __init__(self, username, password):
        self.username, self.password = username, password
        self.token = None

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

        def convert(items, owned):
            parsed = market_context(items, set(), user_id if not owned else None, {}, None, None)
            result = []
            for player in parsed:
                previous = old.get(player['id'], {})
                for field in ('l3', 'season', 'average', 'li', 'change', 'opponent'):
                    player[field] = previous.get(field)
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
