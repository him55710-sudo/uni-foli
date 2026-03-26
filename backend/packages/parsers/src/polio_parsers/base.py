from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from .schemas import CanonicalParseResult


@dataclass(slots=True)
class ParserContext:
    filename: str
    mime_type: str | None = None
    source_url: str | None = None
    file_hash: str | None = None
    local_path: str | None = None
    parser_hints: dict[str, object] = field(default_factory=dict)


@dataclass(slots=True)
class ParserDescriptor:
    name: str
    supported_extensions: tuple[str, ...]
    supported_mime_types: tuple[str, ...]
    priority: int
    is_optional_dependency: bool = False


class DocumentParser(ABC):
    name = "base"
    supported_extensions: tuple[str, ...] = ()
    supported_mime_types: tuple[str, ...] = ()
    priority: int = 100
    is_optional_dependency: bool = False

    @abstractmethod
    def supports(self, filename: str, mime_type: str | None = None) -> bool:
        raise NotImplementedError

    @abstractmethod
    def parse(self, payload: bytes, context: ParserContext) -> CanonicalParseResult:
        raise NotImplementedError

    def is_available(self) -> bool:
        return True

    def describe(self) -> ParserDescriptor:
        return ParserDescriptor(
            name=self.name,
            supported_extensions=self.supported_extensions,
            supported_mime_types=self.supported_mime_types,
            priority=self.priority,
            is_optional_dependency=self.is_optional_dependency,
        )
