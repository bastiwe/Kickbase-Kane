"""Merge immutable league evidence between HA and cumulative Actions artifacts."""
from base64 import b64decode, b64encode
from contextlib import closing
from datetime import datetime
import gzip
import hashlib
from io import BytesIO
import json
from pathlib import Path
import sqlite3
import tempfile
from zipfile import ZipFile

import requests

from features.history_store import HistoryStore, history_lock

SHARED_KINDS = {'transfer', 'kickoff_squad', 'account_achievement'}
MAX_INPUT = 48_000


def atomic_json(path, payload):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=path.parent,
                                     suffix='.tmp', delete=False) as handle:
        temporary = Path(handle.name)
        json.dump(payload, handle, ensure_ascii=False)
    try:
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def read_json(path):
    try:
        value = json.loads(Path(path).read_text(encoding='utf-8'))
        return value if isinstance(value, dict) else {}
    except (OSError, ValueError):
        return {}


def digest(record):
    # Observation time/run may differ when both systems saw the same evidence.
    content = [record['scope'], record['kind'], record['subject'], record['payload']]
    return hashlib.sha256(json.dumps(content, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def evidence(database, scope):
    records = []
    for row in database.execute('SELECT scope,run,kind,subject,observed_at,payload FROM observations WHERE scope=?', (scope,)):
        if row[2] in SHARED_KINDS:
            records.append(dict(zip(('scope', 'run', 'kind', 'subject', 'observed_at', 'payload'), row)))
    for (payload,) in database.execute("SELECT payload FROM events WHERE scope=? AND status='belegt'", (scope,)):
        event = json.loads(payload)
        records.append(dict(scope=scope, run='shared-v1', kind='account_achievement',
                            subject=event['key'], observed_at=event.get('raw', {}).get('dt') or '1970-01-01T00:00:00Z',
                            payload=payload))
    for record in records:
        record['payload'] = json.loads(record['payload'])
        # Different collectors may record different evidence for the same subject.
        # Use content keys on exchange so neither version can suppress the other.
        record['run'] = 'shared-' + digest(record)
    return list({digest(record): record for record in records}.values())


def encode(records):
    raw = json.dumps({'version': 1, 'records': records}, separators=(',', ':')).encode()
    return b64encode(gzip.compress(raw, mtime=0)).decode('ascii')


def import_payload(encoded, history_path, scope=None):
    if len(encoded) > MAX_INPUT:
        raise ValueError('Historienpaket zu groß')
    # Limit decompression, too; dispatched input is external data.
    with gzip.GzipFile(fileobj=BytesIO(b64decode(encoded, validate=True))) as zipped:
        raw = zipped.read(4_000_001)
    if len(raw) > 4_000_000:
        raise ValueError('Entpacktes Historienpaket zu groß')
    payload = json.loads(raw)
    if payload.get('version') != 1 or not isinstance(payload.get('records'), list):
        raise ValueError('Ungültiges Historienpaket')
    records = payload['records']
    for record in records:
        if (record.get('kind') not in SHARED_KINDS
                or not all(isinstance(record.get(k), str) and record[k] for k in ('scope', 'run', 'subject', 'observed_at'))
                or (scope is not None and record['scope'] != scope)):
            raise ValueError('Ungültige Historienbeobachtung')
        datetime.fromisoformat(record['observed_at'].replace('Z', '+00:00'))
    with history_lock(history_path):
        store = HistoryStore(history_path)
        try:
            for record in records:
                store.db.execute('INSERT OR IGNORE INTO observations VALUES (?,?,?,?,?,?)', (
                    record['scope'], record['run'], record['kind'], record['subject'],
                    record['observed_at'], json.dumps(record['payload'], ensure_ascii=False)))
                if record['kind'] == 'account_achievement':
                    event = record['payload']
                    if event.get('kind') == 'API-Erfolg' and event.get('status') == 'belegt':
                        store.db.execute('INSERT OR IGNORE INTO events VALUES (?,?,?,?,?,?,?,?,?)', (
                            record['scope'], event['key'], event['manager'], event['kind'], 'belegt',
                            None, None, json.dumps(event, ensure_ascii=False), record['observed_at']))
        except BaseException:
            store.db.rollback()
            raise
        finally:
            store.close()
    return len(records)


def merge_history(source, destination, scope):
    """Union observations, never overwrite an active database or sum derived events."""
    with closing(sqlite3.connect(source)) as incoming:
        if incoming.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
            raise ValueError('Beschädigtes Historienarchiv')
        records = evidence(incoming, scope)
        with history_lock(destination):
            local = HistoryStore(destination)
            try:
                before = local.db.total_changes
                for row in incoming.execute('SELECT * FROM observations WHERE scope=?', (scope,)):
                    local.db.execute('INSERT OR IGNORE INTO observations VALUES (?,?,?,?,?,?)', row)
                # Proven account events are evidence. Other events are recalculated locally.
                for row in incoming.execute("SELECT * FROM events WHERE scope=? AND status='belegt'", (scope,)):
                    local.db.execute('INSERT OR IGNORE INTO events VALUES (?,?,?,?,?,?,?,?,?)', row)
                changed = local.db.total_changes - before
            except BaseException:
                local.db.rollback()
                raise
            finally:
                local.close()
    return changed, {digest(record) for record in records}


def sync_history(token, repository, root, scope, now):
    """A dispatch is pending until its evidence is seen in a downloaded artifact."""
    from features.github_forecast_sync import _headers, _latest_artifact, dispatch_workflow
    if not token or token == 'null':
        return {'status': 'local', 'imported': 0}
    import re
    if not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', repository or ''):
        raise ValueError('Ungültiges GitHub-Repository')
    root = Path(root)
    history = root / 'manager_history.sqlite3'
    state_path = root / '.manager-history-sync.json'
    state = read_json(state_path)
    if state.get('scope') != scope:
        state = {'scope': scope}
    known = set(state.get('acknowledged', []))
    imported = 0
    artifact = _latest_artifact(_headers(token), repository, 'manager-history')
    if artifact and state.get('artifact_id') != artifact['id']:
        response = requests.get(artifact['archive_download_url'], headers=_headers(token), timeout=(5, 60))
        response.raise_for_status()
        with ZipFile(BytesIO(response.content)) as zipped:
            if zipped.namelist() != ['manager_history.sqlite3']:
                raise ValueError('Ungültiges Historienarchiv')
            with tempfile.TemporaryDirectory(dir=root) as folder:
                source = Path(folder) / 'history.sqlite3'
                source.write_bytes(zipped.read('manager_history.sqlite3'))
                imported, received = merge_history(source, history, scope)
                known.update(received)
        state['artifact_id'] = artifact['id']
    state['acknowledged'] = sorted(known)
    pending = state.get('pending')
    if pending and set(pending['digests']).issubset(known):
        state.pop('pending', None)
        pending = None
    if not pending and history.exists():
        with closing(sqlite3.connect(history)) as db:
            candidates = evidence(db, scope)
        batch, hashes = [], set()
        for record in candidates:
            key = digest(record)
            if key in known or key in hashes:
                continue
            if len(encode(batch + [record])) > MAX_INPUT:
                if not batch:
                    raise ValueError('Einzelne Historienbeobachtung zu groß')
                break
            batch.append(record)
            hashes.add(key)
        if batch:
            pending = {'payload': encode(batch), 'digests': sorted(hashes)}
            state['pending'] = pending
    # Save before sending: network timeouts may mean the dispatch was accepted.
    atomic_json(state_path, state)
    if pending and now.timestamp() - pending.get('sent_at', 0) >= 1800:
        dispatch_workflow(token, repository, 'manager_history.yml', inputs={'history_payload': pending['payload']})
        pending['sent_at'] = now.timestamp()
        atomic_json(state_path, state)
    return {'status': 'pending' if pending else 'current', 'imported': imported,
            'unacknowledged': len(pending['digests']) if pending else 0}
