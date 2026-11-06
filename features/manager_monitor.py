"""Lightweight HA collector: transfers, locked XIs and confirmed settlement."""
from datetime import datetime, timedelta
import json
import os
from pathlib import Path
import time

from features.cash_reconstruction import BERLIN, fetch_manager_transfers, timestamp
from features.history_store import HistoryStore, history_lock
from features.history_sync import atomic_json, read_json, sync_history
from features.manager_history import audit_managers, settled_matchday_days


def contains_errors(value):
    if isinstance(value, dict):
        return any(contains_errors(item) for item in value.values())
    return bool(value)


class ManagerMonitor:
    def __init__(self, get, league_id, start_date, root, *, token='', repository='', audit=audit_managers):
        self.get, self.league_id, self.start_date = get, str(league_id), start_date
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.history = self.root / 'manager_history.sqlite3'
        self.scope = f'{league_id}:{start_date}'
        self.state_path = self.root / '.manager-monitor-state.json'
        self.state = read_json(self.state_path)
        if self.state.get('scope') != self.scope:
            self.state = {'scope': self.scope}
        self.token, self.repository, self.audit = token, repository, audit

    def log(self, message):
        line = datetime.now(BERLIN).isoformat(timespec='seconds') + ' Manager-Erfassung: ' + message
        print(line, flush=True)
        with (self.root / 'manager-monitor.log').open('a', encoding='utf-8') as handle:
            handle.write(line + '\n')

    def task(self, name, now, interval, callback):
        task = self.state.setdefault('tasks', {}).setdefault(name, {})
        if now.timestamp() < task.get('next_at', 0):
            return
        try:
            details = callback()
        except Exception as error:
            task.update(status='retry', error=type(error).__name__, next_at=now.timestamp() + min(interval, 300))
            self.log(name + ': fehlgeschlagen (' + type(error).__name__ + '), erneuter Versuch folgt.')
        else:
            task.update(status='ok', last_success=now.isoformat(), next_at=now.timestamp() + interval,
                        details=details, error=None)
        atomic_json(self.state_path, self.state)

    def schedule(self):
        payload = self.get('/competitions/1/matchdays')
        if not isinstance(payload.get('it'), list):
            raise ValueError('Spielplan fehlt')
        self.state['matchdays'] = payload['it']
        return {'matchdays': len(payload['it'])}

    def capture_kickoff(self, now):
        due = []
        for day in self.state.get('matchdays', []):
            dates = [timestamp(match['dt']) for match in day.get('it', []) if match.get('dt')]
            if (dates and day.get('day') is not None
                    and timedelta(minutes=3) <= now - min(dates) <= timedelta(minutes=35)
                    and str(day['day']) not in self.state.get('captured_days', [])):
                due.append((day['day'], min(dates)))
        if not due:
            return {'captured': 0}
        managers = self.get(f'/leagues/{self.league_id}/ranking')['us']
        if not managers:
            raise ValueError('Managerliste fehlt')
        captured, failed = 0, []
        with history_lock(self.history):
            store = HistoryStore(self.history)
            try:
                for day, kickoff in due:
                    day_failed = False
                    for manager in managers:
                        mid = str(manager['i'])
                        if store.kickoff_squad(self.scope, mid, day):
                            continue
                        try:
                            squad = self.get(f'/leagues/{self.league_id}/managers/{mid}/squad')
                            if not isinstance(squad.get('it'), list):
                                raise ValueError('Kaderliste fehlt')
                            if squad['it'] and not any(isinstance(player.get('lo'), int) for player in squad['it']):
                                raise ValueError('Aufstellungspositionen fehlen')
                            store.observe(self.scope, 'shared-v1', 'kickoff_squad', f'{mid}:{day}', now,
                                          {'manager': manager['n'], 'day': day,
                                           'kickoff': kickoff.isoformat(), 'squad': squad})
                            captured += 1
                        except Exception:
                            failed.append(mid)
                            day_failed = True
                    if not day_failed:
                        self.state.setdefault('captured_days', []).append(str(day))
            finally:
                store.close()
        if captured:
            self.state['dirty'] = True
            self.log(f'{captured} fixierte Spieltagskader gespeichert.')
        if failed:
            raise RuntimeError('Einzelne Kader fehlen')
        return {'captured': captured}

    def transfers(self, now):
        managers = self.get(f'/leagues/{self.league_id}/ranking')['us']
        if not managers:
            raise ValueError('Managerliste fehlt')
        added, failures = 0, []
        # Fetch outside the lock; report jobs may keep running in parallel.
        for manager in managers:
            mid = str(manager['i'])
            try:
                trades = fetch_manager_transfers(self.get, self.league_id, mid, self.start_date)
                with history_lock(self.history):
                    store = HistoryStore(self.history)
                    try:
                        before = store.db.total_changes
                        for trade in trades:
                            store.transfer(self.scope, mid, now, trade)
                        added += store.db.total_changes - before
                    finally:
                        store.close()
            except Exception:
                failures.append(mid)
        if added:
            self.state['dirty'] = True
            self.log(f'{added} neue Transferbeobachtungen gespeichert.')
        if failures:
            raise RuntimeError('Einzelne Transferhistorien fehlen')
        return {'new_transfers': added, 'managers': len(managers)}

    def settlement(self, now):
        feed = self.get(f'/leagues/{self.league_id}/activitiesFeed?max=5000')
        if not isinstance(feed.get('af'), list):
            raise ValueError('Aktivitätenfeed fehlt')
        days = settled_matchday_days(feed, self.start_date)
        self.state['settled_seen'] = sorted(set(self.state.get('settled_seen', [])) | days)
        # Archive account evidence even when the later budget audit fails.
        with history_lock(self.history):
            store = HistoryStore(self.history)
            try:
                for event in feed['af']:
                    if str(event.get('t')) != '26' or not event.get('i') or not event.get('dt'):
                        continue
                    if timestamp(event['dt']) < timestamp(self.start_date):
                        continue
                    key = 'observed:' + str(event['i'])
                    store.db.execute('INSERT OR IGNORE INTO observations VALUES (?,?,?,?,?,?)', (
                        self.scope, 'shared-v1', 'account_achievement', key, now.isoformat(),
                        json.dumps({'key': key, 'manager': 'account', 'kind': 'API-Erfolg',
                                                 'status': 'belegt', 'raw': event, 'included_in_cash': False})))
            finally:
                store.close()
        return {'settled_days': sorted(days)}

    def reconcile(self, now):
        frame = self.audit(self.get, self.league_id, self.start_date, history_path=self.history,
                           now=now, output_dir=self.root / 'manager-history-output')
        summary = frame.attrs['manager_audit']
        if contains_errors(summary.get('errors', {})):
            raise RuntimeError('Budgetauswertung enthält Abruffehler')
        managers = {row['name'] for row in summary.get('manager_budgets', [])}
        if not managers:
            raise ValueError('Managerbudgets fehlen')
        processed = set(self.state.get('settled_processed', []))
        for day in self.state.get('settled_seen', []):
            covered = {event['manager'] for event in summary.get('events', [])
                       if event.get('day') == day and event.get('kind') == 'Spieltagspunkte'}
            if managers and managers.issubset(covered):
                processed.add(day)
        pending = set(self.state.get('settled_seen', [])) - processed
        self.state['settled_processed'] = sorted(processed)
        if pending:
            raise RuntimeError('Finale Spieltagsdaten noch unvollständig')
        self.state['dirty'] = False
        self.log('Managerbudgets und Erfolgsprotokoll aktualisiert.')
        return {'settled_days': sorted(processed), 'managers': len(managers)}

    def synchronize(self, now):
        result = sync_history(self.token, self.repository, self.root, self.scope, now)
        if result.get('imported'):
            self.state['dirty'] = True
        return result

    def tick(self, now):
        # Each task persists independently: a GitHub/network failure cannot stop kickoff capture.
        self.task('schedule', now, 3600, self.schedule)
        self.task('kickoff', now, 60, lambda: self.capture_kickoff(now))
        self.task('transfers', now, 1800, lambda: self.transfers(now))
        self.task('settlement', now, 600, lambda: self.settlement(now))
        self.task('sync', now, 300, lambda: self.synchronize(now))
        pending = set(self.state.get('settled_seen', [])) - set(self.state.get('settled_processed', []))
        task = self.state.get('tasks', {}).get('audit', {})
        last = timestamp(task['last_success']).timestamp() if task.get('last_success') else 0
        if task.get('status') != 'retry' and (self.state.get('dirty') or pending):
            task['next_at'] = min(task.get('next_at', 0), last + 600)
        self.task('audit', now, 21600, lambda: self.reconcile(now))


