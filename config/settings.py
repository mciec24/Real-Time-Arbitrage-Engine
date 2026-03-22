from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    """
    Global application configuration.
    Utilizes Pydantic for strict type validation and environment variable 
    parsing (.env support), essential for production deployments.
    """
    
    BINANCE_WS_URL: str = "wss://stream.binance.com:9443/stream?streams="
    
    # Using immutable tuples prevents accidental runtime modifications of tracked symbols.
    SYMBOLS: tuple[str, ...] = Field(
        default=(
            'btcusdt', 'ethusdt', 'ethbtc',
            'bnbusdt', 'bnbbtc', 'bnbeth',
            'solusdt', 'solbtc', 'soleth',
            'adausdt', 'adabtc',
            'xrpusdt', 'xrpbtc',
            'dogeusdt', 'dogebtc'
        )
    )
    
    QUOTE_CURRENCIES: tuple[str, ...] = Field(
        default=('USDT', 'BTC', 'ETH', 'EUR', 'BNB')
    )

    BASE_CURRENCY: str = "USDT"
    
    # Strict validation bounds to prevent logical errors in the engine.
    INITIAL_BALANCE: float = Field(default=100.0, ge=0.0)
    MIN_PROFIT_PCT: float = Field(default=0.2, ge=0.0)
    MAX_LATENCY_MS: int = Field(default=50, gt=0)
    FEE: float = Field(default=0.001, ge=0.0, lt=1.0)

    # Enforce instance immutability and enable .env file overriding.
    model_config = SettingsConfigDict(frozen=True, env_file=".env", env_file_encoding="utf-8")

config = Settings()