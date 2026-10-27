"""Run full forecasts at configurable Berlin-time slots inside Home Assistant."""

from __future__ import annotations

from datetime import datetime, timedelta
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from typing import Iterable
from zoneinfo import ZoneInfo

from features.github_forecast_sync import dispatch_workflow


APP_ROOT = Path("/app")
DATA_ROOT = Path(os.getenv("KICKBASE_DATA_DIR", "/data"))
BERLIN = ZoneInfo("Europe/Berlin")
DEFAULT_REPORT_TIMES = ("06:30", "14:00", "22:10")
RUN_TIMEOUT_SECONDS = 60 * 60
START_GRACE = timedelta(minutes=15)
RETRY_DELAY = timedelta(minutes=5)
MAX_ATTEMPTS = 3


def parse_report_times(value: str | None) -> tuple[tuple[int, int], ...]:
    """Return valid, unique HH:MM slots in chronological order."""
    slots: set[tuple[int, int]] = set()
    for item in (value or "").split(","):
        candidate = item.strip()
        try:
            hour_text, minute_text = candidate.split(":", 1)
            hour, minute = int(hour_text), int(minute_text)
        except ValueError:
            continue
        if 0 <= hour <= 23 and 0 <= minute <= 59:
            slots.add((hour, minute))

    return tuple(sorted(slots)) or tuple(
        (int(hour), int(minute)) for hour, minute in (slot.split(":") for slot in DEFAULT_REPORT_TIMES)
    )


def next_run(now: datetime, slots: Iterable[tuple[int, int]]) -> datetime:
    candidates = [
        now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        for hour, minute in slots
    ]
    future = [candidate for candidate in candidates if candidate > now]
    return min(future) if future else min(candidates) + timedelta(days=1)


def write_log(message: str, log_file) -> None:
    timestamp = datetime.now(BERLIN).strftime("%Y-%m-%d %H:%M:%S %Z")
    line = f"[{timestamp}] {message}"
    print(line, flush=True)
    log_file.write(f"{line}\n")
    log_file.flush()


def run_report() -> bool:
    DATA_ROOT.mkdir(parents=True, exist_ok=True)
    log_path = DATA_ROOT / "scheduled-report.log"
    with log_path.open("a", encoding="utf-8") as log:
        token = os.getenv('GITHUB_FORECAST_TOKEN', '').strip()
        if token and token != 'null':
            try:
                dispatch_workflow(token, os.getenv('GITHUB_FORECAST_REPOSITORY') or 'bastiwe/Kickbase-Kane',
                                  'actions_spaet.yml')
            except RuntimeError as exc:
                write_log(f'GitHub-Vollreport konnte nicht angefordert werden: {exc}', log)
                return False
            write_log('GitHub-Vollreport angefordert. Berechnung und Mailversand erfolgen in GitHub Actions; '
                      'das Add-on übernimmt anschließend die Ergebnisse per Sync.', log)
            return True
        write_log("Vollreport gestartet.", log)
        try:
            result = subprocess.run(
                [sys.executable, "-u", str(APP_ROOT / "daily_predictions_spaet.py")],
                cwd=DATA_ROOT,
                env=os.environ.copy(),
                stdout=log,
                stderr=subprocess.STDOUT,
                timeout=RUN_TIMEOUT_SECONDS,
                check=False,
            )
        except subprocess.TimeoutExpired:
            write_log("Vollreport abgebrochen: Zeitlimit von 60 Minuten erreicht.", log)
            return False
        except OSError as exc:
            write_log(f"Vollreport konnte nicht gestartet werden: {exc}.", log)
            return False

        if result.returncode == 0:
            write_log("Vollreport erfolgreich beendet.", log)
        else:
            write_log(f"Vollreport beendet mit Exit-Code {result.returncode}. Details stehen oberhalb.", log)
        return result.returncode == 0


def run_due_report(now: datetime, slots: Iterable[tuple[int, int]]) -> bool:
    """Persist attempts so restarts do not dispatch an accepted slot twice."""
    candidates = [
        (now - timedelta(days=days)).replace(hour=hour, minute=minute, second=0, microsecond=0)
        for days in (0, 1) for hour, minute in slots
    ]
    due = [target for target in candidates if timedelta(0) <= now - target <= START_GRACE]
    if not due:
        return False
    target = max(due)
    key = target.strftime('%Y-%m-%d %H:%M')
    DATA_ROOT.mkdir(parents=True, exist_ok=True)
    path = DATA_ROOT / '.scheduled-report-state.json'
    try:
        state = json.loads(path.read_text(encoding='utf-8'))
    except FileNotFoundError:
        state = {}
    previous = state.get(key, {})
    if previous.get('status') in ('running', 'accepted') or previous.get('attempts', 0) >= MAX_ATTEMPTS:
        return False
    if previous.get('last_attempt') and now.timestamp() - previous['last_attempt'] < RETRY_DELAY.total_seconds():
        return False

    def save():
        temporary = path.with_suffix('.tmp')
        temporary.write_text(json.dumps(state), encoding='utf-8')
        temporary.replace(path)

    state = {k: v for k, v in state.items() if k[:10] >= (now - timedelta(days=2)).strftime('%Y-%m-%d')}
    state[key] = {'status': 'running', 'attempts': previous.get('attempts', 0) + 1,
                  'last_attempt': now.timestamp()}
    save()
    success = run_report()
    state[key]['status'] = 'accepted' if success else 'failed'
    save()
    return success


def main() -> None:
    slots = parse_report_times(os.getenv("KICKBASE_REPORT_TIMES"))
    readable_slots = ", ".join(f"{hour:02d}:{minute:02d}" for hour, minute in slots)
    print(f"Kickbase-Planer aktiv. Vollreport taeglich um {readable_slots} (Europe/Berlin).", flush=True)

    while True:
        now = datetime.now(BERLIN)
        target = next_run(now, slots)
        try:
            run_due_report(now, slots)
        except (OSError, ValueError, TypeError) as exc:
            print(f'Kickbase-Planer: Zeitsteuerung fehlgeschlagen: {exc}', flush=True)
        if target != getattr(main, 'last_target', None):
            print(f"Naechster Vollreport: {target.strftime('%Y-%m-%d %H:%M %Z')}.", flush=True)
            main.last_target = target
        # Recheck Berlin wall time regularly, including DST and clock changes.
        time.sleep(30)


if __name__ == "__main__":
    main()
