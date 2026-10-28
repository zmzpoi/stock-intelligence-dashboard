"""Full app page smoke tests using a synthetic Streamlit interface, offline only.

Not a browser test: catches Python control-flow/widget-routing failures without
requiring a real Streamlit server, Groq account or market network connection.
"""
from __future__ import annotations
import runpy
import sys
import types
import unittest
from unittest.mock import Mock, patch
from pathlib import Path
from contextlib import nullcontext
import numpy as np
import pandas as pd

try:
    import yfinance
except ImportError:
    fake_yf=types.ModuleType('yfinance')
    fake_yf.Ticker=Mock()
    fake_yf.Search=Mock()
    sys.modules['yfinance']=fake_yf

import market_data
import news_data


class RerunSignal(Exception):
    pass


class State(dict):
    def __getattr__(self,key):
        if key not in self:
            raise AttributeError(key)
        return self[key]
    def __setattr__(self,key,value):
        self[key]=value


class FakeStreamlit(types.ModuleType):
    def __init__(self):
        super().__init__('streamlit')
        self.session_state=State()
        self.secrets={}
        self.clicked=set()
        self.charts=[]
        self.markdowns=[]
        self.metrics=[]
        self.changes={}
    def __enter__(self):
        return self
    def __exit__(self,exc_type,exc,tb):
        return False
    def cache_data(self,**kwargs):
        def decorate(func):
            func.clear=lambda:None
            return func
        return decorate
    def __getattr__(self,key):
        if key in ('form','spinner','container','expander'):
            return lambda *a,**kw: nullcontext(self)
        if key=='columns':
            return lambda n,**kw:[self for _ in range(n if isinstance(n,int) else len(n))]
        if key in ('set_page_config','caption','info','warning','error','title','write',
                   'metric','dataframe','download_button'):
            return lambda *a,**kw: None
        if key=='markdown':
            return lambda data,*a,**kw:self.markdowns.append(str(data))
        if key=='plotly_chart':
            return lambda fig,**kw:self.charts.append(fig)
        if key=='button' or key=='form_submit_button':
            return lambda *a,**kw:self._clicked(kw.get('key'))
        if key=='slider':
            return self._slider
        if key=='select_slider':
            return self._select_slider
        if key in ('radio','selectbox','segmented_control'):
            return self._select
        if key=='multiselect':
            return lambda *a,**kw:kw.get('default',[])
        if key=='text_input' or key=='text_area':
            return lambda *a,**kw:''
        raise AttributeError(key)
    def _clicked(self,key):
        if key in self.clicked:
            self.clicked.remove(key)
            return True
        return False
    def _slider(self,label,start,end,value=None,**kw):
        key=kw.get('key')
        if key and key in self.session_state:
            return self.session_state[key]
        if key:
            self.session_state[key]=value
        return value
    def _select_slider(self,label,options,value=None,**kw):
        return self.session_state.get(kw.get('key'),value if value is not None else options[0])
    def _select(self,label,options,**kw):
        key=kw.get('key')
        current=self.session_state.get(key,kw.get('default',options[0]))
        if key:
            self.session_state[key]=current
        return current
    def rerun(self):
        raise RerunSignal()


def sample_prices(code,period='5y'):
    dates=pd.bdate_range('2023-01-02','2026-10-27')
    values=100+np.arange(len(dates))*.1+np.sin(np.arange(len(dates))/12)
    data=pd.DataFrame({'Open':values-.2,'High':values+2,'Low':values-2,
                      'Close':values,'Volume':np.arange(len(dates))*10+5000},index=dates)
    data.attrs={'company':market_data.LOCAL_COMPANY_NAMES.get(code,'Sample Corp'),
                'currency':'CNY','market':'CN','source':'offline fixture','adjusted':False}
    return data,pd.Timestamp('2026-10-28T10:00:00Z').to_pydatetime()


