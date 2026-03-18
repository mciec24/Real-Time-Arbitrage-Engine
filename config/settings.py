from dataclasses import dataclass, field

@dataclass
class Settings:
    BINANCE_WS_URL: str = "wss://stream.binance.com:9443/stream?streams="
    SYMBOLS: list[str] = field(default_factory=lambda: ['btcusdt', 'ethusdt', 'ethbtc'])
    QUOTE_CURRENCIES: list[str] = field(default_factory=lambda: ['USDT', 'BTC', 'ETH', 'EUR', 'BNB'])
    BASE_CURRENCY: str = "USDT"
    MIN_PROFIT_PCT: float = 0.1
# Tworzymy jeden, globalny obiekt 'config' (wzorzec Singleton).
config = Settings()