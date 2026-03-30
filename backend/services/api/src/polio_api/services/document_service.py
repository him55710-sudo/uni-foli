from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import delete, select
from sqlalchemy.orm import Session, joinedload

from polio_api.core.config import get_settings
from polio_api.core.database import SessionLocal
from polio_api.core.security import sanitize_public_error
from polio_api.db.models.document_chunk import DocumentChunk
from polio_api.db.models.draft import Draft
from polio_api.db.models.parsed_document import ParsedDocument
from polio_api.db.models.upload_asset import UploadAsset
from polio_domain.enums import (
    DocumentMaskingStatus,
    DocumentProcessingStatus,
    DraftStatus,
    UploadStatus,
)
from polio_ingest import can_ingest_file, parse_uploaded_document
from polio_shared.paths import resolve_stored_path

IN_PROGRESS_DOCUMENT_STATUSES = {
    DocumentProcessingStatus.MASKING.value,
    DocumentProcessingStatus.PARSING.value,
    DocumentProcessingStatus.RETRYING.value,
}
DOCUMENT_FAILURE_FALLBACK = "Document processing failed. Retry after checking the uploaded file."


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def upload_supports_ingest(upload_asset: UploadAsset) -> bool:
    return can_ingest_file(upload_asset.original_filename)


def ensure_document_placeholder(db: Session, upload_asset: UploadAsset) -> ParsedDocument:
    if upload_asset.parsed_document is not None:
        return upload_asset.parsed_document

    source_extension = Path(upload_asset.original_filename or "").suffix.lower() or ".bin"
    document = ParsedDocument(
        project_id=upload_asset.project_id,
        upload_asset_id=upload_asset.id,
        parser_name="pending",
        source_extension=source_extension,
        status=DocumentProcessingStatus.UPLOADED.value,
        masking_status=DocumentMaskingStatus.PENDING.value,
        parse_metadata={
            "filename": upload_asset.original_filename,
            "content_type": upload_asset.content_type,
        },
    )
    db.add(document)
    db.commit()
    db.refresh(document)
    db.refresh(upload_asset)
    return document


def _map_document_status_to_upload_status(document_status: str) -> str:
    mapping = {
        DocumentProcessingStatus.UPLOADED.value: UploadStatus.STORED.value,
        DocumentProcessingStatus.MASKING.value: UploadStatus.MASKING.value,
        DocumentProcessingStatus.PARSING.value: UploadStatus.PARSING.value,
        DocumentProcessingStatus.RETRYING.value: UploadStatus.RETRYING.value,
        DocumentProcessingStatus.PARSED.value: UploadStatus.PARSED.value,
        DocumentProcessingStatus.PARTIAL.value: UploadStatus.PARTIAL.value,
        DocumentProcessingStatus.FAILED.value: UploadStatus.FAILED.value,
    }
    return mapping.get(document_status, UploadStatus.STORED.value)


def mark_document_processing(
    db: Session,
    document: ParsedDocument,
    upload_asset: UploadAsset,
) -> ParsedDocument:
    document.parse_attempts += 1
    document.status = (
        DocumentProcessingStatus.RETRYING.value
        if document.parse_attempts > 1
        else DocumentProcessingStatus.MASKING.value
    )
    document.masking_status = DocumentMaskingStatus.MASKING.value
    document.last_error = None
    document.parse_started_at = utc_now()
    document.parse_completed_at = None
    document.parse_metadata = {
        **(document.parse_metadata or {}),
        "filename": upload_asset.original_filename,
        "content_type": upload_asset.content_type,
    }

    upload_asset.status = _map_document_status_to_upload_status(document.status)
    upload_asset.ingest_error = None
    db.add(document)
    db.add(upload_asset)
    db.commit()
    db.refresh(document)
    return document


def _mark_document_failed(
    db: Session,
    document: ParsedDocument,
    upload_asset: UploadAsset,
    message: str,
    *,
    masking_failed: bool = False,
) -> None:
    public_message = sanitize_public_error(message, fallback=DOCUMENT_FAILURE_FALLBACK)
    document.status = DocumentProcessingStatus.FAILED.value
    if masking_failed:
        document.masking_status = DocumentMaskingStatus.FAILED.value
    document.last_error = public_message
    document.parse_completed_at = utc_now()
    document.parse_metadata = {
        **(document.parse_metadata or {}),
        "warnings": [public_message],
    }

    upload_asset.status = UploadStatus.FAILED.value
    upload_asset.ingest_error = public_message
    db.add(document)
    db.add(upload_asset)
    db.commit()


