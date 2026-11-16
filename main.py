"""CRYPTO BOT PRO - Binance Spot live dashboard; public data only, no order execution."""
import json
import threading
import urllib.parse
import urllib.request
from kivy.app import App
from kivy.clock import Clock
from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.spinner import Spinner
from kivy.uix.scrollview import ScrollView
from indicators import analyze_buy_signal
from pump_scanner import scan_binance_spot

BASE = "https://api.binance.com"
PAIRS = ["BTCUSDT","ETHUSDT","BNBUSDT","SOLUSDT","XRPUSDT","ADAUSDT","DOGEUSDT","TRXUSDT","AVAXUSDT","LINKUSDT","DOTUSDT","SUIUSDT","LTCUSDT","BCHUSDT","TONUSDT","PEPEUSDT","SHIBUSDT","WIFUSDT","BONKUSDT","FLOKIUSDT","NEARUSDT","APTUSDT","OPUSDT","ARBUSDT","INJUSDT","SEIUSDT","TIAUSDT","ATOMUSDT","UNIUSDT","AAVEUSDT"]

def api(path, params=None):
    query = urllib.parse.urlencode(params or {})
    req = urllib.request.Request(BASE + path + (("?" + query) if query else ""), headers={"User-Agent":"CryptoBotPro/2.0"})
    with urllib.request.urlopen(req, timeout=12) as response:
        return json.loads(response.read().decode("utf-8"))

def market_data(symbol):
    ticker = api("/api/v3/ticker/24hr", {"symbol":symbol})
    raw = api("/api/v3/klines", {"symbol":symbol,"interval":"1h","limit":100})
    candles = [{"open":float(k[1]),"high":float(k[2]),"low":float(k[3]),"close":float(k[4]),"volume":float(k[5])} for k in raw]
    return ticker, candles

