from datetime import datetime

from pydantic import BaseModel, ConfigDict, field_validator

from polio_api.core.security import sanitize_public_error

_DOCUMENT_ERROR_FALLBACK = "Document processing failed. Retry after checking the uploaded file."


def _sanitize_parse_metadata(value: object) -> dict[str, object]:
    if not isinstance(value, dict):
        return {}

    safe: dict[str, object] = {}

    chunk_count = value.get("chunk_count")
    if isinstance(chunk_count, int) and chunk_count >= 0:
        safe["chunk_count"] = chunk_count

    table_count = value.get("table_count")
    if isinstance(table_count, int) and table_count >= 0:
        safe["table_count"] = table_count

    warnings = value.get("warnings")
    if isinstance(warnings, list):
        safe["warnings"] = [
            sanitize_public_error(str(item), fallback=_DOCUMENT_ERROR_FALLBACK)
            for item in warnings
            if str(item).strip()
        ][:10]

    page_failures = value.get("page_failures")
    if isinstance(page_failures, list):
        safe_page_failures: list[dict[str, object]] = []
        for item in page_failures[:20]:
            if not isinstance(item, dict):
                continue
            page_number = item.get("page_number")
            safe_item: dict[str, object] = {}
            if isinstance(page_number, int) and page_number >= 0:
                safe_item["page_number"] = page_number
            message = sanitize_public_error(
                str(item.get("message") or ""),
                fallback=_DOCUMENT_ERROR_FALLBACK,
            )
            if message:
                safe_item["message"] = message
            if safe_item:
                safe_page_failures.append(safe_item)
        if safe_page_failures:
            safe["page_failures"] = safe_page_failures

    masking = value.get("masking")
    if isinstance(masking, dict):
        safe_masking: dict[str, object] = {}
        methods = masking.get("methods")
        if isinstance(methods, list):
            safe_masking["methods"] = [str(item).strip() for item in methods if str(item).strip()][:10]
        replacement_count = masking.get("replacement_count")
        if isinstance(replacement_count, int) and replacement_count >= 0:
            safe_masking["replacement_count"] = replacement_count
        pattern_hits = masking.get("pattern_hits")
        if isinstance(pattern_hits, dict):
            normalized_hits: dict[str, int] = {}
            for key, item in list(pattern_hits.items())[:20]:
                try:
                    count = int(item)
                except (TypeError, ValueError):
                    continue
                if count < 0:
                    continue
                normalized_hits[str(key)] = count
            if normalized_hits:
                safe_masking["pattern_hits"] = normalized_hits
        if safe_masking:
            safe["masking"] = safe_masking

    return safe


class ParsedDocumentSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    project_id: str
    upload_asset_id: str
    original_filename: str | None
    content_type: str | None
    file_size_bytes: int | None
    upload_status: str | None
    parser_name: str
    source_extension: str
    status: str
    masking_status: str
    parse_attempts: int
    last_error: str | None
    can_retry: bool
    latest_async_job_id: str | None
    latest_async_job_status: str | None
    latest_async_job_error: str | None
    page_count: int
    word_count: int
    parse_started_at: datetime | None
    parse_completed_at: datetime | None
    created_at: datetime
    updated_at: datetime

    @field_validator("last_error", "latest_async_job_error", mode="before")
    @classmethod
    def sanitize_error_fields(cls, value: object) -> str | None:
        if value is None:
            return None
        return sanitize_public_error(str(value), fallback=_DOCUMENT_ERROR_FALLBACK)


class ParsedDocumentRead(ParsedDocumentSummary):
    content_text: str
    content_markdown: str
    parse_metadata: dict[str, object]

    @field_validator("parse_metadata", mode="before")
    @classmethod
    def sanitize_parse_metadata(cls, value: object) -> dict[str, object]:
        return _sanitize_parse_metadata(value)


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
