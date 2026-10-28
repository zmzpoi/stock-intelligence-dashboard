# Taurus AI 3.0 — delivery test report

Build date: 2026-10-28

## Tested offline

- `python -m compileall -q .` — pass.
- `python i18n.py --check` — pass, 298 keys × three languages.
- `python -m unittest discover -s tests -v` — **24 passing test cases** in this creation environment, including five full-page control-flow smoke simulations.
- Indicator reference fixture: RSI(14) Wilder benchmark matches standard numerical example.
- Configurable indicator calculations: RSI(9) differs from RSI(14); SMA, EMA, MACD, Bollinger, ATR, KDJ produce values on supported synthetic OHLCV input.
- Plotly zoom: full history goes into `x` and candle OHLC, while 3M view only restricts visible date range. Min/max allowed dates remain at actual data boundaries.
- Four market page categories and five navigation pages simulated with mock Streamlit + offline quote adapter.
- Simulated click from Chinese-market company opens research rather than disappearing.
- AI research remains on its own page and mock Groq report generates from data snapshot, without real network access.
- Sample security names are provided without making extra remote calls for known exact A/H tickers.
- Invalid quote rows are removed, not invented or silently filled.

## NOT tested here; must be tested on Mac/Cloud

- Actual Streamlit UI renderer, Safari/Chrome interactive mouse/scroll zoom, mobile rendering.
- Real Yahoo Finance and Google News request success, delayed quotes, upstream throttling and display/reuse license.
- Live Groq account, model permissions, rate limits and current response quality.
- Your local virtualenv, GitHub credentials and repository branch/merge state.
- Streamlit Cloud deployment, remote secrets and full production logs.

**Reason:** The creation environment does not include Streamlit or yfinance, and external package installation/live-network access are unavailable. Page navigation tests use a mocked Streamlit surface, which is not the same as a browser integration test. This report makes no claims of actual Cloud production verification.

## Feature boundary

This release fixes the described core functional problems and improves research. It does not include a licensed whole-exchange market screener, verified market-wide rankings, live intraday trading data, user accounts/watchlist persistence, order execution, robust multi-user AI expenditure limits, PDF reporting, or formal backtesting. Those require separate scopes and often licensed providers.
