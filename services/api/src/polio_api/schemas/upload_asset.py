from datetime import datetime

from pydantic import BaseModel, ConfigDict


class UploadAssetRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    project_id: str
    original_filename: str
    content_type: str
    stored_path: str
    file_size_bytes: int
    sha256: str | None
    status: str
    page_count: int | None
    ingest_error: str | None
    created_at: datetime
    ingested_at: datetime | None
