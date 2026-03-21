from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

from db.base import Base
from db.models.security import Account, AuthSession, DeletionEvent, DeletionRequest, PrivacyScan, Role, Tenant

# revision identifiers, used by Alembic.
revision = "20260321_0006"
down_revision = "20260321_0005"
branch_labels = None
depends_on = None


SECURITY_TABLES = [
    Tenant.__table__,
    Role.__table__,
    Account.__table__,
    AuthSession.__table__,
    DeletionRequest.__table__,
    DeletionEvent.__table__,
    PrivacyScan.__table__,
]


def _has_column(inspector, table_name: str, column_name: str) -> bool:
    return column_name in {column["name"] for column in inspector.get_columns(table_name)}


def _has_index(inspector, table_name: str, index_name: str) -> bool:
    return index_name in {index["name"] for index in inspector.get_indexes(table_name)}


def _has_unique(inspector, table_name: str, constraint_name: str) -> bool:
    return constraint_name in {constraint["name"] for constraint in inspector.get_unique_constraints(table_name)}


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    Base.metadata.create_all(bind=bind, tables=SECURITY_TABLES, checkfirst=True)
    inspector = inspect(bind)

    privacy_masking_mode_enum = sa.Enum(
        "off",
        "detect_only",
        "mask_for_index",
        "mask_all",
        name="privacymaskingmode",
        native_enum=False,
    )

    if "file_objects" in inspector.get_table_names():
        with op.batch_alter_table("file_objects") as batch_op:
            if not _has_column(inspector, "file_objects", "tenant_id"):
                batch_op.add_column(sa.Column("tenant_id", sa.Uuid(), nullable=True))
                batch_op.create_foreign_key("fk_file_objects_tenant_id", "tenants", ["tenant_id"], ["id"], ondelete="CASCADE")
            if not _has_column(inspector, "file_objects", "retention_expires_at"):
                batch_op.add_column(sa.Column("retention_expires_at", sa.DateTime(timezone=True), nullable=True))
            if not _has_column(inspector, "file_objects", "purge_after_at"):
                batch_op.add_column(sa.Column("purge_after_at", sa.DateTime(timezone=True), nullable=True))
            if _has_unique(inspector, "file_objects", "uq_file_objects_sha256"):
                batch_op.drop_constraint("uq_file_objects_sha256", type_="unique")
        inspector = inspect(bind)
        if not _has_index(inspector, "file_objects", "ix_file_objects_sha256"):
            op.create_index("ix_file_objects_sha256", "file_objects", ["sha256"])
        if not _has_index(inspector, "file_objects", "ix_file_objects_tenant_sha256"):
            op.create_index("ix_file_objects_tenant_sha256", "file_objects", ["tenant_id", "sha256"])

    if "student_files" in inspector.get_table_names():
        with op.batch_alter_table("student_files") as batch_op:
            if not _has_column(inspector, "student_files", "tenant_id"):
                batch_op.add_column(sa.Column("tenant_id", sa.Uuid(), nullable=True))
                batch_op.create_foreign_key("fk_student_files_tenant_id", "tenants", ["tenant_id"], ["id"], ondelete="CASCADE")
            if not _has_column(inspector, "student_files", "created_by_account_id"):
                batch_op.add_column(sa.Column("created_by_account_id", sa.Uuid(), nullable=True))
                batch_op.create_foreign_key(
                    "fk_student_files_created_by_account_id",
                    "accounts",
                    ["created_by_account_id"],
                    ["id"],
                    ondelete="SET NULL",
                )
            if not _has_column(inspector, "student_files", "privacy_masking_mode"):
                batch_op.add_column(sa.Column("privacy_masking_mode", privacy_masking_mode_enum, nullable=True))
            if not _has_column(inspector, "student_files", "pii_detected"):
                batch_op.add_column(sa.Column("pii_detected", sa.Boolean(), nullable=False, server_default=sa.false()))
            if not _has_column(inspector, "student_files", "retention_expires_at"):
                batch_op.add_column(sa.Column("retention_expires_at", sa.DateTime(timezone=True), nullable=True))
            if not _has_column(inspector, "student_files", "deletion_requested_at"):
                batch_op.add_column(sa.Column("deletion_requested_at", sa.DateTime(timezone=True), nullable=True))
            if not _has_column(inspector, "student_files", "purge_after_at"):
                batch_op.add_column(sa.Column("purge_after_at", sa.DateTime(timezone=True), nullable=True))
            if _has_unique(inspector, "student_files", "uq_student_files_file_object_id"):
                batch_op.drop_constraint("uq_student_files_file_object_id", type_="unique")
        inspector = inspect(bind)
        if not _has_index(inspector, "student_files", "ix_student_files_file_object_id"):
            op.create_index("ix_student_files_file_object_id", "student_files", ["file_object_id"])
        if not _has_index(inspector, "student_files", "ix_student_files_tenant_status"):
            op.create_index("ix_student_files_tenant_status", "student_files", ["tenant_id", "status"])

    if "student_artifacts" in inspector.get_table_names():
        with op.batch_alter_table("student_artifacts") as batch_op:
            if not _has_column(inspector, "student_artifacts", "tenant_id"):
                batch_op.add_column(sa.Column("tenant_id", sa.Uuid(), nullable=True))
                batch_op.create_foreign_key("fk_student_artifacts_tenant_id", "tenants", ["tenant_id"], ["id"], ondelete="CASCADE")
            if not _has_column(inspector, "student_artifacts", "masked_text"):
                batch_op.add_column(sa.Column("masked_text", sa.Text(), nullable=True))
            if not _has_column(inspector, "student_artifacts", "pii_detected"):
                batch_op.add_column(sa.Column("pii_detected", sa.Boolean(), nullable=False, server_default=sa.false()))
        inspector = inspect(bind)
        if not _has_index(inspector, "student_artifacts", "ix_student_artifacts_tenant_type"):
            op.create_index("ix_student_artifacts_tenant_type", "student_artifacts", ["tenant_id", "artifact_type"])

    if "student_analysis_runs" in inspector.get_table_names():
        with op.batch_alter_table("student_analysis_runs") as batch_op:
            if not _has_column(inspector, "student_analysis_runs", "tenant_id"):
                batch_op.add_column(sa.Column("tenant_id", sa.Uuid(), nullable=True))
                batch_op.create_foreign_key("fk_student_analysis_runs_tenant_id", "tenants", ["tenant_id"], ["id"], ondelete="CASCADE")
            if not _has_column(inspector, "student_analysis_runs", "created_by_account_id"):
                batch_op.add_column(sa.Column("created_by_account_id", sa.Uuid(), nullable=True))
                batch_op.create_foreign_key(
                    "fk_student_analysis_runs_created_by_account_id",
                    "accounts",
                    ["created_by_account_id"],
                    ["id"],
                    ondelete="SET NULL",
                )
            if not _has_column(inspector, "student_analysis_runs", "retention_expires_at"):
                batch_op.add_column(sa.Column("retention_expires_at", sa.DateTime(timezone=True), nullable=True))
            if not _has_column(inspector, "student_analysis_runs", "deletion_requested_at"):
                batch_op.add_column(sa.Column("deletion_requested_at", sa.DateTime(timezone=True), nullable=True))
        inspector = inspect(bind)
        if not _has_index(inspector, "student_analysis_runs", "ix_student_analysis_runs_tenant_status"):
            op.create_index("ix_student_analysis_runs_tenant_status", "student_analysis_runs", ["tenant_id", "status"])

    for table_name in ("citations", "policy_flags", "review_tasks", "response_traces"):
        if table_name not in inspector.get_table_names():
            continue
        with op.batch_alter_table(table_name) as batch_op:
            if not _has_column(inspector, table_name, "tenant_id"):
                batch_op.add_column(sa.Column("tenant_id", sa.Uuid(), nullable=True))
                batch_op.create_foreign_key(f"fk_{table_name}_tenant_id", "tenants", ["tenant_id"], ["id"], ondelete="CASCADE")
            if table_name == "response_traces" and not _has_column(inspector, table_name, "retention_expires_at"):
                batch_op.add_column(sa.Column("retention_expires_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)

    for table_name in ("response_traces", "review_tasks", "policy_flags", "citations"):
        if table_name not in inspector.get_table_names():
            continue
        with op.batch_alter_table(table_name) as batch_op:
            if table_name == "response_traces" and _has_column(inspector, table_name, "retention_expires_at"):
                batch_op.drop_column("retention_expires_at")
            if _has_column(inspector, table_name, "tenant_id"):
                batch_op.drop_column("tenant_id")

    if "student_analysis_runs" in inspector.get_table_names():
        indexes = {index["name"] for index in inspector.get_indexes("student_analysis_runs")}
        if "ix_student_analysis_runs_tenant_status" in indexes:
            op.drop_index("ix_student_analysis_runs_tenant_status", table_name="student_analysis_runs")
        with op.batch_alter_table("student_analysis_runs") as batch_op:
            for column_name in ("deletion_requested_at", "retention_expires_at", "created_by_account_id", "tenant_id"):
                if _has_column(inspector, "student_analysis_runs", column_name):
                    batch_op.drop_column(column_name)

    if "student_artifacts" in inspector.get_table_names():
        indexes = {index["name"] for index in inspector.get_indexes("student_artifacts")}
        if "ix_student_artifacts_tenant_type" in indexes:
            op.drop_index("ix_student_artifacts_tenant_type", table_name="student_artifacts")
        with op.batch_alter_table("student_artifacts") as batch_op:
            for column_name in ("pii_detected", "masked_text", "tenant_id"):
                if _has_column(inspector, "student_artifacts", column_name):
                    batch_op.drop_column(column_name)

    if "student_files" in inspector.get_table_names():
        indexes = {index["name"] for index in inspector.get_indexes("student_files")}
        if "ix_student_files_file_object_id" in indexes:
            op.drop_index("ix_student_files_file_object_id", table_name="student_files")
        if "ix_student_files_tenant_status" in indexes:
            op.drop_index("ix_student_files_tenant_status", table_name="student_files")
        with op.batch_alter_table("student_files") as batch_op:
            for column_name in (
                "purge_after_at",
                "deletion_requested_at",
                "retention_expires_at",
                "pii_detected",
                "privacy_masking_mode",
                "created_by_account_id",
                "tenant_id",
            ):
                if _has_column(inspector, "student_files", column_name):
                    batch_op.drop_column(column_name)

    if "file_objects" in inspector.get_table_names():
        indexes = {index["name"] for index in inspector.get_indexes("file_objects")}
        if "ix_file_objects_sha256" in indexes:
            op.drop_index("ix_file_objects_sha256", table_name="file_objects")
        if "ix_file_objects_tenant_sha256" in indexes:
            op.drop_index("ix_file_objects_tenant_sha256", table_name="file_objects")
        with op.batch_alter_table("file_objects") as batch_op:
            for column_name in ("purge_after_at", "retention_expires_at", "tenant_id"):
                if _has_column(inspector, "file_objects", column_name):
                    batch_op.drop_column(column_name)

    Base.metadata.drop_all(bind=bind, tables=list(reversed(SECURITY_TABLES)), checkfirst=True)
