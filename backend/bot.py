from __future__ import annotations
import asyncio
import random
from time import time
from typing import List
from models import BotConfig, TradeRequest, TradeRecord
from quotex_adapter import QuotexAdapter
from config import settings
from indicators import ema, rsi, macd, sma, bollinger, stochastic, atr, support_resistance, candle_strength
from notifier import send_signal_scheduled, send_auto_stop

class TradingBot:
    def __init__(self, adapter: QuotexAdapter):
        self.adapter = adapter
        self.config = BotConfig()
        self.running = False
        self.history: List[TradeRecord] = []
        self._task: asyncio.Task | None = None
        self._series: dict[str, List[float]] = {}
        self._candles: dict[str, list[dict]] = {}
        self.last_analysis: dict = {}
        self.current_signal: dict | None = None
        self.session_pnl: float = 0.0
        self.consecutive_losses: int = 0
        self.stop_requested_after_current: bool = False
        self.cooldown_until: float = 0.0
        self.pair_cooldowns: dict[str, float] = {}
        self.logs: list[dict] = []
        self.pair_stats: dict[str, dict] = {}
        self.blacklisted_pairs: set[str] = set()

    async def start(self, config: BotConfig):
        self.config = config
        self.config.enabled = True
        self.session_pnl = 0.0
        self.consecutive_losses = 0
        self.stop_requested_after_current = False
        self.cooldown_until = 0.0
        self.logs.clear()
        self._log("START", f"Bot started strategy={self.config.strategy_mode}")
        self.running = True
        await self.adapter.connect()
        if self._task is None or self._task.done():
            self._task = asyncio.create_task(self._loop())

    async def stop(self):
        self._log("STOP", "Bot stopped")
        self.running = False
        self.config.enabled = False
        if self._task and not self._task.done():
            self._task.cancel()

    async def _loop(self):
        while self.running:
            try:
                if len(self.history) >= self.config.max_trades:
                    await self._auto_stop("Max trades reached")
                    break
                if await self._risk_limit_reached():
                    break
                if self.stop_requested_after_current:
                    self.last_analysis = {"status": "STOP_AFTER_CURRENT", "message": "Stopped after current trade"}
                    await self.stop()
                    break
                if self.cooldown_until > time():
                    remaining = int(self.cooldown_until - time())
                    self.last_analysis = {"status": "COOLDOWN", "message": f"Waiting {remaining}s after loss"}
                    await asyncio.sleep(min(remaining, 5))
                    continue
                await self._scheduled_trade_cycle()
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.last_analysis = {"status": "ERROR", "message": str(e)}
                await asyncio.sleep(5)

    async def _risk_limit_reached(self) -> bool:
        if self.config.take_profit_enabled and self.config.take_profit > 0 and self.session_pnl >= self.config.take_profit:
            await self._auto_stop(f"تحقق هدف الربح +{self.config.take_profit}$")
            return True
        if self.config.stop_loss_enabled and self.config.stop_loss > 0 and self.session_pnl <= -abs(self.config.stop_loss):
            await self._auto_stop(f"تجاوز حد الخسارة -{self.config.stop_loss}$")
            return True
        if self.consecutive_losses >= self.config.max_consecutive_losses:
            await self._auto_stop(f"{self.config.max_consecutive_losses} خسارات متتالية")
            return True
        return False

    async def _auto_stop(self, reason: str):
        self.last_analysis = {"status": "AUTO_STOP", "message": reason, "pnl": self.session_pnl, "consecutive_losses": self.consecutive_losses}
        self._log("AUTO_STOP", reason)
        send_auto_stop(reason, round(self.session_pnl, 2), self.consecutive_losses)
        await self.stop()

    async def _scheduled_trade_cycle(self):
        # Fast M1 pipeline:
        # choose the coming minute first, then analyze inside the available 55s window.
        # Example: result at 10:01:05 -> analyze until ~10:01:57 -> enter 10:02:00.
        entry_time = self._next_entry_boundary(min_analysis_seconds=10)
        execute_time = max(time(), entry_time - settings.entry_lead_seconds)
        analysis_deadline = max(time() + 5, execute_time - 0.5)

        if self.config.use_analysis:
            remaining = max(0, int(analysis_deadline - time()))
            self.last_analysis = {"status": "ANALYZING", "message": f"Fast scan for next M1 entry in {remaining}s", "planned_entry_time": entry_time}
            self._log("ANALYZING", self.last_analysis["message"])
            setup = await self._find_best_setup(deadline=analysis_deadline)
            if not setup:
                self.current_signal = None
                self.last_analysis = {"status": "NO_SIGNAL", "message": "No setup in selected confidence bucket for this minute", "planned_entry_time": entry_time}
                self._log("NO_SIGNAL", "No setup in selected confidence bucket for this minute")
                return
            symbol, direction, confidence, reason = setup
        else:
            symbol = await self._resolve_manual_symbol(random_if_auto=True)
            direction = self.config.manual_direction or random.choice(["CALL", "PUT"])
            confidence = 0
            reason = "Random/direct mode without analysis"

        expiry_time = entry_time + 60.0
        result_check_time = expiry_time + settings.result_delay_seconds
        self.current_signal = {
            "symbol": symbol,
            "direction": direction,
            "confidence": confidence,
            "reason": reason,
            "entry_time": entry_time,
            "execute_time": execute_time,
            "expiry_time": expiry_time,
            "result_check_time": result_check_time,
            "amount": self.config.investment_amount,
            "status": "SCHEDULED",
        }
        self.last_analysis = {"status": "SIGNAL_SCHEDULED", "message": "Waiting server-time entry", **self.current_signal}
        self._log("SIGNAL", f"{symbol} {direction} confidence={confidence}% entry={int(entry_time)}")
        send_signal_scheduled(self.current_signal)

        delay = max(0, execute_time - time())
        while delay > 0 and self.running:
            await asyncio.sleep(min(0.25, delay))
            delay = execute_time - time()
        if not self.running:
            return

        trade = await self._place_trade(symbol, direction, confidence, reason, entry_time, result_check_time)
        await self._settle_trade(trade, result_check_time)
        # after result, loop starts again and sends the next signal

    async def _place_trade(self, symbol: str, direction: str, confidence: int, reason: str, entry_time: float, result_check_time: float, amount: float | None = None, step: int = 0) -> TradeRecord:
        self.last_analysis = {"status": "PLACING_TRADE", "symbol": symbol, "direction": direction, "confidence": confidence, "reason": reason, "message": f"Sending order {settings.entry_lead_seconds}s before official entry"}
        req = TradeRequest(symbol=symbol, direction=direction, amount=(amount if amount is not None else self.config.investment_amount), duration_seconds=60)
        trade = await self.adapter.place_trade(req)
        trade.scheduled_entry_time = entry_time
        trade.result_check_time = result_check_time
        trade.step = step
        self.history.insert(0, trade)
        if self.current_signal:
            self.current_signal["status"] = "OPENED"
        self.last_analysis = {"status": "TRADE_OPEN", "symbol": symbol, "direction": direction, "confidence": confidence, "reason": reason, "message": "Order sent; waiting result"}
        self._log("TRADE_OPEN", f"{symbol} {direction} amount={self.config.investment_amount}")
        return trade

    async def _resolve_manual_symbol(self, random_if_auto: bool = False) -> str:
        if self.config.symbol.strip().upper() not in {"AUTO", "AUTO_OTC", "OTC_AUTO"}:
            return self.config.symbol
        assets = await self.adapter.list_assets()
        otc = [a for a in assets if "OTC" in a.upper() or a.lower().endswith("otc")]
        choices = otc or assets or ["eur_usdotc"]
        return random.choice(choices) if random_if_auto else choices[0]

    async def _candidate_assets(self) -> list[str]:
        if self.config.symbol.strip().upper() not in {"AUTO", "AUTO_OTC", "OTC_AUTO"}:
            return [self.config.symbol]
        assets = await self.adapter.list_assets()
        otc = [a for a in assets if "OTC" in a.upper() or a.lower().endswith("otc")]
        raw = (otc or assets or ["EURUSD_otc"])
        now = time()
        filtered = [a for a in raw if self.pair_cooldowns.get(a, 0) <= now and a not in self.blacklisted_pairs]
        return (filtered or [a for a in raw if a not in self.blacklisted_pairs] or raw)[:12]

    async def _find_best_setup(self, deadline: float | None = None):
        candidates = await self._candidate_assets()
        if deadline is None:
            deadline = time() + min(max(self.config.analysis_seconds, 5), 60)
        else:
            # Never exceed configured analysis duration, but use the full remaining minute window when possible.
            deadline = min(deadline, time() + min(max(self.config.analysis_seconds, 5), 60))
        while time() < deadline and self.running:
            for asset in candidates:
                try:
                    if hasattr(self.adapter, "get_recent_candles"):
                        candles = await self.adapter.get_recent_candles(asset, count=80, period=60)
                        if candles:
                            self._candles[asset] = candles[-100:]
                            self._series[asset] = [float(c.get("close", 0) or 0) for c in candles][-100:]
                            continue
                    price = await self.adapter.latest_price(asset)
                    arr = self._series.setdefault(asset, [])
                    arr.append(price)
                    self._series[asset] = arr[-100:]
                except Exception:
                    continue
            await asyncio.sleep(2)
        best = None
        for asset in candidates:
            score = self._score_asset(asset, self._series.get(asset, []), self._candles.get(asset, []))
            if score is None:
                continue
            try:
                sentiment = await self.adapter.get_realtime_sentiment(asset) if hasattr(self.adapter, "get_realtime_sentiment") else None
                score = self._apply_sentiment(score, sentiment)
            except Exception:
                pass
            if best is None or score[2] > best[2]:
                best = score
        # No more random fallback in safe/normal modes: after a loss streak, quality is more important than frequency.
        if best is None and candidates and self.config.strategy_mode == "aggressive":
            asset = random.choice(candidates)
            direction = random.choice(["CALL", "PUT"])
            return asset, direction, 50, "aggressive fallback random OTC"
        if best is not None:
            threshold = max(self.config.min_confidence, {"safe": 90, "normal": 75, "aggressive": 0}.get(self.config.strategy_mode, 75))
            if best[2] < threshold and self.config.strategy_mode != "aggressive":
                self._log("FILTER", f"{best[0]} {best[1]} confidence={best[2]} below threshold={threshold}")
                return None
        return best

    def _apply_sentiment(self, score, sentiment):
        if not sentiment:
            return score
        asset, direction, confidence, reason = score
        try:
            data = sentiment if isinstance(sentiment, dict) else {}
            call = float(data.get("call", data.get("buy", data.get("up", data.get("higher", 0)))) or 0)
            put = float(data.get("put", data.get("sell", data.get("down", data.get("lower", 0)))) or 0)
            if call <= 1 and put <= 1:
                call *= 100; put *= 100
            sent_dir = "CALL" if call >= put else "PUT"
            edge = abs(call - put)
            if edge >= 8:
                if sent_dir == direction:
                    confidence = min(95, int(confidence + min(8, edge / 3)))
                    reason += f", sentiment confirms {sent_dir} {max(call, put):.0f}%"
                else:
                    confidence = max(0, int(confidence - min(10, edge / 2)))
                    reason += f", sentiment divergence {sent_dir} {max(call, put):.0f}%"
        except Exception:
            return score
        return asset, direction, confidence, reason

    def _score_asset(self, asset: str, closes: List[float], candles: list[dict] | None = None):
        candles = candles or []
        if candles and len(candles) >= 5:
            closes = [float(c.get("close", 0) or 0) for c in candles]
            highs = [float(c.get("high", c.get("close", 0)) or 0) for c in candles]
            lows = [float(c.get("low", c.get("close", 0)) or 0) for c in candles]
        else:
            highs = closes[:]
            lows = closes[:]
        if len(closes) < 8:
            return None

        buy = 0
        sell = 0
        reason_parts: list[str] = []
        price = closes[-1]

        # 1) Support / resistance is now a core filter.
        sr = support_resistance(highs, lows, closes, lookback=min(40, len(closes)))
        if sr:
            near_support = sr["dist_support"] <= 0.18 or price <= sr["recent_low"] + sr["range"] * 0.18
            near_resistance = sr["dist_resistance"] <= 0.18 or price >= sr["recent_high"] - sr["range"] * 0.18
            if near_support:
                buy += 24; reason_parts.append(f"near support {sr['support']:.6f}")
            if near_resistance:
                sell += 24; reason_parts.append(f"near resistance {sr['resistance']:.6f}")
            if sr["position"] < 0.28:
                buy += 8; reason_parts.append("lower range bounce zone")
            if sr["position"] > 0.72:
                sell += 8; reason_parts.append("upper range rejection zone")

        # 2) Trend / moving-average alignment.
        ema9 = ema(closes, min(9, len(closes)))
        ema21 = ema(closes, min(21, len(closes))) if len(closes) >= 21 else sma(closes, min(9, len(closes)))
        sma50 = sma(closes, min(50, len(closes))) if len(closes) >= 20 else None
        if ema9 and ema21:
            if ema9 > ema21 and price >= ema9:
                buy += 18; reason_parts.append("EMA9>EMA21 bullish")
            if ema9 < ema21 and price <= ema9:
                sell += 18; reason_parts.append("EMA9<EMA21 bearish")
        if sma50:
            if price > sma50: buy += 8; reason_parts.append("price above SMA50")
            if price < sma50: sell += 8; reason_parts.append("price below SMA50")

        # 3) Momentum confirmation.
        rv = rsi(closes, min(14, max(2, len(closes) - 1)))
        if rv is not None:
            if 38 <= rv <= 58 and len(closes) >= 3 and closes[-1] > closes[-2]:
                buy += 9; reason_parts.append(f"RSI balanced rising {rv:.1f}")
            if 42 <= rv <= 62 and len(closes) >= 3 and closes[-1] < closes[-2]:
                sell += 9; reason_parts.append(f"RSI balanced falling {rv:.1f}")
            if rv < 35:
                buy += 12; reason_parts.append(f"RSI oversold {rv:.1f}")
            if rv > 65:
                sell += 12; reason_parts.append(f"RSI overbought {rv:.1f}")
        stoch = stochastic(highs, lows, closes, min(14, len(closes)))
        if stoch is not None:
            if stoch < 25:
                buy += 10; reason_parts.append(f"stochastic oversold {stoch:.1f}")
            if stoch > 75:
                sell += 10; reason_parts.append(f"stochastic overbought {stoch:.1f}")

        # 4) MACD / momentum and candle confirmation.
        mv = macd(closes)
        if mv:
            if mv["hist"] > 0:
                buy += 9; reason_parts.append("MACD bullish")
            if mv["hist"] < 0:
                sell += 9; reason_parts.append("MACD bearish")
        if len(closes) >= 4:
            if closes[-1] > closes[-2] > closes[-3]:
                buy += 8; reason_parts.append("3-candle bullish momentum")
            if closes[-1] < closes[-2] < closes[-3]:
                sell += 8; reason_parts.append("3-candle bearish momentum")
        if candles:
            cs = candle_strength(candles[-1])
            if cs["lower_wick"] > 0.45 and cs["bull"]:
                buy += 10; reason_parts.append("bullish rejection wick")
            if cs["upper_wick"] > 0.45 and cs["bear"]:
                sell += 10; reason_parts.append("bearish rejection wick")
            if cs["body_ratio"] < 0.12:
                buy -= 6; sell -= 6; reason_parts.append("weak/doji candle penalty")

        # 5) Bollinger + ATR volatility filter.
        bb = bollinger(closes, min(20, len(closes)), 2.0)
        av = atr(highs, lows, closes, min(14, max(2, len(closes) - 1)))
        if bb:
            width_ratio = bb["width"] / max(price, 1e-9)
            if price <= bb["lower"]:
                buy += 10; reason_parts.append("Bollinger lower bounce")
            if price >= bb["upper"]:
                sell += 10; reason_parts.append("Bollinger upper rejection")
            if width_ratio < 0.00018:
                buy -= 8; sell -= 8; reason_parts.append("low volatility penalty")
        if av and sr:
            if av / max(sr["range"], 1e-9) > 0.75:
                buy -= 7; sell -= 7; reason_parts.append("volatile spike penalty")

        direction = "CALL" if buy >= sell else "PUT"
        raw_score = max(buy, sell)
        opposite = min(buy, sell)
        edge = max(0, raw_score - opposite)
        confidence = min(95, max(0, int(raw_score * 0.72 + edge * 0.55)))

        # Strong mode must have clear edge and S/R context. This avoids random entries after loss streaks.
        if self.config.strategy_mode == "safe":
            has_sr = any("support" in r or "resistance" in r for r in reason_parts)
            if not has_sr or edge < 18 or confidence < max(88, self.config.min_confidence):
                return None
        elif self.config.strategy_mode == "normal" and edge < 10:
            return None

        reason = ", ".join(reason_parts[:7]) or "advanced multi-indicator analysis"
        if sr:
            reason += f" | S={sr['support']:.6f} R={sr['resistance']:.6f}"
        return asset, direction, confidence, reason

    async def _settle_trade(self, trade: TradeRecord, result_check_time: float | None = None):
        self.last_analysis = {"status": "WAITING_RESULT", "symbol": trade.symbol, "direction": trade.direction, "message": "Waiting 60s result"}
        result_used = False
        if hasattr(self.adapter, "check_trade_result"):
            try:
                timeout = int(60 + settings.result_delay_seconds + settings.entry_lead_seconds + 10)
                status, profit = await self.adapter.check_trade_result(trade.id, timeout)
                trade.result = "WIN" if str(status).lower() == "win" else "LOSS"
                trade.pnl = float(profit) if profit is not None else (trade.amount * 0.86 if trade.result == "WIN" else -trade.amount)
                trade.closed_at = time(); result_used = True
            except Exception:
                result_used = False
        if not result_used:
            target = result_check_time or (time() + 60 + settings.result_delay_seconds)
            wait = max(0, target - time())
            await asyncio.sleep(wait)
            exit_price = await self.adapter.latest_price(trade.symbol)
            trade.exit_price = exit_price; trade.closed_at = time()
            win = exit_price > (trade.entry_price or exit_price) if trade.direction == "CALL" else exit_price < (trade.entry_price or exit_price)
            trade.result = "WIN" if win else "LOSS"; trade.pnl = trade.amount * 0.86 if win else -trade.amount
        if hasattr(self.adapter, "balance"):
            self.adapter.balance += trade.pnl
        if hasattr(self.adapter, "session_pnl"):
            self.adapter.session_pnl += trade.pnl
        self.session_pnl += float(trade.pnl or 0)
        st = self.pair_stats.setdefault(trade.symbol, {"wins": 0, "losses": 0, "total": 0})
        st["total"] += 1
        if trade.result == "LOSS":
            st["losses"] += 1
            self.consecutive_losses += 1
            if self.config.cooldown_after_loss_minutes > 0:
                self.cooldown_until = time() + self.config.cooldown_after_loss_minutes * 60
            if self.config.pair_cooldown_minutes > 0:
                self.pair_cooldowns[trade.symbol] = time() + self.config.pair_cooldown_minutes * 60
            if st["losses"] >= self.config.auto_blacklist_losses:
                self.blacklisted_pairs.add(trade.symbol)
                self._log("BLACKLIST", f"{trade.symbol} blacklisted after {st['losses']} losses")
        elif trade.result == "WIN":
            st["wins"] += 1
            self.consecutive_losses = 0
        st["accuracy"] = round((st["wins"] / st["total"]) * 100, 2) if st["total"] else 0
        self.last_analysis = {"status": "RESULT", "symbol": trade.symbol, "direction": trade.direction, "result": trade.result, "pnl": trade.pnl, "session_pnl": self.session_pnl, "consecutive_losses": self.consecutive_losses, "step": trade.step}
        self._log("RESULT", f"{trade.symbol} {trade.result} pnl={round(trade.pnl, 2)} session={round(self.session_pnl, 2)} step={trade.step}")
        self.current_signal = None
        if trade.result == "LOSS" and self.config.martingale_enabled and trade.step < self.config.max_martingale_steps and self.running:
            if await self._risk_limit_reached():
                return
            mg_amount = self.config.investment_amount * (2 ** (trade.step + 1))
            entry_time = self._next_minute_boundary()
            execute_time = max(time(), entry_time - settings.entry_lead_seconds)
            result_check_time = entry_time + 60.0 + settings.result_delay_seconds
            self.current_signal = {"symbol": trade.symbol, "direction": trade.direction, "confidence": 0, "reason": f"Martingale step {trade.step + 1}", "entry_time": entry_time, "execute_time": execute_time, "expiry_time": entry_time + 60.0, "result_check_time": result_check_time, "amount": mg_amount, "status": "SCHEDULED"}
            self._log("MARTINGALE", f"{trade.symbol} step={trade.step + 1} amount={mg_amount}")
            delay = max(0, execute_time - time())
            while delay > 0 and self.running:
                await asyncio.sleep(min(0.25, delay)); delay = execute_time - time()
            if self.running:
                mg_trade = await self._place_trade(trade.symbol, trade.direction, 0, f"Martingale step {trade.step + 1}", entry_time, result_check_time, amount=mg_amount, step=trade.step + 1)
                await self._settle_trade(mg_trade, result_check_time)
            return
        await self._risk_limit_reached()

    def _next_minute_boundary(self) -> float:
        now = int(time())
        return float(now - (now % 60) + 60)

    def _next_entry_boundary(self, min_analysis_seconds: int = 10) -> float:
        """Return the nearest M1 boundary that still leaves enough time to analyze and send the signal."""
        now = time()
        entry = self._next_minute_boundary()
        available = entry - settings.entry_lead_seconds - now
        if available < min_analysis_seconds:
            entry += 60.0
        return entry

    async def open_random_trade_now(self, amount: float = 1.0) -> TradeRecord:
        symbol = await self._resolve_manual_symbol(random_if_auto=True)
        direction = random.choice(["CALL", "PUT"])
        entry_time = time()
        result_check_time = entry_time + 60 + settings.result_delay_seconds
        trade = await self._place_trade(symbol, direction, 0, "Immediate random test trade", entry_time, result_check_time)
        asyncio.create_task(self._settle_trade(trade, result_check_time))
        return trade

    def request_stop_after_current(self):
        self.stop_requested_after_current = True
        self._log("STOP_AFTER_CURRENT", "Will stop after current trade/result")
        self.last_analysis = {"status": "STOP_AFTER_CURRENT", "message": "Will stop after current trade/result"}

    def _stats(self) -> dict:
        closed = [t for t in self.history if t.result != "PENDING"]
        wins = sum(1 for t in closed if t.result == "WIN")
        losses = sum(1 for t in closed if t.result == "LOSS")
        total = wins + losses
        accuracy = round((wins / total) * 100, 2) if total else 0.0
        return {"total": total, "wins": wins, "losses": losses, "accuracy": accuracy, "session_pnl": round(self.session_pnl, 2), "consecutive_losses": self.consecutive_losses}

    def _log(self, event: str, message: str):
        self.logs.insert(0, {"time": time(), "event": event, "message": message})
        self.logs = self.logs[:200]

    def status(self):
        return {"running": self.running, "config": self.config.model_dump(), "trades_count": len(self.history), "last_analysis": self.last_analysis, "current_signal": self.current_signal, "session_pnl": self.session_pnl, "consecutive_losses": self.consecutive_losses, "stats": self._stats(), "logs": self.logs[:80], "stop_after_current": self.stop_requested_after_current, "pair_stats": self.pair_stats, "blacklist": list(self.blacklisted_pairs)}
