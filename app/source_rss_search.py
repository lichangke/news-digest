from __future__ import annotations

import os
import re
import subprocess
from datetime import datetime
from typing import List
from zoneinfo import ZoneInfo
from xml.etree import ElementTree as ET

import requests
from dateutil import parser as date_parser

from .dedupe import fingerprint_from_text, normalize_title
from .models import NewsItem
from .source_common import PREFERRED_HOST_PRIORITY, WORKSPACE_DIR


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
