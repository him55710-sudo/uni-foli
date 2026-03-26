from __future__ import annotations

from .base import DocumentParser, ParserContext
from .schemas import CanonicalParseResult


class OcrFallbackParser(DocumentParser):
    name = "ocr_fallback"
    supported_extensions = ()
    supported_mime_types = ()
    priority = 999

    def supports(self, filename: str, mime_type: str | None = None) -> bool:
        return False

    def parse(self, payload: bytes, context: ParserContext) -> CanonicalParseResult:
        raise NotImplementedError("TODO: Wire OCR fallback only when primary parsers fail.")
