"""CRYPTO BOT PRO - Binance Spot live dashboard; public data only, no order execution."""
import json
from datetime import datetime, timezone
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
from kivy.core.text import Label as CoreLabel
from kivy.graphics import Color, RoundedRectangle, Line, Rectangle
from indicators import analyze_buy_signal, candle_trade_markers
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
    depth = api("/api/v3/depth", {"symbol":symbol,"limit":10})
    candles = [{"open":float(k[1]),"high":float(k[2]),"low":float(k[3]),"close":float(k[4]),"volume":float(k[5]),"open_time":int(k[0]),"time":datetime.fromtimestamp(k[0]/1000, timezone.utc).strftime("%m-%d %H:%M")} for k in raw]
    return ticker, candles, depth


class CandleChart(Widget):
    """Native Kivy candlestick chart with EMA overlays and volume bars."""
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.data = []
        self.ema20 = []
        self.ema50 = []
        self.markers = []
        self.zoom = 3.0
        self.offset = 0
        self._touches = {}
        self._pinch_distance = None
        self._pan_remainder = 0.0
        self._touch_start = {}
        self.selected_index = -1
        self.detail_label = None
        self.bind(pos=self.redraw, size=self.redraw)

    def set_data(self, candles, indicators=None):
        self.data = candles or []
        closes = [c["close"] for c in self.data]
        self.ema20 = self._ema(closes, 20)
        self.ema50 = self._ema(closes, 50)
        self.markers = candle_trade_markers(self.data, 80)
        self.offset = 0
        self.selected_index = len(self.data)-1
        self._update_detail()
        self.redraw()

    @staticmethod
    def _ema(values, period):
        if not values: return []
        alpha = 2.0 / (period + 1.0)
        out = [values[0]]
        for value in values[1:]: out.append(value * alpha + out[-1] * (1-alpha))
        return out


    def _update_detail(self):
        if self.detail_label is None or not self.data: return
        idx = self.selected_index if 0 <= self.selected_index < len(self.data) else len(self.data)-1
        c = self.data[idx]
        direction = "BULLISH (GREEN)" if c["close"] >= c["open"] else "BEARISH (RED)"
        stamp = c.get("time", c.get("open_time", ""))
        move = c["close"] - c["open"]
        move_pct = (move / c["open"] * 100.0) if c["open"] else 0.0
        self.detail_label.text = ("CANDLE: {} | O: {} | H: {} | L: {} | C: {} | VOL: {}".format(
            stamp, format(c["open"], ".8g"), format(c["high"], ".8g"),
            format(c["low"], ".8g"), format(c["close"], ".8g"),
            format(c.get("volume", 0), ".6g")) + "\n" + direction +
            " | CHANGE: {:+.8g} ({:+.2f}%) | Candle {} / {}".format(move, move_pct, idx+1, len(self.data)))

    def zoom_in(self):
        self.zoom = min(8.0, self.zoom * 1.25)
        self.redraw()

    def zoom_out(self):
        self.zoom = max(0.35, self.zoom / 1.25)
        self.offset = min(self.offset, max(0, len(self.data)-12))
        self.redraw()

    def reset_view(self):
        self.zoom = 3.0
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
            self._touch_start[touch] = touch.pos
            if len(self._touches) == 2:
                self._pinch_distance = self._pinch_distance_now()
                self._pan_remainder = 0.0
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
                    self.zoom = max(0.35, min(8.0, self.zoom * distance / self._pinch_distance))
                self._pinch_distance = distance
            else:
                dx = touch.x - old[0]
                visible = max(6, min(len(self.data), int(68 / self.zoom)))
                pixels_per_candle = max(2.0, (self.width-dp(73)) / max(1, visible))
                self._pan_remainder += dx
                bars = int(self._pan_remainder / pixels_per_candle)
                if bars:
                    self._pan_remainder -= bars * pixels_per_candle
                    self.offset = max(0, min(max(0, len(self.data)-visible), self.offset + bars))
                    self.selected_index = max(0, min(len(self.data)-1, len(self.data)-self.offset-1))
                    self._update_detail()
            self.redraw()
            return True
        return super().on_touch_move(touch)

    def on_touch_up(self, touch):
        if touch.grab_current is self:
            touch.ungrab(self)
            start = self._touch_start.pop(touch, touch.pos)
            self._touches.pop(touch, None)
            self._pinch_distance = self._pinch_distance_now()
            if len(self._touches) < 2: self._pan_remainder = 0.0
            if not self._touches and not self._touch_start and self.data:
                moved = ((touch.x-start[0])**2 + (touch.y-start[1])**2)**0.5
                if moved < dp(12):
                    left, right = self.x + dp(8), self.right - dp(65)
                    visible = max(6, min(len(self.data), int(68/self.zoom)))
                    end = max(1, len(self.data)-self.offset)
                    begin = max(0, end-visible)
                    slot = (right-left)/max(1,end-begin)
                    idx = begin + int((touch.x-left)/max(1,slot))
                    self.selected_index = max(begin, min(end-1, idx))
                    self._update_detail()
                    self.redraw()
            return True
        return super().on_touch_up(touch)

    def redraw(self, *_):
        self.canvas.clear()
        if not self.data or self.width < 10 or self.height < 10: return
        left, right = self.x + dp(8), self.right - dp(94)
        bottom, top = self.y + dp(30), self.top - dp(12)
        chart_h = (top-bottom) * .78
        vol_h = (top-bottom) * .17
        gap = (top-bottom) * .05
        visible = max(6, min(len(self.data), int(80 / self.zoom)))
        end = max(1, len(self.data) - self.offset)
        begin = max(0, end - visible)
        candles = self.data[begin:end]
        ema20 = self.ema20[begin:end]
        ema50 = self.ema50[begin:end]
        if not candles: return
        vals = [v for c in candles for v in (c["high"], c["low"])]
        raw_lo, raw_hi = min(vals), max(vals)
        raw_span = max(raw_hi - raw_lo, raw_hi * 0.001, 1e-8)
        lo, hi = raw_lo - raw_span * 0.06, raw_hi + raw_span * 0.06
        if hi <= lo: hi = lo + 1
        def yval(v): return bottom + vol_h + gap + ((v-lo)/(hi-lo))*chart_h
        n = len(candles); display_slots = min(visible + 1.5, max(n, 1) + 1.5); slot = (right-left)/max(display_slots,1); candle_w = max(dp(2), min(dp(14), slot*.76))
        maxvol = max((c.get("volume",0) for c in candles), default=1) or 1
        with self.canvas:
            Color(.025,.055,.11,1); Rectangle(pos=(left,bottom),size=(right-left,top-bottom))
            Color(.12,.20,.30,1)
            for j in range(5):
                yy = bottom + (top-bottom)*j/4
                Line(points=[left,yy,right,yy],width=1)
                price_value = lo + (hi-lo)*j/4
                price_tag = CoreLabel(text=format(price_value, ".8g"), font_size=dp(11), color=(.90,.93,1,1))
                price_tag.refresh()
                Color(.82,.88,.96,1)
                Rectangle(texture=price_tag.texture, pos=(self.right-dp(88), yy-price_tag.texture.height/2), size=price_tag.texture.size)
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
            for i,c in enumerate(candles):
                x = left + (i+.5)*slot
                green = c["close"] >= c["open"]
                if green: Color(.02,.95,.48,1)
                else: Color(1,.12,.20,1)
                Line(points=[x,yval(c["low"]),x,yval(c["high"])],width=1.25)
                y1,y2 = yval(c["open"]),yval(c["close"])
                Rectangle(pos=(x-candle_w/2,min(y1,y2)),size=(candle_w,max(dp(2),abs(y2-y1))))
            # Keep the candlestick area uncluttered; signals remain in the dashboard summary.
            # EMA overlays are hidden on the main chart for a clean Binance-style candle view.
            last_price = candles[-1]["close"]
            previous_close = candles[-2]["close"] if len(candles) > 1 else candles[-1]["open"]
            price_delta = last_price - previous_close
            price_color = (.02,.68,.38,1) if price_delta >= 0 else (.88,.12,.20,1)
            last_y = yval(last_price)
            Color(price_color[0],price_color[1],price_color[2],.95)
            Line(points=[left,last_y,right,last_y],width=1.25,dash_length=dp(4),dash_offset=dp(3))
            # Prominent live-price tag aligned with the latest candle on the right axis.
            Color(*price_color)
            RoundedRectangle(pos=(self.right-dp(91),last_y-dp(11)),size=(dp(88),dp(22)),radius=[dp(3)])
            live_tag = CoreLabel(text=format(last_price, ".8g"),font_size=dp(11),bold=True,color=(1,1,1,1))
            live_tag.refresh()
            Color(1,1,1,1)
            Rectangle(texture=live_tag.texture,pos=(self.right-dp(87),last_y-live_tag.texture.height/2),size=live_tag.texture.size)
            # Yellow selection line removed to keep candles unobstructed.

