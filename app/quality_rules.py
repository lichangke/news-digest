from __future__ import annotations

from dataclasses import dataclass


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


JIEMIAN_BLOCKED_KEYWORDS = [
    "活动",
    "峰会",
    "论坛",
    "报名",
    "消费者报告 · 时尚",
    "快讯",
    "直播",
    "发布会",
    "· 证券",
    "商业头条",
    "财说",
    "投资早报",
    "独家",
    "深度",
]

JIEMIAN_STRONG_BLOCKED_KEYWORDS = [
    "· 证券",
    "商业头条",
    "财说",
    "投资早报",
    "独家",
    "深度",
]

JIEMIAN_BLOCKED_SUMMARY_KEYWORDS = [
    "IPO",
    "年报",
    "融资",
    "ETF",
    "股权",
    "股价",
    "A股",
    "港股",
    "上市",
    "募资",
    "扭亏",
    "财务杠杆",
    "估值",
]

JIEMIAN_WHITELIST_KEYWORDS = [
    "政府工作报告",
    "规划纲要",
    "监管",
    "金融监管",
    "民生",
    "消费者权益",
    "公共安全",
    "调查",
    "物价",
    "油价",
    "黄金",
    "银行",
    "医疗",
    "医保",
    "教育",
    "国际",
    "外交",
    "贸易",
]

CCTV_BLOCKED_SUMMARY_FRAGMENTS = [
    "var isHttps",
    "playerParas",
    "播放器",
    "videoCenterId",
    "guid =",
    "share_log",
]


@dataclass(frozen=True)
class JiemianQualityDecision:
    allowed: bool
    whitelist_hit: bool
    strong_blacklist_hit: bool


def get_preferred_host_priority(host: str, default_priority: int) -> int:
    return PREFERRED_HOST_PRIORITY.get(host, default_priority)


def score_general_host_priority(host: str, title: str, fallback_priority: int) -> int:
    if host in PREFERRED_HOST_PRIORITY:
        return min(fallback_priority, PREFERRED_HOST_PRIORITY[host])
    if any(ch.isalpha() for ch in title) and not any('\u4e00' <= ch <= '\u9fff' for ch in title):
        return max(fallback_priority, 120)
    return min(fallback_priority, 40)


def is_cctv_summary_fragment_allowed(text: str) -> bool:
    return not any(fragment in text for fragment in CCTV_BLOCKED_SUMMARY_FRAGMENTS)


def evaluate_jiemian_quality(raw_title: str, title: str, summary: str) -> JiemianQualityDecision:
    lower_title = raw_title.lower()
    if any(keyword.lower() in lower_title for keyword in JIEMIAN_BLOCKED_KEYWORDS):
        return JiemianQualityDecision(allowed=False, whitelist_hit=False, strong_blacklist_hit=False)

    whitelist_hit = any(keyword in title or keyword in summary for keyword in JIEMIAN_WHITELIST_KEYWORDS)
    strong_blacklist_hit = any(keyword.lower() in lower_title for keyword in JIEMIAN_STRONG_BLOCKED_KEYWORDS)
    if strong_blacklist_hit:
        return JiemianQualityDecision(allowed=False, whitelist_hit=whitelist_hit, strong_blacklist_hit=True)
    if not whitelist_hit:
        return JiemianQualityDecision(allowed=False, whitelist_hit=False, strong_blacklist_hit=False)
    if any(keyword in summary for keyword in JIEMIAN_BLOCKED_SUMMARY_KEYWORDS) and not whitelist_hit:
        return JiemianQualityDecision(allowed=False, whitelist_hit=False, strong_blacklist_hit=False)
    if ('界面新闻记者 |' in summary or '界面新闻编辑 |' in summary) and not whitelist_hit:
        return JiemianQualityDecision(allowed=False, whitelist_hit=False, strong_blacklist_hit=False)
    return JiemianQualityDecision(allowed=True, whitelist_hit=whitelist_hit, strong_blacklist_hit=strong_blacklist_hit)
