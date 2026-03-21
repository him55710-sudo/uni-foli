from __future__ import annotations

from sqlalchemy.orm import Session

from db.models.admissions import Source
from db.models.content import IngestionJob
from services.admissions.file_object_service import file_object_service
from services.admissions.ingestion_job_service import ingestion_job_service
from services.admissions.utils import ensure_uuid


class SourceIngestionService:
    async def upload_source_file(
        self,
        session: Session,
        *,
        source_id: str,
        upload,
        source_url: str | None = None,
    ) -> tuple[Source, IngestionJob]:
        source = session.get(Source, ensure_uuid(source_id))
        if source is None:
            raise ValueError("Source not found")

        namespace = f"sources/{source.slug}"
        file_object, is_duplicate = await file_object_service.store_upload(
            session,
            upload=upload,
            namespace=namespace,
            source_url=source_url,
        )
        job = ingestion_job_service.create_job(
            session,
            input_locator=file_object.local_path or file_object.object_key,
            source_id=str(source.id),
            file_object_id=str(file_object.id),
            pipeline_stage="registered",
            trace_json={
                "source_tier": source.source_tier.value,
                "source_url": source_url,
                "source_document_key": source_url or file_object.sha256,
                "original_filename": upload.filename or "upload.bin",
                "is_duplicate_file_object": is_duplicate,
            },
        )
        return source, job

    def register_downloaded_bytes(
        self,
        session: Session,
        *,
        source: Source,
        payload: bytes,
        filename: str,
        mime_type: str,
        source_url: str,
        namespace: str,
        source_crawl_job_id: str | None = None,
        source_document_key: str | None = None,
        metadata_json: dict[str, object] | None = None,
    ) -> tuple[IngestionJob, bool]:
        file_object, is_duplicate = file_object_service.store_bytes(
            session,
            payload=payload,
            namespace=namespace,
            filename=filename,
            mime_type=mime_type,
            source_url=source_url,
            metadata_json=metadata_json,
        )
        job = ingestion_job_service.create_job(
            session,
            input_locator=file_object.local_path or file_object.object_key,
            source_id=str(source.id),
            source_crawl_job_id=source_crawl_job_id,
            file_object_id=str(file_object.id),
            pipeline_stage="registered",
            trace_json={
                "source_tier": source.source_tier.value,
                "source_url": source_url,
                "source_document_key": source_document_key or source_url,
                "original_filename": filename,
                "is_duplicate_file_object": is_duplicate,
                **(metadata_json or {}),
            },
        )
        return job, is_duplicate


source_ingestion_service = SourceIngestionService()
