"""CRYPTO BOT PRO - Binance Spot live dashboard; public data only, no order execution."""
import json
import ssl
import certifi
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
from kivy.uix.widget import Widget
from kivy.core.window import Window
from kivy.graphics import Color, RoundedRectangle, Line, Rectangle
from indicators import analyze_buy_signal
from pump_scanner import scan_binance_spot

BASES = ("https://api.binance.com", "https://api1.binance.com", "https://api2.binance.com", "https://api3.binance.com")
# Use the maintained Mozilla CA bundle on Android; never disable TLS verification.
SSL_CONTEXT = ssl.create_default_context(cafile=certifi.where())
PAIRS = ["BTCUSDT","ETHUSDT","BNBUSDT","SOLUSDT","XRPUSDT","ADAUSDT","DOGEUSDT","TRXUSDT","AVAXUSDT","LINKUSDT","DOTUSDT","SUIUSDT","LTCUSDT","BCHUSDT","TONUSDT","PEPEUSDT","SHIBUSDT","WIFUSDT","BONKUSDT","FLOKIUSDT","NEARUSDT","APTUSDT","OPUSDT","ARBUSDT","INJUSDT","SEIUSDT","TIAUSDT","ATOMUSDT","UNIUSDT","AAVEUSDT"]

def api(path, params=None):
    query = urllib.parse.urlencode(params or {})
    last_error = None
    for base in BASES:
        req = urllib.request.Request(base + path + (("?" + query) if query else ""), headers={"User-Agent":"CryptoBotPro/2.0"})
        try:
            with urllib.request.urlopen(req, timeout=12, context=SSL_CONTEXT) as response:
                return json.loads(response.read().decode("utf-8"))
        except Exception as exc:
            last_error = exc
    raise RuntimeError("All Binance API hosts failed; check DNS/network. Last error: {}".format(last_error))

def market_data(symbol, interval="1h"):
    ticker = api("/api/v3/ticker/24hr", {"symbol":symbol})
    raw = api("/api/v3/klines", {"symbol":symbol,"interval":interval,"limit":100})
    candles = [{"open":float(k[1]),"high":float(k[2]),"low":float(k[3]),"close":float(k[4]),"volume":float(k[5])} for k in raw]
    return ticker, candles


