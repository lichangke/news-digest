from __future__ import annotations

import hashlib
import re
from typing import Iterable, List

from rapidfuzz import fuzz

from .models import NewsItem

NOISE_WORDS = ["刚刚", "最新", "突发", "重磅"]


def normalize_title(title: str) -> str:
    text = title.strip().lower()
    for word in NOISE_WORDS:
        text = text.replace(word, "")
    text = re.sub(r"[\W_]+", "", text)
    return text


def fingerprint_from_text(*parts: str) -> str:
    joined = "|".join(part.strip().lower() for part in parts if part)
    return hashlib.sha1(joined.encode("utf-8")).hexdigest()


def dedupe_items(items: Iterable[NewsItem], title_threshold: int = 92) -> List[NewsItem]:
    selected: List[NewsItem] = []
    filtered_items = [item for item in items if not item.is_candidate_only]
    for item in sorted(filtered_items, key=lambda x: (x.source_priority, x.published_at)):
        duplicated = False
        for existing in selected:
            if item.event_fingerprint == existing.event_fingerprint:
                duplicated = True
                break
            title_similarity = fuzz.ratio(item.normalized_title, existing.normalized_title)
            if title_similarity >= title_threshold:
                duplicated = True
                break

            summary_similarity = 0
            if item.summary and existing.summary:
                summary_similarity = fuzz.partial_ratio(item.summary[:160], existing.summary[:160])

            cross_adapter = bool(item.source_adapter and existing.source_adapter and item.source_adapter != existing.source_adapter)
            if cross_adapter:
                if title_similarity >= 58 and summary_similarity >= 62:
                    duplicated = True
                    break
                if title_similarity >= 72:
                    duplicated = True
                    break
                if summary_similarity >= 78:
                    duplicated = True
                    break
        if not duplicated:
            selected.append(item)
    return selected
