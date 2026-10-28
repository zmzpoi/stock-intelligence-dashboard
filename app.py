"""Taurus AI 3.0 — evidence-first global securities research (Streamlit)."""
from __future__ import annotations
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from html import escape
from pathlib import Path
import hashlib
import json
import os
import time

import pandas as pd
import streamlit as st

from ai_analysis import AIAnalysisError, MODEL, explain
from charting import WINDOWS, create_price_figure, window_bounds
from i18n import language_options, t
from indicators import IndicatorSettings, analyze
from market_data import (MarketDataError, LOCAL_COMPANY_NAMES, fetch_prices, fetch_fundamentals,
                         get_market_indices, get_curated_stocks, normalize_symbol,
                         resolve_symbol, search_stocks)
from news_data import fetch_company_news, fetch_market_news, filter_news
from presentation import LOGO, market_tile, news_cards, section, movement_color
from research_snapshot import build_snapshot, finite
from ui_labels import ui

ROOT = Path(__file__).resolve().parent
st.set_page_config(page_title='Taurus AI | Global Research',
                   page_icon=str(ROOT/'assets/taurus-mark.svg'),layout='wide')
st.markdown('<style>'+(ROOT/'assets/style.css').read_text(encoding='utf-8')+'</style>',
            unsafe_allow_html=True)


@st.cache_data(ttl=900, max_entries=96, show_spinner=False)
def prices_cached(symbol: str, period='5y'):
    return fetch_prices(symbol, period=period)


@st.cache_data(ttl=900, max_entries=24, show_spinner=False)
def overview_cached(symbols: tuple[str,...]):
    """Return best-effort data per ticker; a failure cannot erase market navigation."""
    def pull(code):
        try:
            return code, prices_cached(code, '3mo')
        except Exception:
            return code, None
    with ThreadPoolExecutor(max_workers=4) as pool:
        return dict(pool.map(pull, symbols))


@st.cache_data(ttl=3600, max_entries=64, show_spinner=False)
def fundamentals_cached(symbol):
    return fetch_fundamentals(symbol)


@st.cache_data(ttl=1800, max_entries=64, show_spinner=False)
def company_news_cached(symbol, name, lang):
    return fetch_company_news(symbol, name, lang, limit=10)


@st.cache_data(ttl=1800, max_entries=24, show_spinner=False)
def market_news_cached(market, topic, lang):
    return fetch_market_news(market, topic, lang, limit=12)


for k,v in {'language':'en','market_colors':'neutral','symbol':'AAPL','nav':'home',
            'search_error':'','search_matches':[], 'last_ai_attempt':0.0}.items():
    st.session_state.setdefault(k,v)
if 'pending_nav' in st.session_state:
    st.session_state['nav'] = st.session_state.pop('pending_nav')


def lang():
    return st.session_state.get('language','en')


def tr(key, **kwargs):
    return ui(key,lang(),**kwargs)


def api_key():
    # Never print or log the value, including in exception messages.
    value=os.environ.get('GROQ_API_KEY','').strip()
    if value:
        return value
    try:
        return str(st.secrets.get('GROQ_API_KEY','')).strip()
    except Exception:
        return ''


def navigate(page):
    st.session_state['pending_nav'] = page


def choose_stock(code, destination='research'):
    st.session_state['symbol'] = normalize_symbol(code)
    st.session_state['search_error'] = ''
    st.session_state['search_matches'] = []
    navigate(destination)
    st.rerun()


def handle_search(raw, destination):
    st.session_state['search_error'] = ''
    st.session_state['search_matches'] = []
    try:
        choose_stock(resolve_symbol(raw), destination)
    except MarketDataError as exc:
        try:
            matches = search_stocks(raw)
        except MarketDataError:
            matches = []
        if len(matches) == 1:
            choose_stock(matches[0]['symbol'],destination)
        elif matches:
            st.session_state['search_matches'] = matches
        else:
            st.session_state['search_error'] = str(exc)


