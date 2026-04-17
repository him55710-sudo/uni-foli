from __future__ import annotations

import os
from types import SimpleNamespace
from typing import Any
from urllib.parse import urlparse

from sqlalchemy import text

from unifoli_api.core.config import _is_local_host_url
from unifoli_api.core.errors import UniFoliErrorCode
from unifoli_shared.paths import resolve_runtime_path


def classify_startup_failure(error: Exception | str | None) -> str:
    message = str(error or "").strip()
    normalized = message.lower()
    if "sqlite runtime database is blocked" in normalized:
        return UniFoliErrorCode.DATABASE_URL_REQUIRED.value
    if (
        "database schema has not been initialized" in normalized
        or "database schema is not at alembic head" in normalized
    ):
        return UniFoliErrorCode.DB_SCHEMA_MISMATCH.value
    if any(
        token in normalized
        for token in (
            "connection refused",
            "could not connect",
            "could not translate host name",
            "name or service not known",
            "timeout expired",
            "timed out",
            "failed to connect",
        )
    ):
        return UniFoliErrorCode.DATABASE_UNAVAILABLE.value
    return UniFoliErrorCode.BACKEND_STARTUP_FAILED.value


def remediation_for_error_code(code: str | None) -> str | None:
    if code == UniFoliErrorCode.DATABASE_URL_REQUIRED.value:
        return (
            "Set DATABASE_URL to a managed Postgres connection in Vercel. "
            "Use ALLOW_PRODUCTION_SQLITE=true only as a temporary emergency override."
        )
    if code == UniFoliErrorCode.DB_SCHEMA_MISMATCH.value:
        return "Run Alembic migrations against the deployed database before routing upload traffic."
    if code == UniFoliErrorCode.DATABASE_UNAVAILABLE.value:
        return "Check the deployed database host, credentials, SSL requirements, and network allowlist."
    if code == UniFoliErrorCode.BACKEND_STARTUP_FAILED.value:
        return "Inspect the Vercel Python function logs for the startup traceback and fix the failing dependency."
    return None


def _read_first_env(*keys: str) -> str | None:
    for key in keys:
        value = (os.getenv(key) or "").strip()
        if value:
            return value
    return None


def snapshot_settings_from_env(api_prefix: str | None = None) -> Any:
    llm_provider = (os.getenv("LLM_PROVIDER") or "gemini").strip().lower() or "gemini"
    pdf_provider = (os.getenv("PDF_ANALYSIS_LLM_PROVIDER") or "ollama").strip().lower() or "ollama"
    return SimpleNamespace(
        api_prefix=(api_prefix or os.getenv("API_PREFIX") or "/api/v1").strip() or "/api/v1",
        app_env=(os.getenv("APP_ENV") or "production").strip().lower() or "production",
        serverless_runtime=os.getenv("VERCEL") == "1",
        unifoli_storage_provider=(os.getenv("UNIFOLI_STORAGE_PROVIDER") or os.getenv("OBJECT_STORAGE_PROVIDER") or "local").strip().lower() or "local",
        s3_bucket_name=(os.getenv("S3_BUCKET_NAME") or os.getenv("OBJECT_STORAGE_BUCKET") or "").strip() or None,
        llm_provider=llm_provider,
        guided_chat_llm_provider=(os.getenv("GUIDED_CHAT_LLM_PROVIDER") or "").strip().lower() or None,
        diagnosis_llm_provider=(os.getenv("DIAGNOSIS_LLM_PROVIDER") or "").strip().lower() or None,
        render_llm_provider=(os.getenv("RENDER_LLM_PROVIDER") or "").strip().lower() or None,
        gemini_api_key=_read_first_env("GEMINI_API_KEY", "GOOGLE_API_KEY", "GENAI_API_KEY", "GEMINI_KEY"),
        gemini_model=(os.getenv("GEMINI_MODEL") or "gemini-2.0-flash").strip() or "gemini-2.0-flash",
        ollama_base_url=(os.getenv("OLLAMA_BASE_URL") or "http://localhost:11434/v1").strip() or "http://localhost:11434/v1",
        pdf_analysis_llm_provider=pdf_provider,
        pdf_analysis_gemini_api_key=_read_first_env(
            "PDF_ANALYSIS_GEMINI_API_KEY",
            "GEMINI_API_KEY",
            "GOOGLE_API_KEY",
            "GENAI_API_KEY",
            "GEMINI_KEY",
        ),
        pdf_analysis_ollama_base_url=(os.getenv("PDF_ANALYSIS_OLLAMA_BASE_URL") or "").strip() or None,
        auth_social_login_enabled=(os.getenv("AUTH_SOCIAL_LOGIN_ENABLED") or "").strip().lower() == "true",
        auth_jwt_secret=(os.getenv("AUTH_JWT_SECRET") or "").strip() or None,
        auth_jwt_public_key=(os.getenv("AUTH_JWT_PUBLIC_KEY") or "").strip() or None,
        database_url=(os.getenv("DATABASE_URL") or "").strip() or "sqlite:///./storage/runtime/unifoli.db?check_same_thread=False&timeout=30",
        allow_production_sqlite=(os.getenv("ALLOW_PRODUCTION_SQLITE") or "").strip().lower() == "true",
        database_auto_create_tables=(os.getenv("DATABASE_AUTO_CREATE_TABLES") or "").strip().lower() != "false",
    )


