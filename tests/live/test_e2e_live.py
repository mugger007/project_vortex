from __future__ import annotations

import pytest
from sqlalchemy import select

from app.db.session import get_db_session
from app.models.entities import ScanRun
from app.services.orchestrator import Orchestrator


@pytest.mark.live
@pytest.mark.e2e
def test_live_end_to_end_scan_cycle(
    require_massive,
    require_moomoo,
    require_gemini,
    require_data_infra,
    live_symbols,
) -> None:
    orchestrator = Orchestrator()

    # Keep live E2E runtime bounded while still validating full pipeline.
    orchestrator.watchlist = [live_symbols["massive_symbol"]]

    cards = orchestrator.run_scan_cycle()

    assert isinstance(cards, list)

    with get_db_session() as db:
        latest_run = db.execute(select(ScanRun).order_by(ScanRun.id.desc()).limit(1)).scalar_one_or_none()

    assert latest_run is not None
    assert latest_run.status == "success"
    assert latest_run.metadata_json.get("watchlist_size") == 1
