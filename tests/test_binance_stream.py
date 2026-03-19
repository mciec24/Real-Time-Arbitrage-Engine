import pytest
import asyncio
import json
import math
from exchange.binance_stream import BinanceDataStream
from core.models import ArbitrageOpportunity
from config.settings import config
from unittest.mock import patch
from config.settings import Settings


# TEST DOUBLES (Mocks & Spies)

class SpyEngine:
    """
    A spy object simulating the Graph Engine. 
    Records incoming rates to verify parsing and fee application.
    """
    def __init__(self):
        self.rates_added = []
        # Pre-populate currencies to prevent the worker from waiting indefinitely during tests
        self.currencies = {"BTC", "USDT", "ETH"}
        self.graph = {}
        
        # Control variable for the mock Bellman-Ford return value (if needed)
        self.mock_opportunity = None

    def add_rate(self, base: str, quote: str, rate: float):
        self.rates_added.append((base, quote, rate))

    def bellman_ford(self, start: str):
        return self.mock_opportunity


class SpyOrderManager:
    """
    A spy object to verify if the system attempted to execute a profitable trade.
    It also halts the background stream worker after the first execution to prevent infinite loops.
    """
    def __init__(self, stream_to_stop=None):
        self.executed_opportunities = []
        self.stream_to_stop = stream_to_stop

    def execute_arbitrage(self, opportunity):
        self.executed_opportunities.append(opportunity)
        # Stop the infinite loop in _arbitrage_worker after the first valid execution
        if self.stream_to_stop:
            self.stream_to_stop.stop()


class FakeWebSocket:
    """
    An asynchronous iterator simulating an incoming WebSocket data stream.
    """
    def __init__(self, messages: list[str]):
        self.messages = messages

    async def __aiter__(self):
        for msg in self.messages:
            yield msg
            # Yield control back to the event loop to simulate async I/O
            await asyncio.sleep(0)



# TESTS


def test_parse_symbol_splits_currencies_correctly():
    """Tests if the stream correctly splits the raw symbol string into base and quote currencies."""
    stream = BinanceDataStream(SpyEngine(), SpyOrderManager())
    assert stream._parse_symbol("BTCUSDT") == ("BTC", "USDT")
    assert stream._parse_symbol("INVALID") == (None, None)

def test_calculate_expected_currencies():
    """Tests if the stream correctly calculates the number of unique expected currencies from the configuration."""
    test_config = Settings(SYMBOLS=["btcusdt", "ethbtc"])
    
    with patch("exchange.binance_stream.config", test_config):
        stream = BinanceDataStream(SpyEngine(), SpyOrderManager())
        assert stream.expected_currencies_count == 3

def test_stop_sets_keep_running_false():
    """Tests if the graceful shutdown mechanism correctly sets the internal running flag."""
    stream = BinanceDataStream(SpyEngine(), SpyOrderManager())
    assert stream.keep_running is True
    
    stream.stop()
    assert stream.keep_running is False

@pytest.mark.asyncio
async def test_process_messages_adds_rates_with_fee():
    """Tests if the incoming raw JSON messages are parsed and saved to the engine with applied fees."""
    spy_engine = SpyEngine()
    stream = BinanceDataStream(spy_engine, SpyOrderManager())
    
    fake_json = json.dumps({"data": {"s": "BTCUSDT", "b": "50000.0", "a": "50010.0"}})
    fake_ws = FakeWebSocket([fake_json])
    
    await stream._process_messages(fake_ws)

    assert len(spy_engine.rates_added) == 2

@pytest.mark.asyncio
async def test_arbitrage_worker_executes_on_profitable_opportunity():
    """
    Tests the main background worker. Injects a mathematically profitable graph,
    runs the worker, and verifies if the execution command was dispatched with the correct profit.
    """
    spy_engine = SpyEngine()
    
    # Inject a mathematically valid market with a 20% hidden arbitrage opportunity
    spy_engine.graph = {
        "USDT": {"BTC": -math.log(1.0 / 50000.0)},
        "BTC": {"ETH": -math.log(20.0)},
        "ETH": {"USDT": -math.log(3000.0)}
    }
    spy_engine.currencies = {"USDT", "BTC", "ETH"}
    
    stream = BinanceDataStream(spy_engine, None)
    stream.expected_currencies_count = len(spy_engine.currencies)
    
    spy_manager = SpyOrderManager(stream_to_stop=stream)
    stream.order_manager = spy_manager

    await stream._arbitrage_worker()

    assert len(spy_manager.executed_opportunities) == 1
    assert math.isclose(spy_manager.executed_opportunities[0].expected_profit_pct, 20.0, rel_tol=1e-5)