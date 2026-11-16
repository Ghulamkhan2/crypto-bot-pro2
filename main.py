from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.popup import Popup
from kivy.metrics import dp

from indicators import analyze_buy_signal


class CryptoBotApp(App):
    def build(self):
        self.title = "CRYPTO BOT PRO"
        self.minimum_buy_score = 80

        layout = BoxLayout(
            orientation="vertical",
            padding=dp(18),
            spacing=dp(10)
        )

        layout.add_widget(Label(
            text="[b]CRYPTO BOT PRO[/b]",
            markup=True,
            font_size="26sp",
            size_hint_y=None,
            height=dp(55)
        ))

        layout.add_widget(Label(
            text="SPOT TRADING | BUY CONFIRMATION FILTER",
            font_size="15sp"
        ))

        self.score_label = Label(
            text="BUY CONFIDENCE: WAITING FOR LIVE MARKET DATA",
            font_size="17sp"
        )
        layout.add_widget(self.score_label)

        self.filter_label = Label(
            text="MINIMUM BUY SCORE: 80%",
            font_size="16sp"
        )
        layout.add_widget(self.filter_label)

        filter_button = Button(
            text="CHANGE FILTER: 80% / 100%",
            size_hint_y=None,
            height=dp(48)
        )
        filter_button.bind(on_release=lambda *_: self.toggle_filter())
        layout.add_widget(filter_button)

        self.checks_label = Label(
            text=(
                "5 CONFIRMATIONS (20% EACH)\n"
                "1. EMA 20 above EMA 50\n"
                "2. Price above EMA 20\n"
                "3. RSI between 50 and 68\n"
                "4. MACD above signal\n"
                "5. Volume at least 1.2x average"
            ),
            font_size="14sp",
            halign="left",
            valign="middle"
        )
        self.checks_label.bind(
            size=lambda instance, value: setattr(instance, "text_size", value)
        )
        layout.add_widget(self.checks_label)

        layout.add_widget(Label(
            text="BUY is allowed only at/above the selected score.",
            font_size="13sp"
        ))

        layout.add_widget(Label(
            text=(
                "Safety: score is indicator confluence, not a win probability. "
                "No live order is placed by this screen."
            ),
            font_size="12sp"
        ))

        return layout

    def toggle_filter(self):
        self.minimum_buy_score = 100 if self.minimum_buy_score == 80 else 80
        self.filter_label.text = (
            "MINIMUM BUY SCORE: {}%".format(self.minimum_buy_score)
        )

    def analyze_market_candles(self, candles):
        """Call this with fresh OHLCV candles from the live market feed."""
        result = analyze_buy_signal(candles, self.minimum_buy_score)
        self.score_label.text = "BUY CONFIDENCE: {}% | {}".format(
            result["score"], result["decision"]
        )
        lines = ["{}: {}".format(
            "PASS" if passed else "NO",
            name
        ) for name, passed in result["checks"].items()]
        self.checks_label.text = "\n".join(lines) if lines else result["reason"]
        return result


CryptoBotApp().run()