class CryptoBotApp(App):
    def build(self):
        self.title = "CRYPTO BOT PRO"
        Window.clearcolor = (0.015, 0.025, 0.07, 1)
        self.minimum_buy_score = 80
        self.busy = False
        self.market_request_id = 0
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
        self.price = self.info("[b]LIVE PRICE: loading...[/b]")
        self.price.height = dp(58)
        tfrow = BoxLayout(size_hint_y=None, height=dp(38), spacing=dp(4))
        self.tf_buttons = {}
        for label, interval in (("1m","1m"),("5m","5m"),("15m","15m"),("30m","30m"),("1h","1h"),("4h","4h"),("1D","1d")):
            b = Button(text=label, background_normal="", background_color=(.95,.68,.05,1) if interval == self.interval else (.06,.12,.22,1), color=(.02,.03,.06,1) if interval == self.interval else (1,1,1,1), font_size="12sp")
            b.bind(on_release=lambda btn, iv=interval: self.set_interval(iv))
            self.tf_buttons[interval] = b; tfrow.add_widget(b)
        body.add_widget(tfrow)
        self.chart = CandleChart(size_hint_y=None, height=dp(540))
        body.add_widget(self.chart)
        self.candle_detail = self.info("Tap any candle to inspect it. Latest candle is selected by default.")
        self.candle_detail.height = dp(68)
        self.chart.detail_label = self.candle_detail
        body.add_widget(self.candle_detail)
        self.marker_legend = self.info("[color=20E070]▲ BUY[/color] below candle     [color=FF4D6D]▼ SELL[/color] above candle (80% confirmation)")
        self.marker_legend.height = dp(34)
        body.add_widget(self.marker_legend)
        self.day = self.info("24h change: -- | 24h volume: --")
        self.orderbook = self.info("ORDER BOOK  |  BID: loading...  |  ASK: loading...")
        self.orderbook.height = dp(62)
        self.signal = self.info("SIGNAL: WAIT")
        self.score = self.info("BUY CONFIDENCE: --")
        self.indicators = self.info("RSI: -- | EMA20: -- | EMA50: --")
        self.checks = self.info("Technical confirmations will appear here.")
        for widget in (self.price,self.day,self.signal,self.score,self.indicators,self.checks,self.orderbook): body.add_widget(widget)
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
        self.market_request_id += 1
        request_id = self.market_request_id
        symbol = self.pair.text
        interval = self.interval
        score_threshold = self.minimum_buy_score
        self.busy = True
        self.price.text = "Loading {} {} candles from Binance...".format(symbol, interval.upper())
        threading.Thread(target=self.market_worker,args=(symbol,interval,score_threshold,request_id),daemon=True).start()

    def market_worker(self,symbol,interval,score_threshold,request_id):
        try:
            ticker,candles,depth = market_data(symbol,interval)
            result = analyze_buy_signal(candles,score_threshold)
            Clock.schedule_once(lambda dt:self.show_market(symbol,interval,ticker,result,candles,depth,request_id),0)
        except Exception as exc:
            message=str(exc)[:150]
            Clock.schedule_once(lambda dt:self.market_error(message,request_id),0)

    def market_error(self,message,request_id):
        if request_id != self.market_request_id: return
        self.busy=False
        self.price.text="Binance connection error: "+message
        self.signal.text="SIGNAL: WAIT - refresh when connected"

    def show_market(self,symbol,interval,ticker,result,candles,depth,request_id):
        if request_id != self.market_request_id: return
        self.busy=False
        price=float(ticker.get("lastPrice",0))
        change=float(ticker.get("priceChangePercent",0))
        volume=float(ticker.get("quoteVolume",0))
        self.price.text="[b]{} / {}[/b]     [b]{}[/b]   [color={}]{}{:+.2f}%[/color]".format(symbol[:-4],symbol[-4:],format(price,".8g"),"20E070" if change>=0 else "FF4D6D","" if change>=0 else "",change)
        high=float(ticker.get("highPrice",0)); low=float(ticker.get("lowPrice",0)); base_volume=float(ticker.get("volume",0))
        self.day.text="24h HIGH: {}   LOW: {}\n24h CHANGE: {:+.2f}%   VOL: {:,.3g} {} / {:,.3g} USDT".format(format(high,".8g"),format(low,".8g"),change,base_volume,symbol.replace("USDT",""),volume)
        bids=depth.get("bids",[])[:5]; asks=depth.get("asks",[])[:5]
        bid_text="  ".join("{} ({})".format(format(float(x[0]),".8g"),format(float(x[1]),".5g")) for x in bids[:3]) or "--"
        ask_text="  ".join("{} ({})".format(format(float(x[0]),".8g"),format(float(x[1]),".5g")) for x in asks[:3]) or "--"
        self.orderbook.text="[b][color=20E070]BID[/color][/b] {}\n[b][color=FF4D6D]ASK[/color][/b] {}".format(bid_text,ask_text)
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