def main():
    from features.advisor_live import LiveKickbase
    root = Path(os.getenv('KICKBASE_DATA_DIR', '/data'))
    root.mkdir(parents=True, exist_ok=True)
    monitor = None
    while True:
        try:
            if monitor is None:
                client = LiveKickbase(os.environ['KICK_USER'], os.environ['KICK_PASS'])
                def get(path):
                    import requests
                    time.sleep(.15)
                    try:
                        return client.get(path)
                    except requests.HTTPError as error:
                        if error.response is None or error.response.status_code != 401:
                            raise
                        return client.get(path)  # LiveKickbase cleared the expired token.
                league_name = os.getenv('KICK_LEAGUE_NAME', '')
                leagues = [league for league in get('/leagues/selection').get('it', [])
                           if league.get('n') == league_name]
                if len(leagues) != 1:
                    raise ValueError('Liga nicht eindeutig gefunden')
                monitor = ManagerMonitor(get, leagues[0]['i'], os.getenv('KICK_LEAGUE_START_DATE', '2026-08-15'),
                                         root, token=os.getenv('GITHUB_FORECAST_TOKEN', ''),
                                         repository=os.getenv('GITHUB_FORECAST_REPOSITORY', 'bastiwe/Kickbase-Kane'))
                monitor.log('Hintergrunddienst gestartet; Transfers 30 Min., Abschlussprüfung 10 Min., Startelfprüfung 1 Min.')
            monitor.tick(datetime.now(BERLIN))
        except Exception as error:
            print('Manager-Erfassung: Dienstversuch fehlgeschlagen (' + type(error).__name__ + ').', flush=True)
        time.sleep(30)


if __name__ == '__main__':
    main()
