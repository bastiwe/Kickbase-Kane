import requests

BASE_URL = "https://api.kickbase.com/v4"
CDN_BASE_URL = "https://kickbase.b-cdn.net"

def get_cdn_url(path):
    """Build an absolute Kickbase CDN URL from a relative image path."""

    if not path:
        return None
    if str(path).startswith(("http://", "https://")):
        return path
    return f"{CDN_BASE_URL}/{str(path).lstrip('/')}"

def get_json_with_token(url, token):
    """Fetch JSON data from a given URL using token for authorization."""

    headers = {"Authorization": f"Bearer {token}"}
    resp = requests.get(url, headers=headers)
    resp.raise_for_status()
    return resp.json()
