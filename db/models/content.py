from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db.base import Base
from db.models.mixins import SoftDeleteMixin, TimestampMixin, UUIDPrimaryKeyMixin
from db.types import JSONBType, vector_type
from domain.enums import (
    BlockType,
    ClaimStatus,
    ClaimType,
    ConflictStatus,
    ConflictType,
    DocumentStatus,
    DocumentType,
    ExtractionBatchStatus,
    ExtractionChunkDecisionStatus,
    ExtractionFailureCode,
    ExtractionJobStatus,
    FileObjectStatus,
    IngestionJobStatus,
    RetrievalIndexStatus,
    RetrievalRecordType,
    SourceTier,
    StorageProvider,
)


class FileObject(UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "file_objects"
    __table_args__ = (
        Index("ix_file_objects_storage_provider_status", "storage_provider", "status"),
        Index("ix_file_objects_sha256", "sha256"),
        Index("ix_file_objects_tenant_sha256", "tenant_id", "sha256"),
    )

    tenant_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), nullable=True)
    storage_provider: Mapped[StorageProvider] = mapped_column(
        Enum(StorageProvider, native_enum=False),
        nullable=False,
        default=StorageProvider.LOCAL,
    )
    bucket_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    object_key: Mapped[str] = mapped_column(String(500), nullable=False)
    local_path: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(255), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    md5: Mapped[str | None] = mapped_column(String(32), nullable=True)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    source_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    retention_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    purge_after_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[FileObjectStatus] = mapped_column(
        Enum(FileObjectStatus, native_enum=False),
        nullable=False,
        default=FileObjectStatus.STORED,
    )
    metadata_json: Mapped[dict[str, object]] = mapped_column(JSONBType, nullable=False, default=dict)

    document_versions: Mapped[list["DocumentVersion"]] = relationship(back_populates="file_object")
    ingestion_jobs: Mapped[list["IngestionJob"]] = relationship(back_populates="file_object")
    student_files: Mapped[list["StudentFile"]] = relationship(back_populates="file_object")
    discovered_urls: Mapped[list["DiscoveredUrl"]] = relationship(back_populates="file_object")


class Document(UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "documents"
    __table_args__ = (
        UniqueConstraint("source_id", "source_document_key", name="uq_documents_source_document_key"),
        Index("ix_documents_type_status", "document_type", "status"),
        Index("ix_documents_cycle_year", "admissions_year"),
    )

    source_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("sources.id", ondelete="SET NULL"), nullable=True)
    university_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("universities.id", ondelete="SET NULL"), nullable=True)
    admission_cycle_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("admission_cycles.id", ondelete="SET NULL"),
        nullable=True,
    )
    admission_track_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("admission_tracks.id", ondelete="SET NULL"),
        nullable=True,
    )
    current_version_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("document_versions.id", ondelete="SET NULL", use_alter=True),
        nullable=True,
    )
    source_document_key: Mapped[str | None] = mapped_column(String(255), nullable=True)
    canonical_title: Mapped[str] = mapped_column(String(500), nullable=False)
    document_type: Mapped[DocumentType] = mapped_column(Enum(DocumentType, native_enum=False), nullable=False)
    source_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    publication_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    effective_start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    effective_end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    admissions_year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    cycle_label: Mapped[str | None] = mapped_column(String(80), nullable=True)
    source_tier: Mapped[SourceTier] = mapped_column(Enum(SourceTier, native_enum=False), nullable=False)
    trust_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    freshness_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    quality_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    is_current_cycle: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    status: Mapped[DocumentStatus] = mapped_column(
        Enum(DocumentStatus, native_enum=False),
        nullable=False,
        default=DocumentStatus.REGISTERED,
    )
    metadata_json: Mapped[dict[str, object]] = mapped_column(JSONBType, nullable=False, default=dict)

    source: Mapped["Source | None"] = relationship(back_populates="documents")
    university: Mapped["University | None"] = relationship(back_populates="documents")
    admission_cycle: Mapped["AdmissionCycle | None"] = relationship(back_populates="documents")
    admission_track: Mapped["AdmissionTrack | None"] = relationship(back_populates="documents")
    current_version: Mapped["DocumentVersion | None"] = relationship(
        "DocumentVersion",
        foreign_keys=[current_version_id],
        post_update=True,
    )
    versions: Mapped[list["DocumentVersion"]] = relationship(
        "DocumentVersion",
        foreign_keys="DocumentVersion.document_id",
        back_populates="document",
        cascade="all, delete-orphan",
    )
    parsed_blocks: Mapped[list["ParsedBlock"]] = relationship(back_populates="document", cascade="all, delete-orphan")
    chunks: Mapped[list["DocumentChunk"]] = relationship(back_populates="document", cascade="all, delete-orphan")
    claims: Mapped[list["Claim"]] = relationship(back_populates="document", cascade="all, delete-orphan")
    extraction_jobs: Mapped[list["ExtractionJob"]] = relationship(back_populates="document")
    retrieval_records: Mapped[list["RetrievalIndexRecord"]] = relationship(back_populates="document")
    discovered_urls: Mapped[list["DiscoveredUrl"]] = relationship(back_populates="document")


