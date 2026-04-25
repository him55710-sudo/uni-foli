from __future__ import annotations

import asyncio
import json
import logging
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from threading import Event, Lock, Thread
from typing import Any

from unifoli_api.core.config import get_settings
from unifoli_api.core.llm import LLMRequestError, PDFAnalysisLLMResolution, resolve_pdf_analysis_llm_resolution
from unifoli_ingest.models import ParsedDocumentPayload
from pydantic import BaseModel, Field

_CANONICAL_SCHEMA_VERSION = "2026-04-12"
_MAX_PAGE_INSIGHTS = 8
_MAX_KEY_POINTS = 5
_MAX_EVIDENCE_GAPS = 5

_SECTION_KEYWORDS: dict[str, tuple[str, ...]] = {
    "student_info": ("student", "name", "school", "id", "profile", "인적사항", "학적사항", "학생명"),
    "attendance": ("attendance", "absence", "late", "tardy", "present", "출결", "결석", "지각", "조퇴"),
    "awards": ("award", "prize", "competition", "수상", "상장", "수상명"),
    "creative_activities": ("creative", "club", "activity", "project", "창의적", "동아리", "자율활동", "진로활동"),
    "volunteer": ("volunteer", "service", "hours", "봉사", "봉사시간"),
    "grades_subjects": ("grade", "subject", "score", "evaluation", "교과", "성적", "발달상황"),
    "subject_special_notes": ("special note", "subject note", "comment", "세부능력", "특기사항", "세특"),
    "reading": ("reading", "book", "library", "독서", "도서명"),
    "behavior_general_comments": ("behavior", "general comment", "attitude", "행동특성", "종합의견"),
}

_SECTION_DISPLAY_LABELS: dict[str, str] = {
    "student_info": "인적·학적사항",
    "attendance": "출결상황",
    "awards": "수상경력",
    "creative_activities": "창의적 체험활동",
    "volunteer": "봉사활동",
    "grades_subjects": "교과학습발달상황",
    "subject_special_notes": "세부능력 및 특기사항",
    "reading": "독서활동",
    "behavior_general_comments": "행동특성 및 종합의견",
}

_REQUIRED_STUDENT_RECORD_SECTIONS: tuple[str, ...] = (
    "student_info",
    "attendance",
    "grades_subjects",
    "subject_special_notes",
    "creative_activities",
    "behavior_general_comments",
)

_LEGACY_SECTION_LABELS: dict[str, str] = {
    "student_info": "student_info",
    "attendance": "attendance",
    "awards": "awards",
    "creative_activities": "creative_activities",
    "volunteer": "volunteer",
    "grades_subjects": "grades_subjects",
    "subject_special_notes": "subject_special_notes",
    "reading": "reading",
    "behavior_general_comments": "behavior_general_comments",
}

_TIMELINE_PATTERNS = (
    re.compile(r"[1-3]\s*학년\s*[1-2]\s*학기"),
    re.compile(r"[1-3]\s*학년"),
    re.compile(r"[1-3]\s*-\s*[1-2]"),
    re.compile(r"[1-3]\s*year\s*[1-2]\s*term", re.IGNORECASE),
    re.compile(r"[1-3]\s*year", re.IGNORECASE),
    re.compile(r"[1-2]\s*term", re.IGNORECASE),
)

_MAJOR_HINT_KEYWORDS = (
    "major",
    "career",
    "path",
    "goal",
    "admission",
    "future",
    "전공",
    "진로",
    "희망",
    "관심",
    "학과",
    "계열",
    "적합",
    "탐구",
)
_CAREER_KEYWORDS = ("career", "major", "future", "goal", "admission", "진로", "전공", "희망", "학과", "목표")
_CONTINUITY_KEYWORDS = ("심화", "확장", "연계", "후속", "발전", "연속", "탐구", "비교")
_PROCESS_KEYWORDS = ("과정", "방법", "한계", "개선", "성찰", "분석", "실험", "관찰", "결과")
_EVIDENCE_KEYWORDS = ("수치", "데이터", "결과", "근거", "관찰", "측정", "비교", "그래프", "표")

_PDF_ANALYSIS_SCHEMA_VERSION = "2026-04-13-pdf-analysis-v2"
_HEURISTIC_MODEL_NAME = "heuristic-summary-v1"
_DEFAULT_BATCH_SIZE = 6
_REDUCED_BATCH_SIZE = 3
_MAX_PAGE_TEXT_CHARS = 1800
_MAX_STAGE_A_NOTES = 8
_MAX_AMBIGUITY_NOTES = 8
_MAX_SECTION_CANDIDATES = 12
_SUMMARY_CHAR_LIMIT = 900
_EVIDENCE_NOTE_CHAR_LIMIT = 180

_PDF_ANALYSIS_SYSTEM_INSTRUCTION = (
    "You are a PDF analysis engine for masked student records. "
    "Use only explicitly provided evidence. "
    "Never infer facts that are not present in the provided input. "
    "Return strict JSON matching the schema."
)

_PDF_ANALYSIS_BRIDGE_LOOP: asyncio.AbstractEventLoop | None = None
_PDF_ANALYSIS_BRIDGE_THREAD: Thread | None = None
_PDF_ANALYSIS_BRIDGE_LOCK = Lock()
_PDF_ANALYSIS_BRIDGE_READY = Event()

logger = logging.getLogger("unifoli.pdf_analysis")


@dataclass(frozen=True)
class _MaskedPage:
    page_number: int
    text: str


@dataclass(frozen=True)
class _PipelineAttemptConfig:
    batch_size: int
    compact_synthesis_prompt: bool


class _PipelineStageError(RuntimeError):
    def __init__(self, stage: str, code: str, detail: str | None = None) -> None:
        message = f"{stage}:{code}"
        if detail:
            message = f"{message}:{detail}"
        super().__init__(message)
        self.stage = stage
        self.code = code
        self.detail = detail


class _SectionCandidate(BaseModel):
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    pages: list[int] = Field(default_factory=list)


class _PageInsight(BaseModel):
    page_number: int = Field(ge=1)
    summary: str = ""
    section_candidates: list[str] = Field(default_factory=list)
    evidence_notes: list[str] = Field(default_factory=list)


class _StageABatchOutput(BaseModel):
    batch_summary: str = ""
    key_points: list[str] = Field(default_factory=list)
    page_insights: list[_PageInsight] = Field(default_factory=list)
    evidence_gaps: list[str] = Field(default_factory=list)
    section_candidates: dict[str, _SectionCandidate] = Field(default_factory=dict)
    ambiguity_notes: list[str] = Field(default_factory=list)
    extraction_limits: list[str] = Field(default_factory=list)
    document_type: str = "generic_pdf"
    document_type_confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    likely_student_record: bool = False


class _StageBFinalOutput(BaseModel):
    summary: str = ""
    key_points: list[str] = Field(default_factory=list)
    page_insights: list[_PageInsight] = Field(default_factory=list)
    evidence_gaps: list[str] = Field(default_factory=list)
    document_type: str = "generic_pdf"
    document_type_confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    likely_student_record: bool = False
    section_candidates: dict[str, _SectionCandidate] = Field(default_factory=dict)
    ambiguity_notes: list[str] = Field(default_factory=list)
    extraction_limits: list[str] = Field(default_factory=list)


def _async_pdf_analysis_bridge_runner() -> None:
    global _PDF_ANALYSIS_BRIDGE_LOOP
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    _PDF_ANALYSIS_BRIDGE_LOOP = loop
    _PDF_ANALYSIS_BRIDGE_READY.set()
    loop.run_forever()


def _ensure_pdf_analysis_bridge_loop() -> asyncio.AbstractEventLoop:
    global _PDF_ANALYSIS_BRIDGE_THREAD
    with _PDF_ANALYSIS_BRIDGE_LOCK:
        loop = _PDF_ANALYSIS_BRIDGE_LOOP
        if loop is not None and loop.is_running():
            return loop

        _PDF_ANALYSIS_BRIDGE_READY.clear()
        _PDF_ANALYSIS_BRIDGE_THREAD = Thread(
            target=_async_pdf_analysis_bridge_runner,
            daemon=True,
            name="unifoli-pdf-analysis-loop",
        )
        _PDF_ANALYSIS_BRIDGE_THREAD.start()

    if not _PDF_ANALYSIS_BRIDGE_READY.wait(timeout=5.0):
        raise RuntimeError("Failed to initialize PDF analysis async bridge loop.")

    loop = _PDF_ANALYSIS_BRIDGE_LOOP
    if loop is None or not loop.is_running():
        raise RuntimeError("PDF analysis async bridge loop is unavailable.")
    return loop


def _run_pdf_analysis_async(coro: Any) -> Any:
    if not asyncio.iscoroutine(coro):
        raise TypeError("_run_pdf_analysis_async expects a coroutine object.")

    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)

    loop = _ensure_pdf_analysis_bridge_loop()
    future = asyncio.run_coroutine_threadsafe(coro, loop)
    return future.result()


