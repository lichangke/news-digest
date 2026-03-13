#!/usr/bin/env bash
set -euo pipefail
cd /root/.openclaw/workspace/news-digest
python3 -m venv .venv
. .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
