"""Taurus AI 2.0 — complete, dependency-free UI localization foundation.

Public interface (stable for the V2 modules):
    t(key, language='en', **values) -> translated string
    normalize_language(language) -> 'en' | 'zh' | 'de'
    language_options() -> tuple[(code, native_name), ...]
    format_number(value, language='en', decimals=2) -> str
    format_percent(value, language='en', decimals=2, signed=True) -> str
    format_date(value, language='en') -> str
    format_datetime(value, language='en', tz='UTC') -> str

No import of Streamlit: UI code owns the language selection/session state.
The English, Chinese and German copy has exactly the same set of keys.
Run `python i18n.py --check` to verify completeness and format placeholders.x
git branch --show-current

"""

from __future__ import annotations

from datetime import date, datetime, timezone
from math import isfinite
from string import Formatter
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

DEFAULT_LANGUAGE = 'en'
SUPPORTED_LANGUAGES = ('en', 'zh', 'de')
LANGUAGE_LABELS = {'en': 'English', 'zh': '简体中文', 'de': 'Deutsch'}

# key: (English, Simplified Chinese, German)
# Catalog design: UI language is independent from market price-direction colors.
# Dynamic arguments use Python named placeholders, e.g. {symbol}, {count}.
_COPY: dict[str, tuple[str, str, str]] = {
    # Application + navigation
    'app.name': ('Taurus AI', 'Taurus AI', 'Taurus AI'),
    'app.tagline': ('Smarter research. Clearer decisions.', '更聪明地研究，更清晰地判断。', 'Besser recherchieren. Klarer entscheiden.'),
    'app.subtitle': ('Global stock research powered by data and AI', '数据与 AI 驱动的全球股票研究', 'Globale Aktienrecherche mit Daten und KI'),
    'app.eyebrow': ('GLOBAL STOCK RESEARCH', '全球股票研究', 'GLOBALE AKTIENRECHERCHE'),
    'nav.home': ('Home', '首页', 'Startseite'),
    'nav.markets': ('Markets', '全球市场', 'Märkte'),
    'nav.research': ('Stock Research', '股票研究', 'Aktienanalyse'),
    'nav.news': ('News', '新闻中心', 'Nachrichten'),
    'nav.ai': ('AI Research', 'AI 研究', 'KI-Analyse'),
    'nav.about': ('About', '关于', 'Über uns'),
    'nav.settings': ('Settings', '设置', 'Einstellungen'),
    'nav.accessibility': ('Accessibility', '无障碍', 'Barrierefreiheit'),
    'common.language': ('Language', '语言', 'Sprache'),
    'common.search': ('Search', '搜索', 'Suchen'),
    'common.apply': ('Apply', '应用', 'Anwenden'),
    'common.clear': ('Clear', '清除', 'Löschen'),
    'common.reset': ('Reset', '重置', 'Zurücksetzen'),
    'common.close': ('Close', '关闭', 'Schließen'),
    'common.cancel': ('Cancel', '取消', 'Abbrechen'),
    'common.save': ('Save', '保存', 'Speichern'),
    'common.saved': ('Saved', '已保存', 'Gespeichert'),
    'common.refresh': ('Refresh', '刷新', 'Aktualisieren'),
    'common.retry': ('Retry', '重试', 'Erneut versuchen'),
    'common.loading': ('Loading…', '加载中…', 'Wird geladen …'),
    'common.show_more': ('Show more', '查看更多', 'Mehr anzeigen'),
    'common.show_less': ('Show less', '收起', 'Weniger anzeigen'),
    'common.view_all': ('View all', '查看全部', 'Alle anzeigen'),
    'common.learn_more': ('Learn more', '了解更多', 'Mehr erfahren'),
    'common.open_source': ('Open original source', '打开原始来源', 'Originalquelle öffnen'),
    'common.back': ('Back', '返回', 'Zurück'),
    'common.next': ('Next', '下一步', 'Weiter'),
    'common.export': ('Export', '导出', 'Exportieren'),
    'common.download': ('Download', '下载', 'Herunterladen'),
    'common.copy': ('Copy', '复制', 'Kopieren'),
    'common.date': ('Date', '日期', 'Datum'),
    'common.time': ('Time', '时间', 'Uhrzeit'),
    'common.source': ('Source', '来源', 'Quelle'),
    'common.sources': ('Sources', '来源', 'Quellen'),
    'common.updated': ('Updated', '更新于', 'Aktualisiert'),
    'common.as_of': ('As of {date}', '截至 {date}', 'Stand: {date}'),
    'common.retrieved_at': ('Retrieved {time}', '获取于 {time}', 'Abgerufen: {time}'),
    'common.unavailable': ('Unavailable', '暂无数据', 'Nicht verfügbar'),
    'common.unknown': ('Unknown', '未知', 'Unbekannt'),
    'common.no_data': ('No data available', '暂无可用数据', 'Keine Daten verfügbar'),
    'common.optional': ('Optional', '可选', 'Optional'),
    'common.yes': ('Yes', '是', 'Ja'),
    'common.no': ('No', '否', 'Nein'),
    'common.currency': ('Currency', '币种', 'Währung'),
    'common.market': ('Market', '市场', 'Markt'),
    'common.company': ('Company', '公司', 'Unternehmen'),
    'common.exchange': ('Exchange', '交易所', 'Börse'),
    'common.symbol': ('Ticker', '股票代码', 'Ticker'),
    'common.period': ('Period', '周期', 'Zeitraum'),
    'common.results': ('Results', '结果', 'Ergebnisse'),
    'common.disclaimer': ('Disclaimer', '免责声明', 'Haftungsausschluss'),
    'common.more_details': ('More details', '更多详情', 'Weitere Details'),
    'common.current_selection': ('Selected stock: {symbol}', '当前股票：{symbol}', 'Ausgewählte Aktie: {symbol}'),
    # Homepage and discovery
    'home.hero.title': ('Understand the market. One stock at a time.', '从每只股票开始，看懂市场。', 'Den Markt verstehen. Aktie für Aktie.'),
    'home.hero.description': ('Search global stocks, explore reliable evidence, and ask Taurus AI to explain it.', '搜索全球股票，查看可信数据，让 Taurus AI 帮你理解。', 'Globale Aktien suchen, belastbare Daten prüfen und von Taurus AI erklären lassen.'),
    'home.search.placeholder': ('Search ticker or company name — AAPL, NVIDIA, 贵州茅台…', '搜索股票代码或公司名称，例如 AAPL、英伟达、贵州茅台…', 'Ticker oder Unternehmen suchen – AAPL, NVIDIA, 贵州茅台 …'),
    'home.search.button': ('Research this stock', '研究这只股票', 'Aktie analysieren'),
    'home.popular_searches': ('Popular searches', '热门搜索', 'Häufig gesucht'),
    'home.market_overview': ('Global Market Overview', '全球市场概览', 'Globaler Marktüberblick'),
    'home.market_note': ('Latest available observations, not a guaranteed live feed', '最新可获取的行情，不保证实时', 'Letzte verfügbare Kursdaten, kein garantierter Live-Feed'),
    'home.trending': ('Trending & Active Stocks', '热门与活跃股票', 'Aktuell gefragte und aktive Aktien'),
    'home.trending_note': ('Rankings use observable market activity, not invented search popularity.', '榜单根据可验证的市场活跃度生成，不虚构搜索热度。', 'Ranglisten basieren auf messbarer Marktaktivität, nicht auf erfundener Suchpopularität.'),
    'home.top_news': ('Market News', '市场热点新闻', 'Marktnachrichten'),
    'home.top_news_note': ('Key developments and their original sources', '市场重点事件与原始来源', 'Wichtige Entwicklungen mit Originalquellen'),
    'home.explore_markets': ('Explore markets', '探索市场', 'Märkte entdecken'),
    'home.open_research': ('Open stock research', '进入股票研究', 'Aktienanalyse öffnen'),
    'home.quick_start': ('Start with a company, ticker, or market', '从公司名称、股票代码或市场开始', 'Mit Unternehmen, Ticker oder Markt starten'),
    # Search and market navigation
    'search.title': ('Find a stock', '查找股票', 'Aktie finden'),
    'search.label': ('Company name or ticker', '公司名称或股票代码', 'Unternehmensname oder Ticker'),
    'search.placeholder': ('e.g. AAPL, 600519, Tencent', '例如 AAPL、600519、腾讯', 'z. B. AAPL, 600519, Tencent'),
    'search.results': ('Search results', '搜索结果', 'Suchergebnisse'),
    'search.no_matches': ('No matching securities were found. Try a ticker or a more precise company name.', '未找到匹配证券，请尝试输入代码或更准确的公司名称。', 'Keine passenden Wertpapiere gefunden. Versuche einen Ticker oder einen genaueren Firmennamen.'),
    'search.enter_query': ('Enter a company name or ticker.', '请输入公司名称或股票代码。', 'Bitte Unternehmensname oder Ticker eingeben.'),
    'search.ambiguous': ('Select the correct exchange or listing.', '请选择正确的交易所或上市证券。', 'Bitte die richtige Börse bzw. Notierung auswählen.'),
    'search.unsupported_market': ('This market is not yet supported.', '暂不支持该市场。', 'Dieser Markt wird noch nicht unterstützt.'),
    'search.recent': ('Recently viewed', '最近查看', 'Zuletzt angesehen'),
    'search.suggestions': ('Suggestions', '搜索建议', 'Vorschläge'),
    'market.all': ('All markets', '全部市场', 'Alle Märkte'),
    'market.us': ('United States', '美国', 'USA'),
    'market.cn': ('China A-shares', '中国 A 股', 'China A-Aktien'),
    'market.hk': ('Hong Kong', '中国香港', 'Hongkong'),
    'market.eu': ('Europe', '欧洲', 'Europa'),
    'market.indices': ('Major indices', '主要指数', 'Wichtige Indizes'),
    'market.sectors': ('Sector performance', '行业表现', 'Sektorentwicklung'),
    'market.active': ('Most active', '成交活跃', 'Umsatzstärkste'),
    'market.gainers': ('Top gainers', '涨幅榜', 'Größte Gewinner'),
    'market.losers': ('Top losers', '跌幅榜', 'Größte Verlierer'),
    'market.volume': ('Trading volume', '成交量', 'Handelsvolumen'),
    'market.turnover': ('Trading value', '成交额', 'Handelswert'),
    'market.market_cap': ('Market capitalization', '总市值', 'Marktkapitalisierung'),
    'market.prev_close': ('Previous close', '前收盘价', 'Vorheriger Schlusskurs'),
    'market.day_change': ('Daily change', '当日涨跌幅', 'Tagesveränderung'),
    'market.change_vs_prior': ('vs previous available daily close', '相较上一可用日收盘价', 'ggü. dem letzten verfügbaren Tagesschluss'),
    'market.closed': ('Market closed', '市场休市', 'Markt geschlossen'),
    'market.open': ('Market open', '市场交易中', 'Markt geöffnet'),
    'market.status_unknown': ('Market status unavailable', '无法确认市场状态', 'Marktstatus nicht verfügbar'),
    'market.delayed': ('Delayed quote', '延迟行情', 'Zeitverzögerter Kurs'),
    'market.daily': ('Daily data', '日线数据', 'Tagesdaten'),
    'market.intraday': ('Intraday data', '盘中数据', 'Intraday-Daten'),
    'market.data_as_of': ('Price observation: {date}', '行情日期：{date}', 'Kursstand: {date}'),
    'market.not_live': ('Not a live price feed', '非实时行情', 'Kein Live-Kursfeed'),
    'market.chart_not_available': ('Price history is temporarily unavailable.', '暂时无法获取历史行情。', 'Kursverlauf ist vorübergehend nicht verfügbar.'),
    'market.no_ranking': ('No verified ranking data available for this market.', '该市场暂无经验证的榜单数据。', 'Für diesen Markt sind keine verifizierten Ranglistendaten verfügbar.'),
    # Stock research / charts / indicators
    'stock.title': ('Stock Research', '股票研究', 'Aktienanalyse'),
    'stock.overview': ('Overview', '概览', 'Überblick'),
    'stock.chart': ('Price Chart', '股价图表', 'Kurschart'),
    'stock.technicals': ('Technical Analysis', '技术分析', 'Technische Analyse'),
    'stock.fundamentals': ('Fundamentals', '基本面', 'Fundamentaldaten'),
    'stock.company_news': ('Company News', '公司新闻', 'Unternehmensnachrichten'),
    'stock.ai_insights': ('AI Insights', 'AI 解读', 'KI-Einschätzungen'),
    'stock.about_company': ('About the company', '公司简介', 'Unternehmensprofil'),
    'stock.latest_price': ('Latest available price', '最新可获取价格', 'Letzter verfügbarer Kurs'),
    'stock.price_change': ('Price change', '价格变化', 'Kursänderung'),
    'stock.change_percent': ('Change (%)', '涨跌幅（%）', 'Veränderung (%)'),
    'stock.trading_date': ('Trading date', '交易日期', 'Handelstag'),
    'stock.data_source': ('Market data source', '行情数据来源', 'Marktdatenquelle'),
    'stock.view_full_report': ('View full AI report', '查看完整 AI 报告', 'Vollständigen KI-Bericht anzeigen'),
    'stock.refresh': ('Refresh this stock', '刷新这只股票', 'Diese Aktie aktualisieren'),
    'stock.add_watchlist': ('Add to watchlist', '加入自选股', 'Zur Watchlist hinzufügen'),
    'stock.remove_watchlist': ('Remove from watchlist', '移出自选股', 'Aus Watchlist entfernen'),
    'stock.research_scope': ('Research timeframe', '研究周期', 'Analysezeitraum'),
    'stock.price_not_available': ('Price not available. Try refreshing or selecting another stock.', '暂时无法获取股价，请刷新或选择其他股票。', 'Kurs nicht verfügbar. Bitte aktualisieren oder eine andere Aktie wählen.'),
    'chart.title': ('Price & Trend', '价格与趋势', 'Kurs und Trend'),
    'chart.range': ('Chart range', '图表时间范围', 'Chart-Zeitraum'),
    'chart.line': ('Line', '折线图', 'Linie'),
    'chart.candlestick': ('Candlestick', 'K 线图', 'Kerzenchart'),
    'chart.volume': ('Volume', '成交量', 'Volumen'),
    'chart.compare': ('Compare', '对比', 'Vergleichen'),
    'chart.close': ('Close', '收盘价', 'Schlusskurs'),
    'chart.open': ('Open', '开盘价', 'Eröffnungskurs'),
    'chart.high': ('High', '最高价', 'Höchstkurs'),
    'chart.low': ('Low', '最低价', 'Tiefstkurs'),
    'chart.adjusted': ('Adjusted close', '复权收盘价', 'Bereinigter Schlusskurs'),
    'chart.inspect_data': ('Inspect prices and indicators', '查看价格与指标明细', 'Kurse und Indikatoren prüfen'),
    'chart.note': ('The latest daily candle may be incomplete. Verify the trading date.', '最新日 K 线可能尚未完成，请核对交易日期。', 'Die letzte Tageskerze kann unvollständig sein. Handelstag prüfen.'),
    'chart.no_history': ('Not enough price history for this chart.', '历史行情不足，无法展示图表。', 'Nicht genügend Kursverlauf für dieses Diagramm.'),
    'indicator.title': ('Technical Indicators', '技术指标', 'Technische Indikatoren'),
    'indicator.sma20': ('20-day moving average', '20 日均线', 'Gleitender 20-Tage-Durchschnitt'),
    'indicator.sma50': ('50-day moving average', '50 日均线', 'Gleitender 50-Tage-Durchschnitt'),
    'indicator.rsi14': ('RSI (14)', '相对强弱指数 RSI（14）', 'RSI (14)'),
    'indicator.macd': ('MACD', 'MACD 指标', 'MACD'),
    'indicator.bollinger': ('Bollinger Bands', '布林带', 'Bollinger-Bänder'),
    'indicator.volatility': ('Volatility', '波动率', 'Volatilität'),
    'indicator.signal': ('Technical signal', '技术信号', 'Technisches Signal'),
    'indicator.signal_buy': ('BUY', '买入信号', 'KAUFSIGNAL'),
    'indicator.signal_hold': ('HOLD', '中性信号', 'NEUTRALES SIGNAL'),
    'indicator.signal_sell': ('SELL', '卖出信号', 'VERKAUFSSIGNAL'),
    'indicator.signal_unavailable': ('UNAVAILABLE', '无法判断', 'NICHT VERFÜGBAR'),
    'indicator.signal_note': ('Rule-based classification; not a validated forecast or personal recommendation.', '基于规则的分类，不代表已验证的预测或个性化投资建议。', 'Regelbasierte Einordnung; keine validierte Prognose oder persönliche Empfehlung.'),
    'indicator.reason': ('Why this signal?', '信号依据是什么？', 'Warum dieses Signal?'),
    'indicator.methodology': ('Methodology & limitations', '方法与局限性', 'Methodik und Einschränkungen'),
    'indicator.insufficient': ('Not enough verified observations for a reliable signal.', '缺少足够的有效数据，无法生成可靠信号。', 'Nicht genügend verifizierte Daten für ein belastbares Signal.'),
    # Fundamentals / financials
    'fund.title': ('Financial Fundamentals', '财务基本面', 'Finanzkennzahlen'),
    'fund.valuation': ('Valuation', '估值', 'Bewertung'),
    'fund.profitability': ('Profitability', '盈利能力', 'Profitabilität'),
    'fund.growth': ('Growth', '成长性', 'Wachstum'),
    'fund.balance_sheet': ('Balance Sheet', '资产负债表', 'Bilanz'),
    'fund.income_statement': ('Income Statement', '利润表', 'Gewinn- und Verlustrechnung'),
    'fund.cash_flow': ('Cash Flow', '现金流', 'Cashflow'),
    'fund.revenue': ('Revenue', '营业收入', 'Umsatz'),
    'fund.net_income': ('Net income', '净利润', 'Jahresüberschuss'),
    'fund.eps': ('Earnings per share (EPS)', '每股收益（EPS）', 'Gewinn je Aktie (EPS)'),
    'fund.pe': ('Price-to-earnings (P/E)', '市盈率（PE）', 'Kurs-Gewinn-Verhältnis (KGV)'),
    'fund.pb': ('Price-to-book (P/B)', '市净率（PB）', 'Kurs-Buchwert-Verhältnis (KBV)'),
    'fund.roe': ('Return on equity (ROE)', '净资产收益率（ROE）', 'Eigenkapitalrendite (ROE)'),
    'fund.debt_to_equity': ('Debt-to-equity', '资产负债与权益比', 'Verschuldungsgrad'),
    'fund.free_cash_flow': ('Free cash flow', '自由现金流', 'Freier Cashflow'),
    'fund.dividend_yield': ('Dividend yield', '股息率', 'Dividendenrendite'),
    'fund.fiscal_period': ('Reporting period', '报告期间', 'Berichtszeitraum'),
    'fund.unit': ('Reporting unit', '报表单位', 'Berichtseinheit'),
    'fund.not_reported': ('Not reported by the source', '数据源未披露', 'Von der Quelle nicht ausgewiesen'),
    'fund.data_limited': ('Financial coverage varies by exchange and provider.', '财务数据覆盖范围因交易所及数据源而异。', 'Die Abdeckung von Finanzdaten variiert je nach Börse und Datenanbieter.'),
    # News and events
    'news.title': ('Market News & Intelligence', '市场新闻与资讯', 'Marktnachrichten und Hintergründe'),
    'news.description': ('Explore events, original reporting, and their relevance to stocks.', '查看市场事件、原始报道及相关股票。', 'Ereignisse, Originalberichte und ihre Bedeutung für Aktien entdecken.'),
    'news.top_stories': ('Top Stories', '重点新闻', 'Top-Meldungen'),
    'news.company': ('Company News', '公司新闻', 'Unternehmensnachrichten'),
    'news.macro': ('Macro & Economy', '宏观与经济', 'Makro und Wirtschaft'),
    'news.earnings': ('Earnings & Filings', '财报与公告', 'Geschäftsberichte und Meldungen'),
    'news.technology': ('Technology', '科技', 'Technologie'),
    'news.policy': ('Policy', '政策', 'Politik und Regulierung'),
    'news.market_wide': ('Market-wide', '全市场', 'Marktübergreifend'),
    'news.related_stocks': ('Related stocks', '相关股票', 'Betroffene Aktien'),
    'news.filter.market': ('Filter by market', '按市场筛选', 'Nach Markt filtern'),
    'news.filter.topic': ('Filter by topic', '按主题筛选', 'Nach Thema filtern'),
    'news.filter.time': ('Time range', '时间范围', 'Zeitraum'),
    'news.filter.company': ('Company / ticker', '公司 / 股票代码', 'Unternehmen / Ticker'),
    'news.filter.keyword': ('Search loaded headlines', '搜索已加载新闻标题', 'Geladene Schlagzeilen durchsuchen'),
    'news.latest': ('Latest', '最新', 'Neueste'),
    'news.published': ('Published {date}', '发布于 {date}', 'Veröffentlicht: {date}'),
    'news.publisher': ('Publisher', '发布媒体', 'Quelle'),
    'news.read_original': ('Read original article', '阅读原文', 'Originalartikel lesen'),
    'news.explain': ('Explain this news with Taurus AI', '让 Taurus AI 解读这条新闻', 'Diese Nachricht von Taurus AI erklären lassen'),
    'news.summary': ('News summary', '新闻摘要', 'Nachrichtenzusammenfassung'),
    'news.fact': ('Reported fact', '报道事实', 'Berichtete Tatsache'),
    'news.interpretation': ('AI interpretation', 'AI 推断', 'KI-Interpretation'),
    'news.no_match': ('No matching verified headlines found.', '未找到匹配的有效新闻。', 'Keine passenden verifizierten Schlagzeilen gefunden.'),
    'news.no_source': ('Publisher not supplied', '未提供媒体来源', 'Quelle nicht angegeben'),
    'news.no_date': ('Publication time not supplied', '未提供发布时间', 'Veröffentlichungszeit nicht angegeben'),
    'news.unavailable': ('News is temporarily unavailable. Stock research remains accessible.', '暂时无法获取新闻，股票研究仍可使用。', 'Nachrichten vorübergehend nicht verfügbar. Die Aktienanalyse bleibt nutzbar.'),
    'news.provider_note': ('Article relevance and availability depend on the source.', '新闻相关性和可访问性取决于数据来源。', 'Relevanz und Verfügbarkeit hängen von der Quelle ab.'),
    'news.duplicates_removed': ('Similar reports may be grouped.', '相似报道可能合并展示。', 'Ähnliche Berichte können zusammengefasst werden.'),
    # AI research
    'ai.title': ('Taurus AI Research', 'Taurus AI 智能研究', 'Taurus KI-Analyse'),
    'ai.subtitle': ('Evidence first. Interpretation second.', '先看证据，再做解读。', 'Erst die Fakten, dann die Interpretation.'),
    'ai.generate': ('Generate AI Research Report', '生成 AI 研究报告', 'KI-Analysebericht erstellen'),
    'ai.regenerate': ('Regenerate report', '重新生成报告', 'Bericht neu erstellen'),
    'ai.generating': ('Analyzing verified data…', '正在分析已验证的数据…', 'Verifizierte Daten werden analysiert …'),
    'ai.ask': ('Ask Taurus AI', '向 Taurus AI 提问', 'Taurus AI fragen'),
    'ai.question.placeholder': ('Ask about the evidence, risks, or alternative scenarios…', '询问数据依据、风险或不同市场情景…', 'Frage nach Datenlage, Risiken oder alternativen Szenarien …'),
    'ai.follow_up': ('Ask a follow-up question', '继续追问', 'Nachfrage stellen'),
    'ai.report': ('Research Report', '研究报告', 'Analysebericht'),
    'ai.report.summary': ('Research Summary', '综合研究摘要', 'Zusammenfassung'),
    'ai.report.technical': ('Technical Evidence', '技术面证据', 'Technische Evidenz'),
    'ai.report.fundamental': ('Fundamental Evidence', '基本面证据', 'Fundamentale Evidenz'),
    'ai.report.news': ('Events & Catalysts', '市场事件与催化因素', 'Ereignisse und Kurstreiber'),
    'ai.report.bull': ('Positive Scenario', '积极情景', 'Positives Szenario'),
    'ai.report.bear': ('Negative Scenario', '消极情景', 'Negatives Szenario'),
    'ai.report.invalidations': ('What would change this view?', '什么情况会改变当前判断？', 'Was würde diese Einschätzung ändern?'),
    'ai.report.risks': ('Risks & Uncertainty', '风险与不确定性', 'Risiken und Unsicherheit'),
    'ai.report.watch': ('What to Watch', '后续关注要点', 'Worauf zu achten ist'),
    'ai.report.limitations': ('Limitations', '分析局限性', 'Einschränkungen'),
    'ai.report.sources': ('Evidence & Sources', '证据与来源', 'Belege und Quellen'),
    'ai.report.generated': ('Generated {time}', '生成于 {time}', 'Erstellt: {time}'),
    'ai.status.ready': ('AI ready', 'AI 已连接', 'KI bereit'),
    'ai.status.not_connected': ('AI not connected', 'AI 未连接', 'KI nicht verbunden'),
    'ai.status.session_used': ('AI used this session', '本次会话已使用 AI', 'KI in dieser Sitzung genutzt'),
    'ai.key_missing': ('AI key not configured. Data and rules remain available.', '尚未配置 AI 密钥，行情和规则分析仍可使用。', 'Kein KI-Schlüssel konfiguriert. Kursdaten und Regeln bleiben verfügbar.'),
    'ai.key_rejected': ('The AI provider rejected the key or model access.', 'AI 服务拒绝了密钥或模型访问权限。', 'Der KI-Anbieter hat Schlüssel oder Modellzugriff abgelehnt.'),
    'ai.quota': ('Free AI quota or rate limit reached. Try again later.', '免费 AI 额度或速率限制已达到，请稍后重试。', 'Kostenloses KI-Limit erreicht. Bitte später erneut versuchen.'),
    'ai.cooldown': ('Please wait {seconds} seconds between AI requests.', '两次 AI 请求之间请等待 {seconds} 秒。', 'Bitte {seconds} Sekunden zwischen KI-Anfragen warten.'),
    'ai.error': ('AI could not generate a report. No fabricated fallback is shown.', 'AI 无法生成报告，系统不会展示虚构的替代内容。', 'KI konnte keinen Bericht erstellen. Es werden keine erfundenen Ersatzdaten angezeigt.'),
    'ai.not_forecast': ('AI explanations are not price forecasts or guaranteed trading signals.', 'AI 解释不等于价格预测或保证有效的交易信号。', 'KI-Erklärungen sind keine Kursprognosen oder garantierten Handelssignale.'),
    'ai.snapshot_note': ('Only the listed data snapshot and evidence are used for this report.', '本报告仅使用列明的数据快照和证据。', 'Dieser Bericht verwendet ausschließlich den angegebenen Datenstand und die genannten Belege.'),
    'ai.facts_vs_inference': ('Distinguish source facts from model interpretation.', '请区分来源事实和模型推断。', 'Quellenfakten von Modellinterpretationen unterscheiden.'),
    # Watchlists and comparison (reserved in V2 architecture)
    'watchlist.title': ('Watchlist', '自选股', 'Watchlist'),
    'watchlist.empty': ('No saved stocks yet.', '还没有收藏股票。', 'Noch keine gespeicherten Aktien.'),
    'watchlist.local_only': ('Saved in this session only; not synced across devices.', '仅在当前会话中保存，不跨设备同步。', 'Nur in dieser Sitzung gespeichert; keine geräteübergreifende Synchronisierung.'),
    'compare.title': ('Compare Stocks', '股票对比', 'Aktien vergleichen'),
    'compare.select': ('Select two stocks', '选择两只股票', 'Zwei Aktien auswählen'),
    'compare.insufficient': ('Select two valid securities to compare.', '请选择两只有效证券进行对比。', 'Bitte zwei gültige Wertpapiere zum Vergleich auswählen.'),
    'screen.title': ('Stock Screener', '股票筛选器', 'Aktien-Screener'),
    'screen.filters': ('Screening filters', '筛选条件', 'Screening-Filter'),
    'screen.empty': ('No stocks meet the selected criteria.', '没有股票满足所选条件。', 'Keine Aktien erfüllen die ausgewählten Kriterien.'),
    # Data quality and failure modes
    'error.generic': ('Something went wrong. Please try again.', '发生错误，请重试。', 'Etwas ist schiefgelaufen. Bitte erneut versuchen.'),
    'error.network': ('The data provider could not be reached.', '无法连接数据服务。', 'Der Datenanbieter ist nicht erreichbar.'),
    'error.timeout': ('The request timed out. Please retry.', '请求超时，请重试。', 'Zeitüberschreitung. Bitte erneut versuchen.'),
    'error.rate_limited': ('The provider is temporarily rate-limiting requests.', '数据服务暂时限制请求频率。', 'Der Anbieter begrenzt vorübergehend die Anfragen.'),
    'error.invalid_symbol': ('Enter a valid ticker or company name.', '请输入有效的股票代码或公司名称。', 'Bitte einen gültigen Ticker oder Unternehmensnamen eingeben.'),
    'error.no_prices': ('No price data returned for {symbol}.', '未获取到 {symbol} 的价格数据。', 'Keine Kursdaten für {symbol} erhalten.'),
    'error.stale_prices': ('Price data is older than expected. The signal is withheld.', '行情数据超过预期时效，暂不生成信号。', 'Kursdaten sind älter als erwartet. Das Signal wird zurückgehalten.'),
    'error.invalid_data': ('The source returned incomplete or invalid values.', '数据源返回不完整或无效的数据。', 'Die Quelle lieferte unvollständige oder ungültige Werte.'),
    'error.partial_service': ('Some services are unavailable; other research features still work.', '部分服务暂不可用，其他研究功能仍可使用。', 'Einige Dienste sind nicht verfügbar; andere Analysefunktionen bleiben nutzbar.'),
    'error.no_verified_source': ('Verified data is unavailable; no substitute values are shown.', '缺少可信数据，不会展示虚构的替代数值。', 'Keine verifizierten Daten verfügbar; es werden keine Ersatzwerte erfunden.'),
    'error.unexpected': ('An unexpected error occurred. No report was generated.', '出现未知错误，未生成报告。', 'Unerwarteter Fehler. Es wurde kein Bericht erstellt.'),
    # Controls, method, legal, and freshness
    'settings.theme': ('Appearance', '外观', 'Darstellung'),
    'settings.market_colors': ('Market movement colors', '涨跌颜色方案', 'Farben für Kursbewegungen'),
    'settings.colors.neutral': ('Neutral: blue up / orange down', '中立：蓝涨 / 橙跌', 'Neutral: Blau steigt / Orange fällt'),
    'settings.colors.us': ('US convention: green up / red down', '美股习惯：绿涨 / 红跌', 'US-Stil: Grün steigt / Rot fällt'),
    'settings.colors.cn': ('China convention: red up / green down', 'A 股习惯：红涨 / 绿跌', 'China-Stil: Rot steigt / Grün fällt'),
    'settings.timezone': ('Display timezone', '显示时区', 'Anzeigezeitzone'),
    'settings.data_info': ('Data sources and freshness', '数据来源与时效', 'Datenquellen und Aktualität'),
    'about.title': ('About Taurus AI', '关于 Taurus AI', 'Über Taurus AI'),
    'about.description': ('A research tool combining market data, transparent rules and optional AI explanations.', '结合市场数据、透明规则和可选 AI 解读的研究工具。', 'Ein Recherchetool mit Marktdaten, transparenten Regeln und optionalen KI-Erklärungen.'),
    'about.method': ('Methodology', '研究方法', 'Methodik'),
    'about.limits': ('Data and AI limitations', '数据与 AI 的局限性', 'Grenzen von Daten und KI'),
    'legal.educational': ('For information and research only, not personalized investment advice.', '仅供信息与研究使用，不构成个性化投资建议。', 'Nur zur Information und Recherche, keine persönliche Anlageberatung.'),
    'legal.no_trading': ('No trading execution or brokerage service.', '不提供交易执行或证券经纪服务。', 'Keine Handelsausführung und kein Brokerdienst.'),
    'legal.verify': ('Verify dates, sources and reported values before relying on them.', '使用前请核对日期、来源及数据。', 'Datum, Quellen und Werte vor der Nutzung überprüfen.'),
    'legal.provider_rights': ('Market data usage is subject to provider terms and permissions.', '市场数据使用须遵守数据提供方条款及授权要求。', 'Die Nutzung von Marktdaten unterliegt den Bedingungen und Rechten der Anbieter.'),
    'legal.ai_warning': ('AI may make mistakes. Confirm all claims against the sources.', 'AI 可能出错，请根据来源核实所有陈述。', 'KI kann Fehler machen. Alle Aussagen anhand der Quellen prüfen.'),
    'footer.brand': ('Taurus AI · Research with perspective.', 'Taurus AI · 以更全面的视角研究。', 'Taurus AI · Forschung mit Perspektive.'),
    'footer.disclaimer': ('Research tool · Not investment advice · No trading execution', '研究工具 · 非投资建议 · 不提供交易执行', 'Analysetool · Keine Anlageberatung · Keine Handelsausführung'),
}