class AppSmokeTests(unittest.TestCase):
    def setUp(self):
        self.st=FakeStreamlit()
        self.st.session_state.update({'nav':'home','language':'zh','symbol':'600519.SS','market_colors':'neutral'})
        self.root=Path(__file__).resolve().parents[1]
        self.patches=[patch.dict(sys.modules,{'streamlit':self.st}),
                      patch('market_data.fetch_prices',side_effect=sample_prices),
                      patch('news_data.fetch_market_news',return_value=([],pd.Timestamp('2026-10-28T10:00:00Z').to_pydatetime())),
                      patch('news_data.fetch_company_news',return_value=([],pd.Timestamp('2026-10-28T10:00:00Z').to_pydatetime())),
                      patch('market_data.fetch_fundamentals',return_value=({'company':'Mock',
                              'metrics':{'trailing_pe':20}},pd.Timestamp('2026-10-28T10:00:00Z').to_pydatetime()))]
        for p in self.patches:p.start()
        # presentation imports streamlit at module import, force fresh binding.
        sys.modules.pop('presentation',None)
    def tearDown(self):
        for p in reversed(self.patches):p.stop()
        sys.modules.pop('presentation',None)

    def run_app(self):
        runpy.run_path(str(self.root/'app.py'),run_name='__main__')

    def test_all_five_pages_render_offline(self):
        for page in ('home','markets','research','news','ai'):
            with self.subTest(page=page):
                self.st.session_state['nav']=page
                self.run_app()
                self.assertTrue(self.st.markdowns)
        self.assertGreaterEqual(len(self.st.charts),2)

    def test_all_market_tabs_render(self):
        self.st.session_state['nav']='markets'
        for market in ('US','CN','HK','EU'):
            self.st.session_state['market_tab']=market
            with self.subTest(market=market):
                self.run_app()
        self.assertTrue(self.st.markdowns)

    def test_market_stock_click_routes_to_research(self):
        self.st.session_state['nav']='markets'
        self.st.session_state['market_tab']='CN'
        self.st.clicked.add('market_600519.SS')
        with self.assertRaises(RerunSignal):self.run_app()
        self.assertEqual(self.st.session_state['pending_nav'],'research')
        self.assertEqual(self.st.session_state['symbol'],'600519.SS')

    def test_ai_research_is_independent_and_does_not_redirect(self):
        self.st.session_state['nav']='ai'
        self.run_app()
        self.assertEqual(self.st.session_state['nav'],'ai')
        self.assertTrue(self.st.charts)
        self.assertNotIn('pending_nav',self.st.session_state)

    def test_market_stays_visible_when_quotes_fail(self):
        self.st.session_state['nav']='markets'
        self.st.session_state['market_tab']='HK'
        with patch('market_data.fetch_prices',side_effect=market_data.MarketDataError('offline')):
            self.run_app()
        self.assertTrue(any('腾讯控股' in x for x in self.st.markdowns))

    def test_ai_generated_report_with_mock_key(self):
        self.st.session_state['nav']='ai'
        self.st.secrets={'GROQ_API_KEY':'offline-mock-key'}
        self.st.clicked.add('generate_ai')
        resp=Mock(status_code=200)
        resp.json.return_value={'choices':[{'finish_reason':'stop',
                    'message':{'content':'Mock research evidence and limitations.'}}]}
        with patch('ai_analysis.requests.post',return_value=resp) as post:
            self.run_app()
        self.assertEqual(self.st.session_state['nav'],'ai')
        self.assertIn('Mock research evidence',self.st.session_state['ai_output'])
        self.assertEqual(post.call_count,1)
        self.assertEqual(self.st.session_state['ai_snapshot']['symbol'],'600519.SS')

    def test_research_section_tabs_render(self):
        self.st.session_state['nav']='research'
        for tab in ('overview','chart','fundamentals','news','ai'):
            self.st.session_state['research_tab']=tab
            with self.subTest(tab=tab):
                self.run_app()

if __name__=='__main__':unittest.main()