def ingest_upload_asset(
    db: Session,
    upload_asset: UploadAsset,
    *,
    force: bool = False,
    prepared: bool = False,
) -> ParsedDocument:
    document = ensure_document_placeholder(db, upload_asset)
    if document.status in IN_PROGRESS_DOCUMENT_STATUSES and not force:
        return document
    if document.status in {DocumentProcessingStatus.PARSED.value, DocumentProcessingStatus.PARTIAL.value} and not force:
        return document

    if not upload_supports_ingest(upload_asset):
        message = f"Unsupported ingest extension for {upload_asset.original_filename}"
        _mark_document_failed(db, document, upload_asset, message, masking_failed=True)
        raise ValueError(message)

    if not prepared:
        mark_document_processing(db, document, upload_asset)

    source_path = resolve_stored_path(upload_asset.stored_path)
    if not source_path.exists():
        message = f"Source file not found: {source_path}"
        _mark_document_failed(db, document, upload_asset, message, masking_failed=True)
        raise FileNotFoundError(message)

    settings = get_settings()
    try:
        parsed = parse_uploaded_document(
            source_path,
            chunk_size_chars=settings.upload_chunk_size_chars,
            overlap_chars=settings.upload_chunk_overlap_chars,
            odl_enabled=getattr(settings, "opendataloader_enabled", True),
        )

        if document.chunks:
            db.execute(delete(DocumentChunk).where(DocumentChunk.document_id == document.id))

        document.parser_name = parsed.parser_name
        document.source_extension = parsed.source_extension
        document.status = parsed.processing_status
        document.masking_status = parsed.masking_status
        document.page_count = parsed.page_count
        document.word_count = parsed.word_count
        document.content_text = parsed.content_text
        document.content_markdown = parsed.content_markdown
        document.parse_completed_at = utc_now()
        document.parse_metadata = {
            **parsed.metadata,
            "warnings": [
                sanitize_public_error(str(item), fallback=DOCUMENT_FAILURE_FALLBACK)
                for item in parsed.warnings
                if str(item).strip()
            ],
            "chunk_count": len(parsed.chunks),
            "chunk_evidence_map": {
                str(chunk.chunk_index): chunk.metadata
                for chunk in parsed.chunks
                if chunk.metadata
            },
            "raw_artifact": parsed.raw_artifact,
            "masked_artifact": parsed.masked_artifact,
            "analysis_artifact": parsed.analysis_artifact,
            "parse_confidence": parsed.parse_confidence,
            "needs_review": parsed.needs_review,
        }
        document.last_error = None
        if parsed.processing_status in {
            DocumentProcessingStatus.PARTIAL.value,
            DocumentProcessingStatus.FAILED.value,
        } and parsed.warnings:
            document.last_error = sanitize_public_error(
                parsed.warnings[0],
                fallback=DOCUMENT_FAILURE_FALLBACK,
            )

        from polio_shared.embeddings import get_embedding_service

        embedding_service = get_embedding_service(
            settings.retrieval_embedding_model,
            dimensions=settings.vector_dimensions,
        )
        embedding_metadata = embedding_service.metadata()
        chunk_texts = [c.content_text for c in parsed.chunks]
        embeddings = embedding_service.generate_embeddings(chunk_texts) if chunk_texts else []

        for i, chunk in enumerate(parsed.chunks):
            chunk_embedding = embeddings[i] if i < len(embeddings) else None
            db.add(
                DocumentChunk(
                    document_id=document.id,
                    project_id=upload_asset.project_id,
                    chunk_index=chunk.chunk_index,
                    page_number=chunk.page_number,
                    char_start=chunk.char_start,
                    char_end=chunk.char_end,
                    token_estimate=chunk.token_estimate,
                    content_text=chunk.content_text,
                    embedding=chunk_embedding,
                    embedding_model=embedding_metadata.model_name,
                )
            )

        upload_asset.status = _map_document_status_to_upload_status(document.status)
        upload_asset.page_count = parsed.page_count
        upload_asset.ingested_at = utc_now()
        upload_asset.ingest_error = document.last_error
        db.add(document)
        db.add(upload_asset)
        db.commit()
        db.refresh(document)
        return document
    except Exception as exc:  # noqa: BLE001
        _mark_document_failed(db, document, upload_asset, str(exc), masking_failed=True)
        raise


