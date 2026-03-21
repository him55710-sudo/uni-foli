from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from db.models.audit import Citation, PolicyFlag, ResponseTrace
from db.models.security import DeletionEvent, DeletionRequest, PrivacyScan
from db.models.student import StudentAnalysisRun, StudentArtifact, StudentFile
from domain.enums import DeletionMode, DeletionRequestStatus
from services.admissions.access_control_service import access_control_service
from services.admissions.file_object_service import file_object_service
from services.admissions.utils import ensure_uuid


class DeletionService:
    def list_requests(self, session: Session, *, tenant_id=None, include_global: bool = False) -> list[DeletionRequest]:
        stmt = select(DeletionRequest).where(DeletionRequest.deleted_at.is_(None)).order_by(DeletionRequest.created_at.desc())
        if tenant_id is not None and not include_global:
            stmt = stmt.where(DeletionRequest.tenant_id == ensure_uuid(tenant_id))
        return list(session.scalars(stmt))

    def list_events(self, session: Session, *, tenant_id=None) -> list[DeletionEvent]:
        stmt = select(DeletionEvent).where(DeletionEvent.deleted_at.is_(None)).order_by(DeletionEvent.created_at.desc())
        if tenant_id is not None:
            stmt = stmt.where(DeletionEvent.tenant_id == ensure_uuid(tenant_id))
        return list(session.scalars(stmt))

    def create_request(
        self,
        session: Session,
        *,
        principal,
        target_kind: str,
        target_id: str,
        deletion_mode: DeletionMode,
        reason: str,
    ) -> DeletionRequest:
        target_uuid = ensure_uuid(target_id)
        if target_kind == "student_file":
            student_file = session.get(StudentFile, target_uuid)
            if student_file is None or student_file.deleted_at is not None:
                raise ValueError("Student file not found.")
            access_control_service.require_same_tenant_student_file(principal, student_file)
        elif target_kind == "analysis_run":
            run = session.get(StudentAnalysisRun, target_uuid)
            if run is None or run.deleted_at is not None:
                raise ValueError("Analysis run not found.")
            access_control_service.require_same_tenant_analysis_run(principal, run)
        else:
            raise ValueError("Unsupported deletion target.")

        request = DeletionRequest(
            tenant_id=principal.tenant_id,
            requested_by_account_id=principal.account_id,
            target_kind=target_kind,
            target_id=target_uuid,
            deletion_mode=deletion_mode,
            reason=reason,
            metadata_json={},
        )
        session.add(request)
        session.flush()
        session.refresh(request)
        return request

    def execute_request(self, session: Session, *, deletion_request_id: str, principal) -> DeletionRequest | None:
        deletion_request = session.get(DeletionRequest, ensure_uuid(deletion_request_id))
        if deletion_request is None or deletion_request.deleted_at is not None:
            return None
        access_control_service.require_tenant_access(principal, deletion_request.tenant_id)
        deletion_request.status = DeletionRequestStatus.PROCESSING
        session.flush()

        if deletion_request.target_kind == "student_file":
            self._delete_student_file(session, deletion_request=deletion_request)
        elif deletion_request.target_kind == "analysis_run":
            self._delete_analysis_run(session, deletion_request=deletion_request)
        else:
            deletion_request.status = DeletionRequestStatus.REJECTED
            deletion_request.metadata_json = {"error": f"Unsupported target_kind: {deletion_request.target_kind}"}
            session.flush()
            return deletion_request

        if deletion_request.status == DeletionRequestStatus.PROCESSING:
            deletion_request.status = DeletionRequestStatus.COMPLETED
            deletion_request.processed_at = datetime.now(UTC)
        session.flush()
        session.refresh(deletion_request)
        return deletion_request

    def _delete_student_file(self, session: Session, *, deletion_request: DeletionRequest) -> None:
        student_file = session.get(StudentFile, deletion_request.target_id)
        if student_file is None:
            deletion_request.status = DeletionRequestStatus.FAILED
            deletion_request.metadata_json = {"error": "Student file not found."}
            return
        now = datetime.now(UTC)
        student_file.deletion_requested_at = now
        student_file.deleted_at = now
        self._create_event(
            session,
            deletion_request=deletion_request,
            target_kind="student_file",
            target_id=student_file.id,
            file_object_id=student_file.file_object_id,
            action_kind="soft_delete",
            message="Student file soft-deleted.",
        )

        artifacts = list(
            session.scalars(
                select(StudentArtifact).where(StudentArtifact.student_file_id == student_file.id).where(StudentArtifact.deleted_at.is_(None))
            )
        )
        for artifact in artifacts:
            artifact.deleted_at = now
            self._create_event(
                session,
                deletion_request=deletion_request,
                target_kind="student_artifact",
                target_id=artifact.id,
                file_object_id=None,
                action_kind="soft_delete",
                message="Student artifact soft-deleted.",
            )

        for scan in session.scalars(
            select(PrivacyScan).where(PrivacyScan.student_file_id == student_file.id).where(PrivacyScan.deleted_at.is_(None))
        ):
            scan.deleted_at = now

        analysis_runs = list(
            session.scalars(
                select(StudentAnalysisRun)
                .where(StudentAnalysisRun.primary_student_file_id == student_file.id)
                .where(StudentAnalysisRun.deleted_at.is_(None))
            )
        )
        for run in analysis_runs:
            self._delete_analysis_run_resources(session, run=run, deletion_request=deletion_request, now=now)

        if student_file.file_object is not None:
            if deletion_request.deletion_mode == DeletionMode.HARD_DELETE:
                removed = file_object_service.hard_delete_if_local(session, file_object=student_file.file_object)
                self._create_event(
                    session,
                    deletion_request=deletion_request,
                    target_kind="file_object",
                    target_id=student_file.file_object.id,
                    file_object_id=student_file.file_object.id,
                    action_kind="hard_delete" if removed else "soft_delete",
                    message=(
                        "Underlying file object was removed from local storage."
                        if removed
                        else "Underlying file object remained referenced and was only soft-deleted."
                    ),
                )
            else:
                file_object_service.soft_delete_file_object(session, file_object=student_file.file_object)

    def _delete_analysis_run(self, session: Session, *, deletion_request: DeletionRequest) -> None:
        run = session.get(StudentAnalysisRun, deletion_request.target_id)
        if run is None:
            deletion_request.status = DeletionRequestStatus.FAILED
            deletion_request.metadata_json = {"error": "Analysis run not found."}
            return
        self._delete_analysis_run_resources(session, run=run, deletion_request=deletion_request, now=datetime.now(UTC))

    def _delete_analysis_run_resources(
        self,
        session: Session,
        *,
        run: StudentAnalysisRun,
        deletion_request: DeletionRequest,
        now: datetime,
    ) -> None:
        run.deletion_requested_at = now
        run.deleted_at = now
        self._create_event(
            session,
            deletion_request=deletion_request,
            target_kind="student_analysis_run",
            target_id=run.id,
            file_object_id=None,
            action_kind="soft_delete",
            message="Student analysis run soft-deleted.",
        )
        for citation in session.scalars(select(Citation).where(Citation.analysis_run_id == run.id).where(Citation.deleted_at.is_(None))):
            citation.deleted_at = now
        for policy_flag in session.scalars(
            select(PolicyFlag).where(PolicyFlag.student_analysis_run_id == run.id).where(PolicyFlag.deleted_at.is_(None))
        ):
            policy_flag.deleted_at = now
        for trace in session.scalars(
            select(ResponseTrace).where(ResponseTrace.tenant_id == run.tenant_id).where(ResponseTrace.deleted_at.is_(None))
        ):
            if trace.query_text == f"student_analysis_run:{run.id}":
                trace.deleted_at = now

    def _create_event(
        self,
        session: Session,
        *,
        deletion_request: DeletionRequest,
        target_kind: str,
        target_id,
        file_object_id,
        action_kind: str,
        message: str,
    ) -> None:
        session.add(
            DeletionEvent(
                deletion_request_id=deletion_request.id,
                tenant_id=deletion_request.tenant_id,
                target_kind=target_kind,
                target_id=target_id,
                file_object_id=file_object_id,
                action_kind=action_kind,
                message=message,
                metadata_json={},
            )
        )
        session.flush()


deletion_service = DeletionService()
