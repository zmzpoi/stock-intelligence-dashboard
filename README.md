# Taurus AI

A branded local equity research workspace with interactive price charts, reproducible technical signals and an optional real LLM explanation. Built with Python, Streamlit, Pandas and Plotly. No trades are executed.

**Status:** local development preview. No public deployment has been completed. Yahoo data public-display permission has NOT been established. The user has verified a real Groq response locally. Each new installation still needs its own Free tier API key; keys are never included. No API key is included.

## Run locally

From the project directory with a Python 3.10+ virtual environment:

```bash
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m streamlit run app.py --server.address 127.0.0.1
```

Open http://localhost:8501. The Overview landing page contains S&P 500, Nasdaq Composite and DAX cards, a curated stock grid, a right-side research search and provider news links. Stock research and News are separate navigation views. Search AAPL, MSFT, NVDA or SAP.DE, or another Yahoo-format ticker. Company and currency metadata are displayed only when provided. Failures never substitute fake data.

## Structure

| Module | Responsibility |
|---|---|
| app.py | Overview / research / news views, bounded data loading and session state |
| presentation.py | Escaped data-driven market cards, sparklines and news links |
| assets/ | Taurus bull SVG and responsive light/forest-green styling |
| market_data.py | Yahoo history/metadata/news adapter, validation, readable errors |
| indicators.py | SMA20, SMA50, exact Wilder RSI14 and deterministic rules |
| ai_analysis.py | Optional bounded Groq request, no retry or paid fallback |
| tests/test_project.py | Indicator reference values, error handling and UI tests |

Architecture: input → provider adapter → validated prices → indicator calculation → rules → optional LLM explanation → Streamlit view. This fixed pipeline is ordinary automation with an LLM step, not an autonomous agent. It leaves clear seams for later agent research.

## Rules

BUY: Close > SMA20 > SMA50 and 50 ≤ RSI14 < 70.

SELL: Close < SMA20 < SMA50 and 30 < RSI14 < 50.

Otherwise HOLD. Fewer than 50 records produces UNAVAILABLE, not HOLD. The UI withholds a signal if the latest trading date is in the future or more than seven calendar days old; this is a simple freshness guard, not an exchange-calendar model.

SMA uses trading observations. RSI uses the initial arithmetic average of 14 gains/losses followed by Wilder smoothing. A completely flat series receives RSI=50. Values are based on Yahoo Close with auto_adjust=False; there is no dividend adjustment. Chart 1M/3M windows use 22/66 observations; full history remains the basis for calculations. The latest bar may be incomplete; the midnight index is a trading-date label, not the quote timestamp. Retrieval times are separate UTC timestamps. Price caches expire after 10 minutes and news caches after 5 minutes.

No predictive validity, backtested performance, optimal entry price, profitability or personal suitability is claimed. Corporate actions and provider revisions can affect results.

## Optional AI: Free tier only

Groq documents a Free tier and per-model request/token limits. Keep the account on **Free**; do not add a payment method or upgrade. This code cannot inspect your billing tier, and it cannot guarantee that an account already on a paid tier incurs no charges. Limits and model availability may change.

When ready, create `.streamlit/secrets.toml` locally:

```toml
GROQ_API_KEY = "YOUR_OWN_KEY"
```

Alternatively set GROQ_API_KEY in the process environment. Never paste the key into app.py, this README, chat, GitHub or a screenshot. `.gitignore` excludes the secrets file. In Community Cloud use its Secrets settings, after resolving public data rights.

The current integration uses Groq's `openai/gpt-oss-20b` through `/openai/v1/chat/completions`. It sends only the selected ticker, price/indicator snapshot, rule result and timestamps when the user clicks Generate. It does not send news or fetch articles for the model. It makes one call, limits output tokens, applies a 30-second per-session cooldown and displays errors for quota exhaustion. The cooldown is not a global abuse-prevention system. No key means no model request and a disabled button. The model explains the rule output; it is not a separate verified forecast. Generated text can still be wrong.

## Data rights and deployment boundary

yfinance is an independent open-source wrapper, not an authorized Yahoo public redistribution license. Its documentation states research/educational intent and warns that Yahoo Finance API data is for personal use. A code license or a financial disclaimer does not supply data rights. News retrieval here returns provider-supplied titles, dates and links; it does not copy article bodies. News relevance, availability and display rights still require review.

Do not publish this Yahoo-backed version as a public market-data service on the assumption that free access permits redistribution. Before deployment, establish a suitable provider permission or deliberately agree on a narrower public demonstration with appropriately licensed data. The deployment objective remains pending, not silently abandoned. Free hosting and free LLM access are separate from market-data licensing.

Sources checked 2026-10-27:
- https://ranaroussi.github.io/yfinance/
- https://console.groq.com/docs/billing-faqs
- https://console.groq.com/docs/rate-limits
- https://console.groq.com/docs/api-reference

## Validation

```bash
.venv/bin/python -m unittest discover -s tests -v
```

Tests use explicitly synthetic fixtures in tests only; the app never uses them. Live Yahoo access was confirmed on the user's Mac before this package; company metadata and a real Groq call have also been confirmed by the user. The new homepage index/news paths still require local validation. After local checks, lock the installed dependency versions before deployment. requirements.txt currently uses compatibility ranges, not a reproducible lock.

Next checks: AAPL/SAP.DE; invalid ticker; provider outage; news failure; missing key; live free-tier AI request; mobile layout; dependency lock; rights-aware deployment; external private-browser verification.

## Version 0.2 — Taurus homepage

Added an original geometric bull mark, a light/forest-green brand system, Overview / Stock research / News navigation, a three-index market overview, four curated stock cards with real-data sparklines, right-side search and linked publisher headlines. Indices and stocks are loaded with at most three concurrent requests and a ten-minute cache. A failed card does not block successful cards. News failures are isolated from analysis. No invented market figures or news are used. The language-model prompt now separates price/RSI invalidation conditions and distinguishes retrieval time from market time; model mistakes remain possible.

12 automated checks passed in the development environment, including the homepage navigation, partial data outage and invalid-ticker UI. Browser visual verification still requires the local screenshot review; no browser screenshot was produced in the development environment.

Update archives never contain `.streamlit/secrets.toml` or virtual environments. Extracting the archive into the existing project preserves the separately-created local secrets file.
