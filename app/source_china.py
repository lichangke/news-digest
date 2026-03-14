from __future__ import annotations

import re
from datetime import datetime
from typing import List
from zoneinfo import ZoneInfo

import requests

from .china_sources import CHINA_SOURCE_ADAPTERS
from .dedupe import fingerprint_from_text, normalize_title
from .models import NewsItem


def fetch_from_china_adapters(start_at: datetime, end_at: datetime, tz_name: str) -> List[NewsItem]:
    items: List[NewsItem] = []
    for adapter in CHINA_SOURCE_ADAPTERS:
        if not adapter.enabled:
            continue
        if adapter.name == "cctv":
            items.extend(fetch_cctv_list_items(start_at, end_at, tz_name, adapter.list_urls))
        elif adapter.name == "jiemian":
            items.extend(fetch_jiemian_list_items(start_at, end_at, tz_name, adapter.list_urls))
    return items


def fetch_cctv_list_items(start_at: datetime, end_at: datetime, tz_name: str, urls: List[str]) -> List[NewsItem]:
    tz = ZoneInfo(tz_name)
    items: List[NewsItem] = []
    seen = set()
    for url in urls:
        try:
            resp = requests.get(url, timeout=20, headers={"User-Agent": "Mozilla/5.0 OpenClaw NewsDigest"})
            resp.raise_for_status()
            html = resp.text
        except Exception:
            continue

        detail_links = re.findall(r'https://news\.cctv\.com/\d{4}/\d{2}/\d{2}/[^"\']+?\.shtml', html)
        for detail_url in detail_links:
            if detail_url in seen:
                continue
            seen.add(detail_url)
            item = fetch_cctv_detail_item(detail_url, start_at, end_at, tz)
            if item:
                items.append(item)
    return items


def fetch_cctv_detail_item(detail_url: str, start_at: datetime, end_at: datetime, tz) -> NewsItem | None:
    try:
        resp = requests.get(detail_url, timeout=20, headers={"User-Agent": "Mozilla/5.0 OpenClaw NewsDigest"})
        resp.raise_for_status()
        resp.encoding = resp.apparent_encoding or resp.encoding
        html = resp.text
    except Exception:
        return None

    title_match = re.search(r'<title>(.*?)</title>', html, re.S | re.I)
    title = title_match.group(1).strip() if title_match else ""
    title = title.replace('_新闻频道_央视网(cctv.com)', '').replace('_央视网(cctv.com)', '').strip()
    paragraph_hits = re.findall(r'<p[^>]*>(.*?)</p>', html, re.S | re.I)
    summary = ""
    for para in paragraph_hits:
        text = re.sub(r'<[^>]+>', '', para)
        text = text.replace('&ldquo;', '“').replace('&rdquo;', '”').replace('&nbsp;', ' ')
        text = re.sub(r'\s+', ' ', text).strip(' \u3000')
        blocked_fragments = ['var isHttps', 'playerParas', '播放器', 'videoCenterId', 'guid =', 'share_log']
        if any(fragment in text for fragment in blocked_fragments):
            continue
        if len(text) >= 20 and re.search(r'[\u4e00-\u9fff]', text):
            summary = text[:180]
            break

    body_text = re.sub(r'<[^>]+>', '\n', html)
    body_text = re.sub(r'\n+', '\n', body_text)
    lines = [line.strip() for line in body_text.splitlines() if line.strip()]
    chinese_lines = [line for line in lines if re.search(r'[\u4e00-\u9fff]', line)]
    if not summary:
        for line in chinese_lines:
            if len(line) >= 20 and '央视网消息' in line:
                summary = line[:180]
                break
    if not summary:
        for line in chinese_lines:
            if len(line) >= 20 and title not in line:
                summary = line[:180]
                break
    date_match = re.search(r'/((?:20\d{2})/(?:\d{2})/(?:\d{2}))/', detail_url)
    if not date_match or not title:
        return None
    date_str = date_match.group(1).replace('/', '-')
    precise_time_match = re.search(r'(20\d{2}年\d{2}月\d{2}日\s*\d{2}:\d{2})', html)
    if precise_time_match:
        precise_time = precise_time_match.group(1).replace('年', '-').replace('月', '-').replace('日', '')
        published_at = datetime.fromisoformat(f"{precise_time.strip()}:00").replace(tzinfo=tz)
    else:
        published_at = datetime.fromisoformat(f'{date_str}T12:00:00').replace(tzinfo=tz)
    if not (start_at <= published_at < end_at):
        return None
    return NewsItem(
        title=title,
        summary=summary or '央视详情页抓取结果，摘要待补强。',
        source='news.cctv.com',
        published_at=published_at,
        url=detail_url,
        normalized_title=normalize_title(title),
        event_fingerprint=fingerprint_from_text(title, summary, detail_url),
        source_priority=1,
        source_adapter='cctv',
    )


