from __future__ import annotations

from hashlib import sha256

from sqlalchemy import select
from sqlalchemy.orm import Session

from db.models.content import IngestionJob
from domain.enums import IngestionJobStatus
from services.admissions.utils import ensure_uuid


class IngestionJobService:
    def create_job(
        self,
        session: Session,
        *,
        input_locator: str,
        source_id: str | None = None,
        source_crawl_job_id: str | None = None,
        file_object_id: str | None = None,
        document_id: str | None = None,
        pipeline_stage: str = "registered",
        trace_json: dict[str, object] | None = None,
    ) -> IngestionJob:
        digest = sha256(f"{source_id}:{input_locator}:{file_object_id}:{document_id}".encode("utf-8")).hexdigest()
        existing = session.scalar(select(IngestionJob).where(IngestionJob.idempotency_key == digest))
        if existing is not None:
            return existing

        job = IngestionJob(
            source_id=ensure_uuid(source_id),
            source_crawl_job_id=ensure_uuid(source_crawl_job_id),
            file_object_id=ensure_uuid(file_object_id),
            document_id=ensure_uuid(document_id),
            input_locator=input_locator,
            idempotency_key=digest,
            pipeline_stage=pipeline_stage,
            status=IngestionJobStatus.QUEUED,
            trace_json={"stage": pipeline_stage, **(trace_json or {})},
        )
        session.add(job)
        session.flush()
        session.refresh(job)
        return job

    def get_job(self, session: Session, job_id: str) -> IngestionJob | None:
        return session.get(IngestionJob, ensure_uuid(job_id))

    def list_jobs(self, session: Session, *, limit: int = 100) -> list[IngestionJob]:
        stmt = select(IngestionJob).order_by(IngestionJob.created_at.desc()).limit(limit)
        return list(session.scalars(stmt))

    def list_queued_jobs(self, session: Session, *, limit: int = 20) -> list[IngestionJob]:
        stmt = (
            select(IngestionJob)
            .where(IngestionJob.status == IngestionJobStatus.QUEUED)
            .order_by(IngestionJob.created_at.asc())
            .limit(limit)
        )
        return list(session.scalars(stmt))


ingestion_job_service = IngestionJobService()
