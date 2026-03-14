from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List

from .models import NewsItem
from .quality_rules import score_general_host_priority


@dataclass(frozen=True)
class GeneralItemDecision:
    keep: bool
    reason: str
    priority: int


DEFAULT_GENERAL_MAX_PRIORITY_KEEP = 100


def evaluate_general_item(item: NewsItem, max_priority_keep: int = DEFAULT_GENERAL_MAX_PRIORITY_KEEP) -> GeneralItemDecision:
    host = item.url.split('//', 1)[-1].split('/', 1)[0].replace('www.', '')
    priority = score_general_host_priority(host, item.title, item.source_priority)
    keep = priority < max_priority_keep
    reason = 'accepted' if keep else 'priority_filtered'
    return GeneralItemDecision(keep=keep, reason=reason, priority=priority)


def apply_general_quality_policy(items: Iterable[NewsItem], max_priority_keep: int = DEFAULT_GENERAL_MAX_PRIORITY_KEEP) -> List[NewsItem]:
    selected: List[NewsItem] = []
    for item in items:
        decision = evaluate_general_item(item, max_priority_keep=max_priority_keep)
        item.source_priority = decision.priority
        if decision.keep:
            selected.append(item)
    return selected
