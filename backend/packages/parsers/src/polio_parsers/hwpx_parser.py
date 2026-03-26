from __future__ import annotations

from io import BytesIO
import re
from xml.etree import ElementTree
from zipfile import ZipFile

from polio_domain.enums import BlockType

from .base import DocumentParser, ParserContext
from .schemas import CanonicalBlock, CanonicalParseResult


class HwpxDocumentParser(DocumentParser):
    name = "hwpx_zip_xml"
    supported_extensions = (".hwpx",)
    supported_mime_types = ("application/haansoft-hwpx",)
    priority = 40

    def supports(self, filename: str, mime_type: str | None = None) -> bool:
        lowered = filename.lower()
        return lowered.endswith(".hwpx") or mime_type == "application/haansoft-hwpx"

    def parse(self, payload: bytes, context: ParserContext) -> CanonicalParseResult:
        blocks: list[CanonicalBlock] = []
        raw_parts: list[str] = []
        with ZipFile(BytesIO(payload)) as archive:
            for entry in sorted(item for item in archive.namelist() if item.endswith(".xml")):
                try:
                    xml_text = archive.read(entry).decode("utf-8", errors="ignore")
                except KeyError:
                    continue
                try:
                    root = ElementTree.fromstring(xml_text)
                    text_fragments = [node.text.strip() for node in root.iter() if node.text and node.text.strip()]
                except ElementTree.ParseError:
                    text_fragments = [fragment for fragment in re.split(r"\s+", xml_text) if fragment]
                if not text_fragments:
                    continue
                merged = " ".join(text_fragments)
                raw_parts.append(merged)
                blocks.append(
                    CanonicalBlock(
                        block_index=len(blocks),
                        block_type=BlockType.PARAGRAPH,
                        raw_text=merged,
                        cleaned_text=merged,
                        metadata={"entry_name": entry},
                    )
                )
        raw_text = "\n".join(raw_parts)
        return CanonicalParseResult(
            parser_name=self.name,
            raw_text=raw_text,
            cleaned_text=raw_text,
            blocks=blocks,
            source_url=context.source_url,
            file_hash=context.file_hash,
        )
