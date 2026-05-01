"""add render job template option columns

Revision ID: 20260501_0023
Revises: 20260430_0022
Create Date: 2026-05-01
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision: str = "20260501_0023"
down_revision: Union[str, None] = "20260430_0022"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _column_names(table_name: str) -> set[str]:
    inspector = inspect(op.get_bind())
    if table_name not in inspector.get_table_names():
        return set()
    return {column["name"] for column in inspector.get_columns(table_name)}


def upgrade() -> None:
    columns = _column_names("render_jobs")
    if not columns:
        return

    if "template_id" not in columns:
        op.add_column("render_jobs", sa.Column("template_id", sa.String(length=80), nullable=True))

    if "include_provenance_appendix" not in columns:
        op.add_column(
            "render_jobs",
            sa.Column(
                "include_provenance_appendix",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            ),
        )

    if "hide_internal_provenance_on_final_export" not in columns:
        op.add_column(
            "render_jobs",
            sa.Column(
                "hide_internal_provenance_on_final_export",
                sa.Boolean(),
                nullable=False,
                server_default=sa.true(),
            ),
        )


def downgrade() -> None:
    columns = _column_names("render_jobs")
    if "hide_internal_provenance_on_final_export" in columns:
        op.drop_column("render_jobs", "hide_internal_provenance_on_final_export")
    if "include_provenance_appendix" in columns:
        op.drop_column("render_jobs", "include_provenance_appendix")
    if "template_id" in columns:
        op.drop_column("render_jobs", "template_id")
