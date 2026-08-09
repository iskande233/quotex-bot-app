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
        # Execute immediately after START, then continue a strict 1-minute cycle.
        while self.running:
            if len(self.history) >= self.config.max_trades:
                await self.stop()
                break
            await self._execute_trade_cycle()
            # Align next analysis to the next minute boundary.
            now = int(time())
            await asyncio.sleep(max(2, 60 - (now % 60)))

    async def _execute_trade_cycle(self):
        price = await self.adapter.latest_price(self.config.symbol)
        self._candles.append(price)
        self._candles = self._candles[-120:]

        signal = self.analyze()
        if not signal:
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
        # Fallback at startup: produce a simple deterministic signal so the app starts trading immediately.
        if len(closes) < 8:
            return "CALL" if int(time()) % 2 == 0 else "PUT"

        ema_fast = ema(closes, min(9, len(closes)))
        ema_slow = ema(closes, min(21, len(closes)))
        current_rsi = rsi(closes, min(14, max(2, len(closes) - 1)))
        current_macd = macd(closes) if len(closes) >= 35 else None

        buy_score = 0
        sell_score = 0
        if ema_fast is not None and ema_slow is not None:
            if ema_fast > ema_slow: buy_score += 35
            if ema_fast < ema_slow: sell_score += 35
        if current_rsi is not None:
            if current_rsi < 45: buy_score += 25
            if current_rsi > 55: sell_score += 25
        if current_macd is not None:
            if current_macd["hist"] > 0: buy_score += 20
            if current_macd["hist"] < 0: sell_score += 20
        if closes[-1] > closes[-2]: buy_score += 20
        if closes[-1] < closes[-2]: sell_score += 20

        if buy_score == sell_score:
            return "CALL" if closes[-1] >= closes[-2] else "PUT"
        return "CALL" if buy_score > sell_score else "PUT"

    async def _settle_trade(self, trade: TradeRecord):
        # If the adapter can get the broker result, use it. Otherwise fallback to price comparison.
        result_used = False
        if hasattr(self.adapter, "check_trade_result"):
            try:
                status, profit = await self.adapter.check_trade_result(trade.id, 65)
                trade.result = "WIN" if str(status).lower() == "win" else "LOSS"
                trade.pnl = float(profit) if profit is not None else (trade.amount * 0.86 if trade.result == "WIN" else -trade.amount)
                trade.closed_at = time()
                result_used = True
            except Exception:
                result_used = False

        if not result_used:
            await asyncio.sleep(60)
            exit_price = await self.adapter.latest_price(trade.symbol)
            trade.exit_price = exit_price
            trade.closed_at = time()
            win = exit_price > (trade.entry_price or exit_price) if trade.direction == "CALL" else exit_price < (trade.entry_price or exit_price)
            trade.result = "WIN" if win else "LOSS"
            trade.pnl = trade.amount * 0.86 if win else -trade.amount

        # Paper/Demo account balance simulation if adapter exposes local balance.
        if hasattr(self.adapter, "balance"):
            self.adapter.balance += trade.pnl
        if hasattr(self.adapter, "session_pnl"):
            self.adapter.session_pnl += trade.pnl

    def status(self):
        return {"running": self.running, "config": self.config.model_dump(), "trades_count": len(self.history)}
