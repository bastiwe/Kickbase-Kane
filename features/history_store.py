"""Shared SQLite observations and a process lock for HA and report jobs."""
from contextlib import contextmanager
from datetime import datetime
import json
import hashlib
import os
from pathlib import Path
import sqlite3
from zoneinfo import ZoneInfo


def timestamp(value):
    result = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
    return result.replace(tzinfo=ZoneInfo('Europe/Berlin')) if result.tzinfo is None else result


@contextmanager
def history_lock(path):
    """Fail fast if another process is auditing/merging this history."""
    path = Path(str(path) + '.lock')
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('a+b') as handle:
        handle.seek(0, 2)
        if handle.tell() == 0:
            handle.write(b'0')
            handle.flush()
        handle.seek(0)
        if os.name == 'nt':
            import msvcrt
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        try:
            yield
        finally:
            handle.seek(0)
            if os.name == 'nt':
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(handle, fcntl.LOCK_UN)


class HistoryStore:
    def __init__(self, path):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path, timeout=60)
        self.db.executescript('''
            CREATE TABLE IF NOT EXISTS observations (
                scope TEXT, run TEXT, kind TEXT, subject TEXT, observed_at TEXT,
                payload TEXT, PRIMARY KEY(scope,run,kind,subject));
            CREATE TABLE IF NOT EXISTS events (
                scope TEXT, event_key TEXT, manager TEXT, kind TEXT, status TEXT,
                amount REAL, amount_max REAL, payload TEXT, updated_at TEXT,
                PRIMARY KEY(scope,event_key));
            CREATE TABLE IF NOT EXISTS cache (
                scope TEXT, cache_key TEXT, observed_at TEXT, payload TEXT,
                PRIMARY KEY(scope,cache_key));
        ''')

    def observe(self, scope, run, kind, subject, now, payload):
        self.db.execute('INSERT OR REPLACE INTO observations VALUES (?,?,?,?,?,?)',
                        (scope, run, kind, str(subject), now.isoformat(), json.dumps(payload, ensure_ascii=False)))

    def transfer(self, scope, manager, now, payload):
        key = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
        self.db.execute('INSERT OR IGNORE INTO observations VALUES (?,?,?,?,?,?)',
                        (scope, 'shared-v1', 'transfer', str(manager) + ':' + key,
                         now.isoformat(), json.dumps(payload, ensure_ascii=False)))

    def cached(self, scope, key, now, max_age):
        row = self.db.execute('SELECT observed_at,payload FROM cache WHERE scope=? AND cache_key=?',
                              (scope, key)).fetchone()
        if row and now - timestamp(row[0]) < max_age:
            return json.loads(row[1])
        return None

    def cache(self, scope, key, now, payload):
        self.db.execute('INSERT OR REPLACE INTO cache VALUES (?,?,?,?)',
                        (scope, key, now.isoformat(), json.dumps(payload, ensure_ascii=False)))

    def replace_events(self, scope, events, now):
        keys = [event['key'] for event in events]
        duplicates = sorted({key for key in keys if keys.count(key) > 1})
        if duplicates:
            raise ValueError('Doppelte Ereignisschlüssel: ' + ', '.join(duplicates))
        self.db.execute('DELETE FROM events WHERE scope=?', (scope,))
        for event in events:
            self.db.execute('INSERT INTO events VALUES (?,?,?,?,?,?,?,?,?)',
                            (scope, event['key'], event['manager'], event['kind'], event['status'],
                             event.get('amount'), event.get('amount_max'),
                             json.dumps(event, ensure_ascii=False), now.isoformat()))

    def kickoff_squad(self, scope, manager_id, day):
        row = self.db.execute(
            """SELECT payload FROM observations
               WHERE scope=? AND kind='kickoff_squad' AND subject=?
               ORDER BY observed_at ASC LIMIT 1""",
            (scope, f'{manager_id}:{day}')).fetchone()
        return json.loads(row[0]) if row else None

    def close(self):
        self.db.commit()
        self.db.close()

