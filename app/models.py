from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass
class NewsItem:
    title: str
    summary: str
    source: str
    published_at: datetime
    url: str
    normalized_title: str
    event_fingerprint: str
    source_priority: int = 100
    is_candidate_only: bool = False
    source_adapter: str = ""
