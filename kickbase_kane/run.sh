#!/usr/bin/with-contenv bashio
set -euo pipefail

export KICKBASE_HOME_ASSISTANT=1
export KICKBASE_BIND_HOST=0.0.0.0
export KICKBASE_DATA_DIR=/data
export KICK_USER="$(bashio::config 'kick_user')"
export KICK_PASS="$(bashio::config 'kick_pass')"
export KICK_LEAGUE_NAME="$(bashio::config 'league_name')"
export EMAIL_USER="$(bashio::config 'email_user')"
export EMAIL_PASS="$(bashio::config 'email_pass')"
export OPENAI_API_KEY="$(bashio::config 'openai_api_key')"
export OPENAI_MODEL="$(bashio::config 'openai_model')"
export KICKBASE_REPORT_TIMES="$(bashio::config 'report_times')"
export GITHUB_FORECAST_TOKEN="$(bashio::config 'github_forecast_token')"
export GITHUB_FORECAST_REPOSITORY="$(bashio::config 'github_forecast_repository')"
export GITHUB_FORECAST_SYNC_SECONDS="$(bashio::config 'github_forecast_sync_seconds')"

# The Pi keeps the two useful forecast horizons (1T and 3T) but trains them
# one CPU worker at a time. This avoids a memory spike when three forests are
# kept for the full report; GitHub Actions keep their normal defaults.
export MODEL_N_ESTIMATORS="${MODEL_N_ESTIMATORS:-250}"
export MODEL_N_JOBS="${MODEL_N_JOBS:-1}"
export FULL_REPORT_INCLUDE_7D="${FULL_REPORT_INCLUDE_7D:-0}"

# Existing installations may not have the newly introduced report_times setting
# until their configuration has been saved once after the update.
if [ -z "$KICKBASE_REPORT_TIMES" ] || [ "$KICKBASE_REPORT_TIMES" = "null" ]; then
  export KICKBASE_REPORT_TIMES="21:40,22:10"
fi
if [ -z "$GITHUB_FORECAST_SYNC_SECONDS" ] || [ "$GITHUB_FORECAST_SYNC_SECONDS" = "null" ]; then
  export GITHUB_FORECAST_SYNC_SECONDS="300"
fi

# The dashboard establishes its live context directly from Kickbase on first
# page load. Forecast snapshots are filled by scheduled or manual reports.
cd /data

if [ -n "$GITHUB_FORECAST_TOKEN" ] && [ "$GITHUB_FORECAST_TOKEN" != "null" ]; then
  bashio::log.info "GitHub-Prognose-Sync aktiv; lokale Modellberechnung ist deaktiviert."
  python /app/features/github_forecast_sync.py &
else
  bashio::log.info "Kein GitHub-Prognose-Token konfiguriert; lokale Vollreports bleiben aktiv."
  python /app/addon_schedule_reports.py &
fi
exec python /app/advisor_server.py --port 8099 --no-browser
