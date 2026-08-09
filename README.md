# Quotex Bot App — Architecture Scaffold

Cross-platform trading bot application scaffold for local testing first, with future Railway backend deployment.

> Risk notice: Trading is risky. This repository is a technical scaffold. It defaults to paper/demo mode and does not guarantee profits. Ensure any API usage complies with platform terms.

## Structure

```text
quotex-bot-app/
  frontend/   Flutter UI scaffold
  backend/    FastAPI bot core + local API
  docs/       Architecture and API reference
```

## Quick backend start

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app:app --reload --host 0.0.0.0 --port 8000
```

Open:

```text
http://localhost:8000/docs
```

## Online mode

The Flutter app default backend is now `https://quotex-bot-app-1.onrender.com`. You can still change it at runtime from Settings. The app automatically derives WebSocket as `wss://quotex-bot-app-1.onrender.com/ws`.

Codemagic generates Android platform files if missing and outputs installable APK artifacts.

## Phase 4 additions

- Flutter Quotex Login screen.
- FastAPI auth endpoints for pyquotex session creation.
- In-memory PyQuotexAdapter integration boundary.
- Root `codemagic.yaml` for Flutter APK builds.

## Safety defaults

- `PAPER_MODE=true` by default.
- Real trade execution is blocked until a real adapter is implemented and explicitly enabled.
- Quotex API adapter is an interface/stub to be connected later.

## Server region note

If Quotex login says the service is unavailable in the United States, deploy the backend on a VPS/host in a supported region and set that backend URL in the app Settings. See `docs/SERVER_REGION_AR.md`.

## APK size optimization

Codemagic release workflow uses `--split-per-abi`, `--obfuscate`, and `--split-debug-info`. Install the `arm64-v8a` APK on most modern phones/TV boxes for a much smaller APK than universal debug builds. Debug APKs are expected to be large.

## Launcher icon

The app icon source is `frontend/assets/app_icon.png` and Codemagic generates Android launcher icons during the build using `flutter_launcher_icons`.

## Analysis/Direct modes

The dashboard now supports two execution modes:

- Direct mode: no analysis; trades selected asset using chosen CALL/PUT.
- Analysis mode: scans available OTC assets for up to 20 seconds by default and only trades when confidence is at least 80%.

Telegram notifications are sent from backend when `TELEGRAM_ENABLED=true`, `TELEGRAM_BOT_TOKEN`, and `TELEGRAM_CHAT_ID` are set in hosting environment variables.
