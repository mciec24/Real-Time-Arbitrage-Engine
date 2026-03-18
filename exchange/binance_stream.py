from config.settings import config
import websocket
import json
import time
from core.models import MarketTick


class BinanceDataStream:
    def __init__(self, engine):
        self.engine = engine
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
        symbol = tick.symbol.upper()
        base = None
        quote = None

        for q in config.QUOTE_CURRENCIES:
            if symbol.endswith(q):
                quote = q
                base = symbol[:-len(q)]
                break

        if not base or not quote:
            return
        
        self.engine.add_rate(base, quote, tick.bid_price)
        if tick.ask_price > 0:
            self.engine.add_rate(quote, base, 1.0 / tick.ask_price)
        
        wynik = self.engine.bellman_ford(config.BASE_CURRENCY)

        if wynik:
            print(f"\n💰 ARBITRAŻ ZNALEZIONY! Ścieżka: {wynik}")
        else:
            print(".", end="", flush = True)


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