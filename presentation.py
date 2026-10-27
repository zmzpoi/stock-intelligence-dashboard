"""Escaped, data-driven UI fragments; no network calls or sample market data."""
from html import escape
from pathlib import Path
import numpy as np
import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parent
LOGO = (ROOT / 'assets/taurus-mark.svg').read_text()


def section(title, note=''):
    st.markdown(f'<div class="section-line"><h2>{escape(title)}</h2><span>{escape(note)}</span></div>', unsafe_allow_html=True)


def sparkline(values, color):
    values = np.asarray(values, dtype=float)
    lo, hi = float(values.min()), float(values.max())
    ys = 23 - ((values-lo) / (hi-lo) - .5) * 34 if hi > lo else np.full(len(values),23.)
    xs = np.linspace(2,298,len(values))
    points = ' '.join(f'{x:.1f},{y:.1f}' for x,y in zip(xs,ys))
    return f'<svg class="spark" viewBox="0 0 300 46" preserveAspectRatio="none" aria-label="Recent price trend"><polyline points="{points}" fill="none" stroke="{color}" stroke-width="2" vector-effect="non-scaling-stroke"/></svg>'


def market_tile(symbol, name, result):
    if isinstance(result, str) or result is None:
        value, delta, stamp = 'Unavailable', 'Request failed', ''
        cls = 'neutral'
    else:
        frame, fetched = result
        close = frame['Close']
        change = (float(close.iloc[-1])/float(close.iloc[-2])-1)*100
        value = f'{float(close.iloc[-1]):,.2f}'
        delta = f'{"+" if change >= 0 else ""}{change:.2f}%'
        cls = 'positive' if change >= 0 else 'negative'
        stamp = f'{frame.index[-1]:%d %b %Y} · retrieved {fetched:%H:%M} UTC'
    st.markdown(f'<div class="market-tile"><div class="market-head">{escape(name)}<span class="market-code">{escape(symbol)}</span></div><div class="market-number">{value}</div><div class="{cls}">{delta} <span class="market-code">vs previous daily record</span></div><div class="market-date">{stamp}</div></div>', unsafe_allow_html=True)


def stock_card(symbol, name, result):
    st.markdown(f'<div class="ticker-top"><div class="ticker-icon">{escape(name[:1])}</div><div><div class="ticker-symbol">{escape(symbol)}</div><div class="ticker-name">{escape(name)}</div></div></div>',unsafe_allow_html=True)
    if result is None or isinstance(result,str):
        st.caption('Price unavailable — open research to retry.')
        return
    frame, fetched = result
    close = frame['Close']
    change = (float(close.iloc[-1])/float(close.iloc[-2])-1)*100
    color, cls = ('#19714f','positive') if change >= 0 else ('#bd494b','negative')
    unit = escape(str(frame.attrs.get('currency') or 'unit unavailable'))
    st.markdown(f'<div class="ticker-values"><div class="ticker-price">{float(close.iloc[-1]):,.2f} <span class="unit">{unit}</span></div><div class="{cls}">{change:+.2f}%</div></div>'+sparkline(close.tail(22),color)+f'<div class="small-note">{frame.index[-1]:%d %b %Y} · retrieved {fetched:%H:%M} UTC · 22-observation trend</div>',unsafe_allow_html=True)


def news_cards(items):
    for item in items:
        # URLs have already been checked for an HTTP(S) scheme in the data adapter.
        date = item['date']
        try:
            stamp = pd.to_datetime(date, utc=True).strftime('%d %b %Y · %H:%M UTC')
        except (ValueError, TypeError):
            stamp = date
        st.markdown(f'<div class="news-card"><div class="news-meta">{escape(item["source"])}</div><div class="news-title"><a href="{escape(item["url"],quote=True)}" target="_blank" rel="noopener noreferrer">{escape(item["title"])} ↗</a></div><div class="news-time">{escape(stamp)}</div></div>',unsafe_allow_html=True)
