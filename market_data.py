"""Taurus AI market-data adapter.

All quotes/financial fields are best-effort third-party observations, not a
licensed real-time feed. Price, metadata, search and news currently use Yahoo
through yfinance; do not assume that free access grants public-display rights.

Legacy API kept for the existing Streamlit app:
    fetch_prices(symbol) -> (DataFrame, UTC datetime)
    fetch_news(symbol)   -> (list[dict], UTC datetime)
    normalize_symbol(symbol) -> ticker string

Future-page API:
    search_stocks(query), resolve_symbol(query), get_market_indices(market),
    fetch_fundamentals(symbol), rank_curated_stocks(market, metric).
"""
from __future__ import annotations

from datetime import datetime, timezone
import math
import re
from urllib.parse import urlparse

import numpy as np
import pandas as pd
import yfinance as yf


DATA_PROVIDER = 'Yahoo Finance via yfinance'
# These are *discovery examples*, never presented as a live popularity ranking.
CURATED_STOCKS = {
    'US': ('AAPL', 'MSFT', 'NVDA', 'GOOGL', 'AMZN', 'TSLA', 'META', 'AMD'),
    'CN': ('600519.SS', '601318.SS', '600036.SS', '000858.SZ', '300750.SZ', '002594.SZ'),
    'HK': ('0700.HK', '9988.HK', '3690.HK', '1810.HK'),
    'EU': ('SAP.DE', 'SIE.DE', 'ASML.AS', 'MC.PA'),
}
# Quote symbols verified against source conventions; availability may change.
MARKET_INDICES = {
    'US': (
        {'symbol': '^GSPC', 'name': 'S&P 500'},
        {'symbol': '^IXIC', 'name': 'Nasdaq Composite'},
        {'symbol': '^DJI', 'name': 'Dow Jones Industrial Average'},
    ),
    'CN': (
        {'symbol': '000001.SS', 'name': 'SSE Composite / 上证指数'},
        {'symbol': '399001.SZ', 'name': 'Shenzhen Component / 深证成指'},
        {'symbol': '000300.SS', 'name': 'CSI 300 / 沪深300'},
        {'symbol': '399006.SZ', 'name': 'ChiNext / 创业板指'},
    ),
    'HK': (
        {'symbol': '^HSI', 'name': 'Hang Seng Index / 恒生指数'},
        {'symbol': 'HSTECH.HK', 'name': 'Hang Seng TECH / 恒生科技'},
    ),
    'EU': (
        {'symbol': '^GDAXI', 'name': 'DAX'},
        {'symbol': '^STOXX50E', 'name': 'EURO STOXX 50'},
    ),
}

# Exact-match shortcuts; dynamic company-name lookup uses yf.Search.
_NAME_ALIASES = {
    '苹果': ('AAPL', 'Apple Inc.'), 'apple': ('AAPL', 'Apple Inc.'),
    '微软': ('MSFT', 'Microsoft'), 'microsoft': ('MSFT', 'Microsoft'),
    '英伟达': ('NVDA', 'NVIDIA'), 'nvidia': ('NVDA', 'NVIDIA'),
    '特斯拉': ('TSLA', 'Tesla'), 'tesla': ('TSLA', 'Tesla'),
    '谷歌': ('GOOGL', 'Alphabet'), 'alphabet': ('GOOGL', 'Alphabet'),
    '贵州茅台': ('600519.SS', '贵州茅台'), '茅台': ('600519.SS', '贵州茅台'),
    '宁德时代': ('300750.SZ', '宁德时代'),
    '五粮液': ('000858.SZ', '五粮液'),
    '招商银行': ('600036.SS', '招商银行'),
    '中国平安': ('601318.SS', '中国平安'),
    '腾讯': ('0700.HK', 'Tencent Holdings'),
    '腾讯控股': ('0700.HK', 'Tencent Holdings'),
    '小米': ('1810.HK', 'Xiaomi'),
}

_ALLOWED_TICKER = re.compile(r'\^?[A-Z0-9][A-Z0-9.\-]{0,19}\Z')
_ALLOWED_QUERY = re.compile(r'^[\w\s.\-&\u00c0-\u024f\u4e00-\u9fff]{1,80}$', re.UNICODE)
_ALLOWED_PERIODS = frozenset(('1mo', '3mo', '6mo', '1y', '2y', '5y'))
_ALLOWED_INTERVALS = frozenset(('1d', '1wk', '1mo'))


class MarketDataError(Exception):
    """A readable market-data, search, or provider failure."""


