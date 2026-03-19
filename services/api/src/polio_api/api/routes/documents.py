from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from polio_api.api.deps import get_db
from polio_api.schemas.document import DocumentChunkRead, ParsedDocumentRead, ParsedDocumentSummary
from polio_api.schemas.draft import DraftFromDocumentCreate, DraftRead
from polio_api.services.document_service import (
    create_seed_draft_from_document,
    get_document,
    ingest_upload_asset,
    list_chunks_for_document,
    list_documents_for_project,
)
from polio_api.services.project_service import get_project
from polio_api.services.upload_service import get_upload

router = APIRouter()


@router.get("/{project_id}/documents", response_model=list[ParsedDocumentSummary])
def list_documents_route(project_id: str, db: Session = Depends(get_db)) -> list[ParsedDocumentSummary]:
    project = get_project(db, project_id)
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found.")

    documents = list_documents_for_project(db, project_id)
    return [ParsedDocumentSummary.model_validate(item) for item in documents]


@router.get("/{project_id}/documents/{document_id}", response_model=ParsedDocumentRead)
def get_document_route(project_id: str, document_id: str, db: Session = Depends(get_db)) -> ParsedDocumentRead:
    document = get_document(db, document_id)
    if not document or document.project_id != project_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found.")
    return ParsedDocumentRead.model_validate(document)


@router.get("/{project_id}/documents/{document_id}/chunks", response_model=list[DocumentChunkRead])
def list_document_chunks_route(
    project_id: str,
    document_id: str,
    db: Session = Depends(get_db),
) -> list[DocumentChunkRead]:
    document = get_document(db, document_id)
    if not document or document.project_id != project_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found.")

    chunks = list_chunks_for_document(db, document_id)
    return [DocumentChunkRead.model_validate(item) for item in chunks]


@router.post(
    "/{project_id}/uploads/{upload_id}/ingest",
    response_model=ParsedDocumentRead,
    status_code=status.HTTP_201_CREATED,
)
def ingest_upload_route(project_id: str, upload_id: str, db: Session = Depends(get_db)) -> ParsedDocumentRead:
    upload = get_upload(db, upload_id)
    if not upload or upload.project_id != project_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Upload not found.")

    try:
        document = ingest_upload_asset(db, upload, force=True)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    return ParsedDocumentRead.model_validate(document)


@router.post(
    "/{project_id}/documents/{document_id}/drafts",
    response_model=DraftRead,
    status_code=status.HTTP_201_CREATED,
)
def create_draft_from_document_route(
    project_id: str,
    document_id: str,
    payload: DraftFromDocumentCreate,
    db: Session = Depends(get_db),
) -> DraftRead:
    document = get_document(db, document_id)
    if not document or document.project_id != project_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found.")

    draft = create_seed_draft_from_document(
        db,
        project_id=project_id,
        document=document,
        title=payload.title,
        include_excerpt_limit=payload.include_excerpt_limit,
    )
    return DraftRead.model_validate(draft)
