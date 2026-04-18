from __future__ import annotations

import asyncio
import json

from unifoli_api.core.config import Settings
from unifoli_api.core.llm import LLMRequestError, OllamaClient, PDFAnalysisLLMResolution, get_pdf_analysis_llm_client
from unifoli_api.services.pdf_analysis_service import build_pdf_analysis_metadata
from unifoli_ingest.models import ParsedChunkPayload, ParsedDocumentPayload


class _DeterministicPdfLLM:
    def __init__(self, *, fail_mode: str | None = None):
        self.fail_mode = fail_mode
        self.invalid_json_triggered = False
        self.calls: list[dict[str, object]] = []
        self.stage_a_calls = 0
        self.stage_b_calls = 0

    async def generate_json(self, prompt, response_model, system_instruction=None, temperature=0.2):  # noqa: ANN001
        model_fields = getattr(response_model, "model_fields", {})
        is_stage_a = "batch_summary" in model_fields
        stage = "stage_a" if is_stage_a else "stage_b"
        self.calls.append({"stage": stage, "prompt": prompt, "temperature": float(temperature)})

        if is_stage_a:
            self.stage_a_calls += 1
        else:
            self.stage_b_calls += 1

        if self.fail_mode == "timeout":
            raise TimeoutError("forced timeout")
        if self.fail_mode == "error":
            raise RuntimeError("forced failure")
        if self.fail_mode == "invalid_json_once" and not self.invalid_json_triggered:
            self.invalid_json_triggered = True
            raise LLMRequestError(
                "invalid json",
                limited_reason="invalid_json",
                provider="ollama",
                profile="render",
            )

        payload = _extract_json_payload(prompt)
        if is_stage_a:
            pages = payload.get("pages") if isinstance(payload, dict) else None
            page_payloads = pages if isinstance(pages, list) else []
            if not page_payloads:
                page_payloads = [{"page_number": 1, "masked_text": "masked fallback"}]

            page_insights = []
            key_points = []
            for page in page_payloads:
                page_number = int(page.get("page_number") or 1)
                masked_text = str(page.get("masked_text") or "").strip()
                page_insights.append(
                    {
                        "page_number": page_number,
                        "summary": (masked_text[:80] or f"page {page_number} insight"),
                        "section_candidates": ["student_info"] if page_number == 1 else ["grades_subjects"],
                        "evidence_notes": [f"evidence found on page {page_number}"],
                    }
                )
                if masked_text:
                    key_points.append(masked_text[:60])

            return response_model.model_validate(
                {
                    "batch_summary": "masked batch summary",
                    "key_points": key_points[:3],
                    "page_insights": page_insights,
                    "evidence_gaps": ["some table cells were partially parsed"],
                    "section_candidates": {
                        "student_info": {"confidence": 0.9, "pages": [1]},
                        "grades_subjects": {"confidence": 0.76, "pages": [max(1, len(page_payloads))]},
                    },
                    "ambiguity_notes": ["section border between notes and behavior is unclear"],
                    "extraction_limits": ["masked text quality differs by page"],
                    "document_type": "korean_student_record_pdf",
                    "document_type_confidence": 0.82,
                    "likely_student_record": True,
                }
            )

        return response_model.model_validate(
            {
                "summary": "overall summary from stage outputs",
                "key_points": ["point-1", "point-2"],
                "page_insights": [
                    {
                        "page_number": 1,
                        "summary": "page 1 key facts",
                        "section_candidates": ["student_info"],
                        "evidence_notes": ["student field labels visible"],
                    }
                ],
                "evidence_gaps": ["page 2 table structure is partially broken"],
                "document_type": "korean_student_record_pdf",
                "document_type_confidence": 0.88,
                "likely_student_record": True,
                "section_candidates": {
                    "student_info": {"confidence": 0.93, "pages": [1]},
                    "grades_subjects": {"confidence": 0.71, "pages": [2, 3]},
                },
                "ambiguity_notes": ["subject note and behavior note may overlap"],
                "extraction_limits": ["a few pages had low text quality"],
            }
        )


def _extract_json_payload(prompt: str) -> dict[str, object]:
    marker = "Input payload:\n"
    if marker in prompt:
        candidate = prompt.split(marker, 1)[1].strip()
        return json.loads(candidate)

    marker = "Stage A payload:\n"
    if marker in prompt:
        candidate = prompt.split(marker, 1)[1].strip()
        return json.loads(candidate)

    start = prompt.find("{")
    if start < 0:
        return {}
    return json.loads(prompt[start:])


