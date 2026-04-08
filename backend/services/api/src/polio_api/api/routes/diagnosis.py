from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from polio_api.api.deps import get_current_user, get_db
from polio_api.core.config import get_settings
from polio_api.core.rate_limit import rate_limit
from polio_api.core.security import ensure_resolved_within_base
from polio_api.db.models.diagnosis_run import DiagnosisRun
from polio_api.db.models.project import Project
from polio_api.db.models.response_trace import ResponseTrace
from polio_api.db.models.user import User
from polio_api.schemas.draft import DraftCreate
from polio_api.schemas.diagnosis import (
    ConsultantDiagnosisArtifactResponse,
    DiagnosisReportCreateRequest,
    DiagnosisGuidedPlanRequest,
    DiagnosisGuidedPlanResponse,
    DiagnosisPolicyFlagRead,
    DiagnosisResultPayload,
    DiagnosisRunRequest,
    DiagnosisRunResponse,
)
from polio_api.services.async_job_service import (
    create_async_job,
    dispatch_job_if_enabled,
    get_latest_job_for_resource,
    process_async_job,
)
from polio_api.services.diagnosis_runtime_service import build_policy_scan_text, combine_project_text
from polio_api.services.diagnosis_report_service import (
    build_report_artifact_response,
    generate_consultant_report_artifact,
    get_latest_report_artifact_for_run,
    get_report_artifact_by_id,
    report_artifact_file_path,
)
from polio_api.services.diagnosis_service import (
    DiagnosisCitation,
    attach_policy_flags_to_run,
    build_guided_outline_plan,
    detect_policy_flags,
    ensure_review_task_for_flags,
    latest_response_trace,
    serialize_citation,
    serialize_policy_flag,
)
from polio_api.services.draft_service import create_draft
from polio_api.services.project_service import get_project
from polio_domain.enums import AsyncJobType
from polio_shared.paths import get_export_root, resolve_project_path

router = APIRouter()


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
    return DiagnosisRunResponse(
        id=run.id,
        project_id=run.project_id,
        status=run.status,
        result_payload=payload,
        error_message=run.error_message,
        review_required=bool(run.review_tasks or run.policy_flags),
        policy_flags=[DiagnosisPolicyFlagRead.model_validate(serialize_policy_flag(item)) for item in run.policy_flags],
        citations=citations,
        response_trace_id=trace.id if trace else None,
        async_job_id=async_job.id if async_job else None,
        async_job_status=async_job.status if async_job else None,
    )


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
        review_required=review_task is not None,
        policy_flags=[DiagnosisPolicyFlagRead.model_validate(serialize_policy_flag(item)) for item in flag_records],
        async_job_id=async_job.id,
        async_job_status=async_job.status,
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
            report_mode=payload.report_mode,
            template_id=payload.template_id,
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

    artifact = (
        get_report_artifact_by_id(db, diagnosis_run_id=run.id, artifact_id=artifact_id)
        if artifact_id
        else get_latest_report_artifact_for_run(
            db,
            diagnosis_run_id=run.id,
            report_mode=report_mode if report_mode in {"compact", "premium_10p"} else None,
        )
    )
    if artifact is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Diagnosis report artifact not found.")
    return build_report_artifact_response(artifact=artifact, include_payload=include_payload)


@router.get("/{diagnosis_id}/report.pdf")
@router.get("/runs/{diagnosis_id}/report.pdf")
async def download_consultant_report_pdf_route(
    diagnosis_id: str,
    artifact_id: str | None = Query(default=None),
    report_mode: str = Query(default="premium_10p"),
    template_id: str | None = Query(default=None),
    include_appendix: bool = Query(default=True),
    include_citations: bool = Query(default=True),
    force_regenerate: bool = Query(default=False),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> FileResponse:
    run = _get_run_for_user(db, diagnosis_id, current_user.id)
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Diagnosis run not found.")
    if not run.result_payload:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Diagnosis results are not ready yet.")

    if report_mode not in {"compact", "premium_10p"}:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Invalid report mode.")

    project = get_project(db, run.project_id, owner_user_id=current_user.id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found.")

    artifact = (
        get_report_artifact_by_id(db, diagnosis_run_id=run.id, artifact_id=artifact_id)
        if artifact_id
        else get_latest_report_artifact_for_run(
            db,
            diagnosis_run_id=run.id,
            report_mode=report_mode,
        )
    )

    if (
        artifact is None
        or force_regenerate
        or artifact.status != "READY"
        or bool(artifact.include_appendix) != include_appendix
        or bool(artifact.include_citations) != include_citations
        or (template_id is not None and artifact.template_id != template_id)
        or report_artifact_file_path(artifact) is None
    ):
        artifact = await generate_consultant_report_artifact(
            db,
            run=run,
            project=project,
            report_mode=report_mode,  # type: ignore[arg-type]
            template_id=template_id,
            include_appendix=include_appendix,
            include_citations=include_citations,
            force_regenerate=force_regenerate,
        )

    output_path = report_artifact_file_path(artifact)
    if output_path is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=artifact.error_message or "Diagnosis report artifact is not ready.",
        )

    resolved = _resolve_report_output_path(str(output_path))
    filename = f"consultant-diagnosis-{run.id}-v{artifact.version}.pdf"
    return FileResponse(path=resolved, filename=filename, media_type="application/pdf")


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
    return _build_run_response(db, run)
