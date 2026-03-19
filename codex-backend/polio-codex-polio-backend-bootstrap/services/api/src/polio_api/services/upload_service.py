from __future__ import annotations

import hashlib
from pathlib import Path
from uuid import uuid4

from fastapi import UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from polio_api.core.config import get_settings
from polio_api.db.models.upload_asset import UploadAsset
from polio_api.services.document_service import ingest_upload_asset, upload_supports_ingest
from polio_shared.paths import find_project_root, get_upload_root, slugify


async def store_upload(db: Session, project_id: str, upload: UploadFile) -> UploadAsset:
    project_dir = get_upload_root() / project_id
    project_dir.mkdir(parents=True, exist_ok=True)

    suffix = Path(upload.filename or "file.bin").suffix or ".bin"
    safe_name = slugify(Path(upload.filename or "file").stem)
    filename = f"{safe_name}-{uuid4().hex}{suffix}"
    target_path = project_dir / filename

    contents = await upload.read()
    target_path.write_bytes(contents)
    relative_path = str(target_path.relative_to(find_project_root()))

    asset = UploadAsset(
        project_id=project_id,
        original_filename=upload.filename or filename,
        content_type=upload.content_type or "application/octet-stream",
        stored_path=relative_path,
        file_size_bytes=len(contents),
        sha256=hashlib.sha256(contents).hexdigest(),
    )
    db.add(asset)
    db.commit()
    db.refresh(asset)

    settings = get_settings()
    if settings.auto_ingest_uploads and upload_supports_ingest(asset):
        try:
            ingest_upload_asset(db, asset)
        except Exception:  # noqa: BLE001
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
