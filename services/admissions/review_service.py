from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from db.models.audit import PolicyFlag, ReviewTask
from db.models.content import Claim, Document
from domain.enums import ClaimStatus, ClaimType, DocumentStatus, ReviewTaskStatus, ReviewTaskType
from services.admissions.retrieval_index_service import retrieval_index_service
from services.admissions.utils import ensure_uuid


ALLOWED_REVIEW_TRANSITIONS: dict[ClaimStatus, set[ClaimStatus]] = {
    ClaimStatus.PENDING_REVIEW: {
        ClaimStatus.APPROVED,
        ClaimStatus.REJECTED,
        ClaimStatus.NEEDS_REVISION,
        ClaimStatus.SUPERSEDED,
    },
    ClaimStatus.NEEDS_REVISION: {
        ClaimStatus.APPROVED,
        ClaimStatus.REJECTED,
        ClaimStatus.SUPERSEDED,
        ClaimStatus.NEEDS_REVISION,
    },
    ClaimStatus.APPROVED: {
        ClaimStatus.SUPERSEDED,
        ClaimStatus.NEEDS_REVISION,
    },
    ClaimStatus.REJECTED: {
        ClaimStatus.NEEDS_REVISION,
        ClaimStatus.APPROVED,
    },
    ClaimStatus.SUPERSEDED: set(),
}


