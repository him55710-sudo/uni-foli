from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import FileResponse
from sqlalchemy import desc, func
from sqlalchemy.orm import Session

from unifoli_api.api.deps import get_current_admin, get_db
from unifoli_api.db.models.async_job import AsyncJob
from unifoli_api.db.models.blueprint import Blueprint
from unifoli_api.db.models.diagnosis_report_artifact import DiagnosisReportArtifact
from unifoli_api.db.models.diagnosis_run import DiagnosisRun
from unifoli_api.db.models.draft import Draft
from unifoli_api.db.models.inquiry import Inquiry
from unifoli_api.db.models.parsed_document import ParsedDocument
from unifoli_api.db.models.policy_flag import PolicyFlag
from unifoli_api.db.models.project import Project
from unifoli_api.db.models.quest import Quest
from unifoli_api.db.models.render_job import RenderJob
from unifoli_api.db.models.response_trace import ResponseTrace
from unifoli_api.db.models.review_task import ReviewTask
from unifoli_api.db.models.upload_asset import UploadAsset
from unifoli_api.db.models.user import User
from unifoli_api.db.models.workshop import DraftArtifact, WorkshopSession, WorkshopTurn
from unifoli_shared.paths import resolve_runtime_path

router = APIRouter()


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _count(db: Session, model: Any, *filters: Any) -> int:
    query = db.query(func.count(model.id))
    for item in filters:
        query = query.filter(item)
    return int(query.scalar() or 0)


def _count_since(db: Session, model: Any, created_at_field: Any, since: datetime) -> int:
    return int(db.query(func.count(model.id)).filter(created_at_field >= since).scalar() or 0)


def _sum_int(db: Session, field: Any, *filters: Any) -> int:
    query = db.query(func.coalesce(func.sum(field), 0))
    for item in filters:
        query = query.filter(item)
    return int(query.scalar() or 0)


def _avg_float(db: Session, field: Any, *filters: Any) -> float:
    query = db.query(func.coalesce(func.avg(field), 0))
    for item in filters:
        query = query.filter(item)
    return round(float(query.scalar() or 0), 1)


def _status_breakdown(db: Session, model: Any, field: Any) -> list[dict[str, Any]]:
    rows = db.query(field, func.count(model.id)).group_by(field).order_by(func.count(model.id).desc()).all()
    return [{"status": str(status_value or "unknown"), "count": int(count)} for status_value, count in rows]


def _recent_rows(db: Session, model: Any, order_field: Any, limit: int = 10) -> list[Any]:
    return db.query(model).order_by(desc(order_field)).limit(limit).all()


def _recent_project_rows(db: Session, model: Any, project_id: str, order_field: Any, limit: int = 10) -> list[Any]:
    return db.query(model).filter(model.project_id == project_id).order_by(desc(order_field)).limit(limit).all()


def _safe_text(value: Any, limit: int = 360) -> str | None:
    text = " ".join(str(value or "").split()).strip()
    if not text:
        return None
    if len(text) <= limit:
        return text
    return f"{text[: limit - 3].rstrip()}..."


def _iso(value: Any) -> str | None:
    if isinstance(value, datetime):
        return value.isoformat()
    return None


def _dt_sort_key(value: datetime | None) -> datetime:
    if value is None:
        return datetime.min.replace(tzinfo=timezone.utc)
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def _parse_event_at(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def _project_or_404(db: Session, project_id: str) -> Project:
    project = db.query(Project).filter(Project.id == project_id).first()
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found.")
    return project


def _event(
    *,
    occurred_at: datetime | None,
    category: str,
    severity: str,
    title: str,
    message: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "occurred_at": _iso(occurred_at),
        "category": category,
        "severity": severity,
        "title": title,
        "message": _safe_text(message, 520),
        "metadata": metadata or {},
    }


def _resolve_local_file_path(raw_path: str | None) -> Path:
    if not raw_path:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="File path not found.")
    path = Path(raw_path).expanduser()
    if not path.is_absolute():
        path = resolve_runtime_path(raw_path).expanduser()
    resolved = path.resolve()
    if not resolved.exists() or not resolved.is_file():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Stored file is not available.")
    return resolved


