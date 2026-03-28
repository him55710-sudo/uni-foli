from __future__ import annotations

import abc
import json
import os
from typing import Any, Type, TypeVar

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
            token = getattr(chunk, "text", None)
            if token:
                yield token


class OllamaClient(LLMClient):
    def __init__(self, base_url: str, model: str):
        self.client = AsyncOpenAI(
            base_url=base_url,
            api_key="ollama",  # Required but not used for local Ollama
        )
        self.model = model

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
        )
        async for chunk in response:
            if chunk.choices and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content


def get_llm_client() -> LLMClient:
    settings = get_settings()
    if settings.llm_provider == "ollama":
        return OllamaClient(
            base_url=settings.ollama_base_url,
            model=settings.ollama_model,
        )
    # Default to Gemini
    api_key = settings.gemini_api_key or os.environ.get("GEMINI_API_KEY", "DUMMY_KEY")
    return GeminiClient(api_key=api_key)
