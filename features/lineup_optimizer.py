"""Export a private, self-contained squad simulator from the report snapshot."""

import json
import math
import pandas as pd
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from kickbase_api.config import BASE_URL, get_cdn_url, get_json_with_token
from kickbase_api.league import has_user_market_offer, is_user_market_listing, player_status_value
from kickbase_api.user import get_budget, get_players_in_squad
from kickbase_api.player import get_player_info, get_player_performance
from features.predictions.predictions import normalize_player_status
from features.predictions.snapshot import project_to_matchday


def number(value):
    try:
        result = float(value)
        return result if math.isfinite(result) else None
    except (TypeError, ValueError):
        return None


def text(value):
    return str(value) if value is not None and str(value) not in ('nan', 'None', '<NA>') else ''


def own_bid_amount(item, user_id):
    # Only explicitly owned offers may supply a price; asking prices are not bids.
    for key in ('ownBid', 'ownOffer'):
        offer = item.get(key)
        if isinstance(offer, dict):
            for field in ('prc', 'price', 'amount', 'v'):
                if number(offer.get(field)) is not None:
                    return number(offer[field])
        elif not isinstance(offer, bool) and number(offer) is not None:
            return number(offer)
    for key in ('of', 'ofs', 'offers', 'bids'):
        offers = item.get(key, [])
        if isinstance(offers, dict):
            offers = list(offers.values())
        if not isinstance(offers, list):
            continue
        for offer in offers:
            if not isinstance(offer, dict):
                continue
            owner = offer.get('ui') or offer.get('u') or offer.get('userId') or offer.get('user_id')
            if owner is not None and str(owner) == str(user_id):
                for field in ('prc', 'price', 'amount', 'v'):
                    if number(offer.get(field)) is not None:
                        return number(offer[field])
    return None


def write_lineup_optimizer(token, league_id, user_id, squad_df, predictions_df,
                           output_path='startelf_optimizer.html', history_df=None,
                           refresh_missing_history=False, competition_id=1, history_note=None,
                           forecast_snapshot=None):
    squad = get_players_in_squad(token, league_id).get('it', [])
    market = get_json_with_token(f'{BASE_URL}/leagues/{league_id}/market', token).get('it', [])
    predictions = {str(row['player_id']): row for row in predictions_df.to_dict('records')}
    reports = {' '.join((text(row.get('first_name')), text(row.get('last_name')))).strip(): row
               for row in squad_df.to_dict('records')}
    own_ids = {str(item['i']) for item in squad}
    candidates = [(item, True) for item in squad]
    candidates += [(item, False) for item in market
                   if str(item.get('i')) not in own_ids
                   and (has_user_market_offer(item, user_id) or own_bid_amount(item, user_id) is not None)]
    players = []
    seen = set()
    for item, owned in candidates:
        player_id = str(item.get('i'))
        if player_id in seen:
            continue
        seen.add(player_id)
        row = dict(predictions.get(player_id, {}))
        player_history = history_df
        cached = (history_df is not None and not history_df.empty
                  and history_df['player_id'].astype(str).eq(player_id).any())
        if refresh_missing_history and not cached:
            try:
                info = get_player_info(token, competition_id, player_id)
                row.update(info)
                performance = get_player_performance(token, competition_id, player_id, 50, info.get('team_id'))
                player_history = pd.DataFrame([{**game, **info} for game in performance])
                print(f'Optimizer: loaded missing history for player {player_id}.')
            except Exception as exc:
                print(f'Warning: Optimizer history unavailable for player {player_id}: {exc}')
        name = ' '.join((text(item.get('fn') or row.get('first_name')),
                         text(item.get('ln') or row.get('last_name')))).strip()
        if owned and name in reports:
            row.update(reports[name])
        position = number(item.get('pos') or row.get('position'))
        players.append({
            'id': player_id, 'name': name or f'Spieler {player_id}', 'owned': owned,
            'position': int(position) if position in (1, 2, 3, 4) else 0,
            'team': text(row.get('team_name') or item.get('tn')) or 'Unbekannt',
            'teamId': text(item.get('tid') or row.get('team_id') or row.get('team_name')),
            'image': text(row.get('image_url')) or (get_cdn_url(item['pim']) if item.get('pim') else ''),
            'mv': number(item.get('mv')) if number(item.get('mv')) is not None else number(row.get('mv')),
            'bid': None if owned else own_bid_amount(item, user_id),
            'status': (normalize_player_status(player_status_value(item))
                       if player_status_value(item) is not None
                       else text(row.get('player_status')) or 'Unbekannt'),
            'l3': None, 'season': None,
            'average': number(row.get('last_season_avg_points')),
            'li': number(row.get('starter_rate')),
            'change': number((forecast_snapshot or {}).get('predictions', {}).get(player_id)),
        })
        if player_history is not None and not player_history.empty:
            players[-1].update(history_context(player_history, player_id))
    horizon = forecast_horizon(history_df)
    for player in players:
        player['matchdayChange'] = project_to_matchday(
            forecast_snapshot, player['id'], horizon['updates'] if horizon else None)
    payload = {'players': players, 'budget': number(get_budget(token, league_id)),
               'marketPlayers': market_context(market, own_ids, user_id, predictions, history_df, forecast_snapshot),
               'league': str(league_id), 'user': str(user_id), 'historyNote': history_note,
               'forecast': {key: forecast_snapshot.get(key) for key in ('generatedAt', 'source')}
               if forecast_snapshot else None,
               'forecastHorizon': horizon,
               'generated': datetime.now(ZoneInfo('Europe/Berlin')).strftime('%d.%m.%Y %H:%M')}
    return render_optimizer(payload, output_path)


