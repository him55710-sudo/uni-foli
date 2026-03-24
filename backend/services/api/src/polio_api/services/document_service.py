from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from threading import Thread

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from polio_api.core.config import get_settings
from polio_api.core.database import SessionLocal
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
    document.status = DocumentProcessingStatus.FAILED.value
    if masking_failed:
        document.masking_status = DocumentMaskingStatus.FAILED.value
    document.last_error = message
    document.parse_completed_at = utc_now()
    document.parse_metadata = {
        **(document.parse_metadata or {}),
        "warnings": [message],
    }

    upload_asset.status = UploadStatus.FAILED.value
    upload_asset.ingest_error = message
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
            "warnings": parsed.warnings,
            "chunk_count": len(parsed.chunks),
        }
        document.last_error = None
        if parsed.processing_status in {
            DocumentProcessingStatus.PARTIAL.value,
            DocumentProcessingStatus.FAILED.value,
        } and parsed.warnings:
            document.last_error = parsed.warnings[0]

        for chunk in parsed.chunks:
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
    worker = Thread(
        target=_parse_document_worker,
        args=(document_id,),
        daemon=True,
        name=f"polio-document-parse-{document_id}",
    )
    worker.start()


def _parse_document_worker(document_id: str) -> None:
    db = SessionLocal()
    try:
        parse_document_by_id(db, document_id, force=True, prepared=True)
    except Exception:
        # The document state is already persisted by ingest_upload_asset.
        pass
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
