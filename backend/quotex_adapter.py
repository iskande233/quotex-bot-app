from __future__ import annotations
from abc import ABC, abstractmethod
from random import random
from time import time
from models import TradeRequest, TradeRecord, BalanceResponse

class QuotexAdapter(ABC):
    mode = "PAPER"

    @abstractmethod
    async def connect(self) -> None: ...

    @abstractmethod
    async def get_balance(self) -> BalanceResponse: ...

    @abstractmethod
    async def place_trade(self, req: TradeRequest) -> TradeRecord: ...

    @abstractmethod
    async def latest_price(self, symbol: str) -> float: ...

class PaperQuotexAdapter(QuotexAdapter):
    mode = "PAPER"

    def __init__(self, starting_balance: float = 1000.0):
        self.balance = starting_balance
        self.session_pnl = 0.0
        self._price_by_symbol: dict[str, float] = {}

    async def connect(self) -> None:
        return None

    async def get_balance(self) -> BalanceResponse:
        return BalanceResponse(balance=self.balance, mode=self.mode, session_pnl=self.session_pnl)

    async def latest_price(self, symbol: str) -> float:
        base = self._price_by_symbol.get(symbol)
        if base is None:
            # Stable deterministic-ish starting price per symbol.
            base = 1.0 + (abs(hash(symbol)) % 5000) / 100000
        base += (random() - 0.5) * 0.0012
        self._price_by_symbol[symbol] = base
        return round(base, 6)

    async def place_trade(self, req: TradeRequest) -> TradeRecord:
        price = await self.latest_price(req.symbol)
        return TradeRecord(
            id=f"{self.mode.lower()}_{int(time()*1000)}",
            symbol=req.symbol,
            direction=req.direction,
            amount=req.amount,
            entry_price=price,
            paper=self.mode != "REAL",
        )

class DemoQuotexAdapter(PaperQuotexAdapter):
    """Demo-account adapter scaffold.

    Currently simulated like paper mode, but separated so a legitimate Quotex
    demo-session wrapper can be connected later without touching the API/UI.
    """
    mode = "DEMO"

class RealQuotexAdapter(QuotexAdapter):
    mode = "REAL"

    """Placeholder for a compliant Quotex API/WebSocket wrapper.

    Implement this only with user-owned credentials/session and in compliance
    with the platform's terms. Keep secrets in environment variables.
    """
    async def connect(self) -> None:
        raise NotImplementedError("Real Quotex adapter not connected yet")

    async def get_balance(self) -> BalanceResponse:
        raise NotImplementedError("Real Quotex adapter not connected yet")

    async def place_trade(self, req: TradeRequest) -> TradeRecord:
        raise NotImplementedError("Real Quotex adapter not connected yet")

    async def latest_price(self, symbol: str) -> float:
        raise NotImplementedError("Real Quotex adapter not connected yet")
