import math
import logging
from execution.order_manager import OrderManager
from core.models import ArbitrageOpportunity


class FakeEngine:
    """
    Mock implementation of the Graph engine for isolated testing.
    Provides predefined graph weights without executing the routing algorithms.
    """
    def __init__(self):
        # Define a static market graph yielding a 20% arbitrage profit
        self.graph = {
            "USDT": {"BTC": -math.log(1.0 / 50000.0)},
            "BTC": {"ETH": -math.log(20.0)},
            "ETH": {"USDT": -math.log(3000.0)}
        }


def test_execute_arbitrage_calculates_and_logs_correct_profit(caplog):
    """
    Verifies that OrderManager accurately computes the final balance
    and logs the correct profit metrics for a given arbitrage opportunity.
    """
    # Arrange
    fake_engine = FakeEngine()
    manager = OrderManager(fake_engine)
    manager.initial_balance = 100.0 

    opportunity = ArbitrageOpportunity(
        path=["USDT", "BTC", "ETH", "USDT"],
        expected_profit_pct=20.0
    )

    # Act
    with caplog.at_level(logging.INFO):
        manager.execute_arbitrage(opportunity)

    # Assert
    log_output = caplog.text

    assert "START ARBITRAGE | Path: USDT -> BTC -> ETH -> USDT" in log_output
    assert "FINAL BALANCE: 120.0000" in log_output
    assert "NET PROFIT: 20.0000 (20.0000%)" in log_output