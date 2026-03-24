"""add draft_artifacts + stream_token to workshop_sessions

Revision ID: 20260322_0007
Revises: 20260322_0006
Create Date: 2026-03-22 06:00:00.000000
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.engine.reflection import Inspector
from sqlalchemy.dialects.postgresql import JSONB

revision = '20260322_0007'
down_revision = '20260322_0006'
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = Inspector.from_engine(conn)
    tables = inspector.get_table_names()

    # stream_token column on workshop_sessions
    existing_cols = [c["name"] for c in inspector.get_columns("workshop_sessions")] if "workshop_sessions" in tables else []
    if "workshop_sessions" in tables and "stream_token" not in existing_cols:
        op.add_column("workshop_sessions", sa.Column("stream_token", sa.String(length=128), nullable=True))
        op.create_index("ix_workshop_sessions_stream_token", "workshop_sessions", ["stream_token"], unique=True)

    if "draft_artifacts" not in tables:
        op.create_table(
            "draft_artifacts",
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("session_id", sa.String(length=36), nullable=False),
            sa.Column("report_markdown", sa.Text(), nullable=True),
            sa.Column("teacher_record_summary_500", sa.Text(), nullable=True),
            sa.Column("student_submission_note", sa.Text(), nullable=True),
            sa.Column("evidence_map", JSONB(astext_type=sa.Text()), nullable=True),
            sa.Column("render_status", sa.String(length=32), nullable=False),
            sa.Column("error_message", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["session_id"], ["workshop_sessions.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_draft_artifacts_session_id", "draft_artifacts", ["session_id"], unique=False)


def downgrade() -> None:
    conn = op.get_bind()
    inspector = Inspector.from_engine(conn)
    tables = inspector.get_table_names()

    if "draft_artifacts" in tables:
        op.drop_index("ix_draft_artifacts_session_id", table_name="draft_artifacts")
        op.drop_table("draft_artifacts")

    if "workshop_sessions" in tables:
        existing_cols = [c["name"] for c in inspector.get_columns("workshop_sessions")]
        if "stream_token" in existing_cols:
            op.drop_index("ix_workshop_sessions_stream_token", table_name="workshop_sessions")
            op.drop_column("workshop_sessions", "stream_token")
