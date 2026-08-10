from __future__ import annotations
from typing import List, Optional


def sma(values: List[float], period: int) -> Optional[float]:
    if len(values) < period or period <= 0:
        return None
    return sum(values[-period:]) / period


def ema(values: List[float], period: int) -> Optional[float]:
    if len(values) < period or period <= 0:
        return None
    k = 2 / (period + 1)
    result = sum(values[:period]) / period
    for price in values[period:]:
        result = price * k + result * (1 - k)
    return result


def rsi(values: List[float], period: int = 14) -> Optional[float]:
    if len(values) <= period:
        return None
    gains, losses = [], []
    for i in range(1, len(values)):
        diff = values[i] - values[i - 1]
        gains.append(max(diff, 0))
        losses.append(abs(min(diff, 0)))
    avg_gain = sum(gains[-period:]) / period
    avg_loss = sum(losses[-period:]) / period
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def macd(values: List[float], fast: int = 12, slow: int = 26, signal: int = 9):
    if len(values) < slow + signal:
        return None
    fast_ema = ema(values, fast)
    slow_ema = ema(values, slow)
    if fast_ema is None or slow_ema is None:
        return None
    line = fast_ema - slow_ema
    # Lightweight signal approximation for fast M1 server-side scoring.
    signal_line = ema([line] * signal, signal) or 0.0
    return {"macd": line, "signal": signal_line, "hist": line - signal_line}


def bollinger(values: List[float], period: int = 20, mult: float = 2.0):
    if len(values) < period:
        return None
    window = values[-period:]
    mid = sum(window) / period
    var = sum((x - mid) ** 2 for x in window) / period
    dev = var ** 0.5
    return {"lower": mid - mult * dev, "middle": mid, "upper": mid + mult * dev, "width": (2 * mult * dev)}


def stochastic(highs: List[float], lows: List[float], closes: List[float], period: int = 14):
    if len(closes) < period or len(highs) < period or len(lows) < period:
        return None
    hi = max(highs[-period:])
    lo = min(lows[-period:])
    if hi == lo:
        return 50.0
    return ((closes[-1] - lo) / (hi - lo)) * 100


def atr(highs: List[float], lows: List[float], closes: List[float], period: int = 14):
    if len(closes) <= period or len(highs) <= period or len(lows) <= period:
        return None
    trs = []
    for i in range(1, len(closes)):
        trs.append(max(highs[i] - lows[i], abs(highs[i] - closes[i - 1]), abs(lows[i] - closes[i - 1])))
    return sum(trs[-period:]) / period


def support_resistance(highs: List[float], lows: List[float], closes: List[float], lookback: int = 30):
    """Nearest support/resistance zones for M1 reversal/continuation scoring."""
    if len(closes) < 8:
        return None
    h = highs[-lookback:]
    l = lows[-lookback:]
    c = closes[-lookback:]
    price = closes[-1]
    support = min([x for x in l if x <= price] or l)
    resistance = max([x for x in h if x >= price] or h)
    recent_low = min(l[-8:])
    recent_high = max(h[-8:])
    swing_low = min(l)
    swing_high = max(h)
    rng = max(max(h) - min(l), 1e-9)
    pos = (price - min(l)) / rng
    return {
        "support": support,
        "resistance": resistance,
        "recent_low": recent_low,
        "recent_high": recent_high,
        "swing_low": swing_low,
        "swing_high": swing_high,
        "range": rng,
        "position": pos,
        "dist_support": abs(price - support) / rng,
        "dist_resistance": abs(resistance - price) / rng,
    }


def candle_strength(candle: dict):
    o = float(candle.get("open", candle.get("o", candle.get("close", 0))) or 0)
    h = float(candle.get("high", candle.get("max", candle.get("close", o))) or o)
    l = float(candle.get("low", candle.get("min", candle.get("close", o))) or o)
    c = float(candle.get("close", candle.get("c", o)) or o)
    rng = max(h - l, 1e-9)
    body = abs(c - o)
    upper = h - max(o, c)
    lower = min(o, c) - l
    return {"bull": c > o, "bear": c < o, "body_ratio": body / rng, "upper_wick": upper / rng, "lower_wick": lower / rng}
