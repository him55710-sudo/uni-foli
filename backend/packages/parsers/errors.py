from __future__ import annotations


class ParserError(RuntimeError):
    """Raised when a parser cannot safely parse a payload."""


class ParserNotFoundError(ParserError):
    """Raised when no parser is available for a payload."""
