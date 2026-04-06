from __future__ import annotations

from polio_api.core.config import Settings
from polio_api.core.llm import OllamaClient, get_pdf_analysis_llm_client
from polio_api.services.pdf_analysis_service import build_pdf_analysis_metadata
from polio_ingest.models import ParsedChunkPayload, ParsedDocumentPayload


class _FakePdfLLM:
    async def generate_json(self, prompt, response_model, system_instruction=None, temperature=0.2):  # noqa: ANN001
        return response_model(
            summary="문서의 핵심 흐름이 페이지별로 비교적 명확하게 확인됩니다.",
            key_points=["활동 동기", "과정 기록", "결과와 성찰"],
            page_insights=[
                {"page_number": 1, "summary": "1페이지에는 활동 배경과 목표가 정리되어 있습니다."},
                {"page_number": 2, "summary": "2페이지에는 수행 과정과 결과가 이어집니다."},
            ],
            evidence_gaps=["일부 수치 근거는 원문 재확인이 필요합니다."],
        )


class _TextFallbackPdfLLM:
    async def generate_json(self, prompt, response_model, system_instruction=None, temperature=0.2):  # noqa: ANN001
        raise RuntimeError("json schema response unsupported")

    async def stream_chat(self, prompt, system_instruction=None, temperature=0.5):  # noqa: ANN001
        yield (
            "## PDF 페이지별 핵심 요약\n"
            "전체 요약: 문서 흐름을 페이지별로 검토했습니다.\n"
            "1페이지: 활동 배경과 목표가 정리되어 있습니다.\n"
            "2페이지: 수행 과정과 결과가 이어집니다.\n"
            "근거 부족: 일부 수치는 원문 재확인이 필요합니다.\n"
        )


class _FailingPdfLLM:
    async def generate_json(self, prompt, response_model, system_instruction=None, temperature=0.2):  # noqa: ANN001
        raise RuntimeError("forced llm failure")

    async def stream_chat(self, prompt, system_instruction=None, temperature=0.5):  # noqa: ANN001
        if False:
            yield ""
        raise RuntimeError("forced stream failure")


def _build_sample_payload() -> ParsedDocumentPayload:
    return ParsedDocumentPayload(
        parser_name="pymupdf",
        source_extension=".pdf",
        page_count=2,
        word_count=120,
        content_text="1페이지 활동 배경과 목표. 2페이지 수행 과정과 결과.",
        content_markdown="## Page 1\n활동 배경과 목표\n\n## Page 2\n수행 과정과 결과",
        metadata={},
        chunks=[
            ParsedChunkPayload(
                chunk_index=0,
                page_number=1,
                char_start=0,
                char_end=30,
                token_estimate=8,
                content_text="활동 배경과 목표",
            )
        ],
        masked_artifact={
            "pages": [
                {"page_number": 1, "masked_text": "활동 배경과 목표가 상세히 기록되어 있습니다."},
                {"page_number": 2, "masked_text": "수행 과정과 결과, 다음 계획이 포함되어 있습니다."},
            ]
        },
    )


def test_pdf_analysis_uses_dedicated_model(monkeypatch) -> None:
    settings = Settings(
        pdf_analysis_llm_enabled=True,
        pdf_analysis_llm_provider="ollama",
        pdf_analysis_ollama_model="gemma4-pdf",
        pdf_analysis_ollama_base_url="http://localhost:11434/v1",
    )
    monkeypatch.setattr("polio_api.services.pdf_analysis_service.get_settings", lambda: settings)
    monkeypatch.setattr("polio_api.services.pdf_analysis_service.get_pdf_analysis_llm_client", lambda: _FakePdfLLM())

    metadata = build_pdf_analysis_metadata(_build_sample_payload())

    assert metadata is not None
    assert metadata["engine"] == "llm"
    assert metadata["model"] == "gemma4-pdf"
    assert metadata["summary"]
    assert len(metadata["page_insights"]) >= 1


def test_pdf_analysis_falls_back_without_crashing(monkeypatch) -> None:
    settings = Settings(
        pdf_analysis_llm_enabled=True,
        pdf_analysis_llm_provider="ollama",
        pdf_analysis_ollama_model="gemma4-pdf",
    )
    monkeypatch.setattr("polio_api.services.pdf_analysis_service.get_settings", lambda: settings)
    monkeypatch.setattr("polio_api.services.pdf_analysis_service.get_pdf_analysis_llm_client", lambda: _FailingPdfLLM())

    metadata = build_pdf_analysis_metadata(_build_sample_payload())

    assert metadata is not None
    assert metadata["engine"] == "fallback"
    assert metadata["summary"]
    assert len(metadata["page_insights"]) >= 1


def test_pdf_analysis_recovers_from_text_only_llm(monkeypatch) -> None:
    settings = Settings(
        pdf_analysis_llm_enabled=True,
        pdf_analysis_llm_provider="ollama",
        pdf_analysis_ollama_model="gemma4-pdf",
    )
    monkeypatch.setattr("polio_api.services.pdf_analysis_service.get_settings", lambda: settings)
    monkeypatch.setattr("polio_api.services.pdf_analysis_service.get_pdf_analysis_llm_client", lambda: _TextFallbackPdfLLM())

    metadata = build_pdf_analysis_metadata(_build_sample_payload())

    assert metadata is not None
    assert metadata["engine"] == "llm"
    assert metadata["summary"]
    assert len(metadata["page_insights"]) >= 1
    assert metadata["page_insights"][0]["page_number"] == 1


def test_get_pdf_analysis_llm_client_uses_split_config(monkeypatch) -> None:
    settings = Settings(
        pdf_analysis_llm_enabled=True,
        pdf_analysis_llm_provider="ollama",
        pdf_analysis_ollama_model="gemma4-pdf",
        pdf_analysis_ollama_base_url="http://localhost:11434/v1",
        pdf_analysis_timeout_seconds=33,
        pdf_analysis_keep_alive="10m",
        pdf_analysis_num_ctx=1111,
        pdf_analysis_num_predict=222,
        pdf_analysis_num_thread=3,
    )
    monkeypatch.setattr("polio_api.core.llm.get_settings", lambda: settings)

    client = get_pdf_analysis_llm_client()

    assert isinstance(client, OllamaClient)
    assert client.model == "gemma4-pdf"
    assert client.options["num_ctx"] == 1111
    assert client.options["num_predict"] == 222
    assert client.options["num_thread"] == 3
