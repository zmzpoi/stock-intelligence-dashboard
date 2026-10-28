"""Small, auditable research context for an LLM; no synthetic market facts."""
from __future__ import annotations
from datetime import datetime, timezone
import math
import pandas as pd
from indicators import IndicatorSettings


def finite(x, decimals=4):
    try:
        v = float(x)
        return round(v, decimals) if math.isfinite(v) else None
    except (TypeError, ValueError, OverflowError):
        return None


def build_snapshot(symbol: str, prices: pd.DataFrame, computed: pd.DataFrame,
                   settings: IndicatorSettings, status: str, reasons: list[str],
                   retrieved_at: datetime, fundamentals=None, articles=None):
    if computed.empty:
        raise ValueError('Cannot research an empty price history.')
    latest = computed.iloc[-1]
    first = computed.iloc[0]
    pct = ((float(latest.Close) / float(first.Close) - 1)*100) if float(first.Close) > 0 else None
    recent = computed.tail(20)
    vol_mean = finite(pd.to_numeric(recent.get('Volume'), errors='coerce').mean()) if 'Volume' in recent else None
    metrics = {col: finite(latest.get(col)) for col in (
        'Close', 'Volume','SMA_fast','SMA_slow','EMA','RSI','MACD','MACD_signal',
        'MACD_hist','BB_upper','BB_lower','ATR','K','D','J','DailyReturn')}
    metrics.update({'history_return_pct':finite(pct,2), 'recent_average_volume_20_bars':vol_mean})
    if fundamentals and isinstance(fundamentals,dict):
        f = {'company':fundamentals.get('company'), 'sector':fundamentals.get('sector'),
             'source':fundamentals.get('source'),'period_note':fundamentals.get('period_note'),
             'metrics':{k:finite(v) for k,v in (fundamentals.get('metrics') or {}).items()}}
    else:
        f = {'status':'unavailable'}
    titles = []
    for item in (articles or [])[:5]:
        if isinstance(item,dict):
            titles.append({k:item.get(k) for k in ('title','source','date','url')})
    return {'symbol':symbol,'company':prices.attrs.get('company') or None,
            'market':prices.attrs.get('market') or None,
            'currency':prices.attrs.get('currency') or None,
            'provider':prices.attrs.get('source') or 'Yahoo Finance via yfinance',
            'history_start':str(computed.index[0].date()),
            'history_end':str(computed.index[-1].date()),
            'retrieved_at_utc':retrieved_at.astimezone(timezone.utc).isoformat(),
            'history_bars':len(computed),'adjusted':bool(prices.attrs.get('adjusted',False)),
            'settings':vars(settings),'trend_classification':status,
            'trend_evidence':list(reasons), 'metrics':metrics,
            'fundamentals':f,'headlines_only_not_full_articles':titles,
            'data_limitations':['Prices are delayed best-effort daily history, not guaranteed live prices.',
                                'AI must not infer article contents from headlines.',
                                'Financial metrics may combine reporting periods.',
                                'Historical trend does not predict future returns.']}
