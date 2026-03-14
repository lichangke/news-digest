from __future__ import annotations

import json
import subprocess
from pathlib import Path
from tempfile import NamedTemporaryFile


BRIDGE_SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "feishu_doc_bridge.py"
BRIDGE_TIMEOUT_SECONDS = 90


def sync_markdown(title: str, year_title: str, month_title: str, content: str) -> dict:
    payload = {
        "action": "sync_markdown",
        "title": title,
        "year_title": year_title,
        "month_title": month_title,
        "content": content,
    }
    return _call_bridge(payload)


def _call_bridge(payload: dict) -> dict:
    with NamedTemporaryFile("w", encoding="utf-8", delete=False) as f:
        json.dump(payload, f, ensure_ascii=False)
        temp_path = f.name
    try:
        result = subprocess.run(
            ["python3", str(BRIDGE_SCRIPT), temp_path],
            capture_output=True,
            text=True,
            check=True,
            timeout=BRIDGE_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired:
        return {
            "ok": False,
            "error": f"bridge timeout after {BRIDGE_TIMEOUT_SECONDS}s",
            "timeout_seconds": BRIDGE_TIMEOUT_SECONDS,
        }
    stdout = (result.stdout or "").strip()
    stderr = (result.stderr or "").strip()
    if not stdout:
        return {"ok": False, "error": "bridge returned empty stdout", "stderr": stderr}
    try:
        data = json.loads(stdout)
    except json.JSONDecodeError:
        return {"ok": False, "error": "bridge returned invalid json", "stdout": stdout, "stderr": stderr}
    if stderr:
        data.setdefault("bridge_stderr", stderr)
    return data
