from __future__ import annotations
import asyncio
from time import time
from typing import List
from models import BotConfig, TradeRequest, TradeRecord
from quotex_adapter import QuotexAdapter
from indicators import ema, rsi, macd

class TradingBot:
    def __init__(self, adapter: QuotexAdapter):
        self.adapter = adapter
        self.config = BotConfig()
        self.running = False
        self.history: List[TradeRecord] = []
        self._task: asyncio.Task | None = None
        self._candles: List[float] = []

    async def start(self, config: BotConfig):
        self.config = config
        self.config.enabled = True
        self.running = True
        await self.adapter.connect()
        if self._task is None or self._task.done():
            self._task = asyncio.create_task(self._loop())

    async def stop(self):
        self.running = False
        self.config.enabled = False
        if self._task and not self._task.done():
            self._task.cancel()

    async def _loop(self):
        while self.running:
            # Align to minute boundary.
            now = int(time())
            sleep = 60 - (now % 60)
            await asyncio.sleep(sleep)
            if not self.running:
                break
            await self._on_candle_close()

    async def _on_candle_close(self):
        price = await self.adapter.latest_price(self.config.symbol)
        self._candles.append(price)
        self._candles = self._candles[-120:]

        signal = self.analyze()
        if not signal:
            return
        if len(self.history) >= self.config.max_trades:
            await self.stop()
            return

        req = TradeRequest(
            symbol=self.config.symbol,
            direction=signal,
            amount=self.config.investment_amount,
            duration_seconds=60,
        )
        trade = await self.adapter.place_trade(req)
        self.history.insert(0, trade)
        asyncio.create_task(self._settle_trade(trade))

    def analyze(self):
        closes = self._candles
        if len(closes) < 30:
            return None
        ema_fast = ema(closes, 9)
        ema_slow = ema(closes, 21)
        current_rsi = rsi(closes, 14)
        current_macd = macd(closes)
        if ema_fast is None or ema_slow is None or current_rsi is None or current_macd is None:
            return None

        buy_score = 0
        sell_score = 0
        if ema_fast > ema_slow: buy_score += 30
        if ema_fast < ema_slow: sell_score += 30
        if current_rsi < 38: buy_score += 25
        if current_rsi > 62: sell_score += 25
        if current_macd["hist"] > 0: buy_score += 25
        if current_macd["hist"] < 0: sell_score += 25
        if closes[-1] > closes[-2]: buy_score += 20
        if closes[-1] < closes[-2]: sell_score += 20

        if buy_score >= 75 and buy_score > sell_score:
            return "CALL"
        if sell_score >= 75 and sell_score > buy_score:
            return "PUT"
        return None

    async def _settle_trade(self, trade: TradeRecord):
        await asyncio.sleep(60)
        exit_price = await self.adapter.latest_price(trade.symbol)
        trade.exit_price = exit_price
        trade.closed_at = time()
        win = exit_price > (trade.entry_price or exit_price) if trade.direction == "CALL" else exit_price < (trade.entry_price or exit_price)
        trade.result = "WIN" if win else "LOSS"
        trade.pnl = trade.amount * 0.86 if win else -trade.amount
        # Paper/Demo account balance simulation.
        if hasattr(self.adapter, "balance"):
            self.adapter.balance += trade.pnl
        if hasattr(self.adapter, "session_pnl"):
            self.adapter.session_pnl += trade.pnl

    def status(self):
        return {"running": self.running, "config": self.config.model_dump(), "trades_count": len(self.history)}
