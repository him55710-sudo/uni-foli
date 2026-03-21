from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_db_session
from app.schemas.claim import ClaimExtractionRequestBody, ClaimRead
from app.schemas.extraction import ExtractionJobRead
from services.admissions.claim_service import claim_service


router = APIRouter()


@router.get("", response_model=list[ClaimRead])
def list_claims(session: Session = Depends(get_db_session)) -> list[ClaimRead]:
    return [ClaimRead.model_validate(item) for item in claim_service.list_claims(session)]


@router.get("/{claim_id}", response_model=ClaimRead)
def get_claim(claim_id: str, session: Session = Depends(get_db_session)) -> ClaimRead:
    claim = claim_service.get_claim(session, claim_id)
    if claim is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Claim not found")
    return ClaimRead.model_validate(claim)


@router.post("/extract", response_model=ExtractionJobRead, status_code=status.HTTP_202_ACCEPTED)
def extract_claims(payload: ClaimExtractionRequestBody, session: Session = Depends(get_db_session)) -> ExtractionJobRead:
    job = claim_service.extract_claims_for_document(
        session,
        document_id=payload.document_id,
        model_name=payload.model_name,
        chunk_indexes=payload.chunk_indexes,
        strategy_key=payload.strategy_key,
    )
    session.commit()
    return ExtractionJobRead.model_validate(job)
