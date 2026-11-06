"""Check the visible market values and LI states with deterministic report data."""
import os
from pathlib import Path
import subprocess
import sys
import threading

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from advisor_server import create_server


def main():
    players = [dict(id=str(index), name='Maximilian Mittelst\u00e4dt', team='Stuttgart',
                    position=2, owned=True, mv=None if index == 7 else 12345678,
                    change=-150000, li=li, season=123.4, profitLoss=123456,
                    totalPoints=1234)
               for index, li in enumerate([80, 65, 25, 1, 0, None, 101, 85])]
    server = create_server(0, dict(players=players, marketPlayers=[], budget=1000000))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        return subprocess.run(['node', 'tests/dashboard_player_values_browser.cjs'],
                              env={**os.environ, 'DASHBOARD_TEST_URL': server.origin},
                              timeout=120).returncode
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


if __name__ == '__main__':
    raise SystemExit(main())