def search_area(name, destination='research'):
    with st.form('search_form_'+name,border=False):
        query=st.text_input(tr('search.label'),key='query_'+name,
                            placeholder=tr('home.search.placeholder'),label_visibility='collapsed')
        submit=st.form_submit_button(tr('home.search.button'),type='primary',width='stretch')
    if submit:
        handle_search(query,destination)
    if st.session_state.get('search_error'):
        st.warning(st.session_state['search_error'])
    matches=st.session_state.get('search_matches') or []
    if matches:
        opts=range(len(matches))
        idx=st.selectbox(tr('search.ambiguous'),opts,
                         format_func=lambda i:f"{matches[i]['name']} · {matches[i]['symbol']} · {matches[i]['exchange'] or matches[i]['market']}",
                         key='match_'+name)
        if st.button(tr('stock_research'),key='choose_'+name):
            choose_stock(matches[idx]['symbol'],destination)


def display_name(symbol, frame=None):
    known=LOCAL_COMPANY_NAMES.get(symbol)
    if known:
        return known
    if frame is not None:
        title=frame.attrs.get('company')
        if isinstance(title,str) and title.strip() and title.upper()!=symbol:
            return title.strip()
    return symbol


def news_panel(kind='market',market='US',topic='general',symbol='',name='',keyword='',days=0,limit=8):
    try:
        if kind=='company':
            items, stamp=company_news_cached(symbol,name,lang())
        else:
            items, stamp=market_news_cached(market,topic,lang())
        filtered=filter_news(items,keyword,within_days=days)[:limit]
        if filtered:
            news_cards(filtered,lang())
        else:
            st.info(tr('news.no_match'))
        st.caption(tr('news.provider_note')+' · '+tr('common.retrieved_at',time=stamp.strftime('%Y-%m-%d %H:%M UTC')))
        return filtered
    except (MarketDataError,ValueError,TypeError,OSError):
        st.info(tr('news.unavailable'))
        return []


def index_cards(indices):
    if not indices:
        st.info(tr('price_unavailable'))
        return
    with st.spinner(tr('common.loading')):
        results=overview_cached(tuple(x['symbol'] for x in indices))
    cols=st.columns(min(3,len(indices)))
    for i,item in enumerate(indices):
        code=item['symbol']
        with cols[i%len(cols)]:
            market_tile(code,item['name'],results.get(code),st.session_state.market_colors,lang())
            if st.button(tr('index_research'),key='index_'+code+'_'+st.session_state.nav,width='stretch'):
                choose_stock(code)
    if not any(results.values()):
        st.info(tr('price_unavailable'))


def home():
    st.markdown('<div class="search-hero"><div class="hero-mark">'+LOGO+
                '</div><div class="hero-title">TAURUS AI</div><div class="hero-kicker">'+
                escape(tr('app.tagline'))+'</div><div class="hero-descriptor">'+
                escape(tr('app.subtitle'))+'</div></div>',unsafe_allow_html=True)
    left,center,right=st.columns([1,2.2,1])
    with center:
        search_area('home')
        st.caption('AAPL · NVDA · 600519 · 300750 · 0700.HK · SAP.DE')
    st.markdown('<div class="section-spacer"></div>',unsafe_allow_html=True)
    if st.button(tr('home.explore_markets'),key='goto_markets'):
        navigate('markets');st.rerun()
    section(tr('home.market_overview'),tr('home.market_note'))
    cards=[]
    for m,offset in [('US',0),('US',1),('CN',0),('CN',2),('HK',0),('EU',0)]:
        cards.append(get_market_indices(m)[offset])
    index_cards(cards)
    section(tr('home.quick_start'),tr('curated'))
    picks=[('AAPL','Apple'),('NVDA','NVIDIA'),('600519.SS','贵州茅台'),('0700.HK','腾讯控股')]
    cols=st.columns(4)
    for i,(code,name) in enumerate(picks):
        with cols[i]:
            with st.container(border=True):
                st.markdown('**'+name+'**')
                st.caption(code)
                if st.button(tr('stock_research'),key='pick_'+code,width='stretch'):
                    choose_stock(code)
    section(tr('home.top_news'),tr('home.top_news_note'))
    news_panel(limit=5)


