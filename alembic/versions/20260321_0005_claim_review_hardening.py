from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

from db.types import JSONBType

# revision identifiers, used by Alembic.
revision = "20260321_0005"
down_revision = "20260321_0004"
branch_labels = None
depends_on = None


def _has_column(inspector, table_name: str, column_name: str) -> bool:
    return column_name in {column["name"] for column in inspector.get_columns(table_name)}


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    tables = set(inspector.get_table_names())

    extraction_failure_enum = sa.Enum(
        "timeout",
        "gateway_error",
        "schema_validation_failed",
        "empty_response",
        "no_candidate_chunks",
        "all_batches_failed",
        name="extractionfailurecode",
        native_enum=False,
    )
    extraction_batch_status_enum = sa.Enum(
        "queued",
        "running",
        "succeeded",
        "failed",
        name="extractionbatchstatus",
        native_enum=False,
    )
    extraction_chunk_decision_status_enum = sa.Enum(
        "selected",
        "skipped",
        name="extractionchunkdecisionstatus",
        native_enum=False,
    )

    if "extraction_jobs" in tables:
        with op.batch_alter_table("extraction_jobs") as batch_op:
            if not _has_column(inspector, "extraction_jobs", "model_provider"):
                batch_op.add_column(sa.Column("model_provider", sa.String(length=80), nullable=False, server_default="ollama"))
            if not _has_column(inspector, "extraction_jobs", "prompt_template_version"):
                batch_op.add_column(sa.Column("prompt_template_version", sa.String(length=40), nullable=True))
            if not _has_column(inspector, "extraction_jobs", "selection_policy_key"):
                batch_op.add_column(sa.Column("selection_policy_key", sa.String(length=120), nullable=True))
            if not _has_column(inspector, "extraction_jobs", "batch_count"):
                batch_op.add_column(sa.Column("batch_count", sa.Integer(), nullable=False, server_default="0"))
            if not _has_column(inspector, "extraction_jobs", "successful_batch_count"):
                batch_op.add_column(sa.Column("successful_batch_count", sa.Integer(), nullable=False, server_default="0"))
            if not _has_column(inspector, "extraction_jobs", "failed_batch_count"):
                batch_op.add_column(sa.Column("failed_batch_count", sa.Integer(), nullable=False, server_default="0"))
            if not _has_column(inspector, "extraction_jobs", "retry_count"):
                batch_op.add_column(sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0"))
            if not _has_column(inspector, "extraction_jobs", "failure_reason_code"):
                batch_op.add_column(sa.Column("failure_reason_code", extraction_failure_enum, nullable=True))
            if not _has_column(inspector, "extraction_jobs", "last_latency_ms"):
                batch_op.add_column(sa.Column("last_latency_ms", sa.Integer(), nullable=True))
            if not _has_column(inspector, "extraction_jobs", "trace_id"):
                batch_op.add_column(sa.Column("trace_id", sa.String(length=64), nullable=True))
            if not _has_column(inspector, "extraction_jobs", "selection_summary_json"):
                batch_op.add_column(
                    sa.Column("selection_summary_json", JSONBType, nullable=False, server_default=sa.text("'{}'"))
                )

    tables = set(inspector.get_table_names())
    if "extraction_batch_runs" not in tables:
        op.create_table(
            "extraction_batch_runs",
            sa.Column("extraction_job_id", sa.Uuid(), sa.ForeignKey("extraction_jobs.id", ondelete="CASCADE"), nullable=False),
            sa.Column("batch_index", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("status", extraction_batch_status_enum, nullable=False, server_default="queued"),
            sa.Column("model_provider", sa.String(length=80), nullable=False, server_default="ollama"),
            sa.Column("model_name", sa.String(length=120), nullable=False),
            sa.Column("prompt_template_key", sa.String(length=120), nullable=False),
            sa.Column("prompt_template_version", sa.String(length=40), nullable=True),
            sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("chunk_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("latency_ms", sa.Integer(), nullable=True),
            sa.Column("failure_reason_code", extraction_failure_enum, nullable=True),
            sa.Column("trace_id", sa.String(length=64), nullable=True),
            sa.Column("observation_id", sa.String(length=64), nullable=True),
            sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("error_message", sa.Text(), nullable=True),
            sa.Column("request_payload", JSONBType, nullable=False, server_default=sa.text("'{}'")),
            sa.Column("response_payload", JSONBType, nullable=False, server_default=sa.text("'{}'")),
            sa.Column("metadata_json", JSONBType, nullable=False, server_default=sa.text("'{}'")),
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("extraction_job_id", "batch_index", name="uq_extraction_batch_runs_index"),
        )
        op.create_index("ix_extraction_batch_runs_status_provider", "extraction_batch_runs", ["status", "model_provider"])

    if "extraction_chunk_decisions" not in tables:
        op.create_table(
            "extraction_chunk_decisions",
            sa.Column("extraction_job_id", sa.Uuid(), sa.ForeignKey("extraction_jobs.id", ondelete="CASCADE"), nullable=False),
            sa.Column(
                "document_chunk_id",
                sa.Uuid(),
                sa.ForeignKey("document_chunks_v2.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("status", extraction_chunk_decision_status_enum, nullable=False),
            sa.Column("selection_policy_key", sa.String(length=120), nullable=False),
            sa.Column("priority_score", sa.Float(), nullable=False, server_default="0"),
            sa.Column("reason_codes", JSONBType, nullable=False, server_default=sa.text("'[]'")),
            sa.Column("metadata_json", JSONBType, nullable=False, server_default=sa.text("'{}'")),
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("extraction_job_id", "document_chunk_id", name="uq_extraction_chunk_decisions_scope"),
        )
        op.create_index(
            "ix_extraction_chunk_decisions_job_status",
            "extraction_chunk_decisions",
            ["extraction_job_id", "status"],
        )

    if "claims" in tables:
        with op.batch_alter_table("claims") as batch_op:
            if not _has_column(inspector, "claims", "evidence_quality_score"):
                batch_op.add_column(sa.Column("evidence_quality_score", sa.Float(), nullable=False, server_default="0"))
            if not _has_column(inspector, "claims", "is_direct_rule"):
                batch_op.add_column(sa.Column("is_direct_rule", sa.Boolean(), nullable=False, server_default=sa.false()))
            if not _has_column(inspector, "claims", "unsafe_flagged"):
                batch_op.add_column(sa.Column("unsafe_flagged", sa.Boolean(), nullable=False, server_default=sa.false()))
            if not _has_column(inspector, "claims", "overclaim_flagged"):
                batch_op.add_column(sa.Column("overclaim_flagged", sa.Boolean(), nullable=False, server_default=sa.false()))
            if not _has_column(inspector, "claims", "reviewer_note"):
                batch_op.add_column(sa.Column("reviewer_note", sa.Text(), nullable=True))
            if not _has_column(inspector, "claims", "reviewer_id"):
                batch_op.add_column(sa.Column("reviewer_id", sa.String(length=120), nullable=True))
            if not _has_column(inspector, "claims", "reviewed_at"):
                batch_op.add_column(sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True))
            if not _has_column(inspector, "claims", "university_exception_note"):
                batch_op.add_column(sa.Column("university_exception_note", sa.Text(), nullable=True))
            if not _has_column(inspector, "claims", "prompt_template_version"):
                batch_op.add_column(sa.Column("prompt_template_version", sa.String(length=40), nullable=True))

    if "eval_dataset_examples" not in tables:
        lifecycle_status_enum = sa.Enum(
            "active",
            "paused",
            "low_trust",
            "archived",
            "failed",
            name="lifecyclestatus",
            native_enum=False,
        )
        eval_example_kind_enum = sa.Enum(
            "gold_claim",
            "bad_claim",
            "evidence_span",
            "unsafe_prompt",
            "weak_evidence",
            name="evalexamplekind",
            native_enum=False,
        )
        op.create_table(
            "eval_dataset_examples",
            sa.Column("dataset_key", sa.String(length=120), nullable=False),
            sa.Column("example_key", sa.String(length=120), nullable=False),
            sa.Column("example_kind", eval_example_kind_enum, nullable=False),
            sa.Column("status", lifecycle_status_enum, nullable=False, server_default="active"),
            sa.Column("document_id", sa.Uuid(), sa.ForeignKey("documents.id", ondelete="SET NULL"), nullable=True),
            sa.Column(
                "document_chunk_id",
                sa.Uuid(),
                sa.ForeignKey("document_chunks_v2.id", ondelete="SET NULL"),
                nullable=True,
            ),
            sa.Column("prompt_text", sa.Text(), nullable=True),
            sa.Column("source_text", sa.Text(), nullable=True),
            sa.Column("expected_claims_json", JSONBType, nullable=False, server_default=sa.text("'{}'")),
            sa.Column("expected_flags_json", JSONBType, nullable=False, server_default=sa.text("'{}'")),
            sa.Column("notes", sa.Text(), nullable=True),
            sa.Column("metadata_json", JSONBType, nullable=False, server_default=sa.text("'{}'")),
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("dataset_key", "example_key", name="uq_eval_dataset_examples_key"),
        )
        op.create_index("ix_eval_dataset_examples_kind_status", "eval_dataset_examples", ["example_kind", "status"])

    if "eval_evidence_spans" not in tables:
        op.create_table(
            "eval_evidence_spans",
            sa.Column(
                "eval_example_id",
                sa.Uuid(),
                sa.ForeignKey("eval_dataset_examples.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column(
                "document_chunk_id",
                sa.Uuid(),
                sa.ForeignKey("document_chunks_v2.id", ondelete="SET NULL"),
                nullable=True,
            ),
            sa.Column("span_rank", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("page_number", sa.Integer(), nullable=True),
            sa.Column("char_start", sa.Integer(), nullable=True),
            sa.Column("char_end", sa.Integer(), nullable=True),
            sa.Column("quoted_text", sa.Text(), nullable=False),
            sa.Column("label", sa.String(length=120), nullable=True),
            sa.Column("metadata_json", JSONBType, nullable=False, server_default=sa.text("'{}'")),
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_eval_evidence_spans_example_rank", "eval_evidence_spans", ["eval_example_id", "span_rank"])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    tables = set(inspector.get_table_names())

    if "eval_evidence_spans" in tables:
        indexes = {index["name"] for index in inspector.get_indexes("eval_evidence_spans")}
        if "ix_eval_evidence_spans_example_rank" in indexes:
            op.drop_index("ix_eval_evidence_spans_example_rank", table_name="eval_evidence_spans")
        op.drop_table("eval_evidence_spans")

    if "eval_dataset_examples" in tables:
        indexes = {index["name"] for index in inspector.get_indexes("eval_dataset_examples")}
        if "ix_eval_dataset_examples_kind_status" in indexes:
            op.drop_index("ix_eval_dataset_examples_kind_status", table_name="eval_dataset_examples")
        op.drop_table("eval_dataset_examples")

    if "claims" in tables:
        with op.batch_alter_table("claims") as batch_op:
            for column_name in (
                "prompt_template_version",
                "university_exception_note",
                "reviewed_at",
                "reviewer_id",
                "reviewer_note",
                "overclaim_flagged",
                "unsafe_flagged",
                "is_direct_rule",
                "evidence_quality_score",
            ):
                if _has_column(inspector, "claims", column_name):
                    batch_op.drop_column(column_name)

    if "extraction_chunk_decisions" in tables:
        indexes = {index["name"] for index in inspector.get_indexes("extraction_chunk_decisions")}
        if "ix_extraction_chunk_decisions_job_status" in indexes:
            op.drop_index("ix_extraction_chunk_decisions_job_status", table_name="extraction_chunk_decisions")
        op.drop_table("extraction_chunk_decisions")

    if "extraction_batch_runs" in tables:
        indexes = {index["name"] for index in inspector.get_indexes("extraction_batch_runs")}
        if "ix_extraction_batch_runs_status_provider" in indexes:
            op.drop_index("ix_extraction_batch_runs_status_provider", table_name="extraction_batch_runs")
        op.drop_table("extraction_batch_runs")

    if "extraction_jobs" in tables:
        with op.batch_alter_table("extraction_jobs") as batch_op:
            for column_name in (
                "selection_summary_json",
                "trace_id",
                "last_latency_ms",
                "failure_reason_code",
                "retry_count",
                "failed_batch_count",
                "successful_batch_count",
                "batch_count",
                "selection_policy_key",
                "prompt_template_version",
                "model_provider",
            ):
                if _has_column(inspector, "extraction_jobs", column_name):
                    batch_op.drop_column(column_name)
