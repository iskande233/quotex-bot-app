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
    """Adapter for mrgawade/pyquotex stable_api.

    Expected wrapper API:
        client = Quotex(email=email, password=password)
        check, reason = client.connect()
        client.change_balance("PRACTICE")
        status, trade_info = client.buy(amount, asset, direction, duration=60)
        balance = client.get_balance()

    Credentials stay in memory only. Demo/PRACTICE is the default.
    """

    def __init__(self, email: str, password: str, account_type: str = "demo"):
        self.email = email
        self.password = password
        self.account_type = account_type.lower()
        self.mode = "REAL" if self.account_type == "real" else "DEMO"
        self.client = None
        self.connected = False
        self.session_pnl = 0.0

    def _load_client_class(self):
        # Different public pyquotex forks expose different package names.
        # Try the two most common stable_api import paths.
        try:
            from pyquotex.stable_api import Quotex  # type: ignore
            return Quotex
        except Exception as first_error:
            try:
                from quotexapi.stable_api import Quotex  # type: ignore
                return Quotex
            except Exception as second_error:
                raise RuntimeError(
                    "pyquotex wrapper is not installed or import path changed. "
                    "requirements.txt uses git+https://github.com/cleitonLeonel/pyquotex.git. "
                    "Tried: pyquotex.stable_api.Quotex and quotexapi.stable_api.Quotex."
                ) from second_error

    async def _maybe_await(self, value):
        if hasattr(value, "__await__"):
            return await value
        return value

    def _asset(self, symbol: str) -> str:
        """Normalize common UI symbols to Quotex asset names.

        Examples:
            EUR/USD OTC -> EURUSD_otc
            EURUSD-OTC  -> EURUSD_otc
            EURUSD_otc  -> EURUSD_otc
        """
        clean = symbol.strip().replace("/", "").replace(" ", "").replace("-", "_")
        if clean.upper().endswith("_OTC"):
            return clean[:-4].upper() + "_otc"
        return clean.upper()

    async def connect(self) -> None:
        Quotex = self._load_client_class()
        self.client = Quotex(email=self.email, password=self.password)
        result = await self._maybe_await(self.client.connect())
        check, reason = True, ""
        if isinstance(result, tuple):
            check = bool(result[0])
            reason = str(result[1]) if len(result) > 1 else ""
        elif isinstance(result, bool):
            check = result
        if not check:
            raise RuntimeError(reason or "Quotex connect failed")

        # Demo by default. Quotex wrappers usually call demo PRACTICE.
        balance_mode = "REAL" if self.mode == "REAL" else "PRACTICE"
        if hasattr(self.client, "change_balance"):
            await self._maybe_await(self.client.change_balance(balance_mode))
        self.connected = True

    async def get_balance(self) -> BalanceResponse:
        if not self.connected:
            await self.connect()
        value = await self._maybe_await(self.client.get_balance())
        try:
            balance = float(value)
        except Exception:
            balance = 0.0
        return BalanceResponse(balance=balance, mode=self.mode, session_pnl=self.session_pnl)

    async def latest_price(self, symbol: str) -> float:
        if not self.connected:
            await self.connect()
        asset = self._asset(symbol)
        # Preferred pyquotex candle call. Forks differ; keep fallbacks.
        for args in ((asset, 60, 2), (asset, 60), (asset,)):
            try:
                candles = await self._maybe_await(self.client.get_candles(*args))
                if isinstance(candles, dict):
                    values = list(candles.values())
                    last = values[-1]
                else:
                    last = candles[-1]
                if isinstance(last, dict):
                    return float(last.get("close") or last.get("price") or last.get("c"))
                if isinstance(last, (list, tuple)):
                    return float(last[-1])
            except Exception:
                continue
        raise NotImplementedError("pyquotex get_candles mapping failed for asset " + asset)

    async def place_trade(self, req: TradeRequest) -> TradeRecord:
        if not self.connected:
            await self.connect()
        asset = self._asset(req.symbol)
        direction = "call" if req.direction == "CALL" else "put"
        entry_price = None
        try:
            entry_price = await self.latest_price(req.symbol)
        except Exception:
            pass

        # Required wrapper API: status, trade_info = client.buy(amount, asset, direction, duration=60)
        result = await self._maybe_await(
            self.client.buy(req.amount, asset, direction, duration=req.duration_seconds)
        )
        status = False
        trade_info = None
        if isinstance(result, tuple):
            status = bool(result[0])
            trade_info = result[1] if len(result) > 1 else None
        elif isinstance(result, dict):
            status = bool(result.get("status", result.get("success", True)))
            trade_info = result
        else:
            status = bool(result)
            trade_info = result
        if not status:
            raise RuntimeError(f"Quotex buy failed: {trade_info}")

        trade_id = f"quotex_{int(time()*1000)}"
        if isinstance(trade_info, dict):
            trade_id = str(trade_info.get("id") or trade_info.get("order_id") or trade_info.get("deal_id") or trade_id)
        elif trade_info is not None:
            trade_id = str(trade_info)

        return TradeRecord(
            id=trade_id,
            symbol=asset,
            direction=req.direction,
            amount=req.amount,
            entry_price=entry_price,
            paper=self.mode != "REAL",
        )
