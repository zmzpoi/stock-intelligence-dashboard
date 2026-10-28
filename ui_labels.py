"""V3-specific labels; existing i18n catalog remains backward compatible."""
from i18n import t

NEW = {
 'market_jump':('View this market','查看此市场','Diesen Markt ansehen'),
 'index_research':('Inspect index history','查看指数走势','Indexverlauf ansehen'),
 'curated':('Examples to explore · not market-wide rankings','精选研究样本 · 非全市场涨跌榜','Recherchebeispiele · keine marktweite Rangliste'),
 'stock_research':('Research this security','研究这只证券','Dieses Wertpapier analysieren'),
 'price_unavailable':('Quotes unavailable; the navigation and security list remain available.','行情暂不可用，市场导航和证券列表仍可使用。','Kurse nicht verfügbar; Navigation und Wertpapierliste bleiben nutzbar.'),
 'five_year_notice':('Up to five years of daily observations are loaded. Zoom changes the visible dates; it does not fabricate bars.','最多加载五年日线。缩放改变可见日期，不会虚构行情。','Bis zu fünf Jahre Tagesdaten geladen. Zoomen ändert den sichtbaren Zeitraum.'),
 'lower_indicator':('Lower indicator','副图指标','Unterer Indikator'),
 'type':('Chart type','图表类型','Diagrammtyp'),
 'candles':('Candlestick','K 线','Kerzen'),
 'line':('Line','折线','Linie'),
 'overlay':('Price overlays','价格主图指标','Kurs-Overlays'),
 'settings':('Indicator settings','指标参数设置','Indikator-Einstellungen'),
 'rsi_period':('RSI period','RSI 周期','RSI-Periode'),
 'sma_fast':('SMA short period','短期均线','SMA kurz'),
 'sma_slow':('SMA long period','长期均线','SMA lang'),
 'ema_period':('EMA period','EMA 周期','EMA-Periode'),
 'macd_fast':('MACD fast','MACD 快线周期','MACD schnell'),
 'macd_slow':('MACD slow','MACD 慢线周期','MACD langsam'),
 'macd_signal':('MACD signal','MACD 信号周期','MACD Signal'),
 'bollinger_period':('Bollinger period','布林带周期','Bollinger-Periode'),
 'bollinger_width':('Bollinger std. dev.','布林带标准差倍数','Bollinger Standardabweichung'),
 'technical_explain':('Technical interpretation','技术指标解读','Technische Einordnung'),
 'snapshot':('Research evidence · from current indicator settings','研究证据 · 使用当前指标设置','Research-Daten · mit aktuellen Indikatoreinstellungen'),
 'ai_standalone':('Independent AI Research workspace','独立 AI 研究工作台','Eigenständiger KI-Recherchebereich'),
 'ai_question':('Ask a follow-up about this evidence (optional)','针对这些证据继续提问（可选）','Rückfrage zu diesen Daten (optional)'),
 'ask_ai':('Ask Taurus AI','向 Taurus AI 提问','Taurus AI fragen'),
 'ai_security':('AI responses are generated on demand, can be wrong, and cannot replace source checks.','AI 仅按需生成、可能出错，重要信息需核对来源。','KI-Antworten können fehlerhaft sein; Quellen müssen geprüft werden.'),
 'ai_key_note':('Set GROQ_API_KEY in local .streamlit/secrets.toml or Streamlit Cloud Secrets. Never upload it to GitHub.','在本地或 Streamlit Cloud Secrets 配置 GROQ_API_KEY，勿上传 GitHub。','GROQ_API_KEY lokal oder in Streamlit Cloud Secrets setzen, nie auf GitHub hochladen.'),
 'refresh':('Refresh cached data','刷新缓存数据','Zwischengespeicherte Daten aktualisieren'),
 'data_period':('Actual history available: {start} to {end}','实际可用历史：{start} 至 {end}','Verfügbarer Verlauf: {start} bis {end}'),
 'reset_defaults':('Reset settings','恢复默认参数','Standardwerte wiederherstellen'),
 'trend_bullish':('Bullish alignment (descriptive)','趋势偏强（描述性）','Positive Tendenz (deskriptiv)'),
 'trend_bearish':('Bearish alignment (descriptive)','趋势偏弱（描述性）','Negative Tendenz (deskriptiv)'),
 'trend_mixed':('Mixed / inconclusive','信号不一致','Gemischte Signale'),
 'trend_unavailable':('Insufficient evidence','证据不足','Unzureichende Daten'),
 'download_csv':('Export visible data to CSV','导出当前数据 CSV','Aktuelle Daten als CSV exportieren'),
 'ai_no_evidence':('Generate a report to see an evidence-based explanation.','点击生成报告，查看基于实际数据的解读。','Bericht erstellen, um datengestützte Analyse zu lesen.'),
}

def ui(key: str, lang='en', **kwargs) -> str:
    if key not in NEW:
        return t(key, lang, **kwargs)
    idx = {'en':0,'zh':1,'de':2}.get(lang,0)
    result = NEW[key][idx]
    return result.format(**kwargs) if kwargs else result
