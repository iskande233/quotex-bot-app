# pyquotex / Quotex Wrapper Integration

Phase 4 adds the integration boundary for a real Demo Account adapter.

## Frontend

Flutter includes a `Quotex Login` screen:

- Email
- Password
- Account Type: Demo / Real

It calls:

```text
POST /api/v1/auth/login
POST /api/v1/auth/logout
GET  /api/v1/auth/session
```

## Backend

`PyQuotexAdapter` is implemented in:

```text
backend/quotex_adapter.py
```

It dynamically imports:

```python
from pyquotex.stable_api import Quotex
```

Different GitHub forks may expose different names/methods, so only this adapter needs to be adjusted when choosing the exact wrapper.

## Security

- Credentials are not written to disk.
- Session is kept in memory.
- Use Demo first.
- Real mode is explicit and should only be used with user-owned credentials and in compliance with platform terms.

## Install selected wrapper

After selecting the exact wrapper/fork, install it in the backend environment. Example:

```bash
pip install pyquotex
```

or:

```bash
pip install git+https://github.com/OWNER/REPO.git
```

Then update `PyQuotexAdapter` method mappings if needed:

- `connect`
- `get_balance`
- `get_candles` / `get_realtime_candles`
- `buy` / `trade` / `place_order`

## Railway

Set environment variables:

```text
QUOTEX_MODE=paper     # paper/demo/real
PAPER_MODE=true       # keep true until real wrapper is ready
```

For demo wrapper testing:

```text
QUOTEX_MODE=demo
PAPER_MODE=false
```
