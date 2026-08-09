# Railway Deploy

This project uses Docker with Python 3.12 because the selected pyquotex wrapper requires Python >= 3.12.

1. Create a new Railway project.
2. Connect this GitHub repository.
3. Railway will use the root `Dockerfile`.
4. Set environment variables:

```text
QUOTEX_MODE=paper
PAPER_MODE=true
DEFAULT_SYMBOL=EURUSD-OTC
DEFAULT_INVESTMENT=1
MAX_TRADES=10
```

For demo mode:

```text
QUOTEX_MODE=demo
PAPER_MODE=false
```

Real mode remains a placeholder until a compliant Quotex wrapper is integrated.

After deploy, use:

```text
https://your-railway-url/health
https://your-railway-url/docs
wss://your-railway-url/ws
```

For Flutter, run with:

```bash
flutter run --dart-define=API_BASE_URL=https://your-railway-url --dart-define=API_WS_URL=wss://your-railway-url/ws
```
