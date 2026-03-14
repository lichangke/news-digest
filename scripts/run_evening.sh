#!/usr/bin/env bash
set -uo pipefail
cd /root/.openclaw/workspace/news-digest
mkdir -p logs
if [ ! -x .venv/bin/python ]; then
  echo "Missing virtualenv. Run scripts/setup_venv.sh first." >&2
  exit 1
fi
LOG_FILE="logs/evening.log"
PY_TIMEOUT="120s"
MSG_TIMEOUT="25s"
now() { date '+%Y-%m-%dT%H:%M:%S%z'; }
log() { printf '%s %s\n' "$(now)" "$*" >> "$LOG_FILE"; }
notify() {
  local channel="$1"
  local url="$2"
  local response
  log "notify_start channel=$channel"
  if response=$(timeout "$MSG_TIMEOUT" openclaw message send --channel feishu --target user:ou_846a1fe0812c0797c456361b253e1fbc --message "${channel} 晚间新闻已生成：$url" 2>&1); then
    log "notify_status=ok channel=$channel response=$(printf '%s' "$response" | tr '\n' ' ' | tr '\r' ' ')"
  else
    local status=$?
    log "notify_status=error channel=$channel exit_code=$status response=$(printf '%s' "$response" | tr '\n' ' ' | tr '\r' ' ')"
  fi
  log "notify_end channel=$channel"
}
run_and_push() {
  local channel="$1"
  local output=""
  local status=0
  log "run_start channel=$channel run_type=evening"
  if ! output=$(timeout "$PY_TIMEOUT" .venv/bin/python -m app.main --run-type evening --channel "$channel" --sync-wiki 2>&1); then
    status=$?
  fi
  printf '%s\n' "$output" >> "$LOG_FILE"
  if [ "$status" -ne 0 ]; then
    log "run_status=error channel=$channel exit_code=$status"
  else
    log "run_status=ok channel=$channel"
  fi
  local url
  url=$(printf '%s\n' "$output" | sed -n 's/^wiki_doc_url=//p' | tail -n 1)
  if [ -n "$url" ]; then
    notify "$channel" "$url"
  else
    local sync_status
    sync_status=$(printf '%s\n' "$output" | sed -n 's/^wiki_sync_status=//p' | tail -n 1)
    local sync_error
    sync_error=$(printf '%s\n' "$output" | sed -n 's/^wiki_sync_error=//p' | tail -n 1)
    log "notify_status=skip channel=$channel reason=no_url wiki_sync_status=${sync_status:-unknown} wiki_sync_error=${sync_error:-}"
  fi
  log "run_end channel=$channel run_type=evening"
}
run_and_push general
run_and_push ai
exit 0
