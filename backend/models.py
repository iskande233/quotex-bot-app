from pydantic import BaseModel, Field
from typing import Literal, Optional
from time import time

Direction = Literal["CALL", "PUT"]
Result = Literal["PENDING", "WIN", "LOSS", "DRAW", "SKIPPED"]

class TradeRequest(BaseModel):
    symbol: str = Field(default="EURUSD-OTC")
    direction: Direction
    amount: float = Field(gt=0, default=1.0)
    duration_seconds: int = Field(default=60, ge=30, le=300)

class TradeRecord(BaseModel):
    id: str
    symbol: str
    direction: Direction
    amount: float
    entry_price: Optional[float] = None
    exit_price: Optional[float] = None
    opened_at: float = Field(default_factory=time)
    scheduled_entry_time: Optional[float] = None
    result_check_time: Optional[float] = None
    closed_at: Optional[float] = None
    result: Result = "PENDING"
    pnl: float = 0.0
    paper: bool = True
    step: int = 0

class BalanceResponse(BaseModel):
    balance: float
    mode: Literal["DEMO", "REAL", "PAPER"] = "PAPER"
    session_pnl: float = 0.0

class BotConfig(BaseModel):
    symbol: str = "EURUSD-OTC"
    timeframe: str = "M1"
    investment_amount: float = 5.0
    max_trades: int = 999
    enabled: bool = False
    use_analysis: bool = True
    manual_direction: Optional[Direction] = "CALL"
    min_confidence: int = Field(default=0, ge=0, le=95)
    analysis_seconds: int = Field(default=8, ge=3, le=60)
    take_profit: float = Field(default=6.0, ge=0)
    stop_loss: float = Field(default=3.0, ge=0)
    max_consecutive_losses: int = Field(default=3, ge=1, le=20)
    cooldown_after_loss_minutes: int = Field(default=2, ge=0, le=60)
    pair_cooldown_minutes: int = Field(default=5, ge=0, le=120)
    strategy_mode: Literal["safe", "normal", "aggressive"] = "normal"
    auto_blacklist_losses: int = Field(default=3, ge=1, le=10)
    martingale_enabled: bool = False
    max_martingale_steps: int = Field(default=1, ge=1, le=2)
    take_profit_enabled: bool = True
    stop_loss_enabled: bool = True

class BotStatus(BaseModel):
    running: bool
    config: BotConfig
    trades_count: int

class LoginRequest(BaseModel):
    email: str
    password: str
    account_type: Literal["demo", "real"] = "demo"
    otp_code: Optional[str] = None

class LoginResponse(BaseModel):
    success: bool
    mode: Literal["DEMO", "REAL", "PAPER"]
    message: str = ""
