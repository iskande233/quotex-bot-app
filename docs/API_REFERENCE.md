# API Reference

## Health

`GET /health`

## Bot control

`POST /api/v1/bot/start`

Body:

```json
{
  "symbol": "EURUSD-OTC",
  "timeframe": "M1",
  "investment_amount": 1,
  "max_trades": 10,
  "enabled": true
}
```

`POST /api/v1/bot/stop`

`GET /api/v1/bot/status`

## Execution mode

`POST /api/v1/mode/{mode}`

Allowed modes:

- `paper`
- `demo`
- `real` placeholder

## Trades

`POST /api/v1/trade`

```json
{
  "symbol": "EURUSD-OTC",
  "direction": "CALL",
  "amount": 1,
  "duration_seconds": 60
}
```

`GET /api/v1/balance`

`GET /api/v1/history`

## WebSocket

`GET /ws`

Broadcast snapshot every second:

```json
{
  "type": "snapshot | trade_opened | trade_result | bot_started | bot_stopped | mode_changed",
  "price": 1.02345,
  "candles": [{"time": 123, "open": 1, "high": 1, "low": 1, "close": 1}],
  "balance": {},
  "status": {},
  "history": []
}
```
