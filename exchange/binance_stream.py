import asyncio
import json
import time
import websockets
import logging

from config.settings import config
from core.models import MarketTick
from core.graph_engine import Graph

logger = logging.getLogger(__name__)


class BinanceDataStream:
    def __init__(self, engine, order_manager):
        self.engine = engine
        self.order_manager = order_manager
        self.keep_running = True
        self.lock = asyncio.Lock()

        streams = [f"{s.lower()}@bookTicker" for s in config.SYMBOLS]
        self.url = config.BINANCE_WS_URL + "/".join(streams)

        self.expected_currencies_count = self._calculate_expected_currencies()

    def _calculate_expected_currencies(self) -> int:
        currencies = set()
        for symbol in config.SYMBOLS:
            symbol = symbol.upper()
            for q in config.QUOTE_CURRENCIES:
                if symbol.endswith(q):
                    currencies.add(q)
                    currencies.add(symbol[:-len(q)])
                    break
        return len(currencies)

    async def _process_messages(self, ws):
        # Calculate fee multiplier once to optimize the loop
        fee_multiplier = 1.0 - config.FEE

        async for message in ws:
            if not self.keep_running:
                break

            try:
                data = json.loads(message).get("data")
                if not data:
                    continue

                tick = MarketTick(
                    symbol=data["s"],
                    bid_price=float(data["b"]),
                    ask_price=float(data["a"]),
                    timestamp=int(time.time() * 1000)
                )

                base, quote = self._parse_symbol(tick.symbol)
                if not base or not quote:
                    continue

                async with self.lock:
                    # Sell BASE for QUOTE (bid price), applying the fee
                    self.engine.add_rate(base, quote, tick.bid_price * fee_multiplier)

                    if tick.ask_price > 0:
                        # Buy BASE with QUOTE (ask price), applying the fee
                        self.engine.add_rate(quote, base, (1.0 / tick.ask_price) * fee_multiplier)
                        
            except Exception as e:
                logger.error(f"Processing error: {e}")

    def _parse_symbol(self, symbol: str):
        symbol = symbol.upper()
        for q in config.QUOTE_CURRENCIES:
            if symbol.endswith(q):
                return symbol[:-len(q)], q
        return None, None

    async def _arbitrage_worker(self):
        while len(self.engine.currencies) < self.expected_currencies_count:
            await asyncio.sleep(0.1)

        logger.info("Graph ready. Starting arbitrage detection.")

        while self.keep_running:
            await asyncio.sleep(0.2)

            async with self.lock:
                # Create a fast snapshot of the graph under the lock to avoid blocking the event loop
                graph_snapshot = {node: edges.copy() for node, edges in self.engine.graph.items()}
                currencies_snapshot = self.engine.currencies.copy()

            # Create a temporary engine instance for isolated computation
            temp_engine = Graph()
            temp_engine.graph = graph_snapshot
            temp_engine.currencies = currencies_snapshot

            # Offload Bellman-Ford algorithm to a separate thread
            opportunity = await asyncio.to_thread(
                temp_engine.bellman_ford,
                config.BASE_CURRENCY
            )

            if opportunity and opportunity.expected_profit_pct > config.MIN_PROFIT_PCT:
                logger.info(
                    f"Arbitrage: {opportunity.path} | Net Profit: {opportunity.expected_profit_pct:.4f}%"
                )
                self.order_manager.execute_arbitrage(opportunity)

    async def connect(self):
        while self.keep_running:
            try:
                async with websockets.connect(self.url, ping_interval=None) as ws:
                    listener = asyncio.create_task(self._process_messages(ws))
                    worker = asyncio.create_task(self._arbitrage_worker())

                    done, pending = await asyncio.wait(
                        [listener, worker],
                        return_when=asyncio.FIRST_COMPLETED
                    )

                    for task in pending:
                        task.cancel()

            except Exception as e:
                logger.error(f"Connection error: {e}")
                await asyncio.sleep(5)

            except asyncio.CancelledError:
                logger.info("Stream cancelled.")
                break

    def stop(self):
        self.keep_running = False