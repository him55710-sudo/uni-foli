from __future__ import annotations

import logging

from sqlalchemy import select

from db.models.content import Document
from db.session import session_scope
from domain.enums import DocumentStatus
from services.admissions.claim_service import claim_service


logger = logging.getLogger(__name__)


def run_pending_claim_extraction(limit: int = 10) -> int:
    processed = 0
    with session_scope() as session:
        documents = list(
            session.scalars(
                select(Document)
                .where(Document.status == DocumentStatus.PARSED)
                .order_by(Document.created_at.asc())
                .limit(limit)
            )
        )
        for document in documents:
            logger.info("worker.claims.processing", extra={"document_id": str(document.id)})
            claim_service.extract_claims_for_document(session, document_id=str(document.id))
            processed += 1
    return processed