def normalize_symbol(symbol: str) -> str:
    """Canonicalize stock tickers, including 6-digit A-shares and 4/5-digit HK.

    Ambiguous numeric codes (e.g. 000001) are interpreted as a *stock* on SZ.
    Use explicit 000001.SS for Shanghai Composite index. Beijing listings
    need an explicit .BJ suffix; provider availability is not guaranteed.
    """
    if not isinstance(symbol, str) or not symbol.strip():
        raise MarketDataError('Enter a stock code or use company-name search.')
    code = symbol.strip().upper()
    if any(char.isspace() for char in code) or not _ALLOWED_TICKER.fullmatch(code):
        raise MarketDataError('Invalid ticker. Use AAPL, 600519, 000858, 0700.HK or SAP.DE.')
    if re.fullmatch(r'\d{6}', code):
        if code[0] in '569':
            return code + '.SS'
        if code[0] in '023':
            return code + '.SZ'
        raise MarketDataError('For Beijing stocks use the full .BJ ticker; exchange is ambiguous.')
    if re.fullmatch(r'\d{4,5}', code):
        return code.zfill(4) + '.HK'
    return code


def identify_market(symbol: str) -> str:
    code = normalize_symbol(symbol)
    for market, items in MARKET_INDICES.items():
        if code in {item['symbol'] for item in items}:
            return market
    if code.endswith(('.SS', '.SZ', '.BJ')):
        return 'CN'
    if code.endswith('.HK'):
        return 'HK'
    if code.endswith(('.DE', '.AS', '.PA', '.L', '.MI', '.SW', '.MC')):
        return 'EU'
    return 'US'  # fallback category, not proof of exchange or currency


def get_market_indices(market: str = 'ALL') -> list[dict]:
    """Return a static index *catalog* with no invented prices."""
    key = market.strip().upper()
    if key in ('ALL', 'GLOBAL'):
        return [dict(item, market=m) for m, group in MARKET_INDICES.items() for item in group]
    if key not in MARKET_INDICES:
        raise MarketDataError('Unknown market; choose ALL, US, CN, HK or EU.')
    return [dict(item, market=key) for item in MARKET_INDICES[key]]


def get_curated_stocks(market: str = 'US') -> list[str]:
    """Fixed research watchlist; NOT dynamically computed market leaders."""
    key = market.strip().upper()
    if key in ('ALL', 'GLOBAL'):
        return [symbol for group in CURATED_STOCKS.values() for symbol in group]
    if key not in CURATED_STOCKS:
        raise MarketDataError('Unknown market; choose ALL, US, CN, HK or EU.')
    return list(CURATED_STOCKS[key])


def _search_item(symbol: str, name: str, exchange: str = '', source: str = DATA_PROVIDER) -> dict:
    return {
        'symbol': symbol,
        'name': name or symbol,
        'exchange': exchange or '',
        'market': identify_market(symbol),
        'source': source,
    }


def search_stocks(query: str, max_results: int = 8) -> list[dict]:
    """Search ticker/name; exact known aliases work even when provider is down.

    Does not pretend that a bare ticker was verified to trade. UI should show
    exchange alongside each search result and permit explicit selection.
    """
    if not isinstance(query, str) or not query.strip():
        return []
    q = ' '.join(query.strip().split())
    if not _ALLOWED_QUERY.fullmatch(q):
        raise MarketDataError('Search contains unsupported characters or is too long.')
    limit = max(1, min(int(max_results), 20))
    found = []
    seen = set()

    def add(item):
        code = item['symbol']
        if code not in seen and len(found) < limit:
            found.append(item)
            seen.add(code)

    alias = _NAME_ALIASES.get(q.casefold())
    if alias:
        add(_search_item(alias[0], alias[1], source='Local exact-name mapping'))
        return found
    try:
        normalized = normalize_symbol(q)
    except MarketDataError:
        normalized = None
    ticker_like = bool(normalized and (len(q) <= 5 or '.' in q or '-' in q or q.startswith('^') or any(c.isdigit() for c in q)))
    if ticker_like:
        add(_search_item(normalized, normalized, source='Ticker format; not yet verified'))
        return found

    try:
        quotes = yf.Search(q, max_results=limit, news_count=0, lists_count=0, timeout=15).quotes
    except Exception as exc:
        raise MarketDataError('Company-name search is temporarily unavailable; try a ticker instead.') from exc
    for item in quotes or []:
        if not isinstance(item, dict):
            continue
        raw = str(item.get('symbol') or '')
        try:
            code = normalize_symbol(raw)
        except MarketDataError:
            continue
        name = str(item.get('shortname') or item.get('longname') or raw)
        exchange = str(item.get('exchDisp') or item.get('exchange') or '')
        add(_search_item(code, name[:160], exchange))
    return found


