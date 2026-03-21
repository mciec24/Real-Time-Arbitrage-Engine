from dataclasses import dataclass, field

@dataclass(frozen=True, slots=True)
class Settings:

    BINANCE_WS_URL: str = "wss://stream.binance.com:9443/stream?streams="
    

    SYMBOLS: list[str] = field(default_factory=lambda: [
        'btcusdt', 'ethusdt', 'ethbtc',
        'bnbusdt', 'bnbbtc', 'bnbeth',
        'solusdt', 'solbtc', 'soleth',
        'adausdt', 'adabtc',
        'xrpusdt', 'xrpbtc',
        'dogeusdt', 'dogebtc'
    ])
    
    QUOTE_CURRENCIES: list[str] = field(default_factory=lambda: ['USDT', 'BTC', 'ETH', 'EUR', 'BNB'])

    BASE_CURRENCY: str = "USDT"
    INITIAL_BALANCE: float = 100.0
    MIN_PROFIT_PCT: float = 0.2
    MAX_LATENCY_MS = 50
    FEE: float = 0.001

config = Settings()