def markets():
    section(tr('nav.markets'),tr('market.not_live'))
    choices={'US':tr('market.us'),'CN':tr('market.cn'),'HK':tr('market.hk'),'EU':tr('market.eu')}
    m=st.segmented_control(tr('common.market'),list(choices),default='US',
                           format_func=lambda code:choices[code],key='market_tab') or 'US'
    st.markdown('### '+tr('market.indices'))
    index_cards(get_market_indices(m))
    st.markdown('### '+tr('home.quick_start'))
    st.caption(tr('curated'))
    picks=get_curated_stocks(m)
    cards=st.columns(min(4,len(picks)))
    for i,code in enumerate(picks):
        with cards[i%len(cards)]:
            with st.container(border=True):
                st.markdown('**'+escape(display_name(code))+'**')
                st.caption(code)
                if st.button(tr('stock_research'),key='market_'+code,width='stretch'):
                    choose_stock(code)
    st.markdown('### '+tr('news.top_stories'))
    news_panel(market=m,limit=6)


def reset_indicator_state():
    for k in ('set_rsi','set_sma_fast','set_sma_slow','set_ema','set_macd_fast',
              'set_macd_slow','set_macd_signal','set_bb_period','set_bb_std'):
        st.session_state.pop(k, None)


def indicator_controls():
    st.markdown('#### '+tr('settings'))
    with st.expander(tr('settings'),expanded=False):
        ca,cb,cc=st.columns(3)
        with ca:
            rsi=st.slider(tr('rsi_period'),5,30,14,key='set_rsi')
            fast=st.slider(tr('sma_fast'),5,49,20,key='set_sma_fast')
            slow=st.slider(tr('sma_slow'),50,200,50,key='set_sma_slow')
        with cb:
            ema=st.slider(tr('ema_period'),5,80,20,key='set_ema')
            macd_fast=st.slider(tr('macd_fast'),5,20,12,key='set_macd_fast')
            macd_slow=st.slider(tr('macd_slow'),21,55,26,key='set_macd_slow')
        with cc:
            signal=st.slider(tr('macd_signal'),3,20,9,key='set_macd_signal')
            bb_period=st.slider(tr('bollinger_period'),5,60,20,key='set_bb_period')
            bb_std=st.slider(tr('bollinger_width'),0.5,4.0,2.0,step=.5,key='set_bb_std')
        st.button(tr('reset_defaults'),key='reset_indicators',on_click=reset_indicator_state)
    return IndicatorSettings(rsi_period=st.session_state.get('set_rsi',14),
          sma_fast=st.session_state.get('set_sma_fast',20),
          sma_slow=st.session_state.get('set_sma_slow',50),
          ema_period=st.session_state.get('set_ema',20),
          macd_fast=st.session_state.get('set_macd_fast',12),
          macd_slow=st.session_state.get('set_macd_slow',26),
          macd_signal=st.session_state.get('set_macd_signal',9),
          bb_period=st.session_state.get('set_bb_period',20),
          bb_std=st.session_state.get('set_bb_std',2.0))


def get_research():
    code=st.session_state.symbol
    p=indicator_controls()
    try:
        with st.spinner(tr('common.loading')):
            try:
                prices,stamp=prices_cached(code,'5y')
            except MarketDataError:
                prices,stamp=prices_cached(code,'2y')
        frame,trend,reasons=analyze(prices,p)
    except (MarketDataError,ValueError,KeyError,TypeError,IndexError) as exc:
        st.error(str(exc))
        st.info(tr('stock.price_not_available'))
        if st.button(tr('common.retry'),key='retry_price'):
            prices_cached.clear();st.rerun()
        return None
    last=frame.index[-1].date()
    age=(datetime.now(timezone.utc).date()-last).days
    if age>14 or age < -1:
        trend='UNAVAILABLE'
        reasons.append('Trading observation is stale or in the future: no current trend classification.')
        st.warning(tr('v2.stale'))
    return code,prices,frame,stamp,p,trend,reasons