TRANSLATIONS: dict[str, dict[str, str]] = {
    code: {key: triplet[index] for key, triplet in _COPY.items()}
    for index, code in enumerate(SUPPORTED_LANGUAGES)
}


def language_options() -> tuple[tuple[str, str], ...]:
    """Return language code and its native display name, in menu order."""
    return tuple((code, LANGUAGE_LABELS[code]) for code in ('zh', 'en', 'de'))


def normalize_language(language: str | None) -> str:
    """Resolve language codes, browser locale variants, and native labels."""
    if language is None:
        return DEFAULT_LANGUAGE
    raw = str(language).strip().lower().replace('_', '-')
    if raw in ('中文', '简体中文', 'chinese'):
        return 'zh'
    if raw in ('deutsch', 'german'):
        return 'de'
    if raw in ('english',):
        return 'en'
    prefix = raw.split('-')[0]
    if prefix in SUPPORTED_LANGUAGES:
        return prefix
    return DEFAULT_LANGUAGE


def t(key: str, language: str = DEFAULT_LANGUAGE, **values: Any) -> str:
    """Translate a stable UI key and format named placeholders.

    Unknown keys raise KeyError during development; missing parameters also
    raise a helpful KeyError. No sensitive values should be logged here.
    """
    code = normalize_language(language)
    try:
        template = TRANSLATIONS[code][key]
    except KeyError as exc:
        raise KeyError(f'Unknown translation key: {key!r}') from exc
    if not values:
        return template
    try:
        return template.format_map(values)
    except KeyError as exc:
        raise KeyError(f'Missing placeholder {exc!s} for translation key {key!r}') from exc