def resolve_symbol(query: str) -> str:
    """Resolve an exact ticker or unambiguous company name.

    Do not silently pick from ambiguous remote results: caller should present
    search_stocks() choices to the user.
    """
    if not isinstance(query, str) or not query.strip():
        raise MarketDataError('Enter a stock ticker or company name.')
    alias = _NAME_ALIASES.get(query.strip().casefold())
    if alias:
        return alias[0]
    q = query.strip()
    try:
        code = normalize_symbol(q)
        if len(q) <= 5 or '.' in q or '-' in q or q.startswith('^') or any(c.isdigit() for c in q):
            return code
    except MarketDataError:
        pass
    results = search_stocks(q)
    if len(results) == 1:
        return results[0]['symbol']
    if not results:
        raise MarketDataError('No matching company found. Try its exact ticker.')
    raise MarketDataError('Multiple listings found; select a stock from search results.')


def _validated_prices(prices: pd.DataFrame) -> pd.DataFrame:
    """Discard invalid provider rows, not the entire stock history.

    A missing Close in a past/curr. provisional bar is not evidence that the
    company has no valid historical prices. Never synthesize/fill a close.
    """
    if prices is None or not isinstance(prices, pd.DataFrame) or prices.empty:
        raise MarketDataError('No price history was returned. Try again or choose another ticker.')
    if 'Close' not in prices or not isinstance(prices.index, pd.DatetimeIndex):
        raise MarketDataError('The provider returned an unsupported price format.')
    frame = prices.sort_index().copy()
    frame = frame.loc[~frame.index.isna()]
    frame = frame.loc[~frame.index.duplicated(keep='last')]
    frame['Close'] = pd.to_numeric(frame['Close'], errors='coerce')
    good = np.isfinite(frame['Close'].to_numpy(dtype=float)) & (frame['Close'].to_numpy(dtype=float) > 0)
    discarded = int((~good).sum())
    frame = frame.iloc[np.flatnonzero(good)].copy()
    if len(frame) < 2:
        raise MarketDataError('Not enough valid closing prices were returned. No analysis was generated.')
    for col in ('Open', 'High', 'Low', 'Volume'):
        if col in frame:
            frame[col] = pd.to_numeric(frame[col], errors='coerce')
            frame.loc[~np.isfinite(frame[col].to_numpy(dtype=float)), col] = np.nan
    frame.attrs.update(prices.attrs)
    frame.attrs['discarded_invalid_close_rows'] = discarded
    return frame


def fetch_prices(symbol: str, period: str = '6mo', interval: str = '1d') -> tuple[pd.DataFrame, datetime]:
    """Validated historical OHLCV; unchanged legacy tuple contract.

    auto_adjust=False intentionally retains the provider's raw Close series.
    Dates are exchange-local labels, not real-time timestamps. No fill/forward
    fill is performed across holidays or suspensions.
    """
    code = normalize_symbol(symbol)
    if period not in _ALLOWED_PERIODS or interval not in _ALLOWED_INTERVALS:
        raise MarketDataError('Unsupported history period or interval.')
    ticker = yf.Ticker(code)
    try:
        raw = ticker.history(period=period, interval=interval, auto_adjust=False, timeout=15)
    except Exception as exc:
        raise MarketDataError('Market data request failed. Please try again later.') from exc
    prices = _validated_prices(raw)
    try:
        meta = ticker.get_history_metadata() or {}
    except Exception:
        meta = {}
    if not isinstance(meta, dict):
        meta = {}
    prices.attrs.update({
        'company': meta.get('longName') or meta.get('shortName') or '',
        'currency': meta.get('currency') or '',
        'exchange': meta.get('fullExchangeName') or meta.get('exchangeName') or '',
        'market': identify_market(code),
        'symbol': code,
        'source': DATA_PROVIDER,
        'period': period,
        'interval': interval,
        'adjusted': False,
        'live': False,
        'observation_date': str(prices.index[-1].date()),
    })
    return prices, datetime.now(timezone.utc)


def _valid_number(value):
    if isinstance(value, bool) or value is None:
        return None
    try:
        x = float(value)
        return x if math.isfinite(x) else None
    except (TypeError, ValueError, OverflowError):
        return None


