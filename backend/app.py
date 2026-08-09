from __future__ import annotations
import asyncio
from random import random
from time import time
from typing import Set
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from config import settings
from models import BotConfig, TradeRequest
from quotex_adapter import PaperQuotexAdapter, RealQuotexAdapter
from bot import TradingBot

app = FastAPI(title="Quotex Bot App API", version="0.2.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

adapter = PaperQuotexAdapter() if settings.paper_mode else RealQuotexAdapter()
bot = TradingBot(adapter)

class WsManager:
    def __init__(self):
        self.clients: Set[WebSocket] = set()
        self.chart_points: list[dict] = []

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self.clients.add(ws)

    def disconnect(self, ws: WebSocket):
        self.clients.discard(ws)

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

async def snapshot() -> dict:
    balance = await adapter.get_balance()
    price = await adapter.latest_price(bot.config.symbol)
    now = int(time())
    manager.chart_points.append({"time": now, "price": price})
    manager.chart_points = manager.chart_points[-80:]
    return {
        "type": "snapshot",
        "server_time": now,
        "price": price,
        "chart": manager.chart_points,
        "balance": balance.model_dump(),
        "status": bot.status(),
        "history": [t.model_dump() for t in bot.history[:50]],
    }

async def broadcast_loop():
    while True:
        try:
            await manager.broadcast(await snapshot())
        except Exception:
            pass
        await asyncio.sleep(1)

@app.get("/health")
async def health():
    return {"ok": True, "paper_mode": settings.paper_mode}

@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await manager.connect(ws)
    try:
        await ws.send_json(await snapshot())
        while True:
            # Keep socket alive and allow future client commands.
            await ws.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(ws)
    except Exception:
        manager.disconnect(ws)

@app.post("/api/v1/bot/start")
async def start_bot(config: BotConfig):
    await bot.start(config)
    payload = {"success": True, "status": bot.status()}
    await manager.broadcast(await snapshot())
    return payload

@app.post("/api/v1/bot/stop")
async def stop_bot():
    await bot.stop()
    payload = {"success": True, "status": bot.status()}
    await manager.broadcast(await snapshot())
    return payload

@app.get("/api/v1/bot/status")
async def bot_status():
    return bot.status()

@app.post("/api/v1/trade")
async def place_trade(req: TradeRequest):
    try:
        trade = await adapter.place_trade(req)
        bot.history.insert(0, trade)
        await manager.broadcast(await snapshot())
        return trade
    except NotImplementedError as e:
        raise HTTPException(status_code=501, detail=str(e))

@app.get("/api/v1/balance")
async def balance():
    return await adapter.get_balance()

@app.get("/api/v1/history")
async def history():
    return bot.history