def fetch_jiemian_list_items(start_at: datetime, end_at: datetime, tz_name: str, urls: List[str]) -> List[NewsItem]:
    tz = ZoneInfo(tz_name)
    items: List[NewsItem] = []
    seen = set()
    for url in urls:
        try:
            resp = requests.get(url, timeout=20, headers={"User-Agent": "Mozilla/5.0 OpenClaw NewsDigest"})
            resp.raise_for_status()
            resp.encoding = resp.apparent_encoding or resp.encoding
            html = resp.text
        except Exception:
            continue

        time_map = extract_jiemian_list_times(html, start_at, tz)
        detail_links = re.findall(r'https://www\.jiemian\.com/article/\d+\.html', html)
        for detail_url in detail_links[:30]:
            if detail_url in seen:
                continue
            seen.add(detail_url)
            mapped_time = time_map.get(detail_url)
            item = fetch_jiemian_detail_item(detail_url, start_at, end_at, tz, mapped_time)
            if item:
                items.append(item)
    return items


def extract_jiemian_list_times(html: str, start_at: datetime, tz) -> dict[str, datetime]:
    time_map: dict[str, datetime] = {}
    pattern = re.compile(r'(?P<time>(?:今天\s*)?\d{2}:\d{2}|昨天\s*\d{2}:\d{2}).{0,400}?(?P<url>https://www\.jiemian\.com/article/\d+\.html)', re.S)
    for match in pattern.finditer(html):
        raw_time = re.sub(r'\s+', '', match.group('time'))
        detail_url = match.group('url')
        if raw_time.startswith('昨天'):
            continue
        hm = raw_time.replace('今天', '')
        try:
            dt = datetime.fromisoformat(f"{start_at.date().isoformat()}T{hm}:00").replace(tzinfo=tz)
        except Exception:
            continue
        time_map[detail_url] = dt
    reverse_pattern = re.compile(r'(?P<url>https://www\.jiemian\.com/article/\d+\.html).{0,220}?(?P<time>(?:今天\s*)?\d{2}:\d{2}|昨天\s*\d{2}:\d{2})', re.S)
    for match in reverse_pattern.finditer(html):
        raw_time = re.sub(r'\s+', '', match.group('time'))
        detail_url = match.group('url')
        if detail_url in time_map or raw_time.startswith('昨天'):
            continue
        hm = raw_time.replace('今天', '')
        try:
            dt = datetime.fromisoformat(f"{start_at.date().isoformat()}T{hm}:00").replace(tzinfo=tz)
        except Exception:
            continue
        time_map[detail_url] = dt
    return time_map


