from __future__ import annotations

from pathlib import Path

from sqlalchemy import delete, select
from sqlalchemy.orm import Session, joinedload, load_only

from unifoli_api.core.config import get_settings
from unifoli_api.core.database import SessionLocal, utc_now
from unifoli_api.core.security import sanitize_public_error
from unifoli_api.db.models.document_chunk import DocumentChunk
from unifoli_api.db.models.draft import Draft
from unifoli_api.db.models.parsed_document import ParsedDocument
from unifoli_api.db.models.upload_asset import UploadAsset
from unifoli_api.services.pdf_analysis_service import (
    build_pdf_analysis_metadata,
    build_student_record_canonical_metadata,
    build_student_record_structure_metadata,
    classify_student_record_document_kind,
)
from unifoli_api.services.student_record_pipeline_service import StudentRecordPipelineService
from unifoli_api.schemas.pipeline_metadata import PipelineMetadata
import pdfplumber
import logging
from unifoli_api.core.errors import UniFoliErrorCode, UniFoliError

logger = logging.getLogger(__name__)
from unifoli_domain.enums import (
    DocumentMaskingStatus,
    DocumentProcessingStatus,
    DraftStatus,
    UploadStatus,
)
from unifoli_ingest import can_ingest_file, parse_uploaded_document
from unifoli_shared.storage import (
    get_storage_provider,
    get_storage_provider_name,
    materialize_storage_path_once,
)

IN_PROGRESS_DOCUMENT_STATUSES = {
    DocumentProcessingStatus.MASKING.value,
    DocumentProcessingStatus.PARSING.value,
    DocumentProcessingStatus.RETRYING.value,
}
DOCUMENT_FAILURE_FALLBACK = "Document processing failed. Retry after checking the uploaded file."
STUDENT_RECORD_KEYWORDS = (
    "학교생활기록부",
    "생활기록부",
    "학생부",
    "생기부",
)
ADVANCED_PIPELINE_DEGRADED_SECTIONS = [
    "student_record_structure",
    "subject_specialty_analysis",
    "network_analysis",
    "high_confidence_score_claims",
]
_DOCUMENT_FAILURE_CODE_MAP = {
    "pdf_malformed": "MALFORMED_PDF",
    "pdf_encrypted": "ENCRYPTED_PDF",
    "pdf_no_usable_text": UniFoliErrorCode.NO_USABLE_TEXT.value,
    "file_not_found": UniFoliErrorCode.FILE_NOT_FOUND.value,
    "storage_missing": UniFoliErrorCode.FILE_NOT_FOUND.value,
}


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


def sync_document_async_job_state(
    document: ParsedDocument,
    *,
    job_id: str | None,
    job_status: str | None,
    job_error: str | None = None,
) -> ParsedDocument:
    metadata = dict(document.parse_metadata or {})

    if job_id:
        document.latest_async_job_id = job_id
        metadata["latest_async_job_id"] = job_id
    else:
        document.latest_async_job_id = None
        metadata.pop("latest_async_job_id", None)

    if job_status:
        document.latest_async_job_status = job_status
        metadata["latest_async_job_status"] = job_status
    else:
        document.latest_async_job_status = None
        metadata.pop("latest_async_job_status", None)

    if job_error:
        document.latest_async_job_error = job_error
        metadata["latest_async_job_error"] = job_error
    else:
        document.latest_async_job_error = None
        metadata.pop("latest_async_job_error", None)

    document.parse_metadata = metadata
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


def _normalize_document_failure_code(raw_code: str | None, message: str) -> str:
    normalized = str(raw_code or "").strip()
    lowered = normalized.lower()
    if lowered in _DOCUMENT_FAILURE_CODE_MAP:
        return _DOCUMENT_FAILURE_CODE_MAP[lowered]
    if normalized in {member.value for member in UniFoliErrorCode}:
        return normalized

    lowered_message = str(message or "").lower()
    if "encrypted pdf" in lowered_message:
        return "ENCRYPTED_PDF"
    if "malformed" in lowered_message and "pdf" in lowered_message:
        return "MALFORMED_PDF"
    if "no extractable text" in lowered_message or "no usable text" in lowered_message:
        return UniFoliErrorCode.NO_USABLE_TEXT.value
    if "not found in storage" in lowered_message or "source file not found" in lowered_message:
        return UniFoliErrorCode.FILE_NOT_FOUND.value
    return normalized or UniFoliErrorCode.INTERNAL_ERROR.value


