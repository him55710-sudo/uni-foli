from __future__ import annotations

import abc
import json
import logging
import os
import time
from dataclasses import dataclass
from typing import Any, AsyncIterator, Literal, Type, TypeVar
from urllib.parse import urlparse

from openai import APIConnectionError, APIError, APITimeoutError, AsyncOpenAI, BadRequestError
from pydantic import BaseModel

from polio_api.core.config import get_settings

T = TypeVar("T", bound=BaseModel)
LLMProfile = Literal["fast", "standard", "render"]

logger = logging.getLogger("polio.llm")
_OLLAMA_LOG_COOLDOWN_SECONDS = 120.0
_last_ollama_failure_logs: dict[str, float] = {}


class LLMRequestError(RuntimeError):
    """Provider errors that should trigger deterministic fallback UI behavior."""

    def __init__(
        self,
        user_message: str,
        *,
        limited_reason: str,
        provider: str,
        profile: str,
    ) -> None:
        super().__init__(user_message)
        self.user_message = user_message
        self.limited_reason = limited_reason
        self.provider = provider
        self.profile = profile


@dataclass(frozen=True)
class OllamaRuntimeProfile:
    name: LLMProfile
    model: str
    request_timeout_seconds: float
    keep_alive: str | None
    num_ctx: int
    num_predict: int
    num_thread: int | None
    temperature: float


class LLMClient(abc.ABC):
    @abc.abstractmethod
    async def generate_json(
        self,
        prompt: str,
        response_model: Type[T],
        system_instruction: str | None = None,
        temperature: float = 0.2,
    ) -> T:
        """Generate a structured JSON response from the LLM."""
        pass

    @abc.abstractmethod
    async def stream_chat(
        self,
        prompt: str,
        system_instruction: str | None = None,
        temperature: float = 0.5,
    ) -> AsyncIterator[str]:
        """Stream chat tokens from the LLM."""
        pass


class GeminiClient(LLMClient):
    def __init__(self, api_key: str):
        from google import genai

        self.client = genai.Client(api_key=api_key)
        self.model_name = "gemini-2.0-flash"

    async def generate_json(
        self,
        prompt: str,
        response_model: Type[T],
        system_instruction: str | None = None,
        temperature: float = 0.2,
    ) -> T:
        response = await self.client.models.generate_content_async(
            model=self.model_name,
            contents=prompt,
            config={
                "system_instruction": system_instruction,
                "response_mime_type": "application/json",
                "response_schema": response_model,
                "temperature": temperature,
            },
        )
        return response_model.model_validate_json(response.text)

    async def stream_chat(
        self,
        prompt: str,
        system_instruction: str | None = None,
        temperature: float = 0.5,
    ) -> AsyncIterator[str]:
        response_stream = await self.client.models.generate_content_stream_async(
            model=self.model_name,
            contents=prompt,
            config={
                "system_instruction": system_instruction,
                "temperature": temperature,
            },
        )
        async for chunk in response_stream:
            if chunk.text:
                yield chunk.text


