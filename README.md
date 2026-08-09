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

The Flutter app now supports a runtime backend URL. Open Settings and set your Railway URL, e.g. `https://your-app.up.railway.app`. The app automatically derives WebSocket as `wss://your-app.up.railway.app/ws`.

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
