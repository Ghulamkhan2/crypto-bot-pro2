"""Early momentum scanner for Binance Spot USDT markets.

Alerts identify unusual pre-breakout activity; they do not predict or guarantee
a 2x/3x/4x move. Public market data only; this module never places orders.
"""
import json
import time
import urllib.parse
import urllib.request

BASE = "https://api.binance.com"
MIN_QUOTE_VOLUME = 100000.0
MAX_MARKETS = 25
ALERT_SCORE = 60


def _get_json(path, params=None, timeout=8):
    query = urllib.parse.urlencode(params or {})
    url = BASE + path + (("?" + query) if query else "")
    request = urllib.request.Request(
        url, headers={"User-Agent": "CryptoBotPro/1.0"}
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def score_early_pump(klines):
    """Score four early momentum signals from chronological 5m Binance klines."""
    if not klines or len(klines) < 22:
        return {"score": 0, "alert": False, "signals": [],
                "reason": "Not enough 5-minute candles"}

    try:
        # Binance kline indexes: close=4, quote volume=7, taker-buy quote=10.
        candles = [{
            "open": float(k[1]), "high": float(k[2]),
            "low": float(k[3]), "close": float(k[4]),
            "quote": float(k[7]), "buy_quote": float(k[10]),
        } for k in klines[-22:]]
        if any(c["close"] <= 0 or c["quote"] < 0 for c in candles):
            raise ValueError("invalid market values")
    except (IndexError, TypeError, ValueError):
        return {"score": 0, "alert": False, "signals": [],
                "reason": "Invalid market data"}

    last = candles[-1]
    previous = candles[-21:-1]
    avg_quote = sum(c["quote"] for c in previous) / len(previous)
    volume_ratio = last["quote"] / avg_quote if avg_quote else 0
    price_change = ((last["close"] / last["open"]) - 1) * 100
    buy_ratio = last["buy_quote"] / last["quote"] if last["quote"] else 0
    candle_range = last["high"] - last["low"]
    close_position = ((last["close"] - last["low"]) / candle_range
                      if candle_range > 0 else 0)

    checks = [
        (volume_ratio >= 2.0, "5m volume surge >= 2x"),
        (0.3 <= price_change <= 4.0, "5m price rising 0.3%-4%"),
        (buy_ratio >= 0.55, "Aggressive buying >= 55%"),
        (close_position >= 0.70, "Candle closes near its high"),
    ]
    score = sum(25 for passed, _ in checks if passed)
    return {
        "score": score,
        "alert": score >= ALERT_SCORE,
        "signals": [name for passed, name in checks if passed],
        "volume_ratio": round(volume_ratio, 2),
        "price_change": round(price_change, 2),
        "buy_ratio": round(buy_ratio * 100, 1),
        "reason": "Early momentum conditions detected" if score >= ALERT_SCORE
                  else "No early-pump alert",
    }


def scan_binance_spot():
    """Scan liquid Binance USDT spot pairs using public endpoints only."""
    tickers = _get_json("/api/v3/ticker/24hr")
    exchange = _get_json("/api/v3/exchangeInfo")
    allowed = {
        item["symbol"] for item in exchange.get("symbols", [])
        if item.get("status") == "TRADING"
        and item.get("quoteAsset") == "USDT"
        and item.get("isSpotTradingAllowed", True)
    }
    candidates = []
    for item in tickers:
        symbol = item.get("symbol", "")
        if symbol not in allowed or not symbol.endswith("USDT"):
            continue
        try:
            quote_volume = float(item.get("quoteVolume", 0))
            day_change = float(item.get("priceChangePercent", 0))
        except (TypeError, ValueError):
            continue
        # Exclude illiquid markets and tokens already showing an extreme daily run.
        if quote_volume >= MIN_QUOTE_VOLUME and day_change < 35:
            candidates.append((quote_volume, symbol, day_change))

    candidates.sort(reverse=True)
    results = []
    for quote_volume, symbol, day_change in candidates[:MAX_MARKETS]:
        try:
            klines = _get_json("/api/v3/klines", {
                "symbol": symbol, "interval": "5m", "limit": 22
            })
            result = score_early_pump(klines)
            result.update({
                "symbol": symbol,
                "quote_volume_24h": round(quote_volume, 0),
                "change_24h": round(day_change, 2),
            })
            results.append(result)
        except Exception as exc:
            results.append({"symbol": symbol, "score": 0, "alert": False,
                            "reason": "Market data unavailable: {}".format(str(exc)[:70])})
        time.sleep(0.08)
    results.sort(key=lambda row: row.get("score", 0), reverse=True)
    return results
