"""Multi-factor spot BUY confidence engine.

Input candles must be chronological Binance-style dictionaries with
close/high/low/volume numeric values. Confidence is a confluence score,
not a probability or guarantee of profit.
"""

from math import isfinite


def _ema(values, period):
    if len(values) < period:
        return None
    alpha = 2.0 / (period + 1)
    result = sum(values[:period]) / period
    for value in values[period:]:
        result = value * alpha + result * (1 - alpha)
    return result


def _rsi(values, period=14):
    if len(values) <= period:
        return None
    gains = []
    losses = []
    for previous, current in zip(values[:-1], values[1:]):
        change = current - previous
        gains.append(max(change, 0.0))
        losses.append(max(-change, 0.0))
    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period
    for gain, loss in zip(gains[period:], losses[period:]):
        avg_gain = (avg_gain * (period - 1) + gain) / period
        avg_loss = (avg_loss * (period - 1) + loss) / period
    if avg_loss == 0:
        return 100.0 if avg_gain > 0 else 50.0
    rs = avg_gain / avg_loss
    return 100.0 - (100.0 / (1.0 + rs))


def analyze_buy_signal(candles, minimum_score=80):
    """Return a transparent 0-100 confluence score and BUY/WAIT decision."""
    if minimum_score not in (80, 100):
        raise ValueError("minimum_score must be 80 or 100")
    if not candles or len(candles) < 60:
        return {
            "score": 0, "decision": "WAIT",
            "reason": "At least 60 valid candles are required",
            "checks": {}, "indicators": {},
        }

    try:
        closes = [float(c["close"]) for c in candles]
        volumes = [float(c["volume"]) for c in candles]
        if not all(isfinite(x) and x > 0 for x in closes + volumes):
            raise ValueError("non-finite or non-positive candle data")
    except (KeyError, TypeError, ValueError):
        return {
            "score": 0, "decision": "WAIT",
            "reason": "Invalid OHLCV candle data",
            "checks": {}, "indicators": {},
        }

    ema20 = _ema(closes, 20)
    ema50 = _ema(closes, 50)
    rsi14 = _rsi(closes, 14)

    fast = _ema(closes, 12)
    slow = _ema(closes, 26)
    macd_series = []
    for end in range(26, len(closes) + 1):
        segment = closes[:end]
        macd_series.append(_ema(segment, 12) - _ema(segment, 26))
    signal = _ema(macd_series, 9) if len(macd_series) >= 9 else None
    macd = fast - slow

    avg_volume = sum(volumes[-21:-1]) / 20
    last_volume = volumes[-1]

    checks = {
        "EMA20 above EMA50": ema20 > ema50,
        "Price above EMA20": closes[-1] > ema20,
        "RSI healthy (50-68)": 50 <= rsi14 <= 68,
        "MACD above signal": signal is not None and macd > signal,
        "Volume confirmation (>= 1.2x)": avg_volume > 0 and last_volume >= 1.2 * avg_volume,
    }
    score = sum(20 for passed in checks.values() if passed)
    decision = "BUY" if score >= minimum_score else "WAIT"

    return {
        "score": score,
        "decision": decision,
        "reason": "All required confirmations passed" if decision == "BUY"
                  else "Wait: fewer than the required confirmations",
        "checks": checks,
        "indicators": {
            "price": closes[-1],
            "ema20": ema20,
            "ema50": ema50,
            "rsi14": rsi14,
            "macd": macd,
            "macd_signal": signal,
            "volume_ratio": last_volume / avg_volume if avg_volume else 0,
        },
    }