def _file_response(*, path: str | None, filename: str, media_type: str) -> FileResponse:
    resolved = _resolve_local_file_path(path)
    return FileResponse(
        path=str(resolved),
        filename=filename,
        media_type=media_type,
        content_disposition_type="inline",
        headers={"Cache-Control": "no-store"},
    )


@router.get("/me")
def admin_me(admin: User = Depends(get_current_admin)) -> dict[str, Any]:
    return {
        "is_admin": True,
        "id": admin.id,
        "email": admin.email,
        "name": admin.name,
    }


@router.get("/stats")
def get_admin_stats(
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin),
) -> dict[str, Any]:
    now = _now()
    last_24h = now - timedelta(hours=24)
    last_7d = now - timedelta(days=7)
    last_30d = now - timedelta(days=30)

    diagnosis_failures = _count(db, DiagnosisRun, DiagnosisRun.status.in_(["FAILED", "ERROR"]))
    upload_failures = _count(db, UploadAsset, UploadAsset.status.in_(["FAILED", "failed"]))
    document_failures = _count(db, ParsedDocument, ParsedDocument.status.in_(["FAILED", "failed"]))
    report_failures = _count(db, DiagnosisReportArtifact, DiagnosisReportArtifact.status.in_(["FAILED", "failed"]))
    async_failures = _count(db, AsyncJob, AsyncJob.status.in_(["failed", "dead_lettered", "FAILED", "DEAD_LETTERED"]))

    return {
        "generated_at": now.isoformat(),
        "summary": {
            "total_users": _count(db, User),
            "total_projects": _count(db, Project),
            "total_uploads": _count(db, UploadAsset),
            "total_parsed_documents": _count(db, ParsedDocument),
            "total_diagnosis_runs": _count(db, DiagnosisRun),
            "total_reports": _count(db, DiagnosisReportArtifact),
            "total_drafts": _count(db, Draft),
            "total_workshop_sessions": _count(db, WorkshopSession),
            "total_workshop_turns": _count(db, WorkshopTurn),
            "total_render_jobs": _count(db, RenderJob),
            "total_async_jobs": _count(db, AsyncJob),
            "total_inquiries": _count(db, Inquiry),
            "total_policy_flags": _count(db, PolicyFlag),
            "total_review_tasks": _count(db, ReviewTask),
            "total_response_traces": _count(db, ResponseTrace),
        },
        "growth": {
            "last_24h": {
                "users": _count_since(db, User, User.created_at, last_24h),
                "projects": _count_since(db, Project, Project.created_at, last_24h),
                "uploads": _count_since(db, UploadAsset, UploadAsset.created_at, last_24h),
                "diagnosis_runs": _count_since(db, DiagnosisRun, DiagnosisRun.created_at, last_24h),
                "workshop_turns": _count_since(db, WorkshopTurn, WorkshopTurn.created_at, last_24h),
            },
            "last_7d": {
                "users": _count_since(db, User, User.created_at, last_7d),
                "projects": _count_since(db, Project, Project.created_at, last_7d),
                "uploads": _count_since(db, UploadAsset, UploadAsset.created_at, last_7d),
                "diagnosis_runs": _count_since(db, DiagnosisRun, DiagnosisRun.created_at, last_7d),
                "workshop_turns": _count_since(db, WorkshopTurn, WorkshopTurn.created_at, last_7d),
            },
            "last_30d": {
                "users": _count_since(db, User, User.created_at, last_30d),
                "projects": _count_since(db, Project, Project.created_at, last_30d),
                "uploads": _count_since(db, UploadAsset, UploadAsset.created_at, last_30d),
                "diagnosis_runs": _count_since(db, DiagnosisRun, DiagnosisRun.created_at, last_30d),
                "workshop_turns": _count_since(db, WorkshopTurn, WorkshopTurn.created_at, last_30d),
            },
        },
        "quality": {
            "open_policy_flags": _count(db, PolicyFlag, PolicyFlag.status == "open"),
            "open_review_tasks": _count(db, ReviewTask, ReviewTask.status == "open"),
            "diagnosis_failures": diagnosis_failures,
            "upload_failures": upload_failures,
            "document_failures": document_failures,
            "report_failures": report_failures,
            "async_failures": async_failures,
            "total_failure_signals": diagnosis_failures + upload_failures + document_failures + report_failures + async_failures,
        },
        "usage": {
            "total_upload_bytes": _sum_int(db, UploadAsset.file_size_bytes),
            "total_upload_pages": _sum_int(db, UploadAsset.page_count),
            "avg_upload_pages": _avg_float(db, UploadAsset.page_count),
            "total_document_pages": _sum_int(db, ParsedDocument.page_count),
            "total_document_words": _sum_int(db, ParsedDocument.word_count),
            "avg_document_words": _avg_float(db, ParsedDocument.word_count),
            "total_blueprints": _count(db, Blueprint),
            "total_quests": _count(db, Quest),
            "completed_quests": _count(db, Quest, Quest.status == "COMPLETED"),
            "draft_artifacts": _count(db, DraftArtifact),
        },
        "breakdowns": {
            "project_status": _status_breakdown(db, Project, Project.status),
            "upload_status": _status_breakdown(db, UploadAsset, UploadAsset.status),
            "document_status": _status_breakdown(db, ParsedDocument, ParsedDocument.status),
            "diagnosis_status": _status_breakdown(db, DiagnosisRun, DiagnosisRun.status),
            "report_status": _status_breakdown(db, DiagnosisReportArtifact, DiagnosisReportArtifact.status),
            "render_job_status": _status_breakdown(db, RenderJob, RenderJob.status),
            "async_job_status": _status_breakdown(db, AsyncJob, AsyncJob.status),
            "inquiry_status": _status_breakdown(db, Inquiry, Inquiry.status),
            "policy_flag_severity": _status_breakdown(db, PolicyFlag, PolicyFlag.severity),
            "review_task_status": _status_breakdown(db, ReviewTask, ReviewTask.status),
        },
    }


