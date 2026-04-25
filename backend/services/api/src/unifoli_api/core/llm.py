from __future__ import annotations

import abc
import asyncio
import json
import logging
import os
import re
import time
from dataclasses import dataclass
from typing import Any, AsyncIterator, Literal, Type, TypeVar
from urllib.parse import urlparse

from openai import APIConnectionError, APIError, APITimeoutError, AsyncOpenAI, BadRequestError, NotFoundError
from pydantic import BaseModel

from unifoli_api.core.config import get_settings

T = TypeVar("T", bound=BaseModel)
LLMProfile = Literal["fast", "standard", "render"]
LLMConcern = Literal["default", "guided_chat", "diagnosis", "render", "pdf_analysis"]

logger = logging.getLogger("unifoli.llm")
_OLLAMA_LOG_COOLDOWN_SECONDS = 120.0
_last_ollama_failure_logs: dict[str, float] = {}
_ollama_model_alias_cache: dict[str, str] = {}
DEFAULT_GEMINI_MODEL = "gemini-2.5-flash-lite"


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


@dataclass(frozen=True)
class PDFAnalysisLLMResolution:
    attempted_provider: str
    attempted_model: str
    actual_provider: str
    actual_model: str
    client: LLMClient | None
    fallback_used: bool = False
    fallback_reason: str | None = None


