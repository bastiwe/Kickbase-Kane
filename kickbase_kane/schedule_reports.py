"""Run one full forecast daily without blocking the Home Assistant add-on."""

from datetime import datetime, timedelta
import os
from pathlib import Path
import subprocess
import time
from zoneinfo import ZoneInfo


APP_ROOT = Path('/app')
DATA_ROOT = Path(os.getenv('KICKBASE_DATA_DIR', '/data'))


def next_run(now, schedule):
    hour, minute = (int(value) for value in schedule.split(':'))
    target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    return target if target > now else target + timedelta(days=1)


def main():
    schedule = os.getenv('KICKBASE_REPORT_TIME', '22:15')
    while True:
        now = datetime.now(ZoneInfo('Europe/Berlin'))
        target = next_run(now, schedule)
        time.sleep(max(1, (target - now).total_seconds()))
        DATA_ROOT.mkdir(parents=True, exist_ok=True)
        with (DATA_ROOT / '.scheduled-report.log').open('a', encoding='utf-8') as log:
            log.write(f'\n[{datetime.now(ZoneInfo("Europe/Berlin")).isoformat()}] Vollreport gestartet.\n')
            try:
                result = subprocess.run(['python', '-u', str(APP_ROOT / 'daily_predictions_spaet.py')],
                                        cwd=DATA_ROOT, env=os.environ.copy(), stdout=log,
                                        stderr=subprocess.STDOUT, timeout=3600)
                log.write(f'Vollreport beendet: Exit {result.returncode}.\n')
            except (OSError, subprocess.TimeoutExpired) as exc:
                # A failed run must not stop the scheduler for the following day.
                log.write(f'Vollreport fehlgeschlagen: {type(exc).__name__}.\n')


if __name__ == '__main__':
    main()
