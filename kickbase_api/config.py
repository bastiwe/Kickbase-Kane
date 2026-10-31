import requests
import random
import threading
import time
from email.utils import parsedate_to_datetime
from datetime import datetime, timezone

BASE_URL = "https://api.kickbase.com/v4"
CDN_BASE_URL = "https://kickbase.b-cdn.net"

def get_cdn_url(path):
    """Build an absolute Kickbase CDN URL from a relative image path."""

    if not path:
        return None
    if str(path).startswith(("http://", "https://")):
        return path
    return f"{CDN_BASE_URL}/{str(path).lstrip('/')}"

_request_lock = threading.Lock()
_next_request_at = 0.0
_MIN_INTERVAL_SECONDS = 0.5
_MAX_RETRIES = 5


def _retry_delay(response, attempt):
    header = response.headers.get("Retry-After")
    if header:
        try:
            return max(0.0, min(300.0, float(header)))
        except ValueError:
            try:
                retry_at = parsedate_to_datetime(header)
                if retry_at.tzinfo is None:
                    retry_at = retry_at.replace(tzinfo=timezone.utc)
                return max(0.0, min(300.0, (retry_at - datetime.now(timezone.utc)).total_seconds()))
            except (TypeError, ValueError, OverflowError):
                pass
    return min(60.0, 2.0 * (2 ** attempt)) + random.uniform(0, 1)


def get_json_with_token(url, token):
    """Fetch JSON data from a given URL using token for authorization."""

    headers = {"Authorization": f"Bearer {token}"}
    global _next_request_at
    # Serialize requests through this helper so concurrent workers share one limit.
    with _request_lock:
        for attempt in range(_MAX_RETRIES + 1):
            wait = _next_request_at - time.monotonic()
            if wait > 0:
                time.sleep(wait)
            _next_request_at = time.monotonic() + _MIN_INTERVAL_SECONDS
            resp = requests.get(url, headers=headers, timeout=30)
            if resp.status_code == 429 and attempt < _MAX_RETRIES:
                delay = _retry_delay(resp, attempt)
                print(f"Kickbase API 429; waiting {delay:.1f}s (retry {attempt + 1}/{_MAX_RETRIES}).")
                _next_request_at = max(_next_request_at, time.monotonic() + delay)
                continue
            resp.raise_for_status()
            return resp.json()