def latest_metrics(ctx):
    code,prices,frame,stamp,p,trend,reasons=ctx
    last=frame.iloc[-1]
    st.title(f'{display_name(code,prices)} · {code}' if display_name(code,prices)!=code else code)
    st.caption(f"{prices.attrs.get('exchange') or ''} · {prices.attrs.get('currency') or ''} · "+
               tr('market.data_as_of',date=str(frame.index[-1].date()))+
               ' · '+tr('market.not_live'))
    st.caption(tr('data_period',start=str(frame.index[0].date()),end=str(frame.index[-1].date())))
    discarded=prices.attrs.get('discarded_invalid_close_rows',0)
    if discarded:
        st.warning(tr('v2.invalid_rows',count=discarded))
    cols=st.columns(4)
    delta=finite((float(last.Close)/float(frame.Close.iloc[-2])-1)*100,2) if len(frame)>1 else None
    cols[0].metric(tr('stock.latest_price'),f'{float(last.Close):,.2f}',f'{delta:+.2f}%' if delta is not None else None)
    for c,field,label in [(cols[1],'SMA_fast',f'SMA({p.sma_fast})'),
                          (cols[2],'SMA_slow',f'SMA({p.sma_slow})'),
                          (cols[3],'RSI',f'RSI({p.rsi_period})')]:
        number=finite(last.get(field),2)
        c.metric(label, f'{number:,.2f}' if number is not None else '—')


def chart_panel(ctx):
    code,prices,frame,stamp,p,trend,reasons=ctx
    a,b,c=st.columns([2,1,1])
    with a:
        window=st.select_slider(tr('chart.range'),options=list(WINDOWS),value='6M',key='chart_window')
    with b:
        typ=st.selectbox(tr('type'),['Candlestick','Line'],key='chart_type',
                         format_func=lambda x:tr('candles') if x=='Candlestick' else tr('line'))
    with c:
        lower=st.selectbox(tr('lower_indicator'),['RSI','MACD','Volume','ATR','KDJ'],key='lower')
    overlays=st.multiselect(tr('overlay'),['SMA','EMA','BB'],default=['SMA','EMA'],key='overlays')
    fig=create_price_figure(frame,p,window=window,candle=(typ=='Candlestick'),
                            lower=lower,overlays=tuple(overlays),symbol=code,
                            mode=st.session_state.market_colors,currency=prices.attrs.get('currency',''))
    st.plotly_chart(fig,width='stretch',key='stock_price_chart',config={'displaylogo':False,'scrollZoom':True})
    st.caption(tr('five_year_notice'))
    with st.expander(tr('chart.inspect_data')):
        fields=[k for k in ('Open','High','Low','Close','Volume','SMA_fast','SMA_slow',
                            'EMA','RSI','MACD','MACD_signal','BB_upper','BB_lower','ATR','K','D','J') if k in frame]
        visible_start,visible_end=window_bounds(frame.index,window)
        shown=frame.loc[(frame.index>=visible_start)&(frame.index<=visible_end),fields].sort_index(ascending=False)
        st.dataframe(shown,width='stretch')
        st.download_button(tr('download_csv'),data=shown.to_csv().encode('utf-8-sig'),
                           file_name=f'{code.replace("^","")}-taurus-research.csv',mime='text/csv')


def technical_panel(ctx):
    code,prices,frame,stamp,p,trend,reasons=ctx
    names={'BULLISH':'trend_bullish','BEARISH':'trend_bearish',
           'MIXED':'trend_mixed','UNAVAILABLE':'trend_unavailable'}
    st.markdown('### '+tr('technical_explain'))
    st.markdown('**'+tr(names[trend])+'**')
    for line in reasons:
        st.write('• '+line)
    latest=frame.iloc[-1]
    for field,label in [('MACD','MACD'),('MACD_hist','MACD histogram'),('ATR','ATR'),
                        ('BB_upper','Bollinger upper'),('BB_lower','Bollinger lower'),('K','KDJ K')]:
        number=finite(latest.get(field))
        if number is not None:
            st.caption(f'{label}: {number:,.3f}')
    st.caption(tr('legal.educational'))


