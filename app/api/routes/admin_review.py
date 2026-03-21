from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_db_session
from app.schemas.claim import ClaimRead, ClaimStatusUpdate
from app.schemas.review import DocumentTrustUpdate, PolicyFlagRead, ReviewTaskCreate, ReviewTaskRead, ReviewTaskUpdate
from app.schemas.document import DocumentRead
from services.admissions.review_service import review_service


router = APIRouter()


@router.get("/review-tasks", response_model=list[ReviewTaskRead])
def list_review_tasks(session: Session = Depends(get_db_session)) -> list[ReviewTaskRead]:
    return [ReviewTaskRead.model_validate(item) for item in review_service.list_review_tasks(session)]


@router.post("/review-tasks", response_model=ReviewTaskRead, status_code=status.HTTP_201_CREATED)
def create_review_task(payload: ReviewTaskCreate, session: Session = Depends(get_db_session)) -> ReviewTaskRead:
    task = review_service.create_review_task(
        session,
        task_type=payload.task_type,
        target_kind=payload.target_kind,
        target_id=payload.target_id,
        rationale=payload.rationale,
        priority=payload.priority,
        assigned_to=payload.assigned_to,
        metadata_json=payload.metadata_json,
    )
    session.commit()
    return ReviewTaskRead.model_validate(task)


@router.patch("/review-tasks/{review_task_id}", response_model=ReviewTaskRead)
def update_review_task(
    review_task_id: str,
    payload: ReviewTaskUpdate,
    session: Session = Depends(get_db_session),
) -> ReviewTaskRead:
    task = review_service.update_review_task(
        session,
        review_task_id=review_task_id,
        status=payload.status,
        resolution_note=payload.resolution_note,
        assigned_to=payload.assigned_to,
    )
    if task is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Review task not found")
    session.commit()
    return ReviewTaskRead.model_validate(task)


@router.get("/claims/pending", response_model=list[ClaimRead])
def list_claims_for_review(session: Session = Depends(get_db_session)) -> list[ClaimRead]:
    return [ClaimRead.model_validate(item) for item in review_service.list_claims_for_review(session)]


@router.patch("/claims/{claim_id}", response_model=ClaimRead)
def update_claim_status(
    claim_id: str,
    payload: ClaimStatusUpdate,
    session: Session = Depends(get_db_session),
) -> ClaimRead:
    claim = review_service.update_claim_status(session, claim_id=claim_id, status=payload.status)
    if claim is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Claim not found")
    session.commit()
    return ClaimRead.model_validate(claim)


@router.patch("/documents/{document_id}/trust", response_model=DocumentRead)
def update_document_trust(
    document_id: str,
    payload: DocumentTrustUpdate,
    session: Session = Depends(get_db_session),
) -> DocumentRead:
    document = review_service.update_document_trust(
        session,
        document_id=document_id,
        low_trust=payload.low_trust,
        note=payload.note,
    )
    if document is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    session.commit()
    return DocumentRead.model_validate(document)


@router.get("/policy-flags", response_model=list[PolicyFlagRead])
def list_policy_flags(session: Session = Depends(get_db_session)) -> list[PolicyFlagRead]:
    return [PolicyFlagRead.model_validate(item) for item in review_service.list_policy_flags(session)]