@router.get("/projects")
def list_all_projects(
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin),
) -> list[dict[str, Any]]:
    projects = (
        db.query(Project, User)
        .outerjoin(User, Project.owner_user_id == User.id)
        .order_by(Project.created_at.desc())
        .limit(500)
        .all()
    )

    result = []
    for project, user in projects:
        result.append(
            {
                "id": project.id,
                "title": project.title,
                "target_university": project.target_university,
                "target_major": project.target_major,
                "status": project.status,
                "created_at": project.created_at,
                "updated_at": project.updated_at,
                "counts": {
                    "uploads": _count(db, UploadAsset, UploadAsset.project_id == project.id),
                    "diagnosis_runs": _count(db, DiagnosisRun, DiagnosisRun.project_id == project.id),
                    "reports": _count(db, DiagnosisReportArtifact, DiagnosisReportArtifact.project_id == project.id),
                    "drafts": _count(db, Draft, Draft.project_id == project.id),
                    "workshop_sessions": _count(db, WorkshopSession, WorkshopSession.project_id == project.id),
                    "async_jobs": _count(db, AsyncJob, AsyncJob.project_id == project.id),
                    "open_flags": _count(db, PolicyFlag, PolicyFlag.project_id == project.id, PolicyFlag.status == "open"),
                },
                "owner": {
                    "id": user.id if user else None,
                    "email": user.email if user else None,
                    "name": user.name if user else None,
                    "grade": user.grade if user else None,
                    "target_major": user.target_major if user else None,
                },
            }
        )
    return result


