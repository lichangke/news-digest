#!/usr/bin/env bash
set -euo pipefail
cd /root/.openclaw/workspace/news-digest
if [ $# -ne 1 ]; then
  echo "usage: scripts/retry_notify.sh <runs/result.json>" >&2
  exit 1
fi
python3 scripts/send_news_notify.py "$1"
