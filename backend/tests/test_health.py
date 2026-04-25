from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

from fastapi.testclient import TestClient

from unifoli_api.api.routes import health as health_route
from unifoli_api.core.config import Settings, get_settings
from unifoli_api.core.runtime_diagnostics import build_health_payload, snapshot_settings_from_env
from unifoli_api.main import app, create_app


def _clear_settings_cache() -> None:
    get_settings.cache_clear()


def _probe_boot_payload_in_subprocess(
    *,
    env: dict[str, str],
    path: str,
    repo_root: Path,
) -> tuple[int, dict[str, object]]:
    script = f"""
import json
import sys
from fastapi.testclient import TestClient

sys.path.insert(0, "backend")
import main

with TestClient(main.app) as client:
    response = client.get({path!r})
    print(json.dumps({{"status_code": response.status_code, "payload": response.json()}}))
"""
    process = subprocess.run(
        [sys.executable, "-c", script],
        cwd=str(repo_root),
        env=env,
        capture_output=True,
        text=True,
        check=True,
    )
    lines = [line for line in process.stdout.splitlines() if line.strip()]
    payload = json.loads(lines[-1])
    return int(payload["status_code"]), payload["payload"]


def test_health_check() -> None:
    with TestClient(app) as client:
        response = client.get("/api/v1/health")
        assert response.status_code == 200
        payload = response.json()
        assert payload["status"] == "ok"
        assert payload["boot_ok"] is True
        assert payload["runtime"]["api_prefix"] == "/api/v1"
        assert "database" in payload
        assert "llm" in payload


def test_readiness_reports_database_probe() -> None:
    with TestClient(app) as client:
        response = client.get("/api/v1/readiness")
        assert response.status_code == 200
        payload = response.json()
        assert payload["status"] == "ok"
        assert payload["database"]["connected"] is True


def test_health_check_llm_probe_uses_ttl_cache(monkeypatch) -> None:
    settings = get_settings()
    original_provider = settings.llm_provider
    settings.llm_provider = "ollama"

    call_count = 0

    async def fake_probe(*, profile: str = "fast"):
        nonlocal call_count
        call_count += 1
        return True, None

    monkeypatch.setattr(health_route, "probe_ollama_connectivity", fake_probe)
    health_route._ollama_health_cache["checked_at"] = 0.0
    health_route._ollama_health_cache["ok"] = True
    health_route._ollama_health_cache["reason"] = None

    try:
        with TestClient(app) as client:
            first = client.get("/api/v1/health?check_llm=true")
            second = client.get("/api/v1/health?check_llm=true")
        assert first.status_code == 200
        assert second.status_code == 200
        assert first.json()["llm"]["ollama_reachable"] is True
        assert second.json()["llm"]["ollama_reachable"] is True
        assert second.json()["llm"]["ollama_cached"] is True
        assert call_count == 1
    finally:
        settings.llm_provider = original_provider


def test_create_app_returns_boot_failure_health_when_serverless_database_url_is_missing(monkeypatch) -> None:
    _clear_settings_cache()
    database_url = "sqlite:///./storage/runtime/unifoli.db?check_same_thread=False&timeout=30"

    monkeypatch.setenv("VERCEL", "1")
    monkeypatch.setenv("VERCEL_ENV", "production")
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("APP_DEBUG", "false")
    monkeypatch.setenv("AUTH_ALLOW_LOCAL_DEV_BYPASS", "false")
    monkeypatch.setenv("AUTH_SOCIAL_LOGIN_ENABLED", "false")
    monkeypatch.setenv("CORS_ORIGINS", "https://uni-foli.vercel.app")
    monkeypatch.setenv("LLM_PROVIDER", "gemini")
    monkeypatch.setenv("DATABASE_URL", database_url)
    monkeypatch.delenv("ALLOW_PRODUCTION_SQLITE", raising=False)

    try:
        with TestClient(create_app()) as client:
            response = client.get("/api/v1/health")
        assert response.status_code == 503
        payload = response.json()
        assert payload["status"] == "degraded"
        assert payload["boot_ok"] is False
        assert payload["startup"]["stage"] == "settings"
        assert payload["startup"]["error_code"] == "DATABASE_URL_REQUIRED"
        assert "DATABASE_URL" in (payload["startup"]["remediation"] or "")
    finally:
        _clear_settings_cache()


