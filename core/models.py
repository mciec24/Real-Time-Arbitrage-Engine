from dataclasses import dataclass

@dataclass(slots = True)
class MarketTick:
    symbol: str
    bid_price: float
    ask_price: float
    timestamp: int

@dataclass(slots = True)
class ArbitrageOpportunity:
    path: list[str]
    expected_profit_pct: float