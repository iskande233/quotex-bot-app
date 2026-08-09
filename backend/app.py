from __future__ import annotations
import asyncio
from time import time
from typing import Set
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from config import settings
from models import BotConfig, TradeRequest, LoginRequest, LoginResponse
from quotex_adapter import PaperQuotexAdapter, DemoQuotexAdapter, RealQuotexAdapter, PyQuotexAdapter, QuotexAdapter
from bot import TradingBot
from notifier import send_trade_opened, send_trade_result, send_bot_started, send_bot_stopped

app = FastAPI(title="Quotex Bot App API", version="0.3.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

def make_adapter(mode: str) -> QuotexAdapter:
    mode = (mode or "paper").lower()
    if mode == "demo":
        return DemoQuotexAdapter()
    if mode == "real":
        return RealQuotexAdapter()
    return PaperQuotexAdapter()

adapter: QuotexAdapter = make_adapter(settings.quotex_mode if not settings.paper_mode else "paper")
bot = TradingBot(adapter)

class WsManager:
    def __init__(self):
        self.clients: Set[WebSocket] = set()
        self.chart_points: list[dict] = []
        self.candles: list[dict] = []
        self._current_candle: dict | None = None

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self.clients.add(ws)

    def disconnect(self, ws: WebSocket):
        self.clients.discard(ws)

    def add_price(self, ts: int, price: float):
        self.chart_points.append({"time": ts, "price": price})
        self.chart_points = self.chart_points[-120:]
        minute = ts - (ts % 60)
        c = self._current_candle
        if c is None or c["time"] != minute:
            if c is not None:
                self.candles.append(c)
                self.candles = self.candles[-80:]
            self._current_candle = {"time": minute, "open": price, "high": price, "low": price, "close": price}
        else:
            c["high"] = max(c["high"], price)
            c["low"] = min(c["low"], price)
            c["close"] = price

    def candle_payload(self) -> list[dict]:
        data = list(self.candles)
        if self._current_candle is not None:
            data.append(self._current_candle)
        return data[-80:]

    async def broadcast(self, payload: dict):
        dead = []
        for ws in list(self.clients):
            try:
                await ws.send_json(payload)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws)

manager = WsManager()
_broadcast_task: asyncio.Task | None = None

@app.on_event("startup")
async def on_startup():
    global _broadcast_task
    _broadcast_task = asyncio.create_task(broadcast_loop())

@app.on_event("shutdown")
async def on_shutdown():
    if _broadcast_task:
        _broadcast_task.cancel()

async def snapshot(event: str = "snapshot", extra: dict | None = None) -> dict:
    balance = await adapter.get_balance()
    price = await adapter.latest_price(bot.config.symbol)
    now = int(time())
    manager.add_price(now, price)
    payload = {
        "type": event,
        "server_time": now,
        "price": price,
        "chart": manager.chart_points,
        "candles": manager.candle_payload(),
        "balance": balance.model_dump(),
        "status": bot.status(),
        "history": [t.model_dump() for t in bot.history[:50]],
    }
    if extra:
        payload.update(extra)
    return payload

async def broadcast_loop():
    seen_results: dict[str, str] = {}
    seen_open: set[str] = set()
    while True:
        try:
            # Detect trade open/result events for UI popups.
            event = "snapshot"
            extra = {}
            for t in bot.history[:5]:
                if t.id not in seen_open:
                    seen_open.add(t.id)
                    event = "trade_opened"
                    extra = {"trade": t.model_dump()}
                    send_trade_opened(t)
                    break
                old = seen_results.get(t.id)
                if t.result != "PENDING" and old != t.result:
                    seen_results[t.id] = t.result
                    event = "trade_result"
                    extra = {"trade": t.model_dump()}
                    send_trade_result(t)
                    break
            await manager.broadcast(await snapshot(event, extra))
        except Exception:
            pass
        await asyncio.sleep(1)

@app.get("/")
async def root():
    return {"ok": True, "name": "Quotex Bot App API", "docs": "/docs", "health": "/health"}

@app.get("/health")
async def health():
    return {"ok": True, "mode": getattr(adapter, "mode", "UNKNOWN")}