def _build_payload(*, page_count: int = 3, raw_marker: str = "RAW_SECRET_TEXT") -> ParsedDocumentPayload:
    masked_pages = [
        {
            "page_number": page_number,
            "masked_text": (
                f"Masked page {page_number} student info and grades with section evidence."
                if page_number > 1
                else "Masked page 1 student info section with school and student profile."
            ),
        }
        for page_number in range(1, page_count + 1)
    ]

    return ParsedDocumentPayload(
        parser_name="pymupdf",
        source_extension=".pdf",
        page_count=page_count,
        word_count=1200,
        content_text="\n\n".join(
            f"[Page {page_number}] masked content page {page_number}" for page_number in range(1, page_count + 1)
        ),
        content_markdown="",
        metadata={
            "raw_parse_artifact": {
                "pages": [{"page_number": 1, "text": raw_marker}],
            }
        },
        chunks=[
            ParsedChunkPayload(
                chunk_index=0,
                page_number=1,
                char_start=0,
                char_end=80,
                token_estimate=20,
                content_text="chunk-level masked content",
            )
        ],
        raw_artifact={"pages": [{"page_number": page_number, "text": raw_marker} for page_number in range(1, page_count + 1)]},
        masked_artifact={"pages": masked_pages},
    )


def _patch_settings(monkeypatch, **kwargs) -> Settings:
    settings = Settings(
        pdf_analysis_llm_enabled=True,
        pdf_analysis_llm_provider="ollama",
        pdf_analysis_ollama_model="gemma4-pdf",
        pdf_analysis_ollama_base_url="http://localhost:11434/v1",
        **kwargs,
    )
    monkeypatch.setattr("unifoli_api.services.pdf_analysis_service.get_settings", lambda: settings)
    return settings


def _patch_resolution(
    monkeypatch,
    llm_client,
    *,
    attempted_provider: str = "ollama",
    attempted_model: str = "gemma4-pdf",
    actual_provider: str = "ollama",
    actual_model: str | None = None,
    fallback_used: bool = False,
    fallback_reason: str | None = None,
) -> None:  # noqa: ANN001
    resolution = PDFAnalysisLLMResolution(
        attempted_provider=attempted_provider,
        attempted_model=attempted_model,
        actual_provider=actual_provider,
        actual_model=actual_model or attempted_model,
        client=llm_client,
        fallback_used=fallback_used,
        fallback_reason=fallback_reason,
    )
    monkeypatch.setattr("unifoli_api.services.pdf_analysis_service.resolve_pdf_analysis_llm_resolution", lambda: resolution)


def test_pdf_analysis_llm_success_path(monkeypatch) -> None:
    _patch_settings(monkeypatch)
    fake_llm = _DeterministicPdfLLM()
    _patch_resolution(monkeypatch, fake_llm)

    metadata = build_pdf_analysis_metadata(_build_payload())

    assert metadata is not None
    assert metadata["schema_version"] == "2026-04-13-pdf-analysis-v2"
    assert metadata["engine"] == "llm"
    assert metadata["fallback_used"] is False
    assert metadata["fallback_reason"] is None
    assert metadata["actual_provider"] == "ollama"
    assert metadata["actual_model"] == "gemma4-pdf"
    assert metadata["summary"]
    assert metadata["key_points"]
    assert metadata["page_insights"]
    assert metadata["evidence_gaps"]


def test_pdf_analysis_invalid_json_retry_then_success(monkeypatch) -> None:
    _patch_settings(monkeypatch)
    fake_llm = _DeterministicPdfLLM(fail_mode="invalid_json_once")
    _patch_resolution(monkeypatch, fake_llm)

    metadata = build_pdf_analysis_metadata(_build_payload())

    assert metadata is not None
    assert metadata["engine"] == "llm"
    assert metadata["fallback_used"] is False
    assert fake_llm.invalid_json_triggered is True
    assert fake_llm.stage_a_calls >= 2
    temperatures = [float(call["temperature"]) for call in fake_llm.calls]
    assert min(temperatures) <= 0.08


def test_pdf_analysis_timeout_to_heuristic_fallback(monkeypatch) -> None:
    _patch_settings(monkeypatch)
    fake_llm = _DeterministicPdfLLM(fail_mode="timeout")
    _patch_resolution(monkeypatch, fake_llm)

    metadata = build_pdf_analysis_metadata(_build_payload())

    assert metadata is not None
    assert metadata["engine"] == "heuristic"
    assert metadata["fallback_used"] is True
    assert metadata["fallback_reason"].startswith("stage_a_")
    assert metadata["actual_provider"] == "heuristic"
    assert metadata["actual_model"] == "heuristic-summary-v1"
    assert metadata["actual_pdf_analysis_provider"] == "heuristic"
    assert metadata["actual_pdf_analysis_model"] == "heuristic-summary-v1"


