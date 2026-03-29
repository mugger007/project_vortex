# weekly-options-scanner

Production framework for US equity weekly options premium-selling recommendations.

The system scans for large option-premium jumps, applies hard filters/risk gates, runs analysis + synthesis, and outputs reviewable recommendation cards. It does not auto-trade.

## Data Provider Responsibilities

- Moomoo OpenD (local SDK):
  - Option expiration dates and option chains
  - Account funds, positions, and position Greeks
  - Quote snapshots
- Massive REST API:
  - Underlying bars
  - News
  - Dividends
  - Index aggregate bars

## Project Structure and Key Functions

```text
weekly-options-scanner/
|-- app/
|   |-- __main__.py
|   |-- config.py
|   |-- scheduler.py
|   |-- clients/
|   |   |-- massive_client.py
|   |   |-- moomoo_client.py
|   |   `-- gemini_client.py
|   |-- scanner/
|   |   `-- monitoring_scanner.py
|   |-- analysis/
|   |   |-- market_regime.py
|   |   |-- volatility.py
|   |   |-- overreaction.py
|   |   |-- trends.py
|   |   `-- event_risk.py
|   |-- risk/
|   |   `-- portfolio_engine.py
|   |-- synthesis/
|   |-- services/
|   |   |-- orchestrator.py
|   |   `-- alerts.py
|   |-- api/
|   |   |-- main.py
|   |   `-- routes.py
|   |-- dashboard/
|   |   `-- streamlit_app.py
|   |-- db/
|   |-- models/
|   |-- cache/
|   `-- utils/
|-- tests/
|   |-- test_imports.py
|   `-- live/
|       |-- conftest.py
|       |-- test_massive_live.py
|       |-- test_moomoo_live.py
|       `-- test_e2e_live.py
|-- alembic/
|-- artifacts/
|   `-- test-output/
|-- docker-compose.yml
|-- alembic.ini
|-- pyproject.toml
|-- DEPLOYMENT_CHECKLIST.md
|-- MOOMOO_OPEND.md
`-- README.md
```

## File and Folder Reference

- `app/__main__.py`: CLI entrypoint and app mode selection (api, scheduler, scan-once, backtest).
- `app/config.py`: central settings model and environment-variable loading.
- `app/scheduler.py`: APScheduler wiring and scan cadence control.
- `app/clients/massive_client.py`: Massive REST transport, throttling/retry, and market-data fetch methods.
- `app/clients/moomoo_client.py`: OpenD quote/trade contexts and wrappers for funds/positions/Greeks/options/snapshot.
- `app/clients/gemini_client.py`: Gemini integration for narrative/synthesis generation.
- `app/scanner/monitoring_scanner.py`: option-universe pull + filtering pipeline over provider clients.
- `app/analysis/`: signal and market-state analytics (regime, volatility, trends, event risk, overreaction).
- `app/risk/portfolio_engine.py`: portfolio-level risk evaluation and gating logic.
- `app/synthesis/`: recommendation shaping and final card payload assembly.
- `app/services/orchestrator.py`: end-to-end scan-cycle orchestrator across scanner, analysis, risk, synthesis, persistence.
- `app/services/alerts.py`: outbound notification integrations.
- `app/api/main.py`: FastAPI app bootstrap/lifecycle.
- `app/api/routes.py`: HTTP endpoints (health, run-scan, recommendations).
- `app/dashboard/streamlit_app.py`: Streamlit operations and monitoring UI.
- `app/db/`: database session, migrations integration points, and persistence helpers.
- `app/models/`: ORM/domain models (scan runs, recommendations, audit data, etc.).
- `app/cache/`: Redis cache helper logic and key access paths.
- `app/utils/`: reusable utility functions shared across modules.
- `tests/test_imports.py`: import smoke test for base module integrity.
- `tests/live/conftest.py`: `--run-live` gating, provider readiness checks, and live-symbol fixtures.
- `tests/live/test_moomoo_live.py`: live OpenD validation for quotes/options/funds/positions/Greeks.
- `tests/live/test_massive_live.py`: live Massive validation for bars/news/calendar/dividends/index bars.
- `tests/live/test_e2e_live.py`: full orchestrator live integration test.

## Status

Repository is configured for live-provider validation and local deployment.