def market_context(market, own_ids, user_id, predictions, history, forecasts):
    """Include all offers for the local adviser, without loading more endpoints."""
    result = []
    seen = set()
    now = datetime.now(ZoneInfo('Europe/Berlin'))
    for item in market:
        player_id = str(item.get('i'))
        if player_id in own_ids or player_id in seen or is_user_market_listing(item, user_id):
            continue
        seen.add(player_id)
        row = predictions.get(player_id, {})
        name = ' '.join((text(item.get('fn') or row.get('first_name')),
                         text(item.get('ln') or row.get('last_name')))).strip()
        expiry = number(item.get('exs'))
        position = number(item.get('pos') or row.get('position'))
        player = {
            'id': player_id, 'name': name or f'Spieler {player_id}', 'owned': False,
            'team': text(item.get('tn') or row.get('team_name')) or 'Unbekannt',
            'teamId': text(item.get('tid') or row.get('team_id') or row.get('team_name')),
            'position': int(position) if position in (1, 2, 3, 4) else 0,
            'mv': number(item.get('mv')) if number(item.get('mv')) is not None else number(row.get('mv')),
            'askingPrice': number(item.get('prc')), 'bid': own_bid_amount(item, user_id),
            'image': get_cdn_url(item.get('pim')) or text(row.get('image_url')),
            'expiresAt': (now + timedelta(seconds=expiry)).isoformat()
            if expiry is not None and 0 <= expiry <= 365 * 86400 else None,
            'status': normalize_player_status(player_status_value(item))
            if player_status_value(item) is not None else 'Unbekannt',
            'change': number((forecasts or {}).get('predictions', {}).get(player_id)),
            'l3': None, 'season': None, 'average': number(row.get('last_season_avg_points')),
        }
        if history is not None and not history.empty:
            player.update(history_context(history, player_id))
        result.append(player)
    return result


def forecast_horizon(history, now=None):
    """Count 22:00 updates strictly before the next cached fixture date.

    The database stores dates, not kickoff times, so the fixture day's update
    is excluded rather than assuming a kickoff time.
    """
    if history is None or history.empty or not {'md', 'p'}.issubset(history.columns):
        return None
    now = now or datetime.now(ZoneInfo('Europe/Berlin'))
    now = now.astimezone(ZoneInfo('Europe/Berlin'))
    dates = pd.to_datetime(history['md'], errors='coerce', utc=True).dt.tz_localize(None)
    future = dates[(dates >= pd.Timestamp(now.date())) & pd.to_numeric(history['p'], errors='coerce').isna()]
    if future.empty:
        return None
    next_date = future.min().date()
    updates = max(0, (next_date - now.date()).days - (1 if now.hour >= 22 else 0))
    return {'date': next_date.isoformat(), 'updates': updates}


