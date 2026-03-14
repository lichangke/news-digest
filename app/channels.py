from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Callable, Dict, List

from .models import NewsItem
from .source_china import fetch_from_china_adapters
from .source_rss_search import (
    fetch_ai_rss_items,
    fetch_from_multi_search_engine,
    fetch_from_tavily,
    fetch_rss_group,
    score_general_items,
)

CandidateFetcher = Callable[[datetime, datetime, dict, str], List[NewsItem]]


@dataclass(frozen=True)
class ChannelStrategy:
    name: str
    label_fallback: str
    fetch_candidates: CandidateFetcher


def fetch_general_candidates(start_at: datetime, end_at: datetime, channel_config: dict, tz_name: str) -> List[NewsItem]:
    items: List[NewsItem] = []
    sources_cfg = channel_config.get("sources", {})
    rss_cfg = sources_cfg.get("rss", {})
    search_cfg = sources_cfg.get("search", {})
    preferred = sources_cfg.get("preferred", [])
    query = "今日中国新闻 央视 新华 人民网 界面 澎湃"

    items.extend(fetch_from_china_adapters(start_at, end_at, tz_name))

    china_primary = rss_cfg.get("china_primary", [])
    international_secondary = rss_cfg.get("international_secondary", [])
    if china_primary:
        items.extend(fetch_rss_group(start_at, end_at, china_primary, tz_name, priority_floor=15))
    if international_secondary:
        items.extend(fetch_rss_group(start_at, end_at, international_secondary, tz_name, priority_floor=70))
    if search_cfg.get("tavily"):
        tavily_items = fetch_from_tavily(query, start_at, end_at, tz_name)
        items.extend(score_general_items(tavily_items))
    if search_cfg.get("multi_search_engine"):
        items.extend(fetch_from_multi_search_engine(query, preferred, start_at, end_at, tz_name))
    return items


def fetch_ai_candidates(start_at: datetime, end_at: datetime, channel_config: dict, tz_name: str) -> List[NewsItem]:
    return fetch_ai_rss_items(start_at, end_at, channel_config, tz_name)


CHANNEL_REGISTRY: Dict[str, ChannelStrategy] = {
    "general": ChannelStrategy(
        name="general",
        label_fallback="综合热点",
        fetch_candidates=fetch_general_candidates,
    ),
    "ai": ChannelStrategy(
        name="ai",
        label_fallback="AI / 大模型",
        fetch_candidates=fetch_ai_candidates,
    ),
}


def get_channel_strategy(channel: str) -> ChannelStrategy:
    if channel not in CHANNEL_REGISTRY:
        raise KeyError(f"unknown channel: {channel}")
    return CHANNEL_REGISTRY[channel]
