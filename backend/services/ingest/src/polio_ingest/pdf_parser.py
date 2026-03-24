from __future__ import annotations

from collections import Counter
import logging
from pathlib import Path
import re
from typing import Any

import pdfplumber
from pdfplumber.page import Page

from polio_domain.enums import DocumentMaskingStatus, DocumentProcessingStatus
from polio_ingest.masking import MaskingPipeline
from polio_ingest.models import ParsedChunkPayload, ParsedDocumentPayload

TEXT_EXTENSIONS = {".txt", ".md"}
SUPPORTED_EXTENSIONS = {".pdf", *TEXT_EXTENSIONS}


def _extract_tables_as_markdown(page: Page) -> tuple[str, int, list[str]]:
    failures: list[str] = []
    try:
        tables = page.extract_tables()
    except Exception as exc:  # noqa: BLE001
        failures.append(f"Table extraction failed: {exc}")
        return "", 0, failures

    if not tables:
        return "", 0, failures

    markdown_tables: list[str] = []
    for table in tables:
        if not table:
            continue

        cleaned_rows: list[list[str]] = []
        for row in table:
            if row is None:
                continue
            cleaned_row = []
            for cell in row:
                cell_text = "" if cell is None else str(cell).replace("\r\n", "<br>").replace("\n", "<br>").strip()
                cleaned_row.append(cell_text)
            if any(cell for cell in cleaned_row):
                cleaned_rows.append(cleaned_row)

        if not cleaned_rows:
            continue

        headers = cleaned_rows[0]
        body = cleaned_rows[1:]
        table_lines = [
            "| " + " | ".join(headers) + " |",
            "| " + " | ".join(["---"] * len(headers)) + " |",
        ]
        for row in body:
            padded = row + [""] * max(0, len(headers) - len(row))
            table_lines.append("| " + " | ".join(padded[: len(headers)]) + " |")
        markdown_tables.append("\n".join(table_lines))

    return "\n\n".join(markdown_tables), len(markdown_tables), failures


def parse_uploaded_document(
    file_path: Path,
    *,
    chunk_size_chars: int,
    overlap_chars: int,
) -> ParsedDocumentPayload:
    suffix = file_path.suffix.lower()
    if suffix == ".pdf":
        return parse_pdf_document(
            file_path,
            chunk_size_chars=chunk_size_chars,
            overlap_chars=overlap_chars,
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
) -> ParsedDocumentPayload:
    markdown_sections: list[str] = []
    full_text_parts: list[str] = []
    chunks: list[ParsedChunkPayload] = []
    chunk_index = 0
    page_count = 0
    raw_metadata: dict[str, Any] = {}
    page_summaries: list[dict[str, Any]] = []
    page_failures: list[dict[str, Any]] = []
    all_warnings: list[str] = []
    aggregate_hits: Counter[str] = Counter()
    total_tables = 0
    total_replacements = 0
    masking_methods: set[str] = set()
    masking_pipeline = MaskingPipeline()

    try:
        with pdfplumber.open(file_path) as pdf:
            page_count = len(pdf.pages)
            raw_metadata = pdf.metadata or {}

            for page_number, page in enumerate(pdf.pages, start=1):
                text_errors: list[str] = []
                try:
                    basic_text = page.extract_text(layout=True) or ""
                except Exception as exc:  # noqa: BLE001
                    basic_text = ""
                    text_errors.append(f"Text extraction failed: {exc}")
                    logging.warning("Text extraction failed on page %s: %s", page_number, exc)

                table_markdown, table_count, table_errors = _extract_tables_as_markdown(page)
                total_tables += table_count
                page_errors = [*text_errors, *table_errors]

                raw_page_text = "\n\n".join(
                    part for part in [basic_text.strip(), table_markdown.strip()] if part
                ).strip()
                if not raw_page_text:
                    if page_errors:
                        page_failures.extend(
                            {"page_number": page_number, "message": message} for message in page_errors
                        )
                    continue

                masking_result = masking_pipeline.mask_text(raw_page_text)
                aggregate_hits.update(masking_result.pattern_hits)
                total_replacements += masking_result.replacements
                all_warnings.extend(masking_result.warnings)
                if masking_result.method:
                    masking_methods.add(masking_result.method)

                page_text = _normalize_text(masking_result.text)
                if not page_text:
                    page_failures.append(
                        {"page_number": page_number, "message": "Page became empty after masking."}
                    )
                    continue

                markdown_sections.append(f"## Page {page_number}\n\n{page_text}")
                full_text_parts.append(f"[Page {page_number}]\n{page_text}")

                for content, char_start, char_end in _slice_text(page_text, chunk_size_chars, overlap_chars):
                    chunks.append(
                        ParsedChunkPayload(
                            chunk_index=chunk_index,
                            page_number=page_number,
                            char_start=char_start,
                            char_end=char_end,
                            token_estimate=_estimate_tokens(content),
                            content_text=content,
                        )
                    )
                    chunk_index += 1

                page_summaries.append(
                    {
                        "page_number": page_number,
                        "table_count": table_count,
                        "text_length": len(page_text),
                        "masking_method": masking_result.method,
                        "regex_hits": masking_result.pattern_hits,
                        "warnings": [*page_errors, *masking_result.warnings],
                    }
                )
                page_failures.extend(
                    {"page_number": page_number, "message": message}
                    for message in page_errors
                )
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(f"Error parsing PDF with pdfplumber: {exc}") from exc

    content_text = "\n\n".join(full_text_parts).strip()
    content_markdown = f"# {file_path.stem}\n\n" + ("\n\n".join(markdown_sections) or "No text extracted.")
    processing_status = DocumentProcessingStatus.PARSED.value
    masking_status = DocumentMaskingStatus.MASKED.value

    if not chunks:
        processing_status = DocumentProcessingStatus.FAILED.value
        masking_status = DocumentMaskingStatus.FAILED.value
    elif page_failures:
        processing_status = DocumentProcessingStatus.PARTIAL.value

    metadata = _clean_metadata(
        {
            "filename": file_path.name,
            "title": raw_metadata.get("Title"),
            "author": raw_metadata.get("Author"),
            "subject": raw_metadata.get("Subject"),
            "creator": raw_metadata.get("Creator"),
            "producer": raw_metadata.get("Producer"),
            "table_count": total_tables,
            "page_summaries": page_summaries,
            "page_failures": page_failures,
            "masking": {
                "methods": sorted(masking_methods) or ["regex"],
                "replacement_count": total_replacements,
                "pattern_hits": dict(aggregate_hits),
            },
        }
    )

    warnings = [*all_warnings, *[item["message"] for item in page_failures]]
    return ParsedDocumentPayload(
        parser_name="pdfplumber",
        source_extension=".pdf",
        page_count=page_count,
        word_count=len(content_text.split()),
        content_text=content_text,
        content_markdown=content_markdown.strip(),
        metadata=metadata,
        chunks=chunks,
        processing_status=processing_status,
        masking_status=masking_status,
        warnings=warnings,
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


def _clean_metadata(metadata: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in metadata.items() if value not in (None, "", [], {})}
