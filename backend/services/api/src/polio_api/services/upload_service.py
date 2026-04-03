from __future__ import annotations

import hashlib
from pathlib import Path
from uuid import uuid4

from fastapi import UploadFile
from sqlalchemy.orm import Session

from polio_api.core.config import get_settings
from polio_api.db.models.upload_asset import UploadAsset
from polio_api.services.document_service import ensure_document_placeholder, ingest_upload_asset, upload_supports_ingest
from polio_shared.paths import get_upload_root, slugify, to_stored_path
from polio_domain.enums import UploadStatus


ALLOWED_UPLOAD_CONTENT_TYPES_BY_EXTENSION: dict[str, set[str]] = {
    ".pdf": {
        "application/pdf",
        "application/x-pdf",
        "application/acrobat",
        "application/vnd.pdf",
        "text/pdf",
    },
    ".txt": {"text/plain"},
    ".md": {"text/markdown", "text/plain"},
}
GENERIC_UPLOAD_CONTENT_TYPES = {"application/octet-stream", "binary/octet-stream"}
UPLOAD_READ_CHUNK_SIZE = 1024 * 1024


class UploadValidationError(ValueError):
    def __init__(self, message: str, *, status_code: int = 400) -> None:
        super().__init__(message)
        self.status_code = status_code


async def store_upload(
    db: Session,
    project_id: str,
    upload: UploadFile,
    *,
    auto_ingest: bool | None = None,
) -> UploadAsset:
    settings = get_settings()
    original_filename, content_type, contents = await _read_and_validate_upload(upload, settings=settings)

    project_dir = get_upload_root() / project_id
    project_dir.mkdir(parents=True, exist_ok=True)

    suffix = Path(original_filename).suffix or ".bin"
    safe_name = slugify(Path(original_filename).stem)
    filename = f"{safe_name}-{uuid4().hex}{suffix}"
    target_path = project_dir / filename

    target_path.write_bytes(contents)
    relative_path = to_stored_path(target_path)

    asset = UploadAsset(
        project_id=project_id,
        original_filename=original_filename,
        content_type=content_type,
        stored_path=relative_path,
        file_size_bytes=len(contents),
        sha256=hashlib.sha256(contents).hexdigest(),
        status=UploadStatus.STORED.value,
    )
    db.add(asset)
    db.commit()
    db.refresh(asset)
    ensure_document_placeholder(db, asset)

    if auto_ingest is None:
        auto_ingest = settings.auto_ingest_uploads

    if auto_ingest and upload_supports_ingest(asset):
        try:
            ingest_upload_asset(db, asset)
        except Exception:  # noqa: BLE001
            asset.status = UploadStatus.FAILED.value
            db.commit()
            db.refresh(asset)

    db.refresh(asset)
    return asset


def list_uploads_for_project(db: Session, project_id: str) -> list[UploadAsset]:
    stmt = (
        select(UploadAsset)
        .where(UploadAsset.project_id == project_id)
        .order_by(UploadAsset.created_at.desc())
    )
    return list(db.scalars(stmt))


def get_upload(db: Session, upload_id: str) -> UploadAsset | None:
    return db.get(UploadAsset, upload_id)


async def _read_and_validate_upload(upload: UploadFile, *, settings) -> tuple[str, str, bytes]:
    original_filename = _normalize_original_filename(upload.filename)
    suffix = Path(original_filename).suffix.lower()
    allowed_extensions = {item.lower() for item in settings.upload_allowed_extensions}
    if suffix not in allowed_extensions:
        supported = ", ".join(sorted(allowed_extensions))
        raise UploadValidationError(
            f"Unsupported upload type. Allowed extensions: {supported}.",
            status_code=400,
        )

    chunks: list[bytes] = []
    total_size = 0
    try:
        while True:
            chunk = await upload.read(UPLOAD_READ_CHUNK_SIZE)
            if not chunk:
                break
            total_size += len(chunk)
            if total_size > settings.upload_max_bytes:
                raise UploadValidationError(
                    f"Upload exceeds the maximum size of {settings.upload_max_bytes} bytes.",
                    status_code=413,
                )
            chunks.append(chunk)
    finally:
        await upload.close()

    contents = b"".join(chunks)
    if not contents:
        raise UploadValidationError("Uploaded file is empty.", status_code=400)

    normalized_content_type = (upload.content_type or "").split(";", 1)[0].strip().lower()
    allowed_content_types = ALLOWED_UPLOAD_CONTENT_TYPES_BY_EXTENSION.get(suffix, set())
    if normalized_content_type and normalized_content_type not in allowed_content_types and normalized_content_type not in GENERIC_UPLOAD_CONTENT_TYPES:
        allowed_label = ", ".join(sorted(allowed_content_types)) or "a supported content type"
        raise UploadValidationError(
            f"Unsupported content type for {suffix}. Expected {allowed_label}.",
            status_code=400,
        )

    _validate_upload_contents(suffix=suffix, contents=contents)
    resolved_content_type = normalized_content_type or _default_content_type_for_extension(suffix)
    if resolved_content_type in GENERIC_UPLOAD_CONTENT_TYPES:
        resolved_content_type = _default_content_type_for_extension(suffix)
    return original_filename, resolved_content_type, contents


def _normalize_original_filename(filename: str | None) -> str:
    candidate = Path(filename or "file").name.strip()
    return (candidate[:255] or "file.bin")


def _validate_upload_contents(*, suffix: str, contents: bytes) -> None:
    if suffix == ".pdf":
        # Some PDF producers prepend whitespace/BOM before the PDF signature.
        # Accept files where the signature is present near the beginning.
        header_window = contents[:2048].lstrip()
        if b"%PDF-" not in header_window:
            raise UploadValidationError("Uploaded PDF file is malformed.", status_code=400)
        return

    if suffix in {".txt", ".md"}:
        if b"\x00" in contents:
            raise UploadValidationError("Text uploads must not contain binary data.", status_code=400)
        try:
            contents.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise UploadValidationError("Text uploads must be UTF-8 encoded.", status_code=400) from exc


def _default_content_type_for_extension(suffix: str) -> str:
    defaults = {
        ".pdf": "application/pdf",
        ".txt": "text/plain",
        ".md": "text/markdown",
    }
    return defaults.get(suffix, "application/octet-stream")
