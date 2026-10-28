# Taurus AI 2.0 — Global Stock Research Assistant

A free-hostable Streamlit educational prototype for global equity research. Redesigned
navy/ivory layout, central company/ticker search, US/China/Hong Kong/Europe market
indexes, stock charts, fundamentals, multilingual UI (English/简体中文/Deutsch),
headline research and optional Groq reports. **Not a trading platform.**

## Safe upgrade of an existing project (Mac)

**Always save a backup first** (prefer a clean `taurus-v2` Git branch). This
ZIP intentionally excludes any secrets and virtual environments. Extraction
into the project root adds or overwrites code and UI files, but does not erase
`.streamlit/secrets.toml`. Keep your real Groq key only in Cloud Secrets or
local `.streamlit/secrets.toml`. Never commit it.

```bash
cd /Users/zoumengzhao/PycharmProjects/stock-intelligence-dashboard
# On a clean project, use: git switch -c taurus-v2
unzip -o ~/Downloads/taurus-ai-v2-complete.zip -d .
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python i18n.py --check
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python -m streamlit run app.py --server.address 127.0.0.1
```

Open http://localhost:8501. Leave that Terminal running. Ctrl+C to stop.
If `.venv/bin/python` does not exist, use `venv/bin/python`, or configure a
Python 3.10–3.12 virtualenv. If using a newly created env, install dependencies.

## Test checklist

1. Home: six index cards (failures explicitly labelled), search AAPL → research.
2. Search `600519` or `贵州茅台`; note that A-share availability depends on Yahoo.
3. Change language from English to 简体中文 and Deutsch.
4. Research: latest price, chart 1M/3M/6M/1Y, SMA/RSI and stable bar dates.
5. Select Financials and click "Load"; absent data is labelled.
6. News: RSS headlines open original links; if unavailable, UI shows a notice.
7. Optional AI: verify Groq key is in Secrets; click Generate only once. A 429
   is a free-tier quota/rate warning, not a silent paid retry.
8. Switch to mobile-width window and check navigation and chart layout.

## Important data caveats

- Yahoo-backed yfinance quotes are **not a guaranteed real-time feed**. The latest
  history bar may be provisional; the UI labels observation date and retrieval
  time separately. Invalid closing-price rows are discarded, never interpolated.
- Yahoo news `get_news()` may return empty data; Google News RSS headline-only
  retrieval is a best-effort alternative. RSS service availability and its
  terms may change. No publisher article body is copied.
- Public redistribution / display rights for Yahoo market data and news require
  verification; a free library or free hosting plan does not itself grant them.
- AI text can be wrong. The rule-based BUY/HOLD/SELL *technical labels* are
  unbacktested classifications, not personalized financial advice.
- The home featured stocks are a **curated sample**, NOT a true live popularity
  ranking. No invented market data is displayed when a provider is unavailable.
- The app does not execute trades or store user portfolios. AI limits are per
  Streamlit session, not a secure account-wide quota limit. Do not expose a
  public AI endpoint without provider cost/abuse safeguards.

## Files

- `app.py`: Streamlit navigation, global search, markets, research, news and AI UI.
- `market_data.py`: validated OHLCV, multi-market symbols, fundamentals and
  optional Yahoo headlines; ignores occasional invalid historical rows.
- `news_data.py`: independent RSS retrieval with Yahoo fallback, simple filters.
- `indicators.py`: RSI, SMA, MACD, Bollinger and fixed technical signal rules.
- `ai_analysis.py`: bounded Groq report generation (only when clicked).
- `presentation.py`: safe UI cards, brand mark, sparkline and news headlines.
- `i18n.py`: 275 translation keys, three languages.
- `assets/style.css`: neutral midnight-blue and ivory theme, responsive UI.
- `assets/taurus-mark.svg`: **unchanged user-owned logo** (replace later).
- `tests/test_project.py`: self-contained offline tests using mocks/synthetic
  data for testing only; the app itself displays real provider data or errors.

## Deployment

After local verification, commit changes on `taurus-v2`, then merge into main
only when ready. Push main to GitHub to trigger the existing Streamlit Cloud app
redeploy. Add `GROQ_API_KEY = "..."` to Streamlit Cloud Secrets (not the GitHub
repository). Do not upload `.env`, `secrets.toml` or `venv/`.

This repository does not include a market-data redistribution license. Public
hosting of price/financial information should be evaluated against provider
terms before inviting wide public usage.
