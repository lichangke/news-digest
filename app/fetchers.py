from __future__ import annotations

import os
import re
import subprocess
from datetime import datetime
from pathlib import Path
from typing import List
from zoneinfo import ZoneInfo

import requests
from dateutil import parser as date_parser
from xml.etree import ElementTree as ET

from .china_sources import CHINA_SOURCE_ADAPTERS
from .dedupe import fingerprint_from_text, normalize_title
from .models import NewsItem

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


def fetch_candidate_news(start_at: datetime, end_at: datetime, channel_config: dict, tz_name: str) -> List[NewsItem]:
    label = channel_config.get("label", "unknown")
    if label in {"AI / 大模型", "ai"}:
        return fetch_ai_rss_items(start_at, end_at, channel_config, tz_name)
    return fetch_general_candidates(start_at, end_at, channel_config, tz_name)


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
    title = title_match.group(1).strip() if title_match else ''
    title = title.replace('_新闻频道_央视网(cctv.com)', '').replace('_央视网(cctv.com)', '').strip()
    paragraph_hits = re.findall(r'<p[^>]*>(.*?)</p>', html, re.S | re.I)
    summary = ''
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


def fetch_rss_group(start_at: datetime, end_at: datetime, rss_urls: List[str], tz_name: str, priority_floor: int) -> List[NewsItem]:
    tz = ZoneInfo(tz_name)
    items: List[NewsItem] = []
    for url in rss_urls:
        try:
            resp = requests.get(url, timeout=20, headers={"User-Agent": "Mozilla/5.0 OpenClaw NewsDigest"})
            resp.raise_for_status()
            root = ET.fromstring(resp.content)
        except Exception:
            continue
        for entry in root.findall('.//item')[:12] + root.findall('.//{http://www.w3.org/2005/Atom}entry')[:12]:
            title = _find_text(entry, ['title', '{http://www.w3.org/2005/Atom}title'])
            link = _find_link(entry)
            summary = _find_text(entry, ['description', 'summary', '{http://www.w3.org/2005/Atom}summary'])
            published_raw = _find_text(entry, ['pubDate', 'published', 'updated', '{http://www.w3.org/2005/Atom}published', '{http://www.w3.org/2005/Atom}updated'])
            if not title or not link:
                continue
            try:
                published_at = date_parser.parse(published_raw) if published_raw else datetime.now(tz)
                if published_at.tzinfo is None:
                    published_at = published_at.replace(tzinfo=tz)
                else:
                    published_at = published_at.astimezone(tz)
            except Exception:
                published_at = datetime.now(tz)
            if not (start_at <= published_at < end_at):
                continue
            source_name = _source_name_from_url(url)
            host = link.split('//', 1)[-1].split('/', 1)[0].replace('www.', '')
            source_priority = PREFERRED_HOST_PRIORITY.get(host, priority_floor)
            items.append(
                NewsItem(
                    title=title.strip(),
                    summary=(summary or '').strip()[:180] or 'RSS 条目摘要待补充。',
                    source=source_name,
                    published_at=published_at,
                    url=link,
                    normalized_title=normalize_title(title),
                    event_fingerprint=fingerprint_from_text(title, summary or '', link),
                    source_priority=source_priority,
                )
            )
    return items


def score_general_items(items: List[NewsItem]) -> List[NewsItem]:
    scored: List[NewsItem] = []
    for item in items:
        host = item.url.split('//', 1)[-1].split('/', 1)[0].replace('www.', '')
        if host in PREFERRED_HOST_PRIORITY:
            item.source_priority = min(item.source_priority, PREFERRED_HOST_PRIORITY[host])
        elif re.search(r'[A-Za-z]{4,}', item.title) and not re.search(r'[\u4e00-\u9fff]', item.title):
            item.source_priority = max(item.source_priority, 120)
        else:
            item.source_priority = min(item.source_priority, 40)
        scored.append(item)
    return [item for item in scored if item.source_priority < 100]


