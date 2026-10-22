"""Run full forecasts at configurable Berlin-time slots inside Home Assistant."""

from __future__ import annotations

from datetime import datetime, timedelta
import os
from pathlib import Path
import subprocess
import sys
import time
from typing import Iterable
from zoneinfo import ZoneInfo


APP_ROOT = Path("/app")
DATA_ROOT = Path(os.getenv("KICKBASE_DATA_DIR", "/data"))
BERLIN = ZoneInfo("Europe/Berlin")
DEFAULT_REPORT_TIMES = ("21:40", "22:10")
RUN_TIMEOUT_SECONDS = 60 * 60


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


def run_report() -> None:
    DATA_ROOT.mkdir(parents=True, exist_ok=True)
    log_path = DATA_ROOT / "scheduled-report.log"
    with log_path.open("a", encoding="utf-8") as log:
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
            return
        except OSError as exc:
            write_log(f"Vollreport konnte nicht gestartet werden: {exc}.", log)
            return

        if result.returncode == 0:
            write_log("Vollreport erfolgreich beendet.", log)
        else:
            write_log(f"Vollreport beendet mit Exit-Code {result.returncode}. Details stehen oberhalb.", log)


def main() -> None:
    slots = parse_report_times(os.getenv("KICKBASE_REPORT_TIMES"))
    readable_slots = ", ".join(f"{hour:02d}:{minute:02d}" for hour, minute in slots)
    print(f"Kickbase-Planer aktiv. Vollreport taeglich um {readable_slots} (Europe/Berlin).", flush=True)

    while True:
        now = datetime.now(BERLIN)
        target = next_run(now, slots)
        seconds = max(1, (target - now).total_seconds())
        print(f"Naechster Vollreport: {target.strftime('%Y-%m-%d %H:%M %Z')}.", flush=True)
        time.sleep(seconds)
        run_report()


if __name__ == "__main__":
    main()
