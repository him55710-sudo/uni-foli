from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
import logging
from threading import Thread
from typing import Any

from sqlalchemy import Select, select, update
from sqlalchemy.orm import Session

from polio_api.core.config import get_settings
from polio_api.core.database import SessionLocal
from polio_api.core.security import sanitize_public_error
from polio_api.db.models.async_job import AsyncJob
from polio_api.db.models.diagnosis_run import DiagnosisRun
from polio_api.db.models.parsed_document import ParsedDocument
from polio_api.db.models.project import Project
from polio_api.db.models.render_job import RenderJob
from polio_api.db.models.research_document import ResearchDocument
from polio_api.services.diagnosis_report_service import (
    generate_consultant_report_artifact,
    get_latest_report_artifact_for_run,
    report_artifact_storage_key,
)
from polio_api.services.diagnosis_runtime_service import run_diagnosis_run
from polio_api.services.document_service import parse_document_by_id
from polio_api.services.render_job_service import process_render_job
from polio_api.services.research_service import ingest_research_document
from polio_domain.enums import AsyncJobStatus, AsyncJobType, RenderStatus

logger = logging.getLogger("polio.api.async_jobs")


def utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def create_async_job(
    db: Session,
    *,
    job_type: str,
    resource_type: str,
    resource_id: str,
    project_id: str | None,
    payload: dict[str, object] | None = None,
    max_retries: int | None = None,
) -> AsyncJob:
    settings = get_settings()
    job = AsyncJob(
        job_type=job_type,
        resource_type=resource_type,
        resource_id=resource_id,
        project_id=project_id,
        payload=payload or {},
        max_retries=max_retries if max_retries is not None else settings.async_job_max_retries,
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


def get_async_job(db: Session, job_id: str) -> AsyncJob | None:
    return db.get(AsyncJob, job_id)


def get_latest_job_for_resource(db: Session, *, resource_type: str, resource_id: str) -> AsyncJob | None:
    stmt = (
        select(AsyncJob)
        .where(AsyncJob.resource_type == resource_type, AsyncJob.resource_id == resource_id)
        .order_by(AsyncJob.created_at.desc())
    )
    return db.scalar(stmt)


def list_project_jobs(db: Session, project_id: str) -> list[AsyncJob]:
    stmt = (
        select(AsyncJob)
        .where(AsyncJob.project_id == project_id)
        .order_by(AsyncJob.created_at.desc())
    )
    return list(db.scalars(stmt))


def dispatch_job_if_enabled(job_id: str) -> None:
    settings = get_settings()
    if not settings.async_jobs_inline_dispatch:
        return
    if settings.serverless_runtime:
        logger.info("Skipping background thread dispatch for %s in serverless runtime.", job_id)
        return

    worker = Thread(
        target=run_async_job,
        args=(job_id,),
        daemon=True,
        name=f"polio-async-job-{job_id}",
    )
    worker.start()


def run_async_job(job_id: str) -> AsyncJob | None:
    with SessionLocal() as db:
        return process_async_job(db, job_id)


def _run_async_callable(func: Any, /, *args: Any, **kwargs: Any) -> Any:
    """Run an async callable from sync code, even if this thread already has a running loop."""
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(func(*args, **kwargs))

    result: dict[str, Any] = {}
    error: dict[str, BaseException] = {}

    def runner() -> None:
        try:
            result["value"] = asyncio.run(func(*args, **kwargs))
        except BaseException as exc:  # noqa: BLE001
            error["value"] = exc

    worker = Thread(target=runner, daemon=True, name="polio-inline-async")
    worker.start()
    worker.join()

    if "value" in error:
        raise error["value"]
    return result.get("value")


def process_async_job(db: Session, job_id: str) -> AsyncJob | None:
    _requeue_stale_jobs(db)
    job = _claim_job(db, job_id)
    if job is None:
        return db.get(AsyncJob, job_id)

    try:
        _dispatch_job(db, job)
        job.status = AsyncJobStatus.SUCCEEDED.value
        job.failure_reason = None
        job.completed_at = utc_now()
        db.add(job)
        db.commit()
        db.refresh(job)
        return job
    except Exception as exc:  # noqa: BLE001
        return _handle_job_failure(db, job=job, reason=str(exc))


def process_next_async_job(db: Session) -> AsyncJob | None:
    _requeue_stale_jobs(db)
    job = _claim_next_runnable_job(db)
    if job is None:
        return None
    try:
        _dispatch_job(db, job)
        job.status = AsyncJobStatus.SUCCEEDED.value
        job.failure_reason = None
        job.completed_at = utc_now()
        db.add(job)
        db.commit()
        db.refresh(job)
        return job
    except Exception as exc:  # noqa: BLE001
        return _handle_job_failure(db, job=job, reason=str(exc))


def retry_async_job(db: Session, job_id: str) -> AsyncJob | None:
    job = db.get(AsyncJob, job_id)
    if job is None:
        return None

    job.status = AsyncJobStatus.QUEUED.value
    job.failure_reason = None
    job.started_at = None
    job.completed_at = None
    job.dead_lettered_at = None
    job.next_attempt_at = utc_now()
    db.add(job)
    _reset_resource_for_retry(db, job)
    db.commit()
    db.refresh(job)
    return job


def _claim_job(db: Session, job_id: str) -> AsyncJob | None:
    now = utc_now()
    stmt = (
        update(AsyncJob)
        .where(
            AsyncJob.id == job_id,
            AsyncJob.status.in_([AsyncJobStatus.QUEUED.value, AsyncJobStatus.RETRYING.value]),
            AsyncJob.next_attempt_at <= now,
        )
        .values(
            status=AsyncJobStatus.RUNNING.value,
            started_at=now,
            completed_at=None,
            updated_at=now,
        )
        .execution_options(synchronize_session=False)
    )
    result = db.execute(stmt)
    if result.rowcount == 0:
        db.rollback()
        return None
    db.commit()
    job = db.get(AsyncJob, job_id)
    if job is not None:
        _mark_resource_running(db, job)
        db.commit()
        db.refresh(job)
    return job


def _claim_next_runnable_job(db: Session) -> AsyncJob | None:
    now = utc_now()
    stmt: Select[tuple[AsyncJob]] = (
        select(AsyncJob)
        .where(
            AsyncJob.status.in_([AsyncJobStatus.QUEUED.value, AsyncJobStatus.RETRYING.value]),
            AsyncJob.next_attempt_at <= now,
        )
        .order_by(AsyncJob.next_attempt_at.asc(), AsyncJob.created_at.asc())
    )
    for candidate in db.scalars(stmt):
        claimed = _claim_job(db, candidate.id)
        if claimed is not None:
            return claimed
    return None


def _requeue_stale_jobs(db: Session) -> None:
    settings = get_settings()
    stale_before = utc_now() - timedelta(seconds=settings.async_job_stale_after_seconds)
    stmt = select(AsyncJob).where(
        AsyncJob.status == AsyncJobStatus.RUNNING.value,
        AsyncJob.started_at.is_not(None),
        AsyncJob.started_at < stale_before,
    )
    stale_jobs = list(db.scalars(stmt))
    if not stale_jobs:
        return

    for job in stale_jobs:
        reason = "Job execution became stale and was returned to the retry queue."
        if job.retry_count >= job.max_retries:
            job.status = AsyncJobStatus.FAILED.value
            job.failure_reason = reason
            job.dead_lettered_at = utc_now()
            job.completed_at = utc_now()
            _mark_resource_failed(db, job, reason)
        else:
            job.schedule_retry(delay_seconds=settings.async_job_retry_delay_seconds, reason=reason)
            _mark_resource_retrying(db, job, reason)
        db.add(job)
    db.commit()


def _handle_job_failure(db: Session, *, job: AsyncJob, reason: str) -> AsyncJob:
    public_reason = _public_failure_reason(job, reason)
    logger.warning("Async job failed: %s %s -> %s", job.job_type, job.id, public_reason)
    settings = get_settings()
    if job.retry_count >= job.max_retries:
        job.status = AsyncJobStatus.FAILED.value
        job.failure_reason = public_reason
        job.completed_at = utc_now()
        job.dead_lettered_at = utc_now()
        _mark_resource_failed(db, job, public_reason)
    else:
        job.schedule_retry(delay_seconds=settings.async_job_retry_delay_seconds, reason=public_reason)
        _mark_resource_retrying(db, job, public_reason)
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


def _dispatch_job(db: Session, job: AsyncJob) -> None:
    payload = job.payload or {}
    if job.job_type == AsyncJobType.DOCUMENT_PARSE.value:
        parse_document_by_id(
            db,
            str(payload.get("document_id") or job.resource_id),
            force=True,
            prepared=bool(payload.get("prepared", False)),
        )
        return
    if job.job_type == AsyncJobType.RENDER.value:
        process_render_job(db, str(payload.get("render_job_id") or job.resource_id))
        return
    if job.job_type == AsyncJobType.RESEARCH_INGEST.value:
        ingest_research_document(
            db,
            document_id=str(payload.get("document_id") or job.resource_id),
            payload=dict(payload.get("research_payload") or {}),
        )
        return
    if job.job_type == AsyncJobType.DIAGNOSIS.value:
        completed_run = _run_async_callable(
            run_diagnosis_run,
            db,
            run_id=str(payload.get("run_id") or job.resource_id),
            project_id=str(payload.get("project_id") or job.project_id or ""),
            owner_user_id=str(payload.get("owner_user_id") or ""),
            fallback_target_university=_opt_str(payload.get("fallback_target_university")),
            fallback_target_major=_opt_str(payload.get("fallback_target_major")),
        )
        if isinstance(completed_run, DiagnosisRun):
            logger.info("Diagnosis completed. run_id=%s project_id=%s", completed_run.id, completed_run.project_id)
            try:
                decision = ensure_default_diagnosis_report_job(
                    db,
                    run=completed_run,
                    owner_user_id=_opt_str(payload.get("owner_user_id")),
                    fallback_target_university=_opt_str(payload.get("fallback_target_university")),
                    fallback_target_major=_opt_str(payload.get("fallback_target_major")),
                    report_mode=_opt_str(payload.get("auto_report_mode")) or "premium_10p",
                    include_appendix=bool(payload.get("auto_report_include_appendix", True)),
                    include_citations=bool(payload.get("auto_report_include_citations", True)),
                )
                logger.info(
                    "Diagnosis report auto-bootstrap evaluated. run_id=%s decision=%s",
                    completed_run.id,
                    decision,
                )
            except Exception:  # noqa: BLE001
                # Report bootstrap must not retroactively fail a successful diagnosis run.
                logger.exception(
                    "Diagnosis report auto-bootstrap failed after diagnosis completion. run_id=%s",
                    completed_run.id,
                )
        return
    if job.job_type == AsyncJobType.DIAGNOSIS_REPORT.value:
        run_id = str(payload.get("run_id") or job.resource_id)
        run = db.get(DiagnosisRun, run_id)
        if run is None:
            raise ValueError(f"Diagnosis run not found: {run_id}")
        project_id = str(payload.get("project_id") or run.project_id or "")
        project = db.get(Project, project_id)
        if project is None:
            raise ValueError(f"Project not found for report generation: {project_id}")
        report_mode = str(payload.get("report_mode") or "premium_10p")
        if report_mode not in {"compact", "premium_10p"}:
            report_mode = "premium_10p"
        artifact = _run_async_callable(
            generate_consultant_report_artifact,
            db,
            run=run,
            project=project,
            report_mode=report_mode,  # type: ignore[arg-type]
            template_id=None,
            include_appendix=bool(payload.get("include_appendix", True)),
            include_citations=bool(payload.get("include_citations", True)),
            force_regenerate=bool(payload.get("force_regenerate", False)),
        )
        if getattr(artifact, "status", None) == "FAILED":
            logger.warning(
                "Diagnosis report generation completed with failed artifact. run_id=%s project_id=%s mode=%s artifact_id=%s",
                run.id,
                run.project_id,
                report_mode,
                getattr(artifact, "id", None),
            )
        else:
            logger.info(
                "Diagnosis report generation succeeded. run_id=%s project_id=%s mode=%s artifact_id=%s",
                run.id,
                run.project_id,
                report_mode,
                getattr(artifact, "id", None),
            )
        return
    if job.job_type == AsyncJobType.INQUIRY_EMAIL.value:
        from polio_api.services.inquiry_service import send_inquiry_email_notification

        inquiry_id = str(payload.get("inquiry_id") or job.resource_id)
        send_inquiry_email_notification(db, inquiry_id)
        return
    raise ValueError(f"Unsupported async job type: {job.job_type}")


def ensure_default_diagnosis_report_job(
    db: Session,
    *,
    run: DiagnosisRun,
    owner_user_id: str | None,
    fallback_target_university: str | None,
    fallback_target_major: str | None,
    report_mode: str = "premium_10p",
    include_appendix: bool = True,
    include_citations: bool = True,
) -> str:
    return _queue_auto_diagnosis_report_job(
        db,
        run=run,
        owner_user_id=owner_user_id,
        fallback_target_university=fallback_target_university,
        fallback_target_major=fallback_target_major,
        report_mode=report_mode,
        include_appendix=include_appendix,
        include_citations=include_citations,
    )


def _queue_auto_diagnosis_report_job(
    db: Session,
    *,
    run: DiagnosisRun,
    owner_user_id: str | None,
    fallback_target_university: str | None,
    fallback_target_major: str | None,
    report_mode: str,
    include_appendix: bool,
    include_citations: bool,
) -> str:
    if run.status != "COMPLETED" or not run.result_payload:
        return "diagnosis_not_ready"

    if report_mode not in {"compact", "premium_10p"}:
        report_mode = "premium_10p"

    latest_artifact = get_latest_report_artifact_for_run(
        db,
        diagnosis_run_id=run.id,
        report_mode=report_mode,  # type: ignore[arg-type]
    )
    if (
        latest_artifact is not None
        and latest_artifact.status == "READY"
        and report_artifact_storage_key(latest_artifact)
    ):
        logger.info(
            "Diagnosis report bootstrap reused existing ready artifact. run_id=%s artifact_id=%s mode=%s",
            run.id,
            latest_artifact.id,
            report_mode,
        )
        return "reused_ready_artifact"
    if latest_artifact is not None and latest_artifact.status == "FAILED":
        logger.info(
            "Diagnosis report bootstrap skipped because latest artifact is failed. run_id=%s artifact_id=%s mode=%s",
            run.id,
            latest_artifact.id,
            report_mode,
        )
        return "already_failed_artifact"

    latest_job = get_latest_job_for_resource(
        db,
        resource_type="diagnosis_report",
        resource_id=run.id,
    )
    if latest_job is not None:
        if latest_job.status in {
            AsyncJobStatus.QUEUED.value,
            AsyncJobStatus.RUNNING.value,
            AsyncJobStatus.RETRYING.value,
        }:
            logger.info(
                "Diagnosis report bootstrap found active report job. run_id=%s job_id=%s status=%s",
                run.id,
                latest_job.id,
                latest_job.status,
            )
            return "job_in_progress"
        if latest_job.status in {AsyncJobStatus.SUCCEEDED.value, AsyncJobStatus.FAILED.value}:
            logger.info(
                "Diagnosis report bootstrap skipped because report job already attempted. run_id=%s job_id=%s status=%s",
                run.id,
                latest_job.id,
                latest_job.status,
            )
            return "already_attempted"

    report_job = create_async_job(
        db,
        job_type=AsyncJobType.DIAGNOSIS_REPORT.value,
        resource_type="diagnosis_report",
        resource_id=run.id,
        project_id=run.project_id,
        payload={
            "run_id": run.id,
            "project_id": run.project_id,
            "owner_user_id": owner_user_id,
            "fallback_target_university": fallback_target_university,
            "fallback_target_major": fallback_target_major,
            "report_mode": report_mode,
            "include_appendix": include_appendix,
            "include_citations": include_citations,
            "force_regenerate": False,
            "trigger": "diagnosis_auto",
        },
    )
    dispatch_job_if_enabled(report_job.id)
    logger.info(
        "Diagnosis report auto-generation queued. run_id=%s project_id=%s job_id=%s mode=%s",
        run.id,
        run.project_id,
        report_job.id,
        report_mode,
    )
    return "queued"


def _mark_resource_running(db: Session, job: AsyncJob) -> None:
    if job.job_type == AsyncJobType.DIAGNOSIS.value:
        run = db.get(DiagnosisRun, job.resource_id)
        if run is not None:
            run.status = "RUNNING"
            run.error_message = None
            db.add(run)
    elif job.job_type == AsyncJobType.DIAGNOSIS_REPORT.value:
        run = db.get(DiagnosisRun, job.resource_id)
        if run is not None:
            run.status_message = "Generating consultant diagnosis report..."
            db.add(run)
    elif job.job_type == AsyncJobType.RENDER.value:
        render_job = db.get(RenderJob, job.resource_id)
        if render_job is not None:
            render_job.status = RenderStatus.PROCESSING.value
            render_job.result_message = None
            db.add(render_job)
    elif job.job_type == AsyncJobType.RESEARCH_INGEST.value:
        document = db.get(ResearchDocument, job.resource_id)
        if document is not None:
            document.status = "ingesting"
            document.last_error = None
            db.add(document)
    elif job.job_type == AsyncJobType.DOCUMENT_PARSE.value:
        document = db.get(ParsedDocument, job.resource_id)
        if document is not None:
            metadata = dict(document.parse_metadata or {})
            metadata["latest_async_job_id"] = job.id
            metadata["latest_async_job_status"] = job.status
            document.parse_metadata = metadata
            db.add(document)
    elif job.job_type == AsyncJobType.INQUIRY_EMAIL.value:
        from polio_api.services.inquiry_service import sync_inquiry_delivery_state_from_job

        sync_inquiry_delivery_state_from_job(
            db,
            inquiry_id=job.resource_id,
            delivery_status="sending",
            inquiry_status="delivery_sending",
            async_job_id=job.id,
            async_job_status=job.status,
            retry_needed=False,
        )


def _mark_resource_retrying(db: Session, job: AsyncJob, reason: str) -> None:
    if job.job_type == AsyncJobType.DIAGNOSIS.value:
        run = db.get(DiagnosisRun, job.resource_id)
        if run is not None:
            run.status = "RETRYING"
            run.error_message = reason
            db.add(run)
    elif job.job_type == AsyncJobType.DIAGNOSIS_REPORT.value:
        run = db.get(DiagnosisRun, job.resource_id)
        if run is not None:
            run.status_message = "Retrying diagnosis report generation..."
            db.add(run)
    elif job.job_type == AsyncJobType.RENDER.value:
        render_job = db.get(RenderJob, job.resource_id)
        if render_job is not None:
            render_job.status = RenderStatus.RETRYING.value
            render_job.result_message = reason
            db.add(render_job)
    elif job.job_type == AsyncJobType.RESEARCH_INGEST.value:
        document = db.get(ResearchDocument, job.resource_id)
        if document is not None:
            document.status = "retrying"
            document.last_error = reason
            db.add(document)
    elif job.job_type == AsyncJobType.DOCUMENT_PARSE.value:
        document = db.get(ParsedDocument, job.resource_id)
        if document is not None:
            metadata = dict(document.parse_metadata or {})
            metadata["latest_async_job_id"] = job.id
            metadata["latest_async_job_status"] = job.status
            metadata["latest_async_job_error"] = reason
            document.parse_metadata = metadata
            db.add(document)
    elif job.job_type == AsyncJobType.INQUIRY_EMAIL.value:
        from polio_api.services.inquiry_service import sync_inquiry_delivery_state_from_job

        sync_inquiry_delivery_state_from_job(
            db,
            inquiry_id=job.resource_id,
            delivery_status="retrying",
            inquiry_status="delivery_retrying",
            async_job_id=job.id,
            async_job_status=job.status,
            reason=reason,
            retry_needed=True,
        )


def _mark_resource_failed(db: Session, job: AsyncJob, reason: str) -> None:
    if job.job_type == AsyncJobType.DIAGNOSIS.value:
        run = db.get(DiagnosisRun, job.resource_id)
        if run is not None:
            run.status = "FAILED"
            run.error_message = reason
            db.add(run)
    elif job.job_type == AsyncJobType.DIAGNOSIS_REPORT.value:
        run = db.get(DiagnosisRun, job.resource_id)
        if run is not None:
            run.status_message = "Diagnosis report generation failed."
            db.add(run)
    elif job.job_type == AsyncJobType.RENDER.value:
        render_job = db.get(RenderJob, job.resource_id)
        if render_job is not None:
            render_job.status = RenderStatus.FAILED.value
            render_job.result_message = reason
            db.add(render_job)
    elif job.job_type == AsyncJobType.RESEARCH_INGEST.value:
        document = db.get(ResearchDocument, job.resource_id)
        if document is not None:
            document.status = "failed"
            document.last_error = reason
            db.add(document)
    elif job.job_type == AsyncJobType.DOCUMENT_PARSE.value:
        document = db.get(ParsedDocument, job.resource_id)
        if document is not None:
            metadata = dict(document.parse_metadata or {})
            metadata["latest_async_job_id"] = job.id
            metadata["latest_async_job_status"] = AsyncJobStatus.FAILED.value
            metadata["latest_async_job_error"] = reason
            document.parse_metadata = metadata
            db.add(document)
    elif job.job_type == AsyncJobType.INQUIRY_EMAIL.value:
        from polio_api.services.inquiry_service import sync_inquiry_delivery_state_from_job

        sync_inquiry_delivery_state_from_job(
            db,
            inquiry_id=job.resource_id,
            delivery_status="failed",
            inquiry_status="delivery_failed",
            async_job_id=job.id,
            async_job_status=job.status,
            reason=reason,
            retry_needed=True,
        )


def _reset_resource_for_retry(db: Session, job: AsyncJob) -> None:
    if job.job_type == AsyncJobType.DIAGNOSIS.value:
        run = db.get(DiagnosisRun, job.resource_id)
        if run is not None:
            run.status = "PENDING"
            run.error_message = None
            db.add(run)
    elif job.job_type == AsyncJobType.DIAGNOSIS_REPORT.value:
        run = db.get(DiagnosisRun, job.resource_id)
        if run is not None:
            run.status_message = "Diagnosis report queued for retry."
            db.add(run)
    elif job.job_type == AsyncJobType.RENDER.value:
        render_job = db.get(RenderJob, job.resource_id)
        if render_job is not None:
            render_job.status = RenderStatus.QUEUED.value
            render_job.result_message = None
            db.add(render_job)
    elif job.job_type == AsyncJobType.RESEARCH_INGEST.value:
        document = db.get(ResearchDocument, job.resource_id)
        if document is not None:
            document.status = "pending"
            document.last_error = None
            db.add(document)
    elif job.job_type == AsyncJobType.DOCUMENT_PARSE.value:
        document = db.get(ParsedDocument, job.resource_id)
        if document is not None:
            metadata = dict(document.parse_metadata or {})
            metadata["latest_async_job_id"] = job.id
            metadata["latest_async_job_status"] = AsyncJobStatus.QUEUED.value
            metadata.pop("latest_async_job_error", None)
            document.parse_metadata = metadata
            db.add(document)
    elif job.job_type == AsyncJobType.INQUIRY_EMAIL.value:
        from polio_api.services.inquiry_service import sync_inquiry_delivery_state_from_job

        sync_inquiry_delivery_state_from_job(
            db,
            inquiry_id=job.resource_id,
            delivery_status="queued",
            inquiry_status="delivery_queued",
            async_job_id=job.id,
            async_job_status=AsyncJobStatus.QUEUED.value,
            retry_needed=False,
        )


def _opt_str(value: Any) -> str | None:
    if value is None:
        return None
    normalized = str(value).strip()
    return normalized or None


def _diagnosis_failure_reason(reason: str) -> str:
    fallback = "Diagnosis job failed. Retry after checking the project evidence."
    normalized = sanitize_public_error(reason, fallback=fallback)
    lowered = normalized.lower()

    if "upload a parsed document before running diagnosis" in lowered:
        return "Upload and parse at least one document before running diagnosis."
    if "parsed document content is empty" in lowered:
        return "Diagnosis requires parsed text evidence. Re-run parsing with a clearer source file."
    if "project owner not found" in lowered:
        return "Diagnosis owner context is missing. Re-open the project and retry."
    return normalized


def _public_failure_reason(job: AsyncJob, reason: str) -> str:
    if job.job_type == AsyncJobType.DOCUMENT_PARSE.value:
        return "Document parsing failed. Verify the file is still available and retry."
    if job.job_type == AsyncJobType.RENDER.value:
        return "Render job failed. Review the draft content and retry."
    if job.job_type == AsyncJobType.DIAGNOSIS.value:
        return _diagnosis_failure_reason(reason)
    if job.job_type == AsyncJobType.DIAGNOSIS_REPORT.value:
        return "Diagnosis report generation failed. Retry report generation after checking diagnosis evidence."
    if job.job_type == AsyncJobType.INQUIRY_EMAIL.value:
        return "Inquiry email delivery failed. Retry after checking SMTP configuration."
    return sanitize_public_error(reason, fallback="Async job failed.")
