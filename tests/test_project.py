"""Offline unit tests: no live API keys, stock quotes, or fabricated app data."""
import unittest
from unittest.mock import Mock, patch
from datetime import datetime, timezone
import numpy as np
import pandas as pd

from market_data import MarketDataError, normalize_symbol, _validated_prices, fetch_prices, resolve_symbol, get_market_indices
from indicators import wilder_rsi, analyze
from news_data import parse_rss, filter_news, safe_link
from ai_analysis import AIAnalysisError, explain
from i18n import validate_catalog, t


def fixture(n=100):
    x=np.arange(n)
    return pd.DataFrame({'Close':100 + x*.15 + np.sin(x), 'Volume':1000 + x},
                        index=pd.date_range('2026-02-01',periods=n,freq='B'))


class MarketTests(unittest.TestCase):
    def test_codes_and_names(self):
        self.assertEqual(normalize_symbol('600519'), '600519.SS')
        self.assertEqual(normalize_symbol('000858'),'000858.SZ')
        self.assertEqual(normalize_symbol('0700'),'0700.HK')
        self.assertEqual(resolve_symbol('贵州茅台'),'600519.SS')
        self.assertEqual(resolve_symbol('Apple'),'AAPL')
        self.assertGreaterEqual(len(get_market_indices('CN')),3)

    def test_missing_closes_do_not_kill_entire_history(self):
        data=fixture(75)
        data.iloc[5,data.columns.get_loc('Close')]=np.nan
        data.iloc[-1,data.columns.get_loc('Close')]=np.nan
        clean=_validated_prices(data)
        self.assertEqual(len(clean),73)
        self.assertEqual(clean.attrs['discarded_invalid_close_rows'],2)
        self.assertTrue(np.isfinite(clean.Close).all())
        self.assertEqual(analyze(clean)[1] in ('BUY','SELL','HOLD'),True)

    def test_all_invalid_still_rejected(self):
        data=fixture(3);data['Close']=np.nan
        with self.assertRaises(MarketDataError):
            _validated_prices(data)

    def test_fetch_prices_keeps_legacy_tuple_api(self):
        ticker=Mock()
        ticker.history.return_value=fixture(60)
        ticker.get_history_metadata.return_value={'currency':'USD','longName':'Mock Corp'}
        with patch('market_data.yf.Ticker',return_value=ticker):
            prices, at=fetch_prices('AAPL')
        self.assertEqual(prices.attrs['currency'],'USD')
        self.assertEqual(len(prices),60)
        self.assertIsNotNone(at.tzinfo)


class IndicatorTests(unittest.TestCase):
    def test_wilder_reference(self):
        s=pd.Series([44.34,44.09,44.15,43.61,44.33,44.83,45.10,45.42,45.84,46.08,45.89,46.03,45.61,46.28,46.28])
        self.assertAlmostEqual(wilder_rsi(s).iloc[-1],70.4641350211,places=7)

    def test_metrics_and_signals(self):
        frame,signal,reasons=analyze(fixture(100))
        for col in ('SMA20','SMA50','RSI14','MACD','MACD_hist','BB_upper','BB_lower'):
            self.assertIn(col,frame)
        self.assertIn(signal,('BUY','SELL','HOLD'))
        self.assertTrue(reasons)

    def test_short_history(self):
        self.assertEqual(analyze(fixture(25))[1],'UNAVAILABLE')


class NewsTests(unittest.TestCase):
    def test_rss_parsing_and_dedupe(self):
        xml=b'''<rss><channel><item><title>Alpha shares update</title><link>https://news.google.com/a</link><source>Demo Publisher</source><pubDate>Mon, 26 Oct 2026 12:00:00 GMT</pubDate></item><item><title>Alpha shares update</title><link>https://news.google.com/b</link></item></channel></rss>'''
        items=parse_rss(xml)
        self.assertEqual(len(items),1)
        self.assertEqual(items[0]['source'],'Demo Publisher')
        self.assertTrue(items[0]['date'].startswith('2026-10-26'))
        self.assertEqual(len(filter_news(items,keyword='Alpha')),1)

    def test_reject_unsafe_url(self):
        self.assertFalse(safe_link('javascript:alert(1)'))
        self.assertFalse(safe_link('http://test.example'))


class AIAndLocalizationTests(unittest.TestCase):
    def test_lang_catalog(self):
        count, problems=validate_catalog()
        self.assertGreaterEqual(count,250)
        self.assertFalse(problems)
        self.assertNotEqual(t('nav.home','de'),t('nav.home','zh'))

    def test_missing_key_does_not_request(self):
        with patch('ai_analysis.requests.post') as mock_post:
            with self.assertRaises(AIAnalysisError):
                explain({},'')
            mock_post.assert_not_called()

    def test_rate_limit(self):
        with patch('ai_analysis.requests.post',return_value=Mock(status_code=429)):
            with self.assertRaisesRegex(AIAnalysisError,'rate limit'):
                explain({'symbol':'AAPL'},'test-only-value')

    def test_groq_report(self):
        res=Mock(status_code=200)
        res.json.return_value={'choices':[{'finish_reason':'stop','message':{'content':'Mock educational report'}}]}
        with patch('ai_analysis.requests.post',return_value=res) as call:
            output=explain({'symbol':'AAPL'},'test-only-value','zh')
        self.assertIn('educational',output)
        self.assertIn('Simplified Chinese',call.call_args.kwargs['json']['messages'][0]['content'])


if __name__=='__main__':
    unittest.main()
