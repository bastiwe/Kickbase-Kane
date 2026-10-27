"""Local-only host for the Kickbase trading dashboard and report jobs."""

import argparse
from html.parser import HTMLParser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
import sqlite3
from pathlib import Path
import secrets
import threading
import webbrowser
from datetime import datetime
from zoneinfo import ZoneInfo
from urllib.parse import urlsplit

from dotenv import load_dotenv
import requests

from features.ai_advisor import ask_advisor, prepare_context, validate_report
from features.advisor_live import LiveKickbase, normalize_lineup
from features.sale_bonus import load_sale_bonus
from features.predictions.snapshot import forecast_metadata, multi_day_prediction, read_prediction_snapshot, project_to_matchday
from features.report_jobs import ReportJobs
from features.github_forecast_sync import dispatch_workflow
from features.dashboard_layout import load_design, validate_design


APP_ROOT = Path(__file__).resolve().parent
DATA_ROOT = Path(os.getenv('KICKBASE_DATA_DIR', APP_ROOT)).resolve()
MAX_BODY = 2_000_000


def read_manager_budgets(path, own_cash=None, own_name=None, cash_fetched_at=None):
    """Return the display-safe budget summary produced by the full report."""
    try:
        payload = json.loads(Path(path).read_text(encoding='utf-8'))
    except (OSError, ValueError, TypeError):
        return {'managers': [], 'note': 'Noch kein Managerbudget aus einem Vollreport verfügbar.'}
    rows = []
    for item in payload.get('manager_budgets', []):
        if not isinstance(item, dict):
            continue
        try:
            values = {key: float(item[key]) for key in ('cash', 'squadValue', 'buyingPower')}
        except (KeyError, TypeError, ValueError):
            continue
        if not all(value == value and abs(value) != float('inf') for value in values.values()):
            continue
        rows.append({
            'name': str(item.get('name') or 'Unbekannt'),
            **values,
            'basis': str(item.get('basis') or 'Schätzung'),
        })
    if own_cash is not None:
        own_row = next((row for row in rows if own_name and row['name'] == own_name), None)
        if own_row is None:
            own_row = next((row for row in rows if row['basis'].startswith('API')), None)
        if own_row is not None:
            own_row['cash'] = float(own_cash)
            own_row['buyingPower'] = float(own_cash) + 0.33 * own_row['squadValue']
            own_row['basis'] = 'API live (eigener Kontostand)'
    note = ('Eigener Cash wurde beim Öffnen live aus der API abgerufen; '
            'Cash der Mitmanager bleibt geschätzt. Kaderwerte stammen aus dem letzten Vollreport.'
            if own_cash is not None else
            'Stand des letzten Vollreports: eigener Cash damals aus der API; '
            'Cash der Mitmanager geschätzt. Kaderwerte und Kaufkraft sind nicht live.')
    return {
        'generatedAt': payload.get('generated_at'),
        'cashFetchedAt': cash_fetched_at,
        'managers': rows,
        'note': note,
    }


class ReportParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.capture = False
        self.parts = []

    def handle_starttag(self, tag, attrs):
        if tag == 'script' and dict(attrs).get('id') == 'data':
            self.capture = True

    def handle_data(self, data):
        if self.capture:
            self.parts.append(data)

    def handle_endtag(self, tag):
        if tag == 'script':
            self.capture = False


def read_report(html):
    parser = ReportParser()
    parser.feed(html)
    report = json.loads(''.join(parser.parts))
    json.dumps(report, allow_nan=False)
    return validate_report(report)


class AdvisorServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, address, report=None, api_key=None, model='gpt-5-mini', persist_path=None, memory_path=None):
        super().__init__(address, AdvisorHandler)
        self.report = report or {'players': [], 'budget': None, 'league': 'local', 'user': 'local',
                                 'generated': 'Noch kein Report geladen'}
        self.revision = 1
        self.csrf = secrets.token_urlsafe(32)
        self.api_key = api_key or ''
        self.model = model
        self.persist_path = persist_path
        self.persist_mtime_ns = self._persist_mtime_ns()
        self.memory_path = memory_path or DATA_ROOT / '.advisor-memory.json'
        self.log_path = DATA_ROOT / '.advisor.log'
        self.memory = self._load_memory()
        self.lock = threading.Lock()
        self.request_lock = threading.Lock()
        self.layout_path = DATA_ROOT / '.advisor-dashboard-layout.json'
        self.kickbase = None
        self.report_jobs = ReportJobs(self, APP_ROOT, DATA_ROOT)

    def _persist_mtime_ns(self):
        try:
            return Path(self.persist_path).stat().st_mtime_ns if self.persist_path else None
        except OSError:
            return None

    def reload_persisted_report(self):
        """Hot-load a dashboard report written by the GitHub artifact sync."""
        current_mtime = self._persist_mtime_ns()
        if current_mtime is None or current_mtime == self.persist_mtime_ns:
            return False
        try:
            report = validate_report(json.loads(Path(self.persist_path).read_text(encoding='utf-8')))
        except (OSError, ValueError, TypeError, KeyError):
            return False
        with self.lock:
            latest_mtime = self._persist_mtime_ns()
            if latest_mtime is None or latest_mtime == self.persist_mtime_ns:
                return False
            self.report = report
            self.persist_mtime_ns = latest_mtime
            self.revision += 1
        return True

    def log_event(self, message):
        try:
            with self.log_path.open('a', encoding='utf-8') as handle:
                handle.write(f'{datetime.now().isoformat(timespec="seconds")} {message}\n')
        except OSError:
            pass

    def _load_memory(self):
        try:
            values = json.loads(self.memory_path.read_text(encoding='utf-8'))
            return [item for item in values if isinstance(item, str) and item.strip()][:100]
        except (OSError, ValueError, TypeError):
            return []

    def save_memory(self):
        temporary = self.memory_path.with_suffix('.tmp')
        temporary.write_text(json.dumps(self.memory, ensure_ascii=False, indent=2), encoding='utf-8')
        temporary.replace(self.memory_path)

    @property
    def origin(self):
        return f'http://127.0.0.1:{self.server_port}'


class AdvisorHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        # Request URLs, keys, questions and report contents are not logged.
        pass

    def reply(self, code, value, content_type='application/json; charset=utf-8'):
        body = json.dumps(value, ensure_ascii=False).encode('utf-8') if content_type.startswith('application/json') else value.encode('utf-8')
        self.send_response(code)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Referrer-Policy', 'no-referrer')
        csp = "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' https: data:; connect-src 'self'; base-uri 'none'"
        # Home Assistant Ingress terminates authentication and embeds the app
        # behind a supervisor-owned URL. Its frame origin is installation-
        # specific, so do not add a frame-ancestors directive in that mode.
        # The app has no mapped host port and validates the Ingress user header.
        if os.getenv('KICKBASE_HOME_ASSISTANT') != '1':
            csp += "; frame-ancestors 'none'"
        self.send_header('Content-Security-Policy', csp)
        self.end_headers()
        self.wfile.write(body)

    def valid_host(self):
        if os.getenv('KICKBASE_HOME_ASSISTANT') == '1':
            # Ingress is the authentication and access boundary for add-ons.
            # Some Home Assistant frontend requests (notably the embedded
            # frame's initial document request) do not consistently forward
            # the optional user headers. Requiring one here prevented the
            # application from opening inside the standard Ingress frame.
            # The add-on has no mapped host port; write requests still require
            # the per-page CSRF token below.
            return True
        return self.headers.get('Host') == f'127.0.0.1:{self.server.server_port}'

    def do_GET(self):
        if not self.valid_host():
            self.reply(403, {'error': 'Nur lokaler Zugriff erlaubt.'})
            return
        path = urlsplit(self.path).path
        if path in ('/', '/planner', '/editor', '/api/dashboard-data'):
            self.server.reload_persisted_report()
        if path == '/':
            live_message = ''
            with self.server.lock:
                report, kickbase = self.server.report, self.server.kickbase
            if kickbase:
                try:
                    if report.get('players'):
                        seed = {'selection': [], 'plans': {
                            str(p['id']): {'action': 'keep' if p.get('owned') else 'skip'}
                            for p in report['players']}, 'budget': report.get('budget')}
                        refreshed, _, info = kickbase.refresh(report, seed)
                    else:
                        refreshed, _, info = kickbase.bootstrap(os.getenv('KICK_LEAGUE_NAME', ''))
                    snapshot = read_prediction_snapshot(DATA_ROOT / 'prediction_snapshot_1t.json')
                    if snapshot:
                        horizon = refreshed.get('forecastHorizon') or report.get('forecastHorizon')
                        updates = (horizon or {}).get('updates')
                        for player in refreshed.get('players', []) + refreshed.get('marketPlayers', []):
                            player['change'] = snapshot['predictions'].get(str(player['id']), player.get('change'))
                            player['change7'] = multi_day_prediction(snapshot, player['id'], 7)
                            player['matchdayChange'] = project_to_matchday(snapshot, player['id'], updates)
                        refreshed['forecast'] = forecast_metadata(snapshot)
                        refreshed['forecastHorizon'] = horizon
                    try:
                        refreshed['saleBonus'] = load_sale_bonus(kickbase, refreshed)
                    except (RuntimeError, requests.RequestException, ValueError, KeyError, TypeError):
                        refreshed['saleBonus'] = {'rules': [], 'purchases': {}, 'error': 'Bonusdaten nicht verfügbar'}
                        self.server.log_event('ERROR Verkaufsbonusdaten nicht geladen')
                    with self.server.lock:
                        if self.server.report is report:
                            self.server.report = refreshed
                            self.server.revision += 1
                    fetched_at = datetime.fromisoformat(info['fetchedAt']).astimezone(ZoneInfo('Europe/Berlin'))
                    live_message = 'Kader, Markt und Budget live geladen: ' + fetched_at.strftime('%d.%m.%Y, %H:%M:%S Uhr') + ' (Berlin)'
                except (RuntimeError, requests.RequestException, ValueError, KeyError, TypeError):
                    live_message = 'Live-Kader konnte nicht geladen werden. Angezeigt wird der alte Reportstand.'
                    self.server.log_event('ERROR Live-Kader beim Seitenaufruf nicht geladen')
            else:
                live_message = 'Livezugriff nicht aktiviert. Angezeigt wird der Reportstand.'
            with self.server.lock:
                payload = json.dumps(self.server.report, ensure_ascii=True, allow_nan=False).replace('<', '\\u003c')
                settings = json.dumps({'csrf': self.server.csrf, 'revision': self.server.revision,
                                       'liveMessage': live_message}, ensure_ascii=True).replace('<', '\\u003c')
            template = (APP_ROOT / 'features/trading_dashboard.html').read_text(encoding='utf-8')
            page = template.replace('__PAYLOAD__', payload).replace('__SETTINGS__', settings)
            self.reply(200, page, 'text/html; charset=utf-8')
        elif path == '/planner':
            with self.server.lock:
                payload = json.dumps(self.server.report, ensure_ascii=True, allow_nan=False).replace('<', '\\u003c')
                settings = json.dumps({'csrf': self.server.csrf, 'revision': self.server.revision,
                                       'liveMessage': 'Kader, Budget und Aufstellung stammen aus dem letzten Live-Abruf.'},
                                      ensure_ascii=True).replace('<', '\\u003c')
            template = (APP_ROOT / 'features/mobile_lineup_planner.html').read_text(encoding='utf-8')
            page = template.replace('__PAYLOAD__', payload).replace('__SETTINGS__', settings)
            self.reply(200, page, 'text/html; charset=utf-8')
        elif path == '/editor':
            with self.server.lock:
                payload = json.dumps(self.server.report, ensure_ascii=True, allow_nan=False).replace('<', '\\u003c')
                settings = json.dumps({'csrf': self.server.csrf}, ensure_ascii=True)
            template = (APP_ROOT / 'features/dashboard_editor.html').read_text(encoding='utf-8')
            self.reply(200, template.replace('__PAYLOAD__', payload).replace('__SETTINGS__', settings), 'text/html; charset=utf-8')
        elif path == '/api/dashboard-layout':
            with self.server.lock:
                self.reply(200, load_design(self.server.layout_path))
        elif path == '/api/dashboard-data':
            with self.server.lock:
                self.reply(200, self.server.report)
        elif path in ('/dashboard.js', '/dashboard.css', '/dashboard_layout.js', '/dashboard_editor.js', '/dashboard_editor.css'):
            name = path.lstrip('/')
            content_type = 'text/javascript; charset=utf-8' if name.endswith('.js') else 'text/css; charset=utf-8'
            self.reply(200, (APP_ROOT / 'features' / name).read_text(encoding='utf-8'), content_type)
        elif path.startswith('/api/player-details/'):
            player_id = path.rsplit('/', 1)[-1]
            with self.server.lock:
                client = self.server.kickbase
                known = {str(p['id']) for p in self.server.report['players'] + self.server.report.get('marketPlayers', [])}
            if not client:
                self.reply(409, {'error': 'Kickbase-Livezugriff ist nicht aktiviert.'})
            elif player_id not in known:
                self.reply(404, {'error': 'Spieler nicht im aktuellen Kader oder Markt.'})
            else:
                try:
                    self.reply(200, client.player_details(player_id))
                except (requests.RequestException, RuntimeError, ValueError, KeyError, TypeError) as exc:
                    self.server.log_event('ERROR Spielerdetails: ' + type(exc).__name__)
                    self.reply(502, {'error': 'Kickbase-Spielerdetails derzeit nicht abrufbar. Bitte erneut öffnen.'})
        elif path.startswith('/api/player-market-history/'):
            player_id = path.rsplit('/', 1)[-1]
            with self.server.lock:
                client = self.server.kickbase
                known = {
                    str(p['id']) for p in (
                        self.server.report.get('players', []) + self.server.report.get('marketPlayers', [])
                    )
                }
            if not client:
                self.reply(409, {'error': 'Kickbase-Livezugriff ist nicht aktiviert.'})
            elif player_id not in known:
                self.reply(404, {'error': 'Spieler nicht im aktuellen Kader oder Markt.'})
            else:
                try:
                    self.reply(200, client.player_daily_market_changes(player_id))
                except (requests.RequestException, RuntimeError, ValueError, KeyError, TypeError):
                    self.server.log_event('ERROR Spieler-Marktwerthistorie nicht geladen')
                    self.reply(502, {'error': 'Marktwerthistorie derzeit nicht abrufbar.'})
        elif path == '/api/squad-value-history':
            with self.server.lock:
                client = self.server.kickbase
                league_id = self.server.report.get('league')
                player_ids = [player.get('id') for player in self.server.report.get('players', []) if player.get('owned')]
            if not client:
                self.reply(409, {'series': [], 'note': 'Kickbase-Livezugriff ist nicht aktiviert.'})
            else:
                try:
                    self.reply(200, client.squad_value_history(league_id, player_ids))
                except (requests.RequestException, RuntimeError, ValueError, KeyError, TypeError):
                    self.server.log_event('ERROR Kaderwertverlauf nicht geladen')
                    self.reply(502, {'series': [], 'note': 'Kaderwertverlauf aus Kickbase derzeit nicht abrufbar.'})
        elif path == '/api/manager-budgets':
            with self.server.lock:
                client = self.server.kickbase
                league_id = self.server.report.get('league')
            own_cash = own_name = cash_fetched_at = None
            if client and league_id:
                try:
                    user = client.get('/user/settings').get('u', {})
                    own_name = user.get('unm') or user.get('n') or user.get('name')
                    own_cash = client.get(
                        '/leagues/' + str(league_id) + '/me/budget')['b']
                    cash_fetched_at = datetime.now(ZoneInfo('Europe/Berlin')).isoformat()
                except (requests.RequestException, RuntimeError, ValueError, KeyError, TypeError):
                    self.server.log_event('ERROR Live-Cash für Managerbudgets nicht geladen')
            self.reply(200, read_manager_budgets(
                DATA_ROOT / 'manager-history-output' / 'latest.json',
                own_cash, own_name, cash_fetched_at))
        elif path == '/api/recent-transfers':
            with self.server.lock:
                client = self.server.kickbase
                league_id = self.server.report.get('league')
            if not client or not league_id:
                self.reply(409, {'transfers': [], 'error': 'Kickbase-Livezugriff ist nicht aktiviert.'})
            else:
                try:
                    self.reply(200, client.recent_transfers(league_id, limit=5))
                except (requests.RequestException, RuntimeError, ValueError, KeyError, TypeError):
                    self.server.log_event('ERROR Letzte Transfers nicht geladen')
                    self.reply(502, {'transfers': [], 'error': 'Letzte Transfers derzeit nicht abrufbar.'})
        elif path == '/api/report-job':
            self.reply(200, self.server.report_jobs.read())
        elif path == '/api/status':
            self.reply(200, {'configured': bool(self.server.api_key), 'model': self.server.model,
                             'liveConfigured': self.server.kickbase is not None,
                             'revision': self.server.revision, 'marketCount': len(self.server.report.get('marketPlayers', [])),
                             'memoryCount': len(self.server.memory)})
        elif path == '/api/current-lineup':
            with self.server.lock:
                kickbase, league_id = self.server.kickbase, self.server.report.get('league')
            if not kickbase:
                self.reply(409, {'error': 'Kein Kickbase-Livezugriff konfiguriert.'})
                return
            try:
                self.reply(200, normalize_lineup(kickbase.lineup(league_id)))
            except (requests.RequestException, RuntimeError, ValueError, KeyError, TypeError) as exc:
                self.server.log_event('ERROR Live-Aufstellung: ' + type(exc).__name__)
                self.reply(502, {'error': 'Kickbase-Aufstellung konnte nicht gelesen werden. Details im Serverlog.'})
        else:
            self.reply(404, {'error': 'Nicht gefunden.'})

    def do_POST(self):
        path = urlsplit(self.path).path
        home_assistant = os.getenv('KICKBASE_HOME_ASSISTANT') == '1'
        # The browser origin is the user's Home Assistant URL in Ingress mode,
        # never the private container address. Ingress authentication plus our
        # per-page CSRF token replaces the localhost-origin check there.
        origin_valid = home_assistant or self.headers.get('Origin') == self.server.origin
        if (not self.valid_host() or not origin_valid
                or not secrets.compare_digest(self.headers.get('X-Advisor-Token', ''), self.server.csrf)):
            self.reply(403, {'error': 'Ungültige lokale Sitzung. Seite neu laden.'})
            return
        try:
            length = int(self.headers.get('Content-Length', '0'))
            if not 0 < length <= MAX_BODY or self.headers.get('Content-Type', '').split(';')[0] != 'application/json':
                self.reply(413, {'error': 'Ungültige oder zu große Anfrage.'})
                return
            self.connection.settimeout(110)
            body = json.loads(self.rfile.read(length))
            if not isinstance(body, dict):
                raise ValueError('Ungültige Anfrage.')
            if path in ('/api/dashboard-layout', '/api/dashboard-layout/validate'):
                design = validate_design(body)
                if path.endswith('/validate'):
                    self.reply(200, design)
                    return
                with self.server.lock:
                    current = load_design(self.server.layout_path)
                    if design['revision'] != current['revision']:
                        self.reply(409, {'error': 'Das Layout wurde inzwischen auf einem anderen Gerät geändert. Bitte zuerst exportieren und die Seite neu laden.'})
                        return
                    design['revision'] += 1
                    temporary = self.server.layout_path.with_suffix('.tmp')
                    temporary.write_text(json.dumps(design, ensure_ascii=True, allow_nan=False), encoding='utf-8')
                    temporary.replace(self.server.layout_path)
                self.reply(200, design)
            elif path == '/api/github-report':
                kind = body.get('kind')
                workflows = {'full': 'actions_spaet.yml', 'fast': 'actions_fast.yml'}
                if kind not in workflows:
                    raise ValueError('Ungültige Reportart.')
                result = dispatch_workflow(
                    os.getenv('GITHUB_FORECAST_TOKEN', ''),
                    os.getenv('GITHUB_FORECAST_REPOSITORY', 'bastiwe/Kickbase-Kane'),
                    workflows[kind],
                )
                self.server.log_event('OK /api/github-report kind=' + kind)
                self.reply(202, result)
            elif path == '/api/report-job':
                self.reply(202, self.server.report_jobs.start(body.get('kind')))
            elif path == '/api/key':
                key = body.get('key')
                if not isinstance(key, str) or len(key) > 512 or (key and not key.startswith('sk-')):
                    raise ValueError('Bitte einen gültigen OpenAI-API-Schlüssel eingeben.')
                with self.server.lock:
                    self.server.api_key = key.strip()
                self.reply(200, {'configured': bool(key)})
            elif path == '/api/kickbase':
                username, password = body.get('username', ''), body.get('password', '')
                if not all(isinstance(v, str) and len(v) <= 512 for v in (username, password)):
                    raise ValueError('Ungültige Zugangsdaten.')
                if bool(username) != bool(password):
                    raise ValueError('Benutzername und Passwort werden benötigt.')
                with self.server.lock:
                    self.server.kickbase = LiveKickbase(username, password) if username else None
                self.reply(200, {'configured': bool(username)})
            elif path == '/api/memory':
                action, note = body.get('action'), body.get('note')
                with self.server.lock:
                    if action == 'add':
                        if not isinstance(note, str) or not 3 <= len(note.strip()) <= 500:
                            raise ValueError('Hinweis muss zwischen 3 und 500 Zeichen lang sein.')
                        if note.strip() not in self.server.memory:
                            self.server.memory.append(note.strip())
                            self.server.memory = self.server.memory[-100:]
                            self.server.save_memory()
                    elif action == 'clear':
                        self.server.memory = []
                        self.server.save_memory()
                    else:
                        raise ValueError('Ungültige Gedächtnisaktion.')
                    self.reply(200, {'memory': self.server.memory})
            elif path == '/api/apply-lineup':
                self.apply_lineup(body)
            elif path == '/api/report':
                html = body.get('html')
                if not isinstance(html, str):
                    raise ValueError('HTML-Report fehlt.')
                report = read_report(html)
                with self.server.lock:
                    if self.server.persist_path:
                        temporary = self.server.persist_path.with_suffix('.tmp')
                        temporary.write_text(json.dumps(report, allow_nan=False), encoding='utf-8')
                        temporary.replace(self.server.persist_path)
                        self.server.persist_mtime_ns = self.server._persist_mtime_ns()
                    self.server.report = report
                    self.server.revision += 1
                self.reply(200, {'loaded': True})
            elif path == '/api/chat':
                self.chat(body)
            else:
                self.reply(404, {'error': 'Nicht gefunden.'})
        except (ValueError, TypeError, KeyError, AttributeError) as exc:
            message = (str(exc) if path.startswith('/api/dashboard-layout') else
                       'Ungültige Daten. Bitte einen aktuellen Startelf-HTML-Report laden und die Aufstellung prüfen.')
            self.reply(400, {'error': message})
        except (requests.RequestException, TimeoutError):
            self.reply(502, {'error': 'OpenAI ist momentan nicht erreichbar oder die Anfrage dauerte zu lange. Erneut versuchen.'})
        except RuntimeError as exc:
            self.server.log_event(f'ERROR {self.path}: {exc}')
            self.reply(502, {'error': str(exc)})
        except OSError:
            self.reply(500, {'error': 'Lokale Datei konnte nicht gespeichert werden. Bitte Ordnerberechtigungen prüfen.'})

    def chat(self, body):
        with self.server.lock:
            if body.get('revision') != self.server.revision:
                self.reply(409, {'error': 'Ein neuer Report wurde geladen. Bitte die Seite neu laden.'})
                return
            report, key, model = self.server.report, self.server.api_key, self.server.model
            memory = list(self.server.memory)
            kickbase = self.server.kickbase
        if not key:
            self.reply(409, {'error': 'Bitte zuerst den OpenAI-API-Schlüssel unter KI-Einstellungen hinterlegen.'})
            return
        if not report['players']:
            raise ValueError('Kein Kader geladen.')
        message, history = body.get('message'), body.get('history', [])
        if not isinstance(message, str) or not message.strip() or len(message) > 4000 or not isinstance(history, list) or len(history) > 12:
            raise ValueError('Ungültige Frage.')
        for item in history:
            if not isinstance(item, dict) or item.get('role') not in ('user', 'assistant') or not isinstance(item.get('content'), str) or len(item['content']) > 16000:
                raise ValueError('Ungültiger Chatverlauf.')
        context = prepare_context(report, body.get('state'))
        if not self.server.request_lock.acquire(blocking=False):
            self.reply(429, {'error': 'Es läuft bereits eine KI-Anfrage. Bitte kurz warten.'})
            return
        try:
            if kickbase:
                live_report, live_state, live_info = kickbase.refresh(report, body.get('state'))
                if live_state.get('bonusEnabled') is True:
                    try:
                        live_report['saleBonus'] = load_sale_bonus(kickbase, live_report)
                    except (RuntimeError, requests.RequestException, ValueError, KeyError, TypeError):
                        live_report['saleBonus'] = {}
                        live_info['bonusWarning'] = 'Bonusdaten nicht abrufbar; keine Erfolgsprämien eingerechnet.'
                context = prepare_context(live_report, live_state)
                context['liveData'] = live_info
            result = ask_advisor(key, model, context, message.strip(), history, memory)
            result['checkedPlan'] = context['checkedCurrentPlan']
            result['liveData'] = context.get('liveData')
            self.reply(200, result)
        finally:
            self.server.request_lock.release()

    def apply_lineup(self, body):
        state = body.get('state')
        if not isinstance(state, dict) or not isinstance(state.get('selection'), list):
            raise ValueError('Ungültige Aufstellung.')
        with self.server.lock:
            kickbase, report = self.server.kickbase, self.server.report
        if not kickbase:
            raise RuntimeError('Kickbase-Livezugriff ist nicht aktiviert.')
        selected = [str(player_id) for player_id in state['selection'] if player_id]
        if len(selected) != 11 or len(set(selected)) != 11:
            raise ValueError('Die Startelf muss genau elf unterschiedliche Spieler enthalten.')
        owned = {str(player['id']) for player in report.get('players', []) if player.get('owned')}
        if not set(selected).issubset(owned):
            raise ValueError('Nur Spieler aus deinem aktuellen Kader dürfen aufgestellt werden.')
        formation = state.get('formation')
        if not isinstance(formation, str) or formation not in {'4-4-2', '4-3-3', '3-4-3', '3-5-2', '5-3-2', '4-5-1', '5-4-1', '4-2-4', '5-2-3', '3-6-1'}:
            raise ValueError('Ungültige Kickbase-Formation.')
        result = kickbase.apply_lineup(report.get('league'), formation, selected)
        self.server.log_event(f'OK /api/apply-lineup formation={formation} players={len(selected)}')
        self.reply(200, {'applied': True, 'formation': formation, 'playerCount': len(selected), 'response': result})



