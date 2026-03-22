import asyncio
import logging
import signal
import sys

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

    # Start the stream as a background task
    stream_task = asyncio.create_task(stream.connect())

    # Cross-platform Graceful Shutdown handling
    loop = asyncio.get_running_loop()
    stop_event = asyncio.Event()

    def shutdown_handler(*args):
        logger.info("Shutdown signal received. Initiating graceful shutdown...")
        stream.stop()  # Sets keep_running = False to stop the loops
        stop_event.set()

    # Attempt Unix/Linux/Mac signal registration
    try:
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, shutdown_handler)
    except NotImplementedError:
        # Fallback for Windows
        signal.signal(signal.SIGINT, shutdown_handler)
        signal.signal(signal.SIGTERM, shutdown_handler)

    # Wait for the shutdown signal
    await stop_event.wait()

    # Wait for the main stream task to finish cleanly
    logger.info("Waiting for stream tasks to close...")
    await asyncio.gather(stream_task, return_exceptions=True)

    # Cancel any orphaned background tasks to prevent "Task was destroyed but it is pending!" errors
    tasks = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
    for task in tasks:
        task.cancel()
    
    await asyncio.gather(*tasks, return_exceptions=True)
    logger.info("Application shut down successfully and safely.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass  # Ignore the ugly traceback on manual Ctrl+C