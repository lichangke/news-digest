#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

TIMEOUT_SECONDS = 25
TARGET = "user:ou_846a1fe0812c0797c456361b253e1fbc"
CHANNEL = "feishu"


def main() -> int:
    if len(sys.argv) != 2:
        print(json.dumps({"ok": False, "error": "usage: send_news_notify.py <result.json>"}, ensure_ascii=False))
        return 0

    result_path = Path(sys.argv[1])
    data = json.loads(result_path.read_text(encoding="utf-8"))
    payload = data.get("notify_payload") or {}
    message = payload.get("message")
    if not message:
        out = {"ok": False, "skipped": True, "reason": "notify_payload_missing"}
        print(json.dumps(out, ensure_ascii=False))
        return 0

    try:
        proc = subprocess.run(
            [
                "openclaw",
                "message",
                "send",
                "--channel",
                CHANNEL,
                "--target",
                TARGET,
                "--message",
                message,
            ],
            capture_output=True,
            text=True,
            timeout=TIMEOUT_SECONDS,
            check=False,
        )
    except subprocess.TimeoutExpired:
        print(json.dumps({"ok": False, "error": f"notify timeout after {TIMEOUT_SECONDS}s", "timeout_seconds": TIMEOUT_SECONDS}, ensure_ascii=False))
        return 0

    stdout = (proc.stdout or "").strip()
    stderr = (proc.stderr or "").strip()
    ok = proc.returncode == 0
    print(json.dumps({"ok": ok, "exit_code": proc.returncode, "stdout": stdout, "stderr": stderr}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
