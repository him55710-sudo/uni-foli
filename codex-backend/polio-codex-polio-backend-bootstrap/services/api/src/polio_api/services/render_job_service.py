from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from polio_api.db.models.draft import Draft
from polio_api.db.models.project import Project
from polio_api.db.models.render_job import RenderJob
from polio_api.schemas.render_job import RenderFormatInfo, RenderJobCreate
from polio_api.services.project_service import list_project_discussion_log
from polio_domain.enums import RenderFormat, RenderStatus
from polio_render.dispatcher import dispatch_render
from polio_render.models import RenderBuildContext


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
    return job


def list_render_jobs(db: Session) -> list[RenderJob]:
    return list(db.scalars(select(RenderJob).order_by(RenderJob.created_at.desc())))


def get_render_job(db: Session, job_id: str) -> RenderJob | None:
    return db.get(RenderJob, job_id)


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
        draft = db.get(Draft, job.draft_id)
        project = db.get(Project, job.project_id)
        if not draft or not project:
            raise ValueError("Project or draft missing while processing render job.")

        context = RenderBuildContext(
            project_id=project.id,
            project_title=project.title,
            draft_id=draft.id,
            draft_title=draft.title,
            render_format=RenderFormat(job.render_format),
            content_markdown=draft.content_markdown,
            requested_by=job.requested_by,
            job_id=job.id,
            authenticity_log_lines=list_project_discussion_log(project),
        )
        artifact = dispatch_render(context)

        job.status = RenderStatus.COMPLETED.value
        job.output_path = artifact.relative_path
        job.result_message = artifact.message
    except Exception as exc:  # noqa: BLE001
        job.status = RenderStatus.FAILED.value
        job.result_message = str(exc)

    db.commit()
    db.refresh(job)
    return job