@dataclass(frozen=True)
class LLMRuntimeResolution:
    concern: LLMConcern
    profile: LLMProfile
    attempted_provider: str
    attempted_model: str
    actual_provider: str | None
    actual_model: str | None
    fallback_used: bool
    fallback_reason: str | None
    client: LLMClient | None


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
    def __init__(self, api_key: str, *, model_name: str = DEFAULT_GEMINI_MODEL):
        self.model_name = (model_name or DEFAULT_GEMINI_MODEL).strip() or DEFAULT_GEMINI_MODEL
        self.sdk_variant = "google-genai"
        try:
            from google import genai

            self.client = genai.Client(api_key=api_key)
        except Exception as genai_exc:  # noqa: BLE001
            try:
                import google.generativeai as legacy_genai

                legacy_genai.configure(api_key=api_key)
                self.client = legacy_genai
                self.sdk_variant = "google-generativeai"
                logger.warning(
                    "google-genai SDK unavailable; using legacy google-generativeai Gemini client. error=%s",
                    type(genai_exc).__name__,
                )
            except Exception as legacy_exc:  # noqa: BLE001
                raise genai_exc from legacy_exc
        _initialize_runtime_state(self)

    async def generate_json(
        self,
        prompt: str,
        response_model: Type[T],
        system_instruction: str | None = None,
        temperature: float = 0.2,
    ) -> T:
        started_at = time.perf_counter()
        try:
            if self.sdk_variant == "google-generativeai":
                response = await self._legacy_generate_content(
                    prompt=prompt,
                    system_instruction=system_instruction,
                    temperature=temperature,
                    response_model=response_model,
                    stream=False,
                )
            else:
                config = {
                    "system_instruction": system_instruction,
                    "response_mime_type": "application/json",
                    "response_schema": response_model,
                    "temperature": temperature,
                }
                generate_async = getattr(self.client.models, "generate_content_async", None)
                if callable(generate_async):
                    response = await generate_async(
                        model=self.model_name,
                        contents=prompt,
                        config=config,
                    )
                else:
                    response = await asyncio.to_thread(
                        self.client.models.generate_content,
                        model=self.model_name,
                        contents=prompt,
                        config=config,
                    )
            parsed = response_model.model_validate_json(response.text)
            _record_runtime_success(
                self,
                provider="gemini",
                model=self.model_name,
                operation="generate_json",
                started_at=started_at,
            )
            return parsed
        except Exception as exc:  # noqa: BLE001
            _record_runtime_failure(
                self,
                provider="gemini",
                model=self.model_name,
                operation="generate_json",
                started_at=started_at,
                exc=exc,
            )
            raise

    async def stream_chat(
        self,
        prompt: str,
        system_instruction: str | None = None,
        temperature: float = 0.5,
    ) -> AsyncIterator[str]:
        started_at = time.perf_counter()
        try:
            try:
                if self.sdk_variant == "google-generativeai":
                    response_stream = await self._legacy_generate_content(
                        prompt=prompt,
                        system_instruction=system_instruction,
                        temperature=temperature,
                        stream=True,
                    )
                    async for chunk in response_stream:
                        chunk_text = getattr(chunk, "text", None)
                        if chunk_text:
                            yield str(chunk_text)
                else:
                    config = {
                        "system_instruction": system_instruction,
                        "temperature": temperature,
                    }
                    stream_async = getattr(self.client.models, "generate_content_stream_async", None)
                    if callable(stream_async):
                        response_stream = await stream_async(
                            model=self.model_name,
                            contents=prompt,
                            config=config,
                        )
                        async for chunk in response_stream:
                            if chunk.text:
                                yield chunk.text
                    else:
                        stream_sync = getattr(self.client.models, "generate_content_stream", None)
                        if callable(stream_sync):
                            def _collect_stream_chunks() -> list[str]:
                                chunks: list[str] = []
                                for chunk in stream_sync(
                                    model=self.model_name,
                                    contents=prompt,
                                    config=config,
                                ):
                                    chunk_text = getattr(chunk, "text", None)
                                    if chunk_text:
                                        chunks.append(str(chunk_text))
                                return chunks

                            for token in await asyncio.to_thread(_collect_stream_chunks):
                                yield token
                        else:
                            raise RuntimeError("Gemini stream APIs are unavailable in current SDK.")
            except Exception as stream_exc:  # noqa: BLE001
                logger.warning(
                    "Gemini stream failed; falling back to non-stream generation. model=%s error=%r",
                    self.model_name,
                    stream_exc,
                )
                if self.sdk_variant == "google-generativeai":
                    response = await self._legacy_generate_content(
                        prompt=prompt,
                        system_instruction=system_instruction,
                        temperature=temperature,
                        stream=False,
                    )
                else:
                    response = await asyncio.to_thread(
                        self.client.models.generate_content,
                        model=self.model_name,
                        contents=prompt,
                        config=config,
                    )
                if response.text:
                    yield response.text
            _record_runtime_success(
                self,
                provider="gemini",
                model=self.model_name,
                operation="stream_chat",
                started_at=started_at,
            )
        except Exception as exc:  # noqa: BLE001
            _record_runtime_failure(
                self,
                provider="gemini",
                model=self.model_name,
                operation="stream_chat",
                started_at=started_at,
                exc=exc,
            )
            raise

    async def _legacy_generate_content(
        self,
        *,
        prompt: str,
        system_instruction: str | None,
        temperature: float,
        response_model: Type[BaseModel] | None = None,
        stream: bool = False,
    ) -> Any:
        generation_config: dict[str, Any] = {"temperature": temperature}
        if response_model is not None:
            generation_config["response_mime_type"] = "application/json"
            generation_config["response_schema"] = response_model

        def _call() -> Any:
            model = self.client.GenerativeModel(
                self.model_name,
                system_instruction=system_instruction,
            )
            try:
                return model.generate_content(
                    prompt,
                    generation_config=generation_config,
                    stream=stream,
                )
            except TypeError:
                fallback_config = {"temperature": temperature}
                if response_model is not None:
                    fallback_config["response_mime_type"] = "application/json"
                return model.generate_content(
                    prompt,
                    generation_config=fallback_config,
                    stream=stream,
                )

        response = await asyncio.to_thread(_call)
        if not stream:
            return response

        async def _aiter() -> AsyncIterator[Any]:
            chunks = await asyncio.to_thread(list, response)
            for chunk in chunks:
                yield chunk

        return _aiter()


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
        self.requested_model = (model or "").strip()
        cached_model = _resolve_cached_ollama_model_alias(self.base_url, self.requested_model)
        self.model = cached_model or self.requested_model
        self.keep_alive = keep_alive
        self.default_temperature = default_temperature
        self.options: dict[str, int] = {}
        if num_ctx is not None:
            self.options["num_ctx"] = num_ctx
        if num_predict is not None:
            self.options["num_predict"] = num_predict
        if num_thread is not None:
            self.options["num_thread"] = num_thread
        _initialize_runtime_state(self)

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

    async def _list_available_models(self) -> list[str]:
        try:
            payload = await self.client.models.list()
        except Exception:  # noqa: BLE001
            return []
        models: list[str] = []
        for item in getattr(payload, "data", []) or []:
            model_id = str(getattr(item, "id", "") or "").strip()
            if model_id:
                models.append(model_id)
        return models

    async def _resolve_model_not_found_fallback(self, exc: Exception) -> str | None:
        if _classify_ollama_failure(exc) != "model_not_found":
            return None

        missing_model = _extract_missing_model_from_exception(exc) or self.model or self.requested_model
        if not missing_model:
            return None

        cached_model = _resolve_cached_ollama_model_alias(self.base_url, missing_model)
        if cached_model and cached_model != self.model:
            self.model = cached_model
            return cached_model

        available_models = await self._list_available_models()
        fallback_model = _select_ollama_fallback_model(missing_model, available_models)
        if not fallback_model or fallback_model == self.model:
            return None

        _remember_ollama_model_alias(self.base_url, missing_model, fallback_model)
        if self.requested_model and self.requested_model != missing_model:
            _remember_ollama_model_alias(self.base_url, self.requested_model, fallback_model)
        self.model = fallback_model
        logger.warning(
            "Configured Ollama model was unavailable; retrying with fallback model=%s requested=%s missing=%s base_url=%s profile=%s",
            fallback_model,
            self.requested_model,
            missing_model,
            self.base_url,
            self.profile_name,
        )
        return fallback_model

    async def generate_json(
        self,
        prompt: str,
        response_model: Type[T],
        system_instruction: str | None = None,
        temperature: float = 0.2,
    ) -> T:
        started_at = time.perf_counter()
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

        used_model_fallback = False
        response_model_name = self.model
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=temperature,
                response_format={"type": "json_object"},
                extra_body=self._extra_body(),
            )
        except Exception as exc:  # noqa: BLE001
            fallback_model = await self._resolve_model_not_found_fallback(exc)
            if not fallback_model:
                request_error = _to_ollama_request_error(
                    exc,
                    base_url=self.base_url,
                    model=self.model,
                    profile=self.profile_name,
                )
                _record_runtime_failure(
                    self,
                    provider="ollama",
                    model=self.model,
                    operation="generate_json",
                    started_at=started_at,
                    exc=request_error,
                )
                raise request_error from exc
            try:
                used_model_fallback = True
                response_model_name = fallback_model
                response = await self.client.chat.completions.create(
                    model=fallback_model,
                    messages=messages,
                    temperature=temperature,
                    response_format={"type": "json_object"},
                    extra_body=self._extra_body(),
                )
            except Exception as retry_exc:  # noqa: BLE001
                request_error = _to_ollama_request_error(
                    retry_exc,
                    base_url=self.base_url,
                    model=fallback_model,
                    profile=self.profile_name,
                )
                _record_runtime_failure(
                    self,
                    provider="ollama",
                    model=fallback_model,
                    operation="generate_json",
                    started_at=started_at,
                    exc=request_error,
                )
                raise request_error from retry_exc

        content = response.choices[0].message.content
        if not content:
            request_error = LLMRequestError(
                "LLM 응답이 비어 있어 제한 모드로 전환합니다.",
                limited_reason="empty_response",
                provider="ollama",
                profile=self.profile_name,
            )
            _record_runtime_failure(
                self,
                provider="ollama",
                model=response_model_name,
                operation="generate_json",
                started_at=started_at,
                exc=request_error,
            )
            raise request_error

        try:
            parsed = response_model.model_validate_json(content)
        except Exception as exc:  # noqa: BLE001
            request_error = LLMRequestError(
                "응답 형식을 해석하지 못해 제한 모드로 전환합니다.",
                limited_reason="invalid_json",
                provider="ollama",
                profile=self.profile_name,
            )
            _record_runtime_failure(
                self,
                provider="ollama",
                model=response_model_name,
                operation="generate_json",
                started_at=started_at,
                exc=request_error,
            )
            raise request_error from exc

        if used_model_fallback:
            setattr(self, "last_fallback_used", True)
            setattr(self, "last_fallback_reason", "ollama_model_not_found_fallback")
        _record_runtime_success(
            self,
            provider="ollama",
            model=response_model_name,
            operation="generate_json",
            started_at=started_at,
        )
        return parsed

    async def stream_chat(
        self,
        prompt: str,
        system_instruction: str | None = None,
        temperature: float = 0.5,
    ) -> AsyncIterator[str]:
        started_at = time.perf_counter()
        messages: list[dict[str, str]] = []
        if system_instruction:
            messages.append({"role": "system", "content": system_instruction})
        messages.append({"role": "user", "content": prompt})

        used_model_fallback = False
        response_model_name = self.model
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
            fallback_model = await self._resolve_model_not_found_fallback(exc)
            if not fallback_model:
                request_error = _to_ollama_request_error(
                    exc,
                    base_url=self.base_url,
                    model=self.model,
                    profile=self.profile_name,
                )
                _record_runtime_failure(
                    self,
                    provider="ollama",
                    model=self.model,
                    operation="stream_chat",
                    started_at=started_at,
                    exc=request_error,
                )
                raise request_error from exc
            try:
                used_model_fallback = True
                response_model_name = fallback_model
                response = await self.client.chat.completions.create(
                    model=fallback_model,
                    messages=messages,
                    temperature=temperature,
                    stream=True,
                    extra_body=self._extra_body(),
                )
                async for chunk in response:
                    if chunk.choices and chunk.choices[0].delta.content:
                        yield chunk.choices[0].delta.content
            except Exception as retry_exc:  # noqa: BLE001
                request_error = _to_ollama_request_error(
                    retry_exc,
                    base_url=self.base_url,
                    model=fallback_model,
                    profile=self.profile_name,
                )
                _record_runtime_failure(
                    self,
                    provider="ollama",
                    model=fallback_model,
                    operation="stream_chat",
                    started_at=started_at,
                    exc=request_error,
                )
                raise request_error from retry_exc

        if used_model_fallback:
            setattr(self, "last_fallback_used", True)
            setattr(self, "last_fallback_reason", "ollama_model_not_found_fallback")
        _record_runtime_success(
            self,
            provider="ollama",
            model=response_model_name,
            operation="stream_chat",
            started_at=started_at,
        )


