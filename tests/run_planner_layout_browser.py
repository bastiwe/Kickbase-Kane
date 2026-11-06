"""Verify responsive planner geometry without accessing Kickbase."""
import os
from pathlib import Path
import subprocess
import sys
import threading

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from advisor_server import create_server


def main():
    players = []
    for position, count in [(1, 2), (2, 6), (3, 7), (4, 5)]:
        for index in range(count):
            players.append(dict(id=str(len(players) + 1), name=['Nico Schlotterbeck', 'Maximilian Mittelstädt', 'Joshua Kimmich', 'Harry Kane', 'Angelo Stiller', 'Robin Koch', 'Robert Andrich'][index],
                                position=position, owned=True, mv=12300000, season=123.4,
                                li=85, status='Fit', opponent='M\u00f6nchengladbach (A)',
                                change=50000, profitLoss=-123000, recentForm=[100, 90, 80]))
    server = create_server(0, dict(players=players, marketPlayers=[], budget=5000000))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        result = subprocess.run(['node', 'tests/planner_layout_browser.cjs'],
                                env={**os.environ, 'PLANNER_TEST_URL': server.origin}, timeout=120)
        return result.returncode
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


if __name__ == '__main__':
    raise SystemExit(main())
