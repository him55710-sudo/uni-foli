from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_db_session
from app.schemas.ingestion_job import IngestionJobCreate, IngestionJobRead
from services.admissions.ingestion_job_service import ingestion_job_service
from services.admissions.ingestion_pipeline_service import ingestion_pipeline_service


router = APIRouter()


@router.get("", response_model=list[IngestionJobRead])
def list_ingestion_jobs(session: Session = Depends(get_db_session)) -> list[IngestionJobRead]:
    return [IngestionJobRead.model_validate(item) for item in ingestion_job_service.list_jobs(session)]


@router.post("", response_model=IngestionJobRead, status_code=status.HTTP_201_CREATED)
def create_ingestion_job(payload: IngestionJobCreate, session: Session = Depends(get_db_session)) -> IngestionJobRead:
    job = ingestion_job_service.create_job(
        session,
        input_locator=payload.input_locator,
        source_id=payload.source_id,
        source_crawl_job_id=payload.source_crawl_job_id,
        file_object_id=payload.file_object_id,
        document_id=payload.document_id,
        pipeline_stage=payload.pipeline_stage,
        trace_json=payload.trace_json,
    )
    session.commit()
    session.refresh(job)
    return IngestionJobRead.model_validate(job)


@router.get("/{job_id}", response_model=IngestionJobRead)
def get_ingestion_job(job_id: str, session: Session = Depends(get_db_session)) -> IngestionJobRead:
    job = ingestion_job_service.get_job(session, job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ingestion job not found")
    return IngestionJobRead.model_validate(job)


@router.post("/{job_id}/run", response_model=IngestionJobRead)
def run_ingestion_job(job_id: str, session: Session = Depends(get_db_session)) -> IngestionJobRead:
    job = ingestion_job_service.get_job(session, job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ingestion job not found")
    processed = ingestion_pipeline_service.process_ingestion_job(session, job)
    session.commit()
    return IngestionJobRead.model_validate(processed)
