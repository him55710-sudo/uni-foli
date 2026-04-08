from __future__ import annotations

import asyncio
import time

from fastapi import APIRouter, Query

from polio_api.core.config import get_settings
from polio_api.core.llm import probe_ollama_connectivity

router = APIRouter()
_OLLAMA_HEALTH_TTL_SECONDS = 30.0
_ollama_health_lock = asyncio.Lock()
_ollama_health_cache: dict[str, object] = {
    "checked_at": 0.0,
    "ok": True,
    "reason": None,
}


@router.get("/health")
async def health_check(check_llm: bool = Query(default=False)) -> dict[str, object]:
    settings = get_settings()
    payload: dict[str, object] = {"status": "ok", "llm_provider": settings.llm_provider}
    if check_llm and (settings.llm_provider or "").strip().lower() == "ollama":
        now = time.monotonic()
        checked_at = float(_ollama_health_cache["checked_at"])
        if now - checked_at > _OLLAMA_HEALTH_TTL_SECONDS:
            async with _ollama_health_lock:
                # Re-check inside lock to avoid duplicate probes during bursts.
                lock_now = time.monotonic()
                lock_checked_at = float(_ollama_health_cache["checked_at"])
                if lock_now - lock_checked_at > _OLLAMA_HEALTH_TTL_SECONDS:
                    ok, reason = await probe_ollama_connectivity(profile="fast")
                    _ollama_health_cache["checked_at"] = lock_now
                    _ollama_health_cache["ok"] = ok
                    _ollama_health_cache["reason"] = reason

        ok = bool(_ollama_health_cache["ok"])
        reason = _ollama_health_cache["reason"] if isinstance(_ollama_health_cache["reason"], str) else None
        payload["ollama_reachable"] = ok
        payload["ollama_reason"] = reason
        payload["ollama_cached"] = (
            time.monotonic() - float(_ollama_health_cache["checked_at"]) <= _OLLAMA_HEALTH_TTL_SECONDS
        )
    return payload
