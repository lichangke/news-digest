from __future__ import annotations

from datetime import datetime
from typing import List
from zoneinfo import ZoneInfo

from .channels import get_channel_strategy
from .dedupe import fingerprint_from_text, normalize_title
from .models import NewsItem


def fetch_candidate_news(channel: str, start_at: datetime, end_at: datetime, channel_config: dict, tz_name: str) -> List[NewsItem]:
    strategy = get_channel_strategy(channel)
    return strategy.fetch_candidates(start_at, end_at, channel_config, tz_name)


def make_demo_items(tz_name: str) -> List[NewsItem]:
    tz = ZoneInfo(tz_name)
    demo_time = datetime.now(tz).replace(hour=7, minute=30, second=0, microsecond=0)
    title = '新华社发布今日经济运行观察'
    return [NewsItem(title=title, summary='这是用于联调流程的演示新闻，不代表真实抓取结果。', source='新华社（演示）', published_at=demo_time, url='https://example.com/demo-news', normalized_title=normalize_title(title), event_fingerprint=fingerprint_from_text(title, '经济运行', '新华社'), source_priority=1)]
