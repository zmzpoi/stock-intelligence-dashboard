"""Taurus AI 2.0 — global, multilingual, evidence-first stock research."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
import math
import os
import time
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from ai_analysis import AIAnalysisError, MODEL, explain
from i18n import language_options, t, format_number, format_percent
from indicators import analyze
from market_data import (
    MarketDataError, fetch_prices, fetch_fundamentals, get_market_indices,
    get_curated_stocks, normalize_symbol, resolve_symbol, search_stocks,
)
from news_data import fetch_company_news, fetch_market_news, filter_news
from presentation import LOGO, market_tile, stock_card, news_cards, section, movement_color

ROOT = Path(__file__).resolve().parent
st.set_page_config(page_title='Taurus AI | Global Stock Research', page_icon=str(ROOT/'assets/taurus-mark.svg'), layout='wide')
st.markdown('<style>'+(ROOT/'assets/style.css').read_text(encoding='utf-8')+'</style>',unsafe_allow_html=True)

# All data caches are local process-wide caches with bounded size/expiry.
@st.cache_data(ttl=900, max_entries=64, show_spinner=False)
def prices_cached(symbol, period='1y'):
    return fetch_prices(symbol, period=period)

@st.cache_data(ttl=900, max_entries=4, show_spinner=False)
def overview_cached(symbols):
    def pull(code):
        try:
            return code, fetch_prices(code, period='3mo')
        except Exception:
            return code, None
    with ThreadPoolExecutor(max_workers=3) as pool:
        return dict(pool.map(pull, symbols))

@st.cache_data(ttl=1800, max_entries=32, show_spinner=False)
def news_market_cached(market, topic, language):
    return fetch_market_news(market, topic, language, limit=14)

@st.cache_data(ttl=1800, max_entries=80, show_spinner=False)
def news_company_cached(symbol, company, language):
    return fetch_company_news(symbol, company, language, limit=12)

@st.cache_data(ttl=3600, max_entries=64, show_spinner=False)
def fundamentals_cached(symbol):
    return fetch_fundamentals(symbol)


def tr(key, **kwargs):
    return t(key, st.session_state.language, **kwargs)


def api_key():
    key = os.environ.get('GROQ_API_KEY', '').strip()
    if key:
        return key
    try:
        return str(st.secrets.get('GROQ_API_KEY','')).strip()
    except Exception:
        return ''


def navigate(page):
    # Navigation radio was already created in this run; queue the next value.
    st.session_state.pending_nav = page


def choose_stock(code):
    st.session_state.symbol = code
    st.session_state.search_error = ''
    st.session_state.search_matches = []
    navigate('research')


def handle_search(raw):
    st.session_state.search_error = ''
    st.session_state.search_matches = []
    try:
        code = resolve_symbol(raw)
        choose_stock(code)
    except MarketDataError as exc:
        # An ambiguous company name can return several exchange listings.
        try:
            results = search_stocks(raw)
        except MarketDataError:
            results = []
        if len(results) > 1:
            st.session_state.search_matches = results
        elif len(results) == 1:
            choose_stock(results[0]['symbol'])
        else:
            st.session_state.search_error = str(exc)


def search_area(name, hero=False):
    with st.form('find_'+name, border=False):
        val = st.text_input(tr('search.label'), value='', key='query_'+name,
                            placeholder=tr('home.search.placeholder'), label_visibility='collapsed')
        submitted = st.form_submit_button(tr('home.search.button'), type='primary', width='stretch')
    if submitted:
        handle_search(val)
        st.rerun()
    if st.session_state.search_error:
        st.warning(st.session_state.search_error)
    matches = st.session_state.search_matches
    if matches:
        labels = [f"{x['name']} · {x['symbol']} · {x['exchange'] or x['market']}" for x in matches]
        idx = st.selectbox(tr('search.ambiguous'),range(len(matches)),format_func=lambda n:labels[n], key='match_'+name)
        if st.button(tr('home.open_research'),key='use_match_'+name):
            choose_stock(matches[idx]['symbol'])
            st.rerun()
    if hero:
        st.caption('AAPL · NVDA · TSLA · 贵州茅台 · 腾讯 · SAP.DE')


def date_label(frame, retrieved):
    date = str(frame.index[-1].date())
    source = frame.attrs.get('source') or 'Yahoo Finance via yfinance'
    return f'{tr("stock.trading_date")}: {date} · {source} · {tr("common.retrieved_at", time=retrieved.strftime("%Y-%m-%d %H:%M UTC"))} · {tr("market.not_live")}'


def price_block(code, name, result):
    with st.container(border=True):
        stock_card(code,name,result, st.session_state.market_colors,st.session_state.language)
        if st.button(tr('home.open_research'), key='go_'+code, width='stretch'):
            choose_stock(code)
            st.rerun()


def maybe_news(kind='market', symbol='', company='', market='US', topic='general', limit=6, keyword='', within=0):
    try:
        if kind == 'company':
            items, retrieved = news_company_cached(symbol, company, st.session_state.language)
        else:
            items, retrieved = news_market_cached(market, topic, st.session_state.language)
        items = filter_news(items, keyword, within_days=within)[:limit]
        if not items:
            st.info(tr('news.no_match'))
        else:
            news_cards(items, st.session_state.language)
        st.caption(f'{tr("news.provider_note")} · {tr("common.retrieved_at", time=retrieved.strftime("%Y-%m-%d %H:%M UTC"))}')
        return items
    except (MarketDataError, ValueError, OSError):
        st.info(tr('news.unavailable'))
        return []


def home():
    st.markdown('<div class="search-hero"><div class="hero-mark">'+LOGO+'</div><div class="hero-title">TAURUS AI</div><div class="hero-kicker">'+tr('app.tagline')+'</div><div class="hero-descriptor">'+tr('app.subtitle')+'</div></div>', unsafe_allow_html=True)
    a,b,c=st.columns([1,2.15,1])
    with b:
        search_area('home',hero=True)
    st.markdown('<div class="section-spacer"></div>', unsafe_allow_html=True)
    section(tr('home.market_overview'),tr('home.market_note'))
    indices = [get_market_indices(m)[0] for m in ('US','CN','HK','EU')]
    # Additional index: Nasdaq Composite and CSI 300 to reflect both markets.
    indices.insert(1,get_market_indices('US')[1])
    indices.insert(4,get_market_indices('CN')[2])
    with st.spinner(tr('common.loading')):
        bundle=overview_cached(tuple(x['symbol'] for x in indices))
    cols=st.columns(3)
    for i,item in enumerate(indices):
        with cols[i%3]:
            market_tile(item['symbol'],item['name'],bundle.get(item['symbol']),st.session_state.market_colors,st.session_state.language)
    st.markdown('<div class="section-spacer"></div>', unsafe_allow_html=True)
    section(tr('home.trending'),tr('home.trending_note'))
    st.caption(tr('v2.market_examples'))
    picks=[('AAPL','Apple'),('NVDA','NVIDIA'),('MSFT','Microsoft'),('600519.SS','贵州茅台')]
    # Reuse only existing overview prices where possible; do not silently fire extra I/O.
    # Load a bounded sample with its own cache only when expanded.
    with st.expander(tr('home.quick_start'),expanded=True):
        cols=st.columns(4)
        for idx,(code,name) in enumerate(picks):
            with cols[idx]:
                with st.container(border=True):
                    st.markdown(f'**{name}**')
                    st.caption(code)
                    if st.button(tr('home.open_research'),key='featured_'+code,width='stretch'):
                        choose_stock(code);st.rerun()
    section(tr('home.top_news'),tr('home.top_news_note'))
    maybe_news(limit=5)


def markets():
    section(tr('nav.markets'),tr('market.not_live'))
    names={'US':tr('market.us'),'CN':tr('market.cn'),'HK':tr('market.hk'),'EU':tr('market.eu')}
    market=st.segmented_control(tr('common.market'),list(names),default='US',format_func=lambda x:names[x],key='market_tab')
    market=market or 'US'
    indices=get_market_indices(market)
    with st.spinner(tr('common.loading')):
        data=overview_cached(tuple(x['symbol'] for x in indices))
    cols=st.columns(min(3,len(indices)))
    for i,item in enumerate(indices):
        with cols[i%len(cols)]:
            market_tile(item['symbol'],item['name'],data.get(item['symbol']),st.session_state.market_colors,st.session_state.language)
    section(tr('home.trending'),tr('v2.curated'))
    stocks=get_curated_stocks(market)
    cols=st.columns(4)
    for i,code in enumerate(stocks):
        with cols[i%4]:
            with st.container(border=True):
                st.markdown(f'**{code}**')
                if st.button(tr('home.open_research'),key='market_'+code):
                    choose_stock(code);st.rerun()
    section(tr('news.top_stories'))
    maybe_news(market=market,limit=6)


def price_chart(frame, currency):
    left,right=st.columns([3,1])
    with left:
        window=st.radio(tr('chart.range'),['1M','3M','6M','1Y'],index=2,horizontal=True)
    with right:
        chart_type=st.selectbox(tr('chart.title'),['Line','Candlestick'],label_visibility='collapsed')
    shown=frame.tail({'1M':23,'3M':66,'6M':132,'1Y':260}[window])
    fig=go.Figure()
    if chart_type=='Candlestick' and all(c in shown for c in ('Open','High','Low','Close')) and shown[['Open','High','Low','Close']].notna().all().all():
        fig.add_trace(go.Candlestick(x=shown.index,open=shown.Open,high=shown.High,low=shown.Low,close=shown.Close,
                                   name='OHLC',increasing_line_color='#285EC5',decreasing_line_color='#C87934'))
    else:
        fig.add_trace(go.Scatter(x=shown.index,y=shown.Close,mode='lines',name='Close',line=dict(color='#5266C6',width=2.5)))
    for field,color in [('SMA20','#A2AECB'),('SMA50','#BB9B65')]:
        fig.add_trace(go.Scatter(x=shown.index,y=shown[field],mode='lines',name=field,line=dict(color=color,width=1.8),connectgaps=False))
    fig.update_layout(template='plotly_white',height=410,margin=dict(l=12,r=12,t=25,b=10),paper_bgcolor='rgba(0,0,0,0)',plot_bgcolor='#FFFFFF',
                      yaxis_title=currency,hovermode='x unified',legend=dict(orientation='h',y=1.12),xaxis_rangeslider_visible=False)
    fig.update_yaxes(gridcolor='#E9EDF3')
    fig.update_xaxes(gridcolor='#F1F3F8')
    st.plotly_chart(fig,width='stretch')
    with st.expander(tr('chart.inspect_data')):
        fields=[x for x in ('Open','High','Low','Close','Volume','SMA20','SMA50','RSI14','MACD') if x in frame]
        st.dataframe(frame[fields].tail(90).sort_index(ascending=False),width='stretch')


def fundamentals_panel(code):
    st.caption(tr('v2.mixed_periods'))
    if not st.button(tr('v2.load_fund'),key='fund_load_'+code):
        # Stored only per current stock; avoid extra requests when browsing tabs.
        if st.session_state.get('fund_loaded_symbol')!=code:
            return None
    try:
        with st.spinner(tr('common.loading')):
            result,retrieved=fundamentals_cached(code)
    except MarketDataError as exc:
        st.info(str(exc));return None
    st.session_state.fund_loaded_symbol=code
    st.caption(result.get('source','')+' · '+tr('common.retrieved_at',time=retrieved.strftime('%Y-%m-%d %H:%M UTC')))
    if result.get('sector'):
        st.write(f"{result['sector']} · {result.get('industry','')}")
    if result.get('description'):
        with st.expander(tr('stock.about_company')):
            st.write(result['description'])
    metrics=result.get('metrics',{})
    groups=[(tr('fund.valuation'),[('trailing_pe','P/E'),('price_to_book','P/B'),('market_cap','Market cap')]),
            (tr('fund.profitability'),[('trailing_eps','EPS'),('profit_margin','Profit margin'),('return_on_equity','ROE')]),
            (tr('fund.growth'),[('revenue_growth','Revenue growth'),('earnings_growth','Earnings growth'),('total_revenue','Revenue')]),
            (tr('fund.balance_sheet'),[('total_cash','Cash'),('total_debt','Debt'),('free_cashflow','Free cash flow')])]
    for group,fields in groups:
        st.markdown('**'+group+'**')
        cols=st.columns(3)
        for col,(key,label) in zip(cols,fields):
            v=metrics.get(key)
            if v is None:
                value='—'
            elif key in ('profit_margin','return_on_equity','revenue_growth','earnings_growth'):
                value=f'{v*100:+.1f}%'
            elif key in ('total_cash','total_debt','free_cashflow','total_revenue','market_cap'):
                value=f'{v/1e9:,.2f}B' if abs(v)>=1e9 else f'{v:,.0f}'
            else:
                value=f'{v:,.2f}'
            col.metric(label,value)
    st.caption(result.get('period_note',''))
    return result


def research_data():
    code=st.session_state.symbol
    try:
        with st.spinner(tr('common.loading')):
            prices,retrieved=prices_cached(code)
        frame,signal,reasons=analyze(prices)
    except (MarketDataError,ValueError,KeyError,TypeError,IndexError) as exc:
        st.error(str(exc));st.info(tr('stock.price_not_available'))
        if st.button(tr('common.retry')):
            prices_cached.clear();st.rerun()
        return None
    # Do not present ancient records as current technical signals.
    observation=frame.index[-1]
    try:
        day=observation.date()
        age=(datetime.now(timezone.utc).date()-day).days
        if age > 14 or age < -1:
            st.warning(tr('v2.stale'))
            signal='UNAVAILABLE'
            reasons=['The daily price observation is stale or in the future; no current technical signal is issued.']
    except (TypeError, AttributeError):
        pass
    return code,prices,frame,signal,reasons,retrieved


def ai_panel(context,key):
    code,prices,frame,signal,reasons,retrieved=context
    last=frame.iloc[-1]
    report_signature=f'{code}|{frame.index[-1].date()}|{float(last.Close):.4f}'
    st.markdown('### '+tr('ai.title'))
    st.caption(tr('ai.snapshot_note'))
    key_present=bool(api_key())
    if not key_present:
        st.info(tr('ai.key_missing'))
    if st.button(tr('ai.generate'),type='primary',disabled=not key_present,key='ai_generate_'+key):
        previous=st.session_state.get('last_ai_attempt',0.)
        if time.time()-previous < 45:
            st.warning(tr('ai.cooldown'))
        else:
            st.session_state.last_ai_attempt=time.time()
            snap={'symbol':code,'data_provider':prices.attrs.get('source','Yahoo Finance via yfinance'),
                  'trading_date':str(frame.index[-1].date()),'retrieved_at_utc':retrieved.isoformat(),
                  'currency':prices.attrs.get('currency') or 'not supplied',
                  'technical_signal':signal,'rule_reasons':reasons}
            for col in ('Close','SMA20','SMA50','RSI14','MACD','MACD_signal'):
                v=last.get(col)
                snap[col]=round(float(v),4) if v is not None and pd.notna(v) and math.isfinite(float(v)) else None
            # Fundamentals and headlines are best effort; a failed source never fails the report.
            try:
                f,_=fundamentals_cached(code)
                snap['fundamentals']={'company':f.get('company'),'sector':f.get('sector'),
                   'metrics':{k:(round(v,5) if v is not None else None) for k,v in f.get('metrics',{}).items()},
                   'source':f.get('source'),'period_note':f.get('period_note')}
            except MarketDataError:
                snap['fundamentals']='unavailable'
            try:
                articles,_=news_company_cached(code,prices.attrs.get('company') or '',st.session_state.language)
                snap['headlines']=[{k:article.get(k) for k in ('title','source','date','url')} for article in articles[:5]]
            except MarketDataError:
                snap['headlines']='unavailable'
            try:
                with st.spinner(tr('ai.generating')):
                    answer=explain(snap,api_key(),st.session_state.language)
                st.session_state.ai_report=(report_signature,st.session_state.language,answer,datetime.now(timezone.utc))
            except AIAnalysisError as exc:
                st.warning(str(exc))
    report=st.session_state.get('ai_report')
    if report and report[0]==report_signature and report[1]==st.session_state.language:
        with st.container(border=True):
            st.markdown(report[2])
        st.caption(f'{MODEL} · {report[3]:%Y-%m-%d %H:%M UTC} · {tr("legal.ai_warning")}')
    st.caption(tr('legal.educational'))


def research(only_ai=False):
    section(tr('nav.ai') if only_ai else tr('nav.research'), tr('stock.research_scope'))
    search_area('research')
    context=research_data()
    if context is None:
        return
    code,prices,frame,signal,reasons,retrieved=context
    company=prices.attrs.get('company') or code
    st.title(f'{company} · {code}' if company != code else code)
    st.caption(f"{prices.attrs.get('exchange') or ''} · {prices.attrs.get('currency') or ''} · {date_label(frame,retrieved)}")
    bad=prices.attrs.get('discarded_invalid_close_rows',0)
    if bad:
        st.warning(tr('v2.invalid_rows',count=bad))
    if st.button(tr('stock.refresh'), key='research_refresh'):
        prices_cached.clear();st.rerun()
    last=frame.iloc[-1];price=float(last.Close)
    delta=(price/float(frame.Close.iloc[-2])-1)*100
    cols=st.columns(4)
    cols[0].metric(tr('stock.latest_price'),f'{price:,.2f}',f'{delta:+.2f}%')
    for col,key,label in zip(cols[1:],('SMA20','SMA50','RSI14'),('SMA20','SMA50','RSI(14)')):
        val=last[key];col.metric(label,f'{val:,.2f}' if pd.notna(val) else '—')
    if only_ai:
        ai_panel(context,'standalone');return
    TAB_KEYS=('overview','chart','fundamentals','news','ai')
    TAB_TEXT={'overview':'stock.overview','chart':'stock.chart',
              'fundamentals':'stock.fundamentals','news':'stock.company_news',
              'ai':'stock.ai_insights'}
    panel=st.segmented_control(tr('v2.research_sections'),TAB_KEYS,default='overview',
                               format_func=lambda k:tr(TAB_TEXT[k]),key='research_tab',label_visibility='collapsed') or 'overview'
    if panel=='overview':
        col_a,col_b=st.columns([2.2,1])
        with col_a:
            price_chart(frame,prices.attrs.get('currency') or '')
        with col_b:
            st.markdown('#### '+tr('indicator.signal'))
            color=movement_color({'BUY':1,'SELL':-1}.get(signal,0),st.session_state.market_colors)
            st.markdown(f'<div class="signal-word" style="color:{color}">{signal}</div>',unsafe_allow_html=True)
            st.caption(tr('v2.rule_method'))
            for reason in reasons:
                st.write('• '+reason)
            with st.expander(tr('indicator.methodology')):
                st.write('BUY: Close > SMA20 > SMA50 & 50 ≤ RSI < 70; SELL: Close < SMA20 < SMA50 & 30 < RSI < 50; otherwise HOLD. Needs 50+ valid daily bars. Not backtested or personalized.')
    elif panel=='chart':
        price_chart(frame,prices.attrs.get('currency') or '')
        st.markdown('#### '+tr('v2.rsi_chart'))
        fig=go.Figure()
        shown=frame.tail(140)
        fig.add_trace(go.Scatter(x=shown.index,y=shown.RSI14,name='RSI(14)',line=dict(color='#5266C6')))
        fig.add_hline(y=70,line_dash='dash',line_color='#C87934')
        fig.add_hline(y=30,line_dash='dash',line_color='#285EC5')
        fig.update_layout(height=220,margin=dict(l=10,r=10,t=15,b=10),paper_bgcolor='rgba(0,0,0,0)',plot_bgcolor='#FFFFFF')
        st.plotly_chart(fig,width='stretch')
        st.caption(tr('v2.rsi_note'))
    elif panel=='fundamentals':
        fundamentals_panel(code)
    elif panel=='news':
        maybe_news(kind='company',symbol=code,company=company,limit=10)
    else:
        ai_panel(context,'tab')


def news_page():
    section(tr('news.title'),tr('news.description'))
    market_names={'US':tr('market.us'),'CN':tr('market.cn'),'HK':tr('market.hk'),'EU':tr('market.eu')}
    c1,c2,c3=st.columns([1,1,2])
    with c1:market=st.selectbox(tr('news.filter.market'),list(market_names),format_func=lambda x:market_names[x])
    with c2:topic=st.selectbox(tr('news.filter.topic'),list(('general','technology','macro','earnings')),
                            format_func=lambda x: {'general':tr('news.top_stories'),'technology':tr('news.technology'),'macro':tr('news.macro'),'earnings':tr('news.earnings')}[x])
    with c3:keyword=st.text_input(tr('news.filter.keyword'),placeholder=tr('search.placeholder'))
    days=st.selectbox(tr('news.filter.time'),[0,1,7,30],format_func=lambda n:tr({0:'v2.all_time',1:'v2.one_day',7:'v2.seven_days',30:'v2.thirty_days'}[n]))
    maybe_news(market=market,topic=topic,limit=14,keyword=keyword,within=days)
    st.markdown('### '+tr('news.company'))
    st.caption(st.session_state.symbol)
    maybe_news(kind='company',symbol=st.session_state.symbol,limit=6,keyword=keyword,within=days)


# Stable navigation codes survive language switching.
st.session_state.setdefault('language','en')
st.session_state.setdefault('market_colors','neutral')
st.session_state.setdefault('symbol','AAPL')
st.session_state.setdefault('nav','home')
if 'pending_nav' in st.session_state:
    st.session_state.nav = st.session_state.pop('pending_nav')
st.session_state.setdefault('search_error','')
st.session_state.setdefault('search_matches',[])
head_brand,head_nav,head_options=st.columns([1.6,3,1.4],gap='small')
with head_brand:
    st.markdown('<div class="brand">'+LOGO+'<div><b>TAURUS <span>AI</span></b><small>GLOBAL RESEARCH</small></div></div>',unsafe_allow_html=True)
with head_nav:
    NAV={'home':'nav.home','markets':'nav.markets','research':'nav.research','news':'nav.news','ai':'nav.ai'}
    st.radio('Navigation',list(NAV),format_func=lambda value:tr(NAV[value]),horizontal=True,label_visibility='collapsed',key='nav')
with head_options:
    languages=list(language_options())
    lang_codes=[a[0] for a in languages]
    st.selectbox('Language / 语言',lang_codes,format_func=lambda code:dict(languages)[code],key='language',label_visibility='collapsed')
    options={'neutral':'Blue ↑ / Orange ↓','us':'US · Green ↑','cn':'A-share · Red ↑'}
    st.selectbox(tr('settings.market_colors'),list(options),format_func=lambda x:options[x],key='market_colors',label_visibility='collapsed')
st.markdown('<div class="nav-divider"></div>',unsafe_allow_html=True)
page=st.session_state.nav
if page=='home':home()
elif page=='markets':markets()
elif page=='news':news_page()
elif page=='ai':research(only_ai=True)
else:research()
st.markdown('<div class="site-footer"><b>TAURUS AI</b><span>'+tr('v2.backup_note')+'</span></div>',unsafe_allow_html=True)
st.caption('Market data: Yahoo Finance via yfinance (best-effort, may be delayed). News: Google News RSS / Yahoo fallback. Public display/reuse rights must be independently verified.')
