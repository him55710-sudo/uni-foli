from __future__ import annotations

import fitz  # PyMuPDF
from polio_domain.enums import BlockType
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
        offset = 0

        for page_number, page in enumerate(doc, start=1):
            text = (page.get_text() or "").strip()
            raw_pages.append(text)
            
            # Simple heuristic paragraph splitting
            paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
            for p in paragraphs:
                blocks.append(
                    CanonicalBlock(
                        block_index=len(blocks),
                        block_type=BlockType.PARAGRAPH,
                        page_number=page_number,
                        raw_text=p,
                        cleaned_text=p,
                        char_start=offset,
                        char_end=offset + len(p),
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
                "author": doc.metadata.get("author"),
                "creator": doc.metadata.get("creator"),
                "producer": doc.metadata.get("producer")
            },
        )
