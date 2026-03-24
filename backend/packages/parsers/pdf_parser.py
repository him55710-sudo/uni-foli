from __future__ import annotations

from io import BytesIO

from pypdf import PdfReader

from polio_domain.enums import BlockType

from .base import DocumentParser, ParserContext
from .schemas import CanonicalBlock, CanonicalParseResult


class PdfDocumentParser(DocumentParser):
    name = "pypdf"
    supported_extensions = (".pdf",)
    supported_mime_types = ("application/pdf",)
    priority = 10

    def supports(self, filename: str, mime_type: str | None = None) -> bool:
        lowered = filename.lower()
        return lowered.endswith(".pdf") or mime_type == "application/pdf"

    def parse(self, payload: bytes, context: ParserContext) -> CanonicalParseResult:
        reader = PdfReader(BytesIO(payload))
        blocks: list[CanonicalBlock] = []
        raw_pages: list[str] = []
        offset = 0
        for page_number, page in enumerate(reader.pages, start=1):
            text = (page.extract_text() or "").strip()
            raw_pages.append(text)
            paragraphs = [paragraph.strip() for paragraph in text.split("\n\n") if paragraph.strip()]
            for paragraph in paragraphs:
                blocks.append(
                    CanonicalBlock(
                        block_index=len(blocks),
                        block_type=BlockType.PARAGRAPH,
                        page_number=page_number,
                        raw_text=paragraph,
                        cleaned_text=paragraph,
                        char_start=offset,
                        char_end=offset + len(paragraph),
                    )
                )
                offset += len(paragraph) + 1
        raw_text = "\n".join(raw_pages)
        title = None
        if reader.metadata is not None:
            title = getattr(reader.metadata, "title", None)
        if not title:
            title = next((block.cleaned_text for block in blocks if block.cleaned_text), None)
        return CanonicalParseResult(
            parser_name=self.name,
            title=title,
            raw_text=raw_text,
            cleaned_text=raw_text,
            blocks=blocks,
            source_url=context.source_url,
            file_hash=context.file_hash,
            metadata={"page_count": len(reader.pages), "route_policy": "lightweight_pdf"},
        )
