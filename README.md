# CRYPTO BOT PRO

Android dashboard for Binance Spot public market data. The app is analysis-only: it does not submit, cancel, or manage live exchange orders and does not need a Binance API key.

## Included modules

- `main.py`: Kivy Android app, live selected-pair view, automatic active USDT Spot pair list, one-minute market refresh, BUY confidence filter, and early-momentum scanner.
- `indicators.py`: EMA20/EMA50, RSI(14), MACD confirmation, volume confirmation, and transparent 0–100 confluence score.
- `pump_scanner.py`: scans liquid Binance USDT Spot pairs for 5-minute volume expansion, positive price movement, taker-buy flow, and candle close strength.
- `paper_bot.py`: separate command-line demo/paper strategy with BTC daily trend filter, multi-timeframe checks, simulated position sizing, stop-loss and take-profit. It does not place exchange orders.
- `wallet_dashboard.py`: displays the demo wallet balance and open demo positions.
- `demo_positions.json`: local demo-position store.
- `buildozer.spec` and `.github/workflows/build-apk.yml`: Android packaging configuration and GitHub Actions APK build.
- `docs/index.html`: browser-based live Spot signal board.

## Build the Android APK

1. Open the repository's **Actions** tab.
2. Select **Build CRYPTO BOT PRO APK**.
3. Open the latest successful run.
4. Download the **CRYPTO-BOT-PRO-APK** artifact and extract the APK.

A push to the `main` branch also starts an APK build automatically.

## Run the command-line demo tools

Install Python 3 and the dependencies used by the Android project:

```bash
python -m pip install certifi
python paper_bot.py
python wallet_dashboard.py
```

The demo bot writes simulated positions to `demo_positions.json`. It is separate from the Android dashboard.

## Signals and risk

A BUY score is an indicator confluence score, not a probability or profit guarantee. Early-pump alerts are observations of current market activity, not predictions that a coin will pump. Confirm candle closes, liquidity, spreads, and market structure independently. Use a stop-loss and limit risk to a small fraction of account equity.

## Network and security

The app uses Binance public Spot endpoints over HTTPS and verifies TLS certificates with the Mozilla CA bundle supplied by `certifi`. No API secret or private trading permission is required. Never put exchange API keys in source code or a public repository.


## Latest build verification

A new push to `main` triggers the Android APK workflow. Download the APK only from a completed successful Actions run; a running build is not a verified APK.
