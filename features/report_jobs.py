"""Run the existing reports without blocking the local HTTP server."""
import os
from pathlib import Path
import subprocess
import sys
import threading
import uuid
from copy import deepcopy
from features.predictions.snapshot import read_prediction_snapshot, project_to_matchday


class ReportJobs:
    def __init__(self, server, root):
        self.server, self.root = server, Path(root)
        self.lock = threading.Lock()
        self.status = {'status': 'idle'}

    def read(self):
        with self.lock:
            return deepcopy(self.status)

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
            self.status = {'status': 'running', 'kind': kind, 'id': uuid.uuid4().hex}
        env = os.environ.copy()
        env.update(KICK_USER=client.username, KICK_PASS=client.password,
                   REPORT_LEAGUE_ID=str(report['league']), REPORT_USER_ID=str(report['user']),
                   PYTHONIOENCODING='utf-8')
        threading.Thread(target=self.run, args=(scripts[kind], env, report, kind), daemon=True).start()
        return self.read()

    def run(self, script, env, initial, kind):
        try:
            snapshot_path = self.root / 'prediction_snapshot_1t.json'
            before = snapshot_path.read_bytes() if snapshot_path.exists() else None
            optimizer_path = self.root / 'startelf_optimizer.html'
            previous_optimizer = optimizer_path.stat().st_mtime_ns if optimizer_path.exists() else None
            with (self.root / '.advisor-report-run.log').open('w', encoding='utf-8') as log:
                result = subprocess.run([sys.executable, '-u', str(self.root / script)],
                                        cwd=self.root, env=env, stdout=log, stderr=subprocess.STDOUT,
                                        timeout=3600, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
            if result.returncode:
                raise RuntimeError('Report fehlgeschlagen. Details in .advisor-report-run.log.')
            if not snapshot_path.exists() or snapshot_path.read_bytes() == before:
                raise RuntimeError('Report lieferte keine neuen Prognosedaten.')
            snapshot = read_prediction_snapshot(snapshot_path)
            if not snapshot:
                raise RuntimeError('Neue Prognosen sind ungültig.')
            li = {}
            horizon = initial.get('forecastHorizon')
            if kind == 'full':
                from advisor_server import read_report
                if not optimizer_path.exists() or optimizer_path.stat().st_mtime_ns == previous_optimizer:
                    raise RuntimeError('Report fertig, aber Optimierer-Daten fehlen. Details in .advisor-report-run.log.')
                generated = read_report(optimizer_path.read_text(encoding='utf-8'))
                if (generated['user'], generated['league']) != (initial['user'], initial['league']):
                    raise RuntimeError('Ergebnis gehört zu einer anderen Liga.')
                li = {p['id']: p.get('li') for p in generated['players']}
                horizon = generated.get('forecastHorizon')
            updates = (horizon or {}).get('updates')
            with self.server.lock:
                report = self.server.report
                if (report['user'], report['league']) != (initial['user'], initial['league']):
                    raise RuntimeError('Liga wurde gewechselt; Ergebnis nicht übernommen.')
                patches = {}
                for p in report['players'] + report.get('marketPlayers', []):
                    patch = {'change': snapshot['predictions'].get(p['id']),
                             'matchdayChange': project_to_matchday(snapshot, p['id'], updates)}
                    if p['id'] in li:
                        patch['li'] = li[p['id']]
                    p.update(patch)
                    patches[p['id']] = patch
                forecast = {k: snapshot[k] for k in ('generatedAt', 'source')}
                report.update(forecast=forecast, forecastHorizon=horizon)
            with self.lock:
                self.status.update(status='done', patches=patches, forecast=forecast, forecastHorizon=horizon)
        except Exception as exc:
            with self.lock:
                self.status.update(status='failed', error=str(exc) if isinstance(exc, RuntimeError)
                                   else 'Report konnte nicht abgeschlossen werden. Serverumgebung prüfen.')
