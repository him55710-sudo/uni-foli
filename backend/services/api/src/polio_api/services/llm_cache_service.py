from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from polio_api.db.models.llm_cache_entry import LLMCacheEntry


WHITESPACE_RE = re.compile(r"\s+")


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _coerce_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


@dataclass(frozen=True, slots=True)
class CacheRequest:
    feature_name: str
    model_name: str
    scope_key: str
    config_version: str
    payload: dict[str, Any]
    evidence_keys: list[str] = field(default_factory=list)
    ttl_seconds: int = 0
    bypass: bool = False
    response_format: str = "json"


def build_cache_key(request: CacheRequest) -> str:
    normalized_payload = normalize_payload(
        {
            "feature_name": request.feature_name,
            "model_name": request.model_name,
            "scope_key": request.scope_key,
            "config_version": request.config_version,
            "payload": request.payload,
            "evidence_keys": sorted(request.evidence_keys),
            "response_format": request.response_format,
        }
    )
    serialized = json.dumps(normalized_payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def normalize_payload(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            str(key): normalize_payload(item)
            for key, item in sorted(value.items(), key=lambda item: str(item[0]))
        }
    if isinstance(value, (list, tuple)):
        return [normalize_payload(item) for item in value]
    if isinstance(value, str):
        return WHITESPACE_RE.sub(" ", value).strip()
    return value


def purge_expired_cache_entries(db: Session) -> None:
    db.execute(delete(LLMCacheEntry).where(LLMCacheEntry.expires_at < utc_now()))
    db.commit()


def fetch_cached_response(db: Session, request: CacheRequest) -> str | None:
    if request.bypass or request.ttl_seconds <= 0:
        return None

    key = build_cache_key(request)
    entry = db.get(LLMCacheEntry, key)
    if entry is None or _coerce_utc(entry.expires_at) < utc_now():
        if entry is not None:
            db.delete(entry)
            db.commit()
        return None

    entry.hit_count += 1
    entry.last_accessed_at = utc_now()
    db.add(entry)
    db.commit()
    return entry.response_payload


def store_cached_response(
    db: Session,
    request: CacheRequest,
    *,
    response_payload: str,
) -> None:
    if request.bypass or request.ttl_seconds <= 0:
        return

    key = build_cache_key(request)
    expires_at = utc_now() + timedelta(seconds=request.ttl_seconds)
    entry = db.get(LLMCacheEntry, key)
    if entry is None:
        entry = LLMCacheEntry(
            key=key,
            scope_key=request.scope_key,
            feature_name=request.feature_name,
            model_name=request.model_name,
            config_version=request.config_version,
            response_format=request.response_format,
            response_payload=response_payload,
            hit_count=0,
            expires_at=expires_at,
            last_accessed_at=utc_now(),
        )
    else:
        entry.response_payload = response_payload
        entry.expires_at = expires_at
        entry.last_accessed_at = utc_now()
        entry.response_format = request.response_format
    db.add(entry)
    db.commit()


def cache_stats_for_scope(db: Session, scope_key: str) -> dict[str, int]:
    entries = list(db.scalars(select(LLMCacheEntry).where(LLMCacheEntry.scope_key == scope_key)))
    return {
        "entry_count": len(entries),
        "hit_count": sum(entry.hit_count for entry in entries),
    }
