from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ParsedDocumentSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    project_id: str
    upload_asset_id: str
    original_filename: str | None
    content_type: str | None
    file_size_bytes: int | None
    sha256: str | None
    stored_path: str | None
    upload_status: str | None
    parser_name: str
    source_extension: str
    status: str
    masking_status: str
    parse_attempts: int
    last_error: str | None
    can_retry: bool
    page_count: int
    word_count: int
    parse_started_at: datetime | None
    parse_completed_at: datetime | None
    created_at: datetime
    updated_at: datetime


class ParsedDocumentRead(ParsedDocumentSummary):
    content_text: str
    content_markdown: str
    parse_metadata: dict[str, object]


class DocumentChunkRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    document_id: str
    project_id: str
    chunk_index: int
    page_number: int | None
    char_start: int
    char_end: int
    token_estimate: int
    content_text: str
    embedding_model: str | None
    created_at: datetime
