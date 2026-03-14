from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .wiki_sync import sync_markdown


def publish_to_wiki(run_type: str, channel: str, markdown_path: Path, *, target_dt=None, enabled: bool = True) -> dict[str, Any]:
    if not enabled:
        return {"ok": False, "skipped": True}
    return sync_markdown(run_type, channel, markdown_path, target_dt=target_dt)


def build_notify_payload(run_type: str, channel: str, wiki_sync_result: dict[str, Any]) -> dict[str, Any]:
    if wiki_sync_result.get("ok") and wiki_sync_result.get("url"):
        return {
            "message": f"{channel} {'早间' if run_type == 'morning' else '晚间'}新闻已生成：{wiki_sync_result['url']}",
            "url": wiki_sync_result["url"],
        }
    return {}


def record_notify_result(result_path: str | Path, notify_result: dict[str, Any]) -> None:
    path = Path(result_path)
    data = json.loads(path.read_text(encoding="utf-8"))
    data.setdefault("stages", {})["notify"] = notify_result
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
