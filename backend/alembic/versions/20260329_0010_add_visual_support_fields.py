"""add persisted visual support fields to draft_artifacts

Revision ID: 20260329_0010
Revises: 20260325_0009
Create Date: 2026-03-29 05:20:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.engine.reflection import Inspector
from sqlalchemy.dialects.postgresql import JSONB

revision = "20260329_0010"
down_revision = "20260325_0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = Inspector.from_engine(conn)
    tables = inspector.get_table_names()
    if "draft_artifacts" not in tables:
        return

    existing_cols = {column["name"] for column in inspector.get_columns("draft_artifacts")}
    if "visual_specs" not in existing_cols:
        op.add_column(
            "draft_artifacts",
            sa.Column(
                "visual_specs",
                JSONB(astext_type=sa.Text()).with_variant(sa.JSON(), "sqlite"),
                nullable=False,
                server_default=sa.text("'[]'"),
            ),
        )
    if "math_expressions" not in existing_cols:
        op.add_column(
            "draft_artifacts",
            sa.Column(
                "math_expressions",
                JSONB(astext_type=sa.Text()).with_variant(sa.JSON(), "sqlite"),
                nullable=False,
                server_default=sa.text("'[]'"),
            ),
        )


def downgrade() -> None:
    conn = op.get_bind()
    inspector = Inspector.from_engine(conn)
    tables = inspector.get_table_names()
    if "draft_artifacts" not in tables:
        return

    existing_cols = {column["name"] for column in inspector.get_columns("draft_artifacts")}
    if "math_expressions" in existing_cols:
        op.drop_column("draft_artifacts", "math_expressions")
    if "visual_specs" in existing_cols:
        op.drop_column("draft_artifacts", "visual_specs")
