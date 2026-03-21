from __future__ import annotations

from pathlib import Path
import uuid

from fastapi import UploadFile

from app.core.config import get_settings
from services.admissions.utils import digest_bytes, safe_filename


class LocalObjectStorageService:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.base_path = Path(self.settings.local_object_store_path)
        self.base_path.mkdir(parents=True, exist_ok=True)

    async def store_upload(self, upload: UploadFile, namespace: str) -> tuple[bytes, str, str, str]:
        payload = await upload.read()
        return self.store_bytes(
            payload=payload,
            namespace=namespace,
            filename=upload.filename or "upload.bin",
        )

    def store_bytes(self, *, payload: bytes, namespace: str, filename: str) -> tuple[bytes, str, str, str]:
        sha256_hex, md5_hex = digest_bytes(payload)
        directory = self.base_path / namespace
        directory.mkdir(parents=True, exist_ok=True)
        destination_name = f"{uuid.uuid4()}-{safe_filename(filename)}"
        destination = directory / destination_name
        destination.write_bytes(payload)
        return payload, str(destination), sha256_hex, md5_hex

    def delete_path(self, local_path: str | None) -> None:
        if not local_path:
            return
        path = Path(local_path)
        if path.exists():
            path.unlink()


storage_service = LocalObjectStorageService()