class DocumentVersion(UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "document_versions"
    __table_args__ = (
        UniqueConstraint("document_id", "version_number", name="uq_document_versions_number"),
        UniqueConstraint("document_id", "content_hash", name="uq_document_versions_hash"),
    )

    document_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    file_object_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("file_objects.id", ondelete="RESTRICT"), nullable=False)
    previous_version_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("document_versions.id", ondelete="SET NULL"),
        nullable=True,
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    parser_name: Mapped[str] = mapped_column(String(120), nullable=False)
    parser_version: Mapped[str] = mapped_column(String(40), nullable=False, default="0.1.0")
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    page_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    raw_text_length: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    cleaned_text_length: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    parse_status: Mapped[DocumentStatus] = mapped_column(
        Enum(DocumentStatus, native_enum=False),
        nullable=False,
        default=DocumentStatus.PARSED,
    )
    normalized_payload: Mapped[dict[str, object]] = mapped_column(JSONBType, nullable=False, default=dict)

    document: Mapped["Document"] = relationship(
        back_populates="versions",
        foreign_keys=[document_id],
    )
    file_object: Mapped["FileObject"] = relationship(back_populates="document_versions")
    parsed_blocks: Mapped[list["ParsedBlock"]] = relationship(back_populates="document_version", cascade="all, delete-orphan")
    chunks: Mapped[list["DocumentChunk"]] = relationship(back_populates="document_version", cascade="all, delete-orphan")
    claims: Mapped[list["Claim"]] = relationship(back_populates="document_version", cascade="all, delete-orphan")


class ParsedBlock(UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "parsed_blocks"
    __table_args__ = (
        UniqueConstraint("document_version_id", "block_index", name="uq_parsed_blocks_index"),
        Index("ix_parsed_blocks_document_page", "document_id", "page_start"),
    )

    document_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    document_version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("document_versions.id", ondelete="CASCADE"),
        nullable=False,
    )
    block_index: Mapped[int] = mapped_column(Integer, nullable=False)
    block_type: Mapped[BlockType] = mapped_column(Enum(BlockType, native_enum=False), nullable=False)
    heading_path: Mapped[list[str]] = mapped_column(JSONBType, nullable=False, default=list)
    page_start: Mapped[int | None] = mapped_column(Integer, nullable=True)
    page_end: Mapped[int | None] = mapped_column(Integer, nullable=True)
    char_start: Mapped[int | None] = mapped_column(Integer, nullable=True)
    char_end: Mapped[int | None] = mapped_column(Integer, nullable=True)
    text_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    raw_text: Mapped[str] = mapped_column(Text, nullable=False)
    cleaned_text: Mapped[str] = mapped_column(Text, nullable=False)
    token_estimate: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    metadata_json: Mapped[dict[str, object]] = mapped_column(JSONBType, nullable=False, default=dict)

    document: Mapped["Document"] = relationship(back_populates="parsed_blocks")
    document_version: Mapped["DocumentVersion"] = relationship(back_populates="parsed_blocks")
    claim_evidence: Mapped[list["ClaimEvidence"]] = relationship(back_populates="parsed_block")
    chunks: Mapped[list["DocumentChunk"]] = relationship(back_populates="primary_block")


