"""initial schema

Revision ID: 0001_init
Revises:
Create Date: 2026-03-29 00:00:00
"""

from alembic import op
import sqlalchemy as sa


revision = "0001_init"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "scan_runs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
    )

    op.create_table(
        "snapshot_cache",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("symbol", sa.String(length=32), nullable=False),
        sa.Column("option_symbol", sa.String(length=64), nullable=False),
        sa.Column("expiry", sa.String(length=16), nullable=False),
        sa.Column("snapshot_ts", sa.DateTime(timezone=True), nullable=False),
        sa.Column("premium", sa.Float(), nullable=False),
        sa.Column("oi", sa.Integer(), nullable=False),
        sa.Column("volume", sa.Integer(), nullable=False),
        sa.Column("bid", sa.Float(), nullable=False),
        sa.Column("ask", sa.Float(), nullable=False),
        sa.Column("raw_json", sa.JSON(), nullable=False),
    )
    op.create_index("ix_snapshot_cache_symbol", "snapshot_cache", ["symbol"])
    op.create_index("ix_snapshot_cache_option_symbol", "snapshot_cache", ["option_symbol"])
    op.create_index("ix_snapshot_cache_expiry", "snapshot_cache", ["expiry"])
    op.create_index("ix_snapshot_cache_snapshot_ts", "snapshot_cache", ["snapshot_ts"])

    op.create_table(
        "recommendations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("scan_run_id", sa.Integer(), nullable=False),
        sa.Column("symbol", sa.String(length=32), nullable=False),
        sa.Column("option_symbol", sa.String(length=64), nullable=False),
        sa.Column("recommendation", sa.String(length=32), nullable=False),
        sa.Column("confidence", sa.Integer(), nullable=False),
        sa.Column("scorecard", sa.Integer(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("suggested_strike", sa.Float(), nullable=True),
        sa.Column("suggested_delta", sa.Float(), nullable=True),
        sa.Column("estimated_theta", sa.Float(), nullable=True),
        sa.Column("estimated_vega", sa.Float(), nullable=True),
        sa.Column("rejected", sa.Boolean(), nullable=False),
        sa.Column("full_payload_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_recommendations_scan_run_id", "recommendations", ["scan_run_id"])
    op.create_index("ix_recommendations_symbol", "recommendations", ["symbol"])
    op.create_index("ix_recommendations_option_symbol", "recommendations", ["option_symbol"])

    op.create_table(
        "position_snapshots",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("account_id", sa.String(length=64), nullable=False),
        sa.Column("symbol", sa.String(length=32), nullable=False),
        sa.Column("option_symbol", sa.String(length=64), nullable=False),
        sa.Column("quantity", sa.Float(), nullable=False),
        sa.Column("delta", sa.Float(), nullable=False),
        sa.Column("vega", sa.Float(), nullable=False),
        sa.Column("market_value", sa.Float(), nullable=False),
        sa.Column("raw_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_position_snapshots_account_id", "position_snapshots", ["account_id"])
    op.create_index("ix_position_snapshots_symbol", "position_snapshots", ["symbol"])
    op.create_index("ix_position_snapshots_option_symbol", "position_snapshots", ["option_symbol"])

    op.create_table(
        "audit_logs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("scan_run_id", sa.Integer(), nullable=True),
        sa.Column("stage", sa.String(length=64), nullable=False),
        sa.Column("level", sa.String(length=16), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("payload_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_audit_logs_scan_run_id", "audit_logs", ["scan_run_id"])


def downgrade() -> None:
    op.drop_index("ix_audit_logs_scan_run_id", table_name="audit_logs")
    op.drop_table("audit_logs")

    op.drop_index("ix_position_snapshots_option_symbol", table_name="position_snapshots")
    op.drop_index("ix_position_snapshots_symbol", table_name="position_snapshots")
    op.drop_index("ix_position_snapshots_account_id", table_name="position_snapshots")
    op.drop_table("position_snapshots")

    op.drop_index("ix_recommendations_option_symbol", table_name="recommendations")
    op.drop_index("ix_recommendations_symbol", table_name="recommendations")
    op.drop_index("ix_recommendations_scan_run_id", table_name="recommendations")
    op.drop_table("recommendations")

    op.drop_index("ix_snapshot_cache_snapshot_ts", table_name="snapshot_cache")
    op.drop_index("ix_snapshot_cache_expiry", table_name="snapshot_cache")
    op.drop_index("ix_snapshot_cache_option_symbol", table_name="snapshot_cache")
    op.drop_index("ix_snapshot_cache_symbol", table_name="snapshot_cache")
    op.drop_table("snapshot_cache")

    op.drop_table("scan_runs")
