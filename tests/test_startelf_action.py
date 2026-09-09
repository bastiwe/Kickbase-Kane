import os
from contextlib import closing
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

import pandas as pd

from startelf_optimizer import load_cached_players, send_optimizer_mail


class StartelfActionTests(unittest.TestCase):
    def test_missing_cache_does_not_create_database(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'missing.db'
            history, latest, note = load_cached_players(path)
            self.assertTrue(history.empty and latest.empty)
            self.assertFalse(path.exists())
            self.assertIn('Kein Cache', note)

    def test_latest_metadata_is_selected_without_losing_point_history(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'players.db'
            rows = pd.DataFrame([
                dict(player_id=1, date='2026-09-09', md='2026-09-01', p=100, team_id=2, competition_id=1),
                dict(player_id=1, date='2026-09-02', md='2026-09-01', p=100, team_id=1, competition_id=1),
                dict(player_id=2, date='2026-09-09', md='2026-09-01', p=100, team_id=3, competition_id=2),
            ])
            rows['team_name'] = 'Testverein'
            with closing(sqlite3.connect(path)) as connection:
                rows.to_sql('player_data_1d', connection, index=False)
            history, latest, note = load_cached_players(path)
            self.assertEqual(len(history), 2)
            self.assertEqual(latest.iloc[0]['player_id'], '1')
            self.assertEqual(latest.iloc[0]['team_id'], 2)
            self.assertIn('09.09.2026', note)

    @patch('startelf_optimizer.smtplib.SMTP')
    def test_missing_email_secrets_skip_smtp(self, smtp):
        with patch.dict(os.environ, {}, clear=True):
            send_optimizer_mail('unused.html')
        smtp.assert_not_called()

    @patch('startelf_optimizer.smtplib.SMTP')
    def test_html_is_attached_to_email(self, smtp):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'startelf_optimizer.html'
            path.write_text('<html>Test</html>', encoding='utf-8')
            with patch.dict(os.environ, {'EMAIL_USER': 'test@example.com', 'EMAIL_PASS': 'test'}):
                send_optimizer_mail(path)
            message = smtp.return_value.__enter__.return_value.send_message.call_args.args[0]
            attachments = list(message.iter_attachments())
            self.assertEqual(attachments[0].get_filename(), path.name)
            self.assertEqual(attachments[0].get_payload(decode=True), path.read_bytes())


if __name__ == '__main__':
    unittest.main()
