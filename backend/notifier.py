from __future__ import annotations
import urllib.request
import json
from datetime import datetime
from models import TradeRecord
from config import settings


def _post_telegram(text: str) -> None:
    if not settings.telegram_enabled or not settings.telegram_bot_token or not settings.telegram_chat_id:
        return
    url = f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendMessage"
    payload = json.dumps({
        "chat_id": settings.telegram_chat_id,
        "text": text,
        "parse_mode": "Markdown",
    }).encode("utf-8")
    req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"}, method="POST")
    try:
        urllib.request.urlopen(req, timeout=8).read()
    except Exception:
        pass


def fmt_symbol(symbol: str) -> str:
    s = str(symbol or "").strip()
    low = s.lower()
    if low.endswith("otc"):
        base = low[:-3].replace("_", "").upper()
        return f"{base}-OTC"
    return s.replace("_", "").replace("/", "").upper()


def _time(ms_or_sec: float | int | None = None) -> str:
    if not ms_or_sec:
        return datetime.now().strftime("%H:%M:%S")
    v = float(ms_or_sec)
    if v > 10_000_000_000:
        v = v / 1000.0
    return datetime.fromtimestamp(v).strftime("%H:%M:%S")


def send_login_success(balance) -> None:
    text = f"""{settings.brand_name}

✅ *تم الاتصال بالمنصة بنجاح*
━━━━━━━━━━━
💼 *نوع الحساب:* {balance.mode}
💰 *الرصيد الحالي:* {balance.balance}
📡 *الحالة:* متصل وجاهز للعمل
━━━━━━━━━━━"""
    _post_telegram(text)


def send_bot_started(balance, config) -> None:
    analysis_mode = "تشغيل بالتحليل" if getattr(config, "use_analysis", True) else "تشغيل عشوائي/مباشر بدون تحليل"
    symbol = getattr(config, "symbol", "AUTO_OTC")
    confidence = getattr(config, "min_confidence", 80)
    seconds = getattr(config, "analysis_seconds", 20)
    amount = getattr(config, "investment_amount", 1)
    max_trades = getattr(config, "max_trades", 10)
    text = f"""{settings.brand_name}

🤖 *تم تشغيل البوت بنجاح* ✅
━━━━━━━━━━━
💼 *نوع الحساب:* {balance.mode}
💰 *الرصيد الحالي:* {balance.balance}
📈 *وضع التشغيل:* {analysis_mode}
📊 *الزوج:* {symbol}
💵 *المبلغ:* {amount}
🔢 *Max Trades:* {max_trades}
⚡ *نطاق التحليل:* {confidence}%
⏱️ *مدة التحليل:* {seconds}s
━━━━━━━━━━━
🚀 البوت بدأ البحث عن صفقة M1"""
    _post_telegram(text)


def send_bot_stopped(balance, config) -> None:
    text = f"""{settings.brand_name}

🛑 *تم إيقاف البوت*
━━━━━━━━━━━
💼 *نوع الحساب:* {balance.mode}
💰 *الرصيد الحالي:* {balance.balance}
📉 *Session PnL:* {balance.session_pnl}
━━━━━━━━━━━
✅ البوت متوقف الآن ولن يفتح صفقات جديدة."""
    _post_telegram(text)


def send_signal_scheduled(signal: dict) -> None:
    direction = signal.get("direction")
    direction_text = "CALL 🔼 (شراء)" if direction == "CALL" else "PUT 🔻 (بيع)"
    chart = "📈" if direction == "CALL" else "📉"
    confidence = signal.get("confidence", 0)
    reason = signal.get("reason", "")
    text = f"""{settings.brand_name}

💲 *صفقة جديدة* 💲
━━━━━━━━━━━
📊 *الزوج:* {fmt_symbol(signal.get('symbol'))}
⏱️ *المدة:* M1
🕒 *وقت الدخول:* {_time(signal.get('entry_time'))}
💵 *المبلغ:* {signal.get('amount')}
⚡ *القوة:* {confidence}%
{chart} *الاتجاه:* {direction_text}
━━━━━━━━━━━
🧠 {reason}
⏳ في انتظار وقت الدخول..."""
    _post_telegram(text)


def send_trade_opened(trade: TradeRecord) -> None:
    direction = "CALL 🔼 (شراء)" if trade.direction == "CALL" else "PUT 🔻 (بيع)"
    chart = "📈" if trade.direction == "CALL" else "📉"
    text = f"""{settings.brand_name}

✅ *تم دخول الصفقة فعلياً*
━━━━━━━━━━━
📊 *الزوج:* {fmt_symbol(trade.symbol)}
⏱️ *المدة:* M1
💰 *المبلغ:* {trade.amount}
{chart} *الاتجاه:* {direction}
🕒 *وقت الدخول:* {_time(trade.opened_at)}
━━━━━━━━━━━"""
    _post_telegram(text)


def send_trade_result(trade: TradeRecord) -> None:
    if trade.result == "WIN":
        text = f"""{settings.brand_name}:
🟢💰 *ربح مباشر* 💰🟢
━━━━━━━━━━━
WIN ✅
━━━━━━━━━━━"""
    else:
        text = f"""{settings.brand_name}:
💔 *خسارة* 💔
━━━━━━━━━━━
LOSS ❌
━━━━━━━━━━━"""
    _post_telegram(text)