def test_create_app_surfaces_schema_not_ready_without_crashing(monkeypatch, tmp_path: Path) -> None:
    database_url = f"sqlite:///{(tmp_path / 'serverless-runtime.db').as_posix()}?check_same_thread=False&timeout=30"
    repo_root = Path(__file__).resolve().parents[2]

    monkeypatch.setenv("VERCEL", "1")
    monkeypatch.setenv("VERCEL_ENV", "production")
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("APP_DEBUG", "false")
    monkeypatch.setenv("AUTH_ALLOW_LOCAL_DEV_BYPASS", "false")
    monkeypatch.setenv("AUTH_SOCIAL_LOGIN_ENABLED", "false")
    monkeypatch.setenv("CORS_ORIGINS", "https://uni-foli.vercel.app")
    monkeypatch.setenv("LLM_PROVIDER", "gemini")
    monkeypatch.setenv("ALLOW_PRODUCTION_SQLITE", "true")
    monkeypatch.setenv("DATABASE_URL", database_url)

    env = dict(os.environ)
    env.update(
        {
            "VERCEL": "1",
            "VERCEL_ENV": "production",
            "APP_ENV": "production",
            "APP_DEBUG": "false",
            "AUTH_ALLOW_LOCAL_DEV_BYPASS": "false",
            "AUTH_SOCIAL_LOGIN_ENABLED": "false",
            "CORS_ORIGINS": "https://uni-foli.vercel.app",
            "LLM_PROVIDER": "gemini",
            "ALLOW_PRODUCTION_SQLITE": "true",
            "DATABASE_URL": database_url,
        }
    )

    health_status, health_payload = _probe_boot_payload_in_subprocess(
        env=env,
        path="/api/v1/health",
        repo_root=repo_root,
    )
    upload_status, upload_payload = _probe_boot_payload_in_subprocess(
        env=env,
        path="/api/v1/documents/upload",
        repo_root=repo_root,
    )

    assert health_status == 503
    assert health_payload["startup"]["stage"] == "database_initialization"
    assert health_payload["startup"]["error_code"] == "DB_SCHEMA_MISMATCH"
    assert "migrations" in (health_payload["startup"]["remediation"] or "").lower()

    assert upload_status == 503
    assert upload_payload["startup"]["error_code"] == "DB_SCHEMA_MISMATCH"


def test_root_page_hides_docs_when_disabled_in_production() -> None:
    settings = get_settings()
    original = (
        settings.app_env,
        settings.api_docs_enabled,
        settings.api_root_redirect_enabled,
        settings.public_app_base_url,
    )
    settings.app_env = "production"
    settings.api_docs_enabled = False
    settings.api_root_redirect_enabled = True
    settings.public_app_base_url = "https://uni-foli.vercel.app/app"

    try:
        with TestClient(create_app()) as client:
            response = client.get("/", follow_redirects=False)
            assert response.status_code == 307
            assert response.headers["location"] == "https://uni-foli.vercel.app/app"
            assert client.get("/docs").status_code == 404
    finally:
        (
            settings.app_env,
            settings.api_docs_enabled,
            settings.api_root_redirect_enabled,
            settings.public_app_base_url,
        ) = original


def test_root_page_shows_backend_info_in_local() -> None:
    settings = get_settings()
    original = (
        settings.app_env,
        settings.api_docs_enabled,
        settings.api_root_redirect_enabled,
    )
    settings.app_env = "local"
    settings.api_docs_enabled = False
    settings.api_root_redirect_enabled = True

    try:
        with TestClient(create_app()) as client:
            response = client.get("/")
            assert response.status_code == 200
            assert "Open API Docs" in response.text
    finally:
        settings.app_env, settings.api_docs_enabled, settings.api_root_redirect_enabled = original


