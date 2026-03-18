from core.graph_engine import Graph
from exchange.binance_stream import BinanceDataStream

def main():
    engine = Graph()

    stream = BinanceDataStream(engine)
    stream.connect()

if __name__ == "__main__":
    main()