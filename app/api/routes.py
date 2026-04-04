"""HTTP routes for health checks and scan orchestration endpoints."""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter

from app.db.repositories import ScanRepository
from app.db.session import get_db_session
from app.services.orchestrator import Orchestrator

router = APIRouter()


@router.get("/health")
def healthcheck() -> dict:
    return {"status": "ok", "ts": datetime.now(UTC).isoformat()}


@router.post("/scan/run")
def run_scan_once() -> dict:
    cards = Orchestrator().run_scan_cycle()
    return {"count": len(cards), "items": [c.model_dump() for c in cards]}


@router.get("/recommendations")
def list_recommendations(limit: int = 50) -> dict:
    with get_db_session() as db:
        repo = ScanRepository(db)
        recs = repo.list_recommendations(limit=limit)
    return {
        "count": len(recs),
        "items": [
            {
                "id": r.id,
                "symbol": r.symbol,
                "option_symbol": r.option_symbol,
                "recommendation": r.recommendation,
                "confidence": r.confidence,
                "scorecard": r.scorecard,
                "reason": r.reason,
                "created_at": r.created_at.isoformat(),
                "rejected": r.rejected,
            }
            for r in recs
        ],
    }

