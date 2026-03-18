import asyncio
import json
import time
import websockets
import logging
from config.settings import config
from core.models import MarketTick

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class BinanceDataStream:
    def __init__(self, engine):
        self.engine = engine
        self.keep_running = True
        base_url = config.BINANCE_WS_URL
        streams = [f"{symbol.lower()}@bookTicker" for symbol in config.SYMBOLS]
        self.url = base_url + "/".join(streams)
        
        self.expected_currencies_count = self._calculate_expected_currencies()

    def _calculate_expected_currencies(self) -> int:
        expected_currencies = set()
        for symbol in config.SYMBOLS:
            symbol_upper = symbol.upper()
            for q in config.QUOTE_CURRENCIES:
                if symbol_upper.endswith(q):
                    expected_currencies.add(q)
                    expected_currencies.add(symbol_upper[:-len(q)])
                    break
        return len(expected_currencies)

    async def _process_messages(self, websocket):
        try:
            async for message in websocket:
                if not self.keep_running:
                    break
                
                raw_data = json.loads(message)
                data = raw_data.get('data')
                if not data:
                    continue
                
                tick = MarketTick(
                    symbol=data['s'],
                    bid_price=float(data['b']),
                    ask_price=float(data['a']),
                    timestamp=int(time.time() * 1000)
                )
                
                symbol = tick.symbol.upper()
                base, quote = None, None

                for q in config.QUOTE_CURRENCIES:
                    if symbol.endswith(q):
                        quote = q
                        base = symbol[:-len(q)]
                        break

                if not base or not quote:
                    continue
                
                fee_multiplier = 1.0 - config.FEE

                self.engine.add_rate(base, quote, tick.bid_price * fee_multiplier)
                if tick.ask_price > 0:
                    self.engine.add_rate(quote, base, (1.0 / tick.ask_price) * fee_multiplier)
                    
        except websockets.exceptions.ConnectionClosed:
            logger.warning("WebSocket closed.")
        except Exception as e:
            logger.error(f"Error processing message: {e}")

    async def _arbitrage_worker(self):
        logger.info(f"Waiting for initial data for all {self.expected_currencies_count} currencies...")
        
        # Faza rozgrzewki - czekamy na pełny graf
        while len(self.engine.currencies) < self.expected_currencies_count:
            if not self.keep_running:
                return
            await asyncio.sleep(0.1)
            
        logger.info("Graph fully populated! Starting continuous arbitrage checks...")

        # Główna pętla sprawdzająca
        while self.keep_running:
            await asyncio.sleep(0.2) # Częstotliwość skanowania grafu
            
            wynik = self.engine.bellman_ford(config.BASE_CURRENCY)
            if wynik:
                logger.info(f"💰 Arbitrage found! Path: {wynik}")
            else:
                pass

    async def connect(self):
        while self.keep_running:
            try:
                logger.info(f"Connecting with Binance: {self.url}")
                async with websockets.connect(self.url) as ws:
                    logger.info("Connected! Starting data stream and arbitrage engine...")
                    
                    listener_task = asyncio.create_task(self._process_messages(ws))
                    worker_task = asyncio.create_task(self._arbitrage_worker())
                    
                    await asyncio.gather(listener_task, worker_task)
                    
            except websockets.exceptions.WebSocketException as e:
                logger.error(f"WebSocket connection error: {e}")
            except KeyboardInterrupt:
                self.keep_running = False
                logger.info("Gracefully shutting down...")
                break
            except Exception as e:
                logger.error(f"Unexpected error: {e}")
            
            if self.keep_running:
                logger.warning("Lost connection. System restart in 5 seconds...")
                await asyncio.sleep(5)
                
        logger.info("Stopped program.")