from __future__ import annotations

from unifoli_api.core.config import Settings
from unifoli_api.core.llm import (
    GeminiClient,
    OllamaClient,
    RobustLLMClient,
    _select_ollama_fallback_model,
    get_llm_client,
    resolve_llm_runtime,
)


class _FakeGeminiClient(GeminiClient):
    def __init__(self, api_key: str, *, model_name: str = "gemini-2.5-flash-lite") -> None:
        self.api_key = api_key
        self.model_name = model_name

    async def generate_json(self, prompt, response_model, system_instruction=None, temperature=0.2):  # noqa: ANN001
        raise NotImplementedError

    async def stream_chat(self, prompt, system_instruction=None, temperature=0.5):  # noqa: ANN001
        if False:  # pragma: no cover - keep async generator contract.
            yield ""


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


def test_ollama_production_localhost_is_rejected(monkeypatch) -> None:
    settings = Settings(
        _env_file=None,
        app_env="production",
        llm_provider="ollama",
        gemini_api_key=None,
        ollama_base_url="http://localhost:11434/v1",
        ollama_model="gemma4",
    )
    monkeypatch.setattr("unifoli_api.core.llm.get_settings", lambda: settings)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.delenv("GENAI_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_KEY", raising=False)

    resolution = resolve_llm_runtime(profile="standard")

    assert resolution.client is None
    assert resolution.fallback_used is True
    assert resolution.fallback_reason == "ollama_localhost_blocked_in_deployed_runtime"


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


def test_provider_fallback_can_be_disabled_for_gemini_only_runtime(monkeypatch) -> None:
    settings = Settings(
        _env_file=None,
        app_env="production",
        app_debug=False,
        auth_allow_local_dev_bypass=False,
        llm_provider="gemini",
        llm_provider_fallback_enabled=False,
        ollama_base_url="https://ollama.example.com/v1",
        ollama_model="gemma4-main",
    )
    monkeypatch.setattr("unifoli_api.core.llm.get_settings", lambda: settings)
    monkeypatch.setattr("unifoli_api.core.llm.GeminiClient", _FakeGeminiClient)
    monkeypatch.setenv("GEMINI_API_KEY", "test-gemini-key")

    resolution = resolve_llm_runtime(profile="standard")

    assert isinstance(resolution.client, GeminiClient)
    assert not isinstance(resolution.client, RobustLLMClient)
    assert resolution.actual_provider == "gemini"
    assert resolution.fallback_used is False


def test_provider_fallback_disabled_does_not_use_ollama_when_gemini_is_unavailable(monkeypatch) -> None:
    settings = Settings(
        _env_file=None,
        app_env="production",
        app_debug=False,
        auth_allow_local_dev_bypass=False,
        llm_provider="gemini",
        llm_provider_fallback_enabled=False,
        gemini_api_key=None,
        ollama_base_url="https://ollama.example.com/v1",
        ollama_model="gemma4-main",
    )
    monkeypatch.setattr("unifoli_api.core.llm.get_settings", lambda: settings)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.delenv("GENAI_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_KEY", raising=False)

    resolution = resolve_llm_runtime(profile="standard")

    assert resolution.client is None
    assert resolution.actual_provider is None
    assert resolution.fallback_used is True
    assert resolution.fallback_reason == "gemini_api_key_missing"


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
    monkeypatch.setattr("unifoli_api.core.llm.GeminiClient", _FakeGeminiClient)
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
    monkeypatch.setattr("unifoli_api.core.llm.GeminiClient", _FakeGeminiClient)
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


def test_guided_chat_concern_uses_provider_override_without_default_fallback(monkeypatch) -> None:
    settings = Settings(
        _env_file=None,
        app_env="production",
        app_debug=False,
        auth_allow_local_dev_bypass=False,
        llm_provider="gemini",
        guided_chat_llm_provider="ollama",
        gemini_api_key=None,
        ollama_base_url="https://ollama.example.com/v1",
        ollama_model="gemma4-main",
        ollama_fast_model="gemma4-fast",
    )
    monkeypatch.setattr("unifoli_api.core.llm.get_settings", lambda: settings)

    resolution = resolve_llm_runtime(profile="fast", concern="guided_chat")

    assert resolution.attempted_provider == "ollama"
    assert resolution.attempted_model == "gemma4-fast"
    assert resolution.actual_provider == "ollama"
    assert resolution.fallback_used is False
    assert isinstance(resolution.client, OllamaClient)


def test_render_concern_uses_provider_override_and_render_profile(monkeypatch) -> None:
    settings = Settings(
        _env_file=None,
        app_env="production",
        app_debug=False,
        auth_allow_local_dev_bypass=False,
        llm_provider="gemini",
        render_llm_provider="ollama",
        gemini_api_key=None,
        ollama_base_url="https://ollama.example.com/v1",
        ollama_model="gemma4-main",
        ollama_render_model="gemma4-render",
    )
    monkeypatch.setattr("unifoli_api.core.llm.get_settings", lambda: settings)

    resolution = resolve_llm_runtime(profile="render", concern="render")

    assert resolution.attempted_provider == "ollama"
    assert resolution.attempted_model == "gemma4-render"
    assert resolution.actual_provider == "ollama"
    assert resolution.fallback_used is False
    assert isinstance(resolution.client, OllamaClient)


def test_render_live_generation_uses_render_runtime_resolution(monkeypatch) -> None:
    from unifoli_api.services.workshop_render_service import _supports_live_generation

    settings = Settings(
        _env_file=None,
        app_env="production",
        app_debug=False,
        auth_allow_local_dev_bypass=False,
        llm_provider="gemini",
        render_llm_provider="ollama",
        gemini_api_key=None,
        ollama_base_url="https://ollama.example.com/v1",
        ollama_model="gemma4-main",
        ollama_render_model="gemma4-render",
    )
    monkeypatch.setattr("unifoli_api.core.llm.get_settings", lambda: settings)

    assert _supports_live_generation() is True

