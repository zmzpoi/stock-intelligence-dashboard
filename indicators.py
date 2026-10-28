"""Transparent deterministic indicators; never sends trades or predicts returns."""
import numpy as np
import pandas as pd


def wilder_rsi(close: pd.Series, period: int = 14) -> pd.Series:
    result = pd.Series(np.nan, index=close.index, dtype=float)
    if len(close) <= period:
        return result
    changes = close.astype(float).diff()
    gains = changes.clip(lower=0)
    losses = -changes.clip(upper=0)
    avg_gain = float(gains.iloc[1:period + 1].mean())
    avg_loss = float(losses.iloc[1:period + 1].mean())
    for i in range(period, len(close)):
        if i > period:
            avg_gain = (avg_gain * (period - 1) + float(gains.iloc[i])) / period
            avg_loss = (avg_loss * (period - 1) + float(losses.iloc[i])) / period
        result.iloc[i] = 50.0 if avg_gain == avg_loss == 0 else 100.0 if avg_loss == 0 else 100 - 100 / (1 + avg_gain / avg_loss)
    return result


def analyze(prices: pd.DataFrame):
    frame = prices.copy()
    close = pd.to_numeric(frame['Close'], errors='coerce')
    frame['SMA20'] = close.rolling(20, min_periods=20).mean()
    frame['SMA50'] = close.rolling(50, min_periods=50).mean()
    frame['RSI14'] = wilder_rsi(close)
    fast = close.ewm(span=12, adjust=False).mean()
    slow = close.ewm(span=26, adjust=False).mean()
    frame['MACD'] = fast - slow
    frame['MACD_signal'] = frame['MACD'].ewm(span=9, adjust=False).mean()
    frame['MACD_hist'] = frame['MACD'] - frame['MACD_signal']
    frame['BB_upper'] = frame['SMA20'] + 2 * close.rolling(20).std()
    frame['BB_lower'] = frame['SMA20'] - 2 * close.rolling(20).std()
    frame['DailyReturn'] = close.pct_change(fill_method=None) * 100
    last = frame.iloc[-1]
    needed = last[['Close', 'SMA20', 'SMA50', 'RSI14']].to_numpy(dtype=float)
    if not np.isfinite(needed).all():
        return frame, 'UNAVAILABLE', ['At least 50 valid daily records are required.']
    price, s20, s50, rsi = (float(last[x]) for x in ('Close', 'SMA20', 'SMA50', 'RSI14'))
    reasons = [
        f'Close {price:.2f} vs SMA20 {s20:.2f} and SMA50 {s50:.2f}.',
        f'RSI(14) {rsi:.1f}/100; MACD {float(last["MACD"]):+.3f}.',
    ]
    if price > s20 > s50 and 50 <= rsi < 70:
        return frame, 'BUY', reasons + ['Bullish alignment under the fixed research rule.']
    if price < s20 < s50 and 30 < rsi < 50:
        return frame, 'SELL', reasons + ['Bearish alignment under the fixed research rule.']
    return frame, 'HOLD', reasons + ['No complete directional rule was satisfied.']
