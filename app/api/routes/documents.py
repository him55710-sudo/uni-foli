from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_db_session
from app.schemas.claim import ClaimRead
from app.schemas.document import DocumentChunkRead, DocumentRead, ParsedBlockRead
from services.admissions.claim_service import claim_service
from services.admissions.document_service import document_service


router = APIRouter()


@router.get("", response_model=list[DocumentRead])
def list_documents(session: Session = Depends(get_db_session)) -> list[DocumentRead]:
    return [DocumentRead.model_validate(item) for item in document_service.list_documents(session)]


@router.get("/{document_id}", response_model=DocumentRead)
def get_document(document_id: str, session: Session = Depends(get_db_session)) -> DocumentRead:
    document = document_service.get_document(session, document_id)
    if document is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    return DocumentRead.model_validate(document)


@router.get("/{document_id}/blocks", response_model=list[ParsedBlockRead])
def list_document_blocks(document_id: str, session: Session = Depends(get_db_session)) -> list[ParsedBlockRead]:
    document = document_service.get_document(session, document_id)
    if document is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    return [ParsedBlockRead.model_validate(item) for item in document_service.list_document_blocks(session, document_id=document_id)]


@router.get("/{document_id}/chunks", response_model=list[DocumentChunkRead])
def list_document_chunks(document_id: str, session: Session = Depends(get_db_session)) -> list[DocumentChunkRead]:
    document = document_service.get_document(session, document_id)
    if document is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    return [DocumentChunkRead.model_validate(item) for item in document_service.list_document_chunks(session, document_id=document_id)]


@router.get("/{document_id}/claims", response_model=list[ClaimRead])
def list_document_claims(document_id: str, session: Session = Depends(get_db_session)) -> list[ClaimRead]:
    document = document_service.get_document(session, document_id)
    if document is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    return [ClaimRead.model_validate(item) for item in claim_service.list_claims_for_document(session, document_id=document_id)]