def test_health_payload_reads_firebase_bootstrap_flags_from_loaded_settings(tmp_path: Path) -> None:
    credential_path = tmp_path / "firebase-service-account.json"
    credential_path.write_text("{}", encoding="utf-8")

    settings = SimpleNamespace(
        database_url="sqlite:///:memory:",
        allow_production_sqlite=True,
        database_auto_create_tables=True,
        unifoli_storage_provider="local",
        s3_bucket_name=None,
        llm_provider="gemini",
        guided_chat_llm_provider=None,
        diagnosis_llm_provider=None,
        render_llm_provider=None,
        gemini_api_key=None,
        gemini_model="gemini-2.0-flash",
        ollama_base_url="http://localhost:11434/v1",
        pdf_analysis_ollama_base_url=None,
        pdf_analysis_llm_provider="ollama",
        pdf_analysis_gemini_api_key=None,
        auth_jwt_secret=None,
        auth_jwt_public_key=None,
        firebase_project_id="loaded-from-settings",
        google_application_credentials=str(credential_path),
        firebase_service_account_json=None,
        firebase_service_account_json_base64=None,
        auth_social_login_enabled=False,
        app_env="local",
        serverless_runtime=False,
        api_prefix="/api/v1",
    )
    app_state = SimpleNamespace(
        runtime_boot_stage="ready",
        runtime_boot_ready=True,
        runtime_boot_error_message=None,
        runtime_boot_error_code=None,
    )

    payload = build_health_payload(settings, app_state=app_state)

    assert payload["auth"]["firebase_project_configured"] is True
    assert payload["auth"]["firebase_service_account_configured"] is True


def test_health_payload_exposes_concern_specific_llm_resolution() -> None:
    settings = Settings(
        _env_file=None,
        app_env="production",
        app_debug=False,
        auth_allow_local_dev_bypass=False,
        llm_provider="gemini",
        guided_chat_llm_provider="ollama",
        render_llm_provider="ollama",
        gemini_api_key=None,
        gemini_model="gemini-health",
        ollama_base_url="https://ollama.example.com/v1",
        ollama_model="gemma4-main",
        ollama_fast_model="gemma4-fast",
        ollama_render_model="gemma4-render",
        pdf_analysis_llm_provider="ollama",
        pdf_analysis_ollama_base_url="https://pdf-ollama.example.com/v1",
        pdf_analysis_ollama_model="gemma4-pdf",
    )
    app_state = SimpleNamespace(
        runtime_boot_stage="ready",
        runtime_boot_ready=True,
        runtime_boot_error_message=None,
        runtime_boot_error_code=None,
    )

    payload = build_health_payload(settings, app_state=app_state)
    concerns = payload["llm"]["concerns"]

    assert set(concerns) >= {"default", "guided_chat", "diagnosis", "render", "pdf_analysis"}
    assert concerns["guided_chat"]["requested_provider"] == "ollama"
    assert concerns["guided_chat"]["requested_model"] == "gemma4-fast"
    assert concerns["guided_chat"]["actual_provider"] == "ollama"
    assert concerns["guided_chat"]["fallback_used"] is False
    assert concerns["guided_chat"]["client_available"] is True
    assert concerns["render"]["requested_provider"] == "ollama"
    assert concerns["render"]["requested_model"] == "gemma4-render"
    assert concerns["pdf_analysis"]["requested_provider"] == "ollama"
    assert concerns["pdf_analysis"]["requested_model"] == "gemma4-pdf"
    assert payload["llm"]["gemini_api_key_configured"] is False


def test_snapshot_settings_from_env_accepts_google_api_key_alias(monkeypatch) -> None:
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("PDF_ANALYSIS_GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_KEY", raising=False)
    monkeypatch.setenv("GOOGLE_API_KEY", "test-google-api-key")

    settings = snapshot_settings_from_env()

    assert settings.gemini_api_key == "test-google-api-key"
    assert settings.pdf_analysis_gemini_api_key == "test-google-api-key"


def test_snapshot_settings_from_env_accepts_gemini_key_alias(monkeypatch) -> None:
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("PDF_ANALYSIS_GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.delenv("GENAI_API_KEY", raising=False)
    monkeypatch.setenv("GEMINI_KEY", "test-gemini-key")

    settings = snapshot_settings_from_env()

    assert settings.gemini_api_key == "test-gemini-key"
    assert settings.pdf_analysis_gemini_api_key == "test-gemini-key"
