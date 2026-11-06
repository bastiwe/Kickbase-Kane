"""Serve deterministic live API fixtures through the actual HA page routes."""
import os
from pathlib import Path
import subprocess
import sys
import threading
from unittest.mock import Mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from advisor_server import create_server


def main():
    schedule = {'day': 8, 'it': [
        {'day': 8, 'it': [{'mi': str(i), 'dt': '2026-11-01T14:30:00Z', 'st': 1 if i == 100 else 2,
                          'il': i == 100, 't1g': 2, 't2g': 1, 't1sy': 'BVB', 't2sy': 'FCB',
                          't1im': 'https://images.test/crest.svg', 't2im': 'https://images.test/crest.svg',
                          'mtd': '62', 'mt': 62} for i in range(100, 109)]},
        {'day': 9, 'it': [{'mi': '200', 'dt': '2099-11-01T14:30:00Z', 'st': 0, 't1sy': 'HSV', 't2sy': 'BMG'}]}]}
    responses = {'/competitions/1/matchdays': schedule,
                 '/live/eventtypes': {'it': [{'i': 1, 'ti': 'Pass'}, {'i': 2, 'ti': 'Possession lost'}]}}
    users = []
    for index, name in enumerate(['Anna', 'Ben', 'Clara', 'David', 'Emil']):
        mid, ids = str(index + 1), [str(index * 11 + p + 1) for p in range(11)]
        users.append({'i': mid, 'n': name, 'sp': 10000 - index * 500, 'spl': index + 1, 'mdp': 1000 - index * 100})
        responses[f'/leagues/l/managers/{mid}/dashboard'] = {'tv': 230000000 + index * 10000000, 'mdw': index,
                                                           'ap': 1120}
        responses[f'/leagues/l/managers/{mid}/squad'] = {'it': [
            {'pi': pid, 'pn': ['Schlotterbeck', 'Kimmich', 'Mittelst\u00e4dt', 'Kane'][j % 4], 'lo': j,
             'pos': ([1] + [2] * 4 + [3] * 4 + [4] * 2)[j], 'ap': 110 + j, 'tfhmvt': 10000,
             'pim': 'https://images.test/player.svg'} for j, pid in enumerate(ids)]}
        for day in [8, 9]:
            responses[f'/leagues/l/users/{mid}/teamcenter?dayNumber={day}'] = {
                'us': [{'i': mid, 'lp': ids, 'mdp': 1000 - index * 100}],
                'lp': [{'i': pid, 'n': ['Schlotterbeck', 'Kimmich', 'Mittelst\u00e4dt', 'Kane'][j % 4],
                        'p': j * 10 - index * 5, 'mi': 100, 'pim': 'https://images.test/player.svg'} for j, pid in enumerate(ids)] if day == 8 else []}
            for pid in ids:
                responses[f'/competitions/1/playercenter/{pid}?dayNumber={day}&leagueId=l'] = {
                    'i': pid, 'n': 'Testspieler', 'mi': 100, 'p': 10, 'events': [
                        {'ei': 'correction', 'eti': 1, 'p': -1, 'mt': 20, 'cei': 'pass', 'att': 3},
                        {'ei': 'lost', 'eti': 2, 'p': -1, 'mt': 70},
                        {'ei': 'pass', 'eti': 1, 'p': 12, 'mt': 20}]}
    for day in [8, 9]:
        responses[f'/leagues/l/ranking?dayNumber={day}'] = {'ti': 'Unsere Bundesliga', 'us': users}
    client = Mock()
    client.get.side_effect = lambda path: responses[path]
    server = create_server(0, {'players': [], 'league': 'l'})
    server.kickbase = client
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        return subprocess.run(['node', 'tests/live_matchday_browser.cjs'],
                              env={**os.environ, 'LIVE_TEST_URL': server.origin}, timeout=120).returncode
    finally:
        server.shutdown(); server.server_close(); thread.join()


if __name__ == '__main__':
    raise SystemExit(main())
