from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from db.models.security import Tenant
from db.models.student import StudentAnalysisRun, StudentFile
from domain.enums import StudentAnalysisRunStatus
from services.admissions.access_control_service import access_control_service
from services.admissions.utils import ensure_uuid


class AnalysisRunService:
    def create_run(
        self,
        session: Session,
        *,
        run_type,
        primary_student_file_id: str | None,
        tenant_id,
        created_by_account_id,
        owner_key: str,
        model_name: str,
        prompt_template_key: str,
        retention_expires_at,
        input_snapshot: dict[str, object],
    ) -> StudentAnalysisRun:
        run = StudentAnalysisRun(
            tenant_id=tenant_id,
            created_by_account_id=created_by_account_id,
            run_type=run_type,
            primary_student_file_id=ensure_uuid(primary_student_file_id),
            owner_key=owner_key,
            model_name=model_name,
            prompt_template_key=prompt_template_key,
            retention_expires_at=retention_expires_at,
            input_snapshot=input_snapshot,
            output_summary={},
            status=StudentAnalysisRunStatus.QUEUED,
        )
        session.add(run)
        session.flush()
        session.refresh(run)
        return run

    def create_run_for_principal(
        self,
        session: Session,
        *,
        principal,
        run_type,
        primary_student_file_id: str | None,
        model_name: str,
        prompt_template_key: str,
        input_snapshot: dict[str, object],
    ) -> StudentAnalysisRun:
        tenant = session.get(Tenant, principal.tenant_id)
        if tenant is None:
            raise ValueError("Tenant not found.")
        student_file = None
        if primary_student_file_id is not None:
            student_file = session.get(StudentFile, ensure_uuid(primary_student_file_id))
            if student_file is None or student_file.deleted_at is not None:
                raise ValueError("Student file not found.")
            access_control_service.require_same_tenant_student_file(principal, student_file)
        retention_expires_at = datetime.now(UTC) + timedelta(days=tenant.default_retention_days)
        return self.create_run(
            session,
            run_type=run_type,
            primary_student_file_id=primary_student_file_id,
            tenant_id=tenant.id,
            created_by_account_id=principal.account_id,
            owner_key=principal.email,
            model_name=model_name,
            prompt_template_key=prompt_template_key,
            retention_expires_at=retention_expires_at,
            input_snapshot=input_snapshot,
        )

    def get_run(self, session: Session, run_id: str, *, include_deleted: bool = False) -> StudentAnalysisRun | None:
        run = session.get(StudentAnalysisRun, ensure_uuid(run_id))
        if run is None:
            return None
        if not include_deleted and run.deleted_at is not None:
            return None
        return run

    def list_runs(
        self,
        session: Session,
        *,
        tenant_id=None,
        include_deleted: bool = False,
        limit: int = 100,
    ) -> list[StudentAnalysisRun]:
        stmt = select(StudentAnalysisRun).order_by(StudentAnalysisRun.created_at.desc()).limit(limit)
        if tenant_id is not None:
            stmt = stmt.where(StudentAnalysisRun.tenant_id == ensure_uuid(tenant_id))
        if not include_deleted:
            stmt = stmt.where(StudentAnalysisRun.deleted_at.is_(None))
        return list(session.scalars(stmt))

    def list_queued_runs(self, session: Session, *, limit: int = 20) -> list[StudentAnalysisRun]:
        stmt = (
            select(StudentAnalysisRun)
            .where(StudentAnalysisRun.status == StudentAnalysisRunStatus.QUEUED)
            .where(StudentAnalysisRun.deleted_at.is_(None))
            .order_by(StudentAnalysisRun.created_at.asc())
            .limit(limit)
        )
        return list(session.scalars(stmt))


analysis_run_service = AnalysisRunService()