class OllamaClient(LLMClient):
    def __init__(
        self,
        base_url: str,
        model: str,
        *,
        profile_name: str = "standard",
        request_timeout_seconds: float = 90.0,
        keep_alive: str | None = "30m",
        num_ctx: int | None = 2048,
        num_predict: int | None = 512,
        num_thread: int | None = None,
        default_temperature: float = 0.35,
    ):
        self.base_url = (base_url or "").strip()
        self.profile_name = profile_name
        self.client = AsyncOpenAI(
            base_url=self.base_url,
            api_key="ollama",  # Required by SDK, ignored by Ollama-compatible hosts.
            timeout=request_timeout_seconds,
            max_retries=1,
        )
        self.model = model
        self.keep_alive = keep_alive
        self.default_temperature = default_temperature
        self.options: dict[str, int] = {}
        if num_ctx is not None:
            self.options["num_ctx"] = num_ctx
        if num_predict is not None:
            self.options["num_predict"] = num_predict
        if num_thread is not None:
            self.options["num_thread"] = num_thread

    def _extra_body(self) -> dict[str, Any] | None:
        payload: dict[str, Any] = {}
        if self.keep_alive:
            payload["keep_alive"] = self.keep_alive
        if self.options:
            payload["options"] = self.options
        return payload or None

    async def check_connectivity(self) -> tuple[bool, str | None]:
        try:
            await self.client.models.list()
            return True, None
        except Exception as exc:  # noqa: BLE001
            reason = _classify_ollama_failure(exc)
            _log_ollama_failure_once(
                reason,
                base_url=self.base_url,
                model=self.model,
                profile=self.profile_name,
                exc=exc,
            )
            return False, reason

    async def generate_json(
        self,
        prompt: str,
        response_model: Type[T],
        system_instruction: str | None = None,
        temperature: float = 0.2,
    ) -> T:
        messages: list[dict[str, str]] = []
        if system_instruction:
            messages.append({"role": "system", "content": system_instruction})
        messages.append(
            {
                "role": "user",
                "content": (
                    f"{prompt}\n\n"
                    "Please respond in JSON format strictly following this schema:\n"
                    f"{json.dumps(response_model.model_json_schema(), ensure_ascii=False)}"
                ),
            }
        )

        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=temperature,
                response_format={"type": "json_object"},
                extra_body=self._extra_body(),
            )
        except Exception as exc:  # noqa: BLE001
            raise _to_ollama_request_error(
                exc,
                base_url=self.base_url,
                model=self.model,
                profile=self.profile_name,
            ) from exc

        content = response.choices[0].message.content
        if not content:
            raise LLMRequestError(
                "LLM 응답이 비어 있어 제한 모드로 전환합니다.",
                limited_reason="empty_response",
                provider="ollama",
                profile=self.profile_name,
            )

        try:
            return response_model.model_validate_json(content)
        except Exception as exc:  # noqa: BLE001
            raise LLMRequestError(
                "응답 형식을 해석하지 못해 제한 모드로 전환합니다.",
                limited_reason="invalid_json",
                provider="ollama",
                profile=self.profile_name,
            ) from exc

    async def stream_chat(
        self,
        prompt: str,
        system_instruction: str | None = None,
        temperature: float = 0.5,
    ) -> AsyncIterator[str]:
        messages: list[dict[str, str]] = []
        if system_instruction:
            messages.append({"role": "system", "content": system_instruction})
        messages.append({"role": "user", "content": prompt})

        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=temperature,
                stream=True,
                extra_body=self._extra_body(),
            )
            async for chunk in response:
                if chunk.choices and chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content
        except Exception as exc:  # noqa: BLE001
            raise _to_ollama_request_error(
                exc,
                base_url=self.base_url,
                model=self.model,
                profile=self.profile_name,
            ) from exc


def get_llm_client(*, profile: LLMProfile = "standard") -> LLMClient:
    settings = get_settings()
    provider = (settings.llm_provider or "gemini").strip().lower()
    api_key = (settings.gemini_api_key or os.environ.get("GEMINI_API_KEY") or "").strip()
    has_valid_gemini_key = bool(api_key) and api_key != "DUMMY_KEY"

    if provider == "ollama":
        return _build_ollama_client(profile=profile)

    if provider not in {"gemini", "ollama"}:
        if settings.app_env == "local" and not has_valid_gemini_key:
            return _build_ollama_client(profile=profile)
        raise RuntimeError(f"Unsupported LLM provider: {settings.llm_provider}")

    if has_valid_gemini_key:
        return GeminiClient(api_key=api_key)

    if _has_remote_ollama_endpoint(settings.ollama_base_url):
        logger.warning(
            "Gemini API key is missing; falling back to remote Ollama profile=%s base_url=%s",
            profile,
            settings.ollama_base_url,
        )
        return _build_ollama_client(profile=profile)

    if settings.app_env == "local":
        return _build_ollama_client(profile=profile)

    raise RuntimeError("Gemini API key is not configured.")


def get_llm_temperature(*, profile: LLMProfile = "standard") -> float:
    settings = get_settings()
    provider = (settings.llm_provider or "gemini").strip().lower()
    if provider == "ollama":
        return _resolve_ollama_runtime_profile(profile).temperature
    if profile == "fast":
        return 0.25
    if profile == "render":
        return 0.22
    return 0.35


async def probe_ollama_connectivity(*, profile: LLMProfile = "standard") -> tuple[bool, str | None]:
    client = get_llm_client(profile=profile)
    if not isinstance(client, OllamaClient):
        return True, None
    return await client.check_connectivity()


def get_pdf_analysis_llm_client() -> LLMClient:
    settings = get_settings()
    provider = (settings.pdf_analysis_llm_provider or "ollama").strip().lower()
    gemini_api_key = (
        settings.pdf_analysis_gemini_api_key or settings.gemini_api_key or os.environ.get("GEMINI_API_KEY") or ""
    ).strip()

    if provider == "ollama":
        return _build_ollama_client(
            profile="render",
            base_url=settings.pdf_analysis_ollama_base_url or settings.ollama_base_url,
            model=settings.pdf_analysis_ollama_model or settings.ollama_model,
            request_timeout_seconds=settings.pdf_analysis_timeout_seconds,
            keep_alive=settings.pdf_analysis_keep_alive,
            num_ctx=settings.pdf_analysis_num_ctx,
            num_predict=settings.pdf_analysis_num_predict,
            num_thread=settings.pdf_analysis_num_thread,
        )

    if provider == "gemini":
        if not gemini_api_key or gemini_api_key == "DUMMY_KEY":
            raise RuntimeError("PDF analysis Gemini API key is not configured.")
        return GeminiClient(api_key=gemini_api_key)

    raise RuntimeError(f"Unsupported PDF analysis LLM provider: {settings.pdf_analysis_llm_provider}")