def format_number(value: Any, language: str = DEFAULT_LANGUAGE, decimals: int = 2) -> str:
    """Format an already-converted number with language-specific separators.

    Unlike locale.setlocale, this is thread-safe for concurrent Streamlit users.
    No conversion of units, currencies, or underlying precision occurs.
    """
    code = normalize_language(language)
    if not isinstance(decimals, int) or not 0 <= decimals <= 10:
        raise ValueError('decimals must be an integer between 0 and 10')
    try:
        number = float(value)
        if not isfinite(number):
            return t('common.unavailable', code)
    except (TypeError, ValueError, OverflowError):
        return t('common.unavailable', code)
    formatted = f'{number:,.{decimals}f}'
    if code == 'de':
        return formatted.replace(',', '#').replace('.', ',').replace('#', '.')
    if code == 'zh':
        return formatted
    return formatted


def format_percent(value: Any, language: str = DEFAULT_LANGUAGE, decimals: int = 2, signed: bool = True) -> str:
    """Format an already percent-scaled number, e.g. 2.5 -> +2.50%."""
    code = normalize_language(language)
    value_str = format_number(value, code, decimals)
    if value_str == t('common.unavailable', code):
        return value_str
    number = float(value)
    prefix = '+' if signed and number > 0 else ''
    # Use a real minus for readability; ASCII minus remains accepted in inputs.
    return f'{prefix}{value_str}%'