class RobustLLMClient(LLMClient):
    """
    여러 LLM 제공자를 순차적으로 시도하여 실패 없는 호출을 보장하는 클라이언트.
    Gemini를 우선 시도하고, 실패 시 Ollama로 Fallback합니다.
    """

    def __init__(self, primary: LLMClient, fallback: LLMClient | None = None):
        self.primary = primary
        self.fallback = fallback
        _initialize_runtime_state(self)

    async def generate_json(
        self,
        prompt: str,
        response_model: Type[T],
        system_instruction: str | None = None,
        temperature: float = 0.2,
        max_retries: int = 2,
    ) -> T:
        last_exception = None
        
        # 1. Primary 시도 (재시도 포함)
        for attempt in range(max_retries + 1):
            try:
                result = await self.primary.generate_json(
                    prompt, response_model, system_instruction, temperature
                )
                _inherit_runtime_result(self, self.primary, fallback_used=False, fallback_reason=None)
                return result
            except Exception as e:
                last_exception = e
                logger.warning(f"Primary LLM attempt {attempt + 1} failed: {e}")
                if attempt < max_retries:
                    # 지수 백오프: 1s, 2s, 4s...
                    await asyncio.sleep(2**attempt)
                else:
                    logger.error(f"Primary LLM exhausted all {max_retries + 1} attempts.")

        # 2. Fallback 시도
        if self.fallback:
            logger.warning("Attempting fallback LLM...")
            try:
                result = await self.fallback.generate_json(
                    prompt, response_model, system_instruction, temperature
                )
                _inherit_runtime_result(
                    self,
                    self.fallback,
                    fallback_used=True,
                    fallback_reason=f"primary_failed:{type(last_exception).__name__}" if last_exception else "primary_failed",
                )
                return result
            except Exception as e:
                logger.error(f"Fallback LLM also failed: {e}")
                raise e
        
        if last_exception:
            raise last_exception
        raise RuntimeError("LLM call failed without specific exception")

    async def stream_chat(
        self,
        prompt: str,
        system_instruction: str | None = None,
        temperature: float = 0.5,
        max_retries: int = 1,
    ) -> AsyncIterator[str]:
        # 스트리밍은 구조상 재시도가 복잡하므로 단순 전환만 수행
        try:
            async for chunk in self.primary.stream_chat(prompt, system_instruction, temperature):
                yield chunk
            _inherit_runtime_result(self, self.primary, fallback_used=False, fallback_reason=None)
        except Exception as e:
            logger.error(f"Primary Stream failed: {e}. Attempting fallback...")
            if self.fallback:
                async for chunk in self.fallback.stream_chat(prompt, system_instruction, temperature):
                    yield chunk
                _inherit_runtime_result(
                    self,
                    self.fallback,
                    fallback_used=True,
                    fallback_reason=f"primary_failed:{type(e).__name__}",
                )
            else:
                raise


def get_llm_client(*, profile: LLMProfile = "standard", concern: LLMConcern = "default") -> LLMClient:
    resolution = resolve_llm_runtime(profile=profile, concern=concern)
    if resolution.client is not None:
        return resolution.client
    reason = resolution.fallback_reason or "llm_unconfigured"
    raise RuntimeError(f"No valid LLM client (Gemini or Ollama) could be configured. reason={reason}")


