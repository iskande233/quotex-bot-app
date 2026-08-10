from __future__ import annotations
from abc import ABC, abstractmethod
from random import random
from time import time
from models import TradeRequest, TradeRecord, BalanceResponse

# Official OTC universe requested for the bot. Keep lowercase pyquotex asset format.
OTC_PAIRS = [
    "USDINR_otc", "USDJPY_otc", "USDNGN_otc", "USDPKR_otc",
    "GBPNZD_otc", "AUDNZD_otc", "GBPCHF_otc", "EURNZD_otc",
    "USDZAR_otc", "NZDUSD_otc", "USDCAD_otc", "NZDJPY_otc",
    "GBPUSD_otc", "AUDCAD_otc", "AUDCHF_otc", "EURUSD_otc",
    "USDDZD_otc", "CHFJPY_otc", "EURCHF_otc", "GBPAUD_otc",
    "AUDJPY_otc", "EURAUD_otc", "NZDCHF_otc", "CADCHF_otc",
    "AUDUSD_otc", "EURCAD_otc", "NZDCAD_otc", "USDARS_otc",
    "USDBRL_otc", "USDMXN_otc", "EURGBP_otc", "EURJPY_otc",
    "GBPJPY_otc", "USDCHF_otc", "USDEGP_otc", "USDIDR_otc",
    "USDPHP_otc",
]

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

    async def get_recent_candles(self, symbol: str, count: int = 80, period: int = 60) -> list[dict]:
        candles = []
        for _ in range(max(5, count)):
            price = await self.latest_price(symbol)
            candles.append({"open": price, "high": price, "low": price, "close": price})
        return candles

    async def get_realtime_sentiment(self, symbol: str):
        return None

    async def list_assets(self) -> list[str]:
        return []

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

    async def list_assets(self) -> list[str]:
        return list(OTC_PAIRS)

    async def get_recent_candles(self, symbol: str, count: int = 80, period: int = 60) -> list[dict]:
        candles = []
        price = self._price_by_symbol.get(symbol) or await self.latest_price(symbol)
        for _ in range(max(5, count)):
            o = price
            price = round(price + (random() - 0.5) * 0.0012, 6)
            h = max(o, price) + random() * 0.00025
            l = min(o, price) - random() * 0.00025
            candles.append({"open": round(o, 6), "high": round(h, 6), "low": round(l, 6), "close": round(price, 6)})
        self._price_by_symbol[symbol] = price
        return candles

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

    def __init__(self, email: str, password: str, account_type: str = "demo", otp_code: str | None = None):
        self.email = email
        self.password = password
        self.otp_code = (otp_code or "").strip()
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
        """Normalize symbols to pyquotex format exactly as expected by the wrapper.

        Correct pyquotex OTC format:
            EURUSD_otc, GBPJPY_otc, AUDNZD_otc

        Accepted inputs:
            EURUSD_otc, EURUSD-OTC, EUR/USD OTC, eur_usdotc, EURUSD
        """
        raw = (symbol or "").strip()
        low = raw.lower()
        if low in {"auto", "auto_otc", "otc_auto"}:
            return OTC_PAIRS[0]

        clean = raw.replace(" ", "").replace("/", "").replace("-", "_")
        low_clean = clean.lower()

        # Already correct: EURUSD_otc / eurusd_otc
        if low_clean.endswith("_otc"):
            base = clean[:-4].replace("_", "").upper()
            candidate = f"{base}_otc"
            return candidate

        # Internal/wrong form previously used: eur_usdotc -> EURUSD_otc
        if low_clean.endswith("otc"):
            base = clean[:-3].replace("_", "").upper()
            candidate = f"{base}_otc"
            return candidate

        # Real pair typed manually: EURUSD -> force OTC, because this bot trades OTC only.
        base = clean.replace("_", "").upper()
        if len(base) == 6:
            return f"{base}_otc"

        return clean

    async def connect(self) -> None:
        Quotex = self._load_client_class()
        def otp_callback(message: str):
            if self.otp_code:
                return self.otp_code
            raise RuntimeError("OTP_REQUIRED: Quotex requested a verification code. Enter the code in the OTP field and login again.")

        self.client = Quotex(
            email=self.email,
            password=self.password,
            lang="en",
            user_data_dir=f"/tmp/quotex_{abs(hash(self.email))}",
            on_otp_callback=otp_callback,
        )
        result = await self._maybe_await(self.client.connect())
        check, reason = True, ""
        if isinstance(result, tuple):
            check = bool(result[0])
            reason = str(result[1]) if len(result) > 1 else ""
        elif isinstance(result, bool):
            check = result
        if not check:
            raise RuntimeError(reason or "Quotex connect failed")

        # Demo by default. Cleiton pyquotex uses change_account("PRACTICE"/"REAL").
        balance_mode = "REAL" if self.mode == "REAL" else "PRACTICE"
        if hasattr(self.client, "change_account"):
            await self._maybe_await(self.client.change_account(balance_mode))
        elif hasattr(self.client, "change_balance"):
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


    def _normalize_candle(self, item) -> dict | None:
        try:
            if isinstance(item, dict):
                o = item.get("open", item.get("o", item.get("close", item.get("c"))))
                h = item.get("high", item.get("max", item.get("h", item.get("close", item.get("c")))))
                l = item.get("low", item.get("min", item.get("l", item.get("close", item.get("c")))))
                c = item.get("close", item.get("c", item.get("price", o)))
                return {"open": float(o), "high": float(h), "low": float(l), "close": float(c), "time": item.get("time", item.get("from"))}
            if isinstance(item, (list, tuple)) and len(item) >= 4:
                vals = [float(x) for x in item[-4:]]
                return {"open": vals[0], "high": vals[1], "low": vals[2], "close": vals[3]}
        except Exception:
            return None
        return None

    async def get_recent_candles(self, symbol: str, count: int = 80, period: int = 60) -> list[dict]:
        if not self.connected:
            await self.connect()
        asset = self._asset(symbol)
        import time as _time
        raw = None
        # cleitonLeonel/pyquotex exposes both get_candles and get_historical_candles.
        for call in (
            lambda: self.client.get_candles(asset, _time.time(), count * period, period),
            lambda: self.client.get_candles(asset, None, count * period, period),
            lambda: self.client.get_historical_candles(asset, amount_of_seconds=count * period, period=period, max_workers=2),
            lambda: self.client.get_historical_candles(asset, amount_of_seconds=count * period, period=period),
        ):
            try:
                raw = await self._maybe_await(call())
                if raw:
                    break
            except Exception:
                raw = None
        if isinstance(raw, dict):
            items = list(raw.values())
        else:
            items = list(raw or [])
        candles = [c for c in (self._normalize_candle(x) for x in items) if c]
        candles = candles[-count:]
        if len(candles) >= 5:
            return candles
        # Fallback keeps the bot alive if candle mapping is temporarily unavailable.
        price = await self.latest_price(asset)
        return [{"open": price, "high": price, "low": price, "close": price} for _ in range(max(5, count))]

    async def latest_price(self, symbol: str) -> float:
        if not self.connected:
            await self.connect()
        asset = self._asset(symbol)
        # Cleiton pyquotex signature: get_candles(asset, end_from_time, offset, period, ...)
        import time as _time
        attempts = [
            (asset, _time.time(), 120, 60),
            (asset, None, 120, 60),
        ]
        for args in attempts:
            try:
                candles = await self._maybe_await(self.client.get_candles(*args))
                if not candles:
                    continue
                last = candles[-1] if isinstance(candles, list) else list(candles.values())[-1]
                if isinstance(last, dict):
                    return float(last.get("close") or last.get("price") or last.get("c"))
                if isinstance(last, (list, tuple)):
                    return float(last[-1])
            except Exception:
                continue
        raise NotImplementedError("pyquotex get_candles mapping failed for asset " + asset)

    async def get_realtime_sentiment(self, symbol: str):
        if not self.connected:
            await self.connect()
        method = getattr(self.client, "get_realtime_sentiment", None)
        if not callable(method):
            return None
        try:
            return await self._maybe_await(method(self._asset(symbol)))
        except Exception:
            return None

    async def list_assets(self) -> list[str]:
        """Return only OTC pairs supported by our bot.

        We optionally ask the wrapper for currently available instruments and
        intersect them with the requested OTC universe. If the wrapper cannot
        provide instruments, we still return the official OTC list so AUTO_OTC
        never falls back to real non-OTC assets.
        """
        if not self.connected:
            await self.connect()
        discovered: set[str] = set()
        for method_name in ("get_all_asset_name", "get_all_assets", "get_assets", "get_available_assets"):
            method = getattr(self.client, method_name, None)
            if callable(method):
                try:
                    data = await self._maybe_await(method())
                    if isinstance(data, dict):
                        data = list(data.keys())
                    for item in data or []:
                        if isinstance(item, (list, tuple)) and item:
                            name = str(item[0])
                        elif isinstance(item, dict):
                            name = str(item.get("name") or item.get("asset") or item.get("symbol") or "")
                        else:
                            name = str(item)
                        if name:
                            normalized = self._asset(name)
                            if normalized in OTC_PAIRS:
                                discovered.add(normalized)
                    if discovered:
                        break
                except Exception:
                    continue
        return [p for p in OTC_PAIRS if not discovered or p in discovered]

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

    async def check_trade_result(self, trade_id: str, timeout: int = 65):
        if not self.connected:
            await self.connect()
        if hasattr(self.client, "check_win"):
            return await self._maybe_await(self.client.check_win(trade_id, timeout))
        if hasattr(self.client, "get_result"):
            result = await self._maybe_await(self.client.get_result(trade_id))
            if isinstance(result, tuple):
                return result[0], result[1] if len(result) > 1 else 0
            return result, 0
        raise NotImplementedError("pyquotex result method is not mapped yet")