def _is_student_record_candidate(*, parser_name: str, content_text: str | None) -> bool:
    text = content_text or ""
    return parser_name == "neis" or any(keyword in text for keyword in STUDENT_RECORD_KEYWORDS)


def _append_metadata_warning(metadata: dict, message: str) -> None:
    public_message = sanitize_public_error(message, fallback=DOCUMENT_FAILURE_FALLBACK)
    warnings = [
        sanitize_public_error(str(item), fallback=DOCUMENT_FAILURE_FALLBACK)
        for item in metadata.get("warnings", [])
        if str(item).strip()
    ]
    if public_message not in warnings:
        warnings.append(public_message)
    metadata["warnings"] = warnings


def _mark_advanced_pipeline_degraded(metadata: dict, reason: str) -> None:
    public_reason = sanitize_public_error(reason, fallback=DOCUMENT_FAILURE_FALLBACK)
    metadata["pipeline_status"] = "failed"
    metadata["pipeline_error"] = public_reason
    metadata["needs_review"] = True
    metadata["provisional_reason"] = (
        "심층 학생부 구조 분석이 실패해 일부 리포트 섹션은 보수적으로 제한됩니다."
    )
    metadata["diagnosis_disabled_sections"] = ADVANCED_PIPELINE_DEGRADED_SECTIONS
    _append_metadata_warning(metadata, metadata["provisional_reason"])
    existing_quality = metadata.get("parse_quality")
    parse_quality = existing_quality if isinstance(existing_quality, dict) else {}
    quality_warnings = [
        str(item)
        for item in parse_quality.get("warnings", [])
        if str(item).strip()
    ]
    if metadata["provisional_reason"] not in quality_warnings:
        quality_warnings.append(metadata["provisional_reason"])
    metadata["parse_quality"] = {
        **parse_quality,
        "overall_score": min(float(parse_quality.get("overall_score") or 0.45), 0.45),
        "section_coverage_score": min(float(parse_quality.get("section_coverage_score") or 0.35), 0.35),
        "missing_critical_sections": parse_quality.get("missing_critical_sections") or ADVANCED_PIPELINE_DEGRADED_SECTIONS[:3],
        "warnings": quality_warnings,
        "is_provisional": True,
    }


def _apply_advanced_quality_report(metadata: dict, quality_report: dict) -> None:
    if not quality_report:
        return
    overall_score = float(quality_report.get("overall_score", 0) or 0)
    missing_sections = quality_report.get("missing_critical_sections", [])
    metadata["pipeline_status"] = "success"
    metadata["pipeline_quality_score"] = overall_score
    metadata["pipeline_quality_missing_sections"] = missing_sections
    metadata["parse_quality"] = {
        **(metadata.get("parse_quality") if isinstance(metadata.get("parse_quality"), dict) else {}),
        "overall_score": overall_score,
        "section_coverage_score": overall_score,
        "missing_critical_sections": missing_sections if isinstance(missing_sections, list) else [],
        "warnings": [],
        "is_provisional": bool(missing_sections),
    }
    if missing_sections:
        metadata["needs_review"] = True
        _append_metadata_warning(metadata, "심층 분석에서 일부 필수 학생부 섹션이 부족하게 추출되었습니다.")


