import asyncio
import json
import time
import websockets
import logging
from websockets.client import WebSocketClientProtocol

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

    async def _process_messages(self, ws: WebSocketClientProtocol) -> None:
        """
        Listens to the WebSocket stream, applies defensive parsing, 
        drops stale packets, and safely updates the graph.
        """
        fee_multiplier = 1.0 - config.FEE

        async for message in ws:
            if not self.keep_running:
                break

            try:
                data = json.loads(message).get("data")
                if not data:
                    continue

                # Latency check using configuration
                exchange_time = data.get("E") or data.get("T")
                current_local_time = int(time.time() * 1000)

                if exchange_time:
                    latency = current_local_time - exchange_time
                    if latency > config.MAX_LATENCY_MS:
                        logger.debug(f"Dropped stale packet for {data.get('s')}. Latency: {latency}ms")
                        continue
                    timestamp = exchange_time
                else:
                    timestamp = current_local_time

                # Safe parsing using get() with default empty lists
                bids = data.get("b", [])
                asks = data.get("a", [])

                if not bids or not asks:
                    continue

                # Defensive programming against malformed payload structures
                try:
                    raw_bid_p, raw_bid_q = float(bids[0][0]), float(bids[0][1])
                    raw_ask_p, raw_ask_q = float(asks[0][0]), float(asks[0][1])
                except (IndexError, ValueError, TypeError) as e:
                    logger.debug(f"Skipped malformed packet for {data.get('s')}: {e}")
                    continue

                tick = MarketTick(
                    symbol=data["s"],
                    bid_price=raw_bid_p,
                    bid_qty=raw_bid_q,
                    ask_price=raw_ask_p,
                    ask_qty=raw_ask_q,
                    timestamp=timestamp
                )

                base, quote = self._parse_symbol(tick.symbol)
                if not base or not quote:
                    continue

                async with self.lock:
                    volume_base = tick.bid_qty
                    self.engine.add_rate(base, quote, tick.bid_price * fee_multiplier, volume_base)

                    if tick.ask_price > 0:
                        volume_base = tick.ask_qty
                        self.engine.add_rate(quote, base, (1.0 / tick.ask_price) * fee_multiplier, volume_base)
                        
            except json.JSONDecodeError:
                logger.error("JSON decoding error from stream.")
            except Exception as e:
                logger.error(f"Unexpected processing error: {e}")

    def _parse_symbol(self, symbol: str) -> tuple[str | None, str | None]:
        """Splits a single Binance trading symbol into its base and quote currencies."""
        symbol = symbol.upper()
        for q in config.QUOTE_CURRENCIES:
            if symbol.endswith(q):
                return symbol[:-len(q)], q
        return None, None

    async def _arbitrage_worker(self) -> None:
        """Periodically checks the graph for negative-weight cycles."""
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
        Implements Exponential Backoff reconnection logic for dropped connections.
        """
        base_retry_delay = 1.0
        max_retry_delay = 60.0
        retry_delay = base_retry_delay

        while self.keep_running:
            try:
                async with websockets.connect(self.url, ping_interval=None) as ws:
                    logger.info("Successfully connected to Binance stream.")
                    # Reset delay on successful connection
                    retry_delay = base_retry_delay 

                    listener = asyncio.create_task(self._process_messages(ws))
                    worker = asyncio.create_task(self._arbitrage_worker())

                    done, pending = await asyncio.wait(
                        [listener, worker],
                        return_when=asyncio.FIRST_COMPLETED
                    )

                    for task in pending:
                        task.cancel()

            except (websockets.ConnectionClosed, ConnectionRefusedError) as e:
                logger.warning(f"Connection dropped: {e}. Retrying in {retry_delay}s...")
                await asyncio.sleep(retry_delay)
                # Exponential backoff
                retry_delay = min(retry_delay * 2, max_retry_delay)

            except Exception as e:
                logger.error(f"Critical connection error: {e}. Retrying in {retry_delay}s...")
                await asyncio.sleep(retry_delay)
                retry_delay = min(retry_delay * 2, max_retry_delay)

            except asyncio.CancelledError:
                logger.info("Stream cancelled (shutting down).")
                break
            
    def stop(self) -> None:
        """Signals tasks to shut down."""
        self.keep_running = False