class CryptoBotApp(App):
    def build(self):
        self.title = "CRYPTO BOT PRO"
        self.minimum_buy_score = 80
        self.busy = False
        self.scan_running = False
        root = BoxLayout(orientation="vertical", padding=dp(10), spacing=dp(6))
        root.add_widget(Label(text="[b]CRYPTO BOT PRO[/b]\nBINANCE SPOT LIVE DASHBOARD", markup=True, font_size="21sp", size_hint_y=None, height=dp(62)))
        scroll = ScrollView(do_scroll_x=False)
        body = BoxLayout(orientation="vertical", spacing=dp(7), padding=(0,dp(4)), size_hint_y=None)
        body.bind(minimum_height=body.setter("height"))
        scroll.add_widget(body)
        root.add_widget(scroll)
        body.add_widget(self.heading("SELECT BINANCE USDT COIN"))
        self.pair = Spinner(text="BTCUSDT", values=tuple(PAIRS), size_hint_y=None, height=dp(48))
        self.pair.bind(text=lambda *_: self.refresh_market())
        body.add_widget(self.pair)
        buttons = BoxLayout(size_hint_y=None, height=dp(46), spacing=dp(6))
        refresh = Button(text="REFRESH LIVE DATA")
        refresh.bind(on_release=lambda *_: self.refresh_market())
        self.filter_btn = Button(text="BUY FILTER: 80%")
        self.filter_btn.bind(on_release=lambda *_: self.toggle_filter())
        buttons.add_widget(refresh); buttons.add_widget(self.filter_btn); body.add_widget(buttons)
        self.price = self.info("Live price: loading...")
        self.day = self.info("24h change: -- | 24h volume: --")
        self.signal = self.info("SIGNAL: WAIT")
        self.score = self.info("BUY CONFIDENCE: --")
        self.indicators = self.info("RSI: -- | EMA20: -- | EMA50: --")
        self.checks = self.info("Technical confirmations will appear here.")
        for widget in (self.price,self.day,self.signal,self.score,self.indicators,self.checks): body.add_widget(widget)
        body.add_widget(self.heading("MEME COIN EARLY PUMP SCANNER"))
        scan = Button(text="SCAN BINANCE SPOT COINS NOW", size_hint_y=None, height=dp(50))
        scan.bind(on_release=lambda *_: self.start_scan()); body.add_widget(scan)
        self.scan_status = self.info("Scanner ready. Tap to scan live 5-minute market activity.")
        self.scan_results = self.info("Pump alerts will appear here.")
        body.add_widget(self.scan_status); body.add_widget(self.scan_results)
        body.add_widget(self.info("Binance public market data only. BUY/SELL/WAIT are analysis signals; this app does not place orders."))
        Clock.schedule_once(lambda dt: self.refresh_market(), 0.5)
        return root

    def heading(self, value):
        return Label(text="[b]"+value+"[/b]", markup=True, font_size="16sp", size_hint_y=None, height=dp(35))

    def info(self, value):
        label = Label(text=value, font_size="13sp", halign="left", valign="middle", size_hint_y=None, height=dp(52))
        label.bind(width=lambda obj,w: setattr(obj,"text_size",(w,None)), texture_size=lambda obj,s: setattr(obj,"height",max(dp(42),s[1]+dp(10))))
        return label

    def toggle_filter(self):
        self.minimum_buy_score = 100 if self.minimum_buy_score == 80 else 80
        self.filter_btn.text = "BUY FILTER: {}%".format(self.minimum_buy_score)
        self.refresh_market()

    def refresh_market(self):
        if self.busy: return
        self.busy = True
        symbol = self.pair.text
        self.price.text = "Loading {} from Binance...".format(symbol)
        threading.Thread(target=self.market_worker,args=(symbol,),daemon=True).start()

    def market_worker(self,symbol):
        try:
            ticker,candles = market_data(symbol)
            result = analyze_buy_signal(candles,self.minimum_buy_score)
            Clock.schedule_once(lambda dt:self.show_market(symbol,ticker,result),0)
        except Exception as exc:
            message=str(exc)[:150]
            Clock.schedule_once(lambda dt:self.market_error(message),0)

    def market_error(self,message):
        self.busy=False
        self.price.text="Binance connection error: "+message
        self.signal.text="SIGNAL: WAIT - refresh when connected"

    def show_market(self,symbol,ticker,result):
        self.busy=False
        price=float(ticker.get("lastPrice",0))
        change=float(ticker.get("priceChangePercent",0))
        volume=float(ticker.get("quoteVolume",0))
        self.price.text="{} LIVE PRICE: {}".format(symbol,format(price,".8g"))
        self.day.text="24h change: {:+.2f}% | 24h quote volume: {:,.0f} USDT".format(change,volume)
        ind=result.get("indicators",{})
        decision=result.get("decision","WAIT")
        if decision=="WAIT" and ind and ind.get("price",0)<ind.get("ema20",0)<ind.get("ema50",0) and ind.get("rsi14",50)<45:
            decision="SELL / EXIT WARNING"
        self.signal.text="SIGNAL: "+decision
        self.score.text="BUY CONFIDENCE: {}% | Required: {}%".format(result.get("score",0),self.minimum_buy_score)
        if ind:
            self.indicators.text="RSI(14): {:.1f} | EMA20: {} | EMA50: {}".format(ind["rsi14"],format(ind["ema20"],".8g"),format(ind["ema50"],".8g"))
        else:
            self.indicators.text=result.get("reason","Indicators unavailable")
        checks=result.get("checks",{})
        self.checks.text="\n".join(("PASS  " if ok else "WAIT  ")+name for name,ok in checks.items()) or result.get("reason","Waiting for data")

    def start_scan(self):
        if self.scan_running:
            self.scan_status.text="Scan already running..."; return
        self.scan_running=True
        self.scan_status.text="Connecting to Binance; scanning liquid USDT pairs..."
        self.scan_results.text="Checking volume surge, 5m momentum and aggressive buying..."
        threading.Thread(target=self.scan_worker,daemon=True).start()

    def scan_worker(self):
        try:
            results=scan_binance_spot()
            Clock.schedule_once(lambda dt:self.show_scan(results),0)
        except Exception as exc:
            message=str(exc)[:150]
            Clock.schedule_once(lambda dt:self.scan_error(message),0)

    def scan_error(self,message):
        self.scan_running=False
        self.scan_status.text="Scanner error: "+message

    def show_scan(self,results):
        self.scan_running=False
        alerts=[x for x in results if x.get("alert")]
        self.scan_status.text="{} pairs checked | {} early alerts".format(len(results),len(alerts))
        if not results:
            self.scan_results.text="No eligible USDT pairs returned."; return
        rows=[]
        for item in results[:15]:
            rows.append("{} | {} | Score {}%\n5m volume {:.2f}x | price {:+.2f}% | buyers {:.1f}%".format(item.get("symbol","?"),"EARLY ALERT" if item.get("alert") else "WAIT",item.get("score",0),item.get("volume_ratio",0),item.get("price_change",0),item.get("buy_ratio",0)))
        self.scan_results.text="\n\n".join(rows)

CryptoBotApp().run()
