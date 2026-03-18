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
    MIN_PROFIT_PCT: float = 0.1
    FEE: float = 0.001

config = Settings()