def get_llm_temperature(
    *,
    profile: LLMProfile = "standard",
    concern: LLMConcern = "default",
    resolution: LLMRuntimeResolution | None = None,
) -> float:
    provider = resolution.actual_provider if resolution and resolution.actual_provider else None
    if provider is None:
        provider = _resolve_requested_provider(get_settings(), concern=concern)
    if provider == "ollama":
        return _resolve_ollama_runtime_profile(profile).temperature
    if profile == "fast":
        return 0.25
    if profile == "render":
        return 0.22
    return 0.35


async def probe_ollama_connectivity(*, profile: LLMProfile = "standard") -> tuple[bool, str | None]:
    client, reason = _maybe_build_runtime_ollama_client(profile=profile)
    if client is None:
        return False, reason or "ollama_unavailable"
    return await client.check_connectivity()


def get_pdf_analysis_llm_client() -> LLMClient:
    resolution = resolve_pdf_analysis_llm_resolution()
    if resolution.client is not None:
        return resolution.client
    reason = resolution.fallback_reason or "pdf_analysis_llm_unconfigured"
    raise RuntimeError(f"No valid PDF analysis LLM client could be configured. reason={reason}")


def resolve_pdf_analysis_llm_resolution(*, settings: Any | None = None) -> PDFAnalysisLLMResolution:
    settings = settings or get_settings()
    provider_fallback_enabled = bool(getattr(settings, "llm_provider_fallback_enabled", True))
    attempted_provider = (settings.pdf_analysis_llm_provider or "ollama").strip().lower()
    attempted_model = _resolve_pdf_analysis_requested_model(settings, attempted_provider)
    gemini_client: GeminiClient | None = None
    gemini_reason: str | None = None
    ollama_client: OllamaClient | None = None
    ollama_reason: str | None = None
    if attempted_provider == "gemini" or provider_fallback_enabled:
        gemini_client, gemini_reason = _maybe_build_pdf_analysis_gemini_client(settings=settings)
    if attempted_provider == "ollama" or provider_fallback_enabled:
        ollama_client, ollama_reason = _maybe_build_pdf_analysis_ollama_client(settings=settings)

    actual_provider = "heuristic"
    actual_model = "heuristic-summary-v1"
    fallback_used = False
    fallback_reason: str | None = None
    client: LLMClient | None = None

    if attempted_provider == "ollama":
        if provider_fallback_enabled and ollama_client is not None and gemini_client is not None:
            client = RobustLLMClient(primary=ollama_client, fallback=gemini_client)
            actual_provider = "ollama"
            actual_model = ollama_client.model
        elif ollama_client is not None:
            client = ollama_client
            actual_provider = "ollama"
            actual_model = ollama_client.model
        elif gemini_client is not None:
            client = gemini_client
            actual_provider = "gemini"
            actual_model = gemini_client.model_name
            fallback_used = True
            fallback_reason = ollama_reason or "pdf_analysis_ollama_unavailable_gemini_fallback"
        else:
            fallback_used = True
            fallback_reason = ollama_reason or gemini_reason or "pdf_analysis_llm_unconfigured"
    else:
        if provider_fallback_enabled and gemini_client is not None and ollama_client is not None:
            client = RobustLLMClient(primary=gemini_client, fallback=ollama_client)
            actual_provider = "gemini"
            actual_model = gemini_client.model_name
        elif gemini_client is not None:
            client = gemini_client
            actual_provider = "gemini"
            actual_model = gemini_client.model_name
        elif ollama_client is not None:
            client = ollama_client
            actual_provider = "ollama"
            actual_model = ollama_client.model
            fallback_used = True
            fallback_reason = gemini_reason or "pdf_analysis_gemini_unavailable_ollama_fallback"
        else:
            fallback_used = True
            fallback_reason = gemini_reason or ollama_reason or "pdf_analysis_llm_unconfigured"

    resolution = PDFAnalysisLLMResolution(
        attempted_provider=attempted_provider,
        attempted_model=attempted_model,
        actual_provider=actual_provider,
        actual_model=actual_model,
        client=client,
        fallback_used=fallback_used,
        fallback_reason=fallback_reason,
    )
    _bind_pdf_resolution(resolution, gemini_client=gemini_client, ollama_client=ollama_client)
    _log_llm_event(
        "llm_runtime_resolved",
        concern="pdf_analysis",
        profile="render",
        attempted_provider=resolution.attempted_provider,
        attempted_model=resolution.attempted_model,
        actual_provider=resolution.actual_provider,
        actual_model=resolution.actual_model,
        fallback_used=resolution.fallback_used,
        fallback_reason=resolution.fallback_reason,
        has_client=resolution.client is not None,
    )
    return resolution


def _resolve_pdf_analysis_requested_model(settings: Any, provider: str) -> str:
    if provider == "ollama":
        return (
            str(
                getattr(settings, "pdf_analysis_ollama_model", None)
                or getattr(settings, "ollama_model", None)
                or "gemma4"
            ).strip()
            or "gemma4"
        )
    if provider == "gemini":
        return _resolve_gemini_model_name(settings, concern="pdf_analysis")
    return "unknown"


def resolve_llm_requested_model(
    *,
    profile: LLMProfile = "standard",
    concern: LLMConcern = "default",
    settings: Any | None = None,
) -> str:
    settings = settings or get_settings()
    provider = _resolve_requested_provider(settings, concern=concern)
    if provider == "ollama":
        return _resolve_ollama_runtime_profile(profile, settings=settings).model
    if provider == "gemini":
        return _resolve_gemini_model_name(settings, concern=concern)
    return "unknown"


def _describe_client_provider_model(
    client: LLMClient,
    *,
    requested_provider: str,
    requested_model: str,
) -> tuple[str, str]:
    if isinstance(client, RobustLLMClient):
        # primary 기준으로 설명
        return _describe_client_provider_model(
            client.primary,
            requested_provider=requested_provider,
            requested_model=requested_model,
        )
    if isinstance(client, OllamaClient):
        return "ollama", str(client.model or requested_model).strip() or requested_model
    if isinstance(client, GeminiClient):
        model = str(getattr(client, "model_name", "") or "").strip()
        return "gemini", model or requested_model
    return requested_provider, requested_model