def fundamentals_panel(code):
    st.caption(tr('v2.mixed_periods'))
    if not st.button(tr('v2.load_fund'),key='load_fund_'+code):
        if st.session_state.get('fund_loaded')!=code:
            return None
    try:
        with st.spinner(tr('common.loading')):
            result,stamp=fundamentals_cached(code)
    except MarketDataError as exc:
        st.info(str(exc));return None
    st.session_state['fund_loaded']=code
    st.caption(str(result.get('source',''))+' · '+stamp.strftime('%Y-%m-%d %H:%M UTC'))
    if result.get('sector'):
        st.write(str(result['sector'])+' · '+str(result.get('industry','')))
    if result.get('description'):
        with st.expander(tr('stock.about_company')):
            st.write(result['description'])
    m=result.get('metrics',{})
    sets=[(tr('fund.valuation'),['market_cap','trailing_pe','price_to_book']),
          (tr('fund.profitability'),['trailing_eps','profit_margin','return_on_equity']),
          (tr('fund.growth'),['total_revenue','revenue_growth','earnings_growth']),
          (tr('fund.balance_sheet'),['total_cash','total_debt','free_cashflow'])]
    for title,keys in sets:
        st.markdown('**'+title+'**')
        cols=st.columns(3)
        for col,key in zip(cols,keys):
            value=m.get(key)
            if value is None:
                readable='—'
            elif key in ('profit_margin','return_on_equity','revenue_growth','earnings_growth'):
                readable=f'{value*100:+.1f}%'
            elif abs(value)>=1e9:
                readable=f'{value/1e9:,.2f}B'
            else:
                readable=f'{value:,.2f}'
            col.metric(key.replace('_',' ').title(),readable)
    return result


def get_snapshot(ctx):
    code,prices,frame,stamp,p,trend,reasons=ctx
    fund=None
    headlines=[]
    try:
        fund,_=fundamentals_cached(code)
    except (MarketDataError,ValueError,TypeError):
        pass
    try:
        headlines,_=company_news_cached(code,display_name(code,prices),lang())
    except (MarketDataError,ValueError,TypeError):
        pass
    return build_snapshot(code,prices,frame,p,trend,reasons,stamp,fund,headlines)


def ai_panel(ctx,standalone=False):
    code,prices,frame,stamp,p,trend,reasons=ctx
    st.markdown('### '+tr('ai_standalone' if standalone else 'ai.title'))
    st.caption(tr('snapshot'))
    technical_panel(ctx)
    if not api_key():
        st.info(tr('ai_key_note'))
        return
    sig_data={'code':code,'date':str(frame.index[-1]),'close':finite(frame.Close.iloc[-1]),
              'settings':vars(p),'language':lang()}
    signature=hashlib.sha256(json.dumps(sig_data,sort_keys=True).encode()).hexdigest()
    if st.session_state.get('ai_signature')!=signature:
        st.session_state['ai_signature']=signature
        st.session_state['ai_output']=''
        st.session_state['ai_followup']=''
    if st.button(tr('ai.generate'),type='primary',key='generate_ai'):
        now=time.monotonic()
        if now-st.session_state['last_ai_attempt']<35:
            st.warning(tr('ai.cooldown'))
        else:
            st.session_state['last_ai_attempt']=now
            with st.spinner(tr('ai.generating')):
                try:
                    snap=get_snapshot(ctx)
                    st.session_state['ai_snapshot']=snap
                    st.session_state['ai_output']=explain(snap,api_key(),lang())
                    st.session_state['ai_followup']=''
                except AIAnalysisError as exc:
                    st.warning(str(exc))
    report=st.session_state.get('ai_output','')
    if report:
        with st.container(border=True):
            st.markdown(report)
        st.caption(MODEL+' · '+tr('ai_security'))
        question=st.text_area(tr('ai_question'),key='ai_question',height=90,max_chars=800)
        if st.button(tr('ask_ai'),key='ai_followup_btn',disabled=not bool(question.strip())):
            now=time.monotonic()
            if now-st.session_state['last_ai_attempt']<35:
                st.warning(tr('ai.cooldown'))
            else:
                st.session_state['last_ai_attempt']=now
                try:
                    with st.spinner(tr('ai.generating')):
                        snap=st.session_state.get('ai_snapshot') or get_snapshot(ctx)
                        st.session_state['ai_followup']=explain(snap,api_key(),lang(),
                                             question=question,previous_report=report)
                except AIAnalysisError as exc:
                    st.warning(str(exc))
        if st.session_state.get('ai_followup'):
            st.markdown('#### '+tr('ask_ai'))
            st.markdown(st.session_state['ai_followup'])
    else:
        st.info(tr('ai_no_evidence'))
    st.caption(tr('legal.educational'))