def _resolve_ollama_runtime_profile(profile: LLMProfile) -> OllamaRuntimeProfile:
    settings = get_settings()

    base_timeout = float(settings.ollama_timeout_seconds)
    if profile == "fast":
        timeout = float(settings.ollama_fast_timeout_seconds or min(base_timeout, 45.0))
        num_ctx = max(512, min(settings.ollama_num_ctx, 1536))
        num_predict = max(96, min(settings.ollama_num_predict, 240))
        model = (settings.ollama_fast_model or settings.ollama_model).strip()
        temperature = 0.22
    elif profile == "render":
        timeout = float(settings.ollama_render_timeout_seconds or max(base_timeout, 120.0))
        num_ctx = max(settings.ollama_num_ctx, 4096)
        num_predict = max(settings.ollama_num_predict, 900)
        model = (settings.ollama_render_model or settings.ollama_model).strip()
        temperature = 0.24
    else:
        timeout = float(settings.ollama_standard_timeout_seconds or base_timeout)
        num_ctx = max(1024, settings.ollama_num_ctx)
        num_predict = max(256, settings.ollama_num_predict)
        model = (settings.ollama_standard_model or settings.ollama_model).strip()
        temperature = 0.32

    return OllamaRuntimeProfile(
        name=profile,
        model=model or settings.ollama_model,
        request_timeout_seconds=timeout,
        keep_alive=settings.ollama_keep_alive,
        num_ctx=num_ctx,
        num_predict=num_predict,
        num_thread=settings.ollama_num_thread,
        temperature=temperature,
    )


def _build_ollama_client(
    *,
    profile: LLMProfile = "standard",
    base_url: str | None = None,
    model: str | None = None,
    request_timeout_seconds: float | None = None,
    keep_alive: str | None = None,
    num_ctx: int | None = None,
    num_predict: int | None = None,
    num_thread: int | None = None,
) -> OllamaClient:
    settings = get_settings()
    runtime = _resolve_ollama_runtime_profile(profile)
    return OllamaClient(
        base_url=(base_url or settings.ollama_base_url).strip(),
        model=(model or runtime.model).strip(),
        profile_name=profile,
        request_timeout_seconds=(
            request_timeout_seconds if request_timeout_seconds is not None else runtime.request_timeout_seconds
        ),
        keep_alive=runtime.keep_alive if keep_alive is None else keep_alive,
        num_ctx=runtime.num_ctx if num_ctx is None else num_ctx,
        num_predict=runtime.num_predict if num_predict is None else num_predict,
        num_thread=runtime.num_thread if num_thread is None else num_thread,
        default_temperature=runtime.temperature,
    )


def _classify_ollama_failure(exc: Exception) -> str:
    if isinstance(exc, APITimeoutError):
        return "timeout"
    if isinstance(exc, APIConnectionError):
        return "unreachable"
    if isinstance(exc, BadRequestError):
        return "invalid_request"
    if isinstance(exc, APIError):
        return "provider_error"
    if isinstance(exc, OSError):
        return "unreachable"
    return "unknown"


def _has_remote_ollama_endpoint(base_url: str | None) -> bool:
    if not base_url:
        return False
    parsed = urlparse(base_url)
    host = (parsed.hostname or "").strip().lower()
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return False
    return host not in {"localhost", "127.0.0.1", "::1", "0.0.0.0"}


def _log_ollama_failure_once(
    reason: str,
    *,
    base_url: str,
    model: str,
    profile: str,
    exc: Exception,
) -> None:
    key = f"{reason}:{base_url}:{model}:{profile}"
    now = time.monotonic()
    last = _last_ollama_failure_logs.get(key, 0.0)
    if now - last < _OLLAMA_LOG_COOLDOWN_SECONDS:
        return
    _last_ollama_failure_logs[key] = now
    logger.warning(
        "Ollama request issue detected | reason=%s profile=%s model=%s base_url=%s detail=%s",
        reason,
        profile,
        model,
        base_url,
        repr(exc),
    )


def _to_ollama_request_error(
    exc: Exception,
    *,
    base_url: str,
    model: str,
    profile: str,
) -> LLMRequestError:
    reason = _classify_ollama_failure(exc)
    _log_ollama_failure_once(reason, base_url=base_url, model=model, profile=profile, exc=exc)

    if reason in {"timeout", "unreachable"}:
        message = "AI 응답이 지연되어 제한 모드로 전환합니다."
    elif reason == "invalid_request":
        message = "AI 요청 구성이 맞지 않아 제한 모드로 전환합니다."
    else:
        message = "AI 호출 중 오류가 발생해 제한 모드로 전환합니다."

    return LLMRequestError(
        message,
        limited_reason=f"ollama_{reason}",
        provider="ollama",
        profile=profile,
    )