def parse_document_by_id(
    db: Session,
    document_id: str,
    *,
    force: bool = True,
    prepared: bool = False,
) -> ParsedDocument:
    document = get_document(db, document_id)
    if document is None:
        raise ValueError(f"Document not found: {document_id}")
    if document.upload_asset is None:
        raise ValueError(f"Document has no upload asset: {document_id}")
    return ingest_upload_asset(db, document.upload_asset, force=force, prepared=prepared)


def enqueue_document_parse(document_id: str) -> None:
    db = SessionLocal()
    try:
        document = get_document(db, document_id)
        if document is None:
            return
        from polio_api.services.async_job_service import create_async_job, dispatch_job_if_enabled
        from polio_domain.enums import AsyncJobType

        job = create_async_job(
            db,
            job_type=AsyncJobType.DOCUMENT_PARSE.value,
            resource_type="parsed_document",
            resource_id=document_id,
            project_id=document.project_id,
            payload={"document_id": document_id, "prepared": True},
        )
        document.parse_metadata = {
            **(document.parse_metadata or {}),
            "latest_async_job_id": job.id,
            "latest_async_job_status": job.status,
        }
        db.add(document)
        db.commit()
        dispatch_job_if_enabled(job.id)
    finally:
        db.close()


def list_documents_for_project(db: Session, project_id: str) -> list[ParsedDocument]:
    stmt = (
        select(ParsedDocument)
        .where(ParsedDocument.project_id == project_id)
        .order_by(ParsedDocument.updated_at.desc())
    )
    return list(db.scalars(stmt))


def get_document(db: Session, document_id: str) -> ParsedDocument | None:
    return db.get(ParsedDocument, document_id)


def list_chunks_for_document(db: Session, document_id: str) -> list[DocumentChunk]:
    stmt = (
        select(DocumentChunk)
        .where(DocumentChunk.document_id == document_id)
        .order_by(DocumentChunk.chunk_index.asc())
    )
    return list(db.scalars(stmt))


def list_chunks_for_project(db: Session, project_id: str, *, limit: int | None = None) -> list[DocumentChunk]:
    stmt = (
        select(DocumentChunk)
        .options(joinedload(DocumentChunk.document))
        .where(DocumentChunk.project_id == project_id)
        .order_by(DocumentChunk.chunk_index.asc())
    )
    if limit is not None:
        stmt = stmt.limit(limit)
    return list(db.scalars(stmt))


def create_seed_draft_from_document(
    db: Session,
    *,
    project_id: str,
    document: ParsedDocument,
    title: str | None = None,
    include_excerpt_limit: int = 4000,
) -> Draft:
    excerpt = document.content_markdown.strip()
    if len(excerpt) > include_excerpt_limit:
        excerpt = excerpt[:include_excerpt_limit].rstrip() + "\n\n..."

    source_file = document.parse_metadata.get("filename", "uploaded document")
    markdown = "\n".join(
        [
            f"# {title or f'{document.upload_asset.original_filename} based draft'}",
            "",
            "## Source Document",
            f"- Uploaded file: {source_file}",
            f"- Parser: {document.parser_name}",
            f"- Page count: {document.page_count}",
            f"- Word count: {document.word_count}",
            "",
            "## Drafting Notes",
            "- Stay grounded in the uploaded evidence.",
            "- Add new claims only after they are verified against the source.",
            "",
            "## Extracted Source",
            excerpt or "_No extracted text available._",
        ]
    ).strip()

    draft = Draft(
        project_id=project_id,
        source_document_id=document.id,
        title=title or f"{document.upload_asset.original_filename} based draft",
        content_markdown=markdown,
        status=DraftStatus.OUTLINE.value,
    )
    db.add(draft)
    db.commit()
    db.refresh(draft)
    return draft