@router.get("/projects/{project_id}/assets")
def list_project_assets(
    project_id: str,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin),
) -> dict[str, Any]:
    project = _project_or_404(db, project_id)
    uploads = db.query(UploadAsset).filter(UploadAsset.project_id == project_id).order_by(desc(UploadAsset.created_at)).all()
    documents = db.query(ParsedDocument).filter(ParsedDocument.project_id == project_id).order_by(desc(ParsedDocument.updated_at)).all()
    diagnoses = db.query(DiagnosisRun).filter(DiagnosisRun.project_id == project_id).order_by(desc(DiagnosisRun.created_at)).all()
    reports = (
        db.query(DiagnosisReportArtifact)
        .filter(DiagnosisReportArtifact.project_id == project_id)
        .order_by(desc(DiagnosisReportArtifact.created_at))
        .all()
    )

    return {
        "project": {
            "id": project.id,
            "title": project.title,
            "status": project.status,
            "target_university": project.target_university,
            "target_major": project.target_major,
        },
        "uploads": [
            {
                "id": upload.id,
                "filename": upload.original_filename,
                "content_type": upload.content_type,
                "file_size_bytes": upload.file_size_bytes,
                "page_count": upload.page_count,
                "created_at": upload.created_at,
                "ingested_at": upload.ingested_at,
                "status": upload.status,
                "ingest_error": _safe_text(upload.ingest_error),
            }
            for upload in uploads
        ],
        "documents": [
            {
                "id": document.id,
                "upload_asset_id": document.upload_asset_id,
                "parser_name": document.parser_name,
                "status": document.status,
                "masking_status": document.masking_status,
                "parse_attempts": document.parse_attempts,
                "page_count": document.page_count,
                "word_count": document.word_count,
                "last_error": _safe_text(document.last_error),
                "latest_async_job_id": document.latest_async_job_id,
                "latest_async_job_status": document.latest_async_job_status,
                "latest_async_job_error": _safe_text(document.latest_async_job_error),
                "created_at": document.created_at,
                "updated_at": document.updated_at,
            }
            for document in documents
        ],
        "diagnosis_runs": [
            {
                "id": run.id,
                "status": run.status,
                "status_message": _safe_text(run.status_message),
                "error_message": _safe_text(run.error_message),
                "created_at": run.created_at,
                "updated_at": run.updated_at,
            }
            for run in diagnoses
        ],
        "reports": [
            {
                "id": report.id,
                "diagnosis_run_id": report.diagnosis_run_id,
                "mode": report.report_mode,
                "template_id": report.template_id,
                "format": report.export_format,
                "version": report.version,
                "created_at": report.created_at,
                "updated_at": report.updated_at,
                "status": report.status,
                "error_message": _safe_text(report.error_message),
            }
            for report in reports
        ],
    }


