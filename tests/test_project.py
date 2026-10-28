"""Offline deterministic regression tests: absolutely no real API traffic."""
import sys
import types
import unittest
from unittest.mock import Mock, patch
from datetime import datetime, timezone
import numpy as np
import pandas as pd

# Running offline in a test runner without optional Yahoo dependency is supported.
try:
    import yfinance  # noqa: F401
except ImportError:
    stub=types.ModuleType('yfinance')
    stub.Ticker=Mock()
    stub.Search=Mock()
    sys.modules['yfinance']=stub

from market_data import (MarketDataError, normalize_symbol, _validated_prices, fetch_prices,
                         resolve_symbol, search_stocks, get_market_indices, LOCAL_COMPANY_NAMES)
from indicators import IndicatorSettings, wilder_rsi, analyze, calculate_indicators
from charting import create_price_figure, window_bounds
from research_snapshot import build_snapshot
from news_data import parse_rss, filter_news, safe_link
from ai_analysis import AIAnalysisError, explain
from i18n import validate_catalog, t
from ui_labels import ui


def fixture(n=700):
    x=np.arange(n)
    close=100 + x*.07 + 3*np.sin(x/12)
    return pd.DataFrame({'Open':close-.2,'High':close+1.5,'Low':close-1.5,
                         'Close':close,'Volume':10000+x*30},
                         index=pd.date_range('2023-01-02',periods=n,freq='B'))


class MarketTests(unittest.TestCase):
    def test_normalize_market_codes(self):
        self.assertEqual(normalize_symbol('600519'),'600519.SS')
        self.assertEqual(normalize_symbol('300750'),'300750.SZ')
        self.assertEqual(normalize_symbol('0700'),'0700.HK')
        self.assertEqual(resolve_symbol('贵州茅台'),'600519.SS')
        self.assertIn('腾讯',LOCAL_COMPANY_NAMES['0700.HK'])
        self.assertGreaterEqual(len(get_market_indices('CN')),3)

    def test_code_search_with_local_name(self):
        self.assertEqual(search_stocks('600519')[0]['name'],'贵州茅台')
        self.assertEqual(search_stocks('0700')[0]['name'],'腾讯控股')
        self.assertEqual(search_stocks('9988')[0]['name'],'阿里巴巴')
        self.assertEqual(search_stocks('600519')[0]['symbol'],'600519.SS')

    def test_fallback_known_hk_and_ashare(self):
        ticker=Mock()
        ticker.history.return_value=fixture(120)
        ticker.get_history_metadata.return_value={'currency':'CNY'}
        ticker.get_info.return_value={}
        with patch('market_data.yf.Ticker',return_value=ticker):
            cn,_=fetch_prices('600519')
            hk,_=fetch_prices('0700')
        self.assertEqual(cn.attrs['company'],'贵州茅台')
        self.assertEqual(hk.attrs['company'],'腾讯控股')
        ticker.get_info.assert_not_called()  # no extra network call for local names

    def test_invalid_closes_are_excluded_not_filled(self):
        data=fixture(75)
        data.iloc[5,data.columns.get_loc('Close')]=np.nan
        data.iloc[-1,data.columns.get_loc('Close')]=np.nan
        clean=_validated_prices(data)
        self.assertEqual(len(clean),73)
        self.assertEqual(clean.attrs['discarded_invalid_close_rows'],2)
        self.assertTrue(np.isfinite(clean.Close).all())

    def test_all_invalid_data_rejected(self):
        data=fixture(3)
        data['Close']=np.nan
        with self.assertRaises(MarketDataError):_validated_prices(data)


class IndicatorTests(unittest.TestCase):
    def test_wilder_reference_example(self):
        v=pd.Series([44.34,44.09,44.15,43.61,44.33,44.83,45.10,45.42,45.84,46.08,
                     45.89,46.03,45.61,46.28,46.28])
        self.assertAlmostEqual(wilder_rsi(v).iloc[-1],70.4641350211,places=6)

    def test_period_settings_change_values(self):
        a=calculate_indicators(fixture(500),IndicatorSettings(rsi_period=14))
        b=calculate_indicators(fixture(500),IndicatorSettings(rsi_period=9))
        self.assertNotAlmostEqual(a.RSI.iloc[-1],b.RSI.iloc[-1],places=4)
        self.assertFalse(a[['MACD','RSI','ATR','K','D','J','BB_upper']].tail(1).isna().any().any())

    def test_bad_parameters(self):
        for kw in [{'rsi_period':1},{'sma_fast':50,'sma_slow':50},
                   {'macd_fast':30,'macd_slow':26},{'bb_std':0.1}]:
            with self.assertRaises(ValueError):IndicatorSettings(**kw)

    def test_short_history_no_signal(self):
        frame,status,reasons=analyze(fixture(25))
        self.assertEqual(status,'UNAVAILABLE')
        self.assertTrue(reasons)


