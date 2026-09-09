"""Refresh the lineup planner without market predictions or model training."""

from email.message import EmailMessage
from contextlib import closing
import os
from pathlib import Path
import smtplib
import sqlite3

import pandas as pd
from dotenv import load_dotenv

from features.lineup_optimizer import write_lineup_optimizer
from features.predictions.snapshot import read_prediction_snapshot
from kickbase_api.league import get_league_id
from kickbase_api.user import get_user_id, login


def load_cached_players(path='player_data_total.db', competition_id=1):
    empty = pd.DataFrame(columns=['player_id'])
    db_path = Path(path)
    if not db_path.is_file():
        return empty, empty, 'Kein Cache; Punktdaten werden gezielt nachgeladen.'
    try:
        with closing(sqlite3.connect(db_path.resolve().as_uri() + '?mode=ro', uri=True)) as conn:
            history = pd.read_sql_query('SELECT * FROM player_data_1d', conn)
        required = {'player_id', 'md', 'p', 'team_id', 'team_name', 'date'}
        if not required.issubset(history.columns):
            raise ValueError('Cache schema is incomplete')
        if 'competition_id' in history:
            history = history[pd.to_numeric(history['competition_id'], errors='coerce') == competition_id].copy()
        history = history[history['player_id'].notna()].copy()
        history['player_id'] = history['player_id'].map(lambda value: str(int(value)))
        dates = pd.to_datetime(history['date'], errors='coerce', utc=True)
        history = history.assign(_sort_date=dates).sort_values('_sort_date', na_position='first').drop(columns='_sort_date')
        latest = history.drop_duplicates('player_id', keep='last')
        stamp = dates.max().strftime('%d.%m.%Y') if dates.notna().any() else 'unbekannt'
        note = f'Punktdaten aus Cache (Datenstand {stamp}); fehlende Spieler gezielt nachgeladen.'
        return history, latest, note
    except (sqlite3.Error, pd.errors.DatabaseError, ValueError, TypeError) as exc:
        print(f'Warning: Optimizer cache unavailable: {exc}')
        return empty, empty, 'Cache nicht verwendbar; Punktdaten werden gezielt nachgeladen.'


def send_optimizer_mail(path):
    address, password = os.getenv('EMAIL_USER'), os.getenv('EMAIL_PASS')
    if not address or not password:
        print('Email skipped: EMAIL_USER/EMAIL_PASS missing. Download the GitHub artifact instead.')
        return
    message = EmailMessage()
    message['Subject'] = 'Kickbase Startelf-Optimierer aktualisiert'
    message['From'] = address
    message['To'] = address
    message.set_content(
        'Dein Startelf-Optimierer ist im Anhang. Kader, Gebote und Budget wurden frisch geladen. '
        'Punktdaten stammen aus dem vorhandenen Cache; fehlende Spieler werden gezielt nachgeladen. '
        'Öffne die HTML-Datei im Browser. Sie lässt sich dauerhaft auf deinem PC verwenden. '
        'Es wurden keine Marktwertprognosen oder Modelle berechnet.'
    )
    message.add_attachment(Path(path).read_bytes(), maintype='text', subtype='html', filename=Path(path).name)
    with smtplib.SMTP('smtp.gmail.com', 587, timeout=30) as smtp:
        smtp.starttls()
        smtp.login(address, password)
        smtp.send_message(message)
    print('Startelf optimizer email sent.')


def main():
    load_dotenv()
    username, password = os.getenv('KICK_USER'), os.getenv('KICK_PASS')
    if not username or not password:
        raise RuntimeError('KICK_USER and KICK_PASS are required.')
    token = login(username, password)
    league_id = get_league_id(token, os.getenv('KICK_LEAGUE_NAME', 'Die Spätzünder'))
    user_id = get_user_id(token)
    history, latest, note = load_cached_players()
    print(note)
    path = write_lineup_optimizer(
        token, league_id, user_id, pd.DataFrame(), latest, history_df=history,
        refresh_missing_history=True, history_note=note,
        forecast_snapshot=read_prediction_snapshot(),
    )
    send_optimizer_mail(path)


if __name__ == '__main__':
    main()
