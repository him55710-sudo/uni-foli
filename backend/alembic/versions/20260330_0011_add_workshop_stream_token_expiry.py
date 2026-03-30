"""add workshop stream token expiry

Revision ID: 20260330_0011
Revises: 20260329_0010
Create Date: 2026-03-30 02:55:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.engine.reflection import Inspector

revision = "20260330_0011"
down_revision = "20260329_0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = Inspector.from_engine(conn)
    tables = inspector.get_table_names()
    if "workshop_sessions" not in tables:
        return

    existing_cols = {column["name"] for column in inspector.get_columns("workshop_sessions")}
    if "stream_token_expires_at" not in existing_cols:
        op.add_column(
            "workshop_sessions",
            sa.Column("stream_token_expires_at", sa.DateTime(timezone=True), nullable=True),
        )


def downgrade() -> None:
    conn = op.get_bind()
    inspector = Inspector.from_engine(conn)
    tables = inspector.get_table_names()
    if "workshop_sessions" not in tables:
        return

    existing_cols = {column["name"] for column in inspector.get_columns("workshop_sessions")}
    if "stream_token_expires_at" in existing_cols:
        op.drop_column("workshop_sessions", "stream_token_expires_at")
