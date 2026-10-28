"""Safe reusable Streamlit presentation helpers and neutral market colors."""
from html import escape
from i18n import t
from pathlib import Path
from datetime import datetime
import math
import numpy as np
import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parent
LOGO = (ROOT / 'assets/taurus-mark.svg').read_text(encoding='utf-8')  # user-owned unchanged mark

PALETTES = {
    'neutral': ('#285EC5', '#C87934'),
    'us': ('#18794E', '#C3464C'),
    'cn': ('#C3464C', '#18794E'),
}


def movement_color(change, mode='neutral'):
    up, down = PALETTES.get(mode, PALETTES['neutral'])
    if change is None or not math.isfinite(float(change)) or change == 0:
        return '#64748B'
    return up if change > 0 else down


def sparkline(values, color='#5266C6'):
    points = np.asarray(values, dtype=float)
    points = points[np.isfinite(points)]
    if len(points) < 2:
        return ''
    low, high = float(points.min()), float(points.max())
    x = np.linspace(2, 298, len(points))
    y = 22 - ((points-low)/(high-low)-.5)*33 if high > low else np.full(len(points), 22.)
    path = ' '.join(f'{a:.1f},{b:.1f}' for a, b in zip(x, y))
    return f'<svg viewBox="0 0 300 46" class="spark" role="img" aria-label="Historical observations"><polyline points="{path}" fill="none" stroke="{color}" stroke-width="2.2" vector-effect="non-scaling-stroke"/></svg>'


def section(title: str, note: str = ''):
    st.markdown(f'<div class="section-head"><h2>{escape(title)}</h2><span>{escape(note)}</span></div>', unsafe_allow_html=True)


def market_tile(symbol, name, result, mode='neutral', language='en'):
    if result is None or isinstance(result, str):
        st.markdown(f'<div class="market-tile"><div class="market-head">{escape(name)}</div><div class="market-code">{escape(symbol)}</div><div class="muted">— · {escape(t("v2.data_unavailable", language))}</div></div>', unsafe_allow_html=True)
        return
    frame, retrieved = result
    if len(frame) < 2:
        return
    close = frame['Close'].astype(float)
    change = (close.iloc[-1]/close.iloc[-2]-1)*100
    hue = movement_color(change, mode)
    source_date = str(frame.index[-1].date())
    st.markdown(f'<div class="market-tile"><div class="market-head">{escape(name)}</div><div class="market-code">{escape(symbol)}</div><div class="market-number">{float(close.iloc[-1]):,.2f}</div><div style="color:{hue}" class="market-change">{change:+.2f}% <span>{escape(t("v2.previous_close", language))}</span></div>{sparkline(close.tail(30),hue)}<div class="tiny">{escape(source_date)} · {escape(t("v2.daily_observation", language))}</div></div>',unsafe_allow_html=True)


def stock_card(symbol, name, result, mode='neutral', language='en'):
    st.markdown(f'<div class="ticker-top"><div class="ticker-icon">{escape(name[:1] or "?")}</div><div><b>{escape(symbol)}</b><div class="tiny">{escape(name)}</div></div></div>', unsafe_allow_html=True)
    if result is None or isinstance(result, str):
        st.caption(t("v2.data_unavailable", language))
        return
    frame, retrieved = result
    close = frame['Close'].astype(float)
    change = (close.iloc[-1]/close.iloc[-2]-1)*100
    hue = movement_color(change, mode)
    unit = escape(str(frame.attrs.get('currency') or ''))
    st.markdown(f'<div class="ticker-values"><b>{close.iloc[-1]:,.2f}</b> <span>{unit}</span><span style="color:{hue}">{change:+.2f}%</span></div>'+sparkline(close.tail(25),hue)+f'<div class="tiny">{escape(str(frame.index[-1].date()))} · {escape(t("v2.daily_observation", language))}</div>',unsafe_allow_html=True)


def news_cards(items, language='en'):
    for item in items:
        try:
            dt = pd.to_datetime(item.get('date'), utc=True, errors='coerce')
            stamp = dt.strftime('%d %b %Y · %H:%M UTC') if not pd.isna(dt) else t('news.no_date', language)
        except (TypeError, ValueError):
            stamp = t('news.no_date', language)
        title = escape(item.get('title',''))
        url = escape(item.get('url',''), quote=True)
        provider = escape(item.get('source','Unspecified publisher'))
        st.markdown(f'<div class="news-card"><div class="news-meta">{provider} · {escape(stamp)}</div><div class="news-title"><a href="{url}" target="_blank" rel="noopener noreferrer">{title} ↗</a></div></div>',unsafe_allow_html=True)
