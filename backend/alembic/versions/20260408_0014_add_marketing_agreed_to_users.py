"""add marketing_agreed to users

Revision ID: 20260408_0014
Revises: 20260401_0013
Create Date: 2026-04-08
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision: str = "20260408_0014"
down_revision: Union[str, None] = "20260401_0013"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    if "users" not in inspector.get_table_names():
        return

    columns = {column["name"] for column in inspector.get_columns("users")}
    if "marketing_agreed" not in columns:
        op.add_column(
            "users",
            sa.Column("marketing_agreed", sa.Boolean(), nullable=False, server_default=sa.false()),
        )
        op.execute(sa.text("UPDATE users SET marketing_agreed = false WHERE marketing_agreed IS NULL"))


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    if "users" not in inspector.get_table_names():
        return

    columns = {column["name"] for column in inspector.get_columns("users")}
    if "marketing_agreed" in columns:
        op.drop_column("users", "marketing_agreed")