def format_date(value: date | datetime, language: str = DEFAULT_LANGUAGE) -> str:
    """Format a calendar date without changing its time zone."""
    if not isinstance(value, date):
        raise TypeError('value must be a date or datetime instance')
    code = normalize_language(language)
    if code == 'zh':
        return f'{value.year}年{value.month}月{value.day}日'
    if code == 'de':
        return f'{value.day:02d}.{value.month:02d}.{value.year}'
    return f'{value.year:04d}-{value.month:02d}-{value.day:02d}'


def format_datetime(value: datetime, language: str = DEFAULT_LANGUAGE, tz: str = 'UTC') -> str:
    """Format an aware timestamp in an explicitly selected IANA time zone.

    A naive input is interpreted as UTC, consistent with app provider timestamps.
    """
    if not isinstance(value, datetime):
        raise TypeError('value must be a datetime instance')
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    try:
        local = value.astimezone(ZoneInfo(tz))
    except ZoneInfoNotFoundError as exc:
        raise ValueError(f'Unknown time zone: {tz}') from exc
    label = local.strftime('%Z') or tz
    return f'{format_date(local, language)} {local:%H:%M} {label}'


def _fields(text: str) -> set[str]:
    output: set[str] = set()
    for _literal, field, _format, _conversion in Formatter().parse(text):
        if field is not None:
            if not field.isidentifier():
                raise ValueError(f'Invalid placeholder: {field!r}')
            output.add(field)
    return output


