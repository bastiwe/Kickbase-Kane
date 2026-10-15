import ast
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import pandas as pd

import daily_predictions_fast as fast
import s11_strategy_report as standalone
from features.fast_notifier import send_fast_mail


ROOT = Path(__file__).resolve().parents[1]


class StandaloneStrategyTests(unittest.TestCase):
    def test_standalone_uses_shared_data_and_only_sends_its_own_mail(self):
        market, squad = pd.DataFrame(), pd.DataFrame()
        data = dict(token='test-token', league_id='league', user_id='user',
                    market_df=market, squad_df=squad, predictions_df=pd.DataFrame(),
                    history_df=pd.DataFrame(), forecast_snapshot={})
        with patch.object(standalone, 'generate_fast_report_data', return_value=data), \
                patch.object(standalone, 'enrich_reports_with_ligainsider_signals', return_value=(market, squad)), \
                patch.object(standalone, 'build_lineup_payload', return_value={'budget': 0}) as builder, \
                patch.object(standalone, 'build_strategy_report', return_value={'test': True}), \
                patch.object(standalone, 'write_strategy_report', return_value=Path('report.html')), \
                patch.object(standalone, 'send_strategy_mail') as send, \
                patch.object(fast, 'send_fast_mail') as fast_send:
            standalone.main([])
            builder.assert_called_once()
            send.assert_called_once_with({'test': True}, Path('report.html'))
            fast_send.assert_not_called()
            standalone.main(['--no-email'])
            self.assertEqual(send.call_count, 1)

    def test_fast_report_sends_original_mail_without_strategy_generation(self):
        frame = pd.DataFrame([dict(predicted_mv_target=100_000)])
        with patch.object(fast, 'generate_fast_report_data', return_value=dict(market_df=frame, squad_df=frame)), \
                patch.object(fast, 'display'), patch.object(fast, 'send_fast_mail') as send:
            fast.main()
            self.assertEqual(len(send.call_args.args), 3)
            self.assertEqual(send.call_args.kwargs, {})

    def test_existing_pipelines_have_no_strategy_import_or_invocation(self):
        for file in ('daily_predictions_fast.py', 'daily_predictions_spaet.py'):
            tree = ast.parse((ROOT / file).read_text(encoding='utf-8'))
            self.assertFalse(any(isinstance(node, ast.ImportFrom) and node.module == 'features.strategy_report'
                                 for node in ast.walk(tree)))
            calls = {node.func.id for node in ast.walk(tree)
                     if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)}
            self.assertTrue(calls.isdisjoint({'build_strategy_report', 'write_strategy_report'}))
        for file in ('actions_fast.yml', 'actions_spaet.yml'):
            self.assertNotIn('s11_strategy_report', (ROOT / '.github/workflows' / file).read_text(encoding='utf-8'))

    def test_fast_mail_does_not_contain_s11_report(self):
        with patch.dict('os.environ', EMAIL_USER='test@example.com', EMAIL_PASS='test'), \
                patch('features.fast_notifier.smtplib.SMTP_SSL') as smtp:
            send_fast_mail(pd.DataFrame(), pd.DataFrame(), 'test@example.com')
            message = smtp.return_value.__enter__.return_value.send_message.call_args.args[0]
        self.assertNotIn('S11-Strategie', message.get_body(preferencelist=('html',)).get_content())

    def test_missing_email_configuration_preserves_artifact_only_mode(self):
        with patch.dict('os.environ', {}, clear=True), patch.object(standalone, 'deliver_report_message') as send:
            self.assertFalse(standalone.send_strategy_mail({}, Path('unused')))
            send.assert_not_called()

    def test_standalone_email_has_own_subject_and_attachment(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 's11_strategy_report.html'
            path.write_text('<p>Standalone S11</p>', encoding='utf-8')
            with patch.dict('os.environ', EMAIL_USER='test@example.com', EMAIL_PASS='test'), \
                    patch.object(standalone, 'strategy_html', return_value='<h2>S11</h2>'), \
                    patch.object(standalone, 'deliver_report_message') as send:
                self.assertTrue(standalone.send_strategy_mail({}, path))
        message = send.call_args.args[0]
        self.assertIn('eigenständiger Report', message['Subject'])
        self.assertEqual(message['To'], 'test@example.com')
        self.assertEqual([part.get_filename() for part in message.iter_attachments()], ['s11_strategy_report.html'])


if __name__ == '__main__':
    unittest.main()
