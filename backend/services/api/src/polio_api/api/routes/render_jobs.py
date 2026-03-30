from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from polio_api.api.deps import get_current_user, get_db
from polio_api.core.config import get_settings
from polio_api.core.rate_limit import rate_limit
from polio_api.core.security import ensure_resolved_within_base
from polio_api.db.models.user import User
from polio_api.schemas.render_job import RenderFormatInfo, RenderJobCreate, RenderJobRead
from polio_api.services.async_job_service import get_latest_job_for_resource, process_async_job
from polio_api.services.project_service import get_project
from polio_api.services.render_job_service import (
    build_render_job_payload,
    create_render_job,
    get_render_format_catalog,
    get_render_job_for_owner,
    list_render_jobs_for_owner,
)
from polio_shared.paths import get_export_root, resolve_project_path

router = APIRouter(prefix="/render-jobs")


def _resolve_render_output_path(output_path: str) -> Path:
    try:
        resolved = ensure_resolved_within_base(resolve_project_path(output_path), get_export_root())
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Rendered artifact not found.") from exc
    if not resolved.exists() or not resolved.is_file():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Rendered artifact not found.")
    return resolved


@router.get("/formats", response_model=list[RenderFormatInfo])
def list_render_formats_route() -> list[RenderFormatInfo]:
    return get_render_format_catalog()


@router.post("", response_model=RenderJobRead, status_code=status.HTTP_201_CREATED)
def create_render_job_route(
    payload: RenderJobCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: None = Depends(rate_limit(bucket="render_job_create", limit=10, window_seconds=300)),
) -> RenderJobRead:
    project = get_project(db, payload.project_id, owner_user_id=current_user.id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project or draft not found.")
    job = create_render_job(db, payload)
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project or draft not found.")
    return RenderJobRead.model_validate(build_render_job_payload(db, job))


@router.get("", response_model=list[RenderJobRead])
def list_render_jobs_route(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[RenderJobRead]:
    return [
        RenderJobRead.model_validate(build_render_job_payload(db, item))
        for item in list_render_jobs_for_owner(db, current_user.id)
    ]


@router.get("/{job_id}", response_model=RenderJobRead)
def get_render_job_route(
    job_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> RenderJobRead:
    job = get_render_job_for_owner(db, job_id, current_user.id)
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Render job not found.")
    return RenderJobRead.model_validate(build_render_job_payload(db, job))


@router.get("/{job_id}/download")
def download_render_job_route(
    job_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> FileResponse:
    job = get_render_job_for_owner(db, job_id, current_user.id)
    if not job or not job.output_path:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Rendered artifact not found.")
    output_path = _resolve_render_output_path(job.output_path)
    return FileResponse(path=output_path, filename=output_path.name)


@router.post("/{job_id}/process", response_model=RenderJobRead)
def process_render_job_route(
    job_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: None = Depends(rate_limit(bucket="render_job_process", limit=20, window_seconds=300)),
) -> RenderJobRead:
    settings = get_settings()
    if not settings.allow_inline_render or not settings.allow_inline_job_processing:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inline render is disabled. Use the worker instead.",
        )

    job = get_render_job_for_owner(db, job_id, current_user.id)
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Render job not found.")

    async_job = get_latest_job_for_resource(db, resource_type="render_job", resource_id=job_id)
    if async_job is not None:
        process_async_job(db, async_job.id)
    job = get_render_job_for_owner(db, job_id, current_user.id)
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Render job not found.")
    return RenderJobRead.model_validate(build_render_job_payload(db, job))
