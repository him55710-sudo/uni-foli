from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.engine.reflection import Inspector

# revision identifiers, used by Alembic.
revision = "20260322_0003"
down_revision = "20260322_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = Inspector.from_engine(conn)
    tables = inspector.get_table_names()
    if "parsed_documents" not in tables:
        return

    existing_columns = {column["name"] for column in inspector.get_columns("parsed_documents")}
    if "status" not in existing_columns:
        op.add_column(
            "parsed_documents",
            sa.Column("status", sa.String(length=32), nullable=False, server_default="uploaded"),
        )
    if "masking_status" not in existing_columns:
        op.add_column(
            "parsed_documents",
            sa.Column("masking_status", sa.String(length=32), nullable=False, server_default="pending"),
        )
    if "parse_attempts" not in existing_columns:
        op.add_column(
            "parsed_documents",
            sa.Column("parse_attempts", sa.Integer(), nullable=False, server_default="0"),
        )
    if "last_error" not in existing_columns:
        op.add_column("parsed_documents", sa.Column("last_error", sa.Text(), nullable=True))
    if "parse_started_at" not in existing_columns:
        op.add_column("parsed_documents", sa.Column("parse_started_at", sa.DateTime(timezone=True), nullable=True))
    if "parse_completed_at" not in existing_columns:
        op.add_column("parsed_documents", sa.Column("parse_completed_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    conn = op.get_bind()
    inspector = Inspector.from_engine(conn)
    tables = inspector.get_table_names()
    if "parsed_documents" not in tables:
        return

    existing_columns = {column["name"] for column in inspector.get_columns("parsed_documents")}
    for column_name in [
        "parse_completed_at",
        "parse_started_at",
        "last_error",
        "parse_attempts",
        "masking_status",
        "status",
    ]:
        if column_name in existing_columns:
            op.drop_column("parsed_documents", column_name)
