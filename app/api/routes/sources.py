from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.api.deps import get_db_session
from app.schemas.source import SourceCreate, SourceFileUploadResponse, SourceRead
from services.admissions.source_ingestion_service import source_ingestion_service
from services.admissions.source_service import source_service


router = APIRouter()


@router.get("", response_model=list[SourceRead])
def list_sources(session: Session = Depends(get_db_session)) -> list[SourceRead]:
    return [SourceRead.model_validate(item) for item in source_service.list_sources(session)]


@router.post("", response_model=SourceRead, status_code=status.HTTP_201_CREATED)
def create_source(payload: SourceCreate, session: Session = Depends(get_db_session)) -> SourceRead:
    source = source_service.create_source(
        session,
        name=payload.name,
        base_url=payload.base_url,
        source_tier=payload.source_tier,
        source_category=payload.source_category,
        organization_name=payload.organization_name,
        is_official=payload.is_official,
        allow_crawl=payload.allow_crawl,
        freshness_days=payload.freshness_days,
        crawl_policy=payload.crawl_policy,
    )
    session.commit()
    session.refresh(source)
    return SourceRead.model_validate(source)


@router.get("/{source_id}", response_model=SourceRead)
def get_source(source_id: str, session: Session = Depends(get_db_session)) -> SourceRead:
    source = source_service.get_source(session, source_id)
    if source is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Source not found")
    return SourceRead.model_validate(source)


@router.post("/{source_id}/files", response_model=SourceFileUploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_source_file(
    source_id: str,
    file: UploadFile = File(...),
    source_url: str | None = Form(default=None),
    session: Session = Depends(get_db_session),
) -> SourceFileUploadResponse:
    try:
        source, job = await source_ingestion_service.upload_source_file(
            session,
            source_id=source_id,
            upload=file,
            source_url=source_url,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    session.commit()
    return SourceFileUploadResponse(
        source_id=str(source.id),
        ingestion_job_id=str(job.id),
        file_object_id=str(job.file_object_id) if job.file_object_id else None,
        status=job.status.value,
    )