@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await manager.connect(ws)
    try:
        await ws.send_json(await snapshot())
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(ws)
    except Exception:
        manager.disconnect(ws)


@app.post("/api/v1/auth/login", response_model=LoginResponse)
async def login(req: LoginRequest):
    """Create an in-memory Quotex session via the configured pyquotex wrapper.

    Credentials are not persisted. Demo is the default recommended account type.
    """
    global adapter, bot
    if req.account_type == "real":
        # Keep real mode explicit. Adapter exists but must be used intentionally.
        pass
    await bot.stop()
    new_adapter = PyQuotexAdapter(req.email, req.password, req.account_type, req.otp_code)
    try:
        await new_adapter.connect()
    except RuntimeError as e:
        raise HTTPException(status_code=501, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Quotex login failed: {e}")
    adapter = new_adapter
    bot = TradingBot(adapter)
    await manager.broadcast(await snapshot("login_success", {"mode": getattr(adapter, "mode", "UNKNOWN")}))
    return LoginResponse(success=True, mode=getattr(adapter, "mode", "DEMO"), message="Logged in")

@app.post("/api/v1/auth/logout")
async def logout():
    global adapter, bot
    await bot.stop()
    adapter = PaperQuotexAdapter()
    bot = TradingBot(adapter)
    await manager.broadcast(await snapshot("logout"))
    return {"success": True, "mode": "PAPER"}

@app.get("/api/v1/auth/session")
async def session():
    return {"mode": getattr(adapter, "mode", "UNKNOWN"), "connected": getattr(adapter, "connected", True)}

@app.post("/api/v1/mode/{mode}")
async def switch_mode(mode: str):
    global adapter, bot
    if mode.lower() not in {"paper", "demo", "real"}:
        raise HTTPException(status_code=400, detail="mode must be paper, demo, or real")
    await bot.stop()
    adapter = make_adapter(mode)
    bot = TradingBot(adapter)
    await manager.broadcast(await snapshot("mode_changed", {"mode": getattr(adapter, "mode", "UNKNOWN")}))
    return {"success": True, "mode": getattr(adapter, "mode", "UNKNOWN")}

async def resolve_symbol(config: BotConfig) -> BotConfig:
    # In analysis mode, keep AUTO_OTC so bot can scan all OTC assets and choose best.
    if config.use_analysis:
        return config
    if config.symbol.strip().upper() not in {"AUTO", "AUTO_OTC", "OTC_AUTO"}:
        return config
    assets = await adapter.list_assets()
    otc = [a for a in assets if "OTC" in a.upper()]
    config.symbol = (otc or assets or ["EURUSD-OTC"])[0]
    return config

@app.post("/api/v1/bot/start")
async def start_bot(config: BotConfig):
    config = await resolve_symbol(config)
    await bot.start(config)
    balance = await adapter.get_balance()
    send_bot_started(balance, config)
    await manager.broadcast(await snapshot("bot_started"))
    return {"success": True, "status": bot.status()}

@app.post("/api/v1/bot/stop")
async def stop_bot():
    cfg = bot.config
    await bot.stop()
    balance = await adapter.get_balance()
    send_bot_stopped(balance, cfg)
    await manager.broadcast(await snapshot("bot_stopped"))
    return {"success": True, "status": bot.status()}

@app.get("/api/v1/bot/status")
async def bot_status():
    return bot.status()

@app.post("/api/v1/trade")
async def place_trade(req: TradeRequest):
    try:
        trade = await adapter.place_trade(req)
        bot.history.insert(0, trade)
        await manager.broadcast(await snapshot("trade_opened", {"trade": trade.model_dump()}))
        return trade
    except NotImplementedError as e:
        raise HTTPException(status_code=501, detail=str(e))

@app.get("/api/v1/balance")
async def balance():
    return await adapter.get_balance()

@app.get("/api/v1/assets")
async def assets():
    items = await adapter.list_assets()
    return {"assets": items, "otc": [a for a in items if "OTC" in a.upper()]}

@app.get("/api/v1/history")
async def history():
    return bot.history
