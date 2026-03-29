# weekly-options-scanner

Production-ready framework for US equity weekly options premium-selling recommendations.

This application scans for large option premium jumps, applies hard filters and risk gates, runs multi-layer analysis, and produces human-review recommendation cards. It does not auto-trade.

## What This Project Uses

- FastAPI for API endpoints and scheduler lifecycle.
- Streamlit for dashboard/UI.
- PostgreSQL (SQLAlchemy + Alembic) for persistence.
- Redis for snapshot and low-latency state cache.
- Massive REST API for underlying stocks and indices data.
- Moomoo OpenD daemon (local SDK connection) for options and account/position data.
- Gemini for synthesis and recommendation generation.

## Data Source Architecture

- Moomoo OpenD daemon (local binary protocol):
  - Option expiration dates: `get_option_expiration_date`
  - Option chains: `get_option_chain`
  - Account balances, positions, Greeks, snapshots
- Massive REST API:
  - Underlying bars, news, earnings/dividends, index snapshot

Design rule: all Moomoo data is fetched through OpenD methods, not REST calls.

## Prerequisites

- Python 3.11+
- Docker Desktop (or local PostgreSQL 14+ and Redis 7+)
- Moomoo OpenD desktop app running locally
- API credentials:
  - `MASSIVE_API_KEY`
  - `GEMINI_API_KEY`

## Installation and Setup

### 1. Create and activate virtual environment

Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

macOS/Linux:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 2. Install dependencies

```bash
pip install --upgrade pip setuptools wheel
pip install -e .
```

For development tools (pytest, mypy, ruff):

```bash
pip install -e ".[dev]"
```

### 3. Create `.env`

This project does not keep `.env.example`. Create `.env` manually in project root:

```env
APP_ENV=dev
LOG_LEVEL=INFO

API_HOST=0.0.0.0
API_PORT=8000
STREAMLIT_PORT=8501

SCAN_INTERVAL_MINUTES=10
MAX_MASSIVE_CALLS_PER_MINUTE=5

POSTGRES_DSN=postgresql+psycopg://postgres:postgres@localhost:5432/weekly_options
REDIS_URL=redis://localhost:6379/0

MASSIVE_API_KEY=your_real_massive_key
MASSIVE_BASE_URL=https://api.massive.com

MOOMOO_OPEND_HOST=127.0.0.1
MOOMOO_OPEND_PORT=11111

GEMINI_API_KEY=your_real_gemini_key
GEMINI_MODEL=gemini-1.5-pro

TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=
ALERT_EMAIL_TO=
ALERT_EMAIL_FROM=
SMTP_HOST=
SMTP_PORT=587
SMTP_USER=
SMTP_PASSWORD=

BACKTEST_MODE=false
```

### 4. Start infrastructure

```bash
docker compose up -d
```

Verify:

```bash
docker ps
```

### 5. Run migrations

```bash
alembic upgrade head
```

### 6. Verify with one scan

```bash
python -m app --mode scan-once
```

## Running the App

### API + scheduler

```bash
python -m app --mode api
```

### Dashboard

```bash
streamlit run app/dashboard/streamlit_app.py --server.port 8501
```

### Other modes

```bash
python -m app --mode scheduler
python -m app --mode scan-once
python -m app --mode backtest --backtest-start 2024-01-01 --backtest-end 2024-12-31 --backtest-symbols SPY,QQQ,NVDA
```

## API Endpoints

- `GET /api/health`
- `POST /api/scan/run`
- `GET /api/recommendations?limit=50`

## Testing

The test suite is now live-oriented under `tests/live` and safely gated.

### Default run (safe)

```bash
pytest tests/ -v
```

- Runs non-live checks.
- Live tests are skipped unless explicitly enabled.

### Run live smoke and live unit tests

```bash
pytest tests/live -v --run-live -m "live and not e2e"
```

### Run full live suite including end-to-end

```bash
pytest tests/live -v --run-live
```

### Live test prerequisites and skip behavior

Live tests automatically skip when prerequisites are missing:

- `MASSIVE_API_KEY` missing/placeholder
- Moomoo OpenD socket unavailable at `MOOMOO_OPEND_HOST:MOOMOO_OPEND_PORT`
- `GEMINI_API_KEY` missing/placeholder (for e2e)
- PostgreSQL/Redis unreachable (for e2e)

Optional symbol overrides for live tests:

- `LIVE_MASSIVE_SYMBOL` (default `SPY`)
- `LIVE_MOOMOO_QUOTE_SYMBOL` (default `US.AAPL`)
- `LIVE_MOOMOO_OPTION_SYMBOL` (default `US.AAPL`)

## Troubleshooting

### Moomoo connection refused

- Ensure OpenD app is running and logged in.
- Confirm OpenD host/port match `.env`.

### PostgreSQL connection failures

- Confirm Docker containers are running.
- Validate `POSTGRES_DSN` in `.env`.

### Redis connection failures

- Confirm Redis container is running.
- Validate `REDIS_URL` in `.env`.

### Massive 429 rate-limit errors

- Increase `SCAN_INTERVAL_MINUTES`.
- Reduce watchlist size.
- Keep `MAX_MASSIVE_CALLS_PER_MINUTE` conservative.

### Gemini auth failures

- Verify `GEMINI_API_KEY` value.
- Restart app after updating `.env`.

## Operational Notes

- Keep OpenD running during scans.
- Use `audit_logs` and `recommendations` tables for decision traceability.
- Scheduler interval defaults to 10 minutes; tune based on provider limits.

## Project Layout (Key Paths)

- `app/clients/massive_client.py`
- `app/clients/moomoo_client.py`
- `app/scanner/monitoring_scanner.py`
- `app/services/orchestrator.py`
- `app/api/main.py`
- `tests/live/`

## Status

Ready for local deployment and live-provider validation with gated test execution.
