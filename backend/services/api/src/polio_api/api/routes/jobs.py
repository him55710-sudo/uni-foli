from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from polio_api.api.deps import get_current_user, get_db
from polio_api.core.config import get_settings
from polio_api.db.models.user import User
from polio_api.schemas.async_job import AsyncJobRead
from polio_api.services.async_job_service import (
    dispatch_job_if_enabled,
    get_async_job,
    get_latest_job_for_resource,
    list_project_jobs,
    process_async_job,
    retry_async_job,
)
from polio_api.services.project_service import get_project

router = APIRouter()


def _authorize_job_access(db: Session, job, current_user: User) -> None:
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found.")
    if job.project_id is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied. Job is not bound to a project.")
    project = get_project(db, job.project_id, owner_user_id=current_user.id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found.")


@router.get("", response_model=list[AsyncJobRead])
def list_jobs_route(
    project_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[AsyncJobRead]:
    project = get_project(db, project_id, owner_user_id=current_user.id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found.")
    return [AsyncJobRead.model_validate(item) for item in list_project_jobs(db, project_id)]


@router.get("/resource/{resource_type}/{resource_id}", response_model=AsyncJobRead)
def get_latest_resource_job_route(
    resource_type: str,
    resource_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AsyncJobRead:
    job = get_latest_job_for_resource(db, resource_type=resource_type, resource_id=resource_id)
    _authorize_job_access(db, job, current_user)
    return AsyncJobRead.model_validate(job)


@router.get("/{job_id}", response_model=AsyncJobRead)
def get_job_route(
    job_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AsyncJobRead:
    job = get_async_job(db, job_id)
    _authorize_job_access(db, job, current_user)
    return AsyncJobRead.model_validate(job)


@router.post("/{job_id}/retry", response_model=AsyncJobRead)
def retry_job_route(
    job_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AsyncJobRead:
    job = get_async_job(db, job_id)
    _authorize_job_access(db, job, current_user)
    retried = retry_async_job(db, job_id)
    if retried is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found.")
    dispatch_job_if_enabled(retried.id)
    return AsyncJobRead.model_validate(retried)


@router.post("/{job_id}/process", response_model=AsyncJobRead)
def process_job_route(
    job_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AsyncJobRead:
    settings = get_settings()
    if not settings.allow_inline_job_processing:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inline job processing is disabled. Use the worker instead.",
        )
    job = get_async_job(db, job_id)
    _authorize_job_access(db, job, current_user)
    processed = process_async_job(db, job_id)
    if processed is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found.")
    return AsyncJobRead.model_validate(processed)
