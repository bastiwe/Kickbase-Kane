"""Export a private, self-contained squad simulator from the report snapshot."""

import json
import math
import pandas as pd
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from kickbase_api.config import BASE_URL, get_cdn_url, get_json_with_token
from kickbase_api.league import has_user_market_offer, player_status_value
from kickbase_api.user import get_budget, get_players_in_squad
from features.predictions.predictions import normalize_player_status


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
                           output_path='startelf_optimizer.html', history_df=None):
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
            'l3': number(row.get('last_3_points')), 'season': number(row.get('current_season_points')),
            'previous': number(row.get('last_season_points')),
            'average': number(row.get('last_season_avg_points')),
            'li': number(row.get('starter_rate')),
            'change': number(row.get('predicted_mv_target')),
        })
        if history_df is not None:
            players[-1].update(history_context(history_df, player_id))
    payload = {'players': players, 'budget': number(get_budget(token, league_id)),
               'league': str(league_id), 'user': str(user_id),
               'generated': datetime.now(ZoneInfo('Europe/Berlin')).strftime('%d.%m.%Y %H:%M')}
    return render_optimizer(payload, output_path)


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
    result = {'recent': [number(v) for v in recent['p']],
              'l3': number(recent['p'].sum()) if not recent.empty else None,
              'season': number(current['p'].sum()) if not current.empty else None,
              'previous': number(previous['p'].sum()) if not previous.empty else None,
              'average': number(previous['p'].mean()) if not previous.empty else None,
              'opponent': None}
    upcoming = rows[(rows['_day'] >= today) & rows['p'].isna()].sort_values('_day')
    if not upcoming.empty:
        match = upcoming.iloc[0]
        team_id = number(rows.iloc[-1].get('team_id'))
        home, away = number(match.get('t1')), number(match.get('t2'))
        if team_id is not None and team_id in (home, away):
            opponent_id = away if home == team_id else home
            teams = history[pd.to_numeric(history['team_id'], errors='coerce') == opponent_id]
            if not teams.empty:
                result['opponent'] = text(teams.iloc[-1]['team_name']) + (' (H)' if home == team_id else ' (A)')
    return result


def render_optimizer(payload, output_path):
    template = Path(__file__).with_name('lineup_optimizer.html').read_text(encoding='utf-8')
    serialized = json.dumps(payload, ensure_ascii=True, allow_nan=False).replace('<', '\\u003c')
    path = Path(output_path)
    path.write_text(template.replace('__PAYLOAD__', serialized), encoding='utf-8')
    print(f'Startelf optimizer written to {path}: {len(payload["players"])} players.')
    return path