class DocumentChunk(UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "document_chunks_v2"
    __table_args__ = (
        UniqueConstraint("document_version_id", "chunk_index", name="uq_document_chunks_v2_index"),
        UniqueConstraint("document_version_id", "chunk_hash", name="uq_document_chunks_v2_hash"),
        Index("ix_document_chunks_v2_document_page", "document_id", "page_start"),
    )

    document_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    document_version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("document_versions.id", ondelete="CASCADE"),
        nullable=False,
    )
    primary_block_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("parsed_blocks.id", ondelete="SET NULL"),
        nullable=True,
    )
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    chunk_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    heading_path: Mapped[list[str]] = mapped_column(JSONBType, nullable=False, default=list)
    page_start: Mapped[int | None] = mapped_column(Integer, nullable=True)
    page_end: Mapped[int | None] = mapped_column(Integer, nullable=True)
    char_start: Mapped[int | None] = mapped_column(Integer, nullable=True)
    char_end: Mapped[int | None] = mapped_column(Integer, nullable=True)
    token_estimate: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    content_text: Mapped[str] = mapped_column(Text, nullable=False)
    metadata_json: Mapped[dict[str, object]] = mapped_column(JSONBType, nullable=False, default=dict)

    document: Mapped["Document"] = relationship(back_populates="chunks")
    document_version: Mapped["DocumentVersion"] = relationship(back_populates="chunks")
    primary_block: Mapped["ParsedBlock | None"] = relationship(back_populates="chunks")
    evidence_items: Mapped[list["ClaimEvidence"]] = relationship(back_populates="document_chunk")


class IngestionJob(UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "ingestion_jobs"
    __table_args__ = (
        UniqueConstraint("idempotency_key", name="uq_ingestion_jobs_idempotency_key"),
        Index("ix_ingestion_jobs_status_stage", "status", "pipeline_stage"),
    )

    source_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("sources.id", ondelete="SET NULL"), nullable=True)
    source_crawl_job_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("source_crawl_jobs.id", ondelete="SET NULL"),
        nullable=True,
    )
    file_object_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("file_objects.id", ondelete="SET NULL"), nullable=True)
    document_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("documents.id", ondelete="SET NULL"), nullable=True)
    idempotency_key: Mapped[str] = mapped_column(String(255), nullable=False)
    input_locator: Mapped[str] = mapped_column(String(1000), nullable=False)
    pipeline_stage: Mapped[str] = mapped_column(String(80), nullable=False, default="registered")
    status: Mapped[IngestionJobStatus] = mapped_column(
        Enum(IngestionJobStatus, native_enum=False),
        nullable=False,
        default=IngestionJobStatus.QUEUED,
    )
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    trace_json: Mapped[dict[str, object]] = mapped_column(JSONBType, nullable=False, default=dict)

    file_object: Mapped["FileObject | None"] = relationship(back_populates="ingestion_jobs")
    source_crawl_job: Mapped["SourceCrawlJob | None"] = relationship(back_populates="ingestion_jobs")


class ExtractionJob(UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "extraction_jobs"
    __table_args__ = (Index("ix_extraction_jobs_document_status", "document_id", "status"),)

    document_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    document_version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("document_versions.id", ondelete="CASCADE"),
        nullable=False,
    )
    status: Mapped[ExtractionJobStatus] = mapped_column(
        Enum(ExtractionJobStatus, native_enum=False),
        nullable=False,
        default=ExtractionJobStatus.QUEUED,
    )
    extractor_name: Mapped[str] = mapped_column(String(120), nullable=False, default="ollama_claim_extractor")
    model_provider: Mapped[str] = mapped_column(String(80), nullable=False, default="ollama")
    model_name: Mapped[str] = mapped_column(String(120), nullable=False, default="llama3.1:8b")
    prompt_template_key: Mapped[str] = mapped_column(String(120), nullable=False, default="claim_extraction_v1")
    prompt_template_version: Mapped[str | None] = mapped_column(String(40), nullable=True)
    selection_policy_key: Mapped[str | None] = mapped_column(String(120), nullable=True)
    chunk_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    batch_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    successful_batch_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    failed_batch_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    claims_extracted_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    failure_reason_code: Mapped[ExtractionFailureCode | None] = mapped_column(
        Enum(ExtractionFailureCode, native_enum=False),
        nullable=True,
    )
    last_latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    trace_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    selection_summary_json: Mapped[dict[str, object]] = mapped_column(JSONBType, nullable=False, default=dict)
    job_config: Mapped[dict[str, object]] = mapped_column(JSONBType, nullable=False, default=dict)

    document: Mapped["Document"] = relationship(back_populates="extraction_jobs")
    batch_runs: Mapped[list["ExtractionBatchRun"]] = relationship(back_populates="extraction_job", cascade="all, delete-orphan")
    chunk_decisions: Mapped[list["ExtractionChunkDecision"]] = relationship(
        back_populates="extraction_job",
        cascade="all, delete-orphan",
    )


