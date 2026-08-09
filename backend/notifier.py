from __future__ import annotations
import urllib.request
import urllib.parse
import json
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
        # Do not break trading loop if Telegram fails.
        pass


def fmt_symbol(symbol: str) -> str:
    return symbol.replace("_otc", "-OTC").replace("_OTC", "-OTC").replace("/", "").upper()


def send_trade_opened(trade: TradeRecord) -> None:
    direction = "CALL 🔼 (شراء)" if trade.direction == "CALL" else "PUT 🔻 (بيع)"
    chart = "📈" if trade.direction == "CALL" else "📉"
    text = f"""{settings.brand_name}

💲 *صفقة جديدة* 💲
━━━━━━━━━━━
📊 *الزوج:* {fmt_symbol(trade.symbol)}
⏱️ *المدة:* M1
💰 *المبلغ:* {trade.amount}
{chart} *الاتجاه:* {direction}
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


def send_bot_started(balance, config) -> None:
    analysis_mode = "تشغيل بالتحليل" if getattr(config, "use_analysis", True) else "تشغيل بدون تحليل"
    symbol = getattr(config, "symbol", "AUTO_OTC")
    confidence = getattr(config, "min_confidence", 80)
    seconds = getattr(config, "analysis_seconds", 20)
    amount = getattr(config, "investment_amount", 1)
    max_trades = getattr(config, "max_trades", 10)
    text = f"""{settings.brand_name}

🤖 *البوت متصل ويعمل الآن* ✅
━━━━━━━━━━━
💼 *نوع الحساب:* {balance.mode}
💰 *الرصيد الحالي:* {balance.balance}
📈 *وضع التشغيل:* {analysis_mode}
📊 *الزوج:* {symbol}
💵 *المبلغ:* {amount}
🔢 *Max Trades:* {max_trades}
⚡ *قوة التحليل:* {confidence}%
⏱️ *مدة التحليل:* {seconds}s
━━━━━━━━━━━
🚀 بدأ البحث عن أفضل صفقة M1"""
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
