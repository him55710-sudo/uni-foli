from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from db.models.content import DocumentVersion, FileObject
from db.models.crawl import DiscoveredUrl
from db.models.student import StudentFile
from domain.enums import FileObjectStatus, StorageProvider
from services.admissions.storage_service import storage_service


DedupeScope = Literal["global", "tenant", "none"]


class FileObjectService:
    async def store_upload(
        self,
        session: Session,
        *,
        upload,
        namespace: str,
        source_url: str | None = None,
        metadata_json: dict[str, object] | None = None,
        tenant_id=None,
        dedupe_scope: DedupeScope = "global",
    ) -> tuple[FileObject, bool]:
        payload, local_path, sha256_hex, md5_hex = await storage_service.store_upload(upload, namespace)
        return self._persist_file_object(
            session,
            payload=payload,
            local_path=local_path,
            sha256_hex=sha256_hex,
            md5_hex=md5_hex,
            filename=upload.filename or "upload.bin",
            mime_type=upload.content_type or "application/octet-stream",
            source_url=source_url,
            namespace=namespace,
            metadata_json=metadata_json,
            tenant_id=tenant_id,
            dedupe_scope=dedupe_scope,
        )

    def store_bytes(
        self,
        session: Session,
        *,
        payload: bytes,
        namespace: str,
        filename: str,
        mime_type: str,
        source_url: str | None = None,
        metadata_json: dict[str, object] | None = None,
        tenant_id=None,
        dedupe_scope: DedupeScope = "global",
    ) -> tuple[FileObject, bool]:
        stored_payload, local_path, sha256_hex, md5_hex = storage_service.store_bytes(
            payload=payload,
            namespace=namespace,
            filename=filename,
        )
        return self._persist_file_object(
            session,
            payload=stored_payload,
            local_path=local_path,
            sha256_hex=sha256_hex,
            md5_hex=md5_hex,
            filename=filename,
            mime_type=mime_type,
            source_url=source_url,
            namespace=namespace,
            metadata_json=metadata_json,
            tenant_id=tenant_id,
            dedupe_scope=dedupe_scope,
        )

    def list_file_objects(self, session: Session, *, tenant_id=None, limit: int = 100) -> list[FileObject]:
        stmt = select(FileObject).order_by(FileObject.created_at.desc()).limit(limit)
        if tenant_id is not None:
            stmt = stmt.where(FileObject.tenant_id == tenant_id)
        return list(session.scalars(stmt))

    def soft_delete_file_object(self, session: Session, *, file_object: FileObject) -> None:
        file_object.status = FileObjectStatus.DELETED
        file_object.deleted_at = file_object.deleted_at or datetime.now(UTC)
        session.flush()

    def hard_delete_if_local(self, session: Session, *, file_object: FileObject) -> bool:
        if self.has_active_references(session, file_object=file_object):
            self.soft_delete_file_object(session, file_object=file_object)
            return False
        storage_service.delete_path(file_object.local_path)
        file_object.status = FileObjectStatus.DELETED
        file_object.deleted_at = file_object.deleted_at or datetime.now(UTC)
        session.flush()
        return True

    def has_active_references(self, session: Session, *, file_object: FileObject) -> bool:
        student_file = session.scalar(
            select(StudentFile)
            .where(StudentFile.file_object_id == file_object.id)
            .where(StudentFile.deleted_at.is_(None))
            .limit(1)
        )
        if student_file is not None:
            return True
        document_version = session.scalar(
            select(DocumentVersion)
            .where(DocumentVersion.file_object_id == file_object.id)
            .where(DocumentVersion.deleted_at.is_(None))
            .limit(1)
        )
        if document_version is not None:
            return True
        discovered_url = session.scalar(
            select(DiscoveredUrl)
            .where(DiscoveredUrl.file_object_id == file_object.id)
            .where(DiscoveredUrl.deleted_at.is_(None))
            .limit(1)
        )
        return discovered_url is not None

    def _persist_file_object(
        self,
        session: Session,
        *,
        payload: bytes,
        local_path: str,
        sha256_hex: str,
        md5_hex: str,
        filename: str,
        mime_type: str,
        source_url: str | None,
        namespace: str,
        metadata_json: dict[str, object] | None,
        tenant_id,
        dedupe_scope: DedupeScope,
    ) -> tuple[FileObject, bool]:
        existing = None
        if dedupe_scope == "global":
            existing = session.scalar(select(FileObject).where(FileObject.sha256 == sha256_hex))
        elif dedupe_scope == "tenant":
            existing = session.scalar(
                select(FileObject).where(FileObject.sha256 == sha256_hex).where(FileObject.tenant_id == tenant_id)
            )
        if existing is not None:
            storage_service.delete_path(local_path)
            return existing, True

        file_object = FileObject(
            tenant_id=tenant_id,
            storage_provider=StorageProvider.LOCAL,
            bucket_name=get_settings().object_storage_bucket,
            object_key=local_path,
            local_path=local_path,
            original_filename=filename,
            mime_type=mime_type,
            size_bytes=len(payload),
            md5=md5_hex,
            sha256=sha256_hex,
            source_url=source_url,
            status=FileObjectStatus.STORED,
            metadata_json={"namespace": namespace, **(metadata_json or {})},
        )
        session.add(file_object)
        session.flush()
        session.refresh(file_object)
        return file_object, False


file_object_service = FileObjectService()
