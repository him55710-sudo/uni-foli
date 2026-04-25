from __future__ import annotations

from collections import Counter
import logging
from pathlib import Path
import re

import fitz

from unifoli_domain.enums import DocumentMaskingStatus, DocumentProcessingStatus
from unifoli_ingest.masking import MaskingPipeline
from unifoli_ingest.models import ParsedChunkPayload, ParsedDocumentPayload

TEXT_EXTENSIONS = {".txt", ".md"}
SUPPORTED_EXTENSIONS = {".pdf", *TEXT_EXTENSIONS}

logger = logging.getLogger(__name__)

_PDF_MALFORMED_MESSAGE = "Uploaded PDF file is malformed."
_PDF_ENCRYPTED_MESSAGE = "Encrypted PDF files are not supported. Remove password protection and retry."
_PDF_NO_USABLE_TEXT_MESSAGE = "No extractable text was found in the uploaded PDF."


class PDFParseFailure(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def parse_uploaded_document(
    file_path: Path,
    *,
    chunk_size_chars: int,
    overlap_chars: int,
    odl_enabled: bool = True,
    neis_ensemble_enabled: bool = True,
    neis_auto_detect_enabled: bool = True,
    neis_auto_detect_min_confidence: float = 0.62,
    neis_extractpdf4j_enabled: bool = False,
    neis_extractpdf4j_base_url: str | None = None,
    neis_extractpdf4j_timeout_seconds: float = 8.0,
    neis_dedoc_enabled: bool = True,
    neis_provider_min_quality_score: float = 0.58,
    neis_merge_policy: str = "conservative_table",
) -> ParsedDocumentPayload:
    suffix = file_path.suffix.lower()
    if suffix == ".pdf":
        return parse_pdf_document(
            file_path,
            chunk_size_chars=chunk_size_chars,
            overlap_chars=overlap_chars,
            odl_enabled=odl_enabled,
            neis_ensemble_enabled=neis_ensemble_enabled,
            neis_auto_detect_enabled=neis_auto_detect_enabled,
            neis_auto_detect_min_confidence=neis_auto_detect_min_confidence,
            neis_extractpdf4j_enabled=neis_extractpdf4j_enabled,
            neis_extractpdf4j_base_url=neis_extractpdf4j_base_url,
            neis_extractpdf4j_timeout_seconds=neis_extractpdf4j_timeout_seconds,
            neis_dedoc_enabled=neis_dedoc_enabled,
            neis_provider_min_quality_score=neis_provider_min_quality_score,
            neis_merge_policy=neis_merge_policy,
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
    neis_ensemble_enabled: bool = True,
    neis_auto_detect_enabled: bool = True,
    neis_auto_detect_min_confidence: float = 0.62,
    neis_extractpdf4j_enabled: bool = False,
    neis_extractpdf4j_base_url: str | None = None,
    neis_extractpdf4j_timeout_seconds: float = 8.0,
    neis_dedoc_enabled: bool = True,
    neis_provider_min_quality_score: float = 0.58,
    neis_merge_policy: str = "conservative_table",
) -> ParsedDocumentPayload:
    document = _open_pdf_document(file_path)
    try:
        if neis_ensemble_enabled:
            from unifoli_ingest.neis_pipeline import inspect_pdf_route, is_neis_candidate, parse_pdf_with_neis_pipeline

            try:
                route = inspect_pdf_route(file_path)
            except Exception as exc:  # noqa: BLE001
                logger.exception("NEIS route inspection failed for %s; falling back to base PyMuPDF parsing.", file_path)
                return _parse_pdf_with_pymupdf(
                    document=document,
                    file_path=file_path,
                    chunk_size_chars=chunk_size_chars,
                    overlap_chars=overlap_chars,
                    extra_warnings=["NEIS route inspection failed; generic PDF parsing was used instead."],
                    continuity_metadata={
                        "advanced_parse_fallback_used": True,
                        "advanced_parse_fallback_reason": f"route_inspection_failed:{type(exc).__name__}",
                    },
                )
            if (not neis_auto_detect_enabled) or is_neis_candidate(
                route,
                min_confidence=neis_auto_detect_min_confidence,
            ):
                try:
                    return parse_pdf_with_neis_pipeline(
                        file_path,
                        chunk_size_chars=chunk_size_chars,
                        overlap_chars=overlap_chars,
                        odl_enabled=odl_enabled,
                        neis_extractpdf4j_enabled=neis_extractpdf4j_enabled,
                        neis_extractpdf4j_base_url=neis_extractpdf4j_base_url,
                        neis_extractpdf4j_timeout_seconds=neis_extractpdf4j_timeout_seconds,
                        neis_dedoc_enabled=neis_dedoc_enabled,
                        neis_provider_min_quality_score=neis_provider_min_quality_score,
                        neis_merge_policy=neis_merge_policy,
                    )
                except Exception as exc:  # noqa: BLE001
                    logger.exception("NEIS pipeline failed for %s; falling back to base PyMuPDF parsing.", file_path)
                    return _parse_pdf_with_pymupdf(
                        document=document,
                        file_path=file_path,
                        chunk_size_chars=chunk_size_chars,
                        overlap_chars=overlap_chars,
                        extra_warnings=["Advanced NEIS parsing failed; generic PDF parsing was used instead."],
                        continuity_metadata={
                            "advanced_parse_fallback_used": True,
                            "advanced_parse_fallback_reason": type(exc).__name__,
                            "route_inspection": route,
                        },
                    )

        return _parse_pdf_with_pymupdf(
            document=document,
            file_path=file_path,
            chunk_size_chars=chunk_size_chars,
            overlap_chars=overlap_chars,
        )
    finally:
        document.close()


def _parse_pdf_with_pymupdf(
    *,
    document: fitz.Document,
    file_path: Path,
    chunk_size_chars: int,
    overlap_chars: int,
    extra_warnings: list[str] | None = None,
    continuity_metadata: dict[str, object] | None = None,
) -> ParsedDocumentPayload:
    masking_pipeline = MaskingPipeline()
    masking_counter: Counter[str] = Counter()
    warnings: list[str] = [str(item).strip() for item in (extra_warnings or []) if str(item).strip()]
    replacement_count = 0
    masking_methods: set[str] = set()
    raw_pages: list[dict[str, object]] = []
    masked_pages: list[dict[str, object]] = []
    evidence_references: list[dict[str, object]] = []
    chunk_evidence_map: dict[str, dict[str, object]] = {}
    markdown_parts = [f"# {file_path.stem}"]
    combined_parts: list[str] = []
    chunks: list[ParsedChunkPayload] = []
    char_cursor = 0
    chunk_index = 0
    page_confidences: list[float] = []
    blank_pages: list[int] = []

    for page_number, page in enumerate(document, start=1):
        raw_text, text_blocks, layout_profile = _extract_text_with_layout_blocks(page, page_number=page_number)
        page_bbox = [0.0, 0.0, float(page.rect.width), float(page.rect.height)]
        raw_pages.append(
            {
                "page_number": page_number,
                "bbox": page_bbox,
                "text": raw_text,
                "blocks": text_blocks,
                "layout_profile": layout_profile,
            }
        )

        if not raw_text:
            blank_pages.append(page_number)
            markdown_parts.extend([f"## Page {page_number}", "_No extractable text available._"])
            continue

        masking_result = masking_pipeline.mask_text(raw_text)
        masked_text = _normalize_text(masking_result.text)
        warnings.extend(masking_result.warnings)
        masking_counter.update(masking_result.pattern_hits)
        replacement_count += masking_result.replacements
        masking_methods.add(masking_result.method)

        reference_id = f"page-{page_number}"
        source_confidence = _page_confidence(masked_text)
        page_confidences.append(source_confidence)
        evidence_metadata = {
            "reference_id": reference_id,
            "page_span": [page_number, page_number],
            "bbox_refs": [page_bbox],
            "source_confidence": source_confidence,
            "block_count": layout_profile["text_block_count"],
            "line_count": layout_profile["line_count_estimate"],
        }
        evidence_references.append(evidence_metadata)
        masked_pages.append(
            {
                "page_number": page_number,
                "masked_text": masked_text,
                "layout_profile": layout_profile,
                "masking": {
                    "pattern_hits": masking_result.pattern_hits,
                    "warnings": masking_result.warnings,
                },
            }
        )

        page_heading = f"[Page {page_number}]"
        combined_parts.append(page_heading)
        char_cursor += len(page_heading) + 2
        markdown_parts.extend([f"## Page {page_number}", masked_text])

        page_entry = masked_text
        combined_parts.append(page_entry)
        entry_start = char_cursor
        char_cursor += len(page_entry) + 2

        for content, local_start, local_end in _slice_text(page_entry, chunk_size_chars, overlap_chars):
            metadata = dict(evidence_metadata)
            chunk_evidence_map[str(chunk_index)] = metadata
            chunks.append(
                ParsedChunkPayload(
                    chunk_index=chunk_index,
                    page_number=page_number,
                    char_start=entry_start + local_start,
                    char_end=entry_start + local_end,
                    token_estimate=_estimate_tokens(content),
                    content_text=content,
                    metadata=metadata,
                )
            )
            chunk_index += 1

    content_text = _normalize_text("\n\n".join(part for part in combined_parts if part))
    content_markdown = "\n\n".join(part for part in markdown_parts if part).strip()
    processing_status = DocumentProcessingStatus.PARSED.value if chunks else DocumentProcessingStatus.FAILED.value
    if blank_pages or warnings:
        processing_status = DocumentProcessingStatus.PARTIAL.value if chunks else DocumentProcessingStatus.FAILED.value
    if not chunks and _PDF_NO_USABLE_TEXT_MESSAGE not in warnings:
        warnings.append(_PDF_NO_USABLE_TEXT_MESSAGE)

    parse_confidence = round(
        max(page_confidences, default=0.35)
        if len(page_confidences) == 1
        else sum(page_confidences) / max(len(page_confidences), 1),
        2,
    )
    needs_review = bool(blank_pages) or parse_confidence < 0.55

    analysis_artifact = {
        "schema_version": "student_artifact_parse.v1",
        "artifact_type": "pdf_document",
        "parser_name": "pymupdf",
        "page_count": len(document),
        "needs_review": needs_review,
        "parse_confidence": parse_confidence,
        "evidence_references": evidence_references,
        "chunk_evidence_map": chunk_evidence_map,
        "page_profiles": [
            {
                "page_number": page["page_number"],
                "layout_profile": page.get("layout_profile", {}),
            }
            for page in raw_pages
        ],
        "layout_mode": "pymupdf_text_blocks",
    }
    if continuity_metadata:
        analysis_artifact["continuity"] = continuity_metadata

    metadata = {
        "filename": file_path.name,
        "warnings": warnings,
        "blank_pages": blank_pages,
        "masking": {
            "pattern_hits": dict(masking_counter),
            "replacement_count": replacement_count,
            "methods": sorted(masking_methods),
            "warnings": warnings,
        },
        "raw_parse_artifact": {
            "schema_version": "unifoli.raw_pdf.v1",
            "source": "pymupdf",
            "pages": raw_pages,
        },
        "student_artifact_parse": analysis_artifact,
    }
    if continuity_metadata:
        metadata["continuity"] = continuity_metadata

    return ParsedDocumentPayload(
        parser_name="pymupdf",
        source_extension=file_path.suffix.lower(),
        page_count=len(document),
        word_count=len(content_text.split()),
        content_text=content_text,
        content_markdown=content_markdown,
        metadata=metadata,
        chunks=chunks,
        processing_status=processing_status,
        masking_status=DocumentMaskingStatus.MASKED.value if content_text else DocumentMaskingStatus.FAILED.value,
        warnings=warnings,
        raw_artifact={
            "schema_version": "unifoli.raw_pdf.v1",
            "source": "pymupdf",
            "pages": raw_pages,
        },
        masked_artifact={
            "schema_version": "unifoli.masked_pdf.v1",
            "source": "pymupdf",
            "pages": masked_pages,
            "chunk_evidence_map": chunk_evidence_map,
        },
        analysis_artifact=analysis_artifact,
        parse_confidence=parse_confidence,
        needs_review=needs_review,
    )


def _extract_text_with_layout_blocks(page: fitz.Page, *, page_number: int) -> tuple[str, list[dict[str, object]], dict[str, object]]:
    text_blocks: list[dict[str, object]] = []
    text_parts: list[str] = []
    line_count = 0

    try:
        raw_blocks = page.get_text("blocks", sort=True) or []
    except Exception:  # noqa: BLE001
        raw_blocks = []

    for block_index, block in enumerate(raw_blocks):
        if not isinstance(block, tuple) or len(block) < 5:
            continue
        block_type = int(block[6]) if len(block) >= 7 and isinstance(block[6], int) else 0
        if block_type != 0:
            continue
        text = _normalize_text(str(block[4] or ""))
        if not text:
            continue
        bbox = [round(float(block[i]), 2) for i in range(4)]
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        line_count += max(1, len(lines))
        block_id = f"p{page_number}-b{len(text_blocks)}"
        text_blocks.append(
            {
                "block_id": block_id,
                "block_index": block_index,
                "page_number": page_number,
                "bbox": bbox,
                "text": text,
                "line_count": max(1, len(lines)),
            }
        )
        text_parts.append(text)

    raw_text = _normalize_text("\n\n".join(text_parts))
    if not raw_text:
        raw_text = _normalize_text(page.get_text("text") or "")

    page_width = max(float(page.rect.width), 1.0)
    x_centers = sorted(
        ((float(block["bbox"][0]) + float(block["bbox"][2])) / 2.0)
        for block in text_blocks
        if isinstance(block.get("bbox"), list) and len(block["bbox"]) >= 4
    )
    max_center_gap = max(
        (right - left for left, right in zip(x_centers, x_centers[1:])),
        default=0.0,
    )
    layout_profile = {
        "text_block_count": len(text_blocks),
        "line_count_estimate": line_count,
        "column_hint": "multi_column" if len(text_blocks) >= 4 and max_center_gap > page_width * 0.22 else "single_flow",
        "extraction_strategy": "blocks" if text_blocks else "text_fallback",
    }
    return raw_text, text_blocks, layout_profile


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
    repaired = _repair_mojibake_text(value)
    collapsed = repaired.replace("\x00", " ")
    collapsed = collapsed.replace("\r\n", "\n").replace("\r", "\n")
    collapsed = re.sub(r"[ \t]+", " ", collapsed)
    collapsed = re.sub(r"\n{3,}", "\n\n", collapsed)
    return collapsed.strip()


def _estimate_tokens(value: str) -> int:
    return max(1, round(len(value) / 4))


def _page_confidence(text: str) -> float:
    length = len(text)
    if length >= 600:
        return 0.92
    if length >= 240:
        return 0.82
    if length >= 80:
        return 0.68
    return 0.48


def _open_pdf_document(file_path: Path) -> fitz.Document:
    try:
        document = fitz.open(file_path)
    except Exception as exc:  # noqa: BLE001
        raise PDFParseFailure("pdf_malformed", _PDF_MALFORMED_MESSAGE) from exc
    if document.is_encrypted:
        document.close()
        raise PDFParseFailure("pdf_encrypted", _PDF_ENCRYPTED_MESSAGE)
    return document


def _repair_mojibake_text(value: str) -> str:
    text = str(value or "")
    if not text:
        return ""
    try:
        repaired = text.encode("latin-1").decode("utf-8")
    except UnicodeError:
        return text
    return repaired or text
