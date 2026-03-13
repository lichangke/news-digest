#!/usr/bin/env bash
set -euo pipefail
CRON_TMP=$(mktemp)
crontab -l 2>/dev/null > "$CRON_TMP" || true
sed -i '/news-digest\/scripts\/run_morning.sh/d' "$CRON_TMP"
sed -i '/news-digest\/scripts\/run_evening.sh/d' "$CRON_TMP"
echo "0 8 * * * /root/.openclaw/workspace/news-digest/scripts/run_morning.sh" >> "$CRON_TMP"
echo "0 17 * * * /root/.openclaw/workspace/news-digest/scripts/run_evening.sh" >> "$CRON_TMP"
crontab "$CRON_TMP"
rm -f "$CRON_TMP"
echo "Cron installed: 08:00 morning, 17:00 evening (Asia/Shanghai via host cron timezone)."
