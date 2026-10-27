"""Exercise the real editor routes using an isolated, temporary layout store."""
import os
from pathlib import Path
import subprocess
import tempfile
import threading
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from advisor_server import create_server


def main():
    now = datetime.now(ZoneInfo('Europe/Berlin'))
    update = now.replace(hour=22, minute=0, second=0, microsecond=0)
    if update <= now:
        update += timedelta(days=1)
    report = {'players': [
        {'id': 'kane', 'name': 'Harry Kane', 'owned': True, 'position': 4, 'team': 'Bayern', 'mv': 65000000,
         'change': 30000, 'li': 76, 'season': 192, 'recentForm': [90, 345, 214], 'image': 'https://editor.test/player.png', 'teamImage': 'https://editor.test/crest.png'},
        {'id': 'kimmich', 'name': 'Joshua Kimmich', 'owned': True, 'position': 3, 'team': 'Bayern', 'mv': 59800000,
         'change': -30000, 'li': 71, 'season': 222, 'recentForm': [0, 271, 195], 'image': 'https://editor.test/player.png', 'teamImage': 'https://editor.test/crest.png'}],
        'marketPlayers': [{'id': str(i), 'name': name, 'mv': 10000000, 'change': change,
                          'expiresAt': (update + timedelta(hours=hours)).timestamp(), 'owned': False}
                         for i, name, change, hours in [(1, 'Chance A', 150000, -1), (2, 'Chance B', 250000, -1),
                                                       (3, 'Nachtangebot', 180000, 1), (4, 'Ohne Prognose', None, -1)]],
        'budget': 5185217, 'generated': '27.10.2026', 'customField': {'value': 'Aus dem Vollreport'}}
    with tempfile.TemporaryDirectory() as tmp:
        server = create_server(0, report)
        server.layout_path = Path(tmp) / 'layout.json'
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            result = subprocess.run(['node', 'tests/dashboard_editor_browser.cjs'], env={**os.environ, 'EDITOR_TEST_URL': server.origin}, timeout=180)
            raise SystemExit(result.returncode)
        finally:
            server.shutdown()
            server.server_close()
            thread.join()


if __name__ == '__main__':
    main()