def resolve_llm_runtime(
    *,
    profile: LLMProfile = "standard",
    concern: LLMConcern = "default",
    settings: Any | None = None,
) -> LLMRuntimeResolution:
    settings = settings or get_settings()
    provider_fallback_enabled = bool(getattr(settings, "llm_provider_fallback_enabled", True))
    requested_provider = _resolve_requested_provider(settings, concern=concern)
    attempted_model = resolve_llm_requested_model(profile=profile, concern=concern, settings=settings)
    gemini_client: GeminiClient | None = None
    gemini_reason: str | None = None
    ollama_client: OllamaClient | None = None
    ollama_reason: str | None = None
    if requested_provider == "gemini" or provider_fallback_enabled:
        gemini_client, gemini_reason = _maybe_build_gemini_client(concern=concern, settings=settings)
    if requested_provider == "ollama" or provider_fallback_enabled:
        ollama_client, ollama_reason = _maybe_build_runtime_ollama_client(profile=profile, settings=settings)

    actual_provider: str | None = None
    actual_model: str | None = None
    fallback_used = False
    fallback_reason: str | None = None
    client: LLMClient | None = None

    if requested_provider == "ollama":
        if ollama_client is not None:
            client = ollama_client
            actual_provider = "ollama"
            actual_model = ollama_client.model
        elif provider_fallback_enabled and gemini_client is not None:
            client = gemini_client
            actual_provider = "gemini"
            actual_model = gemini_client.model_name
            fallback_used = True
            fallback_reason = ollama_reason or "ollama_unavailable_gemini_fallback"
        else:
            fallback_used = True
            fallback_reason = ollama_reason or gemini_reason or "llm_unconfigured"
    else:
        if provider_fallback_enabled and gemini_client is not None and ollama_client is not None:
            client = RobustLLMClient(primary=gemini_client, fallback=ollama_client)
            actual_provider = "gemini"
            actual_model = gemini_client.model_name
        elif gemini_client is not None:
            client = gemini_client
            actual_provider = "gemini"
            actual_model = gemini_client.model_name
        elif provider_fallback_enabled and ollama_client is not None:
            client = ollama_client
            actual_provider = "ollama"
            actual_model = ollama_client.model
            fallback_used = True
            fallback_reason = gemini_reason or "gemini_unavailable_ollama_fallback"
        else:
            fallback_used = True
            fallback_reason = gemini_reason or ollama_reason or "llm_unconfigured"

    resolution = LLMRuntimeResolution(
        concern=concern,
        profile=profile,
        attempted_provider=requested_provider,
        attempted_model=attempted_model,
        actual_provider=actual_provider,
        actual_model=actual_model,
        fallback_used=fallback_used,
        fallback_reason=fallback_reason,
        client=client,
    )
    _bind_runtime_resolution(resolution, gemini_client=gemini_client, ollama_client=ollama_client)
    _log_runtime_resolution(resolution)
    return resolution


def _initialize_runtime_state(client: object) -> None:
    setattr(client, "_runtime_selection", {})
    setattr(client, "last_provider_used", None)
    setattr(client, "last_model_used", None)
    setattr(client, "last_latency_ms", None)
    setattr(client, "last_failure_category", None)
    setattr(client, "last_fallback_used", False)
    setattr(client, "last_fallback_reason", None)


def _inherit_runtime_result(
    parent: object,
    source: object,
    *,
    fallback_used: bool,
    fallback_reason: str | None,
) -> None:
    selection = getattr(source, "_runtime_selection", {})
    setattr(parent, "_runtime_selection", selection)
    if isinstance(source, GeminiClient):
        provider = "gemini"
        model = source.model_name
    elif isinstance(source, OllamaClient):
        provider = "ollama"
        model = source.model
    else:
        provider = getattr(source, "last_provider_used", None)
        model = getattr(source, "last_model_used", None)
    setattr(parent, "last_provider_used", provider)
    setattr(parent, "last_model_used", model)
    setattr(parent, "last_latency_ms", getattr(source, "last_latency_ms", None))
    setattr(parent, "last_failure_category", getattr(source, "last_failure_category", None))
    setattr(parent, "last_fallback_used", fallback_used)
    setattr(parent, "last_fallback_reason", fallback_reason)


def _record_runtime_success(
    client: object,
    *,
    provider: str,
    model: str,
    operation: str,
    started_at: float,
) -> None:
    latency_ms = int(max(0.0, (time.perf_counter() - started_at) * 1000.0))
    setattr(client, "last_provider_used", provider)
    setattr(client, "last_model_used", model)
    setattr(client, "last_latency_ms", latency_ms)
    setattr(client, "last_failure_category", None)
    _log_llm_event(
        "llm_request_succeeded",
        operation=operation,
        **_runtime_log_payload(client),
    )


def _record_runtime_failure(
    client: object,
    *,
    provider: str,
    model: str,
    operation: str,
    started_at: float,
    exc: Exception,
) -> None:
    latency_ms = int(max(0.0, (time.perf_counter() - started_at) * 1000.0))
    setattr(client, "last_provider_used", provider)
    setattr(client, "last_model_used", model)
    setattr(client, "last_latency_ms", latency_ms)
    setattr(client, "last_failure_category", _classify_runtime_failure(exc))
    if isinstance(exc, LLMRequestError):
        setattr(client, "last_fallback_reason", exc.limited_reason)
    _log_llm_event(
        "llm_request_failed",
        operation=operation,
        detail=repr(exc),
        **_runtime_log_payload(client),
    )


