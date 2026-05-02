import logging
from pathlib import Path
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import FileResponse, Response
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from unifoli_api.api.deps import get_current_user, get_db
from unifoli_api.core.config import get_settings
from unifoli_api.core.errors import (
    UniFoliErrorCode,
    build_error_detail,
    extract_error_code,
    extract_error_message,
)
from unifoli_api.core.rate_limit import rate_limit
from unifoli_api.core.security import ensure_resolved_within_base
from unifoli_api.db.models.diagnosis_run import DiagnosisRun
from unifoli_api.db.models.project import Project
from unifoli_api.db.models.response_trace import ResponseTrace
from unifoli_api.db.models.user import User
from unifoli_api.schemas.draft import DraftCreate
from unifoli_api.schemas.diagnosis import (
    ConsultantDiagnosisArtifactResponse,
    DiagnosisReportCreateRequest,
    DiagnosisGuidedPlanRequest,
    DiagnosisGuidedPlanResponse,
    DiagnosisPolicyFlagRead,
    DiagnosisResultPayload,
    DiagnosisRunRequest,
    DiagnosisRunResponse,
)
from unifoli_api.services.async_job_service import (
    create_async_job,
    dispatch_job_if_enabled,
    ensure_default_diagnosis_report_job,
    get_latest_job_for_resource,
    process_async_job,
)
from unifoli_api.services.diagnosis_runtime_service import build_policy_scan_text, combine_project_text
from unifoli_api.services.diagnosis_report_service import (
    build_report_artifact_response,
    generate_consultant_report_artifact,
    get_latest_report_artifact_for_run,
    get_report_artifact_by_id,
    load_report_artifact_pdf_bytes,
    report_artifact_file_path,
    report_artifact_storage_key,
    resolve_student_name_from_documents,
)
from unifoli_api.services.diagnosis_service import (
    DiagnosisCitation,
    attach_policy_flags_to_run,
    build_guided_outline_plan,
    detect_policy_flags,
    ensure_review_task_for_flags,
    latest_response_trace,
    serialize_citation,
    serialize_policy_flag,
)
from unifoli_api.services.draft_service import create_draft
from unifoli_api.services.document_service import list_documents_for_project
from unifoli_api.services.project_service import get_project
from unifoli_domain.enums import AsyncJobType
from unifoli_shared.paths import get_export_root, resolve_project_path

router = APIRouter()
logger = logging.getLogger("unifoli.api.diagnosis")
INTERNAL_REPORT_MODE = "premium"


def _normalize_report_mode(value: str | None) -> str:
    # 보고??는 ???? ???? ??플???구조(??리미엄 10???로만 ??성??다.
    normalized = str(value or "").strip().lower()
    if normalized in {"compact", "basic"}:
        return "basic"
    if normalized in {"premium_10p", "premium", ""}:
        return "premium"
    if normalized == "consultant":
        return "consultant"
    return INTERNAL_REPORT_MODE


def _build_diagnosis_download_filename(user: User, *, student_name: str | None = None) -> str:
    raw_name = str(student_name or "").strip() or str(getattr(user, "name", "") or "").strip()
    safe_name = "".join(ch for ch in raw_name if ch not in '<>:"/\\|?*').strip()
    if not safe_name:
        safe_name = "user"
    return f"{safe_name}_school-record-diagnosis-report.pdf"


def _resolve_download_student_name(db: Session, project_id: str) -> str | None:
    try:
        documents = list_documents_for_project(db, project_id)
    except Exception:  # noqa: BLE001
        logger.exception("Failed to resolve student name for diagnosis download. project_id=%s", project_id)
        return None
    return resolve_student_name_from_documents(documents, fallback=None)


def _content_disposition_header(filename: str) -> str:
    encoded = quote(filename)
    return f"attachment; filename=\"diagnosis-report.pdf\"; filename*=UTF-8''{encoded}"


