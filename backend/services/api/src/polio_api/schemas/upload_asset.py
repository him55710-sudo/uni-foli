from datetime import datetime

from pydantic import BaseModel, ConfigDict, field_validator

from polio_api.core.security import sanitize_public_error

_UPLOAD_ERROR_FALLBACK = "Upload ingest failed. Retry after checking the file."


class UploadAssetRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    project_id: str
    original_filename: str
    content_type: str
    file_size_bytes: int
    parsed_document_id: str | None
    status: str
    page_count: int | None
    ingest_error: str | None
    created_at: datetime
    ingested_at: datetime | None

    @field_validator("ingest_error", mode="before")
    @classmethod
    def sanitize_ingest_error(cls, value: object) -> str | None:
        if value is None:
            return None
        return sanitize_public_error(str(value), fallback=_UPLOAD_ERROR_FALLBACK)