class CandleChart(Widget):
    """Native Kivy candlestick chart with EMA overlays and volume bars."""
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.data = []
        self.ema20 = []
        self.ema50 = []
        self.zoom = 1.0
        self.offset = 0
        self._touches = {}
        self._pinch_distance = None
        self.bind(pos=self.redraw, size=self.redraw)

    def set_data(self, candles, indicators=None):
        self.data = candles or []
        closes = [c["close"] for c in self.data]
        self.ema20 = self._ema(closes, 20)
        self.ema50 = self._ema(closes, 50)
        self.offset = min(self.offset, max(0, len(self.data)-12))
        self.redraw()

    @staticmethod
    def _ema(values, period):
        if not values: return []
        alpha = 2.0 / (period + 1.0)
        out = [values[0]]
        for value in values[1:]: out.append(value * alpha + out[-1] * (1-alpha))
        return out


    def zoom_in(self):
        self.zoom = min(8.0, self.zoom * 1.25)
        self.redraw()

    def zoom_out(self):
        self.zoom = max(1.0, self.zoom / 1.25)
        self.offset = min(self.offset, max(0, len(self.data)-12))
        self.redraw()

    def reset_view(self):
        self.zoom = 1.0
        self.offset = 0
        self.redraw()

    def _pinch_distance_now(self):
        if len(self._touches) < 2: return None
        pts = list(self._touches.values())
        dx, dy = pts[0][0]-pts[1][0], pts[0][1]-pts[1][1]
        return max(1.0, (dx*dx+dy*dy)**0.5)

    def on_touch_down(self, touch):
        if self.collide_point(*touch.pos):
            self._touches[touch] = touch.pos
            if len(self._touches) == 2: self._pinch_distance = self._pinch_distance_now()
            touch.grab(self)
            return True
        return super().on_touch_down(touch)

    def on_touch_move(self, touch):
        if touch.grab_current is self and touch in self._touches:
            old = self._touches[touch]
            self._touches[touch] = touch.pos
            if len(self._touches) >= 2:
                distance = self._pinch_distance_now()
                if self._pinch_distance and distance:
                    self.zoom = max(1.0, min(8.0, self.zoom * distance / self._pinch_distance))
                self._pinch_distance = distance
            else:
                dx = touch.x - old[0]
                visible = max(12, int(len(self.data) / self.zoom))
                bars = int(round(dx / max(1, self.width-dp(56)) * visible))
                if bars: self.offset = max(0, min(max(0, len(self.data)-visible), self.offset + bars))
            self.redraw()
            return True
        return super().on_touch_move(touch)

    def on_touch_up(self, touch):
        if touch.grab_current is self:
            touch.ungrab(self)
            self._touches.pop(touch, None)
            self._pinch_distance = self._pinch_distance_now()
            return True
        return super().on_touch_up(touch)

    def redraw(self, *_):
        self.canvas.clear()
        if not self.data or self.width < 10 or self.height < 10: return
        left, right = self.x + dp(8), self.right - dp(48)
        bottom, top = self.y + dp(30), self.top - dp(12)
        chart_h = (top-bottom) * .78
        vol_h = (top-bottom) * .17
        gap = (top-bottom) * .05
        visible = max(12, min(len(self.data), int(len(self.data) / self.zoom)))
        end = max(1, len(self.data) - self.offset)
        begin = max(0, end - visible)
        candles = self.data[begin:end]
        ema20 = self.ema20[begin:end]
        ema50 = self.ema50[begin:end]
        if not candles: return
        vals = [v for c in candles for v in (c["high"], c["low"])]
        lo, hi = min(vals), max(vals)
        if hi <= lo: hi = lo + 1
        def yval(v): return bottom + vol_h + gap + ((v-lo)/(hi-lo))*chart_h
        n = len(candles); slot = (right-left)/max(n,1); candle_w = max(dp(2), slot*.68)
        maxvol = max((c.get("volume",0) for c in candles), default=1) or 1
        with self.canvas:
            Color(.025,.055,.11,1); Rectangle(pos=(left,bottom),size=(right-left,top-bottom))
            Color(.12,.20,.30,1)
            for j in range(5):
                yy = bottom + (top-bottom)*j/4
                Line(points=[left,yy,right,yy],width=1)
            for j in range(6):
                xx = left + (right-left)*j/5
                Line(points=[xx,bottom,xx,top],width=1)
            for i,c in enumerate(candles):
                x = left + (i+.5)*slot
                green = c["close"] >= c["open"]
                if green: Color(.02,.78,.42,.9)
                else: Color(.92,.12,.20,.9)
                vh = (c.get("volume",0)/maxvol)*vol_h
                Rectangle(pos=(x-candle_w/2,bottom),size=(candle_w,max(dp(1),vh)))
            for i,c in enumerate(self.data):
                x = left + (i+.5)*slot
                green = c["close"] >= c["open"]
                if green: Color(.02,.95,.48,1)
                else: Color(1,.12,.20,1)
                Line(points=[x,yval(c["low"]),x,yval(c["high"])],width=1.25)
                y1,y2 = yval(c["open"]),yval(c["close"])
                Rectangle(pos=(x-candle_w/2,min(y1,y2)),size=(candle_w,max(dp(2),abs(y2-y1))))
            for series, rgb in ((ema20,(.05,.72,1,1)),(ema50,(1,.62,.04,1))):
                Color(*rgb)
                pts=[]
                for i,v in enumerate(series): pts.extend([left+(i+.5)*slot,yval(v)])
                if len(pts)>=4: Line(points=pts,width=dp(1.6))
            Color(.15,.9,.75,.8)
            Line(points=[left,yval(candles[-1]["close"]),right,yval(candles[-1]["close"])],width=1,dash_length=dp(4),dash_offset=dp(3))

