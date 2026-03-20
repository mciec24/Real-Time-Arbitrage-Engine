import asyncio
import json
import time
import websockets
import logging
from typing import Tuple, Optional

from config.settings import config
from core.models import MarketTick
from core.graph_engine import Graph

logger = logging.getLogger(__name__)


class BinanceDataStream:
    """
    Manages real-time WebSocket connections to Binance to consume order book data 
    and continuously evaluates the market for triangular arbitrage opportunities.

    The class runs two concurrent asynchronous tasks:
    1. A listener that updates a shared exchange rate graph with real-time bid/ask prices.
    2. A worker that periodically snapshots the graph and runs a cycle-detection algorithm.
    """

    def __init__(self, engine: Graph, order_manager) -> None:
        """
        Initializes the BinanceDataStream.

        Args:
            engine (Graph): The central graph data structure storing exchange rates.
            order_manager: The component responsible for executing trades when 
                an arbitrage opportunity is found.
        """
        self.engine = engine
        self.order_manager = order_manager
        self.keep_running = True
        self.lock = asyncio.Lock()

        # Build the stream URL for multiple symbols (e.g., btcusdt@bookTicker)
        streams = [f"{s.lower()}@bookTicker" for s in config.SYMBOLS]
        self.url = config.BINANCE_WS_URL + "/".join(streams)

        self.expected_currencies_count = self._calculate_expected_currencies()

    def _calculate_expected_currencies(self) -> int:
        """
        Calculates the total number of unique currencies expected in the graph 
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
        Listens to the WebSocket stream, parses incoming order book updates, 
        and safely updates the shared exchange rate graph.

        Calculates effective exchange rates by applying trading fees. Access 
        to the shared graph is protected by an asyncio Lock to prevent race 
        conditions with the arbitrage worker.

        Args:
            ws: The active websockets connection object.
        """
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

    def _parse_symbol(self, symbol: str) -> Tuple[Optional[str], Optional[str]]:
        """
        Splits a single Binance trading symbol into its base and quote currencies.

        Args:
            symbol (str): The raw trading pair symbol (e.g., 'BTCUSDT').

        Returns:
            Tuple[Optional[str], Optional[str]]: A tuple containing the base 
            currency and quote currency, or (None, None) if the quote currency 
            is not found in the configuration.
        """
        symbol = symbol.upper()
        for q in config.QUOTE_CURRENCIES:
            if symbol.endswith(q):
                return symbol[:-len(q)], q
        return None, None

    async def _arbitrage_worker(self) -> None:
        """
        Periodically checks the graph for negative-weight cycles (arbitrage opportunities).

        To ensure high performance and prevent blocking the asyncio event loop:
        1. It takes a rapid, locked snapshot of the graph data.
        2. It creates an isolated Graph instance.
        3. It offloads the CPU-bound Bellman-Ford algorithm to a separate thread.
        """
        # Wait until the graph is sufficiently populated before starting
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

            # Offload CPU-bound Bellman-Ford algorithm to a separate thread
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
        Establishes the WebSocket connection to Binance and manages the lifecycle 
        of the background tasks (listener and worker).

        Implements automatic reconnection logic in case of connection drops.
        """
        while self.keep_running:
            try:
                async with websockets.connect(self.url, ping_interval=None) as ws:
                    listener = asyncio.create_task(self._process_messages(ws))
                    worker = asyncio.create_task(self._arbitrage_worker())

                    # Wait for either task to finish or fail
                    done, pending = await asyncio.wait(
                        [listener, worker],
                        return_when=asyncio.FIRST_COMPLETED
                    )

                    # Cancel any remaining tasks before restarting the connection
                    for task in pending:
                        task.cancel()

            except Exception as e:
                logger.error(f"Connection error: {e}")
                await asyncio.sleep(5)  # Backoff before reconnecting

            except asyncio.CancelledError:
                logger.info("Stream cancelled.")
                break

    def stop(self) -> None:
        """
        Signals the stream and worker tasks to shut down gracefully.
        """
        self.keep_running = False