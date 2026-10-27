"""Synthetic test fixtures only; no fixture is used by the application."""
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
from datetime import datetime, timezone
import numpy as np
import pandas as pd
from indicators import wilder_rsi, analyze
from ai_analysis import explain, AIAnalysisError
from market_data import fetch_prices, MarketDataError


def fixture(n=80):
    close = 100 + np.arange(n) * .1 + np.sin(np.arange(n))
    frame = pd.DataFrame({'Close':close}, index=pd.date_range(end=pd.Timestamp.now(tz='UTC').normalize(), periods=n, freq='D'))
    frame.attrs.update(company='Test fixture', currency='USD', exchange='Test exchange')
    return frame


class IndicatorTests(unittest.TestCase):
    def test_wilder_known_seed(self):
        close = pd.Series([44.34,44.09,44.15,43.61,44.33,44.83,45.10,45.42,45.84,46.08,45.89,46.03,45.61,46.28,46.28])
        self.assertAlmostEqual(wilder_rsi(close).iloc[-1], 70.4641350211, places=7)

    def test_rsi_extremes(self):
        self.assertEqual(wilder_rsi(pd.Series(range(30), dtype=float)).iloc[-1], 100)
        self.assertEqual(wilder_rsi(pd.Series(range(30,0,-1), dtype=float)).iloc[-1], 0)
        self.assertEqual(wilder_rsi(pd.Series([10.] * 30)).iloc[-1], 50)

    def test_insufficient_and_flat(self):
        self.assertEqual(analyze(fixture(49))[1], 'UNAVAILABLE')
        self.assertEqual(analyze(pd.DataFrame({'Close':[10.] * 60}))[1], 'HOLD')

    def test_no_lookahead(self):
        full = analyze(fixture(80))[0]
        prefix = analyze(fixture(80).iloc[:65])[0]
        pd.testing.assert_frame_equal(full.iloc[:65], prefix)

    def test_directional_signals(self):
        rising = pd.DataFrame({'Close':100 + np.cumsum(np.tile([1.,-.6],40))})
        falling = pd.DataFrame({'Close':100 + np.cumsum(np.tile([-1.,.6],40))})
        self.assertEqual(analyze(rising)[1], 'BUY')
        self.assertEqual(analyze(falling)[1], 'SELL')

    def test_invalid_prices(self):
        ticker = Mock()
        ticker.history.return_value = pd.DataFrame({'Close':[10.,np.nan]}, index=pd.date_range('2026-01-01', periods=2))
        with patch('market_data.yf.Ticker', return_value=ticker), self.assertRaises(MarketDataError):
            fetch_prices('AAPL')

    def test_empty_prices(self):
        ticker = Mock()
        ticker.history.return_value = pd.DataFrame()
        with patch('market_data.yf.Ticker', return_value=ticker), self.assertRaises(MarketDataError):
            fetch_prices('AAPL')


class AITests(unittest.TestCase):
    def test_no_key_never_calls_api(self):
        with patch('ai_analysis.requests.post') as post:
            with self.assertRaises(AIAnalysisError):
                explain({}, '')
            post.assert_not_called()

    def test_limit_no_retry(self):
        with patch('ai_analysis.requests.post', return_value=Mock(status_code=429)) as post:
            with self.assertRaisesRegex(AIAnalysisError, 'quota'):
                explain({'rule_signal':'HOLD'}, 'test-only-placeholder')
            self.assertEqual(post.call_count, 1)

    def test_response(self):
        response = Mock(status_code=200)
        response.json.return_value = {'choices':[{'finish_reason':'stop', 'message':{'content':'Test response'}}]}
        with patch('ai_analysis.requests.post', return_value=response):
            self.assertEqual(explain({}, 'test-only-placeholder'), 'Test response')


class UITests(unittest.TestCase):
    def test_search_success_and_failure(self):
        from streamlit.testing.v1 import AppTest
        import streamlit as st
        st.cache_data.clear()
        def prices(symbol):
            if symbol == 'INVALID':
                raise MarketDataError('No data returned.')
            return fixture(), datetime.now(timezone.utc)
        with patch('market_data.fetch_prices', side_effect=prices), patch('market_data.fetch_news', return_value=([], datetime.now(timezone.utc))), patch.dict('os.environ', {'GROQ_API_KEY':''}):
            app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / 'app.py'), default_timeout=15).run()
            self.assertEqual(len(app.exception), 0)
            self.assertEqual(app.radio[0].value, 'Overview')
            next(x for x in app.button if x.label == 'Explore AAPL →').click()
            app.run()
            self.assertEqual(app.radio[0].value, 'Stock research')
            self.assertEqual(len(app.exception), 0)
            self.assertEqual(len(app.metric), 4)
            self.assertTrue(next(x for x in app.button if x.label == 'Generate AI explanation').disabled)
            app.text_input[0].set_value('INVALID')
            next(x for x in app.button if x.label == 'Research this stock →').click()
            app.run()
            self.assertEqual(len(app.exception), 0)
            self.assertEqual(len(app.error), 1)
            self.assertEqual(len(app.metric), 0)

    def test_home_partial_outage_and_news(self):
        from streamlit.testing.v1 import AppTest
        import streamlit as st
        st.cache_data.clear()
        def prices(symbol):
            if symbol == '^IXIC':
                raise MarketDataError('Test outage')
            return fixture(), datetime.now(timezone.utc)
        with patch('market_data.fetch_prices',side_effect=prices), patch('market_data.fetch_news',side_effect=MarketDataError('Test news outage')), patch.dict('os.environ', {'GROQ_API_KEY':''}):
            app=AppTest.from_file(str(Path(__file__).resolve().parents[1]/'app.py'),default_timeout=15).run()
            self.assertEqual(len(app.exception),0)
            self.assertTrue(any('Unavailable' in x.value for x in app.markdown))
            app.radio[0].set_value('News').run()
            self.assertEqual(len(app.exception),0)
            self.assertTrue(any('temporarily unavailable' in x.value for x in app.caption))


if __name__ == '__main__':
    unittest.main()