class ReviewService:
    def list_review_tasks(self, session: Session, *, tenant_id=None) -> list[ReviewTask]:
        stmt = (
            select(ReviewTask)
            .where(ReviewTask.deleted_at.is_(None))
            .order_by(ReviewTask.priority.asc(), ReviewTask.created_at.desc())
        )
        if tenant_id is not None:
            stmt = stmt.where(ReviewTask.tenant_id == ensure_uuid(tenant_id))
        return list(session.scalars(stmt))

    def create_review_task(
        self,
        session: Session,
        *,
        task_type: ReviewTaskType,
        target_kind: str,
        target_id,
        rationale: str,
        priority: int = 5,
        assigned_to: str | None = None,
        tenant_id=None,
        metadata_json: dict[str, object] | None = None,
    ) -> ReviewTask:
        task = ReviewTask(
            tenant_id=ensure_uuid(tenant_id),
            task_type=task_type,
            target_kind=target_kind,
            target_id=ensure_uuid(target_id),
            rationale=rationale,
            priority=priority,
            assigned_to=assigned_to,
            metadata_json=metadata_json or {},
        )
        session.add(task)
        session.flush()
        session.refresh(task)
        return task

    def update_review_task(
        self,
        session: Session,
        *,
        review_task_id: str,
        status: ReviewTaskStatus,
        resolution_note: str | None,
        assigned_to: str | None,
    ) -> ReviewTask | None:
        task = session.get(ReviewTask, ensure_uuid(review_task_id))
        if task is None:
            return None
        task.status = status
        if resolution_note is not None:
            task.resolution_note = resolution_note
        if assigned_to is not None:
            task.assigned_to = assigned_to
        session.flush()
        session.refresh(task)
        return task

    def list_policy_flags(self, session: Session, *, tenant_id=None) -> list[PolicyFlag]:
        stmt = select(PolicyFlag).where(PolicyFlag.deleted_at.is_(None)).order_by(PolicyFlag.created_at.desc())
        if tenant_id is not None:
            stmt = stmt.where(PolicyFlag.tenant_id == ensure_uuid(tenant_id))
        return list(session.scalars(stmt))

    def list_claims_for_review(
        self,
        session: Session,
        *,
        statuses: tuple[ClaimStatus, ...] = (ClaimStatus.PENDING_REVIEW, ClaimStatus.NEEDS_REVISION),
    ) -> list[Claim]:
        stmt = (
            select(Claim)
            .where(Claim.status.in_(statuses))
            .options(selectinload(Claim.evidence_items))
            .order_by(Claim.created_at.desc())
        )
        return list(session.scalars(stmt))

    def review_claim(
        self,
        session: Session,
        *,
        claim_id: str,
        status: ClaimStatus,
        reviewer_id: str | None,
        reviewer_note: str | None,
        evidence_quality_score: float | None,
        university_exception_note: str | None,
        unsafe_flagged: bool | None,
        overclaim_flagged: bool | None,
        claim_type: ClaimType | None,
    ) -> Claim | None:
        claim = session.get(Claim, ensure_uuid(claim_id))
        if claim is None:
            return None
        if status not in ALLOWED_REVIEW_TRANSITIONS.get(claim.status, set()) and status != claim.status:
            raise ValueError(f"Claim status transition {claim.status.value} -> {status.value} is not allowed.")

        claim.status = status
        claim.reviewer_id = reviewer_id or claim.reviewer_id
        claim.reviewed_at = datetime.now(UTC)
        if reviewer_note is not None:
            claim.reviewer_note = reviewer_note
        if evidence_quality_score is not None:
            claim.evidence_quality_score = evidence_quality_score
        if university_exception_note is not None:
            claim.university_exception_note = university_exception_note
        if unsafe_flagged is not None:
            claim.unsafe_flagged = unsafe_flagged
        if overclaim_flagged is not None:
            claim.overclaim_flagged = overclaim_flagged
        if claim_type is not None:
            claim.claim_type = claim_type
            claim.is_direct_rule = claim_type in {
                ClaimType.DOCUMENT_RULE,
                ClaimType.POLICY_STATEMENT,
                ClaimType.ELIGIBILITY_CONDITION,
                ClaimType.CAUTION_RULE,
            }
        retrieval_index_service.upsert_claim_record(session, claim=claim)
        session.flush()
        session.refresh(claim)
        return claim

    def update_claim_status(self, session: Session, *, claim_id: str, status: ClaimStatus) -> Claim | None:
        return self.review_claim(
            session,
            claim_id=claim_id,
            status=status,
            reviewer_id=None,
            reviewer_note=None,
            evidence_quality_score=None,
            university_exception_note=None,
            unsafe_flagged=None,
            overclaim_flagged=None,
            claim_type=None,
        )

    def bulk_mark_low_confidence_claims(
        self,
        session: Session,
        *,
        threshold: float,
        limit: int,
        reviewer_id: str | None,
        reviewer_note: str | None,
    ) -> list[Claim]:
        stmt = (
            select(Claim)
            .where(Claim.status == ClaimStatus.PENDING_REVIEW)
            .where((Claim.confidence_score < threshold) | (Claim.evidence_quality_score < threshold))
            .order_by(Claim.confidence_score.asc(), Claim.created_at.asc())
            .limit(limit)
        )
        claims = list(session.scalars(stmt))
        for claim in claims:
            claim.status = ClaimStatus.NEEDS_REVISION
            claim.reviewer_id = reviewer_id or claim.reviewer_id
            claim.reviewer_note = reviewer_note or "Marked for revision due to low confidence or weak evidence."
            claim.reviewed_at = datetime.now(UTC)
            claim.overclaim_flagged = True
            retrieval_index_service.upsert_claim_record(session, claim=claim)
        session.flush()
        return claims

    def update_document_trust(self, session: Session, *, document_id: str, low_trust: bool, note: str | None) -> Document | None:
        document = session.get(Document, ensure_uuid(document_id))
        if document is None:
            return None
        document.status = DocumentStatus.LOW_TRUST if low_trust else DocumentStatus.NORMALIZED
        document.quality_score = min(document.quality_score, 0.35) if low_trust else max(document.quality_score, 0.5)
        if low_trust:
            self.create_review_task(
                session,
                task_type=ReviewTaskType.DOCUMENT_TRUST_REVIEW,
                target_kind="document",
                target_id=document.id,
                rationale=note or "Document marked as low trust for admin review.",
                priority=1,
            )
        session.flush()
        session.refresh(document)
        return document


review_service = ReviewService()
