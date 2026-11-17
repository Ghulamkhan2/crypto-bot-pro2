
import json
import os
import urllib.request
import ssl
import certifi
from datetime import datetime, timezone

COINS = ["ETHUSDT", "BNBUSDT", "SOLUSDT", "LINKUSDT", "TRXUSDT"]

POSITION_SIZE = 20
MAX_POSITIONS = 2
STOP_LOSS = 0.03
TAKE_PROFIT = 0.05
FILE = "demo_positions.json"
SSL_CONTEXT = ssl.create_default_context(cafile=certifi.where())


def api_data(url):
    req = urllib.request.Request(
        url, headers={"User-Agent": "Mozilla/5.0"}
    )
    with urllib.request.urlopen(req, timeout=20, context=SSL_CONTEXT) as r:
        return json.loads(r.read().decode())


def get_price(symbol):
    url = (
        "https://api.binance.com/api/v3/ticker/price"
        f"?symbol={symbol}"
    )
    return float(api_data(url)["price"])


def get_signal(symbol, interval):
    url = (
        "https://api.binance.com/api/v3/klines"
        f"?symbol={symbol}&interval={interval}&limit=60"
    )

    candles = api_data(url)
    closes = [float(c[4]) for c in candles[:-1]]

    def ema(values, period):
        alpha = 2 / (period + 1)
        result = values[0]
        for value in values[1:]:
            result = value * alpha + result * (1 - alpha)
        return result

    ema20 = ema(closes, 20)
    ema50 = ema(closes, 50)
    close = closes[-1]

    if close > ema20 and ema20 > ema50:
        signal = "BULLISH"
    elif close < ema20 and ema20 < ema50:
        signal = "BEARISH"
    else:
        signal = "WAIT"

    return {
        "signal": signal,
        "close": close,
        "ema20": ema20,
        "ema50": ema50
    }


def load_positions():
    if os.path.exists(FILE):
        with open(FILE, "r") as f:
            return json.load(f)
    return {}


def save_positions(positions):
    with open(FILE, "w") as f:
        json.dump(positions, f, indent=4)


def main():
    positions = load_positions()

    print("\n===== DEMO PAPER TRADING =====")
    print("Time:", datetime.now(timezone.utc).isoformat())

    try:
        btc = get_signal("BTCUSDT", "1d")
        print("\nBTC DAILY:", btc["signal"])
        print("BTC Close:", btc["close"])
    except Exception as e:
        print("BTC DATA ERROR:", e)
        print("NEW ENTRIES BLOCKED")
        return

    # Check existing positions
    for coin in list(positions.keys()):
        try:
            price = get_price(coin)
            entry = positions[coin]["entry"]
            qty = positions[coin].get(
                "qty",
                positions[coin].get("investment", POSITION_SIZE) / entry
            )

            sl = entry * (1 - STOP_LOSS)
            tp = entry * (1 + TAKE_PROFIT)

            print("\nPOSITION:", coin)
            print("Entry:", entry)
            print("Current:", price)
            print("SL:", round(sl, 6))
            print("TP:", round(tp, 6))

            if price <= sl or price >= tp:
                result = (price - entry) * qty
                print("DEMO EXIT:", coin)
                print("Estimated P/L:", round(result, 4), "USDT")
                del positions[coin]

        except Exception as e:
            print("Position error:", coin, e)

    # BTC daily filter
    btc_bullish = btc["signal"] == "BULLISH"

    if not btc_bullish:
        print("\\nBTC FILTER:", btc["signal"])
        print("NEW BUY ENTRIES BLOCKED")

    for coin in COINS:
        if coin in positions:
            continue

        try:
            price = get_price(coin)
            four_hour = get_signal(coin, "4h")
            one_hour = get_signal(coin, "1h")
            fifteen_minute = get_signal(coin, "15m")
            score = 0
            for tf in (four_hour, one_hour):
                if tf["close"] > tf["ema20"]:
                    score += 25
                if tf["ema20"] > tf["ema50"]:
                    score += 25


            print("\\n====================")
            print("COIN:", coin)
            print("Price:", price)
            print("4H:", four_hour["signal"])
            print("1H:", one_hour["signal"])
            print("15M:", fifteen_minute["signal"])
            print("4H EMA20:", round(four_hour["ema20"], 6))
            print("4H EMA50:", round(four_hour["ema50"], 6))
            print("1H EMA20:", round(one_hour["ema20"], 6))
            print("1H EMA50:", round(one_hour["ema50"], 6))
            print("BULLISH SCORE:", score, "/ 100")
            if score == 100:
                trend_status = "STRONG BULLISH"
            elif score >= 75:
                trend_status = "POTENTIAL BULLISH"
            elif score <= 25:
                trend_status = "BEARISH"
            else:
                trend_status = "WAIT"

            if score == 100 and btc_bullish:
                decision = "BUY"
            elif score <= 25:
                decision = "SELL SIGNAL - NO AUTO SELL"
            else:
                decision = "WAIT"

            print("TREND:", trend_status)
            print("FINAL DECISION:", decision)



            if not btc_bullish:
                print("WAIT: BTC FILTER BLOCKS BUY")

            elif len(positions) >= MAX_POSITIONS:
                print("WAIT: Maximum positions reached")

            elif (
                four_hour["signal"] == "BULLISH"
                and one_hour["signal"] == "BULLISH"
                and fifteen_minute["signal"] == "BULLISH"
            ):
                qty = POSITION_SIZE / price

                positions[coin] = {
                    "entry": price,
                    "qty": qty,
                    "investment": POSITION_SIZE,
                    "time": datetime.now(
                        timezone.utc
                    ).isoformat()
                }

                print("DEMO BUY:", coin)
                print("Investment:", POSITION_SIZE, "USDT")
                print("Quantity:", qty)
                print("Stop Loss:", price * (1 - STOP_LOSS))
                print("Take Profit:", price * (1 + TAKE_PROFIT))

            else:
                print("NO ENTRY: Signals not confirmed")

        except Exception as e:
            print("Scan error:", coin, e)

    save_positions(positions)

    print("\n====================")
    print("OPEN DEMO POSITIONS:", len(positions))
    print("PAPER TRADING CHECK COMPLETE")


if __name__ == "__main__":
    main()
