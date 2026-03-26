"""add runtime safety tables and project ownership

Revision ID: 20260325_0009
Revises: 20260322_0008
Create Date: 2026-03-25 10:30:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.engine.reflection import Inspector

revision = "20260325_0009"
down_revision = "20260322_0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = Inspector.from_engine(conn)
    tables = inspector.get_table_names()

    project_columns = [c["name"] for c in inspector.get_columns("projects")] if "projects" in tables else []
    if "owner_user_id" not in project_columns:
        op.add_column("projects", sa.Column("owner_user_id", sa.String(length=36), nullable=True))
        op.create_index("ix_projects_owner_user_id", "projects", ["owner_user_id"], unique=False)

    if "policy_flags" not in tables:
        op.create_table(
            "policy_flags",
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("diagnosis_run_id", sa.String(length=36), nullable=False),
            sa.Column("project_id", sa.String(length=36), nullable=False),
            sa.Column("user_id", sa.String(length=36), nullable=True),
            sa.Column("code", sa.String(length=80), nullable=False),
            sa.Column("severity", sa.String(length=16), nullable=False),
            sa.Column("detail", sa.Text(), nullable=False),
            sa.Column("matched_text", sa.Text(), nullable=True),
            sa.Column("match_count", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("status", sa.String(length=24), nullable=False, server_default="open"),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["diagnosis_run_id"], ["diagnosis_runs.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_policy_flags_diagnosis_run_id", "policy_flags", ["diagnosis_run_id"], unique=False)
        op.create_index("ix_policy_flags_project_id", "policy_flags", ["project_id"], unique=False)
        op.create_index("ix_policy_flags_user_id", "policy_flags", ["user_id"], unique=False)

    if "review_tasks" not in tables:
        op.create_table(
            "review_tasks",
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("diagnosis_run_id", sa.String(length=36), nullable=False),
            sa.Column("project_id", sa.String(length=36), nullable=False),
            sa.Column("user_id", sa.String(length=36), nullable=True),
            sa.Column("task_type", sa.String(length=64), nullable=False),
            sa.Column("status", sa.String(length=24), nullable=False),
            sa.Column("assigned_role", sa.String(length=32), nullable=False),
            sa.Column("reason", sa.Text(), nullable=False),
            sa.Column("details", sa.JSON(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["diagnosis_run_id"], ["diagnosis_runs.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_review_tasks_diagnosis_run_id", "review_tasks", ["diagnosis_run_id"], unique=False)
        op.create_index("ix_review_tasks_project_id", "review_tasks", ["project_id"], unique=False)
        op.create_index("ix_review_tasks_user_id", "review_tasks", ["user_id"], unique=False)

    if "response_traces" not in tables:
        op.create_table(
            "response_traces",
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("diagnosis_run_id", sa.String(length=36), nullable=False),
            sa.Column("project_id", sa.String(length=36), nullable=False),
            sa.Column("user_id", sa.String(length=36), nullable=True),
            sa.Column("model_name", sa.String(length=120), nullable=False),
            sa.Column("request_excerpt", sa.Text(), nullable=False),
            sa.Column("response_excerpt", sa.Text(), nullable=False),
            sa.Column("trace_metadata", sa.JSON(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["diagnosis_run_id"], ["diagnosis_runs.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_response_traces_diagnosis_run_id", "response_traces", ["diagnosis_run_id"], unique=False)
        op.create_index("ix_response_traces_project_id", "response_traces", ["project_id"], unique=False)
        op.create_index("ix_response_traces_user_id", "response_traces", ["user_id"], unique=False)

    if "citations" not in tables:
        op.create_table(
            "citations",
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("response_trace_id", sa.String(length=36), nullable=False),
            sa.Column("diagnosis_run_id", sa.String(length=36), nullable=False),
            sa.Column("project_id", sa.String(length=36), nullable=False),
            sa.Column("document_id", sa.String(length=36), nullable=True),
            sa.Column("document_chunk_id", sa.String(length=36), nullable=True),
            sa.Column("source_label", sa.String(length=255), nullable=False),
            sa.Column("page_number", sa.Integer(), nullable=True),
            sa.Column("excerpt", sa.Text(), nullable=False),
            sa.Column("relevance_score", sa.Float(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["response_trace_id"], ["response_traces.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["diagnosis_run_id"], ["diagnosis_runs.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["document_id"], ["parsed_documents.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["document_chunk_id"], ["document_chunks.id"], ondelete="SET NULL"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_citations_response_trace_id", "citations", ["response_trace_id"], unique=False)
        op.create_index("ix_citations_diagnosis_run_id", "citations", ["diagnosis_run_id"], unique=False)
        op.create_index("ix_citations_project_id", "citations", ["project_id"], unique=False)


def downgrade() -> None:
    conn = op.get_bind()
    inspector = Inspector.from_engine(conn)
    tables = inspector.get_table_names()

    if "citations" in tables:
        op.drop_index("ix_citations_project_id", table_name="citations")
        op.drop_index("ix_citations_diagnosis_run_id", table_name="citations")
        op.drop_index("ix_citations_response_trace_id", table_name="citations")
        op.drop_table("citations")

    if "response_traces" in tables:
        op.drop_index("ix_response_traces_user_id", table_name="response_traces")
        op.drop_index("ix_response_traces_project_id", table_name="response_traces")
        op.drop_index("ix_response_traces_diagnosis_run_id", table_name="response_traces")
        op.drop_table("response_traces")

    if "review_tasks" in tables:
        op.drop_index("ix_review_tasks_user_id", table_name="review_tasks")
        op.drop_index("ix_review_tasks_project_id", table_name="review_tasks")
        op.drop_index("ix_review_tasks_diagnosis_run_id", table_name="review_tasks")
        op.drop_table("review_tasks")

    if "policy_flags" in tables:
        op.drop_index("ix_policy_flags_user_id", table_name="policy_flags")
        op.drop_index("ix_policy_flags_project_id", table_name="policy_flags")
        op.drop_index("ix_policy_flags_diagnosis_run_id", table_name="policy_flags")
        op.drop_table("policy_flags")

    project_columns = [c["name"] for c in inspector.get_columns("projects")] if "projects" in tables else []
    if "owner_user_id" in project_columns:
        op.drop_index("ix_projects_owner_user_id", table_name="projects")
        op.drop_column("projects", "owner_user_id")
