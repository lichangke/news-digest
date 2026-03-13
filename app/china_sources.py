from __future__ import annotations

from dataclasses import dataclass
from typing import List


@dataclass
class SourceAdapter:
    name: str
    list_urls: List[str]
    link_patterns: List[str]
    enabled: bool = True


CHINA_SOURCE_ADAPTERS = [
    SourceAdapter(
        name="cctv",
        list_urls=[
            "https://news.cctv.com/china/",
            "https://news.cctv.com/world/",
            "https://news.cctv.com/society/",
            "https://news.cctv.com/law/",
            "https://news.cctv.com/tech/",
            "https://news.cctv.com/education/",
        ],
        link_patterns=[
            "news.cctv.com",
        ],
    ),
    SourceAdapter(
        name="jiemian",
        list_urls=[
            "https://www.jiemian.com/lists/9.html",
            "https://www.jiemian.com/lists/65.html",
            "https://www.jiemian.com/lists/112.html",
            "https://www.jiemian.com/",
        ],
        link_patterns=[
            "www.jiemian.com/article",
            "jiemian.com/article",
        ],
    ),
    SourceAdapter(
        name="xinhuanet",
        list_urls=[
            "https://www.xinhuanet.com/",
        ],
        link_patterns=[
            "xinhuanet.com",
        ],
        enabled=False,
    ),
    SourceAdapter(
        name="people",
        list_urls=[
            "https://www.people.com.cn/",
        ],
        link_patterns=[
            "people.com.cn",
        ],
        enabled=False,
    ),
    SourceAdapter(
        name="thepaper",
        list_urls=[
            "https://www.thepaper.cn/",
        ],
        link_patterns=[
            "thepaper.cn",
        ],
        enabled=False,
    ),
]
