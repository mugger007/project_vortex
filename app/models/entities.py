from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class ScanRun(Base):
    __tablename__ = "scan_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)


class SnapshotCache(Base):
    __tablename__ = "snapshot_cache"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    symbol: Mapped[str] = mapped_column(String(32), index=True)
    option_symbol: Mapped[str] = mapped_column(String(64), index=True)
    expiry: Mapped[str] = mapped_column(String(16), index=True)
    snapshot_ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    premium: Mapped[float] = mapped_column(Float, nullable=False)
    oi: Mapped[int] = mapped_column(Integer, nullable=False)
    volume: Mapped[int] = mapped_column(Integer, nullable=False)
    bid: Mapped[float] = mapped_column(Float, nullable=False)
    ask: Mapped[float] = mapped_column(Float, nullable=False)
    raw_json: Mapped[dict] = mapped_column(JSON, default=dict)


class Recommendation(Base):
    __tablename__ = "recommendations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    scan_run_id: Mapped[int] = mapped_column(Integer, index=True)
    symbol: Mapped[str] = mapped_column(String(32), index=True)
    option_symbol: Mapped[str] = mapped_column(String(64), index=True)
    recommendation: Mapped[str] = mapped_column(String(32), nullable=False)
    confidence: Mapped[int] = mapped_column(Integer, nullable=False)
    scorecard: Mapped[int] = mapped_column(Integer, nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    suggested_strike: Mapped[float | None] = mapped_column(Float, nullable=True)
    suggested_delta: Mapped[float | None] = mapped_column(Float, nullable=True)
    estimated_theta: Mapped[float | None] = mapped_column(Float, nullable=True)
    estimated_vega: Mapped[float | None] = mapped_column(Float, nullable=True)
    rejected: Mapped[bool] = mapped_column(Boolean, default=False)
    full_payload_json: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class PositionSnapshot(Base):
    __tablename__ = "position_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    account_id: Mapped[str] = mapped_column(String(64), index=True)
    symbol: Mapped[str] = mapped_column(String(32), index=True)
    option_symbol: Mapped[str] = mapped_column(String(64), index=True)
    quantity: Mapped[float] = mapped_column(Float, nullable=False)
    delta: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    vega: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    market_value: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    raw_json: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    scan_run_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    stage: Mapped[str] = mapped_column(String(64), nullable=False)
    level: Mapped[str] = mapped_column(String(16), nullable=False, default="INFO")
    message: Mapped[str] = mapped_column(Text, nullable=False)
    payload_json: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
