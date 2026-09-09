"""Exercise the real local HTTP server with a mocked, non-billable AI call."""
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from advisor_server import create_server
from test_ai_advisor import fixture


def main():
    report, _ = fixture()
    report.update(league='test', user='test', forecast=None, forecastHorizon=None)
    for p in report['players']:
        p.update(image='', status='Fit', average=None, change=None, li=None, bid=None)
    folder = Path('test-output')
    folder.mkdir(exist_ok=True)
    file = folder / 'advisor-report.html'
    file.write_text('<script id="data">'+json.dumps(report)+'</script>', encoding='utf-8')
    server = create_server(0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    calls = []

    def answer(key, model, context, message, history):
        calls.append(context['currentPlan']['budget'])
        return {'answer': 'Testantwort: <script>window.bad = true</script> Budget '
                + str(context['checkedCurrentPlan']['endBudget'])}

    try:
        with patch('advisor_server.ask_advisor', side_effect=answer):
            result = subprocess.run(['node', 'tests/advisor_browser.cjs'], env={**os.environ,
                                    'ADVISOR_TEST_URL': server.origin, 'ADVISOR_TEST_REPORT': str(file.resolve())})
            if result.returncode:
                raise SystemExit(result.returncode)
            assert calls == [50, -100], calls
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


if __name__ == '__main__':
    main()