class ChartTests(unittest.TestCase):
    def setUp(self):
        self.p=IndicatorSettings()
        self.frame=calculate_indicators(fixture(700),self.p)

    def test_zoom_source_contains_full_history(self):
        fig=create_price_figure(self.frame,self.p,window='3M',symbol='600519.SS')
        self.assertEqual(len(fig.data[0].x),len(self.frame))
        self.assertEqual(len(fig.data[0].close),len(self.frame))
        self.assertLess((pd.Timestamp(fig.layout.xaxis.range[1])-
                         pd.Timestamp(fig.layout.xaxis.range[0])).days,100)
        self.assertEqual(pd.Timestamp(fig.layout.xaxis.minallowed),self.frame.index[0])
        self.assertEqual(pd.Timestamp(fig.layout.xaxis.maxallowed),self.frame.index[-1])
        self.assertTrue(fig.layout.xaxis2.rangeslider.visible)

    def test_all_windows_cover_observed_history_only(self):
        for window in ('1M','3M','6M','1Y','2Y','5Y','ALL'):
            first,last=window_bounds(self.frame.index,window)
            self.assertGreaterEqual(first,self.frame.index[0])
            self.assertLessEqual(last,self.frame.index[-1])
            self.assertLessEqual(first,last)

    def test_line_and_lower_indicators(self):
        for lower in ('RSI','MACD','Volume','ATR','KDJ'):
            fig=create_price_figure(self.frame,self.p,candle=False,lower=lower,overlays=('BB',))
            self.assertEqual(len(fig.data[0].x),700)
            self.assertGreaterEqual(len(fig.data),3)


class SnapshotTests(unittest.TestCase):
    def test_snapshot_references_current_indicator_period(self):
        p=IndicatorSettings(rsi_period=9,ema_period=30)
        df=fixture(500)
        df.attrs={'company':'Test corp','currency':'USD'}
        frame,status,reasons=analyze(df,p)
        obj=build_snapshot('DEMO',df,frame,p,status,reasons,datetime.now(timezone.utc))
        self.assertEqual(obj['settings']['rsi_period'],9)
        self.assertEqual(obj['settings']['ema_period'],30)
        self.assertAlmostEqual(obj['metrics']['RSI'],round(float(frame.RSI.iloc[-1]),4),places=3)
        self.assertEqual(obj['fundamentals']['status'],'unavailable')
        self.assertIn('history_start',obj)


class NewsTests(unittest.TestCase):
    def test_parse_rss(self):
        xml=b'<rss><channel><item><title>Alpha shares</title><link>https://news.google.com/a</link><source>News</source><pubDate>Mon, 26 Oct 2026 12:00:00 GMT</pubDate></item></channel></rss>'
        items=parse_rss(xml)
        self.assertEqual(items[0]['source'],'News')
        self.assertEqual(len(filter_news(items,keyword='Alpha')),1)
        self.assertFalse(safe_link('javascript:alert(1)'))


class AIAndTranslationTests(unittest.TestCase):
    def test_i18n_catalog(self):
        count, problems=validate_catalog()
        self.assertGreater(count,250)
        self.assertFalse(problems)
        self.assertNotEqual(t('nav.markets','zh'),t('nav.markets','de'))
        self.assertNotEqual(ui('rsi_period','zh'),ui('rsi_period','de'))

    def test_key_required_no_network(self):
        with patch('ai_analysis.requests.post') as post:
            with self.assertRaises(AIAnalysisError):explain({},'')
            post.assert_not_called()

    def test_rate_limit_and_safe_prompt(self):
        with patch('ai_analysis.requests.post',return_value=Mock(status_code=429)):
            with self.assertRaisesRegex(AIAnalysisError,'rate limit'):
                explain({'symbol':'AAPL'},'test-only')
        resp=Mock(status_code=200)
        resp.json.return_value={'choices':[{'finish_reason':'stop','message':{'content':'Data-backed report'}}]}
        with patch('ai_analysis.requests.post',return_value=resp) as post:
            ans=explain({'symbol':'AAPL','metrics':{'RSI':56}},'test-only','zh',question='Why RSI?')
        self.assertEqual(ans,'Data-backed report')
        call=post.call_args.kwargs['json']['messages']
        self.assertIn('Simplified Chinese',call[0]['content'])
        self.assertIn('Why RSI?',call[1]['content'])
        self.assertNotIn('test-only',str(call))


if __name__=='__main__':unittest.main()
