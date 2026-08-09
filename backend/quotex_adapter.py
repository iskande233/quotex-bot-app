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

class PyQuotexAdapter(QuotexAdapter):
    """pyquotex / Quotex wrapper integration adapter.

    This adapter intentionally imports the wrapper dynamically because different
    GitHub forks expose different module/class names. The default implementation
    targets the common pattern:

        from pyquotex.stable_api import Quotex

    If your selected wrapper uses different method names, update this class only.
    Credentials are kept in memory and are never written to disk.
    """

    def __init__(self, email: str, password: str, account_type: str = "demo"):
        self.email = email
        self.password = password
        self.account_type = account_type.lower()
        self.mode = "REAL" if self.account_type == "real" else "DEMO"
        self.client = None
        self.connected = False

    def _load_client_class(self):
        try:
            from pyquotex.stable_api import Quotex  # type: ignore
            return Quotex
        except Exception as e:
            raise RuntimeError(
                "pyquotex wrapper is not installed or has a different API. "
                "Install your chosen wrapper on the backend, then adjust PyQuotexAdapter._load_client_class()."
            ) from e

    async def connect(self) -> None:
        Quotex = self._load_client_class()
        self.client = Quotex(email=self.email, password=self.password)
        # Common wrappers use either connect() or async connect().
        result = self.client.connect()
        if hasattr(result, "__await__"):
            result = await result
        # Switch account balance mode if wrapper supports it.
        for method_name in ("change_balance", "set_account_type", "set_balance_mode"):
            method = getattr(self.client, method_name, None)
            if callable(method):
                try:
                    r = method("PRACTICE" if self.mode == "DEMO" else "REAL")
                    if hasattr(r, "__await__"):
                        await r
                    break
                except Exception:
                    pass
        self.connected = True

    async def get_balance(self) -> BalanceResponse:
        if not self.connected:
            await self.connect()
        balance = 0.0
        for method_name in ("get_balance", "balance"):
            method = getattr(self.client, method_name, None)
            if callable(method):
                value = method()
                if hasattr(value, "__await__"):
                    value = await value
                try:
                    balance = float(value)
                    break
                except Exception:
                    pass
        return BalanceResponse(balance=balance, mode=self.mode, session_pnl=0.0)

    async def latest_price(self, symbol: str) -> float:
        if not self.connected:
            await self.connect()
        # Wrapper-specific. Try common candle methods; otherwise fail clearly.
        for method_name in ("get_candles", "candles", "get_realtime_candles"):
            method = getattr(self.client, method_name, None)
            if callable(method):
                data = method(symbol, 60, 2)
                if hasattr(data, "__await__"):
                    data = await data
                try:
                    last = data[-1] if isinstance(data, list) else list(data.values())[-1]
                    return float(last.get("close") or last.get("price") or last["c"])
                except Exception:
                    continue
        raise NotImplementedError("Selected pyquotex wrapper price method is not mapped yet")

    async def place_trade(self, req: TradeRequest) -> TradeRecord:
        if not self.connected:
            await self.connect()
        direction = "call" if req.direction == "CALL" else "put"
        price = await self.latest_price(req.symbol)
        for method_name in ("buy", "trade", "place_order"):
            method = getattr(self.client, method_name, None)
            if callable(method):
                result = method(req.amount, req.symbol, direction, req.duration_seconds)
                if hasattr(result, "__await__"):
                    result = await result
                trade_id = None
                try:
                    if isinstance(result, tuple):
                        trade_id = str(result[1] if len(result) > 1 else result[0])
                    elif isinstance(result, dict):
                        trade_id = str(result.get("id") or result.get("order_id") or result)
                    else:
                        trade_id = str(result)
                except Exception:
                    trade_id = f"pyquotex_{int(time()*1000)}"
                return TradeRecord(
                    id=trade_id or f"pyquotex_{int(time()*1000)}",
                    symbol=req.symbol,
                    direction=req.direction,
                    amount=req.amount,
                    entry_price=price,
                    paper=self.mode != "REAL",
                )
        raise NotImplementedError("Selected pyquotex wrapper trade method is not mapped yet")
