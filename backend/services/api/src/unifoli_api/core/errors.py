from enum import Enum
from typing import Any, Dict

from fastapi import HTTPException

class UniFoliErrorCode(str, Enum):
    AUTH_MISSING = "AUTH_MISSING"
    BACKEND_STARTUP_FAILED = "BACKEND_STARTUP_FAILED"
    DATABASE_URL_REQUIRED = "DATABASE_URL_REQUIRED"
    DATABASE_UNAVAILABLE = "DATABASE_UNAVAILABLE"
    FILE_NOT_FOUND = "FILE_NOT_FOUND"
    PARSE_TIMEOUT = "PARSE_TIMEOUT"
    NO_USABLE_TEXT = "NO_USABLE_TEXT"
    MALFORMED_PDF = "MALFORMED_PDF"
    ENCRYPTED_PDF = "ENCRYPTED_PDF"
    PIPELINE_PARTIAL_FAILURE = "PIPELINE_PARTIAL_FAILURE"
    DIAGNOSIS_RUN_FAILURE = "DIAGNOSIS_RUN_FAILURE"
    DIAGNOSIS_INPUT_EMPTY = "DIAGNOSIS_INPUT_EMPTY"
    INVALID_STUDENT_RECORD = "INVALID_STUDENT_RECORD"
    CANONICAL_SCHEMA_EMPTY = "CANONICAL_SCHEMA_EMPTY"
    DIAGNOSIS_TRACE_PERSIST_FAILED = "DIAGNOSIS_TRACE_PERSIST_FAILED"
    REPORT_GEN_FAILURE = "REPORT_GEN_FAILURE"
    REPORT_ARTIFACT_FAILED = "REPORT_ARTIFACT_FAILED"
    CHATBOT_CONTEXT_BUILD_FAILED = "CHATBOT_CONTEXT_BUILD_FAILED"
    DB_SCHEMA_MISMATCH = "DB_SCHEMA_MISMATCH"
    UNAUTHORIZED_GUEST = "UNAUTHORIZED_GUEST"
    PRODUCTION_SQLITE_UNSAFE = "PRODUCTION_SQLITE_UNSAFE"
    INTERNAL_ERROR = "INTERNAL_ERROR"

class UniFoliError(Exception):
    def __init__(
        self, 
        code: UniFoliErrorCode, 
        message: str, 
        details: Dict[str, Any] | None = None
    ):
        self.code = code
        self.message = message
        self.details = details or {}
        super().__init__(self.message)


def _normalize_error_code(code: str | UniFoliErrorCode) -> str:
    return code.value if isinstance(code, UniFoliErrorCode) else str(code or UniFoliErrorCode.INTERNAL_ERROR.value)


def build_error_detail(
    code: str | UniFoliErrorCode,
    message: str,
    *,
    debug_detail: str | None = None,
    stage: str | None = None,
    extra: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    normalized_code = _normalize_error_code(code)
    payload: Dict[str, Any] = {
        "code": normalized_code,
        "error_code": normalized_code,
        "message": str(message or "").strip() or "Request failed.",
    }
    if stage:
        payload["stage"] = str(stage).strip()
    if debug_detail:
        payload["debug_detail"] = str(debug_detail).strip()[:1200]
    if extra:
        payload["details"] = extra
    return payload


def raise_http_error(
    *,
    status_code: int,
    code: str | UniFoliErrorCode,
    message: str,
    debug_detail: str | None = None,
    stage: str | None = None,
    extra: Dict[str, Any] | None = None,
) -> None:
    raise HTTPException(
        status_code=status_code,
        detail=build_error_detail(
            code,
            message,
            debug_detail=debug_detail,
            stage=stage,
            extra=extra,
        ),
    )


def extract_error_code(detail: Any) -> str | None:
    if isinstance(detail, dict):
        value = detail.get("error_code") or detail.get("code")
        normalized = str(value or "").strip()
        return normalized or None
    return None


def extract_error_message(detail: Any) -> str | None:
    if isinstance(detail, dict):
        for key in ("message", "detail", "debug_detail"):
            value = detail.get(key)
            normalized = str(value or "").strip()
            if normalized:
                return normalized
    if isinstance(detail, str):
        normalized = detail.strip()
        return normalized or None
    return None
