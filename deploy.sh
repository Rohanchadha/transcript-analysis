#!/usr/bin/env bash
# Deploy script for the transcript-insights dashboard.
# Usage: ./deploy.sh
#
# What it does:
#   1. git pull origin master
#   2. Stops ONLY this app's uvicorn process. Identification is done by matching
#      BOTH the conda env python path AND the module string "app.main:app", so
#      no other uvicorn on the server (voicebot, other tenants) is touched.
#   3. Restarts it in the background, logging to logs/app.log.

set -euo pipefail

# --- Config -----------------------------------------------------------------
APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_MODULE="app.main:app"
HOST="0.0.0.0"
PORT="8000"
# Conda env python — this is the unique signature for THIS app on the server.
# Other apps live under different envs / venvs and will not match.
PY="/data/miniconda/miniconda3/envs/transcript/bin/python"
PID_FILE="${APP_DIR}/.app.pid"
LOG_DIR="${APP_DIR}/logs"
LOG_FILE="${LOG_DIR}/app.log"
BRANCH="master"

# Unique process signature: must contain BOTH the conda python path AND the
# module name. This guarantees we never touch a uvicorn started by another
# project (e.g. voicebot) even if it serves the same module name from a
# different working directory.
PROC_SIGNATURE="${PY}.*uvicorn.*${APP_MODULE}"

mkdir -p "${LOG_DIR}"
cd "${APP_DIR}"

echo "==> [1/3] git pull origin ${BRANCH}"
git pull origin "${BRANCH}"

echo "==> [2/3] Stopping any running instance matching: ${PROC_SIGNATURE}"
stop_pid() {
    local pid="$1"
    if [ -n "${pid}" ] && kill -0 "${pid}" 2>/dev/null; then
        # Final safety check: verify this PID still matches OUR signature
        # before killing. Protects against PID reuse by an unrelated process.
        local cmdline
        cmdline="$(tr '\0' ' ' < "/proc/${pid}/cmdline" 2>/dev/null || true)"
        if ! echo "${cmdline}" | grep -qE "${PROC_SIGNATURE}"; then
            echo "    Skipping PID ${pid}: cmdline does not match our signature"
            echo "      cmdline: ${cmdline}"
            return 0
        fi
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

# 2b. Safety net: also kill any leftover process whose full command line
#     matches BOTH the conda python path AND the uvicorn module string.
LEFTOVER_PIDS="$(pgrep -f "${PROC_SIGNATURE}" || true)"
if [ -n "${LEFTOVER_PIDS}" ]; then
    for pid in ${LEFTOVER_PIDS}; do
        stop_pid "${pid}"
    done
fi

echo "==> [3/3] Starting ${APP_MODULE} on ${HOST}:${PORT} via ${PY}"
# Use nohup + setsid so the process survives the shell exiting.
# NOTE: --reload is intentionally NOT used in production to avoid double processes.
nohup "${PY}" -m uvicorn "${APP_MODULE}" \
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
