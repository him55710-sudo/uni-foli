from __future__ import annotations

from polio_domain.enums import BlockType

from .base import DocumentParser, ParserContext
from .schemas import CanonicalBlock, CanonicalParseResult


class PlainTextParser(DocumentParser):
    name = "plain_text"
    supported_extensions = (".txt", ".md")
    supported_mime_types = ("text/plain", "text/markdown")
    priority = 80

    def supports(self, filename: str, mime_type: str | None = None) -> bool:
        lowered = filename.lower()
        return lowered.endswith(".txt") or lowered.endswith(".md")

    def parse(self, payload: bytes, context: ParserContext) -> CanonicalParseResult:
        text = payload.decode("utf-8", errors="ignore")
        lines = [line.rstrip() for line in text.splitlines()]
        blocks: list[CanonicalBlock] = []
        heading_path: list[str] = []
        running_offset = 0

        for line in (item for item in lines if item.strip()):
            block_type = BlockType.PARAGRAPH
            title = None
            cleaned_line = line.strip()
            if cleaned_line.startswith("#"):
                level = len(cleaned_line) - len(cleaned_line.lstrip("#"))
                cleaned_line = cleaned_line.lstrip("#").strip()
                heading_path = heading_path[: max(0, level - 1)]
                heading_path.append(cleaned_line)
                block_type = BlockType.TITLE if level == 1 else BlockType.HEADING
                title = cleaned_line
            blocks.append(
                CanonicalBlock(
                    block_index=len(blocks),
                    block_type=block_type,
                    heading_path=list(heading_path),
                    title=title,
                    raw_text=line,
                    cleaned_text=cleaned_line,
                    char_start=running_offset,
                    char_end=running_offset + len(cleaned_line),
                )
            )
            running_offset += len(line) + 1

        title = next((block.cleaned_text for block in blocks if block.block_type in {BlockType.TITLE, BlockType.HEADING}), None)
        if title is None:
            title = next((line.strip() for line in lines if line.strip()), None)
        return CanonicalParseResult(
            parser_name=self.name,
            title=title,
            raw_text=text,
            cleaned_text=text,
            blocks=blocks,
            source_url=context.source_url,
            file_hash=context.file_hash,
            metadata={"route_policy": "lightweight_text"},
        )
