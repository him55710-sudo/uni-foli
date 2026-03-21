from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ParsedDocumentSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    project_id: str
    upload_asset_id: str
    parser_name: str
    source_extension: str
    page_count: int
    word_count: int
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