def fetch_from_tavily(query: str, start_at: datetime, end_at: datetime, tz_name: str) -> List[NewsItem]:
    env = os.environ.copy()
    env_path = WORKSPACE_DIR / '.env'
    if env_path.exists():
        for line in env_path.read_text(encoding='utf-8').splitlines():
            if '=' in line and not line.strip().startswith('#'):
                key, value = line.split('=', 1)
                env[key.strip()] = value.strip()
    script = WORKSPACE_DIR / 'skills' / 'tavily-search' / 'scripts' / 'search.mjs'
    if not script.exists() or 'TAVILY_API_KEY' not in env:
        return []
    try:
        result = subprocess.run(['node', str(script), query, '--topic', 'news', '-n', '10'], capture_output=True, text=True, check=True, env=env)
    except Exception:
        return []
    lines = result.stdout.splitlines()
    items: List[NewsItem] = []
    current_title = None
    current_url = None
    current_snippet = None
    for line in lines:
        line = line.strip()
        if line.startswith('- **') and '**' in line:
            current_title = line.split('**', 2)[1]
        elif line.startswith('http'):
            current_url = line
        elif line.startswith('# '):
            current_snippet = line[2:].strip()
            if current_title and current_url:
                published_at = start_at.replace(hour=min(end_at.hour, max(start_at.hour, start_at.hour + 1)))
                title = current_title
                items.append(NewsItem(title=title, summary=current_snippet[:180], source='Tavily聚合', published_at=published_at, url=current_url, normalized_title=normalize_title(title), event_fingerprint=fingerprint_from_text(title, current_snippet), source_priority=50))
                current_title = None
                current_url = None
                current_snippet = None
    return items


def fetch_from_multi_search_engine(query: str, preferred: List[str], start_at: datetime, end_at: datetime, tz_name: str) -> List[NewsItem]:
    items: List[NewsItem] = []
    source_map = {'xinhua': 'site:xinhuanet.com', 'people': 'site:people.com.cn', 'cctv': 'site:news.cctv.com', 'thepaper': 'site:thepaper.cn', 'jiemian': 'site:jiemian.com'}
    for source in preferred:
        site_query = source_map.get(source)
        if not site_query:
            continue
        title = f'{source} 综合热点候选'
        url = f'https://cn.bing.com/search?q={site_query}+{query}'.replace(' ', '+')
        items.append(NewsItem(title=title, summary='搜索入口候选，不应直接进入最终稿件。', source=f'multi-search-engine:{source}', published_at=start_at.replace(hour=min(end_at.hour, max(start_at.hour, start_at.hour + 1))), url=url, normalized_title=normalize_title(title), event_fingerprint=fingerprint_from_text(title, source, query), source_priority=200, is_candidate_only=True))
    return items


def fetch_ai_rss_items(start_at: datetime, end_at: datetime, channel_config: dict, tz_name: str) -> List[NewsItem]:
    rss_urls = channel_config.get('sources', {}).get('rss', [])
    return fetch_rss_group(start_at, end_at, rss_urls, tz_name, priority_floor=20)


def _find_text(node, tags: List[str]) -> str:
    for tag in tags:
        found = node.find(tag)
        if found is not None and found.text:
            return found.text
    return ''


def _find_link(node) -> str:
    link = node.find('link')
    if link is not None:
        if link.text:
            return link.text.strip()
        href = link.attrib.get('href')
        if href:
            return href.strip()
    atom_link = node.find('{http://www.w3.org/2005/Atom}link')
    if atom_link is not None:
        href = atom_link.attrib.get('href')
        if href:
            return href.strip()
    return ''


def _source_name_from_url(url: str) -> str:
    host = url.split('//', 1)[-1].split('/', 1)[0]
    return host.replace('www.', '')


def make_demo_items(tz_name: str) -> List[NewsItem]:
    tz = ZoneInfo(tz_name)
    demo_time = datetime.now(tz).replace(hour=7, minute=30, second=0, microsecond=0)
    title = '新华社发布今日经济运行观察'
    return [NewsItem(title=title, summary='这是用于联调流程的演示新闻，不代表真实抓取结果。', source='新华社（演示）', published_at=demo_time, url='https://example.com/demo-news', normalized_title=normalize_title(title), event_fingerprint=fingerprint_from_text(title, '经济运行', '新华社'), source_priority=1)]
