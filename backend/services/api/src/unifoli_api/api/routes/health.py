from __future__ import annotations

import asyncio
import time

from fastapi import APIRouter, Query, Request
from fastapi.responses import JSONResponse

from unifoli_api.core.config import get_settings
from unifoli_api.core.llm import probe_ollama_connectivity
from unifoli_api.core.runtime_diagnostics import build_health_payload

router = APIRouter()
_OLLAMA_HEALTH_TTL_SECONDS = 30.0
_ollama_health_lock = asyncio.Lock()
_ollama_health_cache: dict[str, object] = {
    "checked_at": 0.0,
    "ok": True,
    "reason": None,
}


def _settings_may_use_ollama(settings: object) -> bool:
    providers = (
        getattr(settings, "llm_provider", None),
        getattr(settings, "guided_chat_llm_provider", None),
        getattr(settings, "diagnosis_llm_provider", None),
        getattr(settings, "render_llm_provider", None),
        getattr(settings, "pdf_analysis_llm_provider", None),
    )
    return any(str(provider or "").strip().lower() == "ollama" for provider in providers)


@router.get("/health")
async def health_check(
    request: Request,
    check_llm: bool = Query(default=False),
    check_db: bool = Query(default=False),
) -> JSONResponse:
    settings = get_settings()
    ollama_payload: dict[str, object] | None = None
    if check_llm and _settings_may_use_ollama(settings):
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
        ollama_payload = {
            "ollama_reachable": ok,
            "ollama_reason": reason,
            "ollama_cached": (
            time.monotonic() - float(_ollama_health_cache["checked_at"]) <= _OLLAMA_HEALTH_TTL_SECONDS
            ),
        }

    payload = build_health_payload(
        settings,
        app_state=request.app.state,
        check_db=check_db,
        check_llm=check_llm,
        ollama_probe=ollama_payload,
    )
    status_code = 200 if payload["status"] == "ok" else 503
    return JSONResponse(status_code=status_code, content=payload)


@router.get("/readiness")
async def readiness_check(
    request: Request,
    check_llm: bool = Query(default=False),
) -> JSONResponse:
    settings = get_settings()
    payload = build_health_payload(
        settings,
        app_state=request.app.state,
        check_db=True,
        check_llm=check_llm,
    )
    status_code = 200 if payload["status"] == "ok" else 503
    return JSONResponse(status_code=status_code, content=payload)