@router.get("/projects/{project_id}/logs")
def list_project_logs(
    project_id: str,
    limit: int = Query(default=160, ge=1, le=500),
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin),
) -> dict[str, Any]:
    project = _project_or_404(db, project_id)
    events: list[dict[str, Any]] = []
    events.append(
        _event(
            occurred_at=project.created_at,
            category="project",
            severity="info",
            title="프로젝트 생성",
            message=f"{project.target_university or '-'} / {project.target_major or '-'}",
            metadata={"project_id": project.id, "status": project.status, "title": project.title},
        )
    )
    if project.updated_at and project.updated_at != project.created_at:
        events.append(
            _event(
                occurred_at=project.updated_at,
                category="project",
                severity="info",
                title="프로젝트 갱신",
                message=project.title,
                metadata={"project_id": project.id, "status": project.status},
            )
        )

    for upload in _recent_project_rows(db, UploadAsset, project_id, UploadAsset.created_at, limit):
        severity = "danger" if upload.ingest_error else ("warning" if str(upload.status).lower() not in {"stored", "parsed", "completed"} else "info")
        events.append(
            _event(
                occurred_at=upload.created_at,
                category="upload",
                severity=severity,
                title=f"업로드: {upload.original_filename}",
                message=upload.ingest_error or f"status={upload.status}, pages={upload.page_count or 0}, bytes={upload.file_size_bytes or 0}",
                metadata={"upload_id": upload.id, "status": upload.status, "content_type": upload.content_type},
            )
        )

    for document in _recent_project_rows(db, ParsedDocument, project_id, ParsedDocument.updated_at, limit):
        severity = "danger" if document.last_error else ("warning" if str(document.status).lower() in {"failed", "partial"} else "info")
        events.append(
            _event(
                occurred_at=document.updated_at,
                category="parse",
                severity=severity,
                title=f"파싱 상태: {document.status}",
                message=document.last_error or document.latest_async_job_error or f"parser={document.parser_name}, words={document.word_count}, pages={document.page_count}",
                metadata={
                    "document_id": document.id,
                    "upload_asset_id": document.upload_asset_id,
                    "parse_attempts": document.parse_attempts,
                    "latest_async_job_status": document.latest_async_job_status,
                },
            )
        )

    for run in _recent_project_rows(db, DiagnosisRun, project_id, DiagnosisRun.updated_at, limit):
        severity = "danger" if run.error_message or str(run.status).upper() == "FAILED" else ("success" if str(run.status).upper() == "COMPLETED" else "info")
        events.append(
            _event(
                occurred_at=run.updated_at,
                category="diagnosis",
                severity=severity,
                title=f"진단 실행: {run.status}",
                message=run.error_message or run.status_message,
                metadata={"diagnosis_run_id": run.id, "status": run.status},
            )
        )

    for draft in _recent_project_rows(db, Draft, project_id, Draft.updated_at, limit):
        events.append(
            _event(
                occurred_at=draft.updated_at,
                category="draft",
                severity="success" if str(draft.status).lower() in {"completed", "done", "ready"} else "info",
                title=f"문서 초안: {draft.status}",
                message=draft.title,
                metadata={"draft_id": draft.id, "source_document_id": draft.source_document_id},
            )
        )

    for report in _recent_project_rows(db, DiagnosisReportArtifact, project_id, DiagnosisReportArtifact.updated_at, limit):
        severity = "danger" if report.error_message or str(report.status).lower() == "failed" else ("success" if str(report.status).lower() == "ready" else "info")
        events.append(
            _event(
                occurred_at=report.updated_at,
                category="report",
                severity=severity,
                title=f"진단 보고서: {report.status}",
                message=report.error_message or f"{report.report_mode} / {report.export_format} / v{report.version}",
                metadata={"report_id": report.id, "diagnosis_run_id": report.diagnosis_run_id, "format": report.export_format},
            )
        )

    for job in _recent_project_rows(db, AsyncJob, project_id, AsyncJob.updated_at, limit):
        status_text = str(job.status).lower()
        severity = "danger" if status_text in {"failed", "dead_lettered"} or job.failure_reason else ("warning" if status_text in {"retrying"} else "info")
        events.append(
            _event(
                occurred_at=job.updated_at,
                category="async_job",
                severity=severity,
                title=f"비동기 작업: {job.job_type} / {job.status}",
                message=job.failure_reason or job.progress_message,
                metadata={
                    "job_id": job.id,
                    "resource_type": job.resource_type,
                    "resource_id": job.resource_id,
                    "retry_count": job.retry_count,
                    "phase": job.phase,
                    "failure_code": job.failure_code,
                    "progress_stage": job.progress_stage,
                },
            )
        )

    for render_job in _recent_project_rows(db, RenderJob, project_id, RenderJob.updated_at, limit):
        status_text = str(render_job.status).lower()
        severity = "danger" if status_text in {"failed", "error"} else ("success" if status_text in {"ready", "completed", "succeeded"} else "info")
        events.append(
            _event(
                occurred_at=render_job.updated_at,
                category="render",
                severity=severity,
                title=f"문서 렌더링: {render_job.status}",
                message=render_job.result_message or f"{render_job.render_format} / template={render_job.template_id or '-'}",
                metadata={"render_job_id": render_job.id, "draft_id": render_job.draft_id, "format": render_job.render_format},
            )
        )

    for trace in _recent_project_rows(db, ResponseTrace, project_id, ResponseTrace.created_at, limit):
        events.append(
            _event(
                occurred_at=trace.created_at,
                category="response_trace",
                severity="info",
                title=f"AI 응답 추적: {trace.model_name}",
                message=trace.response_excerpt,
                metadata={"trace_id": trace.id, "diagnosis_run_id": trace.diagnosis_run_id},
            )
        )

    sessions = db.query(WorkshopSession).filter(WorkshopSession.project_id == project_id).order_by(desc(WorkshopSession.updated_at)).limit(limit).all()
    session_ids = [session.id for session in sessions]
    for session in sessions:
        events.append(
            _event(
                occurred_at=session.updated_at,
                category="workshop",
                severity="info",
                title=f"워크숍 세션: {session.status}",
                message=f"context_score={session.context_score}, quality={session.quality_level}",
                metadata={"session_id": session.id, "quest_id": session.quest_id},
            )
        )
    if session_ids:
        turns = (
            db.query(WorkshopTurn)
            .filter(WorkshopTurn.session_id.in_(session_ids))
            .order_by(desc(WorkshopTurn.created_at))
            .limit(limit)
            .all()
        )
        for turn in turns:
            events.append(
                _event(
                    occurred_at=turn.created_at,
                    category="workshop_turn",
                    severity="info",
                    title=f"채팅 턴: {turn.speaker_role}",
                    message=turn.response or turn.query,
                    metadata={"turn_id": turn.id, "session_id": turn.session_id, "turn_type": turn.turn_type},
                )
            )

    for flag in _recent_project_rows(db, PolicyFlag, project_id, PolicyFlag.created_at, limit):
        events.append(
            _event(
                occurred_at=flag.created_at,
                category="policy_flag",
                severity="danger" if flag.severity == "high" else "warning",
                title=f"정책 플래그: {flag.code}",
                message=flag.detail,
                metadata={"flag_id": flag.id, "severity": flag.severity, "status": flag.status, "match_count": flag.match_count},
            )
        )

    for task in _recent_project_rows(db, ReviewTask, project_id, ReviewTask.updated_at, limit):
        events.append(
            _event(
                occurred_at=task.updated_at,
                category="review_task",
                severity="warning" if task.status == "open" else "info",
                title=f"검토 작업: {task.task_type}",
                message=task.reason,
                metadata={"review_task_id": task.id, "status": task.status, "assigned_role": task.assigned_role},
            )
        )

    events.sort(key=lambda item: _dt_sort_key(_parse_event_at(item.get("occurred_at"))), reverse=True)
    return {"project_id": project_id, "logs": events[:limit]}


