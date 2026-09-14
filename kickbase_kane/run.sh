#!/usr/bin/with-contenv bashio
set -euo pipefail

export KICKBASE_HOME_ASSISTANT=1
export KICKBASE_BIND_HOST=0.0.0.0
export KICKBASE_DATA_DIR=/data
export KICK_USER="$(bashio::config 'kick_user')"
export KICK_PASS="$(bashio::config 'kick_pass')"
export KICK_LEAGUE_NAME="$(bashio::config 'league_name')"
export OPENAI_API_KEY="$(bashio::config 'openai_api_key')"
export OPENAI_MODEL="$(bashio::config 'openai_model')"
export KICKBASE_REPORT_TIME="$(bashio::config 'report_time')"

python /app/addon_schedule_reports.py &
exec python /app/advisor_server.py --port 8099 --no-browser
