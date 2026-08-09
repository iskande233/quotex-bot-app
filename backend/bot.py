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
        self._series: dict[str, List[float]] = {}
        self.last_analysis: dict = {}

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
            try:
                if len(self.history) >= self.config.max_trades:
                    self.last_analysis = {"status": "STOPPED", "message": "Max trades reached"}
                    await self.stop()
                    break
                await self._execute_trade_cycle()
            except Exception as e:
                # Keep the bot alive and expose the real failure to Flutter instead of silently dying.
                self.last_analysis = {"status": "ERROR", "message": str(e)}
            # after each result cycle, continue from next minute boundary
            now = int(time())
            await asyncio.sleep(max(2, 60 - (now % 60)))

    async def _execute_trade_cycle(self):
        if self.config.use_analysis:
            self.last_analysis = {"status": "ANALYZING", "message": f"Scanning assets for {self.config.analysis_seconds}s at +{self.config.min_confidence}%"}
            setup = await self._find_best_setup()
            if not setup:
                self.last_analysis = {"status": "NO_SIGNAL", "message": "No setup above confidence threshold"}
                return
            symbol, direction, confidence, reason = setup
        else:
            symbol = await self._resolve_manual_symbol()
            direction = self.config.manual_direction or "CALL"
            confidence = 0
            reason = "Manual mode without analysis"

        req = TradeRequest(
            symbol=symbol,
            direction=direction,
            amount=self.config.investment_amount,
            duration_seconds=60,
        )
        self.last_analysis = {"status": "PLACING_TRADE", "symbol": symbol, "direction": direction, "confidence": confidence, "reason": reason}
        trade = await self.adapter.place_trade(req)
        # attach lightweight analysis fields dynamically for API model_dump unaffected
        trade_dict_note = f"{reason} | confidence={confidence}%"
        self.history.insert(0, trade)
        self.last_analysis = {"status": "TRADE_OPENED", "symbol": symbol, "direction": direction, "confidence": confidence, "reason": reason, "note": trade_dict_note}
        asyncio.create_task(self._settle_trade(trade))

    async def _resolve_manual_symbol(self) -> str:
        if self.config.symbol.strip().upper() not in {"AUTO", "AUTO_OTC", "OTC_AUTO"}:
            return self.config.symbol
        assets = await self.adapter.list_assets()
        otc = [a for a in assets if "OTC" in a.upper()]
        return (otc or assets or ["EURUSD-OTC"])[0]

    async def _candidate_assets(self) -> list[str]:
        if self.config.symbol.strip().upper() not in {"AUTO", "AUTO_OTC", "OTC_AUTO"}:
            return [self.config.symbol]
        assets = await self.adapter.list_assets()
        otc = [a for a in assets if "OTC" in a.upper()]
        return (otc or assets or ["EURUSD-OTC"])[:12]

    async def _find_best_setup(self):
        candidates = await self._candidate_assets()
        deadline = time() + min(max(self.config.analysis_seconds, 5), 60)
        while time() < deadline and self.running:
            for asset in candidates:
                try:
                    price = await self.adapter.latest_price(asset)
                    arr = self._series.setdefault(asset, [])
                    arr.append(price)
                    self._series[asset] = arr[-80:]
                except Exception:
                    continue
            await asyncio.sleep(2)

        best = None
        for asset in candidates:
            score = self._score_asset(asset, self._series.get(asset, []))
            if score is None:
                continue
            if best is None or score[2] > best[2]:
                best = score
        if best and best[2] >= self.config.min_confidence:
            return best
        return None

    def _score_asset(self, asset: str, closes: List[float]):
        if len(closes) < 4:
            return None
        buy = 0
        sell = 0
        reason_parts = []
        # Momentum and candle pressure
        if closes[-1] > closes[-2] > closes[-3]:
            buy += 25; reason_parts.append("bullish momentum")
        if closes[-1] < closes[-2] < closes[-3]:
            sell += 25; reason_parts.append("bearish momentum")
        # EMA trend
        if len(closes) >= 9:
            ef = ema(closes, min(9, len(closes)))
            es = ema(closes, min(21, len(closes))) or ema(closes, min(9, len(closes)))
            if ef and es and ef > es:
                buy += 25; reason_parts.append("EMA uptrend")
            if ef and es and ef < es:
                sell += 25; reason_parts.append("EMA downtrend")
        # RSI reversal zones
        if len(closes) >= 8:
            rv = rsi(closes, min(14, max(2, len(closes)-1)))
            if rv is not None and rv < 42:
                buy += 20; reason_parts.append("RSI low bounce")
            if rv is not None and rv > 58:
                sell += 20; reason_parts.append("RSI high rejection")
        # MACD if enough data
        if len(closes) >= 35:
            mv = macd(closes)
            if mv and mv["hist"] > 0:
                buy += 20; reason_parts.append("MACD bullish")
            if mv and mv["hist"] < 0:
                sell += 20; reason_parts.append("MACD bearish")
        # Volatility bonus
        spread = max(closes[-min(len(closes), 10):]) - min(closes[-min(len(closes), 10):])
        if spread > 0:
            if closes[-1] >= closes[-2]: buy += 10
            else: sell += 10
        direction = "CALL" if buy >= sell else "PUT"
        confidence = min(96, max(buy, sell))
        reason = ", ".join(reason_parts[:4]) or "fast price action"
        return asset, direction, confidence, reason

    async def _settle_trade(self, trade: TradeRecord):
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
            self.last_analysis = {"status": "WAITING_RESULT", "symbol": trade.symbol, "direction": trade.direction, "message": "Waiting 60s result"}
            await asyncio.sleep(60)
            exit_price = await self.adapter.latest_price(trade.symbol)
            trade.exit_price = exit_price
            trade.closed_at = time()
            win = exit_price > (trade.entry_price or exit_price) if trade.direction == "CALL" else exit_price < (trade.entry_price or exit_price)
            trade.result = "WIN" if win else "LOSS"
            trade.pnl = trade.amount * 0.86 if win else -trade.amount
        if hasattr(self.adapter, "balance"):
            self.adapter.balance += trade.pnl
        if hasattr(self.adapter, "session_pnl"):
            self.adapter.session_pnl += trade.pnl
        self.last_analysis = {"status": "RESULT", "symbol": trade.symbol, "direction": trade.direction, "result": trade.result, "pnl": trade.pnl}

    def status(self):
        return {"running": self.running, "config": self.config.model_dump(), "trades_count": len(self.history), "last_analysis": self.last_analysis}
