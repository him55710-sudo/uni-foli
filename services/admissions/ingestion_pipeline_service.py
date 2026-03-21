from __future__ import annotations

from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from db.models.content import Document, DocumentVersion, FileObject, IngestionJob, ParsedBlock
from db.models.crawl import DiscoveredUrl
from domain.enums import DiscoveredUrlStatus, DocumentStatus, FileObjectStatus, IngestionJobStatus, SourceTier
from parsers.base import ParserContext
from parsers.registry import parser_registry
from services.admissions.catalog_service import catalog_service
from services.admissions.chunking_service import chunking_service
from services.admissions.normalization_service import normalization_service
from services.admissions.quality_service import quality_scoring_service
from services.admissions.retrieval_index_service import retrieval_index_service
from services.admissions.utils import ensure_uuid


class IngestionPipelineService:
    def process_ingestion_job(self, session: Session, job: IngestionJob) -> IngestionJob:
        if job.file_object_id is None:
            job.status = IngestionJobStatus.FAILED
            job.error_message = "Ingestion job has no file_object_id."
            session.flush()
            return job

        file_object = session.get(FileObject, job.file_object_id)
        if file_object is None or not file_object.local_path:
            job.status = IngestionJobStatus.FAILED
            job.error_message = "File object missing or local path unavailable."
            session.flush()
            return job

        trace_meta = job.trace_json or {}
        source_tier_raw = trace_meta.get("source_tier", SourceTier.TIER_1_OFFICIAL.value)
        source_tier = source_tier_raw if isinstance(source_tier_raw, SourceTier) else SourceTier(str(source_tier_raw))

        job.status = IngestionJobStatus.PARSING
        job.started_at = datetime.now(UTC)
        session.flush()

        try:
            payload = Path(file_object.local_path).read_bytes()
            parsed = parser_registry.parse(
                payload,
                ParserContext(
                    filename=file_object.original_filename,
                    mime_type=file_object.mime_type,
                    source_url=file_object.source_url,
                    file_hash=file_object.sha256,
                    local_path=file_object.local_path,
                    parser_hints={"source_tier": source_tier.value},
                ),
            )
        except Exception as exc:
            job.status = IngestionJobStatus.FAILED
            job.error_message = str(exc)
            job.finished_at = datetime.now(UTC)
            session.flush()
            return job

        admissions_year = parsed.admissions_year or normalization_service.extract_admissions_year(parsed.title or parsed.raw_text)
        catalog_document_type = catalog_service.classify_document_type(
            session,
            f"{parsed.title or ''} {file_object.original_filename}",
        )
        document_type = catalog_document_type or normalization_service.classify_document_type(parsed.title, file_object.original_filename)
        cycle_label, _ = catalog_service.normalize_cycle_label(session, parsed.cycle_label)
        university = catalog_service.canonicalize_university_name(session, parsed.university_name)
        trust_score, freshness_score, quality_score = quality_scoring_service.document_scores(
            source_tier=source_tier,
            publication_date=parsed.publication_date,
            admissions_year=admissions_year,
            document_type=document_type,
            block_count=len(parsed.blocks),
        )
        content_hash = sha256(parsed.cleaned_text.encode("utf-8")).hexdigest()
        source_document_key = str(trace_meta.get("source_document_key") or parsed.source_url or file_object.source_url or job.input_locator)
        document = None
        if job.source_id is not None and source_document_key:
            document = session.scalar(
                select(Document).where(
                    Document.source_id == job.source_id,
                    Document.source_document_key == source_document_key,
                )
            )

        if document is None:
            document = Document(
                source_id=job.source_id,
                source_document_key=source_document_key,
                canonical_title=parsed.title or file_object.original_filename,
                document_type=document_type,
                source_url=parsed.source_url or file_object.source_url,
                publication_date=parsed.publication_date,
                admissions_year=admissions_year,
                cycle_label=cycle_label,
                source_tier=source_tier,
                trust_score=trust_score,
                freshness_score=freshness_score,
                quality_score=quality_score,
                is_current_cycle=admissions_year == datetime.now(UTC).year if admissions_year is not None else False,
                status=DocumentStatus.REGISTERED,
                university_id=university.id if university is not None else None,
                metadata_json={},
            )
            session.add(document)
            session.flush()
        else:
            if document.current_version_id is not None:
                current_version = session.get(DocumentVersion, document.current_version_id)
                if current_version is not None and current_version.content_hash == content_hash:
                    self._update_document_metadata(
                        document=document,
                        parsed=parsed,
                        source_tier=source_tier,
                        admissions_year=admissions_year,
                        cycle_label=cycle_label,
                        document_type=document_type,
                        trust_score=trust_score,
                        freshness_score=freshness_score,
                        quality_score=quality_score,
                        university_id=university.id if university is not None else None,
                    )
                    job.document_id = document.id
                    job.pipeline_stage = "deduped"
                    job.status = IngestionJobStatus.SUCCEEDED
                    job.finished_at = datetime.now(UTC)
                    file_object.status = FileObjectStatus.PARSED
                    self._attach_discovered_url(session, trace_meta, file_object.id, document.id)
                    session.flush()
                    session.refresh(job)
                    return job

        self._update_document_metadata(
            document=document,
            parsed=parsed,
            source_tier=source_tier,
            admissions_year=admissions_year,
            cycle_label=cycle_label,
            document_type=document_type,
            trust_score=trust_score,
            freshness_score=freshness_score,
            quality_score=quality_score,
            university_id=university.id if university is not None else None,
        )
        session.flush()

        version_number = (
            session.scalar(select(func.count(DocumentVersion.id)).where(DocumentVersion.document_id == document.id)) or 0
        ) + 1
        previous_version_id = document.current_version_id
        version = DocumentVersion(
            document_id=document.id,
            file_object_id=file_object.id,
            previous_version_id=previous_version_id,
            version_number=version_number,
            parser_name=parsed.parser_name,
            parser_version=parsed.parser_version,
            content_hash=content_hash,
            page_count=parsed.metadata.get("page_count", 0) if parsed.metadata else 0,
            raw_text_length=len(parsed.raw_text),
            cleaned_text_length=len(parsed.cleaned_text),
            parse_status=DocumentStatus.PARSED,
            normalized_payload=parsed.model_dump(mode="json"),
        )
        session.add(version)
        session.flush()

        persisted_blocks: list[ParsedBlock] = []
        for block in parsed.blocks:
            persisted_block = ParsedBlock(
                document_id=document.id,
                document_version_id=version.id,
                block_index=block.block_index,
                block_type=block.block_type,
                heading_path=block.heading_path,
                page_start=block.page_number,
                page_end=block.page_number,
                char_start=block.char_start,
                char_end=block.char_end,
                text_sha256=sha256(block.cleaned_text.encode("utf-8")).hexdigest(),
                raw_text=block.raw_text,
                cleaned_text=block.cleaned_text,
                token_estimate=max(1, len(block.cleaned_text) // 4),
                metadata_json=block.metadata,
            )
            session.add(persisted_block)
            persisted_blocks.append(persisted_block)

        session.flush()

        chunks = chunking_service.build_chunks(
            document_id=document.id,
            document_version_id=version.id,
            parsed_blocks=persisted_blocks,
        )
        for chunk in chunks:
            session.add(chunk)

        session.flush()
        retrieval_index_service.refresh_document_chunks(session, document_id=document.id)

        document.current_version_id = version.id
        document.status = DocumentStatus.PARSED
        job.document_id = document.id
        job.pipeline_stage = "parsed"
        job.status = IngestionJobStatus.SUCCEEDED
        job.finished_at = datetime.now(UTC)
        file_object.status = FileObjectStatus.PARSED
        self._attach_discovered_url(session, trace_meta, file_object.id, document.id)
        session.flush()
        session.refresh(job)
        return job

    def _update_document_metadata(
        self,
        *,
        document: Document,
        parsed,
        source_tier: SourceTier,
        admissions_year: int | None,
        cycle_label: str | None,
        document_type,
        trust_score: float,
        freshness_score: float,
        quality_score: float,
        university_id,
    ) -> None:
        document.canonical_title = parsed.title or document.canonical_title
        document.document_type = document_type
        document.source_url = parsed.source_url or document.source_url
        document.publication_date = parsed.publication_date or document.publication_date
        document.admissions_year = admissions_year
        document.cycle_label = cycle_label
        document.source_tier = source_tier
        document.trust_score = trust_score
        document.freshness_score = freshness_score
        document.quality_score = quality_score
        document.is_current_cycle = admissions_year == datetime.now(UTC).year if admissions_year is not None else False
        document.university_id = university_id
        document.metadata_json = {
            **(document.metadata_json or {}),
            "issuing_organization": parsed.issuing_organization,
            "university_name": parsed.university_name,
            "track_name": parsed.track_name,
            "parser_name": parsed.parser_name,
            "parser_trace": parsed.parser_trace,
            "parser_fallback_reason": parsed.fallback_reason,
        }

    def _attach_discovered_url(
        self,
        session: Session,
        trace_meta: dict[str, object],
        file_object_id,
        document_id,
    ) -> None:
        discovered_url_id = trace_meta.get("discovered_url_id")
        if not discovered_url_id:
            return
        discovered_url = session.get(DiscoveredUrl, ensure_uuid(str(discovered_url_id)))
        if discovered_url is None:
            return
        discovered_url.file_object_id = file_object_id
        discovered_url.document_id = document_id
        discovered_url.status = DiscoveredUrlStatus.INGESTED
        discovered_url.last_fetched_at = datetime.now(UTC)


ingestion_pipeline_service = IngestionPipelineService()
