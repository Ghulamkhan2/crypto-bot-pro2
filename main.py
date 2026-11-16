import threading

from kivy.app import App
from kivy.clock import Clock
from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.button import Button

from indicators import analyze_buy_signal
from pump_scanner import scan_binance_spot


class CryptoBotApp(App):
    def build(self):
        self.title = "CRYPTO BOT PRO"
        self.minimum_buy_score = 80
        self.scan_running = False

        layout = BoxLayout(
            orientation="vertical",
            padding=dp(14),
            spacing=dp(8)
        )

        layout.add_widget(Label(
            text="[b]CRYPTO BOT PRO[/b]",
            markup=True,
            font_size="25sp",
            size_hint_y=None,
            height=dp(48)
        ))

        layout.add_widget(Label(
            text="SPOT TRADING | BUY CONFIRMATION FILTER",
            font_size="14sp",
            size_hint_y=None,
            height=dp(28)
        ))

        self.score_label = Label(
            text="BUY CONFIDENCE: WAITING FOR LIVE MARKET DATA",
            font_size="16sp",
            size_hint_y=None,
            height=dp(42)
        )
        layout.add_widget(self.score_label)

        self.filter_label = Label(
            text="MINIMUM BUY SCORE: 80%",
            font_size="15sp",
            size_hint_y=None,
            height=dp(28)
        )
        layout.add_widget(self.filter_label)

        filter_button = Button(
            text="CHANGE FILTER: 80% / 100%",
            size_hint_y=None,
            height=dp(44)
        )
        filter_button.bind(on_release=lambda *_: self.toggle_filter())
        layout.add_widget(filter_button)

        self.checks_label = Label(
            text=(
                "BUY CONFIRMATIONS (20% EACH)\\n"
                "1. EMA20 above EMA50\\n"
                "2. Price above EMA20\\n"
                "3. RSI between 50 and 68\\n"
                "4. MACD above signal\\n"
                "5. Volume at least 1.2x average"
            ),
            font_size="13sp",
            halign="left",
            valign="middle",
            size_hint_y=None,
            height=dp(115)
        )
        self.checks_label.bind(
            size=lambda instance, value: setattr(instance, "text_size", value)
        )
        layout.add_widget(self.checks_label)

        layout.add_widget(Label(
            text="[b]MEME COIN PUMP ALERT SCANNER[/b]",
            markup=True,
            font_size="17sp",
            size_hint_y=None,
            height=dp(34)
        ))

        scan_button = Button(
            text="SCAN BINANCE SPOT COINS NOW",
            size_hint_y=None,
            height=dp(50)
        )
        scan_button.bind(on_release=lambda *_: self.start_pump_scan())
        layout.add_widget(scan_button)

        self.scan_status = Label(
            text="Scanner ready. Press the button to check live market activity.",
            font_size="12sp",
            size_hint_y=None,
            height=dp(35)
        )
        layout.add_widget(self.scan_status)

        self.scan_results = Label(
            text=(
                "Waiting for scan...\\n"
                "Checks: volume surge, 5m price momentum, aggressive buying, "
                "and candle close near high."
            ),
            font_size="12sp",
            halign="left",
            valign="top"
        )
        self.scan_results.bind(
            size=lambda instance, value: setattr(instance, "text_size", value)
        )
        layout.add_widget(self.scan_results)

        layout.add_widget(Label(
            text=(
                "Alerts are not guaranteed pumps. Scanner uses public Binance "
                "Spot data only; it does not place trades."
            ),
            font_size="11sp",
            size_hint_y=None,
            height=dp(38)
        ))

        return layout

    def toggle_filter(self):
        self.minimum_buy_score = 100 if self.minimum_buy_score == 80 else 80
        self.filter_label.text = (
            "MINIMUM BUY SCORE: {}%".format(self.minimum_buy_score)
        )

    def analyze_market_candles(self, candles):
        """Analyze fresh OHLCV candles supplied by a live market feed."""
        result = analyze_buy_signal(candles, self.minimum_buy_score)
        self.score_label.text = "BUY CONFIDENCE: {}% | {}".format(
            result["score"], result["decision"]
        )
        lines = ["{}: {}".format("PASS" if passed else "NO", name)
                 for name, passed in result["checks"].items()]
        self.checks_label.text = "\\n".join(lines) if lines else result["reason"]
        return result

    def start_pump_scan(self):
        if self.scan_running:
            self.scan_status.text = "Scan already running. Please wait."
            return
        self.scan_running = True
        self.scan_status.text = "Connecting to Binance public market data..."
        self.scan_results.text = "Scanning liquid USDT spot pairs..."
        threading.Thread(target=self._pump_scan_worker, daemon=True).start()

    def _pump_scan_worker(self):
        try:
            results = scan_binance_spot()
            Clock.schedule_once(lambda dt: self._show_scan_results(results), 0)
        except Exception as exc:
            message = str(exc)
            Clock.schedule_once(lambda dt: self._show_scan_error(message), 0)

    def _show_scan_error(self, message):
        self.scan_running = False
        self.scan_status.text = "Scanner could not get market data."
        self.scan_results.text = (
            "Error: {}\\nCheck internet access or try again later.".format(message[:180])
        )

    def _show_scan_results(self, results):
        self.scan_running = False
        alerts = [item for item in results if item.get("alert")]
        self.scan_status.text = (
            "Scan complete: {} pairs checked | {} early alerts".format(
                len(results), len(alerts)
            )
        )
        if not results:
            self.scan_results.text = "No eligible USDT spot pairs were returned."
            return

        lines = []
        for item in results[:12]:
            symbol = item.get("symbol", "Unknown")
            score = item.get("score", 0)
            marker = "🚨 ALERT" if item.get("alert") else "WAIT"
            lines.append(
                "{} | {} | {}%\\n"
                "Vol: {}x | 5m: {}% | Buy: {}%".format(
                    symbol, marker, score,
                    item.get("volume_ratio", 0),
                    item.get("price_change", 0),
                    item.get("buy_ratio", 0)
                )
            )
        self.scan_results.text = "\\n\\n".join(lines)


CryptoBotApp().run()
