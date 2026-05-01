from __future__ import annotations

from unifoli_api.core.config import Settings


def test_serverless_runtime_reports_sqlite_without_escape_hatch(monkeypatch) -> None:
    monkeypatch.setenv("VERCEL", "1")
    monkeypatch.setenv("VERCEL_ENV", "production")

    settings = Settings(
        _env_file=None,
        app_env="production",
        app_debug=False,
        auth_allow_local_dev_bypass=False,
        llm_provider="gemini",
        database_url="sqlite:///./storage/runtime/unifoli.db?check_same_thread=False&timeout=30",
    )

    assert settings.serverless_runtime is True
    assert settings.allow_production_sqlite is False
    assert settings.database_url.startswith("sqlite:///")


def test_serverless_runtime_allows_sqlite_with_explicit_escape_hatch(monkeypatch) -> None:
    monkeypatch.setenv("VERCEL", "1")
    monkeypatch.setenv("VERCEL_ENV", "preview")

    settings = Settings(
        _env_file=None,
        app_env="production",
        app_debug=False,
        auth_allow_local_dev_bypass=False,
        llm_provider="gemini",
        allow_production_sqlite=True,
        database_url="sqlite:///./storage/runtime/unifoli.db?check_same_thread=False&timeout=30",
    )

    assert settings.allow_production_sqlite is True


def test_serverless_runtime_does_not_crash_on_local_ollama_endpoint(monkeypatch) -> None:
    monkeypatch.setenv("VERCEL", "1")
    monkeypatch.setenv("VERCEL_ENV", "production")

    settings = Settings(
        _env_file=None,
        app_env="production",
        app_debug=False,
        auth_allow_local_dev_bypass=False,
        llm_provider="ollama",
        ollama_base_url="http://localhost:11434/v1",
        allow_production_sqlite=True,
        database_url="sqlite:///./storage/runtime/unifoli.db?check_same_thread=False&timeout=30",
    )

    assert settings.llm_provider == "ollama"


def test_empty_llm_provider_falls_back_to_gemini(monkeypatch) -> None:
    monkeypatch.setenv("VERCEL", "1")
    monkeypatch.setenv("VERCEL_ENV", "production")

    settings = Settings(
        _env_file=None,
        app_env="production",
        app_debug=False,
        auth_allow_local_dev_bypass=False,
        llm_provider="",
        database_url="postgresql+psycopg://user:password@db.example.com/unifoli",
    )

    assert settings.llm_provider == "gemini"


def test_postgresql_url_uses_psycopg_driver() -> None:
    settings = Settings(
        _env_file=None,
        app_env="production",
        app_debug=False,
        auth_allow_local_dev_bypass=False,
        llm_provider="gemini",
        database_url="postgresql://user:password@db.example.com/unifoli",
    )

    assert settings.database_url.startswith("postgresql+psycopg://")


def test_serverless_runtime_infers_vercel_blob_when_token_is_configured(monkeypatch) -> None:
    monkeypatch.setenv("VERCEL", "1")
    monkeypatch.setenv("VERCEL_ENV", "production")
    monkeypatch.setenv("BLOB_READ_WRITE_TOKEN", "vercel-blob-token")

    settings = Settings(
        _env_file=None,
        app_env="production",
        app_debug=False,
        auth_allow_local_dev_bypass=False,
        llm_provider="gemini",
        database_url="postgresql+psycopg://user:password@db.example.com/unifoli",
    )

    assert settings.unifoli_storage_provider == "vercel_blob"


def test_serverless_postgres_pool_allows_small_overflow(monkeypatch) -> None:
    monkeypatch.setenv("VERCEL", "1")
    monkeypatch.setenv("VERCEL_ENV", "production")

    settings = Settings(
        _env_file=None,
        app_env="production",
        app_debug=False,
        auth_allow_local_dev_bypass=False,
        llm_provider="gemini",
        database_url="postgresql+psycopg://user:password@db.example.com/unifoli",
    )

    from unifoli_api.core.database import _build_engine_kwargs

    kwargs = _build_engine_kwargs(settings)

    assert kwargs["pool_size"] == 1
    assert kwargs["max_overflow"] >= 2
    assert kwargs["pool_timeout"] == settings.database_pool_timeout_seconds

