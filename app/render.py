from __future__ import annotations

from datetime import datetime
from typing import Iterable

from .models import NewsItem


def render_markdown(run_type_label: str, start_at: datetime, end_at: datetime, items: Iterable[NewsItem]) -> str:
    items = list(items)
    lines = []
    lines.append(f"# {start_at:%Y年%m月%d日}{run_type_label}新闻汇总")
    lines.append("")
    lines.append(
        f"本文汇总 {start_at:%Y-%m-%d %H:%M} 至 {end_at:%Y-%m-%d %H:%M} 期间公开发布的新闻，共收录 {len(items)} 条。"
    )
    lines.append("")
    for idx, item in enumerate(items, start=1):
        lines.append(f"## {idx}. {item.title}")
        lines.append(f"- 核心内容：{item.summary}")
        lines.append(f"- 新闻来源：{item.source}")
        lines.append(f"- 发布时间：{item.published_at:%Y-%m-%d %H:%M}")
        lines.append(f"- 原文链接：{item.url}")
        lines.append("")
    lines.append("---")
    lines.append(f"采集完成时间：{datetime.now(start_at.tzinfo):%Y-%m-%d %H:%M}")
    lines.append(f"数据范围：{start_at:%Y-%m-%d %H:%M} 至 {end_at:%Y-%m-%d %H:%M}")
    lines.append("说明：已按发布时间窗口与事件相似度进行去重整理。")
    return "\n".join(lines)
