from config.settings import config
import websocket
import json
import time
from core.models import MarketTick

class BinanceDataStream:
    def __init__(self):
        base_url = config.BINANCE_WS_URL
        streams = [f"{symbol.lower()}@bookTicker" for symbol in config.SYMBOLS]
        self.url = base_url + "/".join(streams)

    def on_message(self, ws, message):
        raw_data = json.loads(message)
        data = raw_data.get('data')
        if not data:
            return
        tick = MarketTick(
            symbol=data['s'],
            bid_price=float(data['b']),
            ask_price=float(data['a']),
            timestamp=int(time.time() * 1000)
        )

        print(f"{tick.symbol} BID: {tick.bid_price:.2f} | ASK: {tick.ask_price:.2f}")


    def on_error(self, ws, error):
        print(f"Connection error: {error}")

    def on_close(self, ws, close_status_code, close_msg):
        print("Disconnected from Binance")

    def connect(self):
        print(f"Connecting with Binance: {self.url}")

        ws= websocket.WebSocketApp(
            self.url,
            on_message=self.on_message,
            on_error=self.on_error,
            on_close=self.on_close
        )

        ws.run_forever()