# Pre-Deployment Checklist

Use this checklist to ensure the system is properly configured before running in production.

## Environment & Dependencies

- [ ] Python 3.11+ installed: `python --version`
- [ ] Virtual environment created and activated: `.venv` folder exists, prompt shows `(.venv)`
- [ ] Dependencies installed: `pip install -e .`
- [ ] Dev dependencies installed (for testing): `pip install -e ".[dev]"`
- [ ] All imports work: `python -c "import app; from app.clients.massive_client import MassiveClient"`

## Configuration

- [ ] `.env` file exists (copied from `.env.example`)
- [ ] `.env` is in `.gitignore` (never commit secrets)
- [ ] All required env vars filled:
  - [ ] `MASSIVE_API_KEY` (valid, not placeholder)
  - [ ] `GEMINI_API_KEY` (valid, not placeholder)
  - [ ] `MOOMOO_OPEND_HOST` (default `127.0.0.1`)
  - [ ] `MOOMOO_OPEND_PORT` (default `11111`)
  - [ ] `POSTGRES_DSN` (valid connection string)
  - [ ] `REDIS_URL` (valid connection string)

## Infrastructure

- [ ] PostgreSQL running: `docker ps | grep postgres`
- [ ] Redis running: `docker ps | grep redis`
- [ ] Database initialized: `alembic upgrade head` succeeded
- [ ] All tables created: Check `\dt` in psql or similar

## Moomoo Setup (Critical)

- [ ] OpenD daemon installed from https://www.moomoo.com/download/OpenAPI
- [ ] OpenD application running and showing "Ready" status
- [ ] Port 11111 is open and listening
- [ ] Moomoo account logged in within OpenD
- [ ] Account has options trading enabled

## API & Integrations

- [ ] Massive API key is valid and has quota
- [ ] Gemini API key is valid and enabled
- [ ] Massive endpoint is reachable: `curl https://api.massive.com -I`
- [ ] Network allows outbound HTTPS to Massive and Google APIs

## Scanning Configuration

- [ ] `SCAN_INTERVAL_MINUTES` set appropriately (recommend 10-60)
- [ ] `MAX_MASSIVE_CALLS_PER_MINUTE` set to safe value (recommend 5 for free tier)
- [ ] Watchlist symbols in `orchestrator.py` are valid US/international stocks
- [ ] Hard filter thresholds reviewed (OI > 750, volume > 100, spread < 10%)
- [ ] Premium spike threshold confirmed (> 500%)

## Testing

- [ ] Run one-shot scan: `python -m app --mode scan-once`
- [ ] Scan completed without errors
- [ ] Audit logs show candidates found and processed
- [ ] API health check works: `curl http://localhost:8000/api/health`
- [ ] Integration tests pass: `pytest tests/ -v`

## Risk & Monitoring

- [ ] Risk engine parameters reviewed (max 5% per trade, etc.)
- [ ] Portfolio correlation limits configured
- [ ] Expected max drawdown thresholds reviewed
- [ ] Alerts configured (Telegram/email optional but recommended)
- [ ] Logging level set to INFO: `LOG_LEVEL=INFO` in `.env`

## Deployment Preparation

- [ ] Backup `.env` to secure location (not in repo)
- [ ] All credentials reviewed and valid
- [ ] Recommendation payloads validated (check `audit_logs` table)
- [ ] Dashboard accessible on port 8501: `streamlit run app/dashboard/streamlit_app.py`
- [ ] API accessible on port 8000 (or configured port)

## Production Readiness

- [ ] No hardcoded credentials in code (all from `.env`)
- [ ] Logging captures all errors and decisions
- [ ] Database backups enabled (if using managed database)
- [ ] Monitoring/alerting in place (optional: Prometheus, DataDog, etc.)
- [ ] Rate limits respected (Massive <5 calls/min on free tier)
- [ ] No continuous polling, scheduler interval respected (no 24/7 calls)

## First Run

1. [ ] Start API: `python -m app --mode api`
2. [ ] Start dashboard: `streamlit run app/dashboard/streamlit_app.py`
3. [ ] Manually trigger scan: `curl -X POST http://localhost:8000/api/scan/run`
4. [ ] Check results in dashboard
5. [ ] Review audit logs: `SELECT * FROM audit_logs ORDER BY created_at DESC LIMIT 20;`
6. [ ] Verify recommendations persisted: `SELECT * FROM recommendations ORDER BY created_at DESC LIMIT 10;`

## Go/No-Go Decision

Before running continuously:

- [ ] System responsiveness acceptable
- [ ] No errors in logs during test scan
- [ ] Recommendations appear reasonable
- [ ] All external integrations working
- [ ] Risk checks preventing inadvertent errors
- [ ] Team ready to review recommendations daily

---

**Status**: Ready for deployment ✓ / Needs fixing ✗

**Date**: ___________

**Reviewed by**: ___________
