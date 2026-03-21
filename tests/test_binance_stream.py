import pytest
import asyncio
import json
import math
from exchange.binance_stream import BinanceDataStream
from core.models import ArbitrageOpportunity
from config.settings import config
from unittest.mock import patch
from config.settings import Settings


# TEST DOUBLES

class SpyEngine:
    """Records incoming rates to verify parsing, fee application, and volumes."""
    def __init__(self):
        self.rates_added = []
        self.currencies = {"BTC", "USDT", "ETH"}
        self.graph = {}
        self.mock_opportunity = None

    def add_rate(self, base: str, quote: str, rate: float, volume: float):
        self.rates_added.append((base, quote, rate, volume))

    def bellman_ford(self, start: str):
        return self.mock_opportunity


class SpyOrderManager:
    def __init__(self, stream_to_stop=None):
        self.executed_opportunities = []
        self.stream_to_stop = stream_to_stop

    def execute_arbitrage(self, opportunity):
        self.executed_opportunities.append(opportunity)
        if self.stream_to_stop:
            self.stream_to_stop.stop()


class FakeWebSocket:
    def __init__(self, messages: list[str]):
        self.messages = messages

    async def __aiter__(self):
        for msg in self.messages:
            yield msg
            await asyncio.sleep(0)


# TESTS

def test_parse_symbol_splits_currencies_correctly():
    stream = BinanceDataStream(SpyEngine(), SpyOrderManager())
    assert stream._parse_symbol("BTCUSDT") == ("BTC", "USDT")
    assert stream._parse_symbol("INVALID") == (None, None)

def test_calculate_expected_currencies():
    test_config = Settings(SYMBOLS=["btcusdt", "ethbtc"])
    with patch("exchange.binance_stream.config", test_config):
        stream = BinanceDataStream(SpyEngine(), SpyOrderManager())
        assert stream.expected_currencies_count == 3

def test_stop_sets_keep_running_false():
    stream = BinanceDataStream(SpyEngine(), SpyOrderManager())
    stream.stop()
    assert stream.keep_running is False

@pytest.mark.asyncio
async def test_process_messages_adds_rates_with_fee_and_volume():
    """Tests if Level 2 array format is parsed and saved correctly."""
    spy_engine = SpyEngine()
    stream = BinanceDataStream(spy_engine, SpyOrderManager())
    
    # Using the @depth format: nested arrays for price and quantity
    fake_json = json.dumps({
        "data": {
            "s": "BTCUSDT", 
            "b": [["50000.0", "1.5"]], 
            "a": [["50010.0", "2.0"]]
        }
    })
    fake_ws = FakeWebSocket([fake_json])
    
    await stream._process_messages(fake_ws)

    assert len(spy_engine.rates_added) == 2
    # Verify the volume was passed correctly (1.5 for bid, 2.0 for ask)
    assert spy_engine.rates_added[0][3] == 1.5
    assert spy_engine.rates_added[1][3] == 2.0

@pytest.mark.asyncio
async def test_arbitrage_worker_executes_on_profitable_opportunity():
    spy_engine = SpyEngine()
    
    # Graph now needs to store tuples: (weight, volume)
    spy_engine.graph = {
        "USDT": {"BTC": (-math.log(1.0 / 50000.0), 10.0)},
        "BTC": {"ETH": (-math.log(20.0), 10.0)},
        "ETH": {"USDT": (-math.log(3000.0), 10.0)}
    }
    spy_engine.currencies = {"USDT", "BTC", "ETH"}
    
    stream = BinanceDataStream(spy_engine, None)
    stream.expected_currencies_count = len(spy_engine.currencies)
    
    spy_manager = SpyOrderManager(stream_to_stop=stream)
    stream.order_manager = spy_manager

    await stream._arbitrage_worker()

    assert len(spy_manager.executed_opportunities) == 1
    assert math.isclose(spy_manager.executed_opportunities[0].expected_profit_pct, 20.0, rel_tol=1e-5)