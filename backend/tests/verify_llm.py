import asyncio
import os
from unittest.mock import MagicMock, patch

from pydantic import BaseModel
from polio_api.core.llm import get_llm_client, GeminiClient, OllamaClient
from polio_api.core.config import Settings

class MockResult(BaseModel):
    status: str
    message: str

async def test_llm_switching():
    # Test 1: Default (Gemini)
    with patch("polio_api.core.llm.get_settings") as mock_settings:
        mock_settings.return_value = Settings(llm_provider="gemini", gemini_api_key="test-key")
        client = get_llm_client()
        print(f"Provider: {type(client).__name__}")
        assert isinstance(client, GeminiClient)

    # Test 2: Ollama Switching
    with patch("polio_api.core.llm.get_settings") as mock_settings:
        mock_settings.return_value = Settings(llm_provider="ollama", ollama_model="qwen2.5")
        client = get_llm_client()
        print(f"Provider: {type(client).__name__}")
        assert isinstance(client, OllamaClient)
        assert client.model == "qwen2.5"

    print("✅ LLM switching logic verified!")

if __name__ == "__main__":
    asyncio.run(test_llm_switching())
