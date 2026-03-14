from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from .channels import get_channel_strategy
from .config import load_config
from .dedupe import dedupe_items
from .fetchers import fetch_candidate_news, make_demo_items
from .publishers import build_notify_payload, publish_to_wiki
from .render import render_markdown
from .storage import article_exists, get_conn, save_articles
from .time_window import get_time_window
from .wiki_sync import ensure_node_path


RUN_TYPE_LABELS = {
    "morning": "早间",
    "evening": "晚间",
}

BASE_DIR = Path(__file__).resolve().parent.parent
RUNS_DIR = BASE_DIR / "runs"
LOGS_DIR = BASE_DIR / "logs"


def _iso_now(tzinfo) -> str:
    return datetime.now(tzinfo).isoformat()


def _write_debug_log(run_type: str, channel: str, run_date: str, candidates, deduped, final_items, existed_items, tz_name: str, ignore_state: bool) -> Path:
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    debug_path = LOGS_DIR / f"{channel}-{run_type}-{datetime.now().strftime('%Y%m%d-%H%M%S')}.debug.md"

    lines: list[str] = []
    lines.append(f"# Debug · {run_date} · {channel} · {run_type}")
    lines.append("")
    lines.append(f"- timezone: {tz_name}")
    lines.append(f"- ignore_state: {ignore_state}")
    lines.append(f"- candidates_raw: {len(candidates)}")
    lines.append(f"- after_dedupe: {len(deduped)}")
    lines.append(f"- existed_in_state: {len(existed_items)}")
    lines.append(f"- final_output: {len(final_items)}")
    lines.append("")
    lines.append("## Final items")
    if final_items:
        for item in final_items[:50]:
            lines.append(f"- [{item.source_adapter or 'unknown'}] {item.source} | {item.published_at:%Y-%m-%d %H:%M} | {item.title}")
    else:
        lines.append("- none")
    lines.append("")
    debug_path.write_text("\n".join(lines), encoding="utf-8")
    return debug_path


def build_result(run_type: str, channel: str, *, ignore_state: bool = False, sync_wiki_enabled: bool = True, demo: bool = False) -> dict[str, Any]:
    config = load_config()
    tz_name = config["timezone"]
    channel_config = config["channels"][channel]
    channel_strategy = get_channel_strategy(channel)
    start_at, end_at = get_time_window(run_type, tz_name)
    run_date = start_at.strftime("%Y-%m-%d")
    started_at = _iso_now(start_at.tzinfo)

    result: dict[str, Any] = {
        "ok": True,
        "run_type": run_type,
        "channel": channel,
        "timezone": tz_name,
        "run_date": run_date,
        "window": {
            "start": start_at.isoformat(),
            "end": end_at.isoformat(),
        },
        "ignore_state": ignore_state,
        "sync_wiki_requested": sync_wiki_enabled,
        "started_at": started_at,
        "stages": {
            "collect": {"ok": False},
            "wiki_sync": {"ok": False, "skipped": not sync_wiki_enabled},
            "notify": {"ok": False, "skipped": True},
        },
    }

    try:
        candidates = make_demo_items(tz_name) if demo else fetch_candidate_news(channel, start_at, end_at, channel_config, tz_name)
        deduped = dedupe_items(candidates, title_threshold=config["dedupe"]["title_similarity_threshold"])

        conn = get_conn()
        if ignore_state:
            existed_items = []
            final_items = list(deduped)
        else:
            existed_items = [item for item in deduped if article_exists(conn, run_date, item.event_fingerprint)]
            final_items = [item for item in deduped if not article_exists(conn, run_date, item.event_fingerprint)]
        final_items = final_items[: channel_config.get("max_items", config["max_items"])]

        markdown = render_markdown(f"{RUN_TYPE_LABELS[run_type]}·{channel_config.get('label', channel)}", start_at, end_at, final_items)
        LOGS_DIR.mkdir(parents=True, exist_ok=True)
        markdown_path = LOGS_DIR / f"{channel}-{run_type}-{datetime.now().strftime('%Y%m%d-%H%M%S')}.md"
        markdown_path.write_text(markdown, encoding="utf-8")
        debug_path = _write_debug_log(run_type, channel, run_date, candidates, deduped, final_items, existed_items, tz_name, ignore_state)

        if final_items and not ignore_state:
            save_articles(conn, run_date, run_type, final_items)

        wiki_plan = ensure_node_path(run_type, channel, end_at)
        result["channel_strategy"] = {
            "name": channel_strategy.name,
            "label_fallback": channel_strategy.label_fallback,
        }
        result["counts"] = {
            "candidates": len(candidates),
            "deduped": len(deduped),
            "existed": len(existed_items),
            "selected": len(final_items),
        }
        result["artifacts"] = {
            "markdown_output": str(markdown_path),
            "debug_output": str(debug_path),
        }
        result["wiki_plan"] = {
            "doc_title": wiki_plan["doc_title"],
            "year": wiki_plan["year_title"],
            "month": wiki_plan["month_title"],
            "target_date": wiki_plan["target_date"],
        }
        result["stages"]["collect"] = {"ok": True}

        result["stages"]["wiki_sync"] = publish_to_wiki(
            run_type,
            channel,
            markdown_path,
            target_dt=end_at,
            enabled=sync_wiki_enabled,
        )
        result["stages"]["wiki_sync"].setdefault("ok", False)

        result["notify_payload"] = build_notify_payload(run_type, channel, result["stages"]["wiki_sync"])
        if result["notify_payload"]:
            result["stages"]["notify"] = {"ok": False, "skipped": False, "ready": True}
        else:
            result["stages"]["notify"] = {"ok": False, "skipped": True, "reason": "wiki_url_unavailable"}

    except Exception as exc:
        result["ok"] = False
        result["error"] = str(exc)

    result["finished_at"] = _iso_now(start_at.tzinfo)
    return result


def save_result(result: dict[str, Any]) -> Path:
    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    path = RUNS_DIR / f"{ts}-{result['channel']}-{result['run_type']}.json"
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-type", choices=["morning", "evening"], required=True)
    parser.add_argument("--channel", choices=["general", "ai"], required=True)
    parser.add_argument("--ignore-state", action="store_true")
    parser.add_argument("--no-sync-wiki", action="store_true")
    parser.add_argument("--demo", action="store_true")
    args = parser.parse_args()

    result = build_result(
        args.run_type,
        args.channel,
        ignore_state=args.ignore_state,
        sync_wiki_enabled=not args.no_sync_wiki,
        demo=args.demo,
    )
    result_path = save_result(result)
    print(json.dumps({"ok": result.get("ok", False), "result_path": str(result_path)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