class ExtractionBatchRun(UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "extraction_batch_runs"
    __table_args__ = (
        UniqueConstraint("extraction_job_id", "batch_index", name="uq_extraction_batch_runs_index"),
        Index("ix_extraction_batch_runs_status_provider", "status", "model_provider"),
    )

    extraction_job_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("extraction_jobs.id", ondelete="CASCADE"),
        nullable=False,
    )
    batch_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[ExtractionBatchStatus] = mapped_column(
        Enum(ExtractionBatchStatus, native_enum=False),
        nullable=False,
        default=ExtractionBatchStatus.QUEUED,
    )
    model_provider: Mapped[str] = mapped_column(String(80), nullable=False, default="ollama")
    model_name: Mapped[str] = mapped_column(String(120), nullable=False)
    prompt_template_key: Mapped[str] = mapped_column(String(120), nullable=False)
    prompt_template_version: Mapped[str | None] = mapped_column(String(40), nullable=True)
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    chunk_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    failure_reason_code: Mapped[ExtractionFailureCode | None] = mapped_column(
        Enum(ExtractionFailureCode, native_enum=False),
        nullable=True,
    )
    trace_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    observation_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    request_payload: Mapped[dict[str, object]] = mapped_column(JSONBType, nullable=False, default=dict)
    response_payload: Mapped[dict[str, object]] = mapped_column(JSONBType, nullable=False, default=dict)
    metadata_json: Mapped[dict[str, object]] = mapped_column(JSONBType, nullable=False, default=dict)

    extraction_job: Mapped["ExtractionJob"] = relationship(back_populates="batch_runs")


class ExtractionChunkDecision(UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "extraction_chunk_decisions"
    __table_args__ = (
        UniqueConstraint("extraction_job_id", "document_chunk_id", name="uq_extraction_chunk_decisions_scope"),
        Index("ix_extraction_chunk_decisions_job_status", "extraction_job_id", "status"),
    )

    extraction_job_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("extraction_jobs.id", ondelete="CASCADE"),
        nullable=False,
    )
    document_chunk_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("document_chunks_v2.id", ondelete="CASCADE"),
        nullable=False,
    )
    status: Mapped[ExtractionChunkDecisionStatus] = mapped_column(
        Enum(ExtractionChunkDecisionStatus, native_enum=False),
        nullable=False,
    )
    selection_policy_key: Mapped[str] = mapped_column(String(120), nullable=False)
    priority_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    reason_codes: Mapped[list[str]] = mapped_column(JSONBType, nullable=False, default=list)
    metadata_json: Mapped[dict[str, object]] = mapped_column(JSONBType, nullable=False, default=dict)

    extraction_job: Mapped["ExtractionJob"] = relationship(back_populates="chunk_decisions")
    document_chunk: Mapped["DocumentChunk"] = relationship()


class Claim(UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "claims"
    __table_args__ = (
        UniqueConstraint("document_version_id", "claim_hash", name="uq_claims_document_version_hash"),
        Index("ix_claims_dimension_status", "evaluation_dimension_id", "status"),
        Index("ix_claims_claim_type_status", "claim_type", "status"),
    )

    document_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    document_version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("document_versions.id", ondelete="CASCADE"),
        nullable=False,
    )
    extraction_job_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("extraction_jobs.id", ondelete="SET NULL"),
        nullable=True,
    )
    university_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("universities.id", ondelete="SET NULL"), nullable=True)
    admission_track_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("admission_tracks.id", ondelete="SET NULL"),
        nullable=True,
    )
    evaluation_dimension_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("evaluation_dimensions.id", ondelete="SET NULL"),
        nullable=True,
    )
    claim_type: Mapped[ClaimType] = mapped_column(Enum(ClaimType, native_enum=False), nullable=False)
    claim_text: Mapped[str] = mapped_column(Text, nullable=False)
    normalized_claim_text: Mapped[str] = mapped_column(Text, nullable=False)
    claim_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    source_tier: Mapped[SourceTier] = mapped_column(Enum(SourceTier, native_enum=False), nullable=False)
    applicable_from_year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    applicable_to_year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    applicable_cycle_label: Mapped[str | None] = mapped_column(String(80), nullable=True)
    confidence_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    quality_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    overclaim_risk_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    evidence_quality_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    is_direct_quote_based: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_direct_rule: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    unsafe_flagged: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    overclaim_flagged: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    reviewer_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    reviewer_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    university_exception_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    model_provider: Mapped[str | None] = mapped_column(String(80), nullable=True)
    model_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    prompt_template_key: Mapped[str | None] = mapped_column(String(120), nullable=True)
    prompt_template_version: Mapped[str | None] = mapped_column(String(40), nullable=True)
    status: Mapped[ClaimStatus] = mapped_column(
        Enum(ClaimStatus, native_enum=False),
        nullable=False,
        default=ClaimStatus.PENDING_REVIEW,
    )
    metadata_json: Mapped[dict[str, object]] = mapped_column(JSONBType, nullable=False, default=dict)

    document: Mapped["Document"] = relationship(back_populates="claims")
    document_version: Mapped["DocumentVersion"] = relationship(back_populates="claims")
    evaluation_dimension: Mapped["EvaluationDimension | None"] = relationship(back_populates="claims")
    evidence_items: Mapped[list["ClaimEvidence"]] = relationship(back_populates="claim", cascade="all, delete-orphan")
    citations: Mapped[list["Citation"]] = relationship(back_populates="claim")


