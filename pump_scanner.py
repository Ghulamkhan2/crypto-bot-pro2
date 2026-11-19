"""Fast early-momentum scanner for Binance Spot USDT markets.
Alerts flag unusual 5m activity; they do not predict or guarantee returns.
"""
import json
import ssl
import certifi
import time
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed

BASES = ("https://api.binance.com", "https://api1.binance.com", "https://api2.binance.com", "https://api3.binance.com")
SSL_CONTEXT = ssl.create_default_context(cafile=certifi.where())
MIN_QUOTE_VOLUME = 50000.0
MIN_5M_QUOTE_VOLUME = 10000.0
MAX_MARKETS = 60
MAX_24H_CHANGE_FOR_ALERT = 5.0
ALERT_SCORE = 60
MAX_WORKERS = 8


def _get_json(path, params=None, timeout=7):
    query = urllib.parse.urlencode(params or {})
    last_error = None
    for base in BASES:
        request = urllib.request.Request(
            base + path + (("?" + query) if query else ""),
            headers={"User-Agent": "CryptoBotPro/2.1"}
        )
        try:
            with urllib.request.urlopen(request, timeout=timeout, context=SSL_CONTEXT) as response:
                return json.loads(response.read().decode("utf-8"))
        except Exception as exc:
            last_error = exc
    raise RuntimeError("Binance API unavailable: {}".format(last_error))


def score_early_pump(klines):
    # Live candle creates an EARLY WATCH; closed candles create confirmation.
    if not klines or len(klines) < 22:
        return {"score": 0, "alert": False, "watch": False, "signals": [], "reason": "Not enough 5-minute candles"}
    try:
        closed = [{"open":float(k[1]),"high":float(k[2]),"low":float(k[3]),"close":float(k[4]),"quote":float(k[7]),"buy_quote":float(k[10])} for k in klines[:-1][-21:]]
        k=klines[-1]
        live={"open":float(k[1]),"high":float(k[2]),"low":float(k[3]),"close":float(k[4]),"quote":float(k[7]),"buy_quote":float(k[10])}
        if len(closed)<21 or any(c["close"]<=0 or c["quote"]<0 for c in closed) or live["close"]<=0: raise ValueError("invalid values")
    except (IndexError,TypeError,ValueError):
        return {"score":0,"alert":False,"watch":False,"signals":[],"reason":"Invalid market data"}
    avg_live=sum(c["quote"] for c in closed[-20:])/20
    live_ratio=live["quote"]/avg_live if avg_live else 0
    live_buy=live["buy_quote"]/live["quote"] if live["quote"] else 0
    live_change=(live["close"]/live["open"]-1)*100
    live_range=live["high"]-live["low"]
    live_close_pos=(live["close"]-live["low"])/live_range if live_range>0 else 0
    watch=(live["quote"]>=MIN_5M_QUOTE_VOLUME and live_ratio>=3.0 and live_buy>=0.65 and 0.0<=live_change<=1.2 and live_close_pos>=0.65)
    last=closed[-1]; previous=closed[-21:-1]
    avg_closed=sum(c["quote"] for c in previous)/len(previous) if previous else 0
    volume_ratio=last["quote"]/avg_closed if avg_closed else 0
    price_change=(last["close"]/last["open"]-1)*100
    buy_ratio=last["buy_quote"]/last["quote"] if last["quote"] else 0
    candle_range=last["high"]-last["low"]
    close_position=(last["close"]-last["low"])/candle_range if candle_range>0 else 0
    checks=[
        (last["quote"]>=MIN_5M_QUOTE_VOLUME and volume_ratio>=3.0,"Closed 5m volume >= 10,000 USDT and >= 3.0x average"),
        (0.2<=price_change<=2.0,"Closed 5m price rising 0.2%-2.0%"),
        (buy_ratio>=0.65,"Aggressive buying >= 65%"),
        (close_position>=0.75,"Closed candle finishes in top 25% of range"),
    ]
    score=sum(25 for passed,_ in checks if passed); confirmed=all(passed for passed,_ in checks)
    return {
        "score":score,"alert":confirmed,"watch":watch and not confirmed,
        "signals":[name for passed,name in checks if passed],
        "volume_ratio":round(volume_ratio,2),"volume_5m_usdt":round(last["quote"],2),
        "price_change":round(price_change,2),"buy_ratio":round(buy_ratio*100,1),
        "watch_volume_ratio":round(live_ratio,2),"watch_volume_5m_usdt":round(live["quote"],2),
        "watch_buy_ratio":round(live_buy*100,1),"watch_price_change":round(live_change,2),
        "reason":"Confirmed on closed 5m candle" if confirmed else ("Live 5m early watch only" if watch else "No qualified early watch or confirmed setup"),
        "max_24h_change_for_alert": MAX_24H_CHANGE_FOR_ALERT,
    }

def _scan_one(symbol, quote_volume, day_change):
    klines = _get_json("/api/v3/klines", {
        "symbol": symbol, "interval": "5m", "limit": 22
    })
    result = score_early_pump(klines)
    result.update({
        "symbol": symbol,
        "quote_volume_24h": round(quote_volume, 0),
        "change_24h": round(day_change, 2),
    })
    return result


def scan_binance_spot(on_progress=None):
    """Scan up to 40 liquid USDT pairs concurrently and report progress."""
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
        if quote_volume >= MIN_QUOTE_VOLUME and day_change <= MAX_24H_CHANGE_FOR_ALERT:
            candidates.append((quote_volume, symbol, day_change))
    candidates.sort(reverse=True)
    selected = candidates[:MAX_MARKETS]
    results = []
    total = len(selected)
    if on_progress:
        on_progress(0, total, "starting")
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        futures = {
            pool.submit(_scan_one, symbol, quote_volume, day_change): symbol
            for quote_volume, symbol, day_change in selected
        }
        done = 0
        for future in as_completed(futures):
            symbol = futures[future]
            try:
                results.append(future.result())
            except Exception as exc:
                results.append({
                    "symbol": symbol, "score": 0, "alert": False,
                    "reason": "Data unavailable: {}".format(str(exc)[:65])
                })
            done += 1
            if on_progress:
                on_progress(done, total, symbol)
    results.sort(key=lambda row: row.get("score", 0), reverse=True)
    return results
