from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from config import settings
from models import BotConfig, TradeRequest
from quotex_adapter import PaperQuotexAdapter, RealQuotexAdapter
from bot import TradingBot

app = FastAPI(title="Quotex Bot App API", version="0.1.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

adapter = PaperQuotexAdapter() if settings.paper_mode else RealQuotexAdapter()
bot = TradingBot(adapter)

@app.get("/health")
async def health():
    return {"ok": True, "paper_mode": settings.paper_mode}

@app.post("/api/v1/bot/start")
async def start_bot(config: BotConfig):
    await bot.start(config)
    return {"success": True, "status": bot.status()}

@app.post("/api/v1/bot/stop")
async def stop_bot():
    await bot.stop()
    return {"success": True, "status": bot.status()}

@app.get("/api/v1/bot/status")
async def bot_status():
    return bot.status()

@app.post("/api/v1/trade")
async def place_trade(req: TradeRequest):
    try:
        trade = await adapter.place_trade(req)
        bot.history.insert(0, trade)
        return trade
    except NotImplementedError as e:
        raise HTTPException(status_code=501, detail=str(e))

@app.get("/api/v1/balance")
async def balance():
    return await adapter.get_balance()

@app.get("/api/v1/history")
async def history():
    return bot.history
