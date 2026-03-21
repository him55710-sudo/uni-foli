from __future__ import annotations

import logging

from db.session import session_scope
from services.admissions.ingestion_job_service import ingestion_job_service
from services.admissions.ingestion_pipeline_service import ingestion_pipeline_service


logger = logging.getLogger(__name__)


def run_pending_ingestion_jobs(limit: int = 10) -> int:
    processed = 0
    with session_scope() as session:
        jobs = ingestion_job_service.list_queued_jobs(session, limit=limit)
        for job in jobs:
            logger.info("worker.ingestion.processing", extra={"job_id": str(job.id)})
            ingestion_pipeline_service.process_ingestion_job(session, job)
            processed += 1
    return processed