def create_server(port=8765, report=None, api_key=None, model='gpt-5-mini', persist_path=None):
    host = os.getenv('KICKBASE_BIND_HOST', '127.0.0.1')
    for candidate in range(port, port + 20) if port else (0,):
        try:
            return AdvisorServer((host, candidate), report, api_key, model, persist_path)
        except OSError:
            continue
    raise RuntimeError('Kein freier lokaler Port gefunden.')


def main():
    DATA_ROOT.mkdir(parents=True, exist_ok=True)
    load_dotenv(DATA_ROOT / '.env')
    load_dotenv(APP_ROOT / '.env')
    parser = argparse.ArgumentParser(description='Lokaler Kickbase KI-Ratgeber')
    parser.add_argument('--port', type=int, default=8765)
    parser.add_argument('--report', type=Path)
    parser.add_argument('--no-browser', action='store_true')
    args = parser.parse_args()
    report_path = args.report or DATA_ROOT / 'startelf_optimizer.html'
    saved_report = DATA_ROOT / '.advisor-report.json'
    if not args.report and saved_report.is_file():
        report = validate_report(json.loads(saved_report.read_text(encoding='utf-8')))
    else:
        report = read_report(report_path.read_text(encoding='utf-8')) if report_path.is_file() else None
    server = create_server(args.port, report, os.getenv('OPENAI_API_KEY'), os.getenv('OPENAI_MODEL', 'gpt-5-mini'), saved_report)
    if os.getenv('KICK_USER') and os.getenv('KICK_PASS'):
        server.kickbase = LiveKickbase(os.environ['KICK_USER'], os.environ['KICK_PASS'])
    print('Kickbase KI-Ratgeber: ' + server.origin, flush=True)
    print('Report und API-Schlüssel können in der lokalen Oberfläche geladen werden.', flush=True)
    if not args.no_browser:
        webbrowser.open(server.origin)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == '__main__':
    main()
