"""Headline-only news retrieval, dedupe, and source links. No scraped full articles.

Google News RSS availability varies by region; this is a best-effort fallback,
not a licensed redistribution feed. Titles link to Google's publisher gateway.
"""
from __future__ import annotations
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime
from urllib.parse import urlencode, urlparse
import re
import xml.etree.ElementTree as ET

import requests
from market_data import MarketDataError, fetch_news, normalize_symbol

TOPICS = {
    'general': {'US': 'US stock market earnings economy', 'CN': '中国 A股 股票 市场', 'HK': '香港 股市 恒生', 'EU': 'European stock market'},
    'technology': {'US': 'technology AI semiconductor stocks', 'CN': 'A股 科技 半导体 人工智能', 'HK': '香港 科技股', 'EU': 'Europe technology shares'},
    'macro': {'US': 'Federal Reserve inflation interest rates stocks', 'CN': '中国 央行 宏观 经济 股市', 'HK': '香港 金融 经济', 'EU': 'ECB eurozone economy equities'},
    'earnings': {'US': 'earnings results listed companies', 'CN': '上市公司 业绩 财报 A股', 'HK': '港股 财报 业绩', 'EU': 'European earnings shares'},
}


def _locale(language: str):
    if language == 'zh':
        return {'hl': 'zh-CN', 'gl': 'CN', 'ceid': 'CN:zh-Hans'}
    if language == 'de':
        return {'hl': 'de', 'gl': 'DE', 'ceid': 'DE:de'}
    return {'hl': 'en-US', 'gl': 'US', 'ceid': 'US:en'}


def safe_link(value: str) -> bool:
    try:
        p = urlparse(value)
        return p.scheme == 'https' and bool(p.netloc) and not p.username and not p.password
    except (TypeError, ValueError):
        return False


def parse_rss(xml: bytes, limit: int = 12) -> list[dict]:
    try:
        root = ET.fromstring(xml)
    except ET.ParseError:
        return []
    seen, records = set(), []
    for item in root.findall('.//channel/item'):
        title = ' '.join((item.findtext('title') or '').split())[:280]
        link = (item.findtext('link') or '').strip()
        source = item.find('source')
        publisher = (source.text or '').strip() if source is not None and source.text else 'Google News'
        if not title or not safe_link(link):
            continue
        key = re.sub(r'\W+', ' ', title.casefold()).strip()
        if key in seen:
            continue
        seen.add(key)
        published_raw = item.findtext('pubDate') or ''
        try:
            dt = parsedate_to_datetime(published_raw)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            dt = dt.astimezone(timezone.utc)
            date = dt.isoformat()
        except (TypeError, ValueError, IndexError):
            date = 'Publication date unavailable'
        records.append({'title': title, 'url': link, 'source': publisher[:120], 'date': date})
        if len(records) >= limit:
            break
    return records


def fetch_rss(query: str, language: str = 'en', limit: int = 12) -> tuple[list[dict], datetime]:
    if not query or len(query) > 140:
        raise MarketDataError('Invalid news query.')
    url = 'https://news.google.com/rss/search?' + urlencode({'q': query, **_locale(language)})
    try:
        response = requests.get(url, timeout=(5, 12), headers={'User-Agent': 'TaurusResearchDemo/2.0'}, allow_redirects=True)
        response.raise_for_status()
        if len(response.content) > 1_200_000:
            raise MarketDataError('News feed is too large.')
        items = parse_rss(response.content, limit=max(1, min(limit, 30)))
    except requests.RequestException as exc:
        raise MarketDataError('News RSS service temporarily unavailable.') from exc
    return items, datetime.now(timezone.utc)


def fetch_market_news(market: str = 'US', topic: str = 'general', language: str = 'en', limit: int = 10):
    market = market if market in ('US', 'CN', 'HK', 'EU') else 'US'
    topic = topic if topic in TOPICS else 'general'
    try:
        items, at = fetch_rss(TOPICS[topic][market], language=language, limit=limit)
        if items:
            return items, at
    except MarketDataError:
        pass
    backup = {'US':'^GSPC', 'CN':'000001.SS', 'HK':'^HSI', 'EU':'^GDAXI'}[market]
    try:
        return fetch_news(backup, count=limit)
    except MarketDataError as exc:
        raise MarketDataError('Market news providers are unavailable.') from exc


def fetch_company_news(symbol: str, company: str = '', language: str = 'en', limit: int = 8):
    """RSS search first; Yahoo is a backup as its get_news endpoint can fail."""
    code = normalize_symbol(symbol)
    name = (company or '').strip()[:70]
    q = f'"{name}" stock' if name and name.casefold() != code.casefold() else f'{code} stock news'
    try:
        items, fetched = fetch_rss(q, language, limit)
        if items:
            return items, fetched
    except MarketDataError:
        pass
    try:
        return fetch_news(code, count=limit)
    except MarketDataError as exc:
        raise MarketDataError('Both news sources are unavailable. Price research still works.') from exc


def filter_news(items: list[dict], keyword: str = '', within_days: int = 0):
    now = datetime.now(timezone.utc)
    output = []
    for item in items:
        if keyword and keyword.casefold() not in (item.get('title', '') + ' ' + item.get('source', '')).casefold():
            continue
        if within_days:
            try:
                published = datetime.fromisoformat(item['date'])
                if published.tzinfo is None:
                    published = published.replace(tzinfo=timezone.utc)
                if not now - timedelta(days=within_days) <= published <= now + timedelta(hours=12):
                    continue
            except (ValueError, TypeError, KeyError):
                continue
        output.append(item)
    return output
