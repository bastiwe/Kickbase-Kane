"""Local-only host for the planner and its interactive OpenAI adviser."""

import argparse
from html.parser import HTMLParser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import secrets
import threading
import webbrowser

from dotenv import load_dotenv
import requests

from features.ai_advisor import ask_advisor, prepare_context, validate_report
from features.advisor_live import LiveKickbase


ROOT = Path(__file__).resolve().parent
MAX_BODY = 2_000_000


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
        self.memory_path = memory_path or ROOT / '.advisor-memory.json'
        self.memory = self._load_memory()
        self.lock = threading.Lock()
        self.request_lock = threading.Lock()
        self.kickbase = None

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
        self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' https: data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'")
        self.end_headers()
        self.wfile.write(body)

    def valid_host(self):
        return self.headers.get('Host') == f'127.0.0.1:{self.server.server_port}'

    def do_GET(self):
        if not self.valid_host():
            self.reply(403, {'error': 'Nur lokaler Zugriff erlaubt.'})
            return
        if self.path == '/':
            with self.server.lock:
                payload = json.dumps(self.server.report, ensure_ascii=True, allow_nan=False).replace('<', '\\u003c')
                settings = json.dumps({'csrf': self.server.csrf, 'revision': self.server.revision})
            template = (ROOT / 'features/lineup_optimizer.html').read_text(encoding='utf-8')
            page = template.replace('__PAYLOAD__', payload)
            page = page.replace('</head>', '<link rel="stylesheet" href="/advisor.css"></head>')
            page = page.replace('</body>', '<script>window.KICKBASE_ADVISOR=' + settings
                                + ';</script><script src="/advisor.js"></script></body>')
            self.reply(200, page, 'text/html; charset=utf-8')
        elif self.path in ('/advisor.js', '/advisor.css'):
            name = self.path.lstrip('/')
            content_type = 'text/javascript; charset=utf-8' if name.endswith('.js') else 'text/css; charset=utf-8'
            self.reply(200, (ROOT / 'features' / name).read_text(encoding='utf-8'), content_type)
        elif self.path == '/api/status':
            self.reply(200, {'configured': bool(self.server.api_key), 'model': self.server.model,
                             'liveConfigured': self.server.kickbase is not None,
                             'revision': self.server.revision, 'marketCount': len(self.server.report.get('marketPlayers', [])),
                             'memoryCount': len(self.server.memory)})
        else:
            self.reply(404, {'error': 'Nicht gefunden.'})

    def do_POST(self):
        if (not self.valid_host() or self.headers.get('Origin') != self.server.origin
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
            if self.path == '/api/key':
                key = body.get('key')
                if not isinstance(key, str) or len(key) > 512 or (key and not key.startswith('sk-')):
                    raise ValueError('Bitte einen gültigen OpenAI-API-Schlüssel eingeben.')
                with self.server.lock:
                    self.server.api_key = key.strip()
                self.reply(200, {'configured': bool(key)})
            elif self.path == '/api/kickbase':
                username, password = body.get('username', ''), body.get('password', '')
                if not all(isinstance(v, str) and len(v) <= 512 for v in (username, password)):
                    raise ValueError('Ungültige Zugangsdaten.')
                if bool(username) != bool(password):
                    raise ValueError('Benutzername und Passwort werden benötigt.')
                with self.server.lock:
                    self.server.kickbase = LiveKickbase(username, password) if username else None
                self.reply(200, {'configured': bool(username)})
            elif self.path == '/api/memory':
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
            elif self.path == '/api/report':
                html = body.get('html')
                if not isinstance(html, str):
                    raise ValueError('HTML-Report fehlt.')
                report = read_report(html)
                with self.server.lock:
                    if self.server.persist_path:
                        temporary = self.server.persist_path.with_suffix('.tmp')
                        temporary.write_text(json.dumps(report, allow_nan=False), encoding='utf-8')
                        temporary.replace(self.server.persist_path)
                    self.server.report = report
                    self.server.revision += 1
                self.reply(200, {'loaded': True})
            elif self.path == '/api/chat':
                self.chat(body)
            else:
                self.reply(404, {'error': 'Nicht gefunden.'})
        except (ValueError, TypeError, KeyError, AttributeError):
            self.reply(400, {'error': 'Ungültige Daten. Bitte einen aktuellen Startelf-HTML-Report laden und die Aufstellung prüfen.'})
        except (requests.RequestException, TimeoutError):
            self.reply(502, {'error': 'OpenAI ist momentan nicht erreichbar oder die Anfrage dauerte zu lange. Erneut versuchen.'})
        except RuntimeError as exc:
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
                context = prepare_context(live_report, live_state)
                context['liveData'] = live_info
            result = ask_advisor(key, model, context, message.strip(), history, memory)
            result['checkedPlan'] = context['checkedCurrentPlan']
            result['liveData'] = context.get('liveData')
            self.reply(200, result)
        finally:
            self.server.request_lock.release()


def create_server(port=8765, report=None, api_key=None, model='gpt-5-mini', persist_path=None):
    for candidate in range(port, port + 20) if port else (0,):
        try:
            return AdvisorServer(('127.0.0.1', candidate), report, api_key, model, persist_path)
        except OSError:
            continue
    raise RuntimeError('Kein freier lokaler Port gefunden.')


def main():
    load_dotenv(ROOT / '.env')
    parser = argparse.ArgumentParser(description='Lokaler Kickbase KI-Ratgeber')
    parser.add_argument('--port', type=int, default=8765)
    parser.add_argument('--report', type=Path)
    parser.add_argument('--no-browser', action='store_true')
    args = parser.parse_args()
    report_path = args.report or ROOT / 'startelf_optimizer.html'
    saved_report = ROOT / '.advisor-report.json'
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
