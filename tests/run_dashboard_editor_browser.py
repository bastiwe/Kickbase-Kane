"""Exercise the real editor routes using an isolated, temporary layout store."""
import os
from pathlib import Path
import subprocess
import tempfile
import threading

from advisor_server import create_server


def main():
    report = {'players': [
        {'id': 'kane', 'name': 'Harry Kane', 'owned': True, 'position': 4, 'team': 'Bayern', 'mv': 65000000,
         'li': 76, 'season': 192, 'recentForm': [90, 345, 214], 'image': 'https://editor.test/player.png', 'teamImage': 'https://editor.test/crest.png'},
        {'id': 'kimmich', 'name': 'Joshua Kimmich', 'owned': True, 'position': 3, 'team': 'Bayern', 'mv': 59800000,
         'li': 71, 'season': 222, 'recentForm': [0, 271, 195], 'image': 'https://editor.test/player.png', 'teamImage': 'https://editor.test/crest.png'}],
        'marketPlayers': [], 'budget': 5185217, 'generated': '27.10.2026', 'customField': {'value': 'Aus dem Vollreport'}}
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
