from __future__ import annotations


class ParserError(RuntimeError):
    """Raised when a parser cannot safely parse a payload."""


class ParserNotFoundError(ParserError):
    """Raised when no parser is available for a payload."""


class EmptyDocumentError(ParserError):
    """Raised when the document contains no extractable text (e.g., image-only PDF)."""


class EncryptedDocumentError(ParserError):
    """Raised when the document is password protected."""