def build_pdf_analysis_metadata(
    parsed: ParsedDocumentPayload,
    analysis_artifact: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    # `analysis_artifact` is accepted for backward compatibility with callers
    # that still pass it from parse metadata. The current implementation does
    # not require this input directly.
    _ = analysis_artifact
    settings = get_settings()
    if not getattr(settings, "pdf_analysis_llm_enabled", True):
        return None
    if parsed.source_extension.lower() != ".pdf":
        return None

    started_at = datetime.now(timezone.utc)
    generated_at = datetime.now(timezone.utc)
    attempted_provider, attempted_model = _resolve_requested_pdf_identity(settings)
    masked_pages = _extract_masked_only_pages(parsed)

    resolution: PDFAnalysisLLMResolution | None = None
    try:
        resolution = resolve_pdf_analysis_llm_resolution()
        llm_payload = _run_pdf_analysis_async(
            _build_pdf_analysis_with_llm(
                parsed=parsed,
                masked_pages=masked_pages,
                resolution=resolution,
            )
        )
        actual_provider, actual_model, fallback_used, fallback_reason = _resolve_pdf_analysis_runtime_outcome(resolution)
        return _compose_pdf_analysis_metadata(
            llm_payload,
            started_at=started_at,
            generated_at=generated_at,
            attempted_provider=resolution.attempted_provider,
            attempted_model=resolution.attempted_model,
            actual_provider=actual_provider,
            actual_model=actual_model,
            engine="llm",
            fallback_used=fallback_used,
            fallback_reason=fallback_reason,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("PDF analysis LLM pipeline failed; switching to heuristic fallback: %s", exc)
        return _build_pdf_analysis_heuristic_fallback(
            parsed=parsed,
            masked_pages=masked_pages,
            started_at=started_at,
            generated_at=generated_at,
            attempted_provider=resolution.attempted_provider if resolution else attempted_provider,
            attempted_model=resolution.attempted_model if resolution else attempted_model,
            fallback_reason=_fallback_reason_from_exception(exc),
        )


def _resolve_requested_pdf_identity(settings: Any) -> tuple[str, str]:
    provider = str(getattr(settings, "pdf_analysis_llm_provider", "") or "ollama").strip().lower()
    if provider == "ollama":
        model = str(
            getattr(settings, "pdf_analysis_ollama_model", "")
            or getattr(settings, "ollama_model", "")
            or "gemma4"
        ).strip()
        return provider, model
    if provider == "gemini":
        model = str(getattr(settings, "pdf_analysis_gemini_model", "") or "").strip() or "gemini-2.5-flash-lite"
        return provider, model
    return provider or "unknown", "unknown"


def _extract_masked_only_pages(parsed: ParsedDocumentPayload) -> list[_MaskedPage]:
    from_masked_artifact = _extract_pages_from_masked_artifact(parsed)
    if from_masked_artifact:
        return from_masked_artifact

    from_content_text = _extract_pages_from_content_text(parsed.content_text, page_count=parsed.page_count)
    if from_content_text:
        return from_content_text

    from_chunks = _extract_pages_from_chunks(parsed)
    if from_chunks:
        return from_chunks

    return []


def _extract_pages_from_masked_artifact(parsed: ParsedDocumentPayload) -> list[_MaskedPage]:
    artifact = parsed.masked_artifact if isinstance(parsed.masked_artifact, dict) else {}
    pages = artifact.get("pages")
    if not isinstance(pages, list):
        return []

    numbered: list[tuple[int, str]] = []
    fallback_counter = 1
    for page in pages:
        if not isinstance(page, dict):
            continue
        text = str(page.get("masked_text") or "").strip()
        if not text:
            continue
        try:
            page_number = int(page.get("page_number") or fallback_counter)
        except (TypeError, ValueError):
            page_number = fallback_counter
        page_number = max(1, page_number)
        fallback_counter = page_number + 1
        numbered.append((page_number, text))

    if not numbered:
        return []

    numbered.sort(key=lambda item: item[0])
    seen_pages: set[int] = set()
    result: list[_MaskedPage] = []
    for page_number, text in numbered:
        if page_number in seen_pages:
            continue
        seen_pages.add(page_number)
        result.append(_MaskedPage(page_number=page_number, text=text))
    return result


def _extract_pages_from_content_text(content_text: str, *, page_count: int) -> list[_MaskedPage]:
    content = (content_text or "").strip()
    if not content:
        return []

    page_marker = re.compile(r"\[Page\s+(\d+)\]", re.IGNORECASE)
    marker_matches = list(page_marker.finditer(content))
    if marker_matches:
        pages: list[_MaskedPage] = []
        for index, match in enumerate(marker_matches):
            start = match.end()
            end = marker_matches[index + 1].start() if index + 1 < len(marker_matches) else len(content)
            page_number = int(match.group(1))
            text = content[start:end].strip()
            if text:
                pages.append(_MaskedPage(page_number=max(1, page_number), text=text))
        if pages:
            pages.sort(key=lambda page: page.page_number)
            return pages

    max_pages = max(1, page_count)
    parts = [part.strip() for part in re.split(r"\n{2,}|\f", content) if part.strip()]
    if len(parts) >= 2:
        return [_MaskedPage(page_number=index + 1, text=part) for index, part in enumerate(parts[:max_pages])]

    return [_MaskedPage(page_number=1, text=content)]


def _extract_pages_from_chunks(parsed: ParsedDocumentPayload) -> list[_MaskedPage]:
    if not isinstance(parsed.chunks, list) or not parsed.chunks:
        return []

    bucket: dict[int, list[str]] = {}
    fallback_index = 1
    for chunk in parsed.chunks:
        text = str(getattr(chunk, "content_text", "") or "").strip()
        if not text:
            continue
        try:
            page_number = int(getattr(chunk, "page_number", 0) or 0)
        except (TypeError, ValueError):
            page_number = 0
        if page_number <= 0:
            page_number = fallback_index
            fallback_index += 1
        bucket.setdefault(page_number, []).append(text)

    if not bucket:
        return []

    pages: list[_MaskedPage] = []
    for page_number in sorted(bucket):
        joined = " ".join(part for part in bucket[page_number] if part).strip()
        if joined:
            pages.append(_MaskedPage(page_number=page_number, text=joined))
    return pages


async def _build_pdf_analysis_with_llm(
    *,
    parsed: ParsedDocumentPayload,
    masked_pages: list[_MaskedPage],
    resolution: PDFAnalysisLLMResolution,
) -> dict[str, Any]:
    if not masked_pages:
        raise _PipelineStageError("input", "masked_input_unavailable")

    unique_configs: list[_PipelineAttemptConfig] = []
    for config in _pipeline_attempt_configs(total_pages=len(masked_pages)):
        if config not in unique_configs:
            unique_configs.append(config)

    latest_error: _PipelineStageError | None = None
    for config in unique_configs:
        try:
            stage_a = await _run_stage_a(
                pages=masked_pages,
                resolution=resolution,
                batch_size=config.batch_size,
            )
            stage_b = await _run_stage_b(
                stage_a_outputs=stage_a,
                resolution=resolution,
                compact_prompt=config.compact_synthesis_prompt,
            )
            return _normalize_llm_final_output(
                parsed=parsed,
                masked_pages=masked_pages,
                stage_a_outputs=stage_a,
                stage_b_output=stage_b,
            )
        except _PipelineStageError as exc:
            latest_error = exc
            continue

    if latest_error is not None:
        raise latest_error
    raise _PipelineStageError("pipeline", "unknown_failure")


def _pipeline_attempt_configs(*, total_pages: int) -> list[_PipelineAttemptConfig]:
    initial_batch_size = max(1, min(_DEFAULT_BATCH_SIZE, total_pages or _DEFAULT_BATCH_SIZE))
    reduced_batch_size = max(1, min(_REDUCED_BATCH_SIZE, initial_batch_size))
    if total_pages >= 18:
        initial_batch_size = min(initial_batch_size, 5)
        reduced_batch_size = min(reduced_batch_size, 2)
    return [
        _PipelineAttemptConfig(batch_size=initial_batch_size, compact_synthesis_prompt=False),
        _PipelineAttemptConfig(batch_size=reduced_batch_size, compact_synthesis_prompt=False),
        _PipelineAttemptConfig(batch_size=reduced_batch_size, compact_synthesis_prompt=True),
    ]


async def _run_stage_a(
    *,
    pages: list[_MaskedPage],
    resolution: PDFAnalysisLLMResolution,
    batch_size: int,
) -> list[dict[str, Any]]:
    if batch_size <= 0:
        raise _PipelineStageError("stage_a", "invalid_batch_size")

    batches = [pages[index : index + batch_size] for index in range(0, len(pages), batch_size)]
    stage_outputs: list[dict[str, Any]] = []
    total_batches = max(1, len(batches))

    for batch_index, batch in enumerate(batches, start=1):
        prompt = _build_stage_a_prompt(batch=batch, batch_index=batch_index, total_batches=total_batches)
        response = await _generate_stage_json(
            resolution=resolution,
            prompt=prompt,
            response_model=_StageABatchOutput,
            stage_name="stage_a",
            temperature=0.2,
        )
        stage_outputs.append(
            _normalize_stage_a_batch_output(
                payload=response,
                batch=batch,
                batch_index=batch_index,
            )
        )
    return stage_outputs


async def _run_stage_b(
    *,
    stage_a_outputs: list[dict[str, Any]],
    resolution: PDFAnalysisLLMResolution,
    compact_prompt: bool,
) -> _StageBFinalOutput:
    prompt = _build_stage_b_prompt(stage_a_outputs=stage_a_outputs, compact_prompt=compact_prompt)
    return await _generate_stage_json(
        resolution=resolution,
        prompt=prompt,
        response_model=_StageBFinalOutput,
        stage_name="stage_b",
        temperature=0.16 if compact_prompt else 0.2,
    )


async def _generate_stage_json(
    *,
    resolution: PDFAnalysisLLMResolution,
    prompt: str,
    response_model: type[BaseModel],
    stage_name: str,
    temperature: float,
) -> Any:
    client = resolution.client
    try:
        return await client.generate_json(
            prompt,
            response_model=response_model,
            system_instruction=_PDF_ANALYSIS_SYSTEM_INSTRUCTION,
            temperature=temperature,
        )
    except Exception as first_exc:  # noqa: BLE001
        retry_prompt = (
            f"{prompt}\n\n"
            "Retry mode:\n"
            "- Repair schema violations.\n"
            "- Lower creativity and return deterministic JSON only.\n"
            "- Output JSON only.\n"
        )
        try:
            return await client.generate_json(
                retry_prompt,
                response_model=response_model,
                system_instruction=_PDF_ANALYSIS_SYSTEM_INSTRUCTION,
                temperature=min(temperature, 0.08),
            )
        except Exception as second_exc:  # noqa: BLE001
            code = _classify_llm_exception(second_exc)
            if code == "unknown_failure":
                code = _classify_llm_exception(first_exc)
            raise _PipelineStageError(stage_name, code, type(second_exc).__name__) from second_exc


def _classify_llm_exception(exc: Exception) -> str:
    if isinstance(exc, LLMRequestError):
        reason = str(getattr(exc, "limited_reason", "") or "").strip().lower()
        if reason:
            return reason
        return "llm_request_error"
    if isinstance(exc, (TimeoutError, asyncio.TimeoutError)):
        return "timeout"
    name = type(exc).__name__.strip().lower()
    return name or "unknown_failure"


def _build_stage_a_prompt(*, batch: list[_MaskedPage], batch_index: int, total_batches: int) -> str:
    payload = {
        "batch_index": batch_index,
        "total_batches": total_batches,
        "pages": [
            {"page_number": page.page_number, "masked_text": _clip(page.text, _MAX_PAGE_TEXT_CHARS)}
            for page in batch
        ],
    }
    payload_json = json.dumps(payload, ensure_ascii=False, indent=2)
    return (
        "Stage A task: compress masked PDF pages into evidence-grounded intermediate JSON.\n"
        "Rules:\n"
        "1. Use only the provided masked text.\n"
        "2. Only include page-verifiable claims.\n"
        "3. Do not infer missing facts.\n"
        "4. Unknown or uncertain items must go to evidence_gaps or ambiguity_notes.\n"
        "5. Section labels are confidence-based candidates only.\n"
        "6. Output JSON only.\n\n"
        f"Input payload:\n{payload_json}"
    )


def _build_stage_b_prompt(*, stage_a_outputs: list[dict[str, Any]], compact_prompt: bool) -> str:
    payload = {"stage_a_outputs": stage_a_outputs}
    payload_json = json.dumps(payload, ensure_ascii=False, indent=2)
    if compact_prompt:
        return (
            "Stage B task: synthesize final document analysis strictly from Stage A outputs.\n"
            "No new facts. Unknown info must stay in evidence_gaps or ambiguity_notes.\n"
            "Output JSON only.\n\n"
            f"Stage A payload:\n{payload_json}"
        )
    return (
        "Stage B task: synthesize final JSON for the entire PDF using only Stage A outputs.\n"
        "Rules:\n"
        "1. Do not use any source outside Stage A output.\n"
        "2. Keep claims evidence-grounded and page-verifiable.\n"
        "3. If evidence is missing, use evidence_gaps or ambiguity_notes.\n"
        "4. Section classification must remain candidate/confidence based.\n"
        "5. Output JSON only.\n\n"
        f"Stage A payload:\n{payload_json}"
    )


def _normalize_stage_a_batch_output(
    *,
    payload: _StageABatchOutput,
    batch: list[_MaskedPage],
    batch_index: int,
) -> dict[str, Any]:
    valid_pages = {page.page_number for page in batch}
    normalized_page_insights: list[dict[str, Any]] = []
    for item in payload.page_insights:
        if item.page_number not in valid_pages:
            continue
        summary = _clip(item.summary, _SUMMARY_CHAR_LIMIT)
        if not summary:
            continue
        normalized_page_insights.append(
            {
                "page_number": item.page_number,
                "summary": summary,
                "section_candidates": _dedupe(
                    [str(value).strip() for value in item.section_candidates if str(value).strip()],
                    limit=6,
                ),
                "evidence_notes": _dedupe(
                    [_clip(str(note), _EVIDENCE_NOTE_CHAR_LIMIT) for note in item.evidence_notes if str(note).strip()],
                    limit=6,
                ),
            }
        )

    section_candidates = _normalize_section_candidates(payload.section_candidates, page_cap=max(valid_pages or {1}))
    return {
        "batch_index": batch_index,
        "batch_summary": _clip(payload.batch_summary, _SUMMARY_CHAR_LIMIT),
        "key_points": _dedupe([_clip(item, 220) for item in payload.key_points], limit=_MAX_KEY_POINTS),
        "page_insights": normalized_page_insights,
        "evidence_gaps": _dedupe([_clip(item, 220) for item in payload.evidence_gaps], limit=_MAX_STAGE_A_NOTES),
        "section_candidates": section_candidates,
        "ambiguity_notes": _dedupe([_clip(item, 220) for item in payload.ambiguity_notes], limit=_MAX_AMBIGUITY_NOTES),
        "extraction_limits": _dedupe(
            [_clip(item, 220) for item in payload.extraction_limits],
            limit=_MAX_STAGE_A_NOTES,
        ),
        "document_type": str(payload.document_type or "generic_pdf").strip() or "generic_pdf",
        "document_type_confidence": max(0.0, min(1.0, float(payload.document_type_confidence))),
        "likely_student_record": bool(payload.likely_student_record),
    }


def _normalize_llm_final_output(
    *,
    parsed: ParsedDocumentPayload,
    masked_pages: list[_MaskedPage],
    stage_a_outputs: list[dict[str, Any]],
    stage_b_output: _StageBFinalOutput,
) -> dict[str, Any]:
    combined_stage_a_key_points: list[str] = []
    combined_stage_a_gaps: list[str] = []
    combined_ambiguity: list[str] = []
    combined_limits: list[str] = []
    for batch in stage_a_outputs:
        combined_stage_a_key_points.extend(batch.get("key_points") or [])
        combined_stage_a_gaps.extend(batch.get("evidence_gaps") or [])
        combined_ambiguity.extend(batch.get("ambiguity_notes") or [])
        combined_limits.extend(batch.get("extraction_limits") or [])

    summary = _clip(stage_b_output.summary, _SUMMARY_CHAR_LIMIT)
    if not summary:
        summary = _build_pdf_summary(parsed, [page.text for page in masked_pages])

    key_points = _dedupe(
        [_clip(item, 220) for item in stage_b_output.key_points]
        + [_clip(item, 220) for item in combined_stage_a_key_points],
        limit=_MAX_KEY_POINTS,
    )
    if not key_points:
        key_points = _extract_key_points([page.text for page in masked_pages])

    page_insights = _normalize_page_insights(stage_b_output.page_insights, masked_pages)
    if not page_insights:
        page_insights = _fallback_page_insights_from_stage_a(stage_a_outputs, masked_pages)
    if not page_insights:
        page_insights = _build_page_insights_with_candidates(masked_pages)

    evidence_gaps = _dedupe(
        [_clip(item, 220) for item in stage_b_output.evidence_gaps] + [_clip(item, 220) for item in combined_stage_a_gaps],
        limit=_MAX_EVIDENCE_GAPS,
    )
    if not evidence_gaps:
        evidence_gaps = _build_evidence_gaps(parsed, [page.text for page in masked_pages])

    section_candidates = _normalize_section_candidates(
        stage_b_output.section_candidates,
        page_cap=max((page.page_number for page in masked_pages), default=1),
    )
    if not section_candidates:
        section_candidates = _infer_section_candidates(masked_pages)

    ambiguity_notes = _dedupe(
        [_clip(item, 220) for item in stage_b_output.ambiguity_notes] + [_clip(item, 220) for item in combined_ambiguity],
        limit=_MAX_AMBIGUITY_NOTES,
    )
    extraction_limits = _dedupe(
        [_clip(item, 220) for item in stage_b_output.extraction_limits] + [_clip(item, 220) for item in combined_limits],
        limit=_MAX_STAGE_A_NOTES,
    )

    document_type, confidence, likely_student_record = _normalize_document_type(
        document_type=stage_b_output.document_type,
        confidence=stage_b_output.document_type_confidence,
        likely_student_record=stage_b_output.likely_student_record,
        section_candidates=section_candidates,
    )

    return {
        "schema_version": _PDF_ANALYSIS_SCHEMA_VERSION,
        "summary": summary,
        "key_points": key_points,
        "page_insights": page_insights,
        "evidence_gaps": evidence_gaps,
        "document_type": document_type,
        "document_type_confidence": confidence,
        "likely_student_record": likely_student_record,
        "section_candidates": section_candidates,
        "ambiguity_notes": ambiguity_notes,
        "extraction_limits": extraction_limits,
    }


def _normalize_page_insights(page_insights: list[_PageInsight], masked_pages: list[_MaskedPage]) -> list[dict[str, Any]]:
    valid_pages = {page.page_number for page in masked_pages}
    normalized: list[dict[str, Any]] = []
    for item in page_insights:
        if item.page_number not in valid_pages:
            continue
        summary = _clip(item.summary, _SUMMARY_CHAR_LIMIT)
        if not summary:
            continue
        normalized.append(
            {
                "page_number": item.page_number,
                "summary": summary,
                "section_candidates": _dedupe(
                    [str(value).strip() for value in item.section_candidates if str(value).strip()],
                    limit=6,
                ),
                "evidence_notes": _dedupe(
                    [_clip(str(note), _EVIDENCE_NOTE_CHAR_LIMIT) for note in item.evidence_notes if str(note).strip()],
                    limit=6,
                ),
            }
        )
    normalized.sort(key=lambda item: int(item["page_number"]))
    return normalized[:_MAX_PAGE_INSIGHTS]


def _fallback_page_insights_from_stage_a(
    stage_a_outputs: list[dict[str, Any]],
    masked_pages: list[_MaskedPage],
) -> list[dict[str, Any]]:
    valid_pages = {page.page_number for page in masked_pages}
    collected: list[dict[str, Any]] = []
    for batch in stage_a_outputs:
        for insight in batch.get("page_insights") or []:
            if not isinstance(insight, dict):
                continue
            page_number = int(insight.get("page_number") or 0)
            if page_number <= 0 or page_number not in valid_pages:
                continue
            summary = _clip(str(insight.get("summary") or ""), _SUMMARY_CHAR_LIMIT)
            if not summary:
                continue
            collected.append(
                {
                    "page_number": page_number,
                    "summary": summary,
                    "section_candidates": _dedupe(
                        [str(item).strip() for item in insight.get("section_candidates", []) if str(item).strip()],
                        limit=6,
                    ),
                    "evidence_notes": _dedupe(
                        [
                            _clip(str(item), _EVIDENCE_NOTE_CHAR_LIMIT)
                            for item in insight.get("evidence_notes", [])
                            if str(item).strip()
                        ],
                        limit=6,
                    ),
                }
            )
    collected.sort(key=lambda item: int(item["page_number"]))
    deduped: list[dict[str, Any]] = []
    seen_pages: set[int] = set()
    for item in collected:
        page_number = int(item["page_number"])
        if page_number in seen_pages:
            continue
        seen_pages.add(page_number)
        deduped.append(item)
        if len(deduped) >= _MAX_PAGE_INSIGHTS:
            break
    return deduped


def _normalize_section_candidates(candidates: Any, *, page_cap: int) -> dict[str, dict[str, Any]]:
    if not isinstance(candidates, dict):
        return {}
    normalized: dict[str, dict[str, Any]] = {}
    for label, payload in list(candidates.items())[:_MAX_SECTION_CANDIDATES]:
        key = str(label or "").strip()
        if not key:
            continue
        confidence = 0.0
        pages: list[int] = []
        if isinstance(payload, _SectionCandidate):
            confidence = float(payload.confidence)
            pages = [int(page) for page in payload.pages]
        elif isinstance(payload, dict):
            try:
                confidence = float(payload.get("confidence") or 0.0)
            except (TypeError, ValueError):
                confidence = 0.0
            raw_pages = payload.get("pages")
            if isinstance(raw_pages, list):
                for value in raw_pages:
                    try:
                        page_number = int(value)
                    except (TypeError, ValueError):
                        continue
                    if 1 <= page_number <= max(1, page_cap):
                        pages.append(page_number)
        pages = sorted({page for page in pages if 1 <= page <= max(1, page_cap)})
        if not pages and confidence <= 0.0:
            continue
        normalized[key] = {
            "confidence": round(max(0.0, min(1.0, confidence)), 3),
            "pages": pages,
        }
    return normalized


def _normalize_document_type(
    *,
    document_type: str,
    confidence: float,
    likely_student_record: bool,
    section_candidates: dict[str, dict[str, Any]],
) -> tuple[str, float, bool]:
    normalized_type = str(document_type or "").strip() or "generic_pdf"
    normalized_confidence = round(max(0.0, min(1.0, float(confidence))), 3)
    inferred_likely = bool(likely_student_record)
    if not inferred_likely:
        inferred_likely = "student_info" in section_candidates and "grades_subjects" in section_candidates
    if normalized_type == "generic_pdf" and inferred_likely:
        normalized_type = "korean_student_record_pdf"
    if normalized_confidence <= 0.0:
        normalized_confidence = 0.65 if inferred_likely else 0.42
    return normalized_type, normalized_confidence, inferred_likely


def _build_pdf_analysis_heuristic_fallback(
    *,
    parsed: ParsedDocumentPayload,
    masked_pages: list[_MaskedPage],
    started_at: datetime,
    generated_at: datetime,
    attempted_provider: str,
    attempted_model: str,
    fallback_reason: str,
) -> dict[str, Any]:
    page_texts = [page.text for page in masked_pages]
    section_candidates = _infer_section_candidates(masked_pages)
    likely_student_record = "student_info" in section_candidates and "grades_subjects" in section_candidates
    document_type = "korean_student_record_pdf" if likely_student_record else "generic_pdf"
    document_type_confidence = round(0.67 if likely_student_record else 0.4, 3)

    payload = {
        "schema_version": _PDF_ANALYSIS_SCHEMA_VERSION,
        "summary": _build_pdf_summary(parsed, page_texts),
        "key_points": _extract_key_points(page_texts),
        "page_insights": _build_page_insights_with_candidates(masked_pages),
        "evidence_gaps": _build_evidence_gaps(parsed, page_texts),
        "document_type": document_type,
        "document_type_confidence": document_type_confidence,
        "likely_student_record": likely_student_record,
        "section_candidates": section_candidates,
        "ambiguity_notes": ["LLM synthesis unavailable; using heuristic-only interpretation."],
        "extraction_limits": ["Fallback mode uses deterministic heuristics with masked text only."],
    }
    if fallback_reason:
        payload["extraction_limits"].append(f"fallback_reason={fallback_reason}")

    return _compose_pdf_analysis_metadata(
        payload,
        started_at=started_at,
        generated_at=generated_at,
        attempted_provider=attempted_provider,
        attempted_model=attempted_model,
        actual_provider="heuristic",
        actual_model=_HEURISTIC_MODEL_NAME,
        engine="heuristic",
        fallback_used=True,
        fallback_reason=fallback_reason or "heuristic_only",
    )


def _resolve_pdf_analysis_runtime_outcome(
    resolution: PDFAnalysisLLMResolution,
) -> tuple[str, str, bool, str | None]:
    client = resolution.client
    actual_provider = (
        str(getattr(client, "last_provider_used", "") or "").strip()
        if client is not None
        else ""
    ) or resolution.actual_provider
    actual_model = (
        str(getattr(client, "last_model_used", "") or "").strip()
        if client is not None
        else ""
    ) or resolution.actual_model
    fallback_used = bool(
        getattr(client, "last_fallback_used", resolution.fallback_used)
        if client is not None
        else resolution.fallback_used
    )
    fallback_reason = (
        str(getattr(client, "last_fallback_reason", "") or "").strip()
        if client is not None
        else ""
    ) or resolution.fallback_reason
    if actual_provider != resolution.attempted_provider or actual_model != resolution.attempted_model:
        fallback_used = True
        fallback_reason = fallback_reason or "provider_auto_fallback"
    elif fallback_reason:
        fallback_used = True
    return actual_provider, actual_model, fallback_used, fallback_reason


def _compose_pdf_analysis_metadata(
    payload: dict[str, Any],
    *,
    started_at: datetime,
    generated_at: datetime,
    attempted_provider: str,
    attempted_model: str,
    actual_provider: str,
    actual_model: str,
    engine: str,
    fallback_used: bool,
    fallback_reason: str | None,
) -> dict[str, Any]:
    duration_ms = int(max(0.0, (datetime.now(timezone.utc) - started_at).total_seconds() * 1000.0))
    metadata = {
        "schema_version": str(payload.get("schema_version") or _PDF_ANALYSIS_SCHEMA_VERSION),
        "provider": attempted_provider,
        "attempted_provider": attempted_provider,
        "model": attempted_model,
        "attempted_model": attempted_model,
        "actual_provider": actual_provider,
        "actual_model": actual_model,
        "engine": engine,
        "attempted_pdf_analysis_provider": attempted_provider,
        "attempted_pdf_analysis_model": attempted_model,
        "requested_pdf_analysis_provider": attempted_provider,
        "requested_pdf_analysis_model": attempted_model,
        "actual_pdf_analysis_provider": actual_provider,
        "actual_pdf_analysis_model": actual_model,
        "pdf_analysis_engine": engine,
        "fallback_used": fallback_used,
        "fallback_reason": fallback_reason,
        "processing_duration_ms": duration_ms,
        "generated_at": generated_at.isoformat(),
        "summary": _clip(str(payload.get("summary") or ""), _SUMMARY_CHAR_LIMIT),
        "key_points": _dedupe(
            [str(item).strip() for item in payload.get("key_points", []) if str(item).strip()],
            limit=_MAX_KEY_POINTS,
        ),
        "page_insights": _normalize_legacy_page_insights(payload.get("page_insights")),
        "evidence_gaps": _dedupe(
            [str(item).strip() for item in payload.get("evidence_gaps", []) if str(item).strip()],
            limit=_MAX_EVIDENCE_GAPS,
        ),
        "document_type": str(payload.get("document_type") or "generic_pdf").strip() or "generic_pdf",
        "document_type_confidence": round(
            max(0.0, min(1.0, float(payload.get("document_type_confidence") or 0.0))),
            3,
        ),
        "likely_student_record": bool(payload.get("likely_student_record")),
        "section_candidates": _normalize_section_candidates(payload.get("section_candidates"), page_cap=999),
        "ambiguity_notes": _dedupe(
            [_clip(str(item), 220) for item in payload.get("ambiguity_notes", []) if str(item).strip()],
            limit=_MAX_AMBIGUITY_NOTES,
        ),
        "extraction_limits": _dedupe(
            [_clip(str(item), 220) for item in payload.get("extraction_limits", []) if str(item).strip()],
            limit=_MAX_STAGE_A_NOTES,
        ),
    }
    if not metadata["summary"]:
        metadata["summary"] = "Masked text was analyzed, but the summary could not be finalized."
    if not metadata["key_points"]:
        metadata["key_points"] = ["No stable key point could be extracted from the masked text."]
    if not metadata["page_insights"]:
        metadata["page_insights"] = [
            {"page_number": 1, "summary": metadata["summary"], "section_candidates": [], "evidence_notes": []}
        ]
    if not metadata["evidence_gaps"]:
        metadata["evidence_gaps"] = ["No explicit evidence gaps were reported."]
    return metadata


def _normalize_legacy_page_insights(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    normalized: list[dict[str, Any]] = []
    for item in value[:_MAX_PAGE_INSIGHTS]:
        if not isinstance(item, dict):
            continue
        try:
            page_number = int(item.get("page_number") or 0)
        except (TypeError, ValueError):
            page_number = 0
        if page_number <= 0:
            continue
        summary = _clip(str(item.get("summary") or ""), _SUMMARY_CHAR_LIMIT)
        if not summary:
            continue
        normalized.append(
            {
                "page_number": page_number,
                "summary": summary,
                "section_candidates": _dedupe(
                    [str(section).strip() for section in item.get("section_candidates", []) if str(section).strip()],
                    limit=6,
                ),
                "evidence_notes": _dedupe(
                    [_clip(str(note), _EVIDENCE_NOTE_CHAR_LIMIT) for note in item.get("evidence_notes", []) if str(note).strip()],
                    limit=6,
                ),
            }
        )
    normalized.sort(key=lambda item: int(item["page_number"]))
    return normalized


def _build_page_insights_with_candidates(masked_pages: list[_MaskedPage]) -> list[dict[str, Any]]:
    inferred_sections = _infer_section_candidates(masked_pages)
    page_to_sections: dict[int, list[str]] = {}
    for section, payload in inferred_sections.items():
        for page_number in payload.get("pages", []):
            page_to_sections.setdefault(int(page_number), []).append(section)

    insights: list[dict[str, Any]] = []
    for page in masked_pages[:_MAX_PAGE_INSIGHTS]:
        summary = _clip(_normalize_sentence(page.text), 220)
        if not summary:
            continue
        evidence_notes = _dedupe(_extract_key_points([page.text]), limit=3)
        insights.append(
            {
                "page_number": page.page_number,
                "summary": summary,
                "section_candidates": _dedupe(page_to_sections.get(page.page_number, []), limit=6),
                "evidence_notes": evidence_notes,
            }
        )
    return insights


def _infer_section_candidates(masked_pages: list[_MaskedPage]) -> dict[str, dict[str, Any]]:
    results: dict[str, dict[str, Any]] = {}
    for section, keywords in _SECTION_KEYWORDS.items():
        matched_pages: list[int] = []
        match_score = 0.0
        lowered_keywords = [keyword.lower() for keyword in keywords if keyword]
        for page in masked_pages:
            lowered_text = page.text.lower()
            page_hits = sum(1 for keyword in lowered_keywords if keyword in lowered_text)
            if page_hits <= 0:
                continue
            matched_pages.append(page.page_number)
            match_score += page_hits / max(1, len(lowered_keywords))
        if not matched_pages:
            continue
        confidence = min(0.99, 0.45 + (match_score / max(len(matched_pages), 1)) * 0.5)
        results[section] = {
            "confidence": round(confidence, 3),
            "pages": sorted({int(page) for page in matched_pages}),
        }
    return results


def _fallback_reason_from_exception(exc: Exception) -> str:
    if isinstance(exc, _PipelineStageError):
        stage = str(exc.stage or "pipeline").strip().lower()
        code = str(exc.code or "unknown_failure").strip().lower()
        return f"{stage}_{code}"
    if isinstance(exc, LLMRequestError):
        reason = str(getattr(exc, "limited_reason", "") or "").strip().lower()
        return reason or "llm_request_error"
    return f"pipeline_{type(exc).__name__.strip().lower() or 'unknown_failure'}"


def build_student_record_canonical_metadata(
    *,
    parsed: ParsedDocumentPayload,
    pdf_analysis: dict[str, Any] | None = None,
    analysis_artifact: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    pipeline_canonical = _extract_pipeline_canonical(analysis_artifact)
    if not _looks_like_student_record(parsed, pipeline_canonical):
        return None

    text = _combined_text(parsed)
    page_texts = _extract_page_texts(parsed)
    section_classification = _classify_sections(text)
    section_coverage = _build_section_coverage(section_classification)
    coverage_score = float(section_coverage["coverage_score"])

    timeline_signals = [{"signal": value} for value in _extract_timeline_signals(text)]
    major_alignment_hints = [{"hint": value} for value in _extract_major_alignment_hints(text)]
    weak_sections = [{"section": value} for value in section_coverage["missing_sections"]]
    uncertainties = [{"message": value} for value in _build_uncertainties(parsed, pdf_analysis, section_coverage)]

    grades_subjects = _extract_grades_subjects(text, pipeline_canonical)
    subject_special_notes = _extract_subject_special_notes(text, pipeline_canonical)
    extracurricular = _extract_extracurricular(text, pipeline_canonical)
    career_signals = _extract_career_signals(text, pipeline_canonical)
    reading_activity = _extract_reading_activity(text, pipeline_canonical)
    behavior_opinion = _extract_behavior_opinion(text, pipeline_canonical)
    evidence_bank = _build_evidence_bank(
        page_texts=page_texts,
        section_classification=section_classification,
        pipeline_canonical=pipeline_canonical,
    )
    section_priority_map = _build_section_priority_map(
        section_classification=section_classification,
        evidence_bank=evidence_bank,
    )
    record_stage = _infer_record_stage(text)
    priority_interventions = _build_priority_interventions(
        section_priority_map=section_priority_map,
        evidence_bank=evidence_bank,
        major_alignment_hints=major_alignment_hints,
    )
    diagnostic_questions = _build_diagnostic_questions(
        section_priority_map=section_priority_map,
        evidence_bank=evidence_bank,
        record_stage=record_stage,
    )
    evidence_page_numbers = {
        page
        for item in evidence_bank
        for page in [_coerce_positive_int(item.get("page"))]
        if page is not None
    }

    confidence = round(
        min(
            0.95,
            max(
                0.35,
                0.35
                + coverage_score * 0.35
                + min(len(major_alignment_hints), 3) * 0.05
                + min(len(timeline_signals), 3) * 0.04
                + (0.08 if pipeline_canonical else 0.0)
                + (0.05 if isinstance(pdf_analysis, dict) else 0.0),
            ),
        ),
        3,
    )

    return {
        "schema_version": _CANONICAL_SCHEMA_VERSION,
        "record_type": "korean_student_record_pdf",
        "analysis_source": "pipeline" if pipeline_canonical else "heuristic",
        "document_confidence": confidence,
        "timeline_signals": timeline_signals,
        "major_alignment_hints": major_alignment_hints,
        "weak_or_missing_sections": weak_sections,
        "uncertainties": uncertainties,
        "grades_subjects": grades_subjects,
        "subject_special_notes": subject_special_notes,
        "extracurricular": extracurricular,
        "career_signals": career_signals,
        "reading_activity": reading_activity,
        "behavior_opinion": behavior_opinion,
        "evidence_bank": evidence_bank,
        "section_priority_map": section_priority_map,
        "record_stage": record_stage,
        "priority_interventions": priority_interventions,
        "diagnostic_questions": diagnostic_questions,
        "consulting_summary": _build_consulting_summary(
            confidence=confidence,
            coverage_score=coverage_score,
            record_stage=record_stage,
            section_priority_map=section_priority_map,
            evidence_bank=evidence_bank,
        ),
        "section_classification": section_classification,
        "section_coverage": section_coverage,
        "quality_gates": {
            "missing_required_sections": list(section_coverage.get("missing_required_sections", [])),
            "reanalysis_required": bool(section_coverage["reanalysis_required"]),
            "coverage_score": coverage_score,
            "required_coverage_score": float(section_coverage.get("required_coverage_score", 0.0) or 0.0),
            "evidence_anchor_count": len(evidence_bank),
            "evidence_page_count": len(evidence_page_numbers),
        },
        "page_count": parsed.page_count,
        "word_count": parsed.word_count,
        "student_profile": _extract_student_profile(text, pipeline_canonical),
        "source_pages": len(page_texts),
    }


def build_student_record_structure_metadata(
    *,
    parsed: ParsedDocumentPayload,
    pdf_analysis: dict[str, Any] | None = None,
    analysis_artifact: dict[str, Any] | None = None,
    canonical_schema: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    canonical = canonical_schema or build_student_record_canonical_metadata(
        parsed=parsed,
        pdf_analysis=pdf_analysis,
        analysis_artifact=analysis_artifact,
    )
    if not isinstance(canonical, dict):
        return None

    section_classification = canonical.get("section_classification")
    if not isinstance(section_classification, dict):
        section_classification = {}

    section_density: dict[str, float] = {}
    section_status: dict[str, str] = {}
    for canonical_key, legacy_label in _LEGACY_SECTION_LABELS.items():
        payload = section_classification.get(canonical_key)
        if not isinstance(payload, dict):
            continue
        try:
            density = max(0.0, min(1.0, float(payload.get("density") or 0.0)))
        except (TypeError, ValueError):
            density = 0.0
        section_density[legacy_label] = density
        section_status[legacy_label] = str(payload.get("status") or "missing")

    alignment_values = _extract_value_list(canonical.get("major_alignment_hints"), "hint")
    continuity_values = _extract_value_list(canonical.get("career_signals"), "label")
    process_values = _extract_value_list(canonical.get("subject_special_notes"), "label")
    strong_sections = [
        _SECTION_DISPLAY_LABELS.get(key, key)
        for key, payload in section_classification.items()
        if isinstance(payload, dict) and _coerce_float(payload.get("density"), default=0.0) >= 0.55
    ]

    return {
        "schema_version": _CANONICAL_SCHEMA_VERSION,
        "record_type": canonical.get("record_type") or "korean_student_record_pdf",
        "major_alignment": alignment_values,
        "major_sections": _dedupe(strong_sections, limit=12),
        "section_density": section_density,
        "section_status": section_status,
        "weak_sections": _extract_value_list(canonical.get("weak_or_missing_sections"), "section"),
        "timeline_signals": _extract_value_list(canonical.get("timeline_signals"), "signal"),
        "activity_clusters": _extract_value_list(canonical.get("extracurricular"), "label"),
        "alignment_signals": alignment_values,
        "subject_major_alignment_signals": alignment_values,
        "continuity_signals": continuity_values,
        "process_signals": process_values,
        "process_reflection_signals": process_values,
        "uncertain_items": _extract_value_list(canonical.get("uncertainties"), "message"),
        "coverage_check": canonical.get("section_coverage") or {},
        "contradiction_check": {"passed": True, "items": []},
        "evidence_bank": canonical.get("evidence_bank") if isinstance(canonical.get("evidence_bank"), list) else [],
        "section_priority_map": canonical.get("section_priority_map")
        if isinstance(canonical.get("section_priority_map"), list)
        else [],
        "priority_interventions": canonical.get("priority_interventions")
        if isinstance(canonical.get("priority_interventions"), list)
        else [],
        "diagnostic_questions": canonical.get("diagnostic_questions")
        if isinstance(canonical.get("diagnostic_questions"), list)
        else [],
        "record_stage": canonical.get("record_stage") or "unknown",
        "consulting_summary": canonical.get("consulting_summary") or "",
    }


def _extract_page_texts(parsed: ParsedDocumentPayload) -> list[str]:
    page_texts: list[str] = []

    metadata = parsed.metadata if isinstance(parsed.metadata, dict) else {}
    for container in (
        parsed.masked_artifact,
        metadata.get("masked_artifact"),
        parsed.analysis_artifact,
        metadata.get("analysis_artifact"),
        parsed.raw_artifact,
        metadata.get("raw_parse_artifact"),
        metadata,
    ):
        if not isinstance(container, dict):
            continue
        pages = container.get("pages") or container.get("normalized_pages")
        if not isinstance(pages, list):
            continue
        for page in pages:
            if not isinstance(page, dict):
                continue
            text = str(
                page.get("masked_text")
                or page.get("text")
                or page.get("content_text")
                or page.get("raw_text")
                or ""
            ).strip()
            if text:
                page_texts.append(text)
        if page_texts:
            return page_texts[: max(parsed.page_count, 1)]

    content = (parsed.content_text or "").strip()
    if not content:
        return []

    split_pages = [part.strip() for part in re.split(r"(?=\[Page \d+\])", content) if part.strip()]
    if split_pages:
        return split_pages[: max(parsed.page_count, 1)]
    return [content]


def _combined_text(parsed: ParsedDocumentPayload) -> str:
    return "\n".join(_extract_page_texts(parsed)) or (parsed.content_text or "")


def _build_pdf_summary(parsed: ParsedDocumentPayload, page_texts: list[str]) -> str:
    if not page_texts:
        return "PDF 텍스트를 충분히 추출하지 못해 문서 요약 근거가 제한적입니다."

    first = _clip(_normalize_sentence(page_texts[0]), 180)
    last = _clip(_normalize_sentence(page_texts[-1]), 180) if len(page_texts) > 1 else ""
    page_note = f"{parsed.page_count}페이지 문서에서 핵심 흐름을 정리했습니다."

    if last and last != first:
        return f"{page_note} 첫 페이지 요약은 {first} 마지막 페이지 요약은 {last}"
    return f"{page_note} 요약: {first}"


def _extract_key_points(page_texts: list[str]) -> list[str]:
    candidates: list[str] = []
    for text in page_texts[:_MAX_PAGE_INSIGHTS]:
        for sentence in _split_sentences(text):
            cleaned = _clip(_normalize_sentence(sentence), 180)
            if cleaned and len(cleaned) >= 20:
                candidates.append(cleaned)
            if len(candidates) >= 20:
                break
    return _dedupe(candidates, limit=_MAX_KEY_POINTS)


def _build_page_insights(page_texts: list[str]) -> list[dict[str, Any]]:
    insights: list[dict[str, Any]] = []
    for index, text in enumerate(page_texts[:_MAX_PAGE_INSIGHTS], start=1):
        summary = _clip(_normalize_sentence(text), 220)
        if summary:
            insights.append({"page_number": index, "summary": summary})
    return insights


def _build_evidence_gaps(parsed: ParsedDocumentPayload, page_texts: list[str]) -> list[str]:
    gaps: list[str] = []
    if not page_texts:
        gaps.append("텍스트를 충분히 추출하지 못해 페이지별 근거 확인이 필요합니다.")
    if parsed.needs_review:
        gaps.append("문서 품질이나 스캔 상태를 다시 확인해 추출 누락이 없는지 점검해 주세요.")
    if parsed.page_count > len(page_texts):
        gaps.append("일부 페이지에서 추출 텍스트가 비어 있어 PDF 원문 확인이 필요합니다.")
    warnings = parsed.warnings if isinstance(parsed.warnings, list) else []
    if warnings:
        gaps.append("추가 경고가 있어 표기나 문단 구조가 깨지지 않았는지 확인이 필요합니다.")
    if not gaps:
        gaps.append("학생부 주요 섹션별 근거가 충분한지 최종 검토가 필요합니다.")
    return _dedupe(gaps, limit=_MAX_EVIDENCE_GAPS)


def _looks_like_student_record(parsed: ParsedDocumentPayload, pipeline_canonical: dict[str, Any]) -> bool:
    if pipeline_canonical:
        return True
    text = _combined_text(parsed).strip() or (parsed.content_text or "").strip()
    if not text:
        return False
    hits = sum(1 for keywords in _SECTION_KEYWORDS.values() if any(keyword in text for keyword in keywords))
    return parsed.source_extension.lower() == ".pdf" and hits >= 2


def _extract_pipeline_canonical(analysis_artifact: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(analysis_artifact, dict):
        return {}
    for key in ("canonical_data", "student_record_canonical", "canonical"):
        candidate = analysis_artifact.get(key)
        if isinstance(candidate, dict):
            return candidate
    return {}


def _classify_sections(text: str) -> dict[str, dict[str, Any]]:
    section_classification: dict[str, dict[str, Any]] = {}
    lowered = text.lower()
    total_length = max(len(lowered), 1)
    for key, keywords in _SECTION_KEYWORDS.items():
        matched = [keyword for keyword in keywords if keyword.lower() in lowered]
        density = min(1.0, len(matched) / max(1, len(keywords)))
        section_classification[key] = {
            "label": _LEGACY_SECTION_LABELS.get(key, key),
            "status": "present" if matched else "missing",
            "density": round(density, 3),
            "matched_keywords": matched[:6],
            "count": len(matched),
            "char_ratio": round(sum(lowered.count(keyword.lower()) for keyword in matched) / total_length, 4),
        }
    return section_classification


def _build_section_coverage(section_classification: dict[str, dict[str, Any]]) -> dict[str, Any]:
    section_counts = {
        key: int(payload.get("count") or 0)
        for key, payload in section_classification.items()
        if isinstance(payload, dict)
    }
    missing_sections = [
        _LEGACY_SECTION_LABELS.get(key, key)
        for key, payload in section_classification.items()
        if isinstance(payload, dict) and payload.get("status") != "present"
    ]
    present_count = sum(1 for payload in section_classification.values() if payload.get("status") == "present")
    coverage_score = round(present_count / max(len(_SECTION_KEYWORDS), 1), 3)
    missing_required_sections = [
        _SECTION_DISPLAY_LABELS.get(key, _LEGACY_SECTION_LABELS.get(key, key))
        for key in _REQUIRED_STUDENT_RECORD_SECTIONS
        if (section_classification.get(key) or {}).get("status") != "present"
    ]
    required_present_count = len(_REQUIRED_STUDENT_RECORD_SECTIONS) - len(missing_required_sections)
    required_coverage_score = round(required_present_count / max(len(_REQUIRED_STUDENT_RECORD_SECTIONS), 1), 3)
    return {
        "section_counts": section_counts,
        "required_sections": [
            _SECTION_DISPLAY_LABELS.get(key, _LEGACY_SECTION_LABELS.get(key, key))
            for key in _REQUIRED_STUDENT_RECORD_SECTIONS
        ],
        "missing_required_sections": missing_required_sections,
        "missing_sections": missing_sections,
        "coverage_score": coverage_score,
        "required_coverage_score": required_coverage_score,
        "reanalysis_required": required_coverage_score < 0.5 or coverage_score < 0.45,
    }


def _extract_timeline_signals(text: str) -> list[str]:
    signals: list[str] = []
    for pattern in _TIMELINE_PATTERNS:
        signals.extend(match.group(0) for match in pattern.finditer(text))
    return _dedupe([signal.replace(" ", "") for signal in signals], limit=6)


def _extract_major_alignment_hints(text: str) -> list[str]:
    sentences = _split_sentences(text)
    hints = [
        sentence
        for sentence in sentences
        if any(keyword.lower() in sentence.lower() for keyword in _MAJOR_HINT_KEYWORDS)
    ]
    return _dedupe([_clip(sentence, 180) for sentence in hints], limit=6)


def _build_uncertainties(
    parsed: ParsedDocumentPayload,
    pdf_analysis: dict[str, Any] | None,
    section_coverage: dict[str, Any],
) -> list[str]:
    items: list[str] = []
    if parsed.needs_review:
        items.append("문서 품질 재확인이 필요합니다.")
    if isinstance(section_coverage.get("missing_sections"), list) and section_coverage["missing_sections"]:
        items.append("일부 핵심 학생부 섹션이 누락되어 추가 검토가 필요합니다.")
    if isinstance(pdf_analysis, dict):
        gaps = pdf_analysis.get("evidence_gaps")
        if isinstance(gaps, list):
            items.extend(str(item) for item in gaps[:2] if str(item).strip())
    if not items:
        items.append("현재 자동 분석 결과만으로는 세부 해석에 한계가 있어 원문 검토가 필요합니다.")
    return _dedupe(items, limit=5)


def _extract_grades_subjects(text: str, pipeline_canonical: dict[str, Any]) -> list[dict[str, Any]]:
    grades = pipeline_canonical.get("grades")
    if isinstance(grades, list) and grades:
        items: list[dict[str, Any]] = []
        for entry in grades[:8]:
            if not isinstance(entry, dict):
                continue
            subject = str(entry.get("subject") or "").strip()
            if not subject:
                continue
            items.append({"subject": subject, "label": subject})
        if items:
            return items

    subjects = re.findall(r"(국어|수학|영어|사회|역사|과학|물리|화학|생명과학|지구과학|정보|미술|음악|체육)", text)
    return [{"subject": subject, "label": subject} for subject in _dedupe(subjects, limit=8)]


def _extract_subject_special_notes(text: str, pipeline_canonical: dict[str, Any]) -> list[dict[str, Any]]:
    notes = pipeline_canonical.get("subject_special_notes")
    if isinstance(notes, dict) and notes:
        return [
            {"label": f"{subject}: {_clip(str(note), 140)}"}
            for subject, note in list(notes.items())[:8]
            if str(subject).strip() and str(note).strip()
        ]
    return [{"label": item} for item in _extract_keyword_sentences(text, _SECTION_KEYWORDS["subject_special_notes"], limit=4)]


def _extract_extracurricular(text: str, pipeline_canonical: dict[str, Any]) -> list[dict[str, Any]]:
    narratives = pipeline_canonical.get("extracurricular_narratives")
    if isinstance(narratives, dict) and narratives:
        return [
            {"label": header, "detail": _clip(str(detail), 140)}
            for header, detail in list(narratives.items())[:8]
            if str(header).strip() and str(detail).strip()
        ]
    return [{"label": item} for item in _extract_keyword_sentences(text, _SECTION_KEYWORDS["creative_activities"], limit=4)]


def _extract_career_signals(text: str, pipeline_canonical: dict[str, Any]) -> list[dict[str, Any]]:
    items = _extract_keyword_sentences(text, _CAREER_KEYWORDS, limit=4)
    if not items and pipeline_canonical.get("behavior_opinion"):
        items = [_clip(str(pipeline_canonical.get("behavior_opinion")), 160)]
    return [{"label": item} for item in items]


def _extract_reading_activity(text: str, pipeline_canonical: dict[str, Any]) -> list[dict[str, Any]]:
    reading = pipeline_canonical.get("reading_activities")
    if isinstance(reading, list) and reading:
        return [{"label": _clip(str(item), 140)} for item in reading[:6] if str(item).strip()]
    return [{"label": item} for item in _extract_keyword_sentences(text, _SECTION_KEYWORDS["reading"], limit=4)]


def _extract_behavior_opinion(text: str, pipeline_canonical: dict[str, Any]) -> list[dict[str, Any]]:
    opinion = pipeline_canonical.get("behavior_opinion")
    if isinstance(opinion, str) and opinion.strip():
        return [{"label": _clip(opinion, 160)}]
    return [{"label": item} for item in _extract_keyword_sentences(text, _SECTION_KEYWORDS["behavior_general_comments"], limit=3)]


def _extract_student_profile(text: str, pipeline_canonical: dict[str, Any]) -> dict[str, Any]:
    profile: dict[str, Any] = {}
    if isinstance(pipeline_canonical.get("student_name"), str) and pipeline_canonical["student_name"].strip():
        profile["student_name"] = pipeline_canonical["student_name"].strip()
    if isinstance(pipeline_canonical.get("school_name"), str) and pipeline_canonical["school_name"].strip():
        profile["school_name"] = pipeline_canonical["school_name"].strip()

    name_match = re.search(r"(?:학생명|성명)\s*[:：]?\s*([가-힣]{2,5})", text)
    if name_match and "student_name" not in profile:
        profile["student_name"] = name_match.group(1)

    school_match = re.search(r"([가-힣A-Za-z0-9 ]+고등학교)", text)
    if school_match and "school_name" not in profile:
        profile["school_name"] = school_match.group(1).strip()

    grade_match = re.search(r"([1-3])\s*학년", text)
    if grade_match:
        profile["latest_grade_detected"] = int(grade_match.group(1))
    return profile


def _build_evidence_bank(
    *,
    page_texts: list[str],
    section_classification: dict[str, dict[str, Any]],
    pipeline_canonical: dict[str, Any],
) -> list[dict[str, Any]]:
    canonical_bank = pipeline_canonical.get("evidence_bank")
    if isinstance(canonical_bank, list) and canonical_bank:
        normalized: list[dict[str, Any]] = []
        for index, item in enumerate(canonical_bank[:48], start=1):
            if not isinstance(item, dict):
                continue
            quote = _clip(str(item.get("quote") or item.get("text") or ""), 240)
            if not quote:
                continue
            page = _coerce_positive_int(item.get("page") or item.get("page_number")) or 1
            section = str(item.get("section") or item.get("section_label") or _infer_section_for_text(quote)).strip()
            normalized.append(
                {
                    "anchor_id": str(item.get("anchor_id") or f"canonical-{index}"),
                    "page": page,
                    "section": section or "student_record",
                    "quote": quote,
                    "theme": _infer_evidence_theme(quote),
                    "confidence": round(max(0.45, min(0.95, _coerce_float(item.get("confidence"), default=0.74))), 3),
                    "process_elements": _detect_process_elements(quote),
                }
            )
        if normalized:
            return normalized

    section_density = {
        section: max(0.0, min(1.0, _coerce_float(payload.get("density"), default=0.0)))
        for section, payload in section_classification.items()
        if isinstance(payload, dict)
    }
    bank: list[dict[str, Any]] = []
    seen_quotes: set[str] = set()
    for page_index, text in enumerate(page_texts[:36], start=1):
        candidates = _candidate_evidence_sentences(text)
        if not candidates and text.strip():
            candidates = [_clip(text, 240)]
        per_page_count = 0
        for quote in candidates:
            normalized_quote = _clip(quote, 240)
            if len(normalized_quote) < 12:
                continue
            quote_key = normalized_quote.lower()
            if quote_key in seen_quotes:
                continue
            seen_quotes.add(quote_key)
            section = _infer_section_for_text(normalized_quote)
            confidence = 0.58 + section_density.get(section, 0.18) * 0.32
            if any(keyword in normalized_quote for keyword in _EVIDENCE_KEYWORDS):
                confidence += 0.05
            bank.append(
                {
                    "anchor_id": f"p{page_index}-e{per_page_count + 1}",
                    "page": page_index,
                    "section": _SECTION_DISPLAY_LABELS.get(section, section or "student_record"),
                    "quote": normalized_quote,
                    "theme": _infer_evidence_theme(normalized_quote),
                    "confidence": round(max(0.45, min(0.92, confidence)), 3),
                    "process_elements": _detect_process_elements(normalized_quote),
                }
            )
            per_page_count += 1
            if per_page_count >= 4 or len(bank) >= 48:
                break
        if len(bank) >= 48:
            break
    return bank


def _candidate_evidence_sentences(text: str) -> list[str]:
    sentences = _split_sentences(text)
    scored: list[tuple[int, str]] = []
    for index, sentence in enumerate(sentences):
        clipped = _clip(sentence, 260)
        if len(clipped) < 16:
            continue
        score = 0
        score += 3 if any(keyword in clipped for keyword in _EVIDENCE_KEYWORDS) else 0
        score += 3 if any(keyword in clipped for keyword in _PROCESS_KEYWORDS) else 0
        score += 2 if any(keyword in clipped for keyword in _CONTINUITY_KEYWORDS) else 0
        score += 2 if any(keyword in clipped for keyword in _MAJOR_HINT_KEYWORDS) else 0
        score += 1 if any(char.isdigit() for char in clipped) else 0
        scored.append((score * 1000 - index, clipped))
    scored.sort(reverse=True)
    return _dedupe([item for _, item in scored], limit=8)


def _build_section_priority_map(
    *,
    section_classification: dict[str, dict[str, Any]],
    evidence_bank: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    evidence_by_section: dict[str, int] = {}
    for item in evidence_bank:
        section = _normalize_section_key(str(item.get("section") or ""))
        evidence_by_section[section] = evidence_by_section.get(section, 0) + 1

    rows: list[dict[str, Any]] = []
    for key, payload in section_classification.items():
        if not isinstance(payload, dict):
            continue
        density = max(0.0, min(1.0, _coerce_float(payload.get("density"), default=0.0)))
        evidence_count = evidence_by_section.get(key, 0)
        if density >= 0.6 and evidence_count >= 2:
            priority = "유지·확장"
            action = "강점 근거로 사용하되 동일 표현 반복은 줄이세요."
        elif density >= 0.35 or evidence_count >= 1:
            priority = "정밀 보강"
            action = "근거 문장을 1개 이상 추가하고 과정·한계 설명을 붙이세요."
        else:
            priority = "우선 복구"
            action = "원문 추출 상태를 확인하고 섹션별 핵심 기록을 먼저 확보하세요."
        rows.append(
            {
                "section": key,
                "label": _SECTION_DISPLAY_LABELS.get(key, key),
                "status": str(payload.get("status") or "missing"),
                "density": round(density, 3),
                "evidence_count": evidence_count,
                "priority": priority,
                "recommended_action": action,
            }
        )
    rows.sort(key=lambda item: (item["priority"] != "우선 복구", item["priority"] != "정밀 보강", -item["density"]))
    return rows


def _build_priority_interventions(
    *,
    section_priority_map: list[dict[str, Any]],
    evidence_bank: list[dict[str, Any]],
    major_alignment_hints: list[dict[str, str]],
) -> list[str]:
    weak_rows = [row for row in section_priority_map if row.get("priority") in {"우선 복구", "정밀 보강"}]
    actions: list[str] = []
    for row in weak_rows[:4]:
        actions.append(f"{row.get('label')}: {row.get('recommended_action')}")
    evidence_pages = {
        page
        for item in evidence_bank
        for page in [_coerce_positive_int(item.get("page"))]
        if page is not None
    }
    if len(evidence_pages) < 5:
        actions.append("페이지 근거가 한쪽에 몰려 있습니다. 학년·섹션이 다른 근거를 최소 5페이지 이상으로 분산하세요.")
    if not major_alignment_hints:
        actions.append("목표 전공과 직접 연결되는 교과/활동 문장을 2개 이상 표시해 전공 적합성 축을 보강하세요.")
    if not actions:
        actions.append("현재 강점 축을 유지하면서 주장마다 페이지 앵커와 과정 설명을 연결하세요.")
    return _dedupe(actions, limit=6)


def _build_diagnostic_questions(
    *,
    section_priority_map: list[dict[str, Any]],
    evidence_bank: list[dict[str, Any]],
    record_stage: str,
) -> list[str]:
    weakest = next((row for row in section_priority_map if row.get("priority") == "우선 복구"), None)
    strongest = next((row for row in reversed(section_priority_map) if row.get("priority") == "유지·확장"), None)
    questions = [
        "가장 강한 근거 1개를 목표 전공과 연결하면 어떤 역량이 증명되나요?",
        "근거 없이 좋아 보이는 표현을 제거하면 남는 핵심 사실은 무엇인가요?",
    ]
    if weakest:
        questions.append(f"{weakest.get('label')} 섹션을 보완하려면 원문에서 어떤 문장 1개를 추가 확인해야 하나요?")
    if strongest:
        questions.append(f"{strongest.get('label')}의 강점을 반복하지 않고 한 단계 심화하려면 어떤 비교/분석 근거가 필요할까요?")
    if record_stage == "finalized":
        questions.append("이미 완성된 기록 기준으로 면접에서 방어해야 할 약점 질문은 무엇인가요?")
    else:
        questions.append("아직 기록을 보완할 수 있다면 다음 학기 활동에서 어떤 관찰값을 남겨야 하나요?")
    if evidence_bank:
        questions.append(f"p.{evidence_bank[0].get('page')} 근거를 활용해 2문장 답변을 만들면 첫 문장은 무엇인가요?")
    return _dedupe(questions, limit=6)


def _build_consulting_summary(
    *,
    confidence: float,
    coverage_score: float,
    record_stage: str,
    section_priority_map: list[dict[str, Any]],
    evidence_bank: list[dict[str, Any]],
) -> str:
    priority = next((row for row in section_priority_map if row.get("priority") in {"우선 복구", "정밀 보강"}), None)
    priority_label = str(priority.get("label")) if priority else "근거 밀도"
    stage_label = "완성 기록" if record_stage == "finalized" else "보완 가능 기록" if record_stage == "ongoing" else "단계 미확인 기록"
    return (
        f"{stage_label} 기준으로 문서 신뢰도 {int(confidence * 100)}%, 섹션 커버리지 {int(coverage_score * 100)}%입니다. "
        f"우선 컨설팅 축은 {priority_label}이며, 현재 자동 확보된 근거 앵커는 {len(evidence_bank)}개입니다."
    )


def _infer_record_stage(text: str) -> str:
    if any(marker in text for marker in ("졸업", "최종", "3학년 2학기", "3-2")):
        return "finalized"
    if any(marker in text for marker in ("1학년", "2학년", "3학년 1학기", "3-1")):
        return "ongoing"
    return "unknown"


def _infer_section_for_text(text: str) -> str:
    lowered = text.lower()
    best_section = "student_record"
    best_hits = 0
    for section, keywords in _SECTION_KEYWORDS.items():
        hits = sum(1 for keyword in keywords if keyword.lower() in lowered)
        if hits > best_hits:
            best_section = section
            best_hits = hits
    return best_section


def _normalize_section_key(value: str) -> str:
    normalized = value.strip()
    for key, label in _SECTION_DISPLAY_LABELS.items():
        if normalized == key or normalized == label or label in normalized:
            return key
    return normalized


def _infer_evidence_theme(text: str) -> str:
    if any(keyword in text for keyword in _EVIDENCE_KEYWORDS):
        return "정량·관찰 근거"
    if any(keyword in text for keyword in _PROCESS_KEYWORDS):
        return "과정·성찰 근거"
    if any(keyword in text for keyword in _CONTINUITY_KEYWORDS):
        return "연속성 근거"
    if any(keyword in text for keyword in _MAJOR_HINT_KEYWORDS):
        return "전공 연계 근거"
    return "학생부 핵심 근거"


def _detect_process_elements(text: str) -> dict[str, bool]:
    return {
        "method": any(keyword in text for keyword in ("방법", "과정", "실험", "조사", "분석")),
        "result": any(keyword in text for keyword in ("결과", "변화", "성과", "확인", "도출")),
        "limitation": any(keyword in text for keyword in ("한계", "어려움", "보완", "개선", "성찰")),
    }


def _extract_keyword_sentences(text: str, keywords: tuple[str, ...], *, limit: int) -> list[str]:
    lowered_keywords = [keyword.lower() for keyword in keywords if keyword]
    candidates: list[str] = []
    for sentence in _split_sentences(text):
        lowered = sentence.lower()
        if any(keyword in lowered for keyword in lowered_keywords):
            candidates.append(_clip(sentence, 180))
    return _dedupe(candidates, limit=limit)


def _extract_value_list(value: Any, key: str) -> list[str]:
    if not isinstance(value, list):
        return []
    items: list[str] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        text = str(item.get(key) or "").strip()
        if text:
            items.append(text)
    return _dedupe(items, limit=12)


def _split_sentences(text: str) -> list[str]:
    normalized = re.sub(r"\s+", " ", text or "").strip()
    if not normalized:
        return []
    parts = re.split(r"(?<=[.!?。])\s+|(?<=다)\s+|(?<=요)\s+|\n+", normalized)
    return [part.strip() for part in parts if part.strip()]


def _normalize_sentence(text: str) -> str:
    sentence = re.sub(r"\s+", " ", text or "").strip()
    sentence = re.sub(r"^\[Page \d+\]\s*", "", sentence)
    return sentence


def _clip(text: str | None, max_len: int) -> str:
    normalized = _normalize_sentence(text or "")
    if len(normalized) <= max_len:
        return normalized
    return f"{normalized[: max_len - 3].rstrip()}..."


def _dedupe(items: list[str], *, limit: int) -> list[str]:
    deduped: list[str] = []
    seen: set[str] = set()
    for item in items:
        normalized = " ".join(str(item).split()).strip()
        if not normalized:
            continue
        key = normalized.lower()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(normalized)
        if len(deduped) >= limit:
            break
    return deduped


def _coerce_float(value: Any, *, default: float) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return default
    if parsed != parsed:
        return default
    return parsed


def _coerce_positive_int(value: Any) -> int | None:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None
