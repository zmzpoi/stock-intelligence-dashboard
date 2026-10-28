# Taurus AI 3.0 — Global Stock Research Assistant

Taurus AI is a **Streamlit-based, multilingual educational equity-research website**, not a trading terminal. The source in this folder is a **complete replacement project**, not a one-file patch. It preserves the original `assets/taurus-mark.svg` user logo.

## New in this build

- Five separate navigable pages: Home, Markets, Stock Research, News, AI Research.
- All market index cards and curated security cards have visible research buttons. Market tabs and curated lists stay available even when price providers fail.
- Static, exact-ticker identity labels for a small, audited set of commonly visited A/H/US/European listings. Other ticker names are fetched on a best-effort basis; unknown names remain tickers instead of fabricated names.
- A 5-year-first daily history fetch, 2-year fallback, and date-domain Plotly charts. Changing 1M / 3M / 6M / 1Y / 2Y / 5Y / All adjusts the viewport on the **loaded entire dataset**. Drag-to-zoom, wheel zoom and range slider use that dataset and are constrained to available history; zoom does **not** automatically request prices outside the loaded date range.
- User-configurable RSI, SMA, EMA, MACD and Bollinger periods; ATR, KDJ and volume subplots. Price overlay options and CSV export.
- Evidence snapshot with market observation dates, selected indicator settings, derived technical measurements, optional fundamentals and source-linked headline metadata; independent AI Research page with an on-demand Groq report and follow-up prompt.
- Validated `i18n.py` with **298 translation keys in each of Chinese, German and English**; V2 keys restored after a resend patch that omitted them.
- Offline unit and synthetic-app smoke tests. No test needs a real Groq key or live Yahoo quote.

## Requirements

Python 3.10+; supported dependencies listed in `requirements.txt`. Primary entry point for Streamlit Cloud is **`app.py`** (same as your previous deployment).

## Install locally

1. **Back up or commit your current version.** Do not use `git push --force` to resolve GitHub conflicts.
2. Download `taurus-ai-v3-complete.zip` and extract into the **root** of your existing repository; the ZIP uses paths like `app.py` and `assets/style.css` (no enclosing directory).
3. In a Mac terminal:

```bash
cd /Users/zoumengzhao/PycharmProjects/stock-intelligence-dashboard
unzip -o ~/Downloads/taurus-ai-v3-complete.zip -d .
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python i18n.py --check
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python -m streamlit run app.py --server.address 127.0.0.1
```

If your virtual environment is `venv/` rather than `.venv/`, replace `.venv/bin/python` with `venv/bin/python`. Browser: http://localhost:8501, quit server with `Control+C`.

## Manual acceptance tests (the cloud data providers are not mocked here)

- Markets → US/CN/HK/EU renders an index list and curated tickers; clicking **Research this security** opens the correct stock. If Yahoo cannot provide quotes, navigation still works.
- CN contains `600519.SS` 贵州茅台 and `300750.SZ` 宁德时代; HK contains `0700.HK` 腾讯控股 and `9988.HK` 阿里巴巴. Other names may depend on metadata providers.
- Research `AAPL`, `600519` and `0700`; check ticker, company, currency, last observation date, and candle/line.
- Switch chart window among 1M → 3M → 6M → 1Y → 5Y, zoom and pan. Dates cannot stretch beyond the loaded history. If provider gives fewer than five years, only that available range is shown.
- Change RSI(14) → RSI(9), MACD signal, SMA, EMA, Bollinger; chart and evidence change. Try RSI/MACD/Volume/ATR/KDJ subpanels.
- Standalone AI Research: input/search stock, generate report (if Groq key is configured), and ask a follow-up. Verify it remains on AI Research, not redirected to Stock Research.
- Toggle 简体中文 / Deutsch / English; inspect narrow browser/mobile layout and refresh button.
- Check News and Financials; third-party failures should be understandable instead of breaking other pages.

## Important security and production limitations

- **Never add `.streamlit/secrets.toml`, `.env`, API keys, private files or your Python environment to GitHub.** These are excluded by `.gitignore`; verify with `git ls-files -- .streamlit/secrets.toml .env` (must print nothing).
- Locally use `.streamlit/secrets.toml` with `GROQ_API_KEY = "your-actual-key"`. In Streamlit Cloud, open app **Settings → Secrets**, paste the same TOML entry there, Save and reboot if necessary. The ZIP **does not** contain Secrets; extraction does not overwrite your local file.
- Historical Yahoo prices may be delayed, contain data gaps, or be absent; the chart does not pretend to be real-time. The quote API gives raw, non-adjusted daily Close. Verify any public redistribution/display rights directly with the data provider.
- The curated securities are a fixed list, **not a top gainers / volume ranking** or comprehensive exchange universe. Company metadata is a best-effort lookup, not a licensed complete master security database.
- News are headlines and publisher links, not article bodies. Google News / Yahoo may fail and RSS access terms may vary.
- AI is generated on demand, can hallucinate, is not a guarantee of forecasting performance or investment advice. The per-session cooldown is NOT an account-level security quota; restrict public production model spending separately with Groq's dashboard/settings.
- **The delivered offline tests do not establish live deploy success.** The creation environment lacks the Streamlit and yfinance packages and cannot access your private Cloud Secrets or run your live website browser. You must run the above local tests and manual acceptance pass before merging into your deployed `main` branch.

## GitHub deployment (recommended: branch + Pull Request)

After **all local tests** are good:

```bash
git status --short
git ls-files -- .streamlit/secrets.toml .env
git add .gitignore .streamlit/config.toml README.md UPDATE_GUIDE_ZH.md RELEASE_TEST_REPORT.md \
  ai_analysis.py app.py assets/style.css assets/taurus-mark.svg charting.py \
  i18n.py indicators.py main.py market_data.py news_data.py presentation.py \
  research_snapshot.py ui_labels.py requirements.txt tests/test_project.py tests/test_app_smoke.py
git --no-pager diff --cached --name-only
git commit -m "Taurus AI 3.0 tested research upgrade"
git push -u origin taurus-v3
```

This assumes you first created a clean local `taurus-v3` branch with `git switch -c taurus-v3` **before extracting**. If the branch already exists, do not create it again. Open the GitHub repository and create a Pull Request from `taurus-v3` into `main`; merge only when conflicts and checks are resolved. Streamlit Cloud automatically redeploys only if the app actually watches `main`. The prior GitHub non-fast-forward problem is **not** solved by `--force`; a Pull Request handles remote commits safely.

See [UPDATE_GUIDE_ZH.md](UPDATE_GUIDE_ZH.md) for Chinese step-by-step commands.

## Modules

| File | Role |
|---|---|
| `app.py` | All Streamlit pages, navigation, UI and caching |
| `charting.py` | Pure Plotly figure, date windows, 5y loaded zoom |
| `market_data.py` | Best-effort Yahoo price/fundamental adapters, ticker normalization |
| `indicators.py` | Configurable indicator math and descriptive alignment |
| `research_snapshot.py` | Structured, verified-input context for AI |
| `ai_analysis.py` | Groq API call, bounded evidence-first prompt and follow-up |
| `news_data.py` | News RSS/Yahoo headline search/filter |
| `i18n.py` & `ui_labels.py` | English/Chinese/German string localization |
| `presentation.py` | Market tiles, news cards, logo helper |
| `tests/` | Offline regression and synthetic page interaction tests |

No trades, user accounts, persistent cloud watchlists, licensed real-time feeds, backtested signals, or paid market rankings are included.
