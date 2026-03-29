from __future__ import annotations

from datetime import datetime

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.models.entities import AuditLog, PositionSnapshot, Recommendation, ScanRun, SnapshotCache


class ScanRepository:
    def __init__(self, db: Session):
        self.db = db

    def create_scan_run(self, started_at: datetime, metadata_json: dict) -> ScanRun:
        run = ScanRun(started_at=started_at, status="running", metadata_json=metadata_json)
        self.db.add(run)
        self.db.flush()
        return run

    def complete_scan_run(self, run_id: int, finished_at: datetime, status: str, metadata_json: dict) -> None:
        run = self.db.get(ScanRun, run_id)
        if run is None:
            return
        run.finished_at = finished_at
        run.status = status
        run.metadata_json = metadata_json

    def save_snapshot(self, payload: dict) -> SnapshotCache:
        obj = SnapshotCache(**payload)
        self.db.add(obj)
        self.db.flush()
        return obj

    def get_previous_snapshot(self, option_symbol: str) -> SnapshotCache | None:
        stmt = (
            select(SnapshotCache)
            .where(SnapshotCache.option_symbol == option_symbol)
            .order_by(desc(SnapshotCache.snapshot_ts))
            .limit(1)
        )
        return self.db.execute(stmt).scalar_one_or_none()

    def save_recommendation(self, payload: dict) -> Recommendation:
        obj = Recommendation(**payload)
        self.db.add(obj)
        self.db.flush()
        return obj

    def save_position_snapshot(self, payload: dict) -> PositionSnapshot:
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
        log = AuditLog(
            scan_run_id=scan_run_id,
            stage=stage,
            level=level,
            message=message,
            payload_json=payload_json,
            created_at=datetime.now().astimezone(),
        )
        self.db.add(log)

    def list_recommendations(self, limit: int = 50) -> list[Recommendation]:
        stmt = select(Recommendation).order_by(desc(Recommendation.created_at)).limit(limit)
        return list(self.db.execute(stmt).scalars().all())