def validate_catalog() -> tuple[int, tuple[str, ...]]:
    """Validate all languages, every key, and format placeholders."""
    problems: list[str] = []
    if len(_COPY) != len(set(_COPY)):
        problems.append('Duplicate translation key')
    for key, values in _COPY.items():
        if len(values) != len(SUPPORTED_LANGUAGES):
            problems.append(f'{key}: missing language')
            continue
        try:
            expected_fields = _fields(values[0])
            for code, value in zip(SUPPORTED_LANGUAGES, values):
                if not isinstance(value, str) or not value.strip():
                    problems.append(f'{key}: blank {code} translation')
                if _fields(value) != expected_fields:
                    problems.append(f'{key}: placeholders differ in {code}')
        except ValueError as exc:
            problems.append(f'{key}: {exc}')
    expected = set(_COPY)
    for code in SUPPORTED_LANGUAGES:
        if set(TRANSLATIONS[code]) != expected:
            problems.append(f'{code}: key set differs from source')
    return len(_COPY), tuple(problems)


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='Taurus AI translation quality checks')
    parser.add_argument('--check', action='store_true', help='Check catalog completeness and placeholders')
    parser.add_argument('--demo', action='store_true', help='Preview essential translations')
    args = parser.parse_args()
    if args.check or not args.demo:
        count, errors = validate_catalog()
        if errors:
            for problem in errors:
                print('ERROR:', problem)
            raise SystemExit(1)
        print(f'i18n OK: {count} keys × {len(SUPPORTED_LANGUAGES)} languages (en/zh/de)')
    if args.demo:
        for code, label in language_options():
            print(f'{label}: {t("home.hero.title", code)}')
            print(f'  {t("home.search.placeholder", code)}')
            print(f'  {format_number(12345.67, code)} | {format_percent(2.48, code)}')