def _get_run_for_user(db: Session, diagnosis_id: str, user_id: str) -> DiagnosisRun | None:
    return db.scalar(
        select(DiagnosisRun)
        .join(Project, DiagnosisRun.project_id == Project.id)
        .where(DiagnosisRun.id == diagnosis_id, Project.owner_user_id == user_id)
        .options(
            selectinload(DiagnosisRun.policy_flags),
            selectinload(DiagnosisRun.review_tasks),
            selectinload(DiagnosisRun.response_traces).selectinload(ResponseTrace.citations),
        )
    )


def _build_run_response(db: Session, run: DiagnosisRun) -> DiagnosisRunResponse:
    payload = DiagnosisResultPayload.model_validate_json(run.result_payload) if run.result_payload else None
    trace = latest_response_trace(run)
    citations = [DiagnosisCitation.model_validate(serialize_citation(item)) for item in (trace.citations if trace else [])]
    async_job = get_latest_job_for_resource(db, resource_type="diagnosis_run", resource_id=run.id)
    report_job = get_latest_job_for_resource(db, resource_type="diagnosis_report", resource_id=run.id)
    latest_report = get_latest_report_artifact_for_run(
        db,
        diagnosis_run_id=run.id,
        report_mode=INTERNAL_REPORT_MODE,
    )

    report_status: str | None = None
    if latest_report is not None and latest_report.status in {"READY", "FAILED"}:
        report_status = latest_report.status
    elif report_job is not None:
        normalized_report_job_status = report_job.status.upper()
        if normalized_report_job_status == "SUCCEEDED":
            report_status = "AUTO_STARTING"
        else:
            report_status = normalized_report_job_status
    elif run.status == "COMPLETED" and run.result_payload:
        report_status = "AUTO_STARTING"

    return DiagnosisRunResponse(
        id=run.id,
        project_id=run.project_id,
        status=run.status,
        status_message=getattr(run, "status_message", None),
        result_payload=payload,
        error_message=run.error_message,
        review_required=bool(run.review_tasks or run.policy_flags),
        policy_flags=[DiagnosisPolicyFlagRead.model_validate(serialize_policy_flag(item)) for item in run.policy_flags],
        citations=citations,
        response_trace_id=trace.id if trace else None,
        async_job_id=async_job.id if async_job else None,
        async_job_status=async_job.status if async_job else None,
        report_status=report_status,
        report_async_job_id=report_job.id if report_job else None,
        report_async_job_status=report_job.status if report_job else None,
        report_artifact_id=latest_report.id if latest_report else None,
        report_error_message=(
            (latest_report.error_message if latest_report and latest_report.status == "FAILED" else None)
            or (report_job.failure_reason if report_job and report_job.status == "failed" else None)
        ),
    )


def _ensure_default_report_bootstrap(db: Session, run: DiagnosisRun) -> None:
    if run.status != "COMPLETED" or not run.result_payload:
        return
    try:
        decision = ensure_default_diagnosis_report_job(
            db,
            run=run,
            owner_user_id=None,
            fallback_target_university=None,
            fallback_target_major=None,
            report_mode=INTERNAL_REPORT_MODE,
            include_appendix=True,
            include_citations=True,
        )
        logger.info("Diagnosis route ensured report bootstrap. run_id=%s decision=%s", run.id, decision)
    except Exception:  # noqa: BLE001
        logger.exception("Diagnosis route failed to ensure report bootstrap. run_id=%s", run.id)


def _maybe_process_diagnosis_job_inline(db: Session, run: DiagnosisRun) -> None:
    settings = get_settings()
    if not settings.allow_inline_job_processing:
        return
    if run.status in {"COMPLETED", "FAILED"}:
        return
    async_job = get_latest_job_for_resource(db, resource_type="diagnosis_run", resource_id=run.id)
    if async_job is None:
        return
    if async_job.status not in {"queued", "retrying"}:
        return
    process_async_job(db, async_job.id)


def _maybe_process_report_job_inline(db: Session, run: DiagnosisRun) -> None:
    settings = get_settings()
    if not settings.allow_inline_job_processing:
        return
    if run.status != "COMPLETED":
        return
    report_job = get_latest_job_for_resource(db, resource_type="diagnosis_report", resource_id=run.id)
    if report_job is None:
        return
    if report_job.status not in {"queued", "retrying"}:
        return
    process_async_job(db, report_job.id)


