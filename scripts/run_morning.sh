#!/usr/bin/env bash
set -euo pipefail
cd /root/.openclaw/workspace/news-digest
mkdir -p logs
if [ ! -x .venv/bin/python ]; then
  echo "Missing virtualenv. Run scripts/setup_venv.sh first." >&2
  exit 1
fi
LOG_FILE="logs/morning.log"
run_and_push() {
  local channel="$1"
  local output
  output=$(.venv/bin/python -m app.main --run-type morning --channel "$channel" --sync-wiki 2>&1)
  printf '%s\n' "$output" >> "$LOG_FILE"
  local url
  url=$(printf '%s\n' "$output" | sed -n 's/^wiki_doc_url=//p' | tail -n 1)
  if [ -n "$url" ]; then
    openclaw message send --channel feishu --target user:ou_846a1fe0812c0797c456361b253e1fbc --message "${channel} 早间新闻已生成：$url" >/dev/null 2>&1 || true
  fi
}
run_and_push general
run_and_push ai
