from __future__ import annotations

from io import BytesIO

from app.core.config import get_settings
from domain.enums import BlockType
from parsers.base import DocumentParser, ParserContext
from parsers.errors import ParserError
from parsers.schemas import CanonicalBlock, CanonicalParseResult


class DoclingDocumentParser(DocumentParser):
    name = "docling"
    supported_extensions = (".pdf", ".html", ".htm")
    supported_mime_types = ("application/pdf", "text/html")
    priority = 5
    is_optional_dependency = True

    def supports(self, filename: str, mime_type: str | None = None) -> bool:
        lowered = filename.lower()
        return lowered.endswith((".pdf", ".html", ".htm")) or mime_type in self.supported_mime_types

    def is_available(self) -> bool:
        if not get_settings().docling_enabled:
            return False
        try:
            import docling  # noqa: F401
        except ImportError:
            return False
        return True

    def parse(self, payload: bytes, context: ParserContext) -> CanonicalParseResult:
        if not self.is_available():
            raise ParserError("Docling is not installed.")

        from docling.datamodel.base_models import DocumentStream
        from docling.document_converter import DocumentConverter

        converter = DocumentConverter()
        if context.local_path:
            result = converter.convert(context.local_path)
        else:
            if self._infer_input_format(context.filename, context.mime_type) is None:
                raise ParserError("Unable to infer input format for Docling.")
            result = converter.convert(DocumentStream(name=context.filename, stream=BytesIO(payload)))

        document = getattr(result, "document", None)
        if document is None:
            raise ParserError("Docling conversion returned no document.")

        exported_markdown = document.export_to_markdown()
        text = exported_markdown.strip()
        if not text:
            raise ParserError("Docling produced empty markdown output.")

        blocks = self._markdown_to_blocks(text)
        page_count = None
        conv_pages = getattr(result, "pages", None)
        if conv_pages is not None:
            try:
                page_count = len(conv_pages)
            except TypeError:
                page_count = None
        if page_count is None:
            input_obj = getattr(result, "input", None)
            if input_obj is not None:
                page_count = getattr(input_obj, "page_count", None)

        title = blocks[0].cleaned_text if blocks else None
        return CanonicalParseResult(
            parser_name=self.name,
            parser_version=getattr(__import__("docling"), "__version__", "unknown"),
            title=title,
            raw_text=text,
            cleaned_text=text,
            blocks=blocks,
            source_url=context.source_url,
            file_hash=context.file_hash,
            metadata={
                "page_count": page_count or 0,
                "route_policy": "docling_preferred",
                "docling_used": True,
            },
        )

    def _infer_input_format(self, filename: str, mime_type: str | None) -> object | None:
        from docling.datamodel.base_models import InputFormat

        lowered = filename.lower()
        if lowered.endswith(".pdf") or mime_type == "application/pdf":
            return InputFormat.PDF
        if lowered.endswith((".html", ".htm")) or mime_type == "text/html":
            return InputFormat.HTML
        return None

    def _markdown_to_blocks(self, text: str) -> list[CanonicalBlock]:
        blocks: list[CanonicalBlock] = []
        heading_path: list[str] = []
        offset = 0
        for raw_block in [item.strip() for item in text.split("\n\n") if item.strip()]:
            block_type = BlockType.PARAGRAPH
            title = None
            if raw_block.startswith("#"):
                level = len(raw_block) - len(raw_block.lstrip("#"))
                cleaned = raw_block.lstrip("#").strip()
                heading_path = heading_path[: max(0, level - 1)]
                heading_path.append(cleaned)
                raw_block = cleaned
                block_type = BlockType.HEADING if level > 1 else BlockType.TITLE
                title = cleaned
            block = CanonicalBlock(
                block_index=len(blocks),
                block_type=block_type,
                page_number=None,
                heading_path=list(heading_path),
                title=title,
                raw_text=raw_block,
                cleaned_text=raw_block,
                char_start=offset,
                char_end=offset + len(raw_block),
                metadata={"docling_heading_path": list(heading_path)},
            )
            blocks.append(block)
            offset += len(raw_block) + 2
        return blocks