def _resolve_report_output_path(output_path: str) -> Path:
    try:
        resolved = ensure_resolved_within_base(resolve_project_path(output_path), get_export_root())
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Diagnosis report artifact not found.") from exc
    if not resolved.exists() or not resolved.is_file():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Diagnosis report artifact not found.")
    return resolved


@router.post("/run", response_model=DiagnosisRunResponse)
@router.post("/runs", response_model=DiagnosisRunResponse)
async def trigger_diagnosis(
    payload: DiagnosisRunRequest,
    wait_for_completion: bool = Query(default=False),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: None = Depends(rate_limit(bucket="diagnosis_runs", limit=10, window_seconds=300, guest_limit=2)),
) -> DiagnosisRunResponse:
    settings = get_settings()
    if wait_for_completion and not settings.allow_inline_job_processing:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inline job processing is disabled. Use the worker instead.",
        )

    try:
        project = get_project(db, payload.project_id, owner_user_id=current_user.id)
        if project is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found.")

        documents, full_text = combine_project_text(project.id, db)
        policy_scan_text = build_policy_scan_text(documents) or full_text

        run = DiagnosisRun(project_id=payload.project_id, status="PENDING")
        db.add(run)
        db.flush()

        findings = detect_policy_flags(policy_scan_text)
        flag_records = attach_policy_flags_to_run(db, run=run, project=project, user=current_user, findings=findings)
        review_task = ensure_review_task_for_flags(db, run=run, project=project, user=current_user, findings=findings)
        db.commit()
        db.refresh(run)
    except HTTPException as exc:
        detail = exc.detail
        if isinstance(detail, dict):
            raise
        raise HTTPException(
            status_code=exc.status_code,
            detail=build_error_detail(
                extract_error_code(detail)
                or ("PROJECT_NOT_FOUND" if exc.status_code == status.HTTP_404_NOT_FOUND else UniFoliErrorCode.INTERNAL_ERROR),
                extract_error_message(detail) or "Diagnosis setup failed.",
                stage="diagnosis_route_setup",
            ),
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=build_error_detail(
                UniFoliErrorCode.INTERNAL_ERROR,
                "Diagnosis setup failed before the async run could start.",
                stage="diagnosis_route_setup",
                debug_detail=str(exc),
                extra={"project_id": payload.project_id},
            ),
        ) from exc

    async_job = create_async_job(
        db,
        job_type=AsyncJobType.DIAGNOSIS.value,
        resource_type="diagnosis_run",
        resource_id=run.id,
        project_id=payload.project_id,
        payload={
            "run_id": run.id,
            "project_id": payload.project_id,
            "owner_user_id": current_user.id,
            "fallback_target_university": current_user.target_university or project.target_university,
            "fallback_target_major": current_user.target_major or project.target_major,
            "interest_universities": payload.interest_universities or current_user.interest_universities,
            "auto_report_mode": INTERNAL_REPORT_MODE,
            "auto_report_include_appendix": True,
            "auto_report_include_citations": True,
        },
    )
    if wait_for_completion:
        process_async_job(db, async_job.id)
        completed_run = _get_run_for_user(db, run.id, current_user.id)
        if completed_run is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Diagnosis run not found.")
        return _build_run_response(db, completed_run)

    dispatch_job_if_enabled(async_job.id)

    return DiagnosisRunResponse(
        id=run.id,
        project_id=run.project_id,
        status=run.status,
        status_message=getattr(run, "status_message", None),
        review_required=review_task is not None,
        policy_flags=[DiagnosisPolicyFlagRead.model_validate(serialize_policy_flag(item)) for item in flag_records],
        async_job_id=async_job.id,
        async_job_status=async_job.status,
        report_status=None,
        report_async_job_id=None,
        report_async_job_status=None,
        report_artifact_id=None,
        report_error_message=None,
    )


