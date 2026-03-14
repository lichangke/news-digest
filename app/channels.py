from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Callable, Dict, List

from .channel_policies import (
    ChannelQualityPolicy,
    apply_ai_quality_policy,
    apply_general_quality_policy_for_channel,
    collect_ai_candidates,
    collect_general_candidates,
)
from .models import NewsItem

CandidateFetcher = Callable[[datetime, datetime, dict, str], List[NewsItem]]
QualityApplier = Callable[[List[NewsItem], ChannelQualityPolicy], List[NewsItem]]


@dataclass(frozen=True)
class ChannelStrategy:
    name: str
    label_fallback: str
    fetch_candidates: CandidateFetcher
    apply_quality_policy: QualityApplier
    quality_policy: ChannelQualityPolicy


CHANNEL_REGISTRY: Dict[str, ChannelStrategy] = {
    "general": ChannelStrategy(
        name="general",
        label_fallback="综合热点",
        fetch_candidates=collect_general_candidates,
        apply_quality_policy=apply_general_quality_policy_for_channel,
        quality_policy=ChannelQualityPolicy(channel="general", max_priority_keep=100),
    ),
    "ai": ChannelStrategy(
        name="ai",
        label_fallback="AI / 大模型",
        fetch_candidates=collect_ai_candidates,
        apply_quality_policy=apply_ai_quality_policy,
        quality_policy=ChannelQualityPolicy(channel="ai", max_priority_keep=None),
    ),
}


def get_channel_strategy(channel: str) -> ChannelStrategy:
    if channel not in CHANNEL_REGISTRY:
        raise KeyError(f"unknown channel: {channel}")
    return CHANNEL_REGISTRY[channel]
