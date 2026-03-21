from __future__ import annotations

import logging

from db.session import session_scope
from services.admissions.analysis_run_service import analysis_run_service
from services.admissions.student_analysis_service import student_analysis_service


logger = logging.getLogger(__name__)


def run_pending_analysis_runs(limit: int = 10) -> int:
    processed = 0
    with session_scope() as session:
        runs = analysis_run_service.list_queued_runs(session, limit=limit)
        for run in runs:
            logger.info("worker.analysis.processing", extra={"run_id": str(run.id)})
            student_analysis_service.process_run(session, run)
            processed += 1
    return processed