def test_pdf_analysis_success_preserves_provider_fallback_metadata(monkeypatch) -> None:
    _patch_settings(monkeypatch)
    fake_llm = _DeterministicPdfLLM()
    _patch_resolution(
        monkeypatch,
        fake_llm,
        attempted_provider="ollama",
        attempted_model="gemma4-pdf",
        actual_provider="gemini",
        actual_model="gemini-2.0-flash",
        fallback_used=True,
        fallback_reason="ollama_unreachable",
    )

    metadata = build_pdf_analysis_metadata(_build_payload())

    assert metadata is not None
    assert metadata["engine"] == "llm"
    assert metadata["fallback_used"] is True
    assert metadata["fallback_reason"] == "ollama_unreachable"
    assert metadata["attempted_provider"] == "ollama"
    assert metadata["actual_provider"] == "gemini"
    assert metadata["actual_model"] == "gemini-2.0-flash"


def test_pdf_analysis_metadata_provider_model_fields(monkeypatch) -> None:
    _patch_settings(monkeypatch)
    fake_llm = _DeterministicPdfLLM()
    _patch_resolution(monkeypatch, fake_llm, attempted_model="gemma4-pdf")

    metadata = build_pdf_analysis_metadata(_build_payload())

    assert metadata is not None
    assert metadata["attempted_provider"] == "ollama"
    assert metadata["attempted_model"] == "gemma4-pdf"
    assert metadata["actual_provider"] == "ollama"
    assert metadata["actual_model"] == "gemma4-pdf"
    assert metadata["requested_pdf_analysis_provider"] == "ollama"
    assert metadata["requested_pdf_analysis_model"] == "gemma4-pdf"


def test_pdf_analysis_oversized_pdf_uses_two_stage_batches(monkeypatch) -> None:
    _patch_settings(monkeypatch)
    fake_llm = _DeterministicPdfLLM()
    _patch_resolution(monkeypatch, fake_llm)

    metadata = build_pdf_analysis_metadata(_build_payload(page_count=14))

    assert metadata is not None
    assert metadata["engine"] == "llm"
    assert fake_llm.stage_a_calls >= 3
    assert fake_llm.stage_b_calls >= 1


def test_pdf_analysis_consumer_compatibility_fields(monkeypatch) -> None:
    _patch_settings(monkeypatch)
    fake_llm = _DeterministicPdfLLM()
    _patch_resolution(monkeypatch, fake_llm)

    metadata = build_pdf_analysis_metadata(_build_payload())

    assert metadata is not None
    assert "summary" in metadata and isinstance(metadata["summary"], str)
    assert "key_points" in metadata and isinstance(metadata["key_points"], list)
    assert "page_insights" in metadata and isinstance(metadata["page_insights"], list)
    assert "evidence_gaps" in metadata and isinstance(metadata["evidence_gaps"], list)


def test_pdf_analysis_uses_masked_sources_not_raw(monkeypatch) -> None:
    _patch_settings(monkeypatch)
    fake_llm = _DeterministicPdfLLM()
    _patch_resolution(monkeypatch, fake_llm)

    raw_marker = "RAW_SECRET_SHOULD_NEVER_APPEAR"
    payload = _build_payload(page_count=2, raw_marker=raw_marker)
    metadata = build_pdf_analysis_metadata(payload)

    assert metadata is not None
    joined_prompts = "\n".join(str(call["prompt"]) for call in fake_llm.calls)
    assert raw_marker not in joined_prompts
    assert "Masked page 1" in joined_prompts


def test_pdf_analysis_sync_async_bridge_inside_running_loop(monkeypatch) -> None:
    _patch_settings(monkeypatch)
    fake_llm = _DeterministicPdfLLM()
    _patch_resolution(monkeypatch, fake_llm)

    async def _run_inside_loop() -> dict[str, object] | None:
        return build_pdf_analysis_metadata(_build_payload())

    metadata = asyncio.run(_run_inside_loop())

    assert metadata is not None
    assert metadata["engine"] == "llm"


def test_pdf_analysis_accepts_legacy_analysis_artifact_argument(monkeypatch) -> None:
    _patch_settings(monkeypatch)
    fake_llm = _DeterministicPdfLLM()
    _patch_resolution(monkeypatch, fake_llm)

    metadata = build_pdf_analysis_metadata(
        _build_payload(),
        analysis_artifact={"legacy": "value"},
    )

    assert metadata is not None
    assert metadata["engine"] == "llm"


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
    monkeypatch.setattr("unifoli_api.core.llm.get_settings", lambda: settings)

    client = get_pdf_analysis_llm_client()

    assert isinstance(client, OllamaClient)
    assert client.model == "gemma4-pdf"
    assert client.options["num_ctx"] == 1111
    assert client.options["num_predict"] == 222
    assert client.options["num_thread"] == 3
