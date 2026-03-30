from __future__ import annotations

from pathlib import Path
import re

_ABSOLUTE_PATH_RE = re.compile(r"(?:[A-Za-z]:\\[^\s]+|\\\\[^\s]+|/(?:[^/\s]+/)+[^/\s]+)")
_URL_RE = re.compile(r"https?://\S+")


def sanitize_public_error(message: str | None, *, fallback: str, max_length: int = 280) -> str:
    normalized = " ".join((message or "").split()).strip()
    if not normalized:
        return fallback
    if "traceback" in normalized.lower():
        return fallback
    if _ABSOLUTE_PATH_RE.search(normalized):
        return fallback
    redacted = _URL_RE.sub("[redacted-url]", normalized)
    return redacted[:max_length] or fallback


def ensure_resolved_within_base(path: Path, base_dir: Path) -> Path:
    resolved = path.resolve()
    base_resolved = base_dir.resolve()
    try:
        resolved.relative_to(base_resolved)
    except ValueError as exc:
        raise ValueError("Resolved path escapes the configured storage root.") from exc
    return resolved
