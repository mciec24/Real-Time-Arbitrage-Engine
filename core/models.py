from dataclasses import dataclass

@dataclass(slots=True)
class MarketTick:
    """
    Represents a real-time snapshot of the order book for a given trading symbol.
    Contains the highest bid and lowest ask prices at a specific Unix timestamp in milliseconds.
    """
    symbol: str
    bid_price: float
    ask_price: float
    timestamp: int

@dataclass(slots=True)
class ArbitrageOpportunity:
    """
    Encapsulates a detected cyclical arbitrage opportunity.
    Stores the sequence of currencies forming the profitable cycle and the expected net profit percentage.
    """
    path: list[str]
    expected_profit_pct: float