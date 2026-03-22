from __future__ import annotations
import math
import logging

from config.settings import config
from core.models import ArbitrageOpportunity
from core.graph_engine import Graph

logger = logging.getLogger(__name__)


class OrderManager:
    """
    Manages the execution of trading orders for detected arbitrage opportunities.

    Currently operates in simulation (paper trading) mode. It traverses the 
    detected path, validates bottleneck capacity against the initial balance, 
    calculates step-by-step balance changes, and logs the execution metrics.
    """

    def __init__(self, engine: Graph) -> None:
        """
        Initializes the OrderManager.

        Args:
            engine (Graph): The central graph structure containing rates and liquidity.
        """
        self.engine = engine
        self.initial_balance = config.INITIAL_BALANCE

    def execute_arbitrage(self, opportunity: ArbitrageOpportunity) -> None:
        """
        Simulates trade execution along an arbitrage path, restricting the 
        trade size to the maximum available liquidity (bottleneck volume).

        Args:
            opportunity (ArbitrageOpportunity): The detected arbitrage cycle details.
        """
        path = opportunity.path
        
        # Restrict execution size to the lower of: configured balance or available market liquidity
        execution_balance = min(self.initial_balance, opportunity.max_trade_amount)
        balance = execution_balance

        logger.info("=" * 50)
        logger.info(f"START ARBITRAGE | Path: {' -> '.join(path)}")
        logger.info(f"EXECUTION SIZE: {execution_balance:.4f} (Bottleneck: {opportunity.max_trade_amount:.4f})")

        for i in range(len(path) - 1):
            u, v = path[i], path[i + 1]

            weight, volume = self.engine.graph[u][v]
            rate = math.exp(-weight)

            balance *= rate 

            logger.info(f"[{u} -> {v}] rate: {rate:.6f} | liquidity: {volume:.4f} | balance: {balance:.4f}")

        profit = balance - execution_balance
        pct = (profit / execution_balance) * 100 if execution_balance > 0 else 0.0

        logger.info(f"FINAL BALANCE: {balance:.4f}")
        logger.info(f"NET PROFIT: {profit:.4f} ({pct:.4f}%)")
        logger.info("=" * 50)