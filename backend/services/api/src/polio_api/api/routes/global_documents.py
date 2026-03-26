from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from sqlalchemy.orm import Session

from polio_api.api.deps import get_current_user, get_db
from polio_api.db.models.user import User
from polio_api.schemas.document import ParsedDocumentRead
from polio_api.schemas.project import ProjectCreate
from polio_api.services.document_service import (
    IN_PROGRESS_DOCUMENT_STATUSES,
    ensure_document_placeholder,
    enqueue_document_parse,
    get_document,
    mark_document_processing,
    parse_document_by_id,
    upload_supports_ingest,
)
from polio_api.services.project_service import create_project, get_project
from polio_api.services.upload_service import store_upload

router = APIRouter()


@router.post("/upload", response_model=ParsedDocumentRead, status_code=status.HTTP_201_CREATED)
async def upload_global_document(
    file: UploadFile = File(...),
    project_id: str | None = Form(default=None),
    title: str | None = Form(default=None),
    description: str | None = Form(default=None),
    target_major: str | None = Form(default=None),
    target_university: str | None = Form(default=None),
    auto_parse: bool = Form(default=False),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ParsedDocumentRead:
    active_project_id = project_id
    if active_project_id:
        project = get_project(db, active_project_id, owner_user_id=current_user.id)
        if project is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found.")
    else:
        filename_stem = Path(file.filename or "document").stem
        project = create_project(
            db,
            ProjectCreate(
                title=title or f"{filename_stem} intake",
                description=description or f"Document intake for {file.filename or 'upload'}",
                target_major=target_major,
                target_university=target_university,
            ),
            owner_user_id=current_user.id,
        )
        active_project_id = project.id

    upload = await store_upload(db, project_id=active_project_id, upload=file, auto_ingest=False)
    document = ensure_document_placeholder(db, upload)

    if auto_parse and upload_supports_ingest(upload):
        document = mark_document_processing(db, document, upload)
        enqueue_document_parse(document.id)
        db.refresh(document)

    return ParsedDocumentRead.model_validate(document)


@router.post("/{document_id}/parse", response_model=ParsedDocumentRead, status_code=status.HTTP_202_ACCEPTED)
def parse_global_document(
    document_id: str,
    wait_for_completion: bool = Query(default=False),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ParsedDocumentRead:
    document = get_document(db, document_id)
    if document is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found.")
    project = get_project(db, document.project_id, owner_user_id=current_user.id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found.")
    if document.upload_asset is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Upload asset not found.")

    if wait_for_completion:
        try:
            document = parse_document_by_id(db, document_id, force=True, prepared=False)
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
        except FileNotFoundError as exc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
        return ParsedDocumentRead.model_validate(document)

    if document.status in IN_PROGRESS_DOCUMENT_STATUSES:
        return ParsedDocumentRead.model_validate(document)

    if not upload_supports_ingest(document.upload_asset):
        try:
            document = parse_document_by_id(db, document_id, force=True, prepared=False)
        except ValueError:
            db.refresh(document)
        return ParsedDocumentRead.model_validate(document)

    document = mark_document_processing(db, document, document.upload_asset)
    enqueue_document_parse(document.id)
    db.refresh(document)
    return ParsedDocumentRead.model_validate(document)


@router.get("/{document_id}", response_model=ParsedDocumentRead)
def get_global_document_status(
    document_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ParsedDocumentRead:
    document = get_document(db, document_id)
    if document is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found.")
    project = get_project(db, document.project_id, owner_user_id=current_user.id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found.")
    return ParsedDocumentRead.model_validate(document)
