from __future__ import annotations

import logging

from db.session import initialize_database
from workers.tasks.analysis import run_pending_analysis_runs
from workers.tasks.claims import run_pending_claim_extraction
from workers.tasks.ingestion import run_pending_ingestion_jobs


logger = logging.getLogger(__name__)


def main() -> None:
    initialize_database()
    ingestion_count = run_pending_ingestion_jobs()
    claim_count = run_pending_claim_extraction()
    analysis_count = run_pending_analysis_runs()
    logger.info(
        "worker.cycle.completed",
        extra={
            "ingestion_count": ingestion_count,
            "claim_count": claim_count,
            "analysis_count": analysis_count,
        },
    )


if __name__ == "__main__":
    main()
