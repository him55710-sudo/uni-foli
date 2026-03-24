"""add quality_level and safety fields

Revision ID: 20260322_0008
Revises: 20260322_0007
Create Date: 2026-03-22 07:00:00.000000
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.engine.reflection import Inspector
from sqlalchemy.dialects.postgresql import JSONB

revision = '20260322_0008'
down_revision = '20260322_0007'
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = Inspector.from_engine(conn)

    # workshop_sessions: quality_level 컬럼 추가
    ws_cols = [c["name"] for c in inspector.get_columns("workshop_sessions")] if "workshop_sessions" in inspector.get_table_names() else []
    if "quality_level" not in ws_cols:
        op.add_column("workshop_sessions", sa.Column("quality_level", sa.String(length=8), nullable=False, server_default="mid"))

    # draft_artifacts: safety/quality 메타 컬럼 추가
    da_cols = [c["name"] for c in inspector.get_columns("draft_artifacts")] if "draft_artifacts" in inspector.get_table_names() else []
    if "quality_level_applied" not in da_cols:
        op.add_column("draft_artifacts", sa.Column("quality_level_applied", sa.String(length=8), nullable=True))
    if "safety_score" not in da_cols:
        op.add_column("draft_artifacts", sa.Column("safety_score", sa.Integer(), nullable=True))
    if "safety_flags" not in da_cols:
        op.add_column("draft_artifacts", sa.Column("safety_flags", JSONB(astext_type=sa.Text()), nullable=True))
    if "quality_downgraded" not in da_cols:
        op.add_column("draft_artifacts", sa.Column("quality_downgraded", sa.Boolean(), nullable=False, server_default="false"))


def downgrade() -> None:
    conn = op.get_bind()
    inspector = Inspector.from_engine(conn)

    da_cols = [c["name"] for c in inspector.get_columns("draft_artifacts")] if "draft_artifacts" in inspector.get_table_names() else []
    for col in ["quality_downgraded", "safety_flags", "safety_score", "quality_level_applied"]:
        if col in da_cols:
            op.drop_column("draft_artifacts", col)

    ws_cols = [c["name"] for c in inspector.get_columns("workshop_sessions")] if "workshop_sessions" in inspector.get_table_names() else []
    if "quality_level" in ws_cols:
        op.drop_column("workshop_sessions", "quality_level")
