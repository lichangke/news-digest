#!/usr/bin/env bash
set -uo pipefail
cd /root/.openclaw/workspace/news-digest
mkdir -p logs runs
LOG_FILE="logs/morning.log"
PIPE_TIMEOUT="120s"
now() { date '+%Y-%m-%dT%H:%M:%S%z'; }
log() { printf '%s %s\n' "$(now)" "$*" >> "$LOG_FILE"; }
run_channel() {
  local channel="$1"
  local output=""
  local status=0
  local result_path=""
  local notify_json=""

  log "run_start channel=$channel run_type=morning"
  if ! output=$(timeout "$PIPE_TIMEOUT" .venv/bin/python -m app.pipeline --run-type morning --channel "$channel" 2>&1); then
    status=$?
  fi
  printf '%s\n' "$output" >> "$LOG_FILE"
  result_path=$(printf '%s\n' "$output" | python3 -c 'import json,sys; s=sys.stdin.read().strip().splitlines(); print(json.loads(s[-1]).get("result_path","") if s else "")' 2>/dev/null || true)

  if [ "$status" -ne 0 ]; then
    log "run_status=error channel=$channel exit_code=$status"
  else
    log "run_status=ok channel=$channel result_path=$result_path"
  fi

  if [ -n "$result_path" ] && [ -f "$result_path" ]; then
    notify_json=$(python3 scripts/send_news_notify.py "$result_path")
    printf '%s\n' "$notify_json" >> "$LOG_FILE"
    python3 - "$result_path" "$notify_json" <<'PY'
import json, sys
from app.publishers import record_notify_result
record_notify_result(sys.argv[1], json.loads(sys.argv[2]))
PY
    log "notify_recorded channel=$channel result_path=$result_path"
  else
    log "notify_status=skip channel=$channel reason=result_path_missing"
  fi

  log "run_end channel=$channel run_type=morning"
}
run_channel general
run_channel ai
exit 0
