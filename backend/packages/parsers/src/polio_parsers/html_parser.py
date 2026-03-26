from __future__ import annotations

from html.parser import HTMLParser

from polio_domain.enums import BlockType

from .base import DocumentParser, ParserContext
from .schemas import CanonicalBlock, CanonicalParseResult


class _SimpleHTMLTextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.fragments: list[tuple[str, str]] = []
        self.title: str | None = None
        self.current_tag = "p"
        self._in_title = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.current_tag = tag.lower()
        if self.current_tag == "title":
            self._in_title = True

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "title":
            self._in_title = False
        if tag.lower() in {"p", "div", "section", "article", "li", "tr", "br", "h1", "h2", "h3", "h4"}:
            self.fragments.append(("break", "\n"))

    def handle_data(self, data: str) -> None:
        cleaned = data.strip()
        if not cleaned:
            return
        if self._in_title and not self.title:
            self.title = cleaned
        self.fragments.append((self.current_tag, cleaned))


class HtmlDocumentParser(DocumentParser):
    name = "html_document"
    supported_extensions = (".html", ".htm")
    supported_mime_types = ("text/html",)
    priority = 50

    def supports(self, filename: str, mime_type: str | None = None) -> bool:
        lowered = filename.lower()
        return lowered.endswith(".html") or lowered.endswith(".htm") or mime_type == "text/html"

    def parse(self, payload: bytes, context: ParserContext) -> CanonicalParseResult:
        html = payload.decode("utf-8", errors="ignore")
        extractor = _SimpleHTMLTextExtractor()
        extractor.feed(html)

        blocks: list[CanonicalBlock] = []
        heading_path: list[str] = []
        offset = 0
        for tag, fragment in extractor.fragments:
            if tag == "break":
                continue
            block_type = BlockType.PARAGRAPH
            title = None
            if tag in {"h1", "h2", "h3", "h4"}:
                level = int(tag[1])
                heading_path = heading_path[: max(0, level - 1)]
                heading_path.append(fragment)
                block_type = BlockType.TITLE if level == 1 else BlockType.HEADING
                title = fragment
            blocks.append(
                CanonicalBlock(
                    block_index=len(blocks),
                    block_type=block_type,
                    heading_path=list(heading_path),
                    title=title,
                    raw_text=fragment,
                    cleaned_text=fragment,
                    char_start=offset,
                    char_end=offset + len(fragment),
                )
            )
            offset += len(fragment) + 1

        raw_text = "\n".join(block.cleaned_text for block in blocks)
        return CanonicalParseResult(
            parser_name=self.name,
            title=extractor.title or (blocks[0].cleaned_text if blocks else None),
            raw_text=raw_text,
            cleaned_text=raw_text,
            blocks=blocks,
            source_url=context.source_url,
            file_hash=context.file_hash,
            metadata={"route_policy": "lightweight_html"},
        )