@router.get("/logs/recent")
def list_recent_admin_logs(
    limit: int = Query(default=80, ge=1, le=300),
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin),
) -> dict[str, Any]:
    events: list[dict[str, Any]] = []

    for job in db.query(AsyncJob).filter(AsyncJob.failure_reason.isnot(None)).order_by(desc(AsyncJob.updated_at)).limit(limit).all():
        events.append(
            _event(
                occurred_at=job.updated_at,
                category="async_job",
                severity="danger",
                title=f"작업 실패: {job.job_type}",
                message=job.failure_reason,
                metadata={"project_id": job.project_id, "job_id": job.id, "status": job.status, "failure_code": job.failure_code},
            )
        )
    for run in db.query(DiagnosisRun).filter(DiagnosisRun.error_message.isnot(None)).order_by(desc(DiagnosisRun.updated_at)).limit(limit).all():
        events.append(
            _event(
                occurred_at=run.updated_at,
                category="diagnosis",
                severity="danger",
                title="진단 실패",
                message=run.error_message,
                metadata={"project_id": run.project_id, "diagnosis_run_id": run.id, "status": run.status},
            )
        )
    for document in db.query(ParsedDocument).filter(ParsedDocument.last_error.isnot(None)).order_by(desc(ParsedDocument.updated_at)).limit(limit).all():
        events.append(
            _event(
                occurred_at=document.updated_at,
                category="parse",
                severity="danger",
                title="문서 파싱 오류",
                message=document.last_error,
                metadata={"project_id": document.project_id, "document_id": document.id, "status": document.status},
            )
        )

    events.sort(key=lambda item: _dt_sort_key(_parse_event_at(item.get("occurred_at"))), reverse=True)
    return {"logs": events[:limit]}


@router.get("/uploads/{upload_id}/view")
def view_raw_upload(
    upload_id: str,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin),
) -> FileResponse:
    upload = db.query(UploadAsset).filter(UploadAsset.id == upload_id).first()
    if not upload:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Upload not found.")

    return _file_response(
        path=upload.stored_path,
        filename=upload.original_filename,
        media_type=upload.content_type or "application/octet-stream",
    )


@router.get("/reports/{report_id}/view")
def view_diagnosis_report(
    report_id: str,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin),
) -> FileResponse:
    report = db.query(DiagnosisReportArtifact).filter(DiagnosisReportArtifact.id == report_id).first()
    if not report:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not found.")

    return _file_response(
        path=report.generated_file_path,
        filename=f"diagnosis_{report_id}.{report.export_format or 'pdf'}",
        media_type="application/pdf" if report.export_format == "pdf" else "application/octet-stream",
    )
