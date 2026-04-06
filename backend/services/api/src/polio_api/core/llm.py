from __future__ import annotations

import abc
import json
import os
from typing import Any, AsyncIterator, Type, TypeVar

import google.generativeai as genai
from openai import AsyncOpenAI
from pydantic import BaseModel

from polio_api.core.config import get_settings

T = TypeVar("T", bound=BaseModel)


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
        genai.configure(api_key=api_key)

    async def generate_json(
        self,
        prompt: str,
        response_model: Type[T],
        system_instruction: str | None = None,
        temperature: float = 0.2,
    ) -> T:
        model = genai.GenerativeModel(
            model_name="gemini-1.5-pro",
            system_instruction=system_instruction,
        )
        response = await model.generate_content_async(
            prompt,
            generation_config=genai.GenerationConfig(
                response_mime_type="application/json",
                response_schema=response_model,
                temperature=temperature,
            ),
        )
        return response_model.model_validate_json(response.text)
    async def stream_chat(
        self,
        prompt: str,
        system_instruction: str | None = None,
        temperature: float = 0.5,
    ) -> AsyncIterator[str]:
        model = genai.GenerativeModel(
            model_name="gemini-1.5-pro",
            system_instruction=system_instruction,
        )
        response_stream = await model.generate_content_async(
            prompt,
            stream=True,
            generation_config=genai.GenerationConfig(
                temperature=temperature,
            ),
        )
        async for chunk in response_stream:
            try:
                if chunk.text:
                    yield chunk.text
            except (ValueError, AttributeError):
                # Handle cases where chunk.text is blocked by safety filters or not available
                continue


class OllamaClient(LLMClient):
    def __init__(
        self,
        base_url: str,
        model: str,
        *,
        request_timeout_seconds: float = 90.0,
        keep_alive: str | None = "30m",
        num_ctx: int | None = 2048,
        num_predict: int | None = 512,
        num_thread: int | None = None,
    ):
        self.client = AsyncOpenAI(
            base_url=base_url,
            api_key="ollama",  # Required but not used for local Ollama
            timeout=request_timeout_seconds,
            max_retries=1,
        )
        self.model = model
        self.keep_alive = keep_alive
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

    async def generate_json(
        self,
        prompt: str,
        response_model: Type[T],
        system_instruction: str | None = None,
        temperature: float = 0.2,
    ) -> T:
        messages = []
        if system_instruction:
            messages.append({"role": "system", "content": system_instruction})
        messages.append({"role": "user", "content": f"{prompt}\n\nPlease respond in JSON format strictly following this schema:\n{json.dumps(response_model.model_json_schema(), ensure_ascii=False)}"})

        response = await self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=temperature,
            response_format={"type": "json_object"},
            extra_body=self._extra_body(),
        )
        
        content = response.choices[0].message.content
        if not content:
            raise ValueError("Empty response from Ollama")
            
        return response_model.model_validate_json(content)
    async def stream_chat(
        self,
        prompt: str,
        system_instruction: str | None = None,
        temperature: float = 0.5,
    ) -> AsyncIterator[str]:
        messages = []
        if system_instruction:
            messages.append({"role": "system", "content": system_instruction})
        messages.append({"role": "user", "content": prompt})

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


def get_llm_client() -> LLMClient:
    settings = get_settings()
    provider = (settings.llm_provider or "gemini").strip().lower()
    api_key = (settings.gemini_api_key or os.environ.get("GEMINI_API_KEY") or "").strip()
    has_valid_gemini_key = bool(api_key) and api_key != "DUMMY_KEY"

    if provider == "ollama":
        return _build_ollama_client()

    if provider not in {"gemini", "ollama"}:
        if settings.app_env == "local" and not has_valid_gemini_key:
            return _build_ollama_client()
        raise RuntimeError(f"Unsupported LLM provider: {settings.llm_provider}")

    if has_valid_gemini_key:
        return GeminiClient(api_key=api_key)

    if settings.app_env == "local":
        return _build_ollama_client()

    raise RuntimeError("Gemini API key is not configured.")


def get_pdf_analysis_llm_client() -> LLMClient:
    settings = get_settings()
    provider = (settings.pdf_analysis_llm_provider or "ollama").strip().lower()
    gemini_api_key = (
        settings.pdf_analysis_gemini_api_key or settings.gemini_api_key or os.environ.get("GEMINI_API_KEY") or ""
    ).strip()

    if provider == "ollama":
        return _build_ollama_client(
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


def _build_ollama_client(
    *,
    base_url: str | None = None,
    model: str | None = None,
    request_timeout_seconds: float | None = None,
    keep_alive: str | None = None,
    num_ctx: int | None = None,
    num_predict: int | None = None,
    num_thread: int | None = None,
) -> OllamaClient:
    settings = get_settings()
    return OllamaClient(
        base_url=base_url or settings.ollama_base_url,
        model=model or settings.ollama_model,
        request_timeout_seconds=request_timeout_seconds if request_timeout_seconds is not None else settings.ollama_timeout_seconds,
        keep_alive=settings.ollama_keep_alive if keep_alive is None else keep_alive,
        num_ctx=settings.ollama_num_ctx if num_ctx is None else num_ctx,
        num_predict=settings.ollama_num_predict if num_predict is None else num_predict,
        num_thread=settings.ollama_num_thread if num_thread is None else num_thread,
    )
