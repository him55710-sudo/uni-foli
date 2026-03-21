from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_db_session, require_authenticated_principal
from app.core.config import get_settings
from app.schemas.analysis import AnalysisRunCreate, AnalysisRunRead
from app.schemas.privacy import DeletionRequestCreate, DeletionRequestRead
from services.admissions.access_control_service import access_control_service
from services.admissions.analysis_run_service import analysis_run_service
from services.admissions.deletion_service import deletion_service
from services.admissions.student_analysis_service import student_analysis_service


router = APIRouter()


@router.get("", response_model=list[AnalysisRunRead])
def list_analysis_runs(
    principal=Depends(require_authenticated_principal),
    session: Session = Depends(get_db_session),
) -> list[AnalysisRunRead]:
    items = analysis_run_service.list_runs(session, tenant_id=principal.tenant_id)
    return [AnalysisRunRead.model_validate(item) for item in items]


@router.post("", response_model=AnalysisRunRead, status_code=status.HTTP_201_CREATED)
def create_analysis_run(
    payload: AnalysisRunCreate,
    principal=Depends(require_authenticated_principal),
    session: Session = Depends(get_db_session),
) -> AnalysisRunRead:
    settings = get_settings()
    try:
        run = analysis_run_service.create_run_for_principal(
            session,
            principal=principal,
            run_type=payload.run_type,
            primary_student_file_id=payload.primary_student_file_id,
            model_name=settings.extraction_model_name,
            prompt_template_key="student_analysis_v1",
            input_snapshot=payload.input_snapshot,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    session.commit()
    session.refresh(run)
    return AnalysisRunRead.model_validate(run)


@router.get("/{run_id}", response_model=AnalysisRunRead)
def get_analysis_run(
    run_id: str,
    principal=Depends(require_authenticated_principal),
    session: Session = Depends(get_db_session),
) -> AnalysisRunRead:
    run = analysis_run_service.get_run(session, run_id)
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Analysis run not found")
    try:
        access_control_service.require_same_tenant_analysis_run(principal, run)
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    return AnalysisRunRead.model_validate(run)


@router.post("/{run_id}/run", response_model=AnalysisRunRead)
def run_analysis_run(
    run_id: str,
    principal=Depends(require_authenticated_principal),
    session: Session = Depends(get_db_session),
) -> AnalysisRunRead:
    run = analysis_run_service.get_run(session, run_id)
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Analysis run not found")
    try:
        access_control_service.require_same_tenant_analysis_run(principal, run)
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    processed = student_analysis_service.process_run(session, run)
    session.commit()
    return AnalysisRunRead.model_validate(processed)


@router.post("/{run_id}/deletion-requests", response_model=DeletionRequestRead, status_code=status.HTTP_201_CREATED)
def create_analysis_run_deletion_request(
    run_id: str,
    payload: DeletionRequestCreate,
    principal=Depends(require_authenticated_principal),
    session: Session = Depends(get_db_session),
) -> DeletionRequestRead:
    if payload.target_kind != "analysis_run" or str(payload.target_id) != run_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Deletion request target does not match route.")
    try:
        deletion_request = deletion_service.create_request(
            session,
            principal=principal,
            target_kind=payload.target_kind,
            target_id=run_id,
            deletion_mode=payload.deletion_mode,
            reason=payload.reason,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    session.commit()
    return DeletionRequestRead.model_validate(deletion_request)
