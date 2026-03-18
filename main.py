import asyncio
from core.graph_engine import Graph
from exchange.binance_stream import BinanceDataStream
from execution.order_manager import OrderManager

async def main():
    engine = Graph()
    order_manager = OrderManager(engine) 

    stream = BinanceDataStream(engine, order_manager)
    
    await stream.connect()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nProgram terminated by user.")