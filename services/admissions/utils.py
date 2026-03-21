from __future__ import annotations

from hashlib import md5, sha256
import re
from unicodedata import normalize
from uuid import UUID


def slugify(value: str) -> str:
    normalized = normalize("NFKC", value).strip().lower()
    normalized = re.sub(r"[^a-z0-9가-힣]+", "-", normalized)
    normalized = re.sub(r"-{2,}", "-", normalized)
    return normalized.strip("-") or "item"


def safe_filename(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", value).strip("._") or "upload.bin"


def digest_bytes(payload: bytes) -> tuple[str, str]:
    return sha256(payload).hexdigest(), md5(payload, usedforsecurity=False).hexdigest()


def ensure_uuid(value: str | UUID | None) -> UUID | None:
    if value is None or isinstance(value, UUID):
        return value
    return UUID(str(value))
