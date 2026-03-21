from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

from db.types import JSONBType

# revision identifiers, used by Alembic.
revision = "20260321_0004"
down_revision = "20260321_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    tables = set(inspector.get_table_names())

    if "source_seeds" not in tables:
        op.create_table(
            "source_seeds",
            sa.Column("source_id", sa.Uuid(), sa.ForeignKey("sources.id", ondelete="CASCADE"), nullable=False),
            sa.Column("seed_type", sa.String(length=50), nullable=False),
            sa.Column("label", sa.String(length=255), nullable=False),
            sa.Column("seed_url", sa.String(length=1000), nullable=False),
            sa.Column("allowed_domains", JSONBType, nullable=False),
            sa.Column("allowed_path_prefixes", JSONBType, nullable=False),
            sa.Column("denied_path_prefixes", JSONBType, nullable=False),
            sa.Column("max_depth", sa.Integer(), nullable=False, server_default="2"),
            sa.Column("current_cycle_year_hint", sa.Integer(), nullable=True),
            sa.Column("allow_binary_assets", sa.Boolean(), nullable=False, server_default=sa.text("true")),
            sa.Column("respect_robots_txt", sa.Boolean(), nullable=False, server_default=sa.text("true")),
            sa.Column("status", sa.String(length=50), nullable=False, server_default="active"),
            sa.Column("last_crawled_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("last_succeeded_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("last_error_message", sa.Text(), nullable=True),
            sa.Column("metadata_json", JSONBType, nullable=False),
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("source_id", "seed_url", name="uq_source_seeds_source_seed_url"),
        )
        op.create_index("ix_source_seeds_source_status", "source_seeds", ["source_id", "status"])

    source_crawl_job_columns = {column["name"] for column in inspector.get_columns("source_crawl_jobs")}
    if "source_seed_id" not in source_crawl_job_columns:
        op.add_column("source_crawl_jobs", sa.Column("source_seed_id", sa.Uuid(), nullable=True))
        op.create_foreign_key(
            "fk_source_crawl_jobs_source_seed_id",
            "source_crawl_jobs",
            "source_seeds",
            ["source_seed_id"],
            ["id"],
            ondelete="SET NULL",
        )
    if "crawl_scope" not in source_crawl_job_columns:
        op.add_column(
            "source_crawl_jobs",
            sa.Column("crawl_scope", sa.String(length=80), nullable=False, server_default="seed"),
        )

    if "discovered_urls" not in tables:
        op.create_table(
            "discovered_urls",
            sa.Column("source_id", sa.Uuid(), sa.ForeignKey("sources.id", ondelete="CASCADE"), nullable=False),
            sa.Column("source_seed_id", sa.Uuid(), sa.ForeignKey("source_seeds.id", ondelete="CASCADE"), nullable=False),
            sa.Column("latest_crawl_job_id", sa.Uuid(), sa.ForeignKey("source_crawl_jobs.id", ondelete="SET NULL"), nullable=True),
            sa.Column("file_object_id", sa.Uuid(), sa.ForeignKey("file_objects.id", ondelete="SET NULL"), nullable=True),
            sa.Column("document_id", sa.Uuid(), sa.ForeignKey("documents.id", ondelete="SET NULL"), nullable=True),
            sa.Column("canonical_url", sa.String(length=1000), nullable=False),
            sa.Column("url_hash", sa.String(length=64), nullable=False),
            sa.Column("discovered_from_url", sa.String(length=1000), nullable=True),
            sa.Column("depth", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("content_type", sa.String(length=255), nullable=True),
            sa.Column("http_status", sa.Integer(), nullable=True),
            sa.Column("etag", sa.String(length=255), nullable=True),
            sa.Column("last_modified_header", sa.String(length=255), nullable=True),
            sa.Column("is_html", sa.Boolean(), nullable=False, server_default=sa.text("false")),
            sa.Column("is_downloadable_asset", sa.Boolean(), nullable=False, server_default=sa.text("false")),
            sa.Column("is_current_cycle_relevant", sa.Boolean(), nullable=False, server_default=sa.text("false")),
            sa.Column("relevance_score", sa.Float(), nullable=False, server_default="0"),
            sa.Column("first_seen_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("last_fetched_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("next_refresh_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("status", sa.String(length=50), nullable=False, server_default="discovered"),
            sa.Column("metadata_json", JSONBType, nullable=False),
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("source_id", "canonical_url", name="uq_discovered_urls_source_canonical_url"),
        )
        op.create_index("ix_discovered_urls_seed_status", "discovered_urls", ["source_seed_id", "status"])
        op.create_index("ix_discovered_urls_source_refresh", "discovered_urls", ["source_id", "next_refresh_at"])

    if "university_aliases" not in tables:
        op.create_table(
            "university_aliases",
            sa.Column("university_id", sa.Uuid(), sa.ForeignKey("universities.id", ondelete="CASCADE"), nullable=False),
            sa.Column("alias_text", sa.String(length=255), nullable=False),
            sa.Column("alias_kind", sa.String(length=60), nullable=False, server_default="name"),
            sa.Column("campus_name", sa.String(length=255), nullable=True),
            sa.Column("is_official", sa.Boolean(), nullable=False, server_default=sa.text("false")),
            sa.Column("status", sa.String(length=50), nullable=False, server_default="active"),
            sa.Column("metadata_json", JSONBType, nullable=False),
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("alias_text", name="uq_university_aliases_alias_text"),
        )
        op.create_index("ix_university_aliases_university_status", "university_aliases", ["university_id", "status"])

    if "university_unit_aliases" not in tables:
        op.create_table(
            "university_unit_aliases",
            sa.Column("university_id", sa.Uuid(), sa.ForeignKey("universities.id", ondelete="CASCADE"), nullable=False),
            sa.Column("source_text", sa.String(length=255), nullable=False),
            sa.Column("normalized_unit_name", sa.String(length=255), nullable=False),
            sa.Column("campus_name", sa.String(length=255), nullable=True),
            sa.Column("college_name", sa.String(length=255), nullable=True),
            sa.Column("department_name", sa.String(length=255), nullable=True),
            sa.Column("status", sa.String(length=50), nullable=False, server_default="active"),
            sa.Column("metadata_json", JSONBType, nullable=False),
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("university_id", "source_text", name="uq_university_unit_aliases_source_text"),
        )
        op.create_index("ix_university_unit_aliases_university_status", "university_unit_aliases", ["university_id", "status"])

    if "admission_cycle_aliases" not in tables:
        op.create_table(
            "admission_cycle_aliases",
            sa.Column("alias_text", sa.String(length=255), nullable=False),
            sa.Column("normalized_label", sa.String(length=80), nullable=False),
            sa.Column("cycle_type", sa.String(length=40), nullable=False),
            sa.Column("admissions_year_hint", sa.Integer(), nullable=True),
            sa.Column("is_current_cycle_hint", sa.Boolean(), nullable=False, server_default=sa.text("false")),
            sa.Column("metadata_json", JSONBType, nullable=False),
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("alias_text", name="uq_admission_cycle_aliases_alias_text"),
        )

    if "evaluation_dimension_aliases" not in tables:
        op.create_table(
            "evaluation_dimension_aliases",
            sa.Column("evaluation_dimension_id", sa.Uuid(), sa.ForeignKey("evaluation_dimensions.id", ondelete="CASCADE"), nullable=False),
            sa.Column("alias_text", sa.String(length=255), nullable=False),
            sa.Column("language_code", sa.String(length=8), nullable=False, server_default="ko"),
            sa.Column("metadata_json", JSONBType, nullable=False),
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("alias_text", name="uq_evaluation_dimension_aliases_alias_text"),
        )

    if "document_type_labels" not in tables:
        op.create_table(
            "document_type_labels",
            sa.Column("label_text", sa.String(length=255), nullable=False),
            sa.Column("document_type", sa.String(length=50), nullable=False),
            sa.Column("language_code", sa.String(length=8), nullable=False, server_default="ko"),
            sa.Column("match_mode", sa.String(length=20), nullable=False, server_default="contains"),
            sa.Column("metadata_json", JSONBType, nullable=False),
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("label_text", "language_code", name="uq_document_type_labels_label_language"),
        )

    if "source_tier_examples" not in tables:
        op.create_table(
            "source_tier_examples",
            sa.Column("source_tier", sa.String(length=50), nullable=False),
            sa.Column("example_text", sa.Text(), nullable=False),
            sa.Column("rationale", sa.Text(), nullable=False),
            sa.Column("is_positive_example", sa.Boolean(), nullable=False, server_default=sa.text("true")),
            sa.Column("metadata_json", JSONBType, nullable=False),
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("example_text", name="uq_source_tier_examples_example_text"),
        )
        op.create_index("ix_source_tier_examples_tier", "source_tier_examples", ["source_tier"])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    tables = set(inspector.get_table_names())

    if "source_tier_examples" in tables:
        op.drop_index("ix_source_tier_examples_tier", table_name="source_tier_examples")
        op.drop_table("source_tier_examples")
    if "document_type_labels" in tables:
        op.drop_table("document_type_labels")
    if "evaluation_dimension_aliases" in tables:
        op.drop_table("evaluation_dimension_aliases")
    if "admission_cycle_aliases" in tables:
        op.drop_table("admission_cycle_aliases")
    if "university_unit_aliases" in tables:
        op.drop_index("ix_university_unit_aliases_university_status", table_name="university_unit_aliases")
        op.drop_table("university_unit_aliases")
    if "university_aliases" in tables:
        op.drop_index("ix_university_aliases_university_status", table_name="university_aliases")
        op.drop_table("university_aliases")
    if "discovered_urls" in tables:
        op.drop_index("ix_discovered_urls_source_refresh", table_name="discovered_urls")
        op.drop_index("ix_discovered_urls_seed_status", table_name="discovered_urls")
        op.drop_table("discovered_urls")

    source_crawl_job_columns = {column["name"] for column in inspector.get_columns("source_crawl_jobs")}
    if "crawl_scope" in source_crawl_job_columns:
        op.drop_column("source_crawl_jobs", "crawl_scope")
    if "source_seed_id" in source_crawl_job_columns:
        foreign_keys = {fk["name"] for fk in inspector.get_foreign_keys("source_crawl_jobs")}
        if "fk_source_crawl_jobs_source_seed_id" in foreign_keys:
            op.drop_constraint("fk_source_crawl_jobs_source_seed_id", "source_crawl_jobs", type_="foreignkey")
        op.drop_column("source_crawl_jobs", "source_seed_id")

    if "source_seeds" in tables:
        op.drop_index("ix_source_seeds_source_status", table_name="source_seeds")
        op.drop_table("source_seeds")
