from __future__ import annotations

from pathlib import Path
import re

from pypdf import PdfReader

from polio_ingest.models import ParsedChunkPayload, ParsedDocumentPayload


TEXT_EXTENSIONS = {".txt", ".md"}
SUPPORTED_EXTENSIONS = {".pdf", *TEXT_EXTENSIONS}


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
    reader = PdfReader(str(file_path))
    markdown_sections: list[str] = []
    full_text_parts: list[str] = []
    chunks: list[ParsedChunkPayload] = []
    chunk_index = 0

    for page_number, page in enumerate(reader.pages, start=1):
        page_text = _normalize_text(page.extract_text() or "")
        if not page_text:
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

    content_text = "\n\n".join(full_text_parts).strip()
    content_markdown = f"# {file_path.stem}\n\n" + ("\n\n".join(markdown_sections) or "No text extracted.")
    metadata = _clean_metadata(
        {
            "filename": file_path.name,
            "title": getattr(reader.metadata, "title", None),
            "author": getattr(reader.metadata, "author", None),
            "subject": getattr(reader.metadata, "subject", None),
            "creator": getattr(reader.metadata, "creator", None),
            "producer": getattr(reader.metadata, "producer", None),
        }
    )

    return ParsedDocumentPayload(
        parser_name="pypdf",
        source_extension=".pdf",
        page_count=len(reader.pages),
        word_count=len(content_text.split()),
        content_text=content_text,
        content_markdown=content_markdown.strip(),
        metadata=metadata,
        chunks=chunks,
    )


def parse_text_document(
    file_path: Path,
    *,
    chunk_size_chars: int,
    overlap_chars: int,
) -> ParsedDocumentPayload:
    raw_text = file_path.read_text(encoding="utf-8", errors="ignore")
    normalized = _normalize_text(raw_text)
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
        content_markdown = raw_text.strip()
    else:
        content_markdown = f"# {file_path.stem}\n\n{normalized}"

    return ParsedDocumentPayload(
        parser_name="plain-text",
        source_extension=file_path.suffix.lower(),
        page_count=1,
        word_count=len(normalized.split()),
        content_text=normalized,
        content_markdown=content_markdown.strip(),
        metadata={"filename": file_path.name},
        chunks=chunks,
    )


def can_ingest_file(file_name: str) -> bool:
    return Path(file_name).suffix.lower() in SUPPORTED_EXTENSIONS


def _slice_text(text: str, chunk_size_chars: int, overlap_chars: int) -> list[tuple[str, int, int]]:
    if not text:
        return []

    step = max(chunk_size_chars - overlap_chars, 1)
    chunks: list[tuple[str, int, int]] = []

    for start in range(0, len(text), step):
        end = min(start + chunk_size_chars, len(text))
        chunk = text[start:end].strip()
        if not chunk:
            continue
        chunks.append((chunk, start, end))
        if end >= len(text):
            break

    return chunks


def _normalize_text(value: str) -> str:
    collapsed = value.replace("\x00", " ")
    collapsed = collapsed.replace("\r\n", "\n").replace("\r", "\n")
    collapsed = re.sub(r"[ \t]+", " ", collapsed)
    collapsed = re.sub(r"\n{3,}", "\n\n", collapsed)
    return collapsed.strip()


def _estimate_tokens(value: str) -> int:
    return max(1, round(len(value) / 4))


def _clean_metadata(metadata: dict[str, object]) -> dict[str, object]:
    return {key: value for key, value in metadata.items() if value not in (None, "", [])}
