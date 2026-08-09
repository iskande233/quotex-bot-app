from __future__ import annotations
import asyncio
import json
from pathlib import Path
from time import time
from typing import Set
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from config import settings
from models import BotConfig, TradeRequest, LoginRequest, LoginResponse
from quotex_adapter import PaperQuotexAdapter, DemoQuotexAdapter, RealQuotexAdapter, PyQuotexAdapter, QuotexAdapter
from bot import TradingBot
from notifier import send_trade_opened, send_trade_result, send_bot_started, send_bot_stopped, send_login_success, send_test_message

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

DATA_DIR = Path('/data') if Path('/data').exists() else Path('sessions')
STATE_FILE = DATA_DIR / 'quotex_bot_state.json'

def _load_state() -> dict:
    try:
        if STATE_FILE.exists():
            return json.loads(STATE_FILE.read_text())
    except Exception:
        pass
    return {}

def _save_state(update: dict):
    try:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        state = _load_state()
        state.update(update)
        STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2))
    except Exception:
        pass

async def restore_server_state():
    global adapter, bot
    state = _load_state()
    if not state:
        return
    creds = state.get('quotex_credentials') or {}
    if creds.get('email') and creds.get('password'):
        try:
            new_adapter = PyQuotexAdapter(creds['email'], creds['password'], creds.get('account_type', 'demo'), None)
            await new_adapter.connect()
            adapter = new_adapter
            bot = TradingBot(adapter)
        except Exception as e:
            try: bot._log('AUTO_RECONNECT_ERROR', str(e))
            except Exception: pass
    if state.get('auto_start') and state.get('bot_config'):
        try:
            cfg = BotConfig(**state['bot_config'])
            await bot.start(await resolve_symbol(cfg))
            try:
                bal = await adapter.get_balance(); send_bot_started(bal, cfg)
            except Exception: pass
        except Exception as e:
            try: bot._log('AUTO_START_ERROR', str(e))
            except Exception: pass

async def server_watchdog_loop():
    while True:
        await asyncio.sleep(20)
        try:
            state = _load_state()
            creds = state.get('quotex_credentials') or {}
            if creds.get('email') and creds.get('password') and not getattr(adapter, 'connected', False):
                await restore_server_state()
        except Exception:
            pass

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
    asyncio.create_task(restore_server_state())
    asyncio.create_task(server_watchdog_loop())
    _broadcast_task = asyncio.create_task(broadcast_loop())

@app.on_event("shutdown")
async def on_shutdown():
    if _broadcast_task:
        _broadcast_task.cancel()

async def snapshot(event: str = "snapshot", extra: dict | None = None) -> dict:
    balance = await adapter.get_balance()
    now = int(time())
    price = 0.0
    price_symbol = bot.config.symbol
    try:
        # AUTO_OTC is a scanner mode, not a real Quotex asset. Pick a real asset for dashboard price.
        if price_symbol.strip().upper() in {"AUTO", "AUTO_OTC", "OTC_AUTO"}:
            assets = await adapter.list_assets()
            otc = [a for a in assets if "OTC" in a.upper()]
            price_symbol = (otc or assets or ["EURUSD-OTC"])[0]
        price = await adapter.latest_price(price_symbol)
        manager.add_price(now, price)
    except Exception as e:
        # Never let dashboard snapshot break START/STOP. Keep the UI alive and expose the error.
        if not manager.chart_points:
            manager.add_price(now, 0.0)
        extra = dict(extra or {})
        extra["price_error"] = str(e)
    payload = {
        "type": event,
        "server_time": now,
        "price": price,
        "price_symbol": price_symbol,
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
    st = _load_state()
    return {"ok": True, "mode": getattr(adapter, "mode", "UNKNOWN"), "auto_start": bool(st.get("auto_start")), "persistent_state": str(STATE_FILE)}

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
    _save_state({"quotex_credentials": {"email": req.email, "password": req.password, "account_type": req.account_type}})
    balance = await adapter.get_balance()
    send_login_success(balance)
    await manager.broadcast(await snapshot("login_success", {"mode": getattr(adapter, "mode", "UNKNOWN")}))
    return LoginResponse(success=True, mode=getattr(adapter, "mode", "DEMO"), message="Logged in")

@app.post("/api/v1/auth/logout")
async def logout():
    global adapter, bot
    await bot.stop()
    adapter = PaperQuotexAdapter()
    bot = TradingBot(adapter)
    _save_state({"auto_start": False, "quotex_credentials": {}})
    await manager.broadcast(await snapshot("logout"))
    return {"success": True, "mode": "PAPER"}

@app.get("/api/v1/auth/session")
async def session():
    st = _load_state()
    return {"mode": getattr(adapter, "mode", "UNKNOWN"), "connected": getattr(adapter, "connected", True), "auto_start": bool(st.get("auto_start")), "server_persistent": bool(st.get("quotex_credentials"))}

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
    try:
        config = await resolve_symbol(config)
        await bot.start(config)
        _save_state({"auto_start": True, "bot_config": config.model_dump()})
        balance = await adapter.get_balance()
        send_bot_started(balance, config)
        await manager.broadcast(await snapshot("bot_started"))
        return {"success": True, "status": bot.status()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Bot start failed: {e}")


@app.post("/api/v1/bot/config")
async def update_bot_config(config: BotConfig):
    try:
        config = await resolve_symbol(config)
        bot.config = config
        _save_state({"auto_start": bot.running, "bot_config": config.model_dump()})
        bot._log("CONFIG", "Settings updated without restarting bot")
        await manager.broadcast(await snapshot("config_updated"))
        return {"success": True, "status": bot.status()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Config update failed: {e}")

@app.post("/api/v1/bot/stop_after_current")
async def stop_after_current():
    bot.request_stop_after_current()
    await manager.broadcast(await snapshot("stop_after_current"))
    return {"success": True, "status": bot.status()}

@app.post("/api/v1/bot/stop")
async def stop_bot():
    cfg = bot.config
    await bot.stop()
    _save_state({"auto_start": False})
    balance = await adapter.get_balance()
    send_bot_stopped(balance, cfg)
    await manager.broadcast(await snapshot("bot_stopped"))
    return {"success": True, "status": bot.status()}

@app.get("/api/v1/bot/status")
async def bot_status():
    return bot.status()

@app.post("/api/v1/bot/random_trade")
async def random_trade(amount: float = 1.0):
    try:
        trade = await bot.open_random_trade_now(amount)
        balance = await adapter.get_balance()
        send_trade_opened(trade)
        await manager.broadcast(await snapshot("trade_opened", {"trade": trade.model_dump()}))
        return {"success": True, "trade": trade.model_dump(), "balance": balance.model_dump()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Random trade failed: {e}")

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

@app.post("/api/v1/telegram/test")
async def telegram_test():
    send_test_message()
    return {"success": True, "message": "Telegram test sent"}

@app.get("/api/v1/assets")
async def assets():
    items = await adapter.list_assets()
    return {"assets": items, "otc": [a for a in items if "OTC" in a.upper()]}

@app.get("/api/v1/history")
async def history():
    return bot.history
