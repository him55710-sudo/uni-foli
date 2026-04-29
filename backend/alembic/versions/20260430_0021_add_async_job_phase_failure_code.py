"""add async job phase and failure code columns

Revision ID: 20260430_0021
Revises: 20260426_0020
Create Date: 2026-04-30
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision: str = "20260430_0021"
down_revision: Union[str, None] = "20260426_0020"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _table_names(inspector) -> set[str]:
    return set(inspector.get_table_names())


def _column_names(inspector, table_name: str) -> set[str]:
    return {column["name"] for column in inspector.get_columns(table_name)}


def _index_names(inspector, table_name: str) -> set[str]:
    return {index["name"] for index in inspector.get_indexes(table_name)}


def _create_index_if_missing(inspector, table_name: str, index_name: str, columns: list[str]) -> None:
    if table_name not in _table_names(inspector):
        return
    if index_name in _index_names(inspector, table_name):
        return
    op.create_index(index_name, table_name, columns, unique=False)


def _drop_index_if_present(inspector, table_name: str, index_name: str) -> None:
    if table_name not in _table_names(inspector):
        return
    if index_name not in _index_names(inspector, table_name):
        return
    op.drop_index(index_name, table_name=table_name)


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    if "async_jobs" not in _table_names(inspector):
        return

    columns = _column_names(inspector, "async_jobs")
    if "phase" not in columns:
        op.add_column("async_jobs", sa.Column("phase", sa.String(length=32), nullable=True))
    if "failure_code" not in columns:
        op.add_column("async_jobs", sa.Column("failure_code", sa.String(length=64), nullable=True))

    inspector = inspect(bind)
    _create_index_if_missing(inspector, "async_jobs", "ix_async_jobs_phase", ["phase"])
    _create_index_if_missing(inspector, "async_jobs", "ix_async_jobs_failure_code", ["failure_code"])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    if "async_jobs" not in _table_names(inspector):
        return

    _drop_index_if_present(inspector, "async_jobs", "ix_async_jobs_failure_code")
    _drop_index_if_present(inspector, "async_jobs", "ix_async_jobs_phase")

    columns = _column_names(inspector, "async_jobs")
    if "failure_code" in columns:
        op.drop_column("async_jobs", "failure_code")
    if "phase" in columns:
        op.drop_column("async_jobs", "phase")
