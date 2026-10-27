"""Deterministic indicators; no model calls or trading execution."""
import numpy as np
import pandas as pd


def wilder_rsi(close: pd.Series, period: int = 14) -> pd.Series:
    """Seed with the first period simple averages, then Wilder smoothing."""
    result = pd.Series(np.nan, index=close.index, dtype=float)
    if len(close) <= period:
        return result
    change = close.diff()
    gains = change.clip(lower=0)
    losses = -change.clip(upper=0)
    gain = float(gains.iloc[1:period + 1].mean())
    loss = float(losses.iloc[1:period + 1].mean())
    for i in range(period, len(close)):
        if i > period:
            gain = (gain * (period - 1) + float(gains.iloc[i])) / period
            loss = (loss * (period - 1) + float(losses.iloc[i])) / period
        result.iloc[i] = (50.0 if gain == 0 else 100.0) if loss == 0 else 100 - 100 / (1 + gain / loss)
    return result


def analyze(prices: pd.DataFrame):
    frame = prices.copy()
    frame['SMA20'] = frame['Close'].rolling(20, min_periods=20).mean()
    frame['SMA50'] = frame['Close'].rolling(50, min_periods=50).mean()
    frame['RSI14'] = wilder_rsi(frame['Close'])
    last = frame.iloc[-1]
    if not np.isfinite(last[['Close', 'SMA20', 'SMA50', 'RSI14']].to_numpy(dtype=float)).all():
        return frame, 'UNAVAILABLE', ['At least 50 valid daily records are required.']
    price, short, long, rsi = (float(last[x]) for x in ['Close', 'SMA20', 'SMA50', 'RSI14'])
    reasons = [
        f'Price {price:.2f} is {"above" if price > short else "below" if price < short else "equal to"} SMA20 ({short:.2f}).',
        f'SMA20 is {"above" if short > long else "below" if short < long else "equal to"} SMA50 ({long:.2f}).',
        f'RSI14 is {rsi:.1f} on a 0–100 scale.',
    ]
    if price > short > long and 50 <= rsi < 70:
        return frame, 'BUY', reasons + ['Bullish alignment; RSI is in the configured 50–70 range.']
    if price < short < long and 30 < rsi < 50:
        return frame, 'SELL', reasons + ['Bearish alignment; RSI is in the configured 30–50 range.']
    return frame, 'HOLD', reasons + ['Neither complete BUY nor complete SELL condition is satisfied.']
