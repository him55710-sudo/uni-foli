from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from polio_api.core.config import get_settings
from polio_api.db.models.document_chunk import DocumentChunk
from polio_api.db.models.draft import Draft
from polio_api.db.models.parsed_document import ParsedDocument
from polio_api.db.models.upload_asset import UploadAsset
from polio_domain.enums import DraftStatus, UploadStatus
from polio_ingest import can_ingest_file, parse_uploaded_document
from polio_shared.paths import resolve_stored_path


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def upload_supports_ingest(upload_asset: UploadAsset) -> bool:
    return can_ingest_file(upload_asset.original_filename)


def ingest_upload_asset(db: Session, upload_asset: UploadAsset, *, force: bool = False) -> ParsedDocument:
    if upload_asset.parsed_document and not force:
        return upload_asset.parsed_document

    source_path = resolve_stored_path(upload_asset.stored_path)
    if not source_path.exists():
        upload_asset.status = UploadStatus.FAILED.value
        upload_asset.ingest_error = f"Source file not found: {source_path}"
        db.commit()
        raise FileNotFoundError(upload_asset.ingest_error)

    settings = get_settings()
    upload_asset.status = UploadStatus.PARSING.value
    upload_asset.ingest_error = None
    db.commit()
    db.refresh(upload_asset)

    try:
        parsed = parse_uploaded_document(
            source_path,
            chunk_size_chars=settings.upload_chunk_size_chars,
            overlap_chars=settings.upload_chunk_overlap_chars,
        )

        document = upload_asset.parsed_document
        if not document:
            document = ParsedDocument(
                project_id=upload_asset.project_id,
                upload_asset_id=upload_asset.id,
            )
            db.add(document)
            db.flush()
        else:
            db.execute(delete(DocumentChunk).where(DocumentChunk.document_id == document.id))

        document.parser_name = parsed.parser_name
        document.source_extension = parsed.source_extension
        document.page_count = parsed.page_count
        document.word_count = parsed.word_count
        document.content_text = parsed.content_text
        document.content_markdown = parsed.content_markdown
        document.parse_metadata = parsed.metadata

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

        upload_asset.status = UploadStatus.PARSED.value
        upload_asset.page_count = parsed.page_count
        upload_asset.ingested_at = utc_now()
        upload_asset.ingest_error = None
        db.commit()
        db.refresh(document)
        return document
    except Exception as exc:  # noqa: BLE001
        upload_asset.status = UploadStatus.FAILED.value
        upload_asset.ingest_error = str(exc)
        db.commit()
        raise


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
            f"# {title or f'{document.upload_asset.original_filename} 기반 초안'}",
            "",
            "## 참고 문서",
            f"- 업로드 파일: {source_file}",
            f"- 파서: {document.parser_name}",
            f"- 페이지 수: {document.page_count}",
            f"- 단어 수: {document.word_count}",
            "",
            "## 작성 메모",
            "- 아래 원문 발췌를 참고해서 자기소개서, 활동 정리, 포트폴리오 문단을 발전시켜 주세요.",
            "- 출처를 벗어나는 추측 문장은 직접 검토 후 보강하세요.",
            "",
            "## 원문 발췌",
            excerpt or "_No extracted text available._",
        ]
    ).strip()

    draft = Draft(
        project_id=project_id,
        source_document_id=document.id,
        title=title or f"{document.upload_asset.original_filename} 기반 초안",
        content_markdown=markdown,
        status=DraftStatus.OUTLINE.value,
    )
    db.add(draft)
    db.commit()
    db.refresh(draft)
    return draft
