#!/usr/bin/env bash
set -euo pipefail
cd /root/.openclaw/workspace/news-digest
mkdir -p logs
if [ ! -x .venv/bin/python ]; then
  echo "Missing virtualenv. Run scripts/setup_venv.sh first." >&2
  exit 1
fi
LOG_FILE="logs/evening.log"
notify() {
  local channel="$1"
  local url="$2"
  local response
  if response=$(openclaw message send --channel feishu --target user:ou_846a1fe0812c0797c456361b253e1fbc --message "${channel} 晚间新闻已生成：$url" 2>&1); then
    printf 'notify_status=ok channel=%s\n%s\n' "$channel" "$response" >> "$LOG_FILE"
  else
    printf 'notify_status=error channel=%s\n%s\n' "$channel" "$response" >> "$LOG_FILE"
  fi
}
run_and_push() {
  local channel="$1"
  local output
  output=$(.venv/bin/python -m app.main --run-type evening --channel "$channel" --sync-wiki 2>&1)
  printf '%s\n' "$output" >> "$LOG_FILE"
  local url
  url=$(printf '%s\n' "$output" | sed -n 's/^wiki_doc_url=//p' | tail -n 1)
  if [ -n "$url" ]; then
    notify "$channel" "$url"
  else
    printf 'notify_status=skip channel=%s reason=no_url\n' "$channel" >> "$LOG_FILE"
  fi
}
run_and_push general
run_and_push ai
