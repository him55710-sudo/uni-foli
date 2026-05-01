"""add quality control metadata to draft artifacts

Revision ID: 20260430_0022
Revises: 20260430_0021
Create Date: 2026-04-30
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect
from sqlalchemy.dialects.postgresql import JSONB


revision: str = "20260430_0022"
down_revision: Union[str, None] = "20260430_0021"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _column_names(table_name: str) -> set[str]:
    inspector = inspect(op.get_bind())
    if table_name not in inspector.get_table_names():
        return set()
    return {column["name"] for column in inspector.get_columns(table_name)}


def upgrade() -> None:
    columns = _column_names("draft_artifacts")
    if not columns or "quality_control_meta" in columns:
        return

    op.add_column(
        "draft_artifacts",
        sa.Column(
            "quality_control_meta",
            JSONB(astext_type=sa.Text()).with_variant(sa.JSON(), "sqlite"),
            nullable=True,
        ),
    )


def downgrade() -> None:
    columns = _column_names("draft_artifacts")
    if "quality_control_meta" in columns:
        op.drop_column("draft_artifacts", "quality_control_meta")
