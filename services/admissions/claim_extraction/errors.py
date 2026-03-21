from __future__ import annotations


class ClaimExtractionError(Exception):
    pass


class EmptyExtractionResponseError(ClaimExtractionError):
    pass


class ExtractionSchemaValidationError(ClaimExtractionError):
    pass


class ExtractionResponseParseError(ClaimExtractionError):
    pass
