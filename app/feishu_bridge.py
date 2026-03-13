from __future__ import annotations

import json
import subprocess
from pathlib import Path
from tempfile import NamedTemporaryFile


BRIDGE_SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "feishu_doc_bridge.py"


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
    result = subprocess.run(
        ["python3", str(BRIDGE_SCRIPT), temp_path],
        capture_output=True,
        text=True,
        check=True,
    )
    return json.loads(result.stdout)
