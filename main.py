import asyncio
import logging
import signal

from core.graph_engine import Graph
from exchange.binance_stream import BinanceDataStream
from execution.order_manager import OrderManager


def setup_logging():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )


async def main():
    setup_logging()
    logger = logging.getLogger("main")

    logger.info("Starting Real-Time Arbitrage Engine...")

    engine = Graph()
    order_manager = OrderManager(engine)
    stream = BinanceDataStream(engine, order_manager)

    stop_event = asyncio.Event()

    def shutdown():
        logger.info("Shutdown signal received...")
        stream.keep_running = False
        stop_event.set()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, shutdown)

    # Start stream as a background task
    stream_task = asyncio.create_task(stream.connect())

    # Wait for termination signal
    await stop_event.wait()

    logger.info("Stopping stream...")

    # Cancel the stream task
    stream_task.cancel()

    try:
        await stream_task
    except asyncio.CancelledError:
        logger.info("Stream task cancelled.")

    logger.info("Shutdown complete.")


if __name__ == "__main__":
    asyncio.run(main())