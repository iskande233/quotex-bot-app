import os
from dataclasses import dataclass

@dataclass
class Settings:
    # QUOTEX_MODE: paper | demo | real
    quotex_mode: str = os.getenv("QUOTEX_MODE", "paper").lower()
    paper_mode: bool = os.getenv("PAPER_MODE", "true").lower() == "true"
    quotex_session_token: str = os.getenv("QUOTEX_SESSION_TOKEN", "")
    default_symbol: str = os.getenv("DEFAULT_SYMBOL", "EURUSD-OTC")
    default_timeframe: str = os.getenv("DEFAULT_TIMEFRAME", "M1")
    default_investment: float = float(os.getenv("DEFAULT_INVESTMENT", "1"))
    max_trades: int = int(os.getenv("MAX_TRADES", "10"))
    telegram_enabled: bool = os.getenv("TELEGRAM_ENABLED", "true").lower() == "true"
    telegram_bot_token: str = os.getenv("TELEGRAM_BOT_TOKEN", "7197308817:AAFU77fDScCj_fQJNiElv8IFCLQ08kkufCM")
    telegram_chat_id: str = os.getenv("TELEGRAM_CHAT_ID", "@ltc_36")
    brand_name: str = os.getenv("BRAND_NAME", "SIGNALS QUOTEX DZ")
    entry_lead_seconds: float = float(os.getenv("ENTRY_LEAD_SECONDS", "2.0"))
    result_delay_seconds: float = float(os.getenv("RESULT_DELAY_SECONDS", "5.0"))

settings = Settings()
