#!/usr/bin/env bash
set -euo pipefail
cd /root/.openclaw/workspace/news-digest
if [ $# -ne 2 ]; then
  echo "usage: scripts/latest_run.sh <morning|evening> <general|ai>" >&2
  exit 1
fi
run_type="$1"
channel="$2"
latest=$(ls -1t runs/*-"$channel"-"$run_type".json 2>/dev/null | head -1 || true)
if [ -z "$latest" ]; then
  echo "" >&2
  exit 1
fi
printf '%s\n' "$latest"