class CryptoBotApp(App):
    def build(self):
        self.title = "CRYPTO BOT PRO"
        Window.clearcolor = (0.015, 0.025, 0.07, 1)
        self.minimum_buy_score = 80
        self.busy = False
        self.scan_running = False
        self.pairs_loading = False
        self.interval = "1h"
        root = BoxLayout(orientation="vertical", padding=dp(10), spacing=dp(6))
        root.add_widget(Label(text="[b][color=FFD21F]◆ CRYPTO BOT PRO[/color][/b]\n[color=65C7FF]BINANCE SPOT LIVE DASHBOARD[/color]", markup=True, font_size="21sp", size_hint_y=None, height=dp(68), color=(1,1,1,1)))
        scroll = ScrollView(do_scroll_x=False)
        body = BoxLayout(orientation="vertical", spacing=dp(7), padding=(0,dp(4)), size_hint_y=None)
        body.bind(minimum_height=body.setter("height"))
        scroll.add_widget(body)
        root.add_widget(scroll)
        body.add_widget(self.heading("SELECT BINANCE USDT COIN"))
        self.pair = Spinner(text="BTCUSDT", values=tuple(PAIRS), size_hint_y=None, height=dp(48), background_color=(0.95,0.68,0.05,1), color=(0.03,0.04,0.08,1))
        self.pair.bind(text=lambda *_: self.refresh_market())
        body.add_widget(self.pair)
        self.pair_status = self.info("Loading all Binance Spot USDT trading pairs...")
        body.add_widget(self.pair_status)
        buttons = BoxLayout(size_hint_y=None, height=dp(46), spacing=dp(6))
        refresh = Button(text="↻ REFRESH LIVE DATA", background_normal="", background_color=(0.02,0.55,0.85,1), color=(1,1,1,1), bold=True)
        refresh.bind(on_release=lambda *_: self.refresh_market())
        self.filter_btn = Button(text="BUY FILTER: 80%", background_normal="", background_color=(0.42,0.22,0.78,1), color=(1,1,1,1), bold=True)
        self.filter_btn.bind(on_release=lambda *_: self.toggle_filter())
        buttons.add_widget(refresh); buttons.add_widget(self.filter_btn); body.add_widget(buttons)
        self.price = self.info("Live price: loading...")
        tfrow = BoxLayout(size_hint_y=None, height=dp(38), spacing=dp(4))
        self.tf_buttons = {}
        for label, interval in (("1m","1m"),("5m","5m"),("15m","15m"),("1h","1h"),("4h","4h"),("1D","1d")):
            b = Button(text=label, background_normal="", background_color=(.95,.68,.05,1) if interval == self.interval else (.06,.12,.22,1), color=(.02,.03,.06,1) if interval == self.interval else (1,1,1,1), font_size="12sp")
            b.bind(on_release=lambda btn, iv=interval: self.set_interval(iv))
            self.tf_buttons[interval] = b; tfrow.add_widget(b)
        body.add_widget(tfrow)
        zoomrow = BoxLayout(size_hint_y=None, height=dp(38), spacing=dp(6))
        zoomout = Button(text="− ZOOM OUT", background_normal="", background_color=(.08,.20,.32,1), color=(1,1,1,1), bold=True)
        zoomin = Button(text="+ ZOOM IN", background_normal="", background_color=(.02,.55,.85,1), color=(1,1,1,1), bold=True)
        resetzoom = Button(text="RESET VIEW", background_normal="", background_color=(.95,.68,.05,1), color=(.02,.03,.06,1), bold=True)
        zoomout.bind(on_release=lambda *_: self.chart.zoom_out())
        zoomin.bind(on_release=lambda *_: self.chart.zoom_in())
        resetzoom.bind(on_release=lambda *_: self.chart.reset_view())
        zoomrow.add_widget(zoomout); zoomrow.add_widget(zoomin); zoomrow.add_widget(resetzoom)
        body.add_widget(zoomrow)
        self.chart = CandleChart(size_hint_y=None, height=dp(300))
        body.add_widget(self.chart)
        self.day = self.info("24h change: -- | 24h volume: --")
        self.signal = self.info("SIGNAL: WAIT")
        self.score = self.info("BUY CONFIDENCE: --")
        self.indicators = self.info("RSI: -- | EMA20: -- | EMA50: --")
        self.checks = self.info("Technical confirmations will appear here.")
        for widget in (self.price,self.day,self.signal,self.score,self.indicators,self.checks): body.add_widget(widget)
        body.add_widget(self.heading("MEME COIN EARLY PUMP SCANNER"))
        scan = Button(text="🚀 SCAN BINANCE SPOT COINS NOW", size_hint_y=None, height=dp(50), background_normal="", background_color=(0.68,0.12,0.88,1), color=(1,1,1,1), bold=True)
        scan.bind(on_release=lambda *_: self.start_scan()); body.add_widget(scan)
        self.scan_status = self.info("Scanner ready. Tap to scan live 5-minute market activity.")
        self.scan_results = self.info("Pump alerts will appear here.")
        body.add_widget(self.scan_status); body.add_widget(self.scan_results)
        body.add_widget(self.info("Binance public market data only. BUY/SELL/WAIT are analysis signals; this app does not place orders."))
        Clock.schedule_once(lambda dt: self.refresh_market(), 0.5)
        Clock.schedule_once(lambda dt: self.load_all_pairs(), 1.0)
        # Keep the selected market view fresh without requiring manual taps.
        Clock.schedule_interval(lambda dt: self.refresh_market(), 60)
        return root


    def load_all_pairs(self):
        if self.pairs_loading:
            return
        self.pairs_loading = True
        threading.Thread(target=self.pairs_worker, daemon=True).start()

    def pairs_worker(self):
        try:
            data = api("/api/v3/exchangeInfo")
            symbols = sorted({
                item["symbol"] for item in data.get("symbols", [])
                if item.get("status") == "TRADING"
                and item.get("quoteAsset") == "USDT"
                and item.get("isSpotTradingAllowed", True)
            })
            Clock.schedule_once(lambda dt: self.show_pairs(symbols), 0)
        except Exception as exc:
            message = str(exc)[:120]
            Clock.schedule_once(lambda dt: self.pairs_error(message), 0)

    def show_pairs(self, symbols):
        self.pairs_loading = False
        if symbols:
            current = self.pair.text
            self.pair.values = tuple(symbols)
            self.pair_status.text = "{} active Binance Spot USDT pairs loaded. Tap the coin selector to choose any pair.".format(len(symbols))
            if current not in symbols:
                self.pair.text = "BTCUSDT" if "BTCUSDT" in symbols else symbols[0]
        else:
            self.pair_status.text = "Could not load pair list; showing the built-in popular pairs."

    def pairs_error(self, message):
        self.pairs_loading = False
        self.pair_status.text = "Pair list unavailable; popular pairs remain selectable. " + message

    def heading(self, value):
        return Label(text="[b][color=FFD21F]"+value+"[/color][/b]", markup=True, font_size="16sp", size_hint_y=None, height=dp(38), color=(1,1,1,1))

    def info(self, value):
        label = Label(text="[color=DBEAFE]"+value+"[/color]", markup=True, font_size="13sp", halign="left", valign="middle", size_hint_y=None, height=dp(52), color=(0.86,0.92,1,1))
        label.bind(width=lambda obj,w: setattr(obj,"text_size",(w,None)), texture_size=lambda obj,s: setattr(obj,"height",max(dp(42),s[1]+dp(10))))
        return label

    def set_interval(self, interval):
        self.interval = interval
        for iv, button in self.tf_buttons.items():
            active = iv == interval
            button.background_color = (.95,.68,.05,1) if active else (.06,.12,.22,1)
            button.color = (.02,.03,.06,1) if active else (1,1,1,1)
        self.refresh_market()

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
            ticker,candles = market_data(symbol,self.interval)
            result = analyze_buy_signal(candles,self.minimum_buy_score)
            Clock.schedule_once(lambda dt:self.show_market(symbol,ticker,result,candles),0)
        except Exception as exc:
            message=str(exc)[:150]
            Clock.schedule_once(lambda dt:self.market_error(message),0)

    def market_error(self,message):
        self.busy=False
        self.price.text="Binance connection error: "+message
        self.signal.text="SIGNAL: WAIT - refresh when connected"

    def show_market(self,symbol,ticker,result,candles):
        self.busy=False
        price=float(ticker.get("lastPrice",0))
        change=float(ticker.get("priceChangePercent",0))
        volume=float(ticker.get("quoteVolume",0))
        self.price.text="{} LIVE PRICE: {}".format(symbol,format(price,".8g"))
        self.day.text="24h change: {:+.2f}% | 24h quote volume: {:,.0f} USDT".format(change,volume)
        ind=result.get("indicators",{})
        self.chart.set_data(candles,ind)
        decision=result.get("decision","WAIT")
        if decision=="WAIT" and ind and ind.get("price",0)<ind.get("ema20",0)<ind.get("ema50",0) and ind.get("rsi14",50)<45:
            decision="SELL / EXIT WARNING"
        signal_color = "20E070" if decision == "BUY" else ("FF4D6D" if "SELL" in decision else "FFD21F")
        self.signal.text="[b][color={}]SIGNAL: {}[/color][/b]".format(signal_color, decision)
        self.score.text="[b][color=54D6FF]BUY CONFIDENCE: {}% | Required: {}%[/color][/b]".format(result.get("score",0),self.minimum_buy_score)
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
        self.scan_status.text="[color=54D6FF]Connecting to Binance; preparing scan...[/color]"
        self.scan_results.text="Checking volume surge, 5m momentum and aggressive buying..."
        threading.Thread(target=self.scan_worker,daemon=True).start()

    def scan_worker(self):
        try:
            results=scan_binance_spot(on_progress=lambda done,total,symbol: Clock.schedule_once(lambda dt: self.update_scan_progress(done,total,symbol),0))
            Clock.schedule_once(lambda dt:self.show_scan(results),0)
        except Exception as exc:
            message=str(exc)[:150]
            Clock.schedule_once(lambda dt:self.scan_error(message),0)

    def update_scan_progress(self, done, total, symbol):
        if self.scan_running:
            self.scan_status.text="[color=54D6FF]Scanning {}/{}: {}[/color]".format(done,total,symbol)

    def scan_error(self,message):
        self.scan_running=False
        self.scan_status.text="Scanner error: "+message

    def show_scan(self,results):
        self.scan_running=False
        alerts=[x for x in results if x.get("alert")]
        self.scan_status.text="[b][color=20E070]SCAN COMPLETE: {} pairs checked | {} early alerts[/color][/b]".format(len(results),len(alerts))
        if not results:
            self.scan_results.text="No eligible USDT pairs returned."; return
        rows=[]
        for item in results[:15]:
            rows.append("{} | {} | Score {}%\n5m volume {:.2f}x | price {:+.2f}% | buyers {:.1f}%".format(item.get("symbol","?"),"EARLY ALERT" if item.get("alert") else "WAIT",item.get("score",0),item.get("volume_ratio",0),item.get("price_change",0),item.get("buy_ratio",0)))
        self.scan_results.text="\n\n".join(rows)

CryptoBotApp().run()
