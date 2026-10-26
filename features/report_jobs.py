"""Run the existing reports without blocking the local HTTP server."""
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import uuid
from copy import deepcopy
from features.predictions.snapshot import (
    forecast_metadata,
    multi_day_prediction,
    read_prediction_snapshot,
    project_to_matchday,
)


class ReportJobs:
    def __init__(self, server, app_root, data_root=None):
        self.server = server
        self.app_root = Path(app_root)
        self.data_root = Path(data_root or app_root)
        self.lock = threading.Lock()
        self.status = {'status': 'idle'}

    def read(self):
        with self.lock:
            status = deepcopy(self.status)
        if status.get('status') == 'running':
            status.update(self._progress_from_log(status.get('kind')))
        return status

    def _persist_report(self, report):
        path = getattr(self.server, 'persist_path', None)
        if not path:
            return
        path = Path(path)
        temporary = path.with_suffix('.tmp')
        temporary.write_text(json.dumps(report, allow_nan=False), encoding='utf-8')
        temporary.replace(path)
        self.server.persist_mtime_ns = path.stat().st_mtime_ns

    def _progress_from_log(self, kind):
        """Translate stable report milestones into UI-safe progress information."""
        try:
            log = (self.data_root / '.advisor-report-run.log').read_text(
                encoding='utf-8', errors='replace'
            )
        except OSError:
            return {'progress': 5, 'phase': 'Report wird vorbereitet …'}

        milestones = [
            ('Logged in to Kickbase.', 12, 'Bei Kickbase angemeldet'),
            ('Data reload needed', 22, 'Historische Daten werden aktualisiert'),
            ('Data loaded from database.', 34, 'Markt- und Historiedaten geladen'),
            ('Data preprocessed.', 47, 'Daten für das Modell aufbereitet'),
            ('Model evaluation:', 58, 'Marktwertmodell wird berechnet'),
            ('1T model evaluation:', 66, '1T-Marktwertmodell wird berechnet'),
            ('predicted_mv_target_7d:', 74, 'Mehrtag-Prognosen berechnet'),
            ('=== Market Recommendations ===', 82, 'Transfermarkt wird ausgewertet'),
            ('=== Fast Market 1T Predictions ===', 82, 'Transfermarkt wird ausgewertet'),
            ('=== Squad Recommendations ===', 89, 'Kader wird ausgewertet'),
            ('=== Fast Squad 1T Predictions ===', 89, 'Kader wird ausgewertet'),
        ]
        progress, phase = 8, 'Verbindung und Daten werden vorbereitet'
        for marker, value, message in milestones:
            if marker in log and value >= progress:
                progress, phase = value, message
        if 'Email sent' in log or 'Mail sent' in log:
            progress, phase = 96, 'E-Mail wird versendet'
        elif kind == 'fast' and 'Fast Squad 1T Predictions' in log:
            progress, phase = 94, 'Schnellreport wird abgeschlossen'
        elif kind == 'full' and 'Squad Recommendations' in log:
            progress, phase = 94, 'Vollreport wird abgeschlossen'
        return {'progress': progress, 'phase': phase}

    def start(self, kind):
        scripts = {'full': 'daily_predictions_spaet.py', 'fast': 'daily_predictions_fast.py'}
        if kind not in scripts:
            raise ValueError('Unknown report')
        with self.server.lock:
            client = self.server.kickbase
            report = deepcopy(self.server.report)
        if not client or not report.get('user') or not report.get('league'):
            raise RuntimeError('Zuerst Kickbase verbinden und einen Kader laden.')
        with self.lock:
            if self.status['status'] == 'running':
                raise RuntimeError('Es läuft bereits ein Report.')
            self.status = {
                'status': 'running', 'kind': kind, 'id': uuid.uuid4().hex,
                'progress': 5, 'phase': 'Report wird vorbereitet …',
            }
        env = os.environ.copy()
        env.update(KICK_USER=client.username, KICK_PASS=client.password,
                   REPORT_LEAGUE_ID=str(report['league']), REPORT_USER_ID=str(report['user']),
                   PYTHONIOENCODING='utf-8')
        threading.Thread(target=self.run, args=(scripts[kind], env, report, kind), daemon=True).start()
        return self.read()

    def run(self, script, env, initial, kind):
        try:
            snapshot_path = self.data_root / 'prediction_snapshot_1t.json'
            before = snapshot_path.read_bytes() if snapshot_path.exists() else None
            optimizer_path = self.data_root / 'startelf_optimizer.html'
            previous_optimizer = optimizer_path.stat().st_mtime_ns if optimizer_path.exists() else None
            with (self.data_root / '.advisor-report-run.log').open('w', encoding='utf-8') as log:
                report_env = dict(env, PYTHONPATH=str(self.app_root) + os.pathsep + env.get('PYTHONPATH', ''))
                result = subprocess.run([sys.executable, '-u', str(self.app_root / script)],
                                        cwd=self.data_root, env=report_env, stdout=log, stderr=subprocess.STDOUT,
                                        timeout=3600, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
            log_tail = (self.data_root / '.advisor-report-run.log').read_text(encoding='utf-8', errors='replace')[-1600:]
            if result.returncode:
                if result.returncode < 0:
                    diagnostic = (
                        f'Reportprozess wurde vom System beendet (Signal {-result.returncode}). '
                        'Das deutet meist auf einen Speicherengpass hin. '
                    )
                else:
                    diagnostic = f'Report endete mit Code {result.returncode}. '
                raise RuntimeError(
                    'Report fehlgeschlagen. ' + diagnostic
                    + 'Details im Add-on-Log: ' + log_tail[-700:].replace('\n', ' ')
                )
            if not snapshot_path.exists() or snapshot_path.read_bytes() == before:
                raise RuntimeError('Report lieferte keine neuen Prognosedaten.')
            snapshot = read_prediction_snapshot(snapshot_path)
            if not snapshot:
                raise RuntimeError('Neue Prognosen sind ungültig.')
            generated_by_id = {}
            generated = None
            horizon = initial.get('forecastHorizon')
            generated_fresh = optimizer_path.exists() and optimizer_path.stat().st_mtime_ns != previous_optimizer
            if kind == 'full' and not generated_fresh:
                raise RuntimeError('Report fertig, aber Dashboard-Daten fehlen. Details in .advisor-report-run.log.')
            if generated_fresh:
                from advisor_server import read_report
                generated = read_report(optimizer_path.read_text(encoding='utf-8'))
                if (generated['user'], generated['league']) != (initial['user'], initial['league']):
                    raise RuntimeError('Ergebnis gehört zu einer anderen Liga.')
                generated_by_id = {
                    p['id']: p for p in generated['players'] + generated.get('marketPlayers', [])
                }
                horizon = generated.get('forecastHorizon')
            updates = (horizon or {}).get('updates')
            with self.server.lock:
                report = self.server.report
                if (report['user'], report['league']) != (initial['user'], initial['league']):
                    raise RuntimeError('Liga wurde gewechselt; Ergebnis nicht übernommen.')
                previous_by_id = {
                    p['id']: p for p in report['players'] + report.get('marketPlayers', [])
                }
                # A generated optimizer report contains richer identity data than
                # the lean live market payload. Replace both collections rather
                # than patching only rows that happen to overlap.
                if generated is not None:
                    for generated_player in generated['players'] + generated.get('marketPlayers', []):
                        previous = previous_by_id.get(generated_player['id'], {})
                        if generated_player.get('li') is None and previous.get('li') is not None:
                            generated_player['li'] = previous['li']
                    report['players'] = generated['players']
                    report['marketPlayers'] = generated.get('marketPlayers', [])
                li = {
                    p['id']: p.get('li') for p in report['players'] + report.get('marketPlayers', [])
                    if p.get('li') is not None
                }
                patches = {}
                for p in report['players'] + report.get('marketPlayers', []):
                    # The report export has richer player metadata than the lean
                    # live market endpoint. Keep its complete name, club and image.
                    if generated_by_id:
                        generated_player = generated_by_id.get(p['id'])
                        if generated_player:
                            p.update({
                                key: generated_player[key] for key in (
                                    'name', 'team', 'teamId', 'position', 'image', 'teamImage', 'status',
                                    'l3', 'season', 'average', 'li', 'expiresAt'
                                ) if generated_player.get(key) not in (None, '', 'Unbekannt')
                            })
                    patch = {'change': snapshot['predictions'].get(p['id']),
                             'change7': multi_day_prediction(snapshot, p['id'], 7),
                             'matchdayChange': project_to_matchday(snapshot, p['id'], updates)}
                    if p['id'] in li:
                        patch['li'] = li[p['id']]
                    p.update(patch)
                    patches[p['id']] = patch
                forecast = forecast_metadata(snapshot)
                report.update(forecast=forecast, forecastHorizon=horizon)
                persisted_report = deepcopy(report)
            self._persist_report(persisted_report)
            with self.lock:
                self.status.update(
                    status='done', patches=patches, forecast=forecast, forecastHorizon=horizon,
                    progress=100, phase='Report abgeschlossen',
                    message='Report abgeschlossen. ' + ('E-Mail wurde angestoßen.' if os.getenv('EMAIL_USER') else 'Keine E-Mail-Adresse konfiguriert.')
                )
        except Exception as exc:
            with self.lock:
                self.status.update(status='failed', error=str(exc) if isinstance(exc, RuntimeError)
                                   else 'Report konnte nicht abgeschlossen werden. Serverumgebung prüfen.')