def fetch_jiemian_detail_item(detail_url: str, start_at: datetime, end_at: datetime, tz, mapped_time: datetime | None = None) -> NewsItem | None:
    try:
        resp = requests.get(detail_url, timeout=20, headers={"User-Agent": "Mozilla/5.0 OpenClaw NewsDigest"})
        resp.raise_for_status()
        resp.encoding = resp.apparent_encoding or resp.encoding
        html = resp.text
    except Exception:
        return None
    title_match = re.search(r'<title>(.*?)</title>', html, re.S | re.I)
    title = title_match.group(1).strip() if title_match else ''
    raw_title = title
    title = title.replace('|界面新闻 · 快讯', '').replace('|界面新闻', '').strip()

    lower_title = raw_title.lower()
    blocked_keywords = ['活动', '峰会', '论坛', '报名', '消费者报告 · 时尚', '快讯', '直播', '发布会', '· 证券', '商业头条', '财说', '投资早报', '独家', '深度']
    blocked_summary_keywords = ['IPO', '年报', '融资', 'ETF', '股权', '股价', 'A股', '港股', '上市', '募资', '扭亏', '财务杠杆', '估值']
    whitelist_keywords = ['政府工作报告', '规划纲要', '监管', '金融监管', '民生', '消费者权益', '公共安全', '调查', '物价', '油价', '黄金', '银行', '医疗', '医保', '教育', '国际', '外交', '贸易']
    if any(keyword.lower() in lower_title for keyword in blocked_keywords):
        return None

    published_at = mapped_time
    if published_at is None:
        for pattern in [
            r'(20\\d{2}-\\d{2}-\\d{2}\\s+\\d{2}:\\d{2}:\\d{2})',
            r'(20\\d{2}-\\d{2}-\\d{2}\\s+\\d{2}:\\d{2})',
            r'(20\\d{2}年\\d{2}月\\d{2}日\\s+\\d{2}:\\d{2})',
        ]:
            time_match = re.search(pattern, html)
            if time_match:
                raw = time_match.group(1).replace('年', '-').replace('月', '-').replace('日', '')
                if len(raw.strip()) == 16:
                    raw = raw.strip() + ':00'
                published_at = datetime.fromisoformat(raw.strip()).replace(tzinfo=tz)
                break
    if published_at is None:
        published_at = start_at.replace(hour=12, minute=0)
    if not (start_at <= published_at < end_at):
        return None

    summary = ''
    article_hits = re.findall(r'<div[^>]+class="article-content"[^>]*>(.*?)</div>', html, re.S | re.I)
    if not article_hits:
        article_hits = re.findall(r'<div[^>]+class="article-main"[^>]*>(.*?)</div>', html, re.S | re.I)
    for block in article_hits:
        text = re.sub(r'<[^>]+>', ' ', block)
        text = re.sub(r'\s+', ' ', text).strip(' \u3000')
        if len(text) >= 20 and re.search(r'[\u4e00-\u9fff]', text):
            summary = text[:180]
            break
    if not summary:
        paragraph_hits = re.findall(r'<p[^>]*>(.*?)</p>', html, re.S | re.I)
        for para in paragraph_hits:
            text = re.sub(r'<[^>]+>', '', para)
            text = re.sub(r'\s+', ' ', text).strip(' \u3000')
            if len(text) >= 20 and re.search(r'[\u4e00-\u9fff]', text) and '界面快报' not in text:
                summary = text[:180]
                break
    whitelist_hit = any(keyword in title or keyword in summary for keyword in whitelist_keywords)
    strong_blacklist_hit = any(keyword.lower() in lower_title for keyword in ['· 证券', '商业头条', '财说', '投资早报', '独家', '深度'])
    if strong_blacklist_hit:
        return None
    if not whitelist_hit:
        return None
    if any(keyword in summary for keyword in blocked_summary_keywords) and not whitelist_hit:
        return None
    if ('界面新闻记者 |' in summary or '界面新闻编辑 |' in summary) and not whitelist_hit:
        return None
    if not title:
        return None
    return NewsItem(
        title=title,
        summary=summary or '界面详情页抓取结果，摘要待补强。',
        source='www.jiemian.com',
        published_at=published_at,
        url=detail_url,
        normalized_title=normalize_title(title),
        event_fingerprint=fingerprint_from_text(title, summary, detail_url),
        source_priority=8,
        source_adapter='jiemian',
    )