def _apply_degraded_flags_to_student_record_metadata(metadata: dict) -> None:
    if metadata.get("pipeline_status") != "failed":
        return
    canonical = metadata.get("student_record_canonical")
    if isinstance(canonical, dict) and canonical.get("is_primary_student_record") is not False:
        quality_gates = canonical.get("quality_gates")
        if not isinstance(quality_gates, dict):
            quality_gates = {}
        notes = [
            str(item)
            for item in quality_gates.get("notes", [])
            if str(item).strip()
        ]
        note = "심층 구조 분석 실패로 고신뢰 진단/리포트 섹션은 재분석 전까지 제한됩니다."
        if note not in notes:
            notes.append(note)
        quality_gates.update(
            {
                "reanalysis_required": True,
                "advanced_pipeline_degraded": True,
                "notes": notes,
            }
        )
        canonical["quality_gates"] = quality_gates
        uncertainties = canonical.get("uncertainties")
        if not isinstance(uncertainties, list):
            uncertainties = []
        uncertainty_message = "심층 구조 분석이 실패해 섹션별 판단은 참고용으로 제한됩니다."
        if not any(isinstance(item, dict) and item.get("message") == uncertainty_message for item in uncertainties):
            uncertainties.append({"message": uncertainty_message})
        canonical["uncertainties"] = uncertainties
        metadata["student_record_canonical"] = canonical
    if "student_record_structure" in metadata:
        metadata["student_record_structure_disabled"] = True


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
    failure_code: str | None = None,
    failure_stage: str = "document_ingest",
) -> None:
    public_message = sanitize_public_error(message, fallback=DOCUMENT_FAILURE_FALLBACK)
    normalized_code = _normalize_document_failure_code(failure_code, message)
    existing_metadata = dict(document.parse_metadata or {})
    warnings = [
        sanitize_public_error(str(item), fallback=DOCUMENT_FAILURE_FALLBACK)
        for item in existing_metadata.get("warnings", [])
        if str(item).strip()
    ]
    if public_message not in warnings:
        warnings.append(public_message)
    document.status = DocumentProcessingStatus.FAILED.value
    if masking_failed:
        document.masking_status = DocumentMaskingStatus.FAILED.value
    document.last_error = public_message
    document.parse_completed_at = utc_now()
    document.parse_metadata = {
        **existing_metadata,
        "warnings": warnings,
        "error_code": normalized_code,
        "failure_stage": failure_stage,
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
    job_id: str | None = None,
) -> ParsedDocument:
    document = ensure_document_placeholder(db, upload_asset)
    if document.status in IN_PROGRESS_DOCUMENT_STATUSES and not force:
        return document
    if document.status in {DocumentProcessingStatus.PARSED.value, DocumentProcessingStatus.PARTIAL.value} and not force:
        return document

    if not upload_supports_ingest(upload_asset):
        message = f"Unsupported ingest extension for {upload_asset.original_filename}"
        _mark_document_failed(
            db,
            document,
            upload_asset,
            message,
            masking_failed=True,
            failure_code="unsupported_extension",
            failure_stage="preflight",
        )
        raise ValueError(message)

    if not prepared:
        mark_document_processing(db, document, upload_asset)

    settings = get_settings()
    storage = get_storage_provider(settings)
    if not storage.exists(upload_asset.stored_path):
        message = f"Source file not found in storage: {upload_asset.stored_path}"
        _mark_document_failed(
            db,
            document,
            upload_asset,
            message,
            masking_failed=True,
            failure_code=UniFoliErrorCode.FILE_NOT_FOUND.value,
            failure_stage="storage_lookup",
        )
        raise FileNotFoundError(message)

    source_path: Path | None = None
    cleanup_source_path = False
    try:
        source_path, cleanup_source_path = materialize_storage_path_once(
            storage,
            upload_asset.stored_path,
            suffix=Path(upload_asset.original_filename or upload_asset.stored_path).suffix,
        )
        if source_path is None:
            raise FileNotFoundError(f"Source file not found in storage: {upload_asset.stored_path}")

        # --- STAGE 1: Base Parse (Critical) ---
        try:
            parsed = parse_uploaded_document(
                source_path,
                chunk_size_chars=settings.upload_chunk_size_chars,
                overlap_chars=settings.upload_chunk_overlap_chars,
                odl_enabled=getattr(settings, "opendataloader_enabled", True),
                neis_ensemble_enabled=getattr(settings, "neis_ensemble_enabled", True),
                neis_auto_detect_enabled=getattr(settings, "neis_auto_detect_enabled", True),
                neis_auto_detect_min_confidence=float(getattr(settings, "neis_auto_detect_min_confidence", 0.62)),
                neis_extractpdf4j_enabled=getattr(settings, "neis_extractpdf4j_enabled", False),
                neis_extractpdf4j_base_url=getattr(settings, "neis_extractpdf4j_base_url", None),
                neis_extractpdf4j_timeout_seconds=float(
                    getattr(settings, "neis_extractpdf4j_timeout_seconds", 8.0)
                ),
                neis_dedoc_enabled=getattr(settings, "neis_dedoc_enabled", True),
                neis_provider_min_quality_score=float(getattr(settings, "neis_provider_min_quality_score", 0.58)),
                neis_merge_policy=str(getattr(settings, "neis_merge_policy", "conservative_table")),
            )
        except Exception as parse_err:
            logger.error(f"Base parse failed critically: {parse_err}")
            _mark_document_failed(
                db,
                document,
                upload_asset,
                f"Base parse failed: {str(parse_err)}",
                failure_code=getattr(parse_err, "code", None),
                failure_stage="base_parse",
            )
            raise

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
        
        # Initialize metadata with base parse results
        document.parse_metadata = {
            **parsed.metadata,
            "warnings": [
                sanitize_public_error(str(item), fallback=DOCUMENT_FAILURE_FALLBACK)
                for item in parsed.warnings
                if str(item).strip()
            ],
            "chunk_count": len(parsed.chunks),
            "raw_artifact": parsed.raw_artifact,
            "masked_artifact": parsed.masked_artifact,
            "parse_confidence": parsed.parse_confidence,
            "needs_review": parsed.needs_review,
            "source_storage_provider": get_storage_provider_name(storage),
            "source_storage_key": upload_asset.stored_path,
        }
        if parsed.processing_status == DocumentProcessingStatus.FAILED.value and parsed.warnings:
            document.parse_metadata["error_code"] = _normalize_document_failure_code(
                parsed.metadata.get("error_code") if isinstance(parsed.metadata, dict) else None,
                parsed.warnings[0],
            )
            document.parse_metadata["failure_stage"] = "base_parse"

        document_kind = classify_student_record_document_kind(parsed)
        if document_kind.get("source_document_kind"):
            document.parse_metadata["source_document_kind"] = document_kind["source_document_kind"]
            document.parse_metadata["document_type"] = document_kind.get("document_type")
            document.parse_metadata["document_type_confidence"] = document_kind.get("document_type_confidence")

        # --- STAGE 2: Advanced Semantic Pipeline (Optional) ---
        is_student_record_candidate = _is_student_record_candidate(
            parser_name=parsed.parser_name,
            content_text=parsed.content_text,
        )
        if document_kind.get("source_document_kind") == "diagnosis_report":
            is_student_record_candidate = False
        if is_student_record_candidate and source_path.suffix.lower() == ".pdf":
            try:
                logger.info(f"Applying advanced semantic parsing pipeline: {upload_asset.original_filename}")
                with pdfplumber.open(source_path) as pdf:
                    advanced_pipeline = StudentRecordPipelineService()

                    def _heartbeat(stage: str | None = None, message: str | None = None):
                        if job_id:
                            from unifoli_api.services.async_job_service import heartbeat_async_job, set_async_job_progress
                            heartbeat_async_job(db, job_id)
                            if stage or message:
                                set_async_job_progress(db, job_id, stage=stage or "running", message=message or "진행 중...")

                    _heartbeat(stage="advanced_parse", message="심층 분석 파이프라인을 가동하고 있습니다...")
                    advanced_artifact = advanced_pipeline.process_document(
                        pdf.pages,
                        parsed.content_text,
                        heartbeat_callback=lambda: _heartbeat(stage="advanced_parse", message="심층 분석을 진행 중입니다..."),
                    )
                    document.parse_metadata["analysis_artifact"] = advanced_artifact

                    quality_report = advanced_artifact.get("quality_report", {})
                    if quality_report:
                        _apply_advanced_quality_report(document.parse_metadata, quality_report)
                    else:
                        document.parse_metadata["pipeline_status"] = "success"
                logger.info("Advanced semantic parsing complete.")
            except Exception as e:
                logger.warning(f"Advanced pipeline failed, falling back: {str(e)}")
                _mark_advanced_pipeline_degraded(document.parse_metadata, str(e))
                document.status = DocumentProcessingStatus.PARTIAL.value

        # --- STAGE 3: PDF Analysis LLM (Optional) ---
        pdf_analysis = None
        try:
            pdf_analysis = build_pdf_analysis_metadata(parsed, analysis_artifact=document.parse_metadata.get("analysis_artifact"))
            if pdf_analysis:
                document.parse_metadata["pdf_analysis"] = pdf_analysis
        except Exception as e:
            logger.warning(f"PDF Analysis LLM failed: {e}")
            document.parse_metadata["pdf_analysis_error"] = sanitize_public_error(str(e))

        # --- STAGE 4: Metadata Composition ---
        try:
            student_record_canonical = build_student_record_canonical_metadata(
                parsed=parsed,
                pdf_analysis=pdf_analysis,
                analysis_artifact=document.parse_metadata.get("analysis_artifact"),
            )
            if student_record_canonical:
                document.parse_metadata["student_record_canonical"] = student_record_canonical
            
            student_record_structure = build_student_record_structure_metadata(
                parsed=parsed,
                pdf_analysis=pdf_analysis,
                analysis_artifact=document.parse_metadata.get("analysis_artifact"),
                canonical_schema=student_record_canonical,
            )
            if student_record_structure:
                document.parse_metadata["student_record_structure"] = student_record_structure
            _apply_degraded_flags_to_student_record_metadata(document.parse_metadata)
        except Exception as e:
            logger.warning(f"Metadata composition failed: {e}")

        # --- VALIDATION: Pipeline Integrity ---
        try:
            # Validate and clean up metadata before final stages
            validated_metadata = PipelineMetadata.from_dict(document.parse_metadata)
            document.parse_metadata = validated_metadata.model_dump(exclude_none=True)
            logger.info("Pipeline metadata validation successful.")
        except Exception as e:
            logger.warning(f"Pipeline metadata validation failed: {str(e)}. Proceeding with raw metadata.")

        # --- STAGE 5: Embeddings (Optional) ---
        try:
            from unifoli_shared.embeddings import get_embedding_service
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
        except Exception as e:
            logger.warning(f"Embedding generation failed: {e}")
            document.parse_metadata["embedding_status"] = "failed"

        # Finalize success
        document.last_error = None
        if parsed.processing_status in {
            DocumentProcessingStatus.PARTIAL.value,
            DocumentProcessingStatus.FAILED.value,
        } and parsed.warnings:
            document.last_error = sanitize_public_error(
                parsed.warnings[0],
                fallback=DOCUMENT_FAILURE_FALLBACK,
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
        if document.status != DocumentProcessingStatus.FAILED.value:
            _mark_document_failed(
                db,
                document,
                upload_asset,
                str(exc),
                masking_failed=True,
                failure_code=getattr(exc, "code", None),
                failure_stage="document_ingest",
            )
        raise
    finally:
        if cleanup_source_path and source_path is not None and source_path.exists():
            source_path.unlink()


def parse_document_by_id(
    db: Session,
    document_id: str,
    *,
    force: bool = True,
    prepared: bool = False,
    job_id: str | None = None,
) -> ParsedDocument:
    document = get_document(db, document_id)
    if document is None:
        raise ValueError(f"Document not found: {document_id}")
    if document.upload_asset is None:
        raise ValueError(f"Document has no upload asset: {document_id}")
    return ingest_upload_asset(db, document.upload_asset, force=force, prepared=prepared, job_id=job_id)


def enqueue_document_parse(document_id: str) -> None:
    db = SessionLocal()
    try:
        document = get_document(db, document_id)
        if document is None:
            return
        from unifoli_api.services.async_job_service import create_async_job, dispatch_job_if_enabled
        from unifoli_domain.enums import AsyncJobType

        job = create_async_job(
            db,
            job_type=AsyncJobType.DOCUMENT_PARSE.value,
            resource_type="parsed_document",
            resource_id=document_id,
            project_id=document.project_id,
            payload={"document_id": document_id, "prepared": True},
        )
        sync_document_async_job_state(
            document,
            job_id=job.id,
            job_status=job.status,
            job_error=None,
        )
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
        .options(
            load_only(
                DocumentChunk.id,
                DocumentChunk.document_id,
                DocumentChunk.project_id,
                DocumentChunk.chunk_index,
                DocumentChunk.page_number,
                DocumentChunk.content_text,
            ),
            joinedload(DocumentChunk.document)
            .load_only(ParsedDocument.id, ParsedDocument.upload_asset_id)
            .joinedload(ParsedDocument.upload_asset)
            .load_only(UploadAsset.id, UploadAsset.original_filename),
        )
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
