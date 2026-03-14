from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime
from pathlib import Path

from .config import load_config
from .dedupe import dedupe_items
from .fetchers import fetch_candidate_news, make_demo_items
from .render import render_markdown
from .storage import article_exists, get_conn, save_articles
from .time_window import get_time_window
from .wiki_sync import ensure_node_path, sync_markdown


RUN_TYPE_LABELS = {
    "morning": "早间",
    "evening": "晚间",
}


def _write_debug_log(run_type: str, channel: str, run_date: str, candidates, deduped, final_items, existed_items, tz_name: str, ignore_state: bool) -> Path:
    output_dir = Path(__file__).resolve().parent.parent / "logs"
    output_dir.mkdir(parents=True, exist_ok=True)
    debug_path = output_dir / f"{channel}-{run_type}-{datetime.now().strftime('%Y%m%d-%H%M%S')}.debug.md"

    source_counter = Counter(item.source for item in candidates)
    adapter_counter = Counter((item.source_adapter or "unknown") for item in candidates)

    lines = []
    lines.append(f"# Debug · {run_date} · {channel} · {run_type}")
    lines.append("")
    lines.append(f"- timezone: {tz_name}")
    lines.append(f"- ignore_state: {ignore_state}")
    lines.append(f"- candidates_raw: {len(candidates)}")
    lines.append(f"- after_dedupe: {len(deduped)}")
    lines.append(f"- existed_in_state: {len(existed_items)}")
    lines.append(f"- final_output: {len(final_items)}")
    lines.append("")

    lines.append("## Raw candidates by adapter")
    for name, count in adapter_counter.most_common():
        lines.append(f"- {name}: {count}")
    lines.append("")

    lines.append("## Raw candidates by source")
    for name, count in source_counter.most_common():
        lines.append(f"- {name}: {count}")
    lines.append("")

    lines.append("## Deduped items")
    for item in deduped[:50]:
        lines.append(f"- [{item.source_adapter or 'unknown'}] {item.source} | {item.published_at:%Y-%m-%d %H:%M} | {item.title}")
    lines.append("")

    lines.append("## Removed by state(existing fingerprint)")
    if existed_items:
        for item in existed_items[:50]:
            lines.append(f"- [{item.source_adapter or 'unknown'}] {item.source} | {item.published_at:%Y-%m-%d %H:%M} | {item.title}")
    else:
        lines.append("- none")
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


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-type", choices=["morning", "evening"], required=True)
    parser.add_argument("--channel", choices=["general", "ai"], default="general")
    parser.add_argument("--demo", action="store_true")
    parser.add_argument("--ignore-state", action="store_true")
    parser.add_argument("--sync-wiki", action="store_true")
    args = parser.parse_args()

    config = load_config()
    tz_name = config["timezone"]
    run_type = args.run_type
    channel = args.channel
    channel_config = config["channels"][channel]
    start_at, end_at = get_time_window(run_type, tz_name)
    run_date = start_at.strftime("%Y-%m-%d")

    candidates = make_demo_items(tz_name) if args.demo else fetch_candidate_news(start_at, end_at, channel_config, tz_name)
    deduped = dedupe_items(candidates, title_threshold=config["dedupe"]["title_similarity_threshold"])

    conn = get_conn()
    if args.ignore_state:
        existed_items = []
        final_items = list(deduped)
    else:
        existed_items = [item for item in deduped if article_exists(conn, run_date, item.event_fingerprint)]
        final_items = [item for item in deduped if not article_exists(conn, run_date, item.event_fingerprint)]
    final_items = final_items[: channel_config.get("max_items", config["max_items"])]

    markdown = render_markdown(f"{RUN_TYPE_LABELS[run_type]}·{channel_config.get('label', channel)}", start_at, end_at, final_items)
    output_dir = Path(__file__).resolve().parent.parent / "logs"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{channel}-{run_type}-{datetime.now().strftime('%Y%m%d-%H%M%S')}.md"
    output_path.write_text(markdown, encoding="utf-8")

    debug_path = _write_debug_log(run_type, channel, run_date, candidates, deduped, final_items, existed_items, tz_name, args.ignore_state)

    if final_items and not args.ignore_state:
        save_articles(conn, run_date, run_type, final_items)

    print(f"channel={channel}")
    print(f"run_type={run_type}")
    print(f"window={start_at.isoformat()} -> {end_at.isoformat()}")
    print(f"candidates={len(candidates)} deduped={len(deduped)} existed={len(existed_items)} selected={len(final_items)}")
    wiki_plan = ensure_node_path(run_type, channel, end_at)

    print(f"markdown_output={output_path}")
    print(f"debug_output={debug_path}")
    print(f"wiki_doc_title={wiki_plan['doc_title']}")
    print(f"wiki_year={wiki_plan['year_title']}")
    print(f"wiki_month={wiki_plan['month_title']}")
    if args.sync_wiki:
        print("wiki_sync_requested=true")
        sync_result = sync_markdown(run_type, channel, output_path, target_dt=end_at)
        print(f"wiki_sync_status={'ok' if sync_result.get('ok') else 'error'}")
        if sync_result.get('doc_token'):
            print(f"wiki_doc_token={sync_result['doc_token']}")
        if sync_result.get('url'):
            print(f"wiki_doc_url={sync_result['url']}")
        if sync_result.get('error'):
            print(f"wiki_sync_error={sync_result['error']}")
    print(f"run_date={run_date}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
