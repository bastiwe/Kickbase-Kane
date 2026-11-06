"""Import HA observations passed through workflow_dispatch, without shell interpolation."""
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from features.history_sync import import_payload

count = import_payload(os.environ['HISTORY_PAYLOAD'], 'manager_history.sqlite3')
print(f'{count} HA-Historienbeobachtungen zusammengeführt.')
