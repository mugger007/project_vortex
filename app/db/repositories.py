"""Database repository layer for scan runs, snapshots, and recommendations."""

from __future__ import annotations

import math
from datetime import datetime
from typing import Any

from sqlalchemy import delete, desc, select
from sqlalchemy.orm import Session

from app.models.entities import AuditLog, PositionSnapshot, Recommendation, ScanRun, SnapshotCache


class ScanRepository:
    def __init__(self, db: Session):
        """Wrap a SQLAlchemy session with scan-specific persistence helpers."""
        self.db = db

    def _sanitize_json(self, value: Any) -> Any:
        """Normalize nested payloads for safe PostgreSQL JSON storage."""
        # PostgreSQL JSON does not accept NaN/Infinity tokens or datetime objects.
        if isinstance(value, datetime):
            return value.isoformat()
        if isinstance(value, float):
            return value if math.isfinite(value) else None
        if isinstance(value, dict):
            return {k: self._sanitize_json(v) for k, v in value.items()}
        if isinstance(value, list):
            return [self._sanitize_json(v) for v in value]
        if isinstance(value, tuple):
            return [self._sanitize_json(v) for v in value]
        return value

    def create_scan_run(self, started_at: datetime, metadata_json: dict) -> ScanRun:
        """Create a new scan run row and return the persisted entity."""
        run = ScanRun(
            started_at=started_at,
            status="running",
            metadata_json=self._sanitize_json(metadata_json),
        )
        self.db.add(run)
        self.db.flush()
        return run

    def complete_scan_run(self, run_id: int, finished_at: datetime, status: str, metadata_json: dict) -> None:
        """Mark a scan run as complete and store summary metadata."""
        run = self.db.get(ScanRun, run_id)
        if run is None:
            return
        run.finished_at = finished_at
        run.status = status
        run.metadata_json = self._sanitize_json(metadata_json)

    def save_snapshot(self, payload: dict) -> SnapshotCache:
        """Persist a snapshot cache row after JSON sanitization."""
        payload = dict(payload)
        if "raw_json" in payload:
            payload["raw_json"] = self._sanitize_json(payload["raw_json"])
        obj = SnapshotCache(**payload)
        self.db.add(obj)
        self.db.flush()
        return obj

    def get_previous_snapshot(self, option_symbol: str) -> SnapshotCache | None:
        """Return the latest snapshot for the requested option symbol."""
        stmt = (
            select(SnapshotCache)
            .where(SnapshotCache.option_symbol == option_symbol)
            .order_by(desc(SnapshotCache.snapshot_ts))
            .limit(1)
        )
        return self.db.execute(stmt).scalar_one_or_none()

    def save_recommendation(self, payload: dict) -> Recommendation:
        """Persist a recommendation row after JSON sanitization."""
        payload = dict(payload)
        if "full_payload_json" in payload:
            payload["full_payload_json"] = self._sanitize_json(payload["full_payload_json"])
        obj = Recommendation(**payload)
        self.db.add(obj)
        self.db.flush()
        return obj

    def clear_position_snapshots(self) -> None:
        """Remove all stored position snapshots before ingesting a fresh account snapshot."""
        self.db.execute(delete(PositionSnapshot))

    def save_position_snapshot(self, payload: dict) -> PositionSnapshot:
        """Persist a single position snapshot row."""
        obj = PositionSnapshot(**payload)
        self.db.add(obj)
        self.db.flush()
        return obj

    def add_audit_log(
        self,
        stage: str,
        message: str,
        payload_json: dict,
        scan_run_id: int | None = None,
        level: str = "INFO",
    ) -> None:
        """Append a structured audit log row for the current scan run."""
        log = AuditLog(
            scan_run_id=scan_run_id,
            stage=stage,
            level=level,
            message=message,
            payload_json=self._sanitize_json(payload_json),
            created_at=datetime.now().astimezone(),
        )
        self.db.add(log)

    def list_recommendations(self, limit: int = 50) -> list[Recommendation]:
        """Return the most recent recommendations ordered by creation time."""
        stmt = select(Recommendation).order_by(desc(Recommendation.created_at)).limit(limit)
        return list(self.db.execute(stmt).scalars().all())

