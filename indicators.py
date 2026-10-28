"""Deterministic, configurable daily-bar indicators for educational research.

Price input is never fabricated. NaN warm-up bars remain NaN; calculations use
observed daily closes. Parameters are validated before any computations.
"""
from __future__ import annotations
from dataclasses import dataclass
import numpy as np
import pandas as pd


@dataclass(frozen=True)
class IndicatorSettings:
    rsi_period: int = 14
    sma_fast: int = 20
    sma_slow: int = 50
    ema_period: int = 20
    macd_fast: int = 12
    macd_slow: int = 26
    macd_signal: int = 9
    bb_period: int = 20
    bb_std: float = 2.0
    atr_period: int = 14
    kdj_period: int = 9

    def __post_init__(self):
        for field in ('rsi_period','sma_fast','sma_slow','ema_period','macd_fast','macd_slow','macd_signal','bb_period','atr_period','kdj_period'):
            value = getattr(self, field)
            if type(value) is not int or not 2 <= value <= 250:
                raise ValueError(f'{field} must be an integer from 2 to 250.')
        if self.sma_fast >= self.sma_slow or self.macd_fast >= self.macd_slow:
            raise ValueError('Fast indicator period must be shorter than slow period.')
        if not 0.5 <= self.bb_std <= 4.0 or not np.isfinite(self.bb_std):
            raise ValueError('Bollinger width must be between 0.5 and 4.0.')


def wilder_rsi(close: pd.Series, period: int = 14) -> pd.Series:
    """Wilder RSI: initial simple mean then Wilder smoothing; flat prices -> 50."""
    if not isinstance(period, int) or not 2 <= period <= 250:
        raise ValueError('RSI period must be from 2 to 250')
    close = pd.to_numeric(close, errors='coerce').astype(float)
    result = pd.Series(np.nan, index=close.index, dtype=float)
    if len(close) <= period:
        return result
    diff = close.diff()
    gains = diff.clip(lower=0)
    losses = -diff.clip(upper=0)
    avg_gain = float(gains.iloc[1:period + 1].mean())
    avg_loss = float(losses.iloc[1:period + 1].mean())
    for i in range(period, len(close)):
        if i > period:
            avg_gain = (avg_gain * (period - 1) + float(gains.iloc[i])) / period
            avg_loss = (avg_loss * (period - 1) + float(losses.iloc[i])) / period
        result.iloc[i] = (50.0 if avg_gain == avg_loss == 0 else
                          100.0 if avg_loss == 0 else
                          100 - 100 / (1 + avg_gain / avg_loss))
    return result


def calculate_indicators(prices: pd.DataFrame, settings: IndicatorSettings | None = None) -> pd.DataFrame:
    p = settings or IndicatorSettings()
    if prices.empty or 'Close' not in prices:
        raise ValueError('Daily Close series required for indicators.')
    frame = prices.copy()
    close = pd.to_numeric(frame['Close'], errors='coerce').astype(float)
    frame['SMA_fast'] = close.rolling(p.sma_fast, min_periods=p.sma_fast).mean()
    frame['SMA_slow'] = close.rolling(p.sma_slow, min_periods=p.sma_slow).mean()
    frame['EMA'] = close.ewm(span=p.ema_period, adjust=False, min_periods=p.ema_period).mean()
    frame['RSI'] = wilder_rsi(close, p.rsi_period)
    ema_fast = close.ewm(span=p.macd_fast, adjust=False, min_periods=p.macd_slow).mean()
    ema_slow = close.ewm(span=p.macd_slow, adjust=False, min_periods=p.macd_slow).mean()
    frame['MACD'] = ema_fast - ema_slow
    frame['MACD_signal'] = frame['MACD'].ewm(span=p.macd_signal, adjust=False, min_periods=p.macd_signal).mean()
    frame['MACD_hist'] = frame['MACD'] - frame['MACD_signal']
    ma = close.rolling(p.bb_period, min_periods=p.bb_period).mean()
    sigma = close.rolling(p.bb_period, min_periods=p.bb_period).std(ddof=0)
    frame['BB_mid'], frame['BB_upper'], frame['BB_lower'] = ma, ma + p.bb_std * sigma, ma - p.bb_std * sigma
    if {'High', 'Low', 'Close'} <= set(frame.columns):
        high, low = (pd.to_numeric(frame[c], errors='coerce') for c in ('High', 'Low'))
        previous_close = close.shift(1)
        tr = pd.concat([(high-low).abs(), (high-previous_close).abs(), (low-previous_close).abs()], axis=1).max(axis=1)
        frame['ATR'] = tr.ewm(alpha=1/p.atr_period, adjust=False, min_periods=p.atr_period).mean()
        low_min = low.rolling(p.kdj_period, min_periods=p.kdj_period).min()
        high_max = high.rolling(p.kdj_period, min_periods=p.kdj_period).max()
        rsv = ((close - low_min) / (high_max - low_min).replace(0, np.nan) * 100).clip(0, 100)
        frame['K'] = rsv.ewm(alpha=1/3, adjust=False, min_periods=1).mean()
        frame['D'] = frame['K'].ewm(alpha=1/3, adjust=False, min_periods=1).mean()
        frame['J'] = 3 * frame['K'] - 2 * frame['D']
    else:
        for col in ('ATR', 'K', 'D', 'J'):
            frame[col] = np.nan
    frame['DailyReturn'] = close.pct_change(fill_method=None) * 100
    # Backward-compatible names for existing tests/callers (always match actual settings).
    frame['SMA20'],frame['SMA50'],frame['RSI14'] = frame['SMA_fast'],frame['SMA_slow'],frame['RSI']
    return frame


def analyze(prices: pd.DataFrame, settings: IndicatorSettings | None = None):
    """Return (daily frame, descriptive trend category, auditable facts)."""
    p = settings or IndicatorSettings()
    frame = calculate_indicators(prices, p)
    last = frame.iloc[-1]
    required = [last[col] for col in ('Close','SMA_fast','SMA_slow','RSI')]
    if not all(pd.notna(x) and np.isfinite(float(x)) for x in required):
        return frame, 'UNAVAILABLE', [f'Insufficient history: SMA({p.sma_slow}) and RSI({p.rsi_period}) need warm-up bars.']
    price, fast, slow, rsi = (float(x) for x in required)
    reasons = [f'Close {price:.2f}; SMA({p.sma_fast}) {fast:.2f}; SMA({p.sma_slow}) {slow:.2f}.',
               f'RSI({p.rsi_period}) {rsi:.1f}; MACD({p.macd_fast},{p.macd_slow},{p.macd_signal}) {last["MACD"]:.3f}.']
    if price > fast > slow and 50 <= rsi < 70:
        return frame, 'BULLISH', reasons + ['Positive trend alignment; not a prediction or a trade signal.']
    if price < fast < slow and 30 < rsi < 50:
        return frame, 'BEARISH', reasons + ['Negative trend alignment; not a prediction or a trade signal.']
    return frame, 'MIXED', reasons + ['Indicators disagree or do not satisfy a directional rule.']
