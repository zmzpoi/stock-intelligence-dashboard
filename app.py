"""Taurus AI — an evidence-first stock research workspace."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import os
from pathlib import Path
import time
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from ai_analysis import AIAnalysisError, MODEL, explain
from indicators import analyze
from market_data import MarketDataError, fetch_news, fetch_prices
from presentation import LOGO, section, market_tile, stock_card, news_cards

ROOT = Path(__file__).resolve().parent
MARKETS = [('^GSPC', 'S&P 500'), ('^IXIC', 'Nasdaq Composite'), ('^GDAXI', 'DAX')]
COMPANIES = [('AAPL', 'Apple'), ('MSFT', 'Microsoft'), ('NVDA', 'NVIDIA'), ('SAP.DE', 'SAP')]
st.set_page_config(page_title='Taurus AI | Stock research', page_icon=str(ROOT/'assets/taurus-mark.svg'), layout='wide')
st.markdown('<style>'+(ROOT/'assets/style.css').read_text()+'</style>', unsafe_allow_html=True)


@st.cache_data(ttl=600, max_entries=32, show_spinner=False)
def load_prices(symbol):
    return fetch_prices(symbol)


@st.cache_data(ttl=600, max_entries=2, show_spinner=False)
def load_overview():
    # Bounded concurrent I/O; no Streamlit calls inside worker threads.
    def fetch(symbol):
        try:
            return symbol, fetch_prices(symbol)
        except Exception:
            return symbol, 'Market data unavailable'
    symbols = [s for s, _ in MARKETS + COMPANIES]
    with ThreadPoolExecutor(max_workers=3) as pool:
        return dict(pool.map(fetch, symbols))


@st.cache_data(ttl=300, max_entries=32, show_spinner=False)
def load_news(symbol):
    try:
        return fetch_news(symbol)
    except Exception:
        return 'News is temporarily unavailable. You can still use price analysis.'


def get_api_key():
    key = os.environ.get('GROQ_API_KEY', '').strip()
    if key:
        return key
    try:
        return str(st.secrets.get('GROQ_API_KEY', '')).strip()
    except (FileNotFoundError, st.errors.StreamlitSecretNotFoundError):
        return ''


def select_symbol(symbol):
    st.session_state.active_symbol = symbol
    st.session_state.nav = 'Stock research'


def submit_search(widget_key):
    select_symbol(st.session_state[widget_key].strip().upper())


def search_box(key, compact=False):
    if not compact:
        st.markdown('<div class="rail-eyebrow">YOUR AI RESEARCH ASSISTANT</div>', unsafe_allow_html=True)
        st.markdown('### What’s on your radar?')
        st.caption('Start with a ticker. Explore the trend, then ask Taurus to explain the evidence.')
    with st.form(f'search_{key}'):
        st.text_input('Stock symbol', value=st.session_state.active_symbol, key=key, placeholder='Try AAPL, NVDA or SAP.DE', max_chars=20)
        st.form_submit_button('Research this stock →', type='primary', on_click=submit_search, args=(key,), width='stretch')
    if not compact:
        st.caption('Real market data · Explainable rules · Optional AI')


def render_news(symbol, limit=5, keyword=''):
    result = load_news(symbol)
    if isinstance(result,str):
        st.caption(result)
        if st.button('Retry headlines', key=f'retry_{symbol}'):
            load_news.clear(symbol)
            st.rerun()
        return
    items, fetched = result
    if keyword:
        needle = keyword.casefold()
        items = [x for x in items if needle in (x['title']+' '+x['source']).casefold()]
    if not items:
        st.caption('No matching headlines were returned. No sample news is substituted.')
    else:
        news_cards(items[:limit])
    st.caption(f'Via Yahoo Finance · retrieved {fetched:%d %b %H:%M} UTC. Provider relevance may vary.')


def render_home():
    left, right = st.columns([2.1, 1], gap='large')
    with left:
        st.markdown('<div class="hero"><div class="overline">TAURUS AI · INDEPENDENT STOCK RESEARCH</div><h1>A clearer view<br>of the market.</h1><p>Your AI-powered stock research assistant.<br>Explore the trends. Understand the signals. Question the story.</p><div class="hero-art">'+LOGO+'</div></div>', unsafe_allow_html=True)
    with right:
        with st.container(key='research_entry'):
            search_box('home_search')
    title, refresh = st.columns([5,1])
    with title:
        section('Market pulse', 'Latest available daily observations · not a live feed')
    with refresh:
        if st.button('↻ Refresh', key='refresh_home'):
            load_overview.clear()
    with st.spinner('Loading your market overview…'):
        bundle = load_overview()
    for col, (symbol,name) in zip(st.columns(3), MARKETS):
        with col:
            market_tile(symbol,name,bundle.get(symbol))
    st.markdown('<div class="feature-strip"><span><b>01</b> &nbsp; Read the market</span><span><b>02</b> &nbsp; Inspect the signal</span><span><b>03</b> &nbsp; Ask better questions</span></div>', unsafe_allow_html=True)
    stocks, news = st.columns([2.1,1], gap='large')
    with stocks:
        section('On the radar', 'A curated list, not a popularity ranking')
        for i in range(0,len(COMPANIES),2):
            for col,(symbol,name) in zip(st.columns(2),COMPANIES[i:i+2]):
                with col:
                    with st.container(border=True):
                        stock_card(symbol,name,bundle.get(symbol))
                        st.button('Explore '+symbol+' →', key='open_'+symbol, on_click=select_symbol, args=(symbol,), width='stretch')
        st.caption('Daily price changes compare the last two returned records. Small charts show the latest 22 observations. Figures can be delayed or incomplete; inspect each date before use.')
    with news:
        section('In the headlines', 'Publisher links ↗')
        render_news('^GSPC',limit=4)
    with st.expander('About Taurus AI'):
        st.write('Taurus combines market data, transparent technical rules and an optional AI explanation. It is a research prototype, not a validated investment strategy. BUY / HOLD / SELL labels come from the rule engine; the LLM explains the supplied snapshot. News is shown separately and is not included in the AI analysis yet.')
        st.write('The Yahoo-backed version remains a local personal research preview. Public market-data display permission and deployment are still pending.')


def render_news_page():
    section('The news desk', 'Headlines and original sources')
    st.caption('Find provider headlines for a ticker, then filter the returned results. This is not a search across the entire web.')
    with st.form('news_search'):
        c1,c2,c3 = st.columns([2,3,1])
        with c1:
            ticker = st.text_input('News ticker', value=st.session_state.active_symbol, max_chars=20)
        with c2:
            keyword = st.text_input('Filter loaded headlines', placeholder='e.g. earnings')
        with c3:
            st.write('')
            apply = st.form_submit_button('Find news',type='primary')
    if apply:
        st.session_state.news_query = (ticker.strip().upper(),keyword.strip())
    symbol, keyword = st.session_state.get('news_query',(st.session_state.active_symbol,''))
    render_news(symbol,keyword=keyword)


def render_research(api_key):
    top_left, top_right = st.columns([2.1,1],gap='large')
    with top_left:
        section('Stock research', 'Price → indicators → signal → explanation')
        st.caption('Follow the evidence behind the signal. The AI brief is generated only when you request it.')
    with top_right:
        search_box('research_search',compact=True)
    symbol = st.session_state.active_symbol
    if st.button('Refresh selected stock'):
        load_prices.clear(symbol)
    try:
        with st.spinner('Retrieving market data…'):
            prices, fetched_at = load_prices(symbol)
    except MarketDataError as exc:
        st.error(str(exc))
        st.info('Try another symbol or retry later. No substitute data is displayed.')
        st.stop()
    except Exception:
        st.error('An unexpected data error occurred. No analysis was generated.')
        st.stop()

    frame, signal, reasons = analyze(prices)
    last = frame.iloc[-1]
    last_price = float(last['Close'])
    change_pct = (last_price / float(frame['Close'].iloc[-2]) - 1) * 100
    trading_date = frame.index[-1].date()
    age_days = (datetime.now(timezone.utc).date() - trading_date).days
    if age_days > 7 or age_days < 0:
        signal = 'UNAVAILABLE'
        reasons = ['The latest trading date is stale or in the future. A signal is withheld.']
        st.warning('Price data is outside the freshness check (0–7 calendar days). Verify the source.')
    company = prices.attrs.get('company') or symbol
    currency = prices.attrs.get('currency') or 'currency unavailable'
    st.subheader(f'{company} · {symbol}' if company != symbol else symbol)
    st.caption(f'{prices.attrs.get("exchange") or "Exchange not supplied"}  /  Daily data  /  {currency}')

    cards = st.columns(4)
    cards[0].metric('Latest available daily price', f'{last_price:,.2f}', f'{change_pct:+.2f}% vs previous record')
    for column, field, label in zip(cards[1:], ['SMA20', 'SMA50', 'RSI14'], ['20-day average', '50-day average', 'RSI · 14 days']):
        value = last[field]
        column.metric(label, 'Unavailable' if pd.isna(value) else f'{value:,.2f}')
    st.caption(f'Trading date: {trading_date} · Retrieved: {fetched_at:%Y-%m-%d %H:%M:%S} UTC · Cache: up to 10 minutes')

    chart_col, insight_col = st.columns([2.1, 1], gap='large')
    with chart_col:
        st.markdown('### Price & trend')
        window = st.radio('Chart window', ['1M', '3M', '6M'], index=2, horizontal=True)
        shown = frame.tail({'1M': 22, '3M': 66, '6M': len(frame)}[window])
        fig = go.Figure()
        for field, color, width in [('Close', '#146b4b', 3), ('SMA20', '#87a56e', 1.6), ('SMA50', '#9a742b', 1.6)]:
            fig.add_trace(go.Scatter(x=shown.index, y=shown[field], name=field, mode='lines', line=dict(color=color, width=width), connectgaps=False))
        fig.update_layout(template='plotly_white', height=390, paper_bgcolor='#f5f6f2', plot_bgcolor='#f5f6f2', margin=dict(l=5,r=5,t=20,b=10), hovermode='x unified', legend=dict(orientation='h', y=1.12), yaxis_title=currency)
        fig.update_xaxes(showgrid=False)
        fig.update_yaxes(gridcolor='#e0e5dd')
        st.plotly_chart(fig, width='stretch')
        st.caption('Daily Close supplied by Yahoo; auto_adjust=False. Indicators use the same Close series. The latest daily bar may be incomplete. Chart windows approximate trading months.')
        with st.expander('Inspect prices and indicators'):
            st.dataframe(frame[['Close', 'SMA20', 'SMA50', 'RSI14']].tail(50), width='stretch')

    with insight_col:
        with st.container(border=True):
            st.caption('TECHNICAL RESEARCH SIGNAL · RULE ENGINE')
            color = {'BUY':'#146b4b', 'SELL':'#bd494b', 'HOLD':'#9a742b', 'UNAVAILABLE':'#758278'}[signal]
            st.markdown(f'<div class="signal-word" style="color:{color}">{signal}</div>', unsafe_allow_html=True)
            st.caption('Rule output, not an AI forecast or validated trading recommendation.')
            for reason in reasons:
                st.write('• ' + reason)
        with st.container(border=True):
            section('Company headlines')
            render_news(symbol, limit=3)

    st.divider()
    st.markdown('<div class="ai-banner"><h2>✧ The Taurus research brief</h2><p>Your signal, explained. A focused AI reading of the evidence.</p></div>', unsafe_allow_html=True)
    st.caption('Turn the observed signal into a readable explanation. No news or fundamentals are sent to the model in this version.')
    snapshot = {'symbol': symbol, 'currency': currency, 'trading_date': str(trading_date), 'retrieved_at_utc': fetched_at.isoformat(), 'rule_signal': signal, 'reasons': reasons}
    for field in ['Close', 'SMA20', 'SMA50', 'RSI14']:
        snapshot[field] = None if pd.isna(last[field]) else round(float(last[field]), 4)
    report_key = f'{symbol}|{fetched_at.isoformat()}'
    if not api_key:
        st.info('AI is not connected yet. The stock chart and technical signal work independently. A Groq Free tier key enables the real model integration.')
    st.caption('On request, the ticker and the displayed numeric snapshot are sent to Groq. Keep your provider account on the Free tier; this application cannot inspect your billing plan.')
    if st.button('Generate AI explanation', type='primary', disabled=not api_key or signal == 'UNAVAILABLE'):
        elapsed = time.time() - st.session_state.get('last_ai_attempt', 0)
        if elapsed < 30:
            st.warning('Please wait 30 seconds between AI requests.')
        else:
            st.session_state.last_ai_attempt = time.time()
            st.session_state.pop('ai_report', None)
            try:
                with st.spinner('Generating a grounded explanation…'):
                    text = explain(snapshot, api_key)
                st.session_state.ai_verified = True
                st.session_state.ai_report = (report_key, text, datetime.now(timezone.utc))
            except AIAnalysisError as exc:
                st.warning(str(exc))
    report = st.session_state.get('ai_report')
    if report and report[0] == report_key:
        with st.container(key='ai_output'):
            st.markdown(report[1])
        st.caption(f'AI-generated · Groq / {MODEL} · {report[2]:%Y-%m-%d %H:%M:%S} UTC · Verify model statements against the displayed values.')

    with st.expander('Methodology & limitations'):
        st.markdown('''
    **BUY:** Close > SMA20 > SMA50, and 50 ≤ RSI14 < 70.

    **SELL:** Close < SMA20 < SMA50, and 30 < RSI14 < 50.

    **HOLD:** Neither complete condition is met. HOLD is a neutral classification, not personal advice to keep a position.

    **UNAVAILABLE:** Fewer than 50 records, invalid indicators, or a latest date outside the 0–7 calendar day freshness check.

    SMA uses an arithmetic average. RSI uses Wilder smoothing seeded by the first 14 gains/losses; a flat series is assigned RSI=50. All indicators use the provider's Close series without dividend adjustment. Historical revisions, corporate actions and an incomplete current bar can change the result. No backtest, transaction costs, fundamentals, news assessment or personal suitability evaluation is included. An LLM explains the numeric evidence; it does not establish predictive accuracy. This is a fixed workflow, not an autonomous agent.''')


st.session_state.setdefault('active_symbol', 'AAPL')
st.session_state.setdefault('nav', 'Overview')
api_key = get_api_key()
brand, nav, status = st.columns([2.2,3.4,1.5], gap='small')
with brand:
    st.markdown('<div class="brand">'+LOGO+'<div><div class="brand-name">TAURUS <span>AI</span></div><div class="brand-sub">Clarity through evidence</div></div></div>', unsafe_allow_html=True)
with nav:
    st.radio('Navigation', ['Overview', 'Stock research', 'News'], horizontal=True, key='nav', label_visibility='collapsed')
with status:
    label = 'AI responded this session' if st.session_state.get('ai_verified') else 'AI key configured' if api_key else 'AI not connected'
    st.markdown('<div class="status"><b></b> '+label+'</div>', unsafe_allow_html=True)
st.divider()
if st.session_state.nav == 'Overview':
    render_home()
elif st.session_state.nav == 'News':
    render_news_page()
else:
    render_research(api_key)
st.markdown('<div class="footer"><span>TAURUS AI / Research with perspective.</span><span>Research demo · Not investment advice · No trading execution</span></div>', unsafe_allow_html=True)
st.caption('Yahoo Finance via yfinance · Local personal research preview. Public data display permission has not been established.')