def build_health_payload(
    settings: Any,
    *,
    app_state: Any | None = None,
    check_db: bool = False,
    check_llm: bool = False,
    ollama_probe: dict[str, Any] | None = None,
) -> dict[str, Any]:
    startup_stage = str(getattr(app_state, "runtime_boot_stage", "ready") or "ready")
    startup_ready = bool(getattr(app_state, "runtime_boot_ready", True))
    startup_error_message = str(getattr(app_state, "runtime_boot_error_message", "") or "").strip() or None
    startup_error_code = str(getattr(app_state, "runtime_boot_error_code", "") or "").strip() or None

    database_scheme = urlparse(str(settings.database_url or "")).scheme or str(settings.database_url).split(":", 1)[0]
    database_info: dict[str, Any] = {
        "configured": bool(str(settings.database_url or "").strip()),
        "scheme": database_scheme or None,
        "allow_production_sqlite": bool(getattr(settings, "allow_production_sqlite", False)),
        "auto_create_tables": bool(getattr(settings, "database_auto_create_tables", True)),
        "connected": None,
        "error": None,
    }

    if check_db and startup_ready:
        try:
            from unifoli_api.core.database import engine

            with engine.connect() as connection:
                connection.execute(text("SELECT 1"))
            database_info["connected"] = True
        except Exception as exc:  # noqa: BLE001
            startup_ready = False
            startup_error_message = str(exc).strip() or "Database connectivity probe failed."
            startup_error_code = startup_error_code or classify_startup_failure(exc)
            database_info["connected"] = False
            database_info["error"] = startup_error_message
    elif check_db:
        database_info["connected"] = False

    storage_info = {
        "provider": str(getattr(settings, "unifoli_storage_provider", "local") or "local"),
        "bucket": getattr(settings, "s3_bucket_name", None),
    }

    resolved_pdf_ollama = (
        getattr(settings, "pdf_analysis_ollama_base_url", None)
        or getattr(settings, "ollama_base_url", None)
        or ""
    )
    llm_info: dict[str, Any] = {
        "default_provider": getattr(settings, "llm_provider", "gemini"),
        "guided_chat_provider": getattr(settings, "guided_chat_llm_provider", None) or getattr(settings, "llm_provider", "gemini"),
        "diagnosis_provider": getattr(settings, "diagnosis_llm_provider", None) or getattr(settings, "llm_provider", "gemini"),
        "render_provider": getattr(settings, "render_llm_provider", None) or getattr(settings, "llm_provider", "gemini"),
        "gemini_api_key_configured": bool(getattr(settings, "gemini_api_key", None)),
        "gemini_model": getattr(settings, "gemini_model", None),
        "ollama_base_url": getattr(settings, "ollama_base_url", None),
        "ollama_localhost_only": _is_local_host_url(getattr(settings, "ollama_base_url", None)),
        "pdf_analysis_provider": getattr(settings, "pdf_analysis_llm_provider", None),
        "pdf_analysis_gemini_api_key_configured": bool(
            getattr(settings, "pdf_analysis_gemini_api_key", None) or getattr(settings, "gemini_api_key", None)
        ),
        "pdf_analysis_ollama_base_url": resolved_pdf_ollama or None,
        "pdf_analysis_ollama_localhost_only": _is_local_host_url(resolved_pdf_ollama),
    }

    if check_llm and ollama_probe:
        llm_info.update(ollama_probe)

    firebase_service_account_inline = bool(
        (os.getenv("FIREBASE_SERVICE_ACCOUNT_JSON") or "").strip()
        or (os.getenv("FIREBASE_SERVICE_ACCOUNT_JSON_BASE64") or "").strip()
        or str(getattr(settings, "firebase_service_account_json", "") or "").strip()
        or str(getattr(settings, "firebase_service_account_json_base64", "") or "").strip()
    )
    google_application_credentials = (os.getenv("GOOGLE_APPLICATION_CREDENTIALS") or "").strip() or str(
        getattr(settings, "google_application_credentials", "") or ""
    ).strip()
    resolved_google_application_credentials = (
        resolve_runtime_path(google_application_credentials).expanduser()
        if google_application_credentials
        else None
    )
    auth_info = {
        "jwt_configured": bool(getattr(settings, "auth_jwt_secret", None) or getattr(settings, "auth_jwt_public_key", None)),
        "firebase_project_configured": bool(
            (os.getenv("FIREBASE_PROJECT_ID") or "").strip()
            or (os.getenv("GOOGLE_CLOUD_PROJECT") or "").strip()
            or (os.getenv("GCLOUD_PROJECT") or "").strip()
            or str(getattr(settings, "firebase_project_id", "") or "").strip()
        ),
        "firebase_service_account_configured": firebase_service_account_inline
        or bool(resolved_google_application_credentials and resolved_google_application_credentials.exists()),
        "social_login_enabled": bool(getattr(settings, "auth_social_login_enabled", False)),
    }

    startup_error_code = startup_error_code or (classify_startup_failure(startup_error_message) if startup_error_message else None)
    payload = {
        "status": "ok" if startup_ready else "degraded",
        "boot_ok": startup_ready,
        "runtime": {
            "app_env": getattr(settings, "app_env", "production"),
            "serverless_runtime": bool(getattr(settings, "serverless_runtime", False)),
            "api_prefix": getattr(settings, "api_prefix", "/api/v1"),
        },
        "storage": storage_info,
        "database": database_info,
        "llm": llm_info,
        "auth": auth_info,
        "startup": {
            "stage": startup_stage,
            "error_code": startup_error_code,
            "message": startup_error_message,
            "remediation": remediation_for_error_code(startup_error_code),
        },
    }
    return payload
