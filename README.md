# weekly-options-scanner

Production-ready framework for **US equity weekly options premium-selling** (theta-decay) recommendations.

The system scans for extreme option premium spikes, applies hard liquidity/event/risk gates, performs multi-layer analysis, and generates **human-in-the-loop** recommendation cards. It never auto-trades.

## Core Capabilities

- FastAPI backend API for scan control and results retrieval.
- Streamlit dashboard for monitoring opportunities and recommendation cards.
- PostgreSQL persistence using SQLAlchemy + Alembic migrations.
- Redis cache for snapshot deltas and low-latency state.
- APScheduler polling loop (default every 10 minutes).
- Massive REST market data ingestion (no continuous WebSockets).
- Moomoo account/position ingestion via official Python SDK + local OpenD daemon.
- Google Gemini analysis for overreaction and final synthesis.
- Full audit trail in database for each scan stage and decision.
- Backtesting scaffold with historical replay entrypoints.

## Strategy Workflow

1. Poll Massive snapshots (interval from `SCAN_INTERVAL_MINUTES`, default 10).
2. Detect weekly-expiry Friday contracts with premium jump > 500% vs previous cached snapshot.
3. Apply hard liquidity gates:
   - OI > 750
   - Volume > 100/day
   - Bid-ask spread < 10% of premium
4. Analyze filtered contracts:
   - News overreaction probability (Gemini)
   - Volatility percentile (current-week HV vs historical distribution)
   - Trend profile (EMA/MA/momentum)
   - Event risk in next 5 days (earnings/dividend; macro hook included)
   - Market regime (VIX + broad market proxy)
5. Run portfolio risk checks from Moomoo account state:
   - Max 5% capital per trade
   - Portfolio delta/vega limits
   - Correlation cap > 0.7 rejected
   - Expected max drawdown check
6. Synthesize recommendation with weighted scorecard + Gemini structured JSON output.
7. Persist recommendation + full payload + audit logs.
8. Alert on high-confidence setups only (optional Telegram/email).

## Requirements

- Python 3.11+
- PostgreSQL 14+
- Redis 7+
- Moomoo OpenD daemon (local installation)
- API credentials for:
  - Massive
  - Google Gemini

**See [SETUP.md](SETUP.md) for detailed installation and configuration instructions.**

## Quick Start

### 1) Clone and create environment

```bash
python -m venv .venv
# Windows PowerShell
.\.venv\Scripts\Activate.ps1

pip install -e .
```

### 2) Start PostgreSQL and Redis

```bash
docker compose up -d
```

### 3) Configure environment

Copy `.env.example` to `.env` and fill credentials.

**Important**: `.env` is listed in `.gitignore` and should never be committed. It contains your real secrets.

### 4) Run migrations

```bash
alembic upgrade head
```

### 5) Start backend API + scheduler

```bash
python -m app --mode api
```

API will run on `http://0.0.0.0:8000` by default and scheduler starts in-process.

### 6) Start dashboard

```bash
streamlit run app/dashboard/streamlit_app.py --server.port 8501
```

Open `http://localhost:8501`.

## Run Modes

### API mode (default)

```bash
python -m app --mode api
```

Starts FastAPI and scheduler.

### Scheduler-only mode

```bash
python -m app --mode scheduler
```

Runs scanner loop without API server.

### One-shot scan

```bash
python -m app --mode scan-once
```

### Backtest replay mode (stub scaffold)

```bash
python -m app --mode backtest --backtest-start 2024-01-01 --backtest-end 2024-12-31 --backtest-symbols SPY,QQQ,NVDA
```

## API Endpoints

- `GET /api/health`
- `POST /api/scan/run`
- `GET /api/recommendations?limit=50`

## Rate-Limit Notes

- The scanner is **polling-based**, never continuous WebSocket.
- Poll interval is controlled by `SCAN_INTERVAL_MINUTES` (default 10).
- Massive calls are throttled through a per-minute limiter with retry/backoff.
- Set `MAX_MASSIVE_CALLS_PER_MINUTE=5` for free-tier safety.

## Configuration Reference

### Core runtime

- `APP_ENV`: environment tag (`dev`, `staging`, `prod`)
- `LOG_LEVEL`: logging level
- `API_HOST`, `API_PORT`: FastAPI bind settings
- `STREAMLIT_PORT`: dashboard port

### Scanning/rate limits

- `SCAN_INTERVAL_MINUTES`: polling interval for scanner (default 10)
- `MAX_MASSIVE_CALLS_PER_MINUTE`: local throttling cap

### Infrastructure

- `POSTGRES_DSN`: SQLAlchemy DSN
- `REDIS_URL`: Redis connection string

### Data providers

- `MASSIVE_API_KEY`, `MASSIVE_BASE_URL`: Massive market data provider
- `MOOMOO_OPEND_HOST`, `MOOMOO_OPEND_PORT`: Local OpenD daemon (default 127.0.0.1:11111)
- `GEMINI_API_KEY`, `GEMINI_MODEL`: Google Generative AI

### Optional alerts

- Telegram: `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`
- Email: `ALERT_EMAIL_TO`, `ALERT_EMAIL_FROM`, `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`

