import asyncio
import json
import time
import websockets
import logging
from typing import Tuple, Optional

from config.settings import config
from core.models import MarketTick
from core.graph_engine import Graph
from execution.order_manager import OrderManager

logger = logging.getLogger(__name__)


class BinanceDataStream:
    """
    Manages real-time WebSocket connections to Binance to consume order book data 
    and evaluates the market for triangular arbitrage opportunities.

    Executes two concurrent asynchronous tasks:
    1. A listener updating a shared exchange rate graph with real-time bid/ask prices and volumes.
    2. A worker periodically snapshotting the graph and executing cycle detection.
    """

    def __init__(self, engine: Graph, order_manager: OrderManager) -> None:
        """
        Initializes the BinanceDataStream.

        Args:
            engine (Graph): The central graph data structure storing exchange rates.
            order_manager (OrderManager): Component responsible for executing trades.
        """
        self.engine = engine
        self.order_manager = order_manager
        self.keep_running = True
        self.lock = asyncio.Lock()

        streams = [f"{s.lower()}@depth@100ms" for s in config.SYMBOLS]
        self.url = config.BINANCE_WS_URL + "/".join(streams)

        self.expected_currencies_count = self._calculate_expected_currencies()

    def _calculate_expected_currencies(self) -> int:
        """
        Calculates the expected number of unique currencies in the graph 
        based on the configured trading symbols.

        Returns:
            int: The number of unique base and quote currencies.
        """
        currencies = set()
        for symbol in config.SYMBOLS:
            symbol = symbol.upper()
            for q in config.QUOTE_CURRENCIES:
                if symbol.endswith(q):
                    currencies.add(q)
                    currencies.add(symbol[:-len(q)])
                    break
        return len(currencies)

    async def _process_messages(self, ws) -> None:
        """
        Listens to the WebSocket stream, parses Level 2 order book updates,
        drops stale packets, and safely updates the graph with rate and liquidity data.
        """
        fee_multiplier = 1.0 - config.FEE
        MAX_LATENCY_MS = 50 

        async for message in ws:
            if not self.keep_running:
                break

            try:
                data = json.loads(message).get("data")
                if not data:
                    continue

                # Latency check
                exchange_time = data.get("E") or data.get("T")
                current_local_time = int(time.time() * 1000)

                if exchange_time:
                    latency = current_local_time - exchange_time
                    if latency > MAX_LATENCY_MS:
                        logger.debug(f"Dropped stale packet for {data.get('s')}. Latency: {latency}ms")
                        continue
                    timestamp = exchange_time
                else:
                    timestamp = current_local_time

                # Parse Level 2 Order Book Depth
                if "b" not in data or "a" not in data:
                    continue

                if not data["b"] or not data["a"]:
                    continue

                raw_bid_p, raw_bid_q = data["b"][0][0], data["b"][0][1]
                raw_ask_p, raw_ask_q = data["a"][0][0], data["a"][0][1]

                tick = MarketTick(
                    symbol=data["s"],
                    bid_price=float(raw_bid_p),
                    bid_qty=float(raw_bid_q),
                    ask_price=float(raw_ask_p),
                    ask_qty=float(raw_ask_q),
                    timestamp=timestamp
                )

                base, quote = self._parse_symbol(tick.symbol)
                if not base or not quote:
                    continue

                async with self.lock:
                    # Note: Base volume is used directly as a simplification for the MVP.
                    # In a production system, this volume should be normalized to config.BASE_CURRENCY.
                    volume_base = tick.bid_qty
                    self.engine.add_rate(base, quote, tick.bid_price * fee_multiplier, volume_base)

                    if tick.ask_price > 0:
                        volume_base = tick.ask_qty
                        self.engine.add_rate(quote, base, (1.0 / tick.ask_price) * fee_multiplier, volume_base)
                        
            except Exception as e:
                logger.error(f"Processing error: {e}")

    def _parse_symbol(self, symbol: str) -> Tuple[Optional[str], Optional[str]]:
        """
        Splits a single Binance trading symbol into its base and quote currencies.

        Args:
            symbol (str): The raw trading pair symbol (e.g., 'BTCUSDT').

        Returns:
            Tuple[Optional[str], Optional[str]]: A tuple containing the base 
            and quote currency, or (None, None) if the quote currency is not found.
        """
        symbol = symbol.upper()
        for q in config.QUOTE_CURRENCIES:
            if symbol.endswith(q):
                return symbol[:-len(q)], q
        return None, None

    async def _arbitrage_worker(self) -> None:
        """
        Periodically checks the graph for negative-weight cycles (arbitrage opportunities).

        Takes a locked snapshot of the graph and offloads the CPU-bound Bellman-Ford 
        algorithm to a separate thread to prevent event loop blocking.
        """
        while len(self.engine.currencies) < self.expected_currencies_count:
            await asyncio.sleep(0.1)

        logger.info("Graph ready. Starting arbitrage detection.")

        while self.keep_running:
            await asyncio.sleep(0.2)

            async with self.lock:
                graph_snapshot = {node: edges.copy() for node, edges in self.engine.graph.items()}
                currencies_snapshot = self.engine.currencies.copy()

            temp_engine = Graph()
            temp_engine.graph = graph_snapshot
            temp_engine.currencies = currencies_snapshot

            opportunity = await asyncio.to_thread(
                temp_engine.bellman_ford,
                config.BASE_CURRENCY
            )

            if opportunity and opportunity.expected_profit_pct > config.MIN_PROFIT_PCT:
                logger.info(
                    f"Arbitrage: {opportunity.path} | Net Profit: {opportunity.expected_profit_pct:.4f}%"
                )
                self.order_manager.execute_arbitrage(opportunity)

    async def connect(self) -> None:
        """
        Establishes the WebSocket connection and manages background tasks.
        Implements automatic reconnection logic for dropped connections.
        """
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

    def stop(self) -> None:
        """Signals tasks to shut down."""
        self.keep_running = False