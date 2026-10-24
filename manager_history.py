"""Capture league snapshots or build a budget audit without sending mail."""
import argparse
from datetime import datetime, timedelta
import os

from dotenv import load_dotenv

from features.advisor_live import LiveKickbase
from features.cash_reconstruction import BERLIN, timestamp
from features.manager_history import audit_managers


def kickoff_due(payload, now, window=timedelta(minutes=35)):
    for day in payload.get('it', []):
        dates = [timestamp(m['dt']) for m in day.get('it', []) if m.get('dt')]
        if dates and timedelta(minutes=3) <= now - min(dates) <= window:
            return True
    return False


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--capture-only', action='store_true')
    parser.add_argument('--after-kickoff-only', action='store_true')
    args = parser.parse_args()
    load_dotenv()
    now = datetime.now(BERLIN)
    client = LiveKickbase(os.environ['KICK_USER'], os.environ['KICK_PASS'])
    if args.after_kickoff_only and not kickoff_due(client.get('/competitions/1/matchdays'), now):
        print('Kein Spieltagsbeginn vor 3 bis 35 Minuten; kein Kaderabruf.')
        return
    if os.getenv('GITHUB_OUTPUT'):
        with open(os.environ['GITHUB_OUTPUT'], 'a', encoding='utf-8') as output:
            output.write('capture_due=true\n')
    league_id = os.getenv('REPORT_LEAGUE_ID')
    if not league_id:
        name = os.getenv('KICK_LEAGUE_NAME') or 'Die Spätzünder'
        matches = [x for x in client.get('/leagues/selection')['it'] if x.get('n') == name]
        if len(matches) != 1:
            raise ValueError('Liga nicht eindeutig gefunden')
        league_id = matches[0]['i']
    result = audit_managers(client.get, league_id, os.getenv('LEAGUE_START_DATE', '2026-08-15'),
                            history_path=os.getenv('MANAGER_HISTORY_PATH', 'manager_history.sqlite3'),
                            capture_only=args.capture_only, now=now)
    if args.capture_only:
        print(result)
        if result['errors']:
            raise RuntimeError('Kader-Snapshot unvollständig; erfolgreiche Einzelabrufe wurden archiviert')
    else:
        print(result.to_string(index=False))
        print('Audit gespeichert. Keine Mail versendet.')


if __name__ == '__main__':
    main()
