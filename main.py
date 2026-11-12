from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.popup import Popup
from kivy.metrics import dp

class CryptoBotApp(App):
    def build(self):
        self.title = "CRYPTO BOT PRO"

        layout = BoxLayout(
            orientation="vertical",
            padding=dp(18),
            spacing=dp(12)
        )

        layout.add_widget(Label(
            text="[b]CRYPTO BOT PRO[/b]",
            markup=True,
            font_size="26sp",
            size_hint_y=None,
            height=dp(55)
        ))

        layout.add_widget(Label(
            text="DEMO MODE",
            color=(0, 0.8, 0.3, 1),
            font_size="18sp"
        ))

        layout.add_widget(Label(
            text="Wallet Balance: 100 USDT\n"
                 "Invested: 0 USDT\n"
                 "Available: 100 USDT\n"
                 "Open Trades: 0",
            font_size="18sp"
        ))

        layout.add_widget(Label(
            text="BTC DAILY FILTER: WAIT",
            font_size="18sp"
        ))

        self.signal = Label(
            text="TRADING SIGNAL: WAIT",
            font_size="23sp",
            color=(1, 0.7, 0, 1)
        )
        layout.add_widget(self.signal)

        buy = Button(text="BUY", background_color=(0, 0.6, 0.2, 1))
        buy.bind(on_release=lambda x: self.confirm("BUY"))
        layout.add_widget(buy)

        sell = Button(text="SELL", background_color=(0.8, 0.1, 0.1, 1))
        sell.bind(on_release=lambda x: self.confirm("SELL"))
        layout.add_widget(sell)

        wait = Button(text="WAIT")
        wait.bind(on_release=lambda x: self.set_wait())
        layout.add_widget(wait)

        layout.add_widget(Label(
            text="No real orders. Demo screen only.",
            font_size="13sp"
        ))

        return layout

    def confirm(self, action):
        content = BoxLayout(orientation="vertical", padding=dp(12))
        content.add_widget(Label(
            text=f"{action} signal selected.\n"
                 "This is only a demo.\n"
                 "No Binance order will be placed."
        ))
        close = Button(text="OK", size_hint_y=None, height=dp(45))
        content.add_widget(close)
        popup = Popup(
            title="Confirmation",
            content=content,
            size_hint=(0.85, 0.4)
        )
        close.bind(on_release=popup.dismiss)
        popup.open()

    def set_wait(self):
        self.signal.text = "TRADING SIGNAL: WAIT"

CryptoBotApp().run()
