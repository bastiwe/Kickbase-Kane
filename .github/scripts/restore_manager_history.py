"""Restore the latest cumulative manager-history artifact."""
from io import BytesIO
import os
from pathlib import Path
import sqlite3
import zipfile

import requests


def main():
    session = requests.Session()
    session.headers.update(Authorization='Bearer ' + os.environ['GH_TOKEN'],
                           Accept='application/vnd.github+json')
    url = f"https://api.github.com/repos/{os.environ['GITHUB_REPOSITORY']}/actions/artifacts"
    response = session.get(url, params={'name': 'manager-history', 'per_page': 100}, timeout=30)
    response.raise_for_status()
    artifacts = [item for item in response.json().get('artifacts', []) if not item.get('expired')]
    if not artifacts:
        print('Kein bestehendes Managerarchiv; Erstaufbau aus der API.')
        return
    latest = max(artifacts, key=lambda item: (item['created_at'], item['id']))
    response = session.get(latest['archive_download_url'], timeout=60)
    response.raise_for_status()
    with zipfile.ZipFile(BytesIO(response.content)) as archive:
        names = [name for name in archive.namelist() if name == 'manager_history.sqlite3']
        if len(names) != 1:
            raise ValueError('Archiv enthält nicht genau manager_history.sqlite3')
        temporary = Path('manager_history.restore')
        temporary.write_bytes(archive.read(names[0]))
    with sqlite3.connect(temporary) as database:
        if database.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
            raise ValueError('Managerarchiv ist beschädigt')
    temporary.replace('manager_history.sqlite3')
    print('Managerarchiv wiederhergestellt:', latest['created_at'])


if __name__ == '__main__':
    main()
