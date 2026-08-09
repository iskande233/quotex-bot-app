# Architecture

## Modes

1. Local client-side testing mode: Flutter app communicates with local FastAPI backend.
2. Future server mode: backend can be deployed to Railway.
3. Execution adapters:
   - `PaperQuotexAdapter`: local simulated account.
   - `DemoQuotexAdapter`: separated demo scaffold, currently simulated until a compliant wrapper is connected.
   - `RealQuotexAdapter`: explicit placeholder only.

## Flow

START -> connect adapter -> wait candle close -> analyze -> place 60s trade -> settle -> log result -> WebSocket broadcast.

## WebSocket

Backend broadcasts once per second:

- account/balance
- bot status
- OHLC candles
- trade history
- event type for popups

## Flutter

- START / STOP buttons call backend endpoints.
- Settings page changes symbol, amount, max trades, timeframe, and execution mode.
- Candlestick chart paints backend OHLC candles.
- SnackBar popups show trade open/result events.

## Safety

Default is paper mode. Real adapter must be implemented explicitly with user-owned credentials/session and in compliance with platform terms.