def history_context(history, player_id):
    """Use completed, unique matchdays, never forward-filled daily price rows."""
    rows = history[history['player_id'].astype(str) == player_id].copy()
    if rows.empty:
        return {}
    today = pd.Timestamp(datetime.now(ZoneInfo('Europe/Berlin')).date())
    rows['_day'] = pd.to_datetime(rows['md'], errors='coerce', utc=True).dt.tz_localize(None)
    rows['p'] = pd.to_numeric(rows['p'], errors='coerce')
    completed = rows[(rows['_day'] <= today) & rows['p'].notna()].sort_values('_day').drop_duplicates('_day', keep='last')
    season_start = pd.Timestamp(year=today.year if today.month >= 7 else today.year - 1, month=7, day=1)
    current = completed[completed['_day'] >= season_start]
    previous = completed[(completed['_day'] < season_start) & (completed['_day'] >= season_start - pd.DateOffset(years=1))]
    recent = current.tail(3)
    def latest_value(columns):
        for column in columns:
            if column in rows.columns:
                values = pd.to_numeric(rows[column], errors='coerce').dropna()
                if not values.empty:
                    return number(values.iloc[-1])
        return None

    history_rows = []
    for _, row in completed.tail(8).iloc[::-1].iterrows():
        history_rows.append({
            'date': text(row.get('_day').date() if hasattr(row.get('_day'), 'date') else row.get('_day')),
            'points': number(row.get('p')), 'minutes': number(row.get('mp')),
            'goals': number(row.get('goals') if 'goals' in row else row.get('g')),
            'assists': number(row.get('assists') if 'assists' in row else row.get('a')),
            'cards': number(row.get('k') if 'k' in row else row.get('cards')),
        })
    result = {'recent': [number(v) for v in recent['p']],
              'l3': number(recent['p'].mean()) if not recent.empty else None,
              'season': number(current['p'].mean()) if not current.empty else None,
              'average': number(previous['p'].mean()) if not previous.empty else None,
              'opponent': None, 'history': history_rows,
              'minutes': latest_value(('mp', 'minutes')), 'cards': latest_value(('k', 'cards')),
              'goals': latest_value(('goals', 'g')), 'assists': latest_value(('assists', 'a')),
              'fixtures': []}
    upcoming = rows[(rows['_day'] >= today) & rows['p'].isna()].sort_values('_day')
    if not upcoming.empty:
        match = upcoming.iloc[0]
        team_id = number(rows.iloc[-1].get('team_id'))
        home, away = number(match.get('t1')), number(match.get('t2'))
        if team_id is not None and team_id in (home, away):
            opponent_id = away if home == team_id else home
            teams = history[pd.to_numeric(history['team_id'], errors='coerce') == opponent_id]
            if not teams.empty:
                is_home = home == team_id
                opponent_name = text(teams.iloc[-1]['team_name'])
                result['opponent'] = opponent_name + (' (H)' if is_home else ' (A)')
                result['fixtures'] = [{'date': text(match.get('_day').date() if hasattr(match.get('_day'), 'date') else match.get('_day')),
                                       'opponent': opponent_name, 'venue': 'Heim' if is_home else 'Auswärts',
                                       'rank': number(teams.iloc[-1].get('rank'))}]
    return result


def render_optimizer(payload, output_path):
    template = Path(__file__).with_name('lineup_optimizer.html').read_text(encoding='utf-8')
    serialized = json.dumps(payload, ensure_ascii=True, allow_nan=False).replace('<', '\\u003c')
    path = Path(output_path)
    path.write_text(template.replace('__PAYLOAD__', serialized), encoding='utf-8')
    print(f'Startelf optimizer written to {path}: {len(payload["players"])} players.')
    return path