### Backtesting

- `BACKTEST_MODE`: toggle helper for deployment context

## Observability and Audit Trail

- Structured JSON logs via `structlog`.
- Every scan run persisted in `scan_runs`.
- Every recommendation persisted in `recommendations` with full payload.
- Every stage decision/error persisted in `audit_logs`.
- Daily option/account snapshots persisted in `snapshot_cache` and `position_snapshots`.

## Project Structure

```
weekly-options-scanner/
  app/
    __init__.py                     # package marker
    __main__.py                     # CLI entrypoint (api/scheduler/scan-once/backtest)
    config.py                       # .env-based settings model
    logging.py                      # structlog configuration
    scheduler.py                    # APScheduler setup with interval polling
    api/
      __init__.py
      main.py                       # FastAPI app + lifespan startup/shutdown
      routes.py                     # health, scan trigger, recommendations endpoints
    analysis/
      __init__.py
      overreaction.py               # Massive news + Gemini overreaction score
      volatility.py                 # current-week HV vs historical percentile
      trends.py                     # EMA/MA/momentum trend scoring
      event_risk.py                 # earnings/dividend near-term flags
      market_regime.py              # VIX/index regime scoring
    backtest/
      __init__.py
      replay.py                     # historical replay stub and contract
    cache/
      __init__.py
      redis_client.py               # Redis JSON/float cache wrapper
    clients/
      __init__.py
      massive_client.py             # Massive REST adapter with throttle/retry
      moomoo_client.py              # Moomoo OpenAPI adapter for balances/positions/greeks
      gemini_client.py              # Gemini text->JSON adapter
    db/
      __init__.py
      session.py                    # SQLAlchemy engine + session context manager
      repositories.py               # persistence operations and audit methods
    models/
      __init__.py                   # model exports
      base.py                       # SQLAlchemy declarative base
      entities.py                   # ORM entities: scans, snapshots, recs, audit
      schemas.py                    # pydantic domain schemas
    risk/
      __init__.py
      portfolio_engine.py           # position sizing, exposure, correlation, drawdown checks
    scanner/
      __init__.py
      filters.py                    # hard liquidity and weekly expiry filters
      monitoring_scanner.py         # spike detection and candidate generation
    services/
      __init__.py
      alerts.py                     # telegram/email alerts for high-confidence setups
      orchestrator.py               # end-to-end pipeline coordinator
    synthesis/
      __init__.py
      prompt_builder.py             # detailed Gemini synthesis prompt
      recommendation_engine.py      # weighted scorecard + Gemini recommendation
    dashboard/
      __init__.py
      streamlit_app.py              # Streamlit monitoring UI
    utils/
      __init__.py
      time.py                       # UTC helper
  alembic/
    env.py                          # Alembic runtime config
    script.py.mako                  # migration template
    versions/
      0001_init.py                  # initial schema migration
  alembic.ini                       # Alembic config
  docker-compose.yml                # local postgres + redis
  pyproject.toml                    # project metadata + dependencies
  .env.example                      # environment template
  README.md                         # operational documentation
  tests/                            # test package placeholder
```

## Monitoring Tips

- Use `GET /api/health` for liveness.
- Inspect `recommendations` and `audit_logs` tables for decision traceability.
- Keep scheduler interval at 10 minutes or more on free Massive plans.
- Watch for repeated 429 errors in logs and increase interval if needed.

## Running Tests

Run integration tests with mocked responses:

```bash
pip install -e ".[dev]"
pytest tests/ -v
```

Tests cover:
- Massive client rate-limiting and error handling
- Moomoo OpenAPI client lifecycle and data parsing
- Scanner spike detection and liquidity filters
- API endpoint responses and request/response validation

See `tests/` for full test suite.

## Troubleshooting

### No recommendations generated

- Confirm Massive API key is valid and returning options snapshots.
- Validate scanner watchlist symbols.
- Check hard gates (OI, volume, spread) and >500% spike requirement are naturally strict.
- Query `audit_logs` for rejection reasons.

### FastAPI starts but dashboard fails

- Ensure API host/port is reachable from Streamlit.
- If binding to `0.0.0.0`, dashboard can still use `localhost` endpoint.

### Migration errors

- Verify `POSTGRES_DSN` is correct.
- Re-run `alembic upgrade head` after database is up.

### Moomoo data errors

**Error**: `ConnectionRefusedError` when accessing Moomoo positions

**Likely cause**: OpenD daemon is not running.

**Solution**:
1. Open Moomoo OpenD desktop application (download from https://www.moomoo.com/download/OpenAPI)
2. Log in with your account
3. Verify it shows "Ready" status and is listening on localhost:11111
4. Re-run your scan or API

**Note**: OpenD daemon must remain running in the background. It's a persistent process, not started/stopped automatically.

## Production Hardening Checklist

- Add secrets manager (Vault/SM/KMS) instead of plaintext `.env`.
- Add message queue worker for asynchronous scans/alerts.
- Add metrics (Prometheus) and trace IDs in logs.
- Add full integration tests and historical replay correctness checks.
- Add explicit sector-mapping and macro calendar endpoint integration.
