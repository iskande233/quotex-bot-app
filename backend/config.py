import os
from dataclasses import dataclass

@dataclass
class Settings:
    paper_mode: bool = os.getenv("PAPER_MODE", "true").lower() == "true"
    quotex_session_token: str = os.getenv("QUOTEX_SESSION_TOKEN", "")
    default_symbol: str = os.getenv("DEFAULT_SYMBOL", "EURUSD-OTC")
    default_timeframe: str = os.getenv("DEFAULT_TIMEFRAME", "M1")
    default_investment: float = float(os.getenv("DEFAULT_INVESTMENT", "1"))
    max_trades: int = int(os.getenv("MAX_TRADES", "10"))

settings = Settings()
