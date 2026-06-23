#!/bin/zsh

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
APP_DIR="$SCRIPT_DIR"
PID_FILE="/tmp/po_app_uvicorn.pid"
SUPERVISOR_PID_FILE="/tmp/po_app_supervisor.pid"
LOG_OUT="/tmp/po_app.out"
LOG_ERR="/tmp/po_app.err"

cd "$APP_DIR" || exit 1

tail_logs() {
  touch "$LOG_OUT" "$LOG_ERR"
  echo "PO Automation server is already supervised. Showing live logs..."
  tail -n 20 -f "$LOG_OUT" "$LOG_ERR"
}

server_is_reachable() {
  curl -s --max-time 2 http://localhost:8000/ >/dev/null 2>&1
}

if [ -f "$SUPERVISOR_PID_FILE" ]; then
  EXISTING_SUPERVISOR_PID=$(cat "$SUPERVISOR_PID_FILE" 2>/dev/null)
  if [ -n "$EXISTING_SUPERVISOR_PID" ] && kill -0 "$EXISTING_SUPERVISOR_PID" 2>/dev/null; then
    tail_logs
    exit 0
  fi
fi

echo $$ > "$SUPERVISOR_PID_FILE"
trap 'if [ "$(cat "$SUPERVISOR_PID_FILE" 2>/dev/null)" = "$$" ]; then rm -f "$SUPERVISOR_PID_FILE"; fi' EXIT INT TERM

touch "$LOG_OUT" "$LOG_ERR"
echo "Starting PO Automation supervisor from $APP_DIR"

while true; do
  if server_is_reachable; then
    echo "PO Automation server is already running on http://localhost:8000"
    sleep 5
    continue
  fi

  if [ -f "$PID_FILE" ]; then
    PID=$(cat "$PID_FILE" 2>/dev/null)
    if [ -n "$PID" ] && kill -0 "$PID" 2>/dev/null; then
      sleep 5
      continue
    fi
  fi

  echo "Launching uvicorn on http://0.0.0.0:8000" | tee -a "$LOG_OUT"
  ./.venv/bin/uvicorn app:app --host 0.0.0.0 --port 8000 >>"$LOG_OUT" 2>>"$LOG_ERR" &
  echo $! > "$PID_FILE"
  wait $!
  echo "uvicorn exited; restarting in 2 seconds..." | tee -a "$LOG_OUT"
  sleep 2
done