@router.post("/{diagnosis_id}/guided-plan", response_model=DiagnosisGuidedPlanResponse)
@router.post("/runs/{diagnosis_id}/guided-plan", response_model=DiagnosisGuidedPlanResponse)
async def build_guided_plan_route(
    diagnosis_id: str,
    payload: DiagnosisGuidedPlanRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> DiagnosisGuidedPlanResponse:
    run = _get_run_for_user(db, diagnosis_id, current_user.id)
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Diagnosis run not found.")
    if not run.result_payload:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Diagnosis results are not ready yet.")

    result = DiagnosisResultPayload.model_validate_json(run.result_payload)
    try:
        direction, topic, outline = build_guided_outline_plan(
            result=result,
            direction_id=payload.direction_id,
            topic_id=payload.topic_id,
            page_count=payload.page_count,
            export_format=payload.export_format,
            template_id=payload.template_id,
            include_provenance_appendix=payload.include_provenance_appendix,
            hide_internal_provenance_on_final_export=payload.hide_internal_provenance_on_final_export,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    if payload.open_text_note:
        outline.outline_markdown = (
            f"{outline.outline_markdown}\n\n## Optional Student Note\n{payload.open_text_note.strip()}"
        )

    draft = create_draft(
        db,
        project_id=run.project_id,
        payload=DraftCreate(
            title=topic.title,
            content_markdown=outline.outline_markdown,
        ),
    )
    outline.draft_id = draft.id
    outline.draft_title = draft.title
    return DiagnosisGuidedPlanResponse(
        diagnosis_run_id=run.id,
        project_id=run.project_id,
        direction=direction,
        topic=topic,
        outline=outline,
    )


@router.post("/{diagnosis_id}/report", response_model=ConsultantDiagnosisArtifactResponse)
@router.post("/runs/{diagnosis_id}/report", response_model=ConsultantDiagnosisArtifactResponse)
async def generate_consultant_report_route(
    diagnosis_id: str,
    payload: DiagnosisReportCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ConsultantDiagnosisArtifactResponse:
    run = _get_run_for_user(db, diagnosis_id, current_user.id)
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Diagnosis run not found.")
    if not run.result_payload:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Diagnosis results are not ready yet.")

    project = get_project(db, run.project_id, owner_user_id=current_user.id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found.")

    try:
        artifact = await generate_consultant_report_artifact(
            db,
            run=run,
            project=project,
            report_mode=_normalize_report_mode(payload.report_mode),  # type: ignore[arg-type]
            template_id=None,
            include_appendix=payload.include_appendix,
            include_citations=payload.include_citations,
            force_regenerate=payload.force_regenerate,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc

    return build_report_artifact_response(artifact=artifact, include_payload=True)


@router.get("/{diagnosis_id}/report", response_model=ConsultantDiagnosisArtifactResponse)
@router.get("/runs/{diagnosis_id}/report", response_model=ConsultantDiagnosisArtifactResponse)
async def get_consultant_report_route(
    diagnosis_id: str,
    artifact_id: str | None = Query(default=None),
    report_mode: str | None = Query(default=None),
    include_payload: bool = Query(default=True),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ConsultantDiagnosisArtifactResponse:
    run = _get_run_for_user(db, diagnosis_id, current_user.id)
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Diagnosis run not found.")

    # Keep auto-generated report delivery moving even when the frontend only polls this route.
    if run.status == "COMPLETED" and run.result_payload:
        _ensure_default_report_bootstrap(db, run)
        _maybe_process_report_job_inline(db, run)
        refreshed = _get_run_for_user(db, diagnosis_id, current_user.id)
        if refreshed is not None:
            run = refreshed

    normalized_mode = _normalize_report_mode(report_mode)
    artifact = (
        get_report_artifact_by_id(db, diagnosis_run_id=run.id, artifact_id=artifact_id)
        if artifact_id
        else get_latest_report_artifact_for_run(
            db,
            diagnosis_run_id=run.id,
            report_mode=normalized_mode,
        )
    )
    if artifact is None and artifact_id:
        logger.warning(
            "Diagnosis report artifact id was stale or missing. run_id=%s artifact_id=%s mode=%s",
            run.id,
            artifact_id,
            normalized_mode,
        )
        artifact = get_latest_report_artifact_for_run(
            db,
            diagnosis_run_id=run.id,
            report_mode=normalized_mode,
        )

    if artifact is None and run.status == "COMPLETED" and run.result_payload:
        project = get_project(db, run.project_id, owner_user_id=current_user.id)
        if project is not None:
            try:
                artifact = await generate_consultant_report_artifact(
                    db,
                    run=run,
                    project=project,
                    report_mode=normalized_mode,  # type: ignore[arg-type]
                    template_id=None,
                    include_appendix=True,
                    include_citations=True,
                    force_regenerate=False,
                )
                logger.info(
                    "Recovered diagnosis report read by generating missing artifact. run_id=%s artifact_id=%s mode=%s",
                    run.id,
                    artifact.id,
                    normalized_mode,
                )
            except Exception:  # noqa: BLE001
                logger.exception(
                    "Failed to recover diagnosis report artifact on read. run_id=%s artifact_id=%s mode=%s",
                    run.id,
                    artifact_id,
                    normalized_mode,
                )
    if artifact is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Diagnosis report artifact not found.")
    return build_report_artifact_response(artifact=artifact, include_payload=include_payload)


@router.get("/{diagnosis_id}/report.pdf")
@router.get("/runs/{diagnosis_id}/report.pdf")
async def download_consultant_report_pdf_route(
    diagnosis_id: str,
    artifact_id: str | None = Query(default=None),
    report_mode: str = Query(default=INTERNAL_REPORT_MODE),
    template_id: str | None = Query(default=None),
    include_appendix: bool = Query(default=True),
    include_citations: bool = Query(default=True),
    force_regenerate: bool = Query(default=False),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Response:
    run = _get_run_for_user(db, diagnosis_id, current_user.id)
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Diagnosis run not found.")
    if not run.result_payload:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Diagnosis results are not ready yet.")

    # Ensure queued auto-report jobs are progressed for download requests as well.
    if run.status == "COMPLETED":
        _ensure_default_report_bootstrap(db, run)
        _maybe_process_report_job_inline(db, run)
        refreshed = _get_run_for_user(db, diagnosis_id, current_user.id)
        if refreshed is not None:
            run = refreshed

    normalized_mode = _normalize_report_mode(report_mode)

    artifact = (
        get_report_artifact_by_id(db, diagnosis_run_id=run.id, artifact_id=artifact_id)
        if artifact_id
        else get_latest_report_artifact_for_run(
            db,
            diagnosis_run_id=run.id,
            report_mode=normalized_mode,
        )
    )
    if artifact is None and artifact_id:
        logger.warning(
            "Diagnosis report download received stale artifact id. run_id=%s artifact_id=%s mode=%s",
            run.id,
            artifact_id,
            normalized_mode,
        )
        artifact = get_latest_report_artifact_for_run(
            db,
            diagnosis_run_id=run.id,
            report_mode=normalized_mode,
        )

    if (
        artifact is None
        or force_regenerate
        or artifact.status != "READY"
        or bool(artifact.include_appendix) != include_appendix
        or bool(artifact.include_citations) != include_citations
        or (report_artifact_storage_key(artifact) is None and report_artifact_file_path(artifact) is None)
    ):
        project = get_project(db, run.project_id, owner_user_id=current_user.id)
        if project is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found.")
        artifact = await generate_consultant_report_artifact(
            db,
            run=run,
            project=project,
            report_mode=normalized_mode,  # type: ignore[arg-type]
            template_id=None,
            include_appendix=include_appendix,
            include_citations=include_citations,
            force_regenerate=force_regenerate,
        )

    output_path = report_artifact_file_path(artifact)
    storage_bytes = load_report_artifact_pdf_bytes(artifact)
    if storage_bytes is None and artifact.status == "READY":
        storage_key = report_artifact_storage_key(artifact)
        if storage_key or output_path:
            logger.warning(
                "Diagnosis report binary was missing for READY artifact. Attempting one-time regeneration. "
                "run_id=%s artifact_id=%s mode=%s",
                run.id,
                artifact.id,
                normalized_mode,
            )
            project = get_project(db, run.project_id, owner_user_id=current_user.id)
            if project is not None:
                artifact = await generate_consultant_report_artifact(
                    db,
                    run=run,
                    project=project,
                    report_mode=normalized_mode,  # type: ignore[arg-type]
                    template_id=None,
                    include_appendix=include_appendix,
                    include_citations=include_citations,
                    force_regenerate=True,
                )
                output_path = report_artifact_file_path(artifact)
                storage_bytes = load_report_artifact_pdf_bytes(artifact)
    student_name = _resolve_download_student_name(db, run.project_id)
    if storage_bytes is not None:
        filename = _build_diagnosis_download_filename(current_user, student_name=student_name)
        return Response(
            content=storage_bytes,
            media_type="application/pdf",
            headers={
                "Content-Disposition": _content_disposition_header(filename),
            },
        )

    if output_path is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=artifact.error_message or "Diagnosis report artifact is not ready.",
        )

    resolved = _resolve_report_output_path(str(output_path))
    filename = _build_diagnosis_download_filename(current_user, student_name=student_name)
    return FileResponse(
        path=resolved,
        filename=filename,
        media_type="application/pdf",
        headers={"Content-Disposition": _content_disposition_header(filename)},
    )


@router.get("/{diagnosis_id}", response_model=DiagnosisRunResponse)
@router.get("/runs/{diagnosis_id}", response_model=DiagnosisRunResponse)
async def get_diagnosis_status(
    diagnosis_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> DiagnosisRunResponse:
    run = _get_run_for_user(db, diagnosis_id, current_user.id)
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Diagnosis run not found.")
    _maybe_process_diagnosis_job_inline(db, run)
    run = _get_run_for_user(db, diagnosis_id, current_user.id)
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Diagnosis run not found.")
    _ensure_default_report_bootstrap(db, run)
    _maybe_process_report_job_inline(db, run)
    run = _get_run_for_user(db, diagnosis_id, current_user.id)
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Diagnosis run not found.")
    return _build_run_response(db, run)
@router.get("/project/{project_id}/latest", response_model=DiagnosisRunResponse)
async def get_latest_diagnosis_for_project(
    project_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> DiagnosisRunResponse:
    run = db.scalar(
        select(DiagnosisRun)
        .join(Project, DiagnosisRun.project_id == Project.id)
        .where(Project.id == project_id, Project.owner_user_id == current_user.id)
        .order_by(DiagnosisRun.created_at.desc())
        .limit(1)
        .options(
            selectinload(DiagnosisRun.policy_flags),
            selectinload(DiagnosisRun.review_tasks),
            selectinload(DiagnosisRun.response_traces).selectinload(ResponseTrace.citations),
        )
    )
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No diagnosis run found for this project.")
    _maybe_process_diagnosis_job_inline(db, run)
    run = db.scalar(
        select(DiagnosisRun)
        .join(Project, DiagnosisRun.project_id == Project.id)
        .where(Project.id == project_id, Project.owner_user_id == current_user.id)
        .order_by(DiagnosisRun.created_at.desc())
        .limit(1)
        .options(
            selectinload(DiagnosisRun.policy_flags),
            selectinload(DiagnosisRun.review_tasks),
            selectinload(DiagnosisRun.response_traces).selectinload(ResponseTrace.citations),
        )
    )
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No diagnosis run found for this project.")
    _ensure_default_report_bootstrap(db, run)
    _maybe_process_report_job_inline(db, run)
    run = db.scalar(
        select(DiagnosisRun)
        .join(Project, DiagnosisRun.project_id == Project.id)
        .where(Project.id == project_id, Project.owner_user_id == current_user.id)
        .order_by(DiagnosisRun.created_at.desc())
        .limit(1)
        .options(
            selectinload(DiagnosisRun.policy_flags),
            selectinload(DiagnosisRun.review_tasks),
            selectinload(DiagnosisRun.response_traces).selectinload(ResponseTrace.citations),
        )
    )
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No diagnosis run found for this project.")
    return _build_run_response(db, run)
