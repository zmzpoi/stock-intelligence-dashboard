"""Yahoo data adapter for LOCAL personal research. Public rights are unresolved."""
from datetime import datetime, timezone
import re
from urllib.parse import urlparse
import numpy as np
import pandas as pd
import yfinance as yf


class MarketDataError(Exception):
    pass


def normalize_symbol(symbol):
    symbol = symbol.strip().upper()
    if not re.fullmatch(r'\^?[A-Z0-9][A-Z0-9.-]{0,19}', symbol):
        raise MarketDataError('Enter a ticker such as AAPL, MSFT, NVDA or SAP.DE.')
    return symbol


def fetch_prices(symbol):
    symbol = normalize_symbol(symbol)
    ticker = yf.Ticker(symbol)
    try:
        prices = ticker.history(period='6mo', interval='1d', auto_adjust=False, timeout=15)
    except Exception as exc:
        raise MarketDataError('Market data request failed. Please try again later.') from exc
    if prices is None or prices.empty:
        raise MarketDataError('No data returned. Check the symbol; the provider may also be unavailable or rate-limiting requests.')
    if 'Close' not in prices or not isinstance(prices.index, pd.DatetimeIndex):
        raise MarketDataError('Unexpected price data format.')
    prices = prices.sort_index().copy()
    close = pd.to_numeric(prices['Close'], errors='coerce')
    if not np.isfinite(close.to_numpy(dtype=float)).all() or (close <= 0).any():
        raise MarketDataError('Missing or invalid prices received; analysis was stopped.')
    if prices.index.has_duplicates or prices.index.isna().any():
        raise MarketDataError('Duplicate or invalid trading dates received.')
    if len(prices) < 2:
        raise MarketDataError('At least two daily records are required.')
    prices['Close'] = close
    try:
        meta = ticker.get_history_metadata() or {}
    except Exception:
        meta = {}
    prices.attrs['company'] = meta.get('longName') or meta.get('shortName') or ''
    prices.attrs['currency'] = meta.get('currency') or ''
    prices.attrs['exchange'] = meta.get('fullExchangeName') or meta.get('exchangeName') or ''
    return prices, datetime.now(timezone.utc)


def fetch_news(symbol):
    symbol = normalize_symbol(symbol)
    try:
        items = yf.Ticker(symbol).get_news(count=5)
        results = []
        for item in items or []:
            content = item.get('content') or item
            canonical = content.get('canonicalUrl') or {}
            url = canonical.get('url') if isinstance(canonical, dict) else None
            url = url or content.get('link', '')
            parsed = urlparse(url)
            if parsed.scheme not in ('https', 'http') or not parsed.netloc:
                continue
            title = content.get('title')
            if not title:
                continue
            provider = content.get('provider') or {}
            source = provider.get('displayName') if isinstance(provider, dict) else None
            results.append({'title': str(title), 'url': url, 'source': source or content.get('publisher') or 'Publisher not supplied', 'date': str(content.get('pubDate') or 'Publication time not supplied')})
        return results, datetime.now(timezone.utc)
    except Exception as exc:
        raise MarketDataError('News could not be retrieved. Price analysis is still available.') from exc
