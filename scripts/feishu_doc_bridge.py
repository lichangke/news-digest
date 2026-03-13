#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import re
import sys
import time
import uuid
from pathlib import Path
from typing import Any

import requests

WORKSPACE_DIR = Path(__file__).resolve().parents[2]
CONFIG_PATH = WORKSPACE_DIR / "news-digest" / "config" / "config.json"
ENV_PATH = WORKSPACE_DIR / ".env"
BASE_URL = "https://open.feishu.cn/open-apis"
KNOWN_DAILY_SUMMARY_NODE = "PoAgwUBlKi7z7WkEgFJczEfVnnJ"


def load_env() -> None:
    if not ENV_PATH.exists():
        return
    for line in ENV_PATH.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip())


def load_config() -> dict[str, Any]:
    return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))


def get_tenant_access_token() -> str:
    app_id = os.environ.get("FEISHU_APP_ID", "")
    app_secret = os.environ.get("FEISHU_APP_SECRET", "")
    if not app_id or not app_secret:
        raise RuntimeError("missing FEISHU_APP_ID / FEISHU_APP_SECRET")
    resp = requests.post(
        f"{BASE_URL}/auth/v3/tenant_access_token/internal",
        json={"app_id": app_id, "app_secret": app_secret},
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()
    if data.get("code") != 0:
        raise RuntimeError(f"tenant_access_token failed: {data}")
    return data["tenant_access_token"]


def api(method: str, path: str, token: str, *, params: dict | None = None, body: dict | None = None) -> dict[str, Any]:
    resp = requests.request(
        method,
        f"{BASE_URL}{path}",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json; charset=utf-8"},
        params=params,
        json=body,
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()
    if data.get("code") != 0:
        raise RuntimeError(f"api failed {path}: {data}")
    return data


def list_nodes(space_id: str, parent_node_token: str, token: str) -> list[dict[str, Any]]:
    data = api("GET", f"/wiki/v2/spaces/{space_id}/nodes", token, params={"parent_node_token": parent_node_token, "page_size": 50})
    return data.get("data", {}).get("items", [])


def find_child(space_id: str, parent_node_token: str, title: str, token: str) -> dict[str, Any] | None:
    for item in list_nodes(space_id, parent_node_token, token):
        if item.get("title") == title:
            return item
    return None


def build_unique_doc_title(space_id: str, parent_node_token: str, base_title: str, token: str) -> str:
    existing_titles = {item.get("title", "") for item in list_nodes(space_id, parent_node_token, token)}
    if base_title not in existing_titles:
        return base_title
    return f"{base_title}（重跑 {time.strftime('%H%M%S')}）"


def create_node(space_id: str, parent_node_token: str, title: str, token: str) -> dict[str, Any]:
    data = api(
        "POST",
        f"/wiki/v2/spaces/{space_id}/nodes",
        token,
        body={"parent_node_token": parent_node_token, "node_type": "origin", "obj_type": "docx", "title": title},
    )
    return data.get("data", {}).get("node", {})


def ensure_doc(space_id: str, year_title: str, month_title: str, doc_title: str, token: str) -> dict[str, Any]:
    year_node = find_child(space_id, KNOWN_DAILY_SUMMARY_NODE, year_title, token)
    if year_node is None:
        year_node = create_node(space_id, KNOWN_DAILY_SUMMARY_NODE, year_title, token)

    month_node = find_child(space_id, year_node["node_token"], month_title, token)
    if month_node is None:
        month_node = create_node(space_id, year_node["node_token"], month_title, token)

    unique_title = build_unique_doc_title(space_id, month_node["node_token"], doc_title, token)
    doc_node = create_node(space_id, month_node["node_token"], unique_title, token)
    return {"year_node": year_node, "month_node": month_node, "doc_node": doc_node, "doc_title": unique_title}


def make_text_elements(text: str) -> list[dict[str, Any]]:
    return [{"text_run": {"content": text}}]


def markdown_to_blocks(content: str) -> list[dict[str, Any]]:
    blocks: list[dict[str, Any]] = []
    for raw in content.splitlines():
        line = raw.rstrip()
        if not line:
            blocks.append({"block_type": 2, "text": {"elements": make_text_elements(" ")}})
            continue
        if line == "---":
            blocks.append({"block_type": 2, "text": {"elements": make_text_elements(" ")}})
            continue
        if line.startswith("# "):
            blocks.append({"block_type": 3, "heading1": {"elements": make_text_elements(line[2:].strip())}})
            continue
        if line.startswith("## "):
            blocks.append({"block_type": 4, "heading2": {"elements": make_text_elements(line[3:].strip())}})
            continue
        m = re.match(r"^(\d+)\.\s+(.*)$", line)
        if m:
            blocks.append({"block_type": 13, "ordered": {"elements": make_text_elements(m.group(2).strip())}})
            continue
        if line.startswith("- "):
            blocks.append({"block_type": 12, "bullet": {"elements": make_text_elements(line[2:].strip())}})
            continue
        blocks.append({"block_type": 2, "text": {"elements": make_text_elements(line)}})
    return blocks


def append_block_batch(doc_token: str, token: str, blocks: list[dict[str, Any]]) -> None:
    body = {"children": blocks, "index": -1, "client_token": str(uuid.uuid4())}
    last_error: Exception | None = None
    for attempt in range(4):
        try:
            api("POST", f"/docx/v1/documents/{doc_token}/blocks/{doc_token}/children", token, body=body)
            return
        except Exception as exc:
            last_error = exc
            if "429" not in str(exc):
                raise
            time.sleep(1.2 * (attempt + 1))
    raise RuntimeError(f"append_block_batch failed after retries: {last_error}")


def chunk_blocks(blocks: list[dict[str, Any]], batch_size: int = 20) -> list[list[dict[str, Any]]]:
    return [blocks[i:i + batch_size] for i in range(0, len(blocks), batch_size)]


def write_doc_content(doc_token: str, content: str, token: str) -> dict[str, Any]:
    blocks = markdown_to_blocks(content)
    batches = chunk_blocks(blocks)
    for batch in batches:
        append_block_batch(doc_token, token, batch)
        time.sleep(0.35)
    return {"ok": True, "batches": len(batches), "blocks": len(blocks)}


def handle_sync(payload: dict[str, Any]) -> dict[str, Any]:
    config = load_config()
    token = get_tenant_access_token()
    feishu = config["feishu"]
    space_id = feishu["wiki_space_id"]
    year_title = payload["year_title"]
    month_title = payload["month_title"]
    doc_title = payload["title"]
    content = payload["content"]

    ensured = ensure_doc(space_id, year_title, month_title, doc_title, token)
    doc_node = ensured["doc_node"]
    doc_token = doc_node["obj_token"]
    write_doc_content(doc_token, content, token)
    return {
        "ok": True,
        "space_id": space_id,
        "year_node_token": ensured["year_node"]["node_token"],
        "month_node_token": ensured["month_node"]["node_token"],
        "node_token": doc_node["node_token"],
        "doc_token": doc_token,
        "title": ensured["doc_title"],
        "url": f"https://feishu.cn/docx/{doc_token}",
    }


def main() -> int:
    load_env()
    payload_path = Path(sys.argv[1])
    payload = json.loads(payload_path.read_text(encoding="utf-8"))
    action = payload.get("action")
    try:
        if action == "sync_markdown":
            result = handle_sync(payload)
            print(json.dumps(result, ensure_ascii=False))
            return 0
        print(json.dumps({"ok": False, "error": "unsupported action", "action": action}, ensure_ascii=False))
        return 0
    except Exception as exc:
        print(json.dumps({"ok": False, "error": str(exc), "action": action}, ensure_ascii=False))
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