def research(standalone=False):
    section(tr('nav.ai') if standalone else tr('nav.research'),tr('stock.research_scope'))
    search_area('ai' if standalone else 'research',destination='ai' if standalone else 'research')
    ctx=get_research()
    if ctx is None:
        return
    latest_metrics(ctx)
    if st.button(tr('refresh'),key='refresh_research'):
        prices_cached.clear();st.rerun()
    if standalone:
        chart_panel(ctx)
        ai_panel(ctx,True)
        return
    options=['overview','chart','fundamentals','news','ai']
    keys={'overview':'stock.overview','chart':'stock.chart','fundamentals':'stock.fundamentals',
          'news':'stock.company_news','ai':'stock.ai_insights'}
    tab=st.segmented_control(tr('v2.research_sections'),options,default='overview',
             format_func=lambda x:tr(keys[x]),key='research_tab',label_visibility='collapsed') or 'overview'
    if tab in ('overview','chart'):
        chart_panel(ctx)
        technical_panel(ctx)
    elif tab=='fundamentals':
        fundamentals_panel(ctx[0])
    elif tab=='news':
        news_panel(kind='company',symbol=ctx[0],name=display_name(ctx[0],ctx[1]),limit=10)
    elif tab=='ai':
        ai_panel(ctx)


def news_page():
    section(tr('news.title'),tr('news.description'))
    choices={'US':tr('market.us'),'CN':tr('market.cn'),'HK':tr('market.hk'),'EU':tr('market.eu')}
    a,b,c=st.columns([1,1,2])
    with a:
        market=st.selectbox(tr('news.filter.market'),list(choices),format_func=lambda x:choices[x])
    with b:
        topic=st.selectbox(tr('news.filter.topic'),list(('general','technology','macro','earnings')))
    with c:
        keyword=st.text_input(tr('news.filter.keyword'))
    days=st.selectbox(tr('news.filter.time'),[0,1,7,30],format_func=lambda n:{0:'All',1:'1d',7:'7d',30:'30d'}[n])
    news_panel(market=market,topic=topic,keyword=keyword,days=days,limit=12)
    st.markdown('### '+tr('news.company'))
    st.caption(st.session_state.symbol)
    news_panel(kind='company',symbol=st.session_state.symbol,keyword=keyword,days=days,limit=6)


# Fixed navigation identifiers do not depend on the translated labels.
brand,nav,options=st.columns([1.45,3.1,1.35],gap='small')
with brand:
    st.markdown('<div class="brand">'+LOGO+
                '<div><b>TAURUS <span>AI</span></b><small>GLOBAL RESEARCH</small></div></div>',
                unsafe_allow_html=True)
with nav:
    pages={'home':'nav.home','markets':'nav.markets','research':'nav.research',
           'news':'nav.news','ai':'nav.ai'}
    st.radio('Navigation',list(pages),format_func=lambda x:tr(pages[x]),
             horizontal=True,label_visibility='collapsed',key='nav')
with options:
    language_names=dict(language_options())
    st.selectbox('Language / 语言',list(language_names),format_func=lambda x:language_names[x],
                 key='language',label_visibility='collapsed')
    color_names={'neutral':'Blue ↑ / Orange ↓','us':'US · Green ↑','cn':'A shares · Red ↑'}
    st.selectbox(tr('settings.market_colors'),list(color_names),
                 format_func=lambda x:color_names[x],key='market_colors',label_visibility='collapsed')
st.markdown('<div class="nav-divider"></div>',unsafe_allow_html=True)

page=st.session_state.nav
if page=='home':
    home()
elif page=='markets':
    markets()
elif page=='research':
    research()
elif page=='ai':
    research(True)
elif page=='news':
    news_page()
else:
    st.session_state['pending_nav']='home'
    st.rerun()
st.markdown('<div class="site-footer"><b>TAURUS AI</b><span>Global equity research · educational use only</span></div>',unsafe_allow_html=True)
st.caption('Prices: Yahoo via yfinance (best effort, delayed; no guaranteed public redistribution license). '
           'News: RSS/Yahoo headlines, not full articles. AI output may be inaccurate; verify source dates.')
