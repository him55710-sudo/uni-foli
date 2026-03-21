from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from db.models.security import PrivacyScan, Tenant
from db.models.student import StudentArtifact, StudentFile
from domain.enums import PrivacyMaskingMode, StudentFileStatus
from parsers.base import ParserContext
from parsers.registry import parser_registry
from services.admissions.file_object_service import file_object_service
from services.admissions.normalization_service import normalization_service
from services.admissions.privacy_service import privacy_service
from services.admissions.utils import ensure_uuid


class StudentFileService:
    async def upload_student_file(
        self,
        session: Session,
        *,
        upload,
        artifact_type=None,
        principal,
        school_year_hint: int | None = None,
        admissions_target_year: int | None = None,
    ) -> StudentFile:
        tenant = session.get(Tenant, principal.tenant_id)
        if tenant is None:
            raise ValueError("Tenant not found.")

        retention_expires_at = datetime.now(UTC) + timedelta(days=tenant.default_retention_days)
        file_object, is_duplicate = await file_object_service.store_upload(
            session,
            upload=upload,
            namespace="student-files",
            metadata_json={"tenant_id": str(tenant.id)},
            tenant_id=tenant.id,
            dedupe_scope="none",
        )
        file_object.tenant_id = tenant.id
        file_object.retention_expires_at = retention_expires_at
        file_object.purge_after_at = retention_expires_at

        payload = b""
        if file_object.local_path:
            payload = Path(file_object.local_path).read_bytes()

        resolved_artifact_type = artifact_type or normalization_service.classify_student_artifact_type(
            upload.filename or "",
            upload.content_type,
        )

        student_file = StudentFile(
            tenant_id=tenant.id,
            created_by_account_id=principal.account_id,
            owner_key=principal.email,
            file_object_id=file_object.id,
            artifact_type=resolved_artifact_type,
            upload_filename=upload.filename or "upload.bin",
            mime_type=upload.content_type or "application/octet-stream",
            school_year_hint=school_year_hint,
            admissions_target_year=admissions_target_year,
            privacy_masking_mode=tenant.masking_mode,
            pii_detected=False,
            retention_expires_at=retention_expires_at,
            purge_after_at=retention_expires_at,
            status=StudentFileStatus.UPLOADED,
            parse_summary={"is_duplicate_file_object": is_duplicate},
        )
        session.add(student_file)
        session.flush()

        try:
            parsed = parser_registry.parse(
                payload,
                ParserContext(
                    filename=upload.filename or "upload.bin",
                    mime_type=upload.content_type,
                    file_hash=file_object.sha256,
                    local_path=file_object.local_path,
                ),
            )
            pii_detected = False
            student_file.status = StudentFileStatus.PARSED
            for block in parsed.blocks:
                privacy_result = privacy_service.scan_and_mask(
                    session,
                    tenant=tenant,
                    route_name="student_file.upload",
                    text=block.cleaned_text,
                    student_file_id=student_file.id,
                )
                pii_detected = pii_detected or privacy_result.pii_detected
                stored_cleaned_text = (
                    privacy_result.index_text
                    if tenant.masking_mode in {PrivacyMaskingMode.MASK_FOR_INDEX, PrivacyMaskingMode.MASK_ALL}
                    else block.cleaned_text
                )
                artifact = StudentArtifact(
                    tenant_id=tenant.id,
                    student_file_id=student_file.id,
                    artifact_type=resolved_artifact_type,
                    artifact_index=block.block_index,
                    title=block.title,
                    section_label=" > ".join(block.heading_path) if block.heading_path else None,
                    page_start=block.page_number,
                    page_end=block.page_number,
                    char_start=block.char_start,
                    char_end=block.char_end,
                    raw_text=block.raw_text,
                    cleaned_text=stored_cleaned_text,
                    masked_text=privacy_result.masked_text if privacy_result.masked_text != block.cleaned_text else None,
                    pii_detected=privacy_result.pii_detected,
                    metadata_json={**block.metadata, "privacy_engine": privacy_result.engine_name},
                )
                session.add(artifact)
                session.flush()
                if privacy_result.scan_id is not None:
                    scan = session.get(PrivacyScan, privacy_result.scan_id)
                    if scan is not None:
                        scan.student_artifact_id = artifact.id

            student_file.pii_detected = pii_detected
            student_file.parse_summary = {
                "parser_name": parsed.parser_name,
                "title": parsed.title,
                "block_count": len(parsed.blocks),
                "parser_trace": parsed.parser_trace,
                "parser_fallback_reason": parsed.fallback_reason,
                "pii_detected": pii_detected,
                "privacy_masking_mode": tenant.masking_mode.value,
            }
        except Exception as exc:
            student_file.status = StudentFileStatus.REVIEW_REQUIRED
            student_file.parse_summary = {"error": privacy_service.mask_for_logs(str(exc))}

        session.flush()
        session.refresh(student_file)
        return student_file

    def get_student_file(self, session: Session, student_file_id: str, *, include_deleted: bool = False) -> StudentFile | None:
        student_file = session.get(StudentFile, ensure_uuid(student_file_id))
        if student_file is None:
            return None
        if not include_deleted and student_file.deleted_at is not None:
            return None
        return student_file

    def list_student_files(self, session: Session, *, tenant_id=None, include_deleted: bool = False) -> list[StudentFile]:
        stmt = select(StudentFile).order_by(StudentFile.created_at.desc())
        if tenant_id is not None:
            stmt = stmt.where(StudentFile.tenant_id == ensure_uuid(tenant_id))
        if not include_deleted:
            stmt = stmt.where(StudentFile.deleted_at.is_(None))
        return list(session.scalars(stmt))


student_file_service = StudentFileService()
