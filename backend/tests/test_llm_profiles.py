from __future__ import annotations

import pytest

from unifoli_api.core.config import Settings
from unifoli_api.core.llm import (
    GeminiClient,
    OllamaClient,
    RobustLLMClient,
    _select_ollama_fallback_model,
    get_llm_client,
)


def test_ollama_profile_model_fallbacks(monkeypatch) -> None:
    settings = Settings(
        _env_file=None,
        app_env="production",
        app_debug=False,
        auth_allow_local_dev_bypass=False,
        llm_provider="ollama",
        ollama_base_url="https://ollama.example.com/v1",
        ollama_model="gemma4-main",
        ollama_fast_model="gemma4-fast",
        ollama_standard_model="gemma4-standard",
        ollama_render_model=None,
        ollama_fast_timeout_seconds=12,
        ollama_standard_timeout_seconds=60,
        ollama_render_timeout_seconds=180,
    )
    monkeypatch.setattr("unifoli_api.core.llm.get_settings", lambda: settings)

    fast = get_llm_client(profile="fast")
    standard = get_llm_client(profile="standard")
    render = get_llm_client(profile="render")

    assert isinstance(fast, OllamaClient)
    assert isinstance(standard, OllamaClient)
    assert isinstance(render, OllamaClient)

    assert fast.model == "gemma4-fast"
    assert standard.model == "gemma4-standard"
    assert render.model == "gemma4-main"  # profile model fallback
    assert fast.options.get("num_predict", 0) <= 240
    assert render.options.get("num_predict", 0) >= 900


def test_ollama_production_localhost_is_rejected() -> None:
    with pytest.raises(ValueError):
        Settings(
            _env_file=None,
            app_env="production",
            llm_provider="ollama",
            ollama_base_url="http://localhost:11434/v1",
            ollama_model="gemma4",
        )


def test_gemini_missing_key_falls_back_to_remote_ollama(monkeypatch) -> None:
    settings = Settings(
        _env_file=None,
        app_env="production",
        app_debug=False,
        auth_allow_local_dev_bypass=False,
        llm_provider="gemini",
        gemini_api_key=None,
        ollama_base_url="https://ollama.example.com/v1",
        ollama_model="gemma4-main",
    )
    monkeypatch.setattr("unifoli_api.core.llm.get_settings", lambda: settings)

    client = get_llm_client(profile="standard")
    assert isinstance(client, OllamaClient)
    assert client.model == "gemma4-main"


def test_gemini_uses_google_api_key_env_alias(monkeypatch) -> None:
    settings = Settings(
        _env_file=None,
        app_env="production",
        app_debug=False,
        auth_allow_local_dev_bypass=False,
        llm_provider="gemini",
        gemini_api_key=None,
        ollama_base_url="https://ollama.example.com/v1",
        ollama_model="gemma4-main",
    )
    monkeypatch.setattr("unifoli_api.core.llm.get_settings", lambda: settings)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.setenv("GOOGLE_API_KEY", "test-google-api-key")

    client = get_llm_client(profile="standard")
    assert isinstance(client, (GeminiClient, RobustLLMClient))


def test_gemini_uses_gemini_key_env_alias(monkeypatch) -> None:
    settings = Settings(
        _env_file=None,
        app_env="production",
        app_debug=False,
        auth_allow_local_dev_bypass=False,
        llm_provider="gemini",
        gemini_api_key=None,
        ollama_base_url="https://ollama.example.com/v1",
        ollama_model="gemma4-main",
    )
    monkeypatch.setattr("unifoli_api.core.llm.get_settings", lambda: settings)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.setenv("GEMINI_KEY", "test-gemini-key-alias")

    client = get_llm_client(profile="standard")
    assert isinstance(client, (GeminiClient, RobustLLMClient))


def test_select_ollama_fallback_model_prefers_same_family_and_nearest_size() -> None:
    chosen = _select_ollama_fallback_model(
        "qwen2.5:7b",
        ["gemma:latest", "qwen2.5:14b", "qwen2.5:32b"],
    )
    assert chosen == "qwen2.5:14b"


def test_select_ollama_fallback_model_prefers_latest_when_family_missing() -> None:
    chosen = _select_ollama_fallback_model(
        "nonexistent:7b",
        ["gemma3:4b", "gemma:latest", "qwen2.5:14b"],
    )
    assert chosen == "gemma:latest"