def fetch_fundamentals(symbol: str) -> tuple[dict, datetime]:
    """Best-effort snapshot. Missing data stays None, never filled by an LLM.

    Monetary fields are in reportedCurrency / financialCurrency when provided;
    not all valuation ratios use the same reporting period. Not suitable for
    cross-market comparisons without separate normalization.
    """
    code = normalize_symbol(symbol)
    try:
        info = yf.Ticker(code).get_info() or {}
    except Exception as exc:
        raise MarketDataError('Company financial data is temporarily unavailable.') from exc
    if not isinstance(info, dict) or not info:
        raise MarketDataError('The provider returned no verified financial profile.')
    fields = {
        'market_cap': 'marketCap', 'trailing_pe': 'trailingPE',
        'forward_pe': 'forwardPE', 'price_to_book': 'priceToBook',
        'trailing_eps': 'trailingEps', 'forward_eps': 'forwardEps',
        'total_revenue': 'totalRevenue', 'revenue_growth': 'revenueGrowth',
        'earnings_growth': 'earningsGrowth', 'profit_margin': 'profitMargins',
        'operating_margin': 'operatingMargins', 'return_on_equity': 'returnOnEquity',
        'total_debt': 'totalDebt', 'total_cash': 'totalCash',
        'free_cashflow': 'freeCashflow', 'dividend_yield': 'dividendYield',
        'fifty_two_week_high': 'fiftyTwoWeekHigh',
        'fifty_two_week_low': 'fiftyTwoWeekLow',
    }
    result = {
        'symbol': code,
        'company': str(info.get('longName') or info.get('shortName') or code)[:180],
        'sector': str(info.get('sector') or '')[:120],
        'industry': str(info.get('industry') or '')[:120],
        'description': str(info.get('longBusinessSummary') or '')[:3500],
        'currency': str(info.get('currency') or ''),
        'financial_currency': str(info.get('financialCurrency') or ''),
        'exchange': str(info.get('exchange') or ''),
        'market': identify_market(code),
        'source': DATA_PROVIDER,
        'period_note': 'Mixed provider-reported trailing, forward, and latest-period fields; confirm each filing date.',
        'metrics': {key: _valid_number(info.get(source_key)) for key, source_key in fields.items()},
    }
    return result, datetime.now(timezone.utc)


def _safe_news_url(value):
    if not isinstance(value, str) or len(value) > 2048:
        return None
    url = value.strip()
    parsed = urlparse(url)
    if parsed.scheme not in ('https', 'http') or not parsed.hostname or parsed.username or parsed.password:
        return None
    return url


def _parse_news(items: list, limit: int) -> list[dict]:
    results = []
    seen = set()
    for item in items or []:
        if not isinstance(item, dict):
            continue
        content = item.get('content') or item
        if not isinstance(content, dict):
            continue
        canonical = content.get('canonicalUrl') or {}
        link = canonical.get('url') if isinstance(canonical, dict) else None
        link = link or content.get('link') or item.get('link')
        url = _safe_news_url(link)
        title = str(content.get('title') or '').strip()
        if not url or not title or url in seen:
            continue
        provider = content.get('provider') or {}
        source = provider.get('displayName') if isinstance(provider, dict) else None
        published = content.get('pubDate') or content.get('providerPublishTime') or item.get('providerPublishTime')
        if isinstance(published, (int, float)):
            try:
                published = datetime.fromtimestamp(published, tz=timezone.utc).isoformat()
            except (ValueError, OverflowError, OSError):
                published = None
        results.append({
            'title': title[:400], 'url': url,
            'source': str(source or content.get('publisher') or item.get('publisher') or 'Publisher not supplied')[:120],
            'date': str(published or 'Publication time not supplied')[:100],
        })
        seen.add(url)
        if len(results) >= limit:
            break
    return results


def fetch_news(symbol: str, count: int = 5) -> tuple[list[dict], datetime]:
    """Existing headline-link API; full news-center ingestion lives elsewhere."""
    code = normalize_symbol(symbol)
    limit = max(1, min(int(count), 30))
    try:
        items = yf.Ticker(code).get_news(count=limit)
    except Exception as exc:
        raise MarketDataError('News could not be retrieved. Price analysis is still available.') from exc
    return _parse_news(items, limit), datetime.now(timezone.utc)


def rank_curated_stocks(market: str = 'US', metric: str = 'volume', limit: int = 8) -> list[dict]:
    """Rank the limited *curated universe*, not all stocks in the market.

    Results label coverage honestly. Avoid showing ranks when daily volume is
    absent or inconsistent; no fabricated market-wide 'most active' claim.
    """
    if metric not in ('volume', 'change_pct'):
        raise MarketDataError('Ranking metric must be volume or change_pct.')
    symbols = get_curated_stocks(market)[:12]
    results = []
    for code in symbols:
        try:
            frame, _ = fetch_prices(code, period='1mo')
            close = frame['Close']
            change_pct = (float(close.iloc[-1]) / float(close.iloc[-2]) - 1.0) * 100.0
            volume = _valid_number(frame['Volume'].iloc[-1]) if 'Volume' in frame else None
            if metric == 'volume' and volume is None:
                continue
            results.append({
                'symbol': code, 'market': identify_market(code),
                'latest_close': float(close.iloc[-1]), 'change_pct': change_pct,
                'volume': volume, 'as_of': str(frame.index[-1].date()),
                'universe': 'curated sample', 'source': DATA_PROVIDER,
            })
        except (MarketDataError, KeyError, TypeError, ValueError, IndexError):
            continue
    results.sort(key=lambda row: row[metric], reverse=True)
    return results[:max(1, min(int(limit), 12))]
