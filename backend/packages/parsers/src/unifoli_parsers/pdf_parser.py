from __future__ import annotations

import fitz  # PyMuPDF
from unifoli_domain.enums import BlockType
from .base import DocumentParser, ParserContext
from .schemas import CanonicalBlock, CanonicalParseResult
from .errors import EmptyDocumentError, EncryptedDocumentError


class PdfDocumentParser(DocumentParser):
    name = "pymupdf"
    supported_extensions = (".pdf",)
    supported_mime_types = ("application/pdf",)
    priority = 20

    def supports(self, filename: str, mime_type: str | None = None) -> bool:
        lowered = filename.lower()
        return lowered.endswith(".pdf") or mime_type == "application/pdf"

    def parse(self, payload: bytes, context: ParserContext) -> CanonicalParseResult:
        doc = fitz.open(stream=payload, filetype="pdf")
        if doc.is_encrypted:
            raise EncryptedDocumentError("The PDF is password protected. Please remove the password and try again.")

        blocks: list[CanonicalBlock] = []
        raw_pages: list[str] = []
        page_layouts: list[dict[str, object]] = []
        offset = 0

        for page_number, page in enumerate(doc, start=1):
            text, page_blocks, layout_profile = _extract_page_blocks(page, page_number=page_number)
            raw_pages.append(text)
            page_layouts.append({"page_number": page_number, **layout_profile})

            iterable_blocks = page_blocks or [
                {
                    "text": paragraph,
                    "bbox": None,
                    "line_count": max(1, len([line for line in paragraph.splitlines() if line.strip()])),
                }
                for paragraph in text.split("\n\n")
                if paragraph.strip()
            ]
            for item in iterable_blocks:
                p = str(item.get("text") or "").strip()
                if not p:
                    continue
                blocks.append(
                    CanonicalBlock(
                        block_index=len(blocks),
                        block_type=BlockType.PARAGRAPH,
                        page_number=page_number,
                        raw_text=p,
                        cleaned_text=p,
                        char_start=offset,
                        char_end=offset + len(p),
                        metadata={
                            "bbox": item.get("bbox"),
                            "line_count": item.get("line_count"),
                        },
                    )
                )
                offset += len(p) + 1

        raw_text = "\n".join(raw_pages)
        if not raw_text.strip() and len(doc) > 0:
            raise EmptyDocumentError("No extractable text found. This may be an image-only PDF. Please use a text-based PDF or OCR the file before uploading.")
            
        title = doc.metadata.get("title")
        if not title:
            title = next((b.cleaned_text for b in blocks if len(b.cleaned_text) > 5), None)
            
        return CanonicalParseResult(
            parser_name=self.name,
            title=title,
            raw_text=raw_text,
            cleaned_text=raw_text,
            blocks=blocks,
            source_url=context.source_url,
            file_hash=context.file_hash,
            metadata={
                "page_count": len(doc),
                "page_layouts": page_layouts,
                "layout_mode": "pymupdf_text_blocks",
                "author": doc.metadata.get("author"),
                "creator": doc.metadata.get("creator"),
                "producer": doc.metadata.get("producer")
            },
        )


def _extract_page_blocks(page: fitz.Page, *, page_number: int) -> tuple[str, list[dict[str, object]], dict[str, object]]:
    parsed_blocks: list[dict[str, object]] = []
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
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        line_count += max(1, len(lines))
        parsed_blocks.append(
            {
                "block_id": f"p{page_number}-b{len(parsed_blocks)}",
                "block_index": block_index,
                "text": text,
                "bbox": [round(float(block[i]), 2) for i in range(4)],
                "line_count": max(1, len(lines)),
            }
        )
        text_parts.append(text)

    text = _normalize_text("\n\n".join(text_parts))
    if not text:
        text = _normalize_text(page.get_text("text") or "")
    return text, parsed_blocks, {
        "text_block_count": len(parsed_blocks),
        "line_count_estimate": line_count,
        "extraction_strategy": "blocks" if parsed_blocks else "text_fallback",
    }


def _normalize_text(value: str) -> str:
    text = value.replace("\x00", " ").replace("\r\n", "\n").replace("\r", "\n")
    text = "\n".join(line.strip() for line in text.splitlines())
    while "\n\n\n" in text:
        text = text.replace("\n\n\n", "\n\n")
    return text.strip()
