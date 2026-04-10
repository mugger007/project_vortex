# weekly-options-scanner

Production framework for US equity weekly options premium-selling recommendations.

The system scans for large option-premium jumps, applies hard filters/risk gates, runs analysis + synthesis, and outputs reviewable recommendation cards. It does not auto-trade.

Each module under `app/` includes a short file-level description comment, and key public functions carry docstrings so the runtime flow is easier to trace while reading the source.

## Data Provider Responsibilities

- Moomoo OpenD (local SDK):
  - Option expiration dates and option chains
  - Account funds, positions, and position Greeks
  - Option quote snapshots (including OI and pricing fields)
- Massive REST API:
  - Underlying bars
  - News
  - Dividends
  - Ticker reference/overview lookups
  - Historical window and rate-limit constrained transport for analysis inputs
- Alpha Vantage REST API:
  - Earnings calendar lookups used in event-risk analysis
- yfinance:
  - Index intraday snapshots used by market-regime analytics (`^VIX`, `^GSPC`)
  - Index previous-close change calculations used in market-regime summaries
- Gemini API:
  - Structured JSON generation for overreaction and recommendation synthesis

## Project Structure and Key Functions

```text
weekly-options-scanner/
|-- app/
|   |-- __main__.py
|   |-- config.py
|   |-- scheduler.py
|   |-- clients/
|   |   |-- alpha_vantage_client.py
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
|   `-- utils/
|-- tests/
|   |-- conftest.py
|   |-- test_imports.py
|   |-- test_orchestrator.py
|   |-- test_market_regime_unit.py
|   |-- test_recommendation_engine_unit.py
|   |-- test_monitoring_scanner_unit.py
|   `-- live/
|       |-- test_alpha_vantage_live.py
|       |-- test_event_risk_live.py
|       |-- test_market_regime_live.py
|       |-- test_monitoring_scanner_live.py
|       |-- test_recommendation_engine_live.py
|       |-- conftest.py
|       |-- test_massive_live.py
|       |-- test_moomoo_live.py
|       |-- test_overreaction_live.py
|       |-- test_trends_live.py
|       |-- test_volatility_live.py
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
- `app/clients/alpha_vantage_client.py`: Alpha Vantage earnings-calendar adapter.
- `app/clients/gemini_client.py`: Gemini integration for narrative/synthesis generation.
- `app/clients/yfinance_client.py`: yfinance adapter for intraday, daily, and fast-info spot lookups.
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
- `app/utils/`: reusable utility functions shared across modules.
- `tests/test_imports.py`: import smoke test for base module integrity.
- `tests/conftest.py`: deterministic shared fixtures for unit tests.
- `tests/test_orchestrator.py`: isolated orchestration unit test using monkeypatched dependencies.
- `tests/test_market_regime_unit.py`: deterministic market regime scoring tests using mocked yfinance metrics.
- `tests/test_recommendation_engine_unit.py`: recommendation/scorecard unit tests including hard-block behavior.
- `tests/test_monitoring_scanner_unit.py`: scanner unit tests for jump-threshold and OTM pass/reject paths.
- `tests/live/conftest.py`: `--run-live` gating, provider readiness checks, and live-symbol fixtures.
- `tests/live/test_moomoo_live.py`: live OpenD validation for quotes/options/funds/positions/Greeks.
- `tests/live/test_massive_live.py`: live Massive validation for bars/news/calendar/dividends/index bars.
- `tests/live/test_alpha_vantage_live.py`: live Alpha Vantage earnings calendar validation.
- `tests/live/test_monitoring_scanner_live.py`: live scanner smoke validation with real Moomoo option-chain/snapshot flow.
- `tests/live/test_overreaction_live.py`: live overreaction analyzer validation using Massive news + Gemini output.
- `tests/live/test_trends_live.py`: live trend analyzer validation.
- `tests/live/test_volatility_live.py`: live volatility analyzer validation.
- `tests/live/test_event_risk_live.py`: live event-risk analyzer validation.
- `tests/live/test_market_regime_live.py`: live yfinance-driven market regime validation.
- `tests/live/test_recommendation_engine_live.py`: live recommendation synthesis validation using direct live analyzer outputs with deterministic fallback.
- `tests/live/test_e2e_live.py`: full orchestrator live integration test.

## Testing Notes

- Unit tests are deterministic and isolated from external infra/providers.
- Live tests are gated behind `--run-live` and should use `live_symbols` from `tests/live/conftest.py` rather than hardcoded tickers.
- Live recommendation test is intentionally decoupled from cross-test artifact dependencies.
- Source files are documented with module-level descriptions and key-function docstrings to make the pipeline easier to follow.

## Status

Repository is configured for live-provider validation, local deployment, and persisted JSON artifacts under `artifacts/test-output/` for live test inspection.
