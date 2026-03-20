import math
import logging
from typing import TYPE_CHECKING

from config.settings import config
from core.models import ArbitrageOpportunity

# Used for type hinting without causing circular imports if Graph is imported elsewhere
if TYPE_CHECKING:
    from core.graph_engine import Graph

logger = logging.getLogger(__name__)


class OrderManager:
    """
    Manages the execution of trading orders for detected arbitrage opportunities.

    Currently configured for 'paper trading' (simulation). It traverses the 
    detected arbitrage path, calculates the step-by-step balance changes using 
    the fee-adjusted exchange rates, and logs the expected profit without 
    interacting with the live exchange API.
    """

    def __init__(self, engine: 'Graph') -> None:
        """
        Initializes the OrderManager with a reference to the market graph and 
        the starting capital.

        Args:
            engine (Graph): The central graph data structure containing the latest 
                fee-adjusted exchange rates.
        """
        self.engine = engine
        self.initial_balance = config.INITIAL_BALANCE

    def execute_arbitrage(self, opportunity: ArbitrageOpportunity) -> None:
        """
        Simulates the execution of a series of trades along an arbitrage path.

        Iterates through the sequence of currencies in the negative-weight cycle,
        reverts the log-transformed edge weights back to actual exchange rates,
        and computes the final balance. Logs the entire process for debugging 
        and validation purposes.

        Args:
            opportunity (ArbitrageOpportunity): An object containing the cyclic 
                path of currencies and the theoretically expected profit percentage.
        """
        path = opportunity.path
        balance = self.initial_balance

        logger.info("=" * 50)
        logger.info(f"START ARBITRAGE | Path: {' -> '.join(path)}")

        for i in range(len(path) - 1):
            u, v = path[i], path[i + 1]

            # The weight in the graph is the negative log of the fee-adjusted rate
            weight = self.engine.graph[u][v]
            
            # Revert the negative natural logarithm back to the standard exchange rate
            rate = math.exp(-weight)

            # Update balance by simulating the trade
            balance *= rate 

            logger.info(f"{u} -> {v} | net_rate={rate:.6f} | balance={balance:.4f}")

        profit = balance - self.initial_balance
        pct = (profit / self.initial_balance) * 100

        logger.info(f"FINAL BALANCE: {balance:.4f}")
        logger.info(f"NET PROFIT: {profit:.4f} ({pct:.4f}%)")
        logger.info("=" * 50)