def _runtime_log_payload(client: object) -> dict[str, Any]:
    selection = getattr(client, "_runtime_selection", {}) or {}
    last_provider = getattr(client, "last_provider_used", None)
    last_model = getattr(client, "last_model_used", None)
    return {
        **selection,
        "last_provider_used": last_provider,
        "last_model_used": last_model,
        # Backward-compatible aliases for older call sites and persisted debug payloads.
        "provider": last_provider,
        "model": last_model,
        "latency_ms": getattr(client, "last_latency_ms", None),
        "failure_category": getattr(client, "last_failure_category", None),
        "fallback_used": getattr(client, "last_fallback_used", None),
        "fallback_reason": getattr(client, "last_fallback_reason", None),
    }


def get_last_llm_invocation(client: object | None) -> dict[str, Any]:
    if client is None:
        return {}
    return _runtime_log_payload(client)


def _log_llm_event(event: str, **payload: Any) -> None:
    compact_payload = ", ".join(
        f"{key}={value}"
        for key, value in payload.items()
        if value is not None
    )
    logger.info("%s | %s", event, compact_payload)


def _log_runtime_resolution(resolution: LLMRuntimeResolution) -> None:
    _log_llm_event(
        "llm_runtime_resolved",
        concern=resolution.concern,
        profile=resolution.profile,
        attempted_provider=resolution.attempted_provider,
        attempted_model=resolution.attempted_model,
        actual_provider=resolution.actual_provider,
        actual_model=resolution.actual_model,
        fallback_used=resolution.fallback_used,
        fallback_reason=resolution.fallback_reason,
        has_client=resolution.client is not None,
    )


def _bind_runtime_resolution(
    resolution: LLMRuntimeResolution,
    *,
    gemini_client: GeminiClient | None,
    ollama_client: OllamaClient | None,
) -> None:
    if gemini_client is not None:
        _set_runtime_selection(
            gemini_client,
            concern=resolution.concern,
            profile=resolution.profile,
            attempted_provider=resolution.attempted_provider,
            attempted_model=resolution.attempted_model,
            actual_provider="gemini",
            actual_model=gemini_client.model_name,
        )
    if ollama_client is not None:
        _set_runtime_selection(
            ollama_client,
            concern=resolution.concern,
            profile=resolution.profile,
            attempted_provider=resolution.attempted_provider,
            attempted_model=resolution.attempted_model,
            actual_provider="ollama",
            actual_model=ollama_client.model,
        )
    if resolution.client is not None:
        _set_runtime_selection(
            resolution.client,
            concern=resolution.concern,
            profile=resolution.profile,
            attempted_provider=resolution.attempted_provider,
            attempted_model=resolution.attempted_model,
            actual_provider=resolution.actual_provider,
            actual_model=resolution.actual_model,
        )


def _bind_pdf_resolution(
    resolution: PDFAnalysisLLMResolution,
    *,
    gemini_client: GeminiClient | None,
    ollama_client: OllamaClient | None,
) -> None:
    if gemini_client is not None:
        _set_runtime_selection(
            gemini_client,
            concern="pdf_analysis",
            profile="render",
            attempted_provider=resolution.attempted_provider,
            attempted_model=resolution.attempted_model,
            actual_provider="gemini",
            actual_model=gemini_client.model_name,
        )
    if ollama_client is not None:
        _set_runtime_selection(
            ollama_client,
            concern="pdf_analysis",
            profile="render",
            attempted_provider=resolution.attempted_provider,
            attempted_model=resolution.attempted_model,
            actual_provider="ollama",
            actual_model=ollama_client.model,
        )
    if resolution.client is not None:
        _set_runtime_selection(
            resolution.client,
            concern="pdf_analysis",
            profile="render",
            attempted_provider=resolution.attempted_provider,
            attempted_model=resolution.attempted_model,
            actual_provider=resolution.actual_provider,
            actual_model=resolution.actual_model,
        )


def _set_runtime_selection(
    client: object,
    *,
    concern: str,
    profile: str,
    attempted_provider: str,
    attempted_model: str,
    actual_provider: str | None,
    actual_model: str | None,
) -> None:
    setattr(
        client,
        "_runtime_selection",
        {
            "concern": concern,
            "profile": profile,
            "attempted_provider": attempted_provider,
            "attempted_model": attempted_model,
            "actual_provider": actual_provider,
            "actual_model": actual_model,
        },
    )


def _classify_runtime_failure(exc: Exception) -> str:
    if isinstance(exc, LLMRequestError):
        return str(exc.limited_reason or "provider_error").strip().lower() or "provider_error"
    if isinstance(exc, (APITimeoutError, TimeoutError, asyncio.TimeoutError)):
        return "timeout"
    if isinstance(exc, APIConnectionError):
        return "unreachable"
    if isinstance(exc, NotFoundError):
        return "not_found"
    if isinstance(exc, BadRequestError):
        return "invalid_request"
    if isinstance(exc, APIError):
        return "provider_error"
    name = type(exc).__name__.strip().lower()
    if "timeout" in name:
        return "timeout"
    if "connection" in name or "network" in name or "socket" in name:
        return "unreachable"
    if "json" in name or "decode" in name or "validation" in name:
        return "invalid_response"
    return "provider_error"


def _resolve_requested_provider(settings: Any, *, concern: LLMConcern) -> str:
    if concern == "guided_chat":
        value = getattr(settings, "guided_chat_llm_provider", None) or getattr(settings, "llm_provider", "gemini")
    elif concern == "diagnosis":
        value = getattr(settings, "diagnosis_llm_provider", None) or getattr(settings, "llm_provider", "gemini")
    elif concern == "render":
        value = getattr(settings, "render_llm_provider", None) or getattr(settings, "llm_provider", "gemini")
    elif concern == "pdf_analysis":
        value = getattr(settings, "pdf_analysis_llm_provider", None) or "ollama"
    else:
        value = getattr(settings, "llm_provider", "gemini")
    normalized = str(value or "").strip().lower()
    return normalized or "gemini"


def _resolve_gemini_model_name(settings: Any, *, concern: LLMConcern) -> str:
    if concern == "pdf_analysis":
        value = getattr(settings, "pdf_analysis_gemini_model", None) or getattr(settings, "gemini_model", None)
    else:
        value = getattr(settings, "gemini_model", None)
    normalized = str(value or "").strip()
    return normalized or DEFAULT_GEMINI_MODEL


def _resolve_gemini_api_key(
    settings: Any,
    *,
    include_pdf_override: bool = False,
) -> str:
    candidates: list[str | None] = []
    if include_pdf_override:
        candidates.append(getattr(settings, "pdf_analysis_gemini_api_key", None))
    candidates.extend(
        [
            getattr(settings, "gemini_api_key", None),
            os.environ.get("PDF_ANALYSIS_GEMINI_API_KEY") if include_pdf_override else None,
            os.environ.get("GEMINI_API_KEY"),
            os.environ.get("GOOGLE_API_KEY"),
            os.environ.get("GENAI_API_KEY"),
            os.environ.get("GEMINI_KEY"),
        ]
    )
    for value in candidates:
        normalized = str(value or "").strip()
        if normalized:
            return normalized
    return ""


def _maybe_build_gemini_client(
    *,
    concern: LLMConcern,
    settings: Any | None = None,
) -> tuple[GeminiClient | None, str | None]:
    settings = settings or get_settings()
    api_key = _resolve_gemini_api_key(settings)
    if not api_key or api_key == "DUMMY_KEY":
        return None, "gemini_api_key_missing"
    try:
        return GeminiClient(api_key=api_key, model_name=_resolve_gemini_model_name(settings, concern=concern)), None
    except Exception as exc:  # noqa: BLE001
        logger.warning("Gemini client initialization failed for concern=%s: %s", concern, exc)
        return None, f"gemini_init_failed:{type(exc).__name__}"


def _maybe_build_runtime_ollama_client(
    *,
    profile: LLMProfile,
    settings: Any | None = None,
) -> tuple[OllamaClient | None, str | None]:
    settings = settings or get_settings()
    base_url = str(getattr(settings, "ollama_base_url", "") or "").strip()
    if not _is_valid_http_url(base_url):
        return None, "ollama_endpoint_invalid"
    if _ollama_localhost_blocked(getattr(settings, "app_env", "production"), base_url):
        return None, "ollama_localhost_blocked_in_deployed_runtime"
    try:
        return _build_ollama_client(profile=profile, base_url=base_url, settings=settings), None
    except Exception as exc:  # noqa: BLE001
        logger.warning("Ollama client initialization failed: %s", exc)
        return None, f"ollama_init_failed:{type(exc).__name__}"


def _maybe_build_pdf_analysis_gemini_client(
    *,
    settings: Any | None = None,
) -> tuple[GeminiClient | None, str | None]:
    settings = settings or get_settings()
    api_key = _resolve_gemini_api_key(settings, include_pdf_override=True)
    if not api_key or api_key == "DUMMY_KEY":
        return None, "gemini_api_key_missing"
    try:
        return GeminiClient(api_key=api_key, model_name=_resolve_gemini_model_name(settings, concern="pdf_analysis")), None
    except Exception as exc:  # noqa: BLE001
        logger.warning("PDF Gemini client initialization failed: %s", exc)
        return None, f"gemini_init_failed:{type(exc).__name__}"