class ClaimEvidence(UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "claim_evidence"
    __table_args__ = (
        UniqueConstraint("claim_id", "parsed_block_id", "char_start", "char_end", name="uq_claim_evidence_span"),
        Index("ix_claim_evidence_claim_rank", "claim_id", "evidence_rank"),
    )

    claim_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("claims.id", ondelete="CASCADE"), nullable=False)
    parsed_block_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("parsed_blocks.id", ondelete="CASCADE"), nullable=False)
    document_chunk_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("document_chunks_v2.id", ondelete="SET NULL"),
        nullable=True,
    )
    document_version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("document_versions.id", ondelete="CASCADE"),
        nullable=False,
    )
    evidence_rank: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    page_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    char_start: Mapped[int | None] = mapped_column(Integer, nullable=True)
    char_end: Mapped[int | None] = mapped_column(Integer, nullable=True)
    evidence_text: Mapped[str] = mapped_column(Text, nullable=False)
    confidence_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

    claim: Mapped["Claim"] = relationship(back_populates="evidence_items")
    parsed_block: Mapped["ParsedBlock"] = relationship(back_populates="claim_evidence")
    document_chunk: Mapped["DocumentChunk | None"] = relationship(back_populates="evidence_items")


class ConflictRecord(UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "conflict_records"
    __table_args__ = (
        UniqueConstraint("primary_claim_id", "conflicting_claim_id", "conflict_type", name="uq_conflict_pair"),
        Index("ix_conflict_records_status_type", "status", "conflict_type"),
    )

    primary_claim_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("claims.id", ondelete="CASCADE"), nullable=False)
    conflicting_claim_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("claims.id", ondelete="CASCADE"), nullable=False)
    winning_claim_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("claims.id", ondelete="SET NULL"), nullable=True)
    conflict_type: Mapped[ConflictType] = mapped_column(Enum(ConflictType, native_enum=False), nullable=False)
    severity_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    resolution_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[ConflictStatus] = mapped_column(
        Enum(ConflictStatus, native_enum=False),
        nullable=False,
        default=ConflictStatus.OPEN,
    )
    metadata_json: Mapped[dict[str, object]] = mapped_column(JSONBType, nullable=False, default=dict)


class RetrievalIndexRecord(UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "retrieval_index_records"
    __table_args__ = (
        UniqueConstraint("record_type", "record_id", name="uq_retrieval_index_records_target"),
        Index("ix_retrieval_index_records_status_tier", "index_status", "source_tier"),
    )

    record_type: Mapped[RetrievalRecordType] = mapped_column(Enum(RetrievalRecordType, native_enum=False), nullable=False)
    record_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    document_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    document_version_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("document_versions.id", ondelete="SET NULL"),
        nullable=True,
    )
    source_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("sources.id", ondelete="SET NULL"), nullable=True)
    university_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("universities.id", ondelete="SET NULL"), nullable=True)
    admission_cycle_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("admission_cycles.id", ondelete="SET NULL"),
        nullable=True,
    )
    admission_track_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("admission_tracks.id", ondelete="SET NULL"),
        nullable=True,
    )
    source_tier: Mapped[SourceTier] = mapped_column(Enum(SourceTier, native_enum=False), nullable=False)
    searchable_text: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[object | None] = mapped_column(vector_type(1536), nullable=True)
    embedding_model: Mapped[str | None] = mapped_column(String(120), nullable=True)
    lexical_weight: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    vector_weight: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    freshness_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    trust_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    quality_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    index_status: Mapped[RetrievalIndexStatus] = mapped_column(
        Enum(RetrievalIndexStatus, native_enum=False),
        nullable=False,
        default=RetrievalIndexStatus.PENDING,
    )
    metadata_json: Mapped[dict[str, object]] = mapped_column(JSONBType, nullable=False, default=dict)

    document: Mapped["Document"] = relationship(back_populates="retrieval_records")
