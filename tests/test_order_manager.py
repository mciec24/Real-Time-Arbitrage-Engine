import math
import logging
from execution.order_manager import OrderManager
from core.models import ArbitrageOpportunity


class FakeEngine:
    """Mock implementation providing tuple-based graph weights (weight, volume)."""
    def __init__(self):
        self.graph = {
            "USDT": {"BTC": (-math.log(1.0 / 50000.0), 5.0)},
            "BTC": {"ETH": (-math.log(20.0), 10.0)},
            "ETH": {"USDT": (-math.log(3000.0), 5.0)}
        }


def test_execute_arbitrage_calculates_and_logs_correct_profit(caplog):
    """
    Verifies OrderManager computes final balance and limits execution to bottleneck.
    """
    fake_engine = FakeEngine()
    manager = OrderManager(fake_engine)
    manager.initial_balance = 100.0 

    # Bottleneck is exactly equal to our balance (100.0 vs max 100.0)
    opportunity = ArbitrageOpportunity(
        path=["USDT", "BTC", "ETH", "USDT"],
        expected_profit_pct=20.0,
        max_trade_amount=150.0 # High liquidity, should use initial_balance
    )

    with caplog.at_level(logging.INFO):
        manager.execute_arbitrage(opportunity)

    log_output = caplog.text

    assert "START ARBITRAGE | Path: USDT -> BTC -> ETH -> USDT" in log_output
    assert "EXECUTION SIZE: 100.0000" in log_output
    assert "FINAL BALANCE: 120.0000" in log_output
    assert "NET PROFIT: 20.0000 (20.0000%)" in log_output

def test_execute_arbitrage_restricts_size_to_bottleneck(caplog):
    """
    Verifies that the manager restricts trade size when market liquidity is low.
    """
    fake_engine = FakeEngine()
    manager = OrderManager(fake_engine)
    manager.initial_balance = 100.0 

    # Very low liquidity (only 10.0 available)
    opportunity = ArbitrageOpportunity(
        path=["USDT", "BTC", "ETH", "USDT"],
        expected_profit_pct=20.0,
        max_trade_amount=10.0 
    )

    with caplog.at_level(logging.INFO):
        manager.execute_arbitrage(opportunity)

    log_output = caplog.text

    assert "EXECUTION SIZE: 10.0000 (Bottleneck: 10.0000)" in log_output
    assert "FINAL BALANCE: 12.0000" in log_output  # 20% on 10.0 is 2.0
    assert "NET PROFIT: 2.0000" in log_output