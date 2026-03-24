from __future__ import annotations

from .base import DocumentParser, ParserContext, ParserDescriptor
from .docling_parser import DoclingDocumentParser
from .errors import ParserError, ParserNotFoundError
from .html_parser import HtmlDocumentParser
from .hwpx_parser import HwpxDocumentParser
from .ocr_fallback import OcrFallbackParser
from .pdf_parser import PdfDocumentParser
from .schemas import CanonicalParseResult
from .text_parser import PlainTextParser


class ParserRegistry:
    def __init__(self) -> None:
        self.parsers: list[DocumentParser] = sorted(
            [
                DoclingDocumentParser(),
                PdfDocumentParser(),
                HtmlDocumentParser(),
                HwpxDocumentParser(),
                PlainTextParser(),
                OcrFallbackParser(),
            ],
            key=lambda parser: parser.priority,
        )

    def available_parsers(self) -> list[ParserDescriptor]:
        return [parser.describe() for parser in self.parsers]

    def candidate_parsers(self, filename: str, mime_type: str | None = None) -> list[DocumentParser]:
        return [parser for parser in self.parsers if parser.supports(filename, mime_type)]

    def find(self, filename: str, mime_type: str | None = None) -> DocumentParser:
        for parser in self.candidate_parsers(filename, mime_type):
            if parser.is_available():
                return parser
        raise ParserNotFoundError(f"No parser registered for {filename}")

    def parse(self, payload: bytes, context: ParserContext) -> CanonicalParseResult:
        candidates = self.candidate_parsers(context.filename, context.mime_type)
        if not candidates:
            raise ParserNotFoundError(f"No parser registered for {context.filename}")

        trace: list[dict[str, object]] = []
        errors: list[str] = []
        for parser in candidates:
            if not parser.is_available():
                trace.append(
                    {
                        "parser_name": parser.name,
                        "status": "unavailable",
                        "reason": "optional_dependency_missing",
                    }
                )
                continue
            try:
                result = parser.parse(payload, context)
                trace.append({"parser_name": parser.name, "status": "succeeded"})
                result.parser_trace = trace
                if len(trace) > 1:
                    result.fallback_reason = "; ".join(errors) or "primary parser unavailable"
                result.metadata = {
                    **result.metadata,
                    "parser_trace": trace,
                    "parser_fallback_reason": result.fallback_reason,
                }
                return result
            except Exception as exc:
                errors.append(f"{parser.name}: {exc}")
                trace.append(
                    {
                        "parser_name": parser.name,
                        "status": "failed",
                        "reason": str(exc),
                    }
                )

        raise ParserError("; ".join(errors) or f"All parsers failed for {context.filename}")


parser_registry = ParserRegistry()