def _maybe_build_pdf_analysis_ollama_client(
    *,
    settings: Any | None = None,
) -> tuple[OllamaClient | None, str | None]:
    settings = settings or get_settings()
    base_url = str(
        getattr(settings, "pdf_analysis_ollama_base_url", None)
        or getattr(settings, "ollama_base_url", "")
        or ""
    ).strip()
    if not _is_valid_http_url(base_url):
        return None, "ollama_endpoint_invalid"
    if _ollama_localhost_blocked(getattr(settings, "app_env", "production"), base_url):
        return None, "ollama_localhost_blocked_in_deployed_runtime"
    try:
        return (
            _build_ollama_client(
                profile="render",
                base_url=base_url,
                model=getattr(settings, "pdf_analysis_ollama_model", None) or getattr(settings, "ollama_model", None),
                request_timeout_seconds=getattr(settings, "pdf_analysis_timeout_seconds", 60.0),
                keep_alive=getattr(settings, "pdf_analysis_keep_alive", "15m"),
                num_ctx=getattr(settings, "pdf_analysis_num_ctx", 3072),
                num_predict=getattr(settings, "pdf_analysis_num_predict", 512),
                num_thread=getattr(settings, "pdf_analysis_num_thread", None),
                settings=settings,
            ),
            None,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("PDF Ollama client initialization failed: %s", exc)
        return None, f"ollama_init_failed:{type(exc).__name__}"


def _resolve_ollama_runtime_profile(
    profile: LLMProfile,
    *,
    settings: Any | None = None,
) -> OllamaRuntimeProfile:
    settings = settings or get_settings()

    base_timeout = float(getattr(settings, "ollama_timeout_seconds", 90.0))
    base_model = str(getattr(settings, "ollama_model", "gemma4") or "gemma4")
    base_num_ctx = int(getattr(settings, "ollama_num_ctx", 2048) or 2048)
    base_num_predict = int(getattr(settings, "ollama_num_predict", 512) or 512)
    if profile == "fast":
        timeout = float(getattr(settings, "ollama_fast_timeout_seconds", None) or min(base_timeout, 45.0))
        num_ctx = max(512, min(base_num_ctx, 1536))
        num_predict = max(96, min(base_num_predict, 240))
        model = str(getattr(settings, "ollama_fast_model", None) or base_model).strip()
        temperature = 0.22
    elif profile == "render":
        timeout = float(getattr(settings, "ollama_render_timeout_seconds", None) or max(base_timeout, 120.0))
        num_ctx = max(base_num_ctx, 4096)
        num_predict = max(base_num_predict, 900)
        model = str(getattr(settings, "ollama_render_model", None) or base_model).strip()
        temperature = 0.24
    else:
        timeout = float(getattr(settings, "ollama_standard_timeout_seconds", None) or base_timeout)
        num_ctx = max(1024, base_num_ctx)
        num_predict = max(256, base_num_predict)
        model = str(getattr(settings, "ollama_standard_model", None) or base_model).strip()
        temperature = 0.32

    return OllamaRuntimeProfile(
        name=profile,
        model=model or base_model,
        request_timeout_seconds=timeout,
        keep_alive=getattr(settings, "ollama_keep_alive", "30m"),
        num_ctx=num_ctx,
        num_predict=num_predict,
        num_thread=getattr(settings, "ollama_num_thread", None),
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
    settings: Any | None = None,
) -> OllamaClient:
    settings = settings or get_settings()
    runtime = _resolve_ollama_runtime_profile(profile, settings=settings)
    return OllamaClient(
        base_url=(base_url or getattr(settings, "ollama_base_url", "")).strip(),
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
    if isinstance(exc, NotFoundError):
        if _extract_missing_model_from_exception(exc):
            return "model_not_found"
        return "provider_error"
    if isinstance(exc, BadRequestError):
        if _extract_missing_model_from_exception(exc):
            return "model_not_found"
        return "invalid_request"
    if isinstance(exc, APIError):
        if _extract_missing_model_from_exception(exc):
            return "model_not_found"
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


def _ollama_localhost_blocked(app_env: str | None, base_url: str | None) -> bool:
    normalized_env = str(app_env or "").strip().lower()
    if normalized_env == "local":
        return False
    if not base_url:
        return False
    parsed = urlparse(base_url)
    host = (parsed.hostname or "").strip().lower()
    return host in {"localhost", "127.0.0.1", "::1", "0.0.0.0"}


def _is_valid_http_url(value: str | None) -> bool:
    if not value:
        return False
    parsed = urlparse(value)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


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
        message = "AI 응답이 지연되어 안전 모드로 전환합니다."
    elif reason == "model_not_found":
        message = "요청한 AI 모델을 찾지 못해 안전 모드로 전환합니다."
    elif reason == "invalid_request":
        message = "AI 요청 구성이 올바르지 않아 안전 모드로 전환합니다."
    else:
        message = "AI 처리 중 오류가 발생해 안전 모드로 전환합니다."

    return LLMRequestError(
        message,
        limited_reason=f"ollama_{reason}",
        provider="ollama",
        profile=profile,
    )


def _ollama_alias_cache_key(base_url: str, model: str) -> str:
    return f"{(base_url or '').strip().lower()}::{(model or '').strip().lower()}"


def _resolve_cached_ollama_model_alias(base_url: str, requested_model: str) -> str | None:
    if not requested_model:
        return None
    return _ollama_model_alias_cache.get(_ollama_alias_cache_key(base_url, requested_model))


def _remember_ollama_model_alias(base_url: str, requested_model: str, fallback_model: str) -> None:
    normalized_requested = str(requested_model or "").strip()
    normalized_fallback = str(fallback_model or "").strip()
    if not normalized_requested or not normalized_fallback:
        return
    _ollama_model_alias_cache[_ollama_alias_cache_key(base_url, normalized_requested)] = normalized_fallback


def _extract_missing_model_from_exception(exc: Exception) -> str | None:
    message = str(exc or "")
    match = re.search(r"model ['\"]([^'\"]+)['\"] not found", message, flags=re.IGNORECASE)
    if not match:
        return None
    missing_model = str(match.group(1) or "").strip()
    return missing_model or None


def _split_ollama_model_name(value: str) -> tuple[str, str | None]:
    normalized = str(value or "").strip()
    if not normalized:
        return "", None
    if ":" not in normalized:
        return normalized.lower(), None
    base, tag = normalized.rsplit(":", 1)
    return base.lower(), tag.lower()


def _parse_ollama_size_tag(tag: str | None) -> float | None:
    if not tag:
        return None
    match = re.match(r"(\d+(?:\.\d+)?)b$", tag.strip().lower())
    if not match:
        return None
    try:
        return float(match.group(1))
    except ValueError:
        return None


def _select_ollama_fallback_model(requested_model: str, available_models: list[str]) -> str | None:
    normalized_requested = str(requested_model or "").strip()
    if not normalized_requested:
        return None

    deduped: list[str] = []
    seen: set[str] = set()
    for raw in available_models:
        candidate = str(raw or "").strip()
        if not candidate:
            continue
        key = candidate.lower()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(candidate)

    if not deduped:
        return None

    for candidate in deduped:
        if candidate.lower() == normalized_requested.lower():
            return candidate

    requested_base, requested_tag = _split_ollama_model_name(normalized_requested)
    family_candidates = [
        candidate
        for candidate in deduped
        if _split_ollama_model_name(candidate)[0] == requested_base and requested_base
    ]
    if family_candidates:
        latest = [
            candidate
            for candidate in family_candidates
            if (_split_ollama_model_name(candidate)[1] or "") == "latest"
        ]
        if latest:
            return sorted(latest, key=lambda item: item.lower())[0]

        requested_size = _parse_ollama_size_tag(requested_tag)
        if requested_size is not None:
            sized_candidates: list[tuple[str, float]] = []
            for candidate in family_candidates:
                _, candidate_tag = _split_ollama_model_name(candidate)
                candidate_size = _parse_ollama_size_tag(candidate_tag)
                if candidate_size is not None:
                    sized_candidates.append((candidate, candidate_size))
            if sized_candidates:
                sized_candidates.sort(key=lambda item: item[1])
                for candidate, candidate_size in sized_candidates:
                    if candidate_size >= requested_size:
                        return candidate
                return sized_candidates[-1][0]

        return sorted(family_candidates, key=lambda item: item.lower())[0]

    latest_any = [candidate for candidate in deduped if candidate.lower().endswith(":latest")]
    if latest_any:
        return sorted(latest_any, key=lambda item: item.lower())[0]
    return sorted(deduped, key=lambda item: item.lower())[0]
