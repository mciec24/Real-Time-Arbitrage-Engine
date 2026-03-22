from dataclasses import dataclass

@dataclass(slots=True, frozen=True)
class MarketTick:
    """
    Represents a real-time snapshot of the order book for a given trading symbol.
    
    Contains the highest bid price, lowest ask price, and their available volumes
    at a specific Unix timestamp in milliseconds. This is crucial for calculating
    maximum trade execution size to prevent slippage.
    """
    symbol: str
    bid_price: float
    bid_qty: float 
    ask_price: float
    ask_qty: float 
    timestamp: int

@dataclass(slots=True, frozen=True)
class ArbitrageOpportunity:
    """
    Encapsulates a detected cyclical arbitrage opportunity.
    
    Stores the sequence of currencies, the theoretically expected profit percentage,
    and the bottleneck capacity (maximum execution amount) along the path.
    """
    path: list[str]
    expected_profit_pct: float
    max_trade_amount: float 