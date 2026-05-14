#!/usr/bin/env bash
# Deploy script for the transcript-insights dashboard.
# Usage: ./deploy.sh
#
# What it does:
#   1. git pull origin master
#   2. Stops ONLY this app's uvicorn process (uses a PID file, falls back to
#      matching the unique module path "app.main:app"). Other uvicorn
#      processes on the server (e.g. voicebot.app.main:app) are NOT touched.
#   3. Restarts it in the background, logging to logs/app.log.

set -euo pipefail

# --- Config -----------------------------------------------------------------
APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_MODULE="app.main:app"          # unique to this project (voicebot uses voicebot.app.main:app)
HOST="0.0.0.0"
PORT="8000"
VENV_PY="${APP_DIR}/.venv/bin/python"
PID_FILE="${APP_DIR}/.app.pid"
LOG_DIR="${APP_DIR}/logs"
LOG_FILE="${LOG_DIR}/app.log"
BRANCH="master"

mkdir -p "${LOG_DIR}"
cd "${APP_DIR}"

echo "==> [1/3] git pull origin ${BRANCH}"
git pull origin "${BRANCH}"

echo "==> [2/3] Stopping any running instance of ${APP_MODULE}"
stop_pid() {
    local pid="$1"
    if [ -n "${pid}" ] && kill -0 "${pid}" 2>/dev/null; then
        echo "    Killing PID ${pid}"
        kill "${pid}" 2>/dev/null || true
        # wait up to 10s for graceful shutdown
        for _ in $(seq 1 10); do
            if ! kill -0 "${pid}" 2>/dev/null; then
                return 0
            fi
            sleep 1
        done
        echo "    PID ${pid} did not exit, sending SIGKILL"
        kill -9 "${pid}" 2>/dev/null || true
    fi
}

# 2a. Stop via PID file if it exists
if [ -f "${PID_FILE}" ]; then
    stop_pid "$(cat "${PID_FILE}")"
    rm -f "${PID_FILE}"
fi

# 2b. Safety net: also kill any leftover uvicorn whose command line contains
#     the EXACT module string. This avoids touching the voicebot or other apps.
LEFTOVER_PIDS="$(pgrep -f "uvicorn ${APP_MODULE}" || true)"
if [ -n "${LEFTOVER_PIDS}" ]; then
    for pid in ${LEFTOVER_PIDS}; do
        stop_pid "${pid}"
    done
fi

echo "==> [3/3] Starting ${APP_MODULE} on ${HOST}:${PORT}"
# Use nohup + setsid so the process survives the shell exiting.
nohup "${VENV_PY}" -m uvicorn "${APP_MODULE}" \
    --host "${HOST}" --port "${PORT}" \
    >> "${LOG_FILE}" 2>&1 &
NEW_PID=$!
echo "${NEW_PID}" > "${PID_FILE}"
disown || true

sleep 2
if kill -0 "${NEW_PID}" 2>/dev/null; then
    echo "==> Started successfully (PID ${NEW_PID}). Logs: ${LOG_FILE}"
else
    echo "!! Process exited immediately. Check ${LOG_FILE}" >&2
    exit 1
fi
