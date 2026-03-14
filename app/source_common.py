from __future__ import annotations

from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
WORKSPACE_DIR = BASE_DIR.parent

PREFERRED_HOST_PRIORITY = {
    "xinhuanet.com": 1,
    "people.com.cn": 2,
    "news.cctv.com": 1,
    "thepaper.cn": 4,
    "jiemian.com": 8,
    "feeds.bbci.co.uk": 20,
    "zaobao.com.sg": 25,
    "reuters.com": 70,
    "nytimes.com": 80,
    "bbc.com": 85,
}
