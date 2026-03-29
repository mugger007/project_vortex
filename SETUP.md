# Setup Guide

Complete step-by-step instructions to get `weekly-options-scanner` running locally.

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Environment Setup](#environment-setup)
3. [Configure Credentials](#configure-credentials)
4. [Install Dependencies](#install-dependencies)
5. [Start Infrastructure](#start-infrastructure)
6. [Run Migrations](#run-migrations)
7. [Verify Installation](#verify-installation)
8. [Troubleshooting](#troubleshooting)

## Prerequisites

- **Python 3.11 or higher**
- **Git**
- **Docker & Docker Compose** (for PostgreSQL and Redis)
- **Moomoo OpenD** (for live account data)

### Check Python version

```bash
python --version
```

If you have multiple Python installations, use `python3.11` or `python3.12` explicitly.

## Environment Setup

### 1. Clone the repository

```bash
cd Projects
git clone <repo-url> weekly-options-scanner
cd weekly-options-scanner
```

### 2. Create a virtual environment

A **virtual environment** isolates Python dependencies for this project from system-wide packages.

#### Windows (PowerShell)

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

If you get a permission error, run PowerShell as Administrator or allow execution policy:
```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

#### macOS / Linux

```bash
python3 -m venv .venv
source .venv/bin/activate
```

**Verify activation**: Your command prompt should show `(.venv)` at the start.

### 3. Upgrade pip, setuptools, and wheel

```bash
pip install --upgrade pip setuptools wheel
```

## Install Dependencies

With your virtual environment activated:

```bash
pip install -e .
```

The `.` installs the current package in editable mode. This reads `pyproject.toml` and installs all dependencies:
- FastAPI, Uvicorn (API server)
- Streamlit (dashboard)
- PostgreSQL async driver, SQLAlchemy (ORM)
- Redis client
- Pandas, NumPy, pandas-ta (analytics)
- APScheduler (cron jobs)
- Google Generative AI SDK
- Moomoo Python SDK
- structlog (logging)
- Many others

### Optional: Install dev dependencies

For testing and linting:

```bash
pip install -e ".[dev]"
```

## Start Infrastructure

### Docker Compose (PostgreSQL + Redis)

Start the containers:

```bash
docker compose up -d
```

**Verify they're running**:

```bash
docker ps
```

You should see two containers: `postgres` and `redis`.

**Check logs**:

```bash
docker compose logs
```

**Stop containers** (when done):

```bash
docker compose down
```

### Manual setup (if not using Docker)

If you prefer manual postgres/redis setup:

- **PostgreSQL**: Create a database `weekly_options` on `localhost:5432`
- **Redis**: Ensure it's running on `localhost:6379`
- Update `POSTGRES_DSN` and `REDIS_URL` in `.env` accordingly

## Run Migrations

Initialize the database schema using Alembic:

```bash
alembic upgrade head
```

**Verify**: The command should print `Running upgrade ... -> 0001_init ...` and complete successfully.

## Verify Installation

### 1. Test imports

```bash
python -c "import app; print('Imports OK')"
```

### 2. Check database connectivity

```bash
python -c "from app.db.session import engine; print('DB:', engine.url)"
```

### 3. Test a dry-run scan

```bash
python -m app --mode scan-once
```

This runs a single scan cycle to validate all integrations. It will take ~30-60 seconds and should:
- Connect to Massive API
- Query option snapshots
- Run analysis on filtered candidates
- Synthetic results will show in the logs

If successful, you'll see logs like:
```
scheduled_scan_started interval=10
scheduled_scan_finished
```

## Running the System

Once verified, you can start the full system:

### 1. Start API + Scheduler (in one terminal)

```bash
python -m app --mode api
```

This starts:
- FastAPI on `http://0.0.0.0:8000`
- APScheduler in-process (polls every 10 minutes)

### 2. Start Dashboard (in another terminal, same venv)

```bash
streamlit run app/dashboard/streamlit_app.py --server.port 8501
```

Open dashboard: `http://localhost:8501`

### 3. Trigger a scan manually

```bash
# In a third terminal
curl -X POST http://localhost:8000/api/scan/run
```

Or click "Run Scan Now" in the Streamlit dashboard.

## Troubleshooting

### Virtual environment not found

**Error**: `(.venv) is not recognized as an internal command`

**Solution**: If using PowerShell, you may need to enable execution policy:
```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

Then activate again:
```powershell
.\.venv\Scripts\Activate.ps1
```

### ModuleNotFoundError: moomoo

**Error**: `ModuleNotFoundError: No module named 'moomoo'`

**Likely cause**: moomoo-api wasn't installed or Python environment isn't activated.

**Solution**:
1. Ensure `.venv` is activated (you should see `(.venv)` in your prompt)
2. Re-run: `pip install -e .`
3. Verify: `python -c "from moomoo import OpenQuoteContext"`

### Moomoo connection refused

**Error**: `ConnectionRefusedError: [Errno 111] Connection refused` or `Failed to connect to localhost:11111`

**Likely cause**: OpenD daemon isn't running.

**Solution**:
1. Open the Moomoo OpenD desktop application
2. Log in with your account
3. Wait for it to fully load and show "Ready" status
4. Re-run your scan

### PostgreSQL connection error

**Error**: `psycopg.OperationalError: connection failed`

**Solution**:
1. Verify Docker is running: `docker ps`
2. If containers aren't running, start them: `docker compose up -d`
3. Wait 10 seconds for postgres to initialize
4. Re-try your command

### Alembic migration failed

**Error**: `sqlalchemy.exc.OperationalError` during `alembic upgrade head`

**Solution**:
1. Ensure PostgreSQL is running: `docker ps`
2. Verify `POSTGRES_DSN` in `.env` is correct
3. Check migrations are in `alembic/versions/`: you should see `0001_init.py`
4. Re-run: `alembic upgrade head`

### "No recommendations yet" in dashboard

**Expected for first run**. The system waits for:
1. A scan to complete (check scheduler is running or trigger manually)
2. Candidates to pass hard liquidity filters (OI > 750, volume > 100, spread < 10%)
3. Analysis and synthesis to complete

Check logs for rejection reasons:
```bash
# In psql or tool of choice
SELECT stage, message FROM audit_logs ORDER BY created_at DESC LIMIT 20;
```

### Massive API rate limit (429 errors)

**Symptom**: Logs show `429` errors from Massive API.

**Solution**:
1. Increase `SCAN_INTERVAL_MINUTES` in `.env` (e.g., from 10 to 20)
2. Reduce watchlist size in `orchestrator.py`
3. Restart the scanner

### Gemini API errors

**Error**: `ValueError: API key is not valid` or authentication failures

**Solution**:
1. Verify your `GEMINI_API_KEY` in `.env` is correct
2. Check it's from: https://makersuite.google.com/app/apikey
3. Ensure it's enabled for the Generative AI Python SDK
4. Restart the scanner

## Next Steps

Once the system is running:

1. **Monitor logs**: Use `docker compose logs -f` to watch container logs
2. **Check the database**: Use your favorite SQL client to query `recommendations`, `audit_logs`, etc.
3. **Review recommendations** in the Streamlit dashboard
4. **Fine-tune parameters**: Adjust `SCAN_INTERVAL_MINUTES`, watchlist, filters, and risk limits in config/orchestrator
5. **Add integration tests**: See `tests/` for stubs

## Getting Help

- Check `README.md` for operational docs and configuration reference
- Review `app/__main__.py` for all run modes: `api`, `scheduler`, `scan-once`, `backtest`
- Inspect `audit_logs` table for detailed decision tracing
- Enable debug logging: set `LOG_LEVEL=DEBUG` in `.env`

---

**Happy scanning!**
