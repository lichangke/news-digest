from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import List

from .general_quality import apply_general_quality_policy
from .models import NewsItem
from .source_china import fetch_from_china_adapters
from .source_rss_search import (
    fetch_ai_rss_items,
    fetch_from_multi_search_engine,
    fetch_from_tavily,
    fetch_rss_group,
)


@dataclass(frozen=True)
class ChannelQualityPolicy:
    channel: str
    max_priority_keep: int | None = None
    drop_candidate_only: bool = True


GENERAL_QUERY = "今日中国新闻 央视 新华 人民网 界面 澎湃"


def collect_general_candidates(start_at: datetime, end_at: datetime, channel_config: dict, tz_name: str) -> List[NewsItem]:
    items: List[NewsItem] = []
    sources_cfg = channel_config.get("sources", {})
    rss_cfg = sources_cfg.get("rss", {})
    search_cfg = sources_cfg.get("search", {})
    preferred = sources_cfg.get("preferred", [])

    items.extend(fetch_from_china_adapters(start_at, end_at, tz_name))

    china_primary = rss_cfg.get("china_primary", [])
    international_secondary = rss_cfg.get("international_secondary", [])
    if china_primary:
        items.extend(fetch_rss_group(start_at, end_at, china_primary, tz_name, priority_floor=15))
    if international_secondary:
        items.extend(fetch_rss_group(start_at, end_at, international_secondary, tz_name, priority_floor=70))
    if search_cfg.get("tavily"):
        items.extend(fetch_from_tavily(GENERAL_QUERY, start_at, end_at, tz_name))
    if search_cfg.get("multi_search_engine"):
        items.extend(fetch_from_multi_search_engine(GENERAL_QUERY, preferred, start_at, end_at, tz_name))
    return items


def collect_ai_candidates(start_at: datetime, end_at: datetime, channel_config: dict, tz_name: str) -> List[NewsItem]:
    return fetch_ai_rss_items(start_at, end_at, channel_config, tz_name)


def apply_general_quality_policy_for_channel(items: List[NewsItem], policy: ChannelQualityPolicy) -> List[NewsItem]:
    max_priority_keep = policy.max_priority_keep if policy.max_priority_keep is not None else 100
    return apply_general_quality_policy(items, max_priority_keep=max_priority_keep)


def apply_ai_quality_policy(items: List[NewsItem], policy: ChannelQualityPolicy) -> List[NewsItem]:
    return items
