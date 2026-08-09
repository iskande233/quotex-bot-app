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
    closed_at: Optional[float] = None
    result: Result = "PENDING"
    pnl: float = 0.0
    paper: bool = True

class BalanceResponse(BaseModel):
    balance: float
    mode: Literal["DEMO", "REAL", "PAPER"] = "PAPER"
    session_pnl: float = 0.0

class BotConfig(BaseModel):
    symbol: str = "EURUSD-OTC"
    timeframe: str = "M1"
    investment_amount: float = 1.0
    max_trades: int = 10
    enabled: bool = False

class BotStatus(BaseModel):
    running: bool
    config: BotConfig
    trades_count: int

class LoginRequest(BaseModel):
    email: str
    password: str
    account_type: Literal["demo", "real"] = "demo"

class LoginResponse(BaseModel):
    success: bool
    mode: Literal["DEMO", "REAL", "PAPER"]
    message: str = ""
