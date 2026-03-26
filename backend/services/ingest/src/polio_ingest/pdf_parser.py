from __future__ import annotations

from pathlib import Path
import re

from polio_domain.enums import DocumentMaskingStatus, DocumentProcessingStatus
from polio_ingest.masking import MaskingPipeline
from polio_ingest.models import ParsedChunkPayload, ParsedDocumentPayload
from polio_ingest.neis_pipeline import parse_pdf_with_neis_pipeline

TEXT_EXTENSIONS = {".txt", ".md"}
SUPPORTED_EXTENSIONS = {".pdf", *TEXT_EXTENSIONS}


def parse_uploaded_document(
    file_path: Path,
    *,
    chunk_size_chars: int,
    overlap_chars: int,
    odl_enabled: bool = True,
) -> ParsedDocumentPayload:
    suffix = file_path.suffix.lower()
    if suffix == ".pdf":
        return parse_pdf_document(
            file_path,
            chunk_size_chars=chunk_size_chars,
            overlap_chars=overlap_chars,
            odl_enabled=odl_enabled,
        )
    if suffix in TEXT_EXTENSIONS:
        return parse_text_document(
            file_path,
            chunk_size_chars=chunk_size_chars,
            overlap_chars=overlap_chars,
        )
    raise ValueError(f"Unsupported ingest extension: {suffix or '<none>'}")


def parse_pdf_document(
    file_path: Path,
    *,
    chunk_size_chars: int,
    overlap_chars: int,
    odl_enabled: bool = True,
) -> ParsedDocumentPayload:
    return parse_pdf_with_neis_pipeline(
        file_path,
        chunk_size_chars=chunk_size_chars,
        overlap_chars=overlap_chars,
        odl_enabled=odl_enabled,
    )


def parse_text_document(
    file_path: Path,
    *,
    chunk_size_chars: int,
    overlap_chars: int,
) -> ParsedDocumentPayload:
    raw_text = file_path.read_text(encoding="utf-8", errors="ignore")
    masking_pipeline = MaskingPipeline()
    masking_result = masking_pipeline.mask_text(raw_text)
    normalized = _normalize_text(masking_result.text)

    chunks = [
        ParsedChunkPayload(
            chunk_index=index,
            page_number=None,
            char_start=char_start,
            char_end=char_end,
            token_estimate=_estimate_tokens(content),
            content_text=content,
        )
        for index, (content, char_start, char_end) in enumerate(
            _slice_text(normalized, chunk_size_chars, overlap_chars)
        )
    ]

    if file_path.suffix.lower() == ".md":
        content_markdown = masking_result.text.strip()
    else:
        content_markdown = f"# {file_path.stem}\n\n{normalized}"

    processing_status = (
        DocumentProcessingStatus.PARSED.value if chunks else DocumentProcessingStatus.FAILED.value
    )
    masking_status = (
        DocumentMaskingStatus.MASKED.value if normalized else DocumentMaskingStatus.FAILED.value
    )

    return ParsedDocumentPayload(
        parser_name="plain-text",
        source_extension=file_path.suffix.lower(),
        page_count=1,
        word_count=len(normalized.split()),
        content_text=normalized,
        content_markdown=content_markdown.strip(),
        metadata={
            "filename": file_path.name,
            "masking": {
                "methods": [masking_result.method],
                "replacement_count": masking_result.replacements,
                "pattern_hits": masking_result.pattern_hits,
            },
            "warnings": masking_result.warnings,
        },
        chunks=chunks,
        processing_status=processing_status,
        masking_status=masking_status,
        warnings=masking_result.warnings,
    )


def can_ingest_file(file_name: str) -> bool:
    return Path(file_name).suffix.lower() in SUPPORTED_EXTENSIONS


def _slice_text(text: str, chunk_size_chars: int, overlap_chars: int) -> list[tuple[str, int, int]]:
    if not text:
        return []

    step = max(chunk_size_chars - overlap_chars, 1)
    sliced: list[tuple[str, int, int]] = []
    for start in range(0, len(text), step):
        end = min(start + chunk_size_chars, len(text))
        chunk = text[start:end].strip()
        if chunk:
            sliced.append((chunk, start, end))
        if end >= len(text):
            break
    return sliced


def _normalize_text(value: str) -> str:
    collapsed = value.replace("\x00", " ")
    collapsed = collapsed.replace("\r\n", "\n").replace("\r", "\n")
    collapsed = re.sub(r"[ \t]+", " ", collapsed)
    collapsed = re.sub(r"\n{3,}", "\n\n", collapsed)
    return collapsed.strip()


def _estimate_tokens(value: str) -> int:
    return max(1, round(len(value) / 4))
