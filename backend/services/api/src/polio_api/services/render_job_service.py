from __future__ import annotations

import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from polio_api.core.config import get_settings
from polio_api.db.models.draft import Draft
from polio_api.db.models.project import Project
from polio_api.db.models.render_job import RenderJob
from polio_api.schemas.render_job import RenderFormatInfo, RenderJobCreate
from polio_api.services.project_service import list_project_discussion_log
from polio_domain.enums import AsyncJobType
from polio_domain.enums import RenderFormat, RenderStatus
from polio_render.dispatcher import dispatch_render
from polio_render.models import RenderBuildContext

logger = logging.getLogger("polio.api.render_jobs")


def get_render_format_catalog() -> list[RenderFormatInfo]:
    return [
        RenderFormatInfo(
            format=RenderFormat.PDF,
            implementation_level="reportlab",
            description="Creates a styled PDF document with ReportLab.",
        ),
        RenderFormatInfo(
            format=RenderFormat.PPTX,
            implementation_level="python-pptx",
            description="Creates a real PowerPoint presentation with section-based slides.",
        ),
        RenderFormatInfo(
            format=RenderFormat.HWPX,
            implementation_level="template",
            description="Creates an HWPX package by filling a bundled skeleton template.",
        ),
    ]


def create_render_job(db: Session, payload: RenderJobCreate) -> RenderJob | None:
    project = db.get(Project, payload.project_id)
    draft = db.get(Draft, payload.draft_id)

    if not project or not draft or draft.project_id != project.id:
        return None

    job = RenderJob(
        project_id=payload.project_id,
        draft_id=payload.draft_id,
        render_format=payload.render_format.value,
        requested_by=payload.requested_by,
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    from polio_api.services.async_job_service import create_async_job

    create_async_job(
        db,
        job_type=AsyncJobType.RENDER.value,
        resource_type="render_job",
        resource_id=job.id,
        project_id=job.project_id,
        payload={"render_job_id": job.id},
    )
    return job


def list_render_jobs_for_owner(db: Session, owner_user_id: str) -> list[RenderJob]:
    stmt = (
        select(RenderJob)
        .join(Project, Project.id == RenderJob.project_id)
        .where(Project.owner_user_id == owner_user_id)
        .order_by(RenderJob.created_at.desc())
    )
    return list(db.scalars(stmt))


def get_render_job(db: Session, job_id: str) -> RenderJob | None:
    return db.get(RenderJob, job_id)


def get_render_job_for_owner(db: Session, job_id: str, owner_user_id: str) -> RenderJob | None:
    stmt = (
        select(RenderJob)
        .join(Project, Project.id == RenderJob.project_id)
        .where(RenderJob.id == job_id, Project.owner_user_id == owner_user_id)
    )
    return db.scalar(stmt)


def get_next_queued_render_job(db: Session) -> RenderJob | None:
    stmt = (
        select(RenderJob)
        .where(RenderJob.status == RenderStatus.QUEUED.value)
        .order_by(RenderJob.created_at.asc())
    )
    return db.scalars(stmt).first()


def process_render_job(db: Session, job_id: str) -> RenderJob | None:
    job = db.get(RenderJob, job_id)
    if not job:
        return None

    job.status = RenderStatus.PROCESSING.value
    db.commit()
    db.refresh(job)

    try:
        from polio_api.db.models.workshop import DraftArtifact
        draft = db.get(Draft, job.draft_id)
        project = db.get(Project, job.project_id)
        if not draft or not project:
            raise ValueError("Project or draft missing while processing render job.")

        visual_specs = []
        math_expressions = []
        
        # Check if this draft is linked to a workshop session for visuals
        # Currently, workshop produces artifacts directly, but the render job path might refer to a Draft model.
        # Since 'visual_specs' exist in 'DraftArtifact', we filter them if this draft was derived from a workshop.
        stmt = select(DraftArtifact).where(DraftArtifact.id == draft.id).limit(1)
        artifact = db.execute(stmt).scalars().first()
        
        if artifact:
            # Filter ONLY approved items
            visual_specs = [v for v in (artifact.visual_specs or []) if v.get("approval_status") == "approved"]
            math_expressions = [m for m in (artifact.math_expressions or []) if m.get("approval_status") == "approved"]

        context = RenderBuildContext(
            project_id=project.id,
            project_title=project.title,
            draft_id=draft.id,
            draft_title=draft.title,
            render_format=RenderFormat(job.render_format),
            content_markdown=draft.content_markdown,
            requested_by=job.requested_by,
            job_id=job.id,
            visual_specs=visual_specs,
            math_expressions=math_expressions,
            authenticity_log_lines=list_project_discussion_log(project),
        )
        artifact = dispatch_render(context)

        job.status = RenderStatus.COMPLETED.value
        job.output_path = artifact.relative_path
        job.result_message = artifact.message
    except Exception as exc:  # noqa: BLE001
        logger.exception("Render job failed: %s", job.id)
        job.status = RenderStatus.FAILED.value
        job.result_message = "Render job failed. Review the draft content and retry."

    db.commit()
    db.refresh(job)
    return job


def build_render_job_payload(db: Session, job: RenderJob) -> dict[str, object]:
    from polio_api.services.async_job_service import get_latest_job_for_resource

    settings = get_settings()
    async_job = get_latest_job_for_resource(db, resource_type="render_job", resource_id=job.id)
    return {
        "id": job.id,
        "project_id": job.project_id,
        "draft_id": job.draft_id,
        "render_format": job.render_format,
        "status": job.status,
        "download_url": f"{settings.api_prefix}/render-jobs/{job.id}/download" if job.output_path else None,
        "result_message": job.result_message,
        "requested_by": job.requested_by,
        "async_job_id": async_job.id if async_job else None,
        "async_job_status": async_job.status if async_job else None,
        "retry_count": async_job.retry_count if async_job else 0,
        "max_retries": async_job.max_retries if async_job else 0,
        "failure_reason": async_job.failure_reason if async_job else None,
        "dead_lettered_at": async_job.dead_lettered_at if async_job else None,
        "created_at": job.created_at,
        "updated_at": job.updated_at,
    }
