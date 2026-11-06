from datetime import datetime
from contextlib import closing
from io import BytesIO
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import Mock, patch
from zipfile import ZipFile

from features.cash_reconstruction import BERLIN
from features.history_store import HistoryStore, history_lock
from features.history_sync import digest, encode, evidence, import_payload, merge_history, read_json, sync_history
from features.github_forecast_sync import sync_latest_manager_audit


class HistorySyncTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.now = datetime(2026, 11, 6, 21, 0, tzinfo=BERLIN)
        self.scope = 'l:2026-08-15'

    def seed(self, path, subject='1:10'):
        store = HistoryStore(path)
        store.observe(self.scope, 'shared-v1', 'kickoff_squad', subject, self.now,
                      {'squad': {'it': [{'pi': 'p1', 'lo': 0}]}})
        store.transfer(self.scope, '1', self.now, {'pi': 'p1', 'tty': 1, 'trp': 1000, 'dt': self.now.isoformat()})
        store.close()

    def records(self, path):
        with closing(sqlite3.connect(path)) as db:
            return evidence(db, self.scope)

    def test_payload_and_archive_merge_are_idempotent_and_preserve_both_sides(self):
        local, remote = self.root / 'local.db', self.root / 'remote.db'
        self.seed(local, 'local:10')
        self.seed(remote, 'remote:10')
        records = self.records(local)
        for _ in range(2):
            import_payload(encode(records), remote, self.scope)
            merge_history(remote, local, self.scope)
        self.assertEqual(len(self.records(local)), 3)
        self.assertEqual(len(self.records(remote)), 3)
        self.assertEqual({digest(r) for r in self.records(local)}, {digest(r) for r in self.records(remote)})

    def test_dispatch_is_not_acknowledgement_until_published_artifact_contains_records(self):
        local, remote = self.root / 'manager_history.sqlite3', self.root / 'remote.db'
        self.seed(local)
        with patch('features.github_forecast_sync._latest_artifact', return_value=None), \
                patch('features.github_forecast_sync.dispatch_workflow') as dispatch:
            self.assertEqual(sync_history('token', 'o/r', self.root, self.scope, self.now)['status'], 'pending')
            sync_history('token', 'o/r', self.root, self.scope, self.now)
            dispatch.assert_called_once()
            packet = dispatch.call_args.kwargs['inputs']['history_payload']
        self.assertEqual(read_json(self.root / '.manager-history-sync.json')['acknowledged'], [])
        import_payload(packet, remote, self.scope)
        archive = BytesIO()
        with ZipFile(archive, 'w') as zipped:
            zipped.writestr('manager_history.sqlite3', remote.read_bytes())
        response = Mock(content=archive.getvalue())
        artifact = {'id': 42, 'archive_download_url': 'https://artifact'}
        with patch('features.github_forecast_sync._latest_artifact', return_value=artifact), \
                patch('features.history_sync.requests.get', return_value=response), \
                patch('features.github_forecast_sync.dispatch_workflow') as dispatch:
            result = sync_history('token', 'o/r', self.root, self.scope, self.now)
        self.assertEqual(result['status'], 'current')
        dispatch.assert_not_called()
        self.assertEqual(len(read_json(self.root / '.manager-history-sync.json')['acknowledged']), 2)

    def test_dispatch_error_keeps_packet_for_retry(self):
        self.seed(self.root / 'manager_history.sqlite3')
        with patch('features.github_forecast_sync._latest_artifact', return_value=None), \
                patch('features.github_forecast_sync.dispatch_workflow', side_effect=RuntimeError):
            with self.assertRaises(RuntimeError):
                sync_history('token', 'o/r', self.root, self.scope, self.now)
        pending = read_json(self.root / '.manager-history-sync.json')['pending']
        self.assertNotIn('sent_at', pending)
        self.assertTrue(pending['digests'])

    def test_conflicting_observations_keep_both_versions_and_can_be_acknowledged(self):
        local, remote = self.root / 'local.db', self.root / 'remote.db'
        self.seed(local)
        self.seed(remote)
        store = HistoryStore(remote)
        store.db.execute("UPDATE observations SET payload=? WHERE kind='kickoff_squad'",
                         (json.dumps({'squad': {'it': [{'pi': 'different', 'lo': 0}]}}),))
        store.close()
        packet = encode(self.records(local) + self.records(remote))
        import_payload(packet, remote, self.scope)
        self.assertEqual(len(self.records(remote)), 3)
        self.assertTrue({digest(r) for r in self.records(local)}.issubset({digest(r) for r in self.records(remote)}))

    def test_unexpected_scope_rejected_and_writer_lock_excludes_other_processes(self):
        source = self.root / 'source.db'
        self.seed(source)
        target = self.root / 'target.db'
        with self.assertRaises(ValueError):
            import_payload(encode(self.records(source)), target, 'other:2026-08-15')
        with history_lock(target), self.assertRaises(OSError):
            with history_lock(target):
                pass

    def test_older_remote_summary_does_not_replace_newer_ha_audit(self):
        target = self.root / 'manager-history-output/latest.json'
        target.parent.mkdir()
        target.write_text(json.dumps({'generated_at': '2026-11-06T12:00:00Z', 'manager_budgets': [{'name': 'local'}]}))
        archive = BytesIO()
        with ZipFile(archive, 'w') as zipped:
            zipped.writestr('latest.json', json.dumps({'generated_at': '2026-11-06T11:00:00Z', 'manager_budgets': []}))
        artifact = {'id': 1, 'updated_at': '2026-11-06T14:00:00Z', 'archive_download_url': 'https://artifact'}
        with patch('features.github_forecast_sync._latest_artifact', return_value=artifact), \
                patch('features.github_forecast_sync.requests.get', return_value=Mock(content=archive.getvalue())):
            result = sync_latest_manager_audit('token', 'o/r', self.root)
        self.assertEqual(result['status'], 'current')
        self.assertEqual(json.loads(target.read_text())['manager_budgets'][0]['name'], 'local')

    def test_dispatch_packets_are_bounded_and_remaining_records_are_not_dropped(self):
        history = self.root / 'manager_history.sqlite3'
        store = HistoryStore(history)
        for index in range(20):
            store.transfer(self.scope, '1', self.now, {'pi': str(index), 'tty': 1, 'trp': index,
                                                      'dt': self.now.isoformat()})
        store.close()
        with patch('features.history_sync.MAX_INPUT', 900), \
                patch('features.github_forecast_sync._latest_artifact', return_value=None), \
                patch('features.github_forecast_sync.dispatch_workflow') as dispatch:
            sync_history('token', 'o/r', self.root, self.scope, self.now)
        packet = dispatch.call_args.kwargs['inputs']['history_payload']
        state = read_json(self.root / '.manager-history-sync.json')
        self.assertLessEqual(len(packet), 900)
        self.assertGreater(len(state['pending']['digests']), 0)
        self.assertLess(len(state['pending']['digests']), 20)
        self.assertEqual(len(self.records(history)), 20)


if __name__ == '__main__':
    unittest.main()
