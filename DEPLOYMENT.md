# Web deployment

## Recommended setup

Use the wint.global package for the public website and mail domain, and run the
Kickbase application on a small Linux VPS. The application needs a persistent
Python process, outbound HTTPS requests to Kickbase, a writable data directory,
and a reverse proxy with TLS. A normal shared-hosting PHP process is not enough.

Recommended routing:

```text
bastiwe.de                 existing website
app.bastiwe.de             Kickbase application / reverse proxy
```

The browser must only talk to `app.bastiwe.de`. Kickbase credentials and API
tokens stay on the server and are never embedded into HTML or JavaScript.

## Required server configuration

Install Python 3.11+, create a virtual environment, and install:

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
```

Create an environment file outside the repository or protect it with file
permissions:

```dotenv
KICK_USER=...
KICK_PASS=...
OPENAI_API_KEY=...
OPENAI_MODEL=gpt-5-mini
```

The current local server can be used behind a reverse proxy during the first
deployment. It must listen only on `127.0.0.1`; Nginx or Caddy terminates TLS
and forwards requests to it. A production login/session layer is required
before exposing it to more than one trusted user.

## DNS and TLS

Create an `A` or `AAAA` record for `app.bastiwe.de` pointing to the VPS. Keep
`bastiwe.de` pointed at the existing wint.global webspace. Issue a Let's Encrypt
certificate for `app.bastiwe.de` and redirect HTTP to HTTPS.

## Data ownership

The optimizer should load these values live from Kickbase: squad, budget,
lineup, market, bids, player status, market value, points, match history and
club limits. The report/cache is only needed for values Kickbase does not
provide historically or directly: 1T/3T/7T market forecasts, model history,
backtests and overpay analysis.

Before public deployment, add a real application authentication layer, rate
limiting, encrypted session cookies, automatic token expiry and a privacy notice.
