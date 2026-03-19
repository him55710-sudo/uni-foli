from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from polio_api.api.deps import get_db
from polio_api.core.config import get_settings
from polio_api.schemas.render_job import RenderFormatInfo, RenderJobCreate, RenderJobRead
from polio_api.services.render_job_service import (
    create_render_job,
    get_render_format_catalog,
    get_render_job,
    list_render_jobs,
    process_render_job,
)

router = APIRouter(prefix="/render-jobs")


@router.get("/formats", response_model=list[RenderFormatInfo])
def list_render_formats_route() -> list[RenderFormatInfo]:
    return get_render_format_catalog()


@router.post("", response_model=RenderJobRead, status_code=status.HTTP_201_CREATED)
def create_render_job_route(payload: RenderJobCreate, db: Session = Depends(get_db)) -> RenderJobRead:
    job = create_render_job(db, payload)
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project or draft not found.")
    return RenderJobRead.model_validate(job)


@router.get("", response_model=list[RenderJobRead])
def list_render_jobs_route(db: Session = Depends(get_db)) -> list[RenderJobRead]:
    return [RenderJobRead.model_validate(item) for item in list_render_jobs(db)]


@router.get("/{job_id}", response_model=RenderJobRead)
def get_render_job_route(job_id: str, db: Session = Depends(get_db)) -> RenderJobRead:
    job = get_render_job(db, job_id)
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Render job not found.")
    return RenderJobRead.model_validate(job)


@router.post("/{job_id}/process", response_model=RenderJobRead)
def process_render_job_route(job_id: str, db: Session = Depends(get_db)) -> RenderJobRead:
    settings = get_settings()
    if not settings.allow_inline_render:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inline render is disabled. Use the worker instead.",
        )

    job = process_render_job(db, job_id)
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Render job not found.")
    return RenderJobRead.model_validate(job)
