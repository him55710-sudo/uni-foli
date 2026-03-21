from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.api.deps import get_db_session, require_authenticated_principal
from app.schemas.privacy import DeletionRequestCreate, DeletionRequestRead
from app.schemas.student_file import StudentFileRead
from domain.enums import StudentArtifactType
from services.admissions.access_control_service import access_control_service
from services.admissions.deletion_service import deletion_service
from services.admissions.student_file_service import student_file_service


router = APIRouter()


@router.get("", response_model=list[StudentFileRead])
def list_student_files(
    principal=Depends(require_authenticated_principal),
    session: Session = Depends(get_db_session),
) -> list[StudentFileRead]:
    items = student_file_service.list_student_files(session, tenant_id=principal.tenant_id)
    return [StudentFileRead.model_validate(item) for item in items]


@router.post("", response_model=StudentFileRead, status_code=status.HTTP_201_CREATED)
async def upload_student_file(
    file: UploadFile = File(...),
    artifact_type: StudentArtifactType | None = Form(default=None),
    school_year_hint: int | None = Form(default=None),
    admissions_target_year: int | None = Form(default=None),
    principal=Depends(require_authenticated_principal),
    session: Session = Depends(get_db_session),
) -> StudentFileRead:
    student_file = await student_file_service.upload_student_file(
        session,
        upload=file,
        artifact_type=artifact_type,
        principal=principal,
        school_year_hint=school_year_hint,
        admissions_target_year=admissions_target_year,
    )
    session.commit()
    session.refresh(student_file)
    return StudentFileRead.model_validate(student_file)


@router.get("/{student_file_id}", response_model=StudentFileRead)
def get_student_file(
    student_file_id: str,
    principal=Depends(require_authenticated_principal),
    session: Session = Depends(get_db_session),
) -> StudentFileRead:
    student_file = student_file_service.get_student_file(session, student_file_id)
    if student_file is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student file not found")
    try:
        access_control_service.require_same_tenant_student_file(principal, student_file)
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    return StudentFileRead.model_validate(student_file)


@router.post("/{student_file_id}/deletion-requests", response_model=DeletionRequestRead, status_code=status.HTTP_201_CREATED)
def create_student_file_deletion_request(
    student_file_id: str,
    payload: DeletionRequestCreate,
    principal=Depends(require_authenticated_principal),
    session: Session = Depends(get_db_session),
) -> DeletionRequestRead:
    if payload.target_kind != "student_file" or str(payload.target_id) != student_file_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Deletion request target does not match route.")
    try:
        deletion_request = deletion_service.create_request(
            session,
            principal=principal,
            target_kind=payload.target_kind,
            target_id=student_file_id,
            deletion_mode=payload.deletion_mode,
            reason=payload.reason,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    session.commit()
    return DeletionRequestRead.model_validate(deletion_request)
