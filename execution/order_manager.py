import math
import logging
from config.settings import config
from core.models import ArbitrageOpportunity

logger = logging.getLogger(__name__)


class OrderManager:
    def __init__(self, engine):
        self.engine = engine
        self.initial_balance = config.INITIAL_BALANCE

    def execute_arbitrage(self, opportunity: ArbitrageOpportunity):
        path = opportunity.path
        balance = self.initial_balance

        logger.info("=" * 50)
        logger.info(f"START ARBITRAGE | Path: {' -> '.join(path)}")

        for i in range(len(path) - 1):
            u, v = path[i], path[i + 1]

            # Weight already includes the applied fee
            weight = self.engine.graph[u][v]
            rate = math.exp(-weight)

            balance *= rate 

            logger.info(f"{u} -> {v} | net_rate={rate:.6f} | balance={balance:.4f}")

        profit = balance - self.initial_balance
        pct = (profit / self.initial_balance) * 100

        logger.info(f"FINAL BALANCE: {balance:.4f}")
        logger.info(f"NET PROFIT: {profit:.4f} ({pct:.4f}%)")
        logger.info("=" * 50)