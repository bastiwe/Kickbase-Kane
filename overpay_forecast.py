"""On-demand opponent analysis using cached data, without model training."""

import argparse
from datetime import datetime
import os
from pathlib import Path
import webbrowser
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
from dotenv import load_dotenv

from features.budgets import calc_manager_budgets
from features.overpay_tool import write_overpay_tool
from features.predictions.predictions import (
    add_player_quality_signals, enrich_market_decisions_with_context,
    join_current_market, join_current_squad,
)
from features.predictions.snapshot import read_prediction_snapshot, market_cycle
from kickbase_api.league import get_league_id
from kickbase_api.config import BASE_URL, get_json_with_token, get_cdn_url
from kickbase_api.user import login, get_user_id
from startelf_optimizer import load_cached_players


def cached_predictions(history, latest, snapshot, season_start, now=None):
    """Use only forecasts from the current market cycle; never fabricate targets."""
    if latest.empty:
        raise RuntimeError('Spielerdaten fehlen. Zuerst Spaet oder Fast 1T ausfuehren; lokal player_data_total.db bereitstellen.')
    history, latest = history.copy(), latest.copy()
    history['player_id'] = pd.to_numeric(history['player_id'], errors='raise')
    latest['player_id'] = pd.to_numeric(latest['player_id'], errors='raise')
    result = add_player_quality_signals(latest, history, season_start)
    values = history.sort_values('date').drop_duplicates(['player_id', 'date']).copy()
    values['mv_change_1d'] = values.groupby('player_id')['mv'].diff()
    changes = values.drop_duplicates('player_id', keep='last').set_index('player_id')['mv_change_1d']
    result['mv_change_1d'] = result['player_id'].map(changes)
    cycle = market_cycle(now or datetime.now(ZoneInfo('Europe/Berlin')))
    for days, column in [(1, 'predicted_mv_target'), (3, 'predicted_mv_target_3d'), (7, 'predicted_mv_target_7d')]:
        entry = (snapshot or {}) if days == 1 else (snapshot or {}).get('multiDay', {}).get(str(days), {})
        try:
            forecasts = entry['predictions'] if market_cycle(entry['generatedAt']) == cycle else {}
        except (KeyError, ValueError, TypeError):
            forecasts = {}
        result[column] = result['player_id'].map(lambda value: forecasts.get(str(int(value)), np.nan))
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--open', action='store_true', help='HTML nach Erstellung im Browser oeffnen')
    args = parser.parse_args()
    load_dotenv()
    username, password = os.getenv('KICK_USER'), os.getenv('KICK_PASS')
    if not username or not password:
        raise RuntimeError('KICK_USER und KICK_PASS fehlen in .env bzw. GitHub Secrets.')
    history, latest, note = load_cached_players()
    print(note)
    season_start = os.getenv('KICK_LEAGUE_START_DATE', '2026-08-15')
    predictions = cached_predictions(history, latest, read_prediction_snapshot(), season_start)
    token = login(username, password)
    league_id = get_league_id(token, os.getenv('KICK_LEAGUE_NAME', 'Die Spätzünder'))
    user_id = get_user_id(token)
    predictions = refresh_market_players(token, league_id, predictions)
    budgets = calc_manager_budgets(token, league_id, season_start,
                                   int(os.getenv('KICK_START_BUDGET', '80000000')))
    # The legacy bid heuristics need numeric targets. Missing targets supply no
    # speculative upside; their display and value-based bid limits remain unknown.
    targets = ['predicted_mv_target', 'predicted_mv_target_3d', 'predicted_mv_target_7d']
    numeric = predictions.copy()
    numeric[targets] = numeric[targets].fillna(0)
    market = join_current_market(token, league_id, numeric, user_id, include_player_id=True)
    squad = join_current_squad(token, league_id, numeric, user_id, season_start)
    market = enrich_market_decisions_with_context(market, squad, budgets, keep_all=True)
    availability = predictions.set_index('player_id')['predicted_mv_target'].notna()
    for index, row in market.iterrows():
        if not availability.get(row['player_id'], False):
            market.loc[index, ['predicted_mv_target', 'max_bid', 'bid_gap']] = np.nan
    path = write_overpay_tool(market, budgets)
    print('Keine Modelle trainiert, keine Mail versendet. Fehlende/veraltete Prognosen erscheinen als unbekannt.')
    if args.open:
        webbrowser.open(Path(path).resolve().as_uri())


def refresh_market_players(token, league_id, predictions):
    """Use current market values and include players absent from the cache."""
    result = predictions.set_index('player_id').copy()
    payload = get_json_with_token(f'{BASE_URL}/leagues/{league_id}/market', token)
    for player in payload.get('it', []):
        try:
            player_id = int(player['i'])
        except (KeyError, TypeError, ValueError):
            continue
        if player_id not in result.index:
            result.loc[player_id] = np.nan
        for source, target in [('mv', 'mv'), ('fn', 'first_name'), ('ln', 'last_name'),
                               ('tn', 'team_name'), ('pos', 'position')]:
            if player.get(source) is not None:
                result.loc[player_id, target] = player[source]
        if pd.isna(result.loc[player_id].get('last_name')) and player.get('n'):
            result.loc[player_id, 'last_name'] = player['n']
        if player.get('pim'):
            result.loc[player_id, 'image_url'] = get_cdn_url(player['pim'])
    for column in ['first_name', 'last_name', 'team_name', 'image_url', 'top_player_tag']:
        if column not in result:
            result[column] = ''
        result[column] = result[column].fillna('')
    result.index.name = 'player_id'
    return result.reset_index()


if __name__ == '__main__':
    main()
