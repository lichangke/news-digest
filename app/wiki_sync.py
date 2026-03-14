from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path
from typing import Tuple
from zoneinfo import ZoneInfo

from .config import load_config
from .feishu_bridge import sync_markdown as bridge_sync_markdown


RUN_TYPE_LABELS = {
    "morning": "早间",
    "evening": "晚间",
}


# Existing known nodes in the current workspace/wiki setup.
KNOWN_DAILY_SUMMARY_NODE = "PoAgwUBlKi7z7WkEgFJczEfVnnJ"


def build_doc_title(run_date: datetime, run_type: str, channel: str, channel_config: dict) -> str:
    date_part = run_date.strftime("%Y年%m月%d日")
    if channel == "ai":
        suffix = channel_config.get("wiki_title_suffix") or f"AI / 大模型{RUN_TYPE_LABELS[run_type]}汇总"
        return f"【{date_part}】{suffix}"
    return f"【{date_part}】{RUN_TYPE_LABELS[run_type]}新闻汇总"


def build_index_title(run_date: datetime) -> Tuple[str, str]:
    return f"{run_date:%Y年}", f"{run_date:%m月}"


def ensure_node_path(run_type: str, channel: str, target_dt: datetime | None = None) -> dict:
    config = load_config()
    feishu = config["feishu"]
    channel_config = config["channels"][channel]
    tz = ZoneInfo(config["timezone"])
    target_dt = target_dt or datetime.now(tz)

    year_title, month_title = build_index_title(target_dt)
    doc_title = build_doc_title(target_dt, run_type, channel, channel_config)

    return {
        "space_id": feishu["wiki_space_id"],
        "root_node_token": feishu["wiki_root_node_token"],
        "daily_summary_node_token": KNOWN_DAILY_SUMMARY_NODE,
        "year_title": year_title,
        "month_title": month_title,
        "doc_title": doc_title,
        "channel": channel,
        "run_type": run_type,
        "target_date": target_dt.strftime("%Y-%m-%d"),
        "owner_open_id": feishu.get("owner_open_id", ""),
    }


def sync_markdown(run_type: str, channel: str, markdown_path: Path, target_dt: datetime | None = None) -> dict:
    plan = ensure_node_path(run_type, channel, target_dt=target_dt)
    content = markdown_path.read_text(encoding="utf-8")
    result = bridge_sync_markdown(plan["doc_title"], plan["year_title"], plan["month_title"], content)
    result["plan"] = plan
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--channel", required=True)
    parser.add_argument("--run-type", required=True)
    parser.add_argument("--markdown", required=True)
    args = parser.parse_args()

    md_path = Path(args.markdown)
    if not md_path.exists():
        raise FileNotFoundError(md_path)

    plan = ensure_node_path(args.run_type, args.channel)
    print(
        "wiki_sync_plan "
        f"channel={args.channel} run_type={args.run_type} markdown={md_path} "
        f"year={plan['year_title']} month={plan['month_title']} title={plan['doc_title']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
