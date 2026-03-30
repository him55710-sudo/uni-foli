"""add inquiries table

Revision ID: 20260330_0012
Revises: 20260330_0011
Create Date: 2026-03-30 09:40:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.engine.reflection import Inspector

revision = "20260330_0012"
down_revision = "20260330_0011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = Inspector.from_engine(conn)
    tables = inspector.get_table_names()
    if "inquiries" in tables:
        return

    op.create_table(
        "inquiries",
        sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
        sa.Column("inquiry_type", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default=sa.text("'received'")),
        sa.Column("name", sa.String(length=200), nullable=True),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("phone", sa.String(length=50), nullable=True),
        sa.Column("subject", sa.String(length=200), nullable=True),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("inquiry_category", sa.String(length=100), nullable=True),
        sa.Column("institution_name", sa.String(length=200), nullable=True),
        sa.Column("institution_type", sa.String(length=80), nullable=True),
        sa.Column("source_path", sa.String(length=255), nullable=True),
        sa.Column("extra_fields", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_inquiries_inquiry_type", "inquiries", ["inquiry_type"])
    op.create_index("ix_inquiries_status", "inquiries", ["status"])
    op.create_index("ix_inquiries_email", "inquiries", ["email"])


def downgrade() -> None:
    conn = op.get_bind()
    inspector = Inspector.from_engine(conn)
    tables = inspector.get_table_names()
    if "inquiries" not in tables:
        return

    for index_name in ("ix_inquiries_email", "ix_inquiries_status", "ix_inquiries_inquiry_type"):
        try:
            op.drop_index(index_name, table_name="inquiries")
        except Exception:
            pass
    op.drop_table("inquiries")
