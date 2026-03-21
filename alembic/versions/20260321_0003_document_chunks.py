from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

from db.types import JSONBType

# revision identifiers, used by Alembic.
revision = "20260321_0003"
down_revision = "20260321_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    tables = set(inspector.get_table_names())

    if "document_chunks_v2" not in tables:
        op.create_table(
            "document_chunks_v2",
            sa.Column("document_id", sa.Uuid(), sa.ForeignKey("documents.id", ondelete="CASCADE"), nullable=False),
            sa.Column(
                "document_version_id",
                sa.Uuid(),
                sa.ForeignKey("document_versions.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("primary_block_id", sa.Uuid(), sa.ForeignKey("parsed_blocks.id", ondelete="SET NULL"), nullable=True),
            sa.Column("chunk_index", sa.Integer(), nullable=False),
            sa.Column("chunk_hash", sa.String(length=64), nullable=False),
            sa.Column("heading_path", JSONBType, nullable=False),
            sa.Column("page_start", sa.Integer(), nullable=True),
            sa.Column("page_end", sa.Integer(), nullable=True),
            sa.Column("char_start", sa.Integer(), nullable=True),
            sa.Column("char_end", sa.Integer(), nullable=True),
            sa.Column("token_estimate", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("content_text", sa.Text(), nullable=False),
            sa.Column("metadata_json", JSONBType, nullable=False),
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("document_version_id", "chunk_index", name="uq_document_chunks_v2_index"),
            sa.UniqueConstraint("document_version_id", "chunk_hash", name="uq_document_chunks_v2_hash"),
        )
        op.create_index("ix_document_chunks_v2_document_page", "document_chunks_v2", ["document_id", "page_start"])

    claim_evidence_columns = {column["name"] for column in inspector.get_columns("claim_evidence")}
    if "document_chunk_id" not in claim_evidence_columns:
        op.add_column(
            "claim_evidence",
            sa.Column("document_chunk_id", sa.Uuid(), nullable=True),
        )
        op.create_foreign_key(
            "fk_claim_evidence_document_chunk_id",
            "claim_evidence",
            "document_chunks_v2",
            ["document_chunk_id"],
            ["id"],
            ondelete="SET NULL",
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    claim_evidence_columns = {column["name"] for column in inspector.get_columns("claim_evidence")}
    if "document_chunk_id" in claim_evidence_columns:
        foreign_keys = {fk["name"] for fk in inspector.get_foreign_keys("claim_evidence")}
        if "fk_claim_evidence_document_chunk_id" in foreign_keys:
            op.drop_constraint("fk_claim_evidence_document_chunk_id", "claim_evidence", type_="foreignkey")
        op.drop_column("claim_evidence", "document_chunk_id")

    if "document_chunks_v2" in set(inspector.get_table_names()):
        indexes = {index["name"] for index in inspector.get_indexes("document_chunks_v2")}
        if "ix_document_chunks_v2_document_page" in indexes:
            op.drop_index("ix_document_chunks_v2_document_page", table_name="document_chunks_v2")
        op.drop_table("document_chunks_v2")
