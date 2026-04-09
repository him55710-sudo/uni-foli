from __future__ import annotations

import asyncio
import json
import re
import threading
from collections import OrderedDict
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field

from polio_api.core.config import get_settings
from polio_api.core.llm import get_pdf_analysis_llm_client
from polio_api.core.security import sanitize_public_error
from polio_ingest.models import ParsedDocumentPayload

_MAX_PAGES_FOR_PROMPT = 8
_MAX_PAGE_TEXT_CHARS = 1400
_MAX_RAW_LLM_RESPONSE_CHARS = 16000
_PDF_ANALYSIS_FALLBACK_REASON = "LLM PDF analysis failed. Generated heuristic summary instead."
_CANONICAL_SCHEMA_VERSION = "2026-04-10"
_CANONICAL_MAX_ITEMS_PER_FIELD = 8
_CANONICAL_MAX_EVIDENCE_PER_ITEM = 3

_SECTION_KEYWORDS: dict[str, tuple[str, ...]] = {
    "grades_subjects": ("교과학습발달상황", "과목", "성취도", "등급", "평균", "grades"),
    "subject_special_notes": ("세특", "세부능력", "특기사항", "subject_special_notes"),
    "extracurricular": ("창의적 체험활동", "창체", "동아리", "봉사", "자율활동", "진로활동"),
    "career_signals": ("진로", "진학", "희망학과", "희망 전공", "목표", "career"),
    "reading_activity": ("독서", "도서", "읽은", "reading"),
    "behavior_opinion": ("행동특성", "종합의견", "인성", "태도", "behavior"),
}

_SUBJECT_KEYWORDS: tuple[str, ...] = (
    "국어",
    "수학",
    "영어",
    "한국사",
    "사회",
    "역사",
    "과학",
    "물리",
    "화학",
    "생명과학",
    "지구과학",
    "정보",
    "컴퓨터",
    "프로그래밍",
    "기하",
    "확률과 통계",
    "미적분",
    "경제",
    "정치",
    "법",
    "심리",
    "철학",
    "미술",
    "음악",
    "체육",
)


class PdfPageInsight(BaseModel):
    page_number: int = Field(ge=1, le=5000)
    summary: str = Field(min_length=1, max_length=260)


class PdfAnalysisLLMResponse(BaseModel):
    summary: str = Field(min_length=1, max_length=900)
    key_points: list[str] = Field(default_factory=list, max_length=8)
    page_insights: list[PdfPageInsight] = Field(default_factory=list, max_length=20)
    evidence_gaps: list[str] = Field(default_factory=list, max_length=8)


def build_pdf_analysis_metadata(parsed: ParsedDocumentPayload) -> dict[str, Any] | None:
    settings = get_settings()
    if not settings.pdf_analysis_llm_enabled:
        return None
    if parsed.source_extension.lower() != ".pdf":
        return None

    started_at = datetime.now(timezone.utc)
    page_items = _extract_page_items(parsed)
    heuristic = _build_heuristic_analysis(parsed=parsed, page_items=page_items)
    requested_model = _resolve_pdf_analysis_model_name()
    requested_provider = (settings.pdf_analysis_llm_provider or "ollama").strip().lower()

    def _base_metadata(
        *,
        engine: str,
        actual_provider: str,
        actual_model: str,
        fallback_used: bool,
        fallback_reason: str | None = None,
    ) -> dict[str, Any]:
        duration_ms = int(
            max(
                0.0,
                (datetime.now(timezone.utc) - started_at).total_seconds() * 1000.0,
            )
        )
        payload: dict[str, Any] = {
            "provider": actual_provider,
            "model": actual_model,
            "engine": engine,
            "pdf_analysis_engine": engine,
            "generated_at": _utc_iso(),
            "requested_pdf_analysis_provider": requested_provider,
            "requested_pdf_analysis_model": requested_model,
            "actual_pdf_analysis_provider": actual_provider,
            "actual_pdf_analysis_model": actual_model,
            "fallback_used": fallback_used,
            "processing_duration_ms": duration_ms,
        }
        if fallback_reason:
            payload["fallback_reason"] = fallback_reason
        return payload

    if not page_items:
        return {
            **_base_metadata(
                engine="fallback",
                actual_provider="heuristic",
                actual_model="heuristic",
                fallback_used=True,
                fallback_reason="No extractable PDF page text was available for LLM analysis.",
            ),
            "attempted_provider": requested_provider,
            "attempted_model": requested_model,
            "failure_reason": "No extractable PDF page text was available for LLM analysis.",
            **heuristic,
        }

    llm = None
    prompt = _build_prompt(parsed=parsed, page_items=page_items)
    try:
        llm = get_pdf_analysis_llm_client()
        llm_response = _run_async(
            llm.generate_json(
                prompt=prompt,
                response_model=PdfAnalysisLLMResponse,
                system_instruction=_pdf_analysis_system_instruction(),
                temperature=0.15,
            )
        )
        normalized = _normalize_llm_response(llm_response=llm_response, heuristic=heuristic, page_items=page_items)
        return {
            **_base_metadata(
                engine="llm",
                actual_provider=requested_provider,
                actual_model=requested_model,
                fallback_used=False,
            ),
            **normalized,
        }
    except Exception as exc:
        failure_reason = sanitize_public_error(
            str(exc),
            fallback=_PDF_ANALYSIS_FALLBACK_REASON,
            max_length=220,
        )
        recovered = _recover_structured_response_from_text(
            llm=llm,
            prompt=prompt,
            heuristic=heuristic,
            page_items=page_items,
        )
        if recovered is not None:
            normalized = _normalize_llm_response(
                llm_response=recovered,
                heuristic=heuristic,
                page_items=page_items,
            )
            return {
                **_base_metadata(
                    engine="llm",
                    actual_provider=requested_provider,
                    actual_model=requested_model,
                    fallback_used=True,
                    fallback_reason="recovered_from_text_fallback",
                ),
                "attempted_provider": requested_provider,
                "attempted_model": requested_model,
                "recovered_from_text_fallback": True,
                **normalized,
            }
        return {
            **_base_metadata(
                engine="fallback",
                actual_provider="heuristic",
                actual_model="heuristic",
                fallback_used=True,
                fallback_reason=failure_reason,
            ),
            "attempted_provider": requested_provider,
            "attempted_model": requested_model,
            "failure_reason": failure_reason,
            **heuristic,
        }


def _run_async(coro):  # noqa: ANN001
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)

    result_holder: dict[str, Any] = {}
    error_holder: list[BaseException] = []

    def _runner() -> None:
        loop = asyncio.new_event_loop()
        try:
            asyncio.set_event_loop(loop)
            result_holder["value"] = loop.run_until_complete(coro)
        except BaseException as exc:  # noqa: BLE001
            error_holder.append(exc)
        finally:
            loop.close()

    thread = threading.Thread(target=_runner, daemon=True)
    thread.start()
    thread.join()

    if error_holder:
        raise error_holder[0]
    return result_holder.get("value")


def _pdf_analysis_system_instruction() -> str:
    return (
        "역할: 학생부/업로드 PDF의 페이지별 핵심 내용을 안전하게 요약하는 분석 도우미.\n"
        "규칙:\n"
        "- 반드시 한국어 존댓말만 사용해 주세요.\n"
        "- 제공된 텍스트 근거 밖의 사실을 만들지 마세요.\n"
        "- 근거가 부족하면 evidence_gaps에 명확히 적어 주세요.\n"
        "- 출력은 반드시 지정된 JSON 스키마를 따르세요.\n"
        "- summary는 3~5문장, key_points는 최대 5개, page_insights는 페이지별 한 줄 요약으로 작성해 주세요.\n"
    )


def _build_prompt(*, parsed: ParsedDocumentPayload, page_items: list[dict[str, Any]]) -> str:
    prompt_payload = {
        "page_count": parsed.page_count,
        "word_count": parsed.word_count,
        "parser_name": parsed.parser_name,
        "warnings": parsed.warnings[:5],
        "pages": page_items[:_MAX_PAGES_FOR_PROMPT],
    }
    return (
        "[요청]\n"
        "업로드된 PDF의 페이지별 핵심과 전체 문서 흐름을 요약해 주세요.\n"
        "과장/추측 없이 근거 기반으로 작성해 주세요.\n\n"
        "[문서 데이터 JSON]\n"
        f"{json.dumps(prompt_payload, ensure_ascii=False, indent=2)}\n"
    )


def _recover_structured_response_from_text(
    *,
    llm: Any,
    prompt: str,
    heuristic: dict[str, Any],
    page_items: list[dict[str, Any]],
) -> PdfAnalysisLLMResponse | None:
    if llm is None:
        return None
    try:
        raw_response = _run_async(_request_flexible_json_response(llm=llm, prompt=prompt))
    except Exception:
        return None
    return _parse_flexible_llm_response(raw=raw_response, heuristic=heuristic, page_items=page_items)


async def _request_flexible_json_response(*, llm: Any, prompt: str) -> str:
    fallback_prompt = (
        f"{prompt}\n"
        "[출력 형식]\n"
        "반드시 JSON 객체 하나만 출력해 주세요. 마크다운/설명문은 금지입니다.\n"
        "{\n"
        '  "summary": "문서 전체 흐름 요약 (존댓말)",\n'
        '  "key_points": ["핵심 포인트1", "핵심 포인트2"],\n'
        '  "page_insights": [{"page_number": 1, "summary": "1페이지 핵심"}],\n'
        '  "evidence_gaps": ["근거 부족 항목"]\n'
        "}\n"
    )
    chunks: list[str] = []
    total_chars = 0
    async for token in llm.stream_chat(
        prompt=fallback_prompt,
        system_instruction=_pdf_analysis_system_instruction(),
        temperature=0.1,
    ):
        if token:
            chunks.append(token)
            total_chars += len(token)
            if total_chars >= _MAX_RAW_LLM_RESPONSE_CHARS:
                break
    return "".join(chunks).strip()


def _parse_flexible_llm_response(
    *,
    raw: str,
    heuristic: dict[str, Any],
    page_items: list[dict[str, Any]],
) -> PdfAnalysisLLMResponse | None:
    if not raw:
        return None

    json_candidate = _extract_json_object_candidate(raw)
    if json_candidate:
        try:
            payload = json.loads(json_candidate)
            return _coerce_payload_to_response(
                payload=payload,
                heuristic=heuristic,
                page_items=page_items,
            )
        except Exception:
            pass

    freeform_response = _coerce_freeform_text_to_response(
        raw=raw,
        heuristic=heuristic,
        page_items=page_items,
    )
    return freeform_response


def _extract_json_object_candidate(raw: str) -> str | None:
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?", "", cleaned, flags=re.IGNORECASE).strip()
        cleaned = re.sub(r"```$", "", cleaned).strip()

    try:
        json.loads(cleaned)
        return cleaned
    except Exception:
        pass

    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start == -1 or end <= start:
        return None
    candidate = cleaned[start : end + 1].strip()
    try:
        json.loads(candidate)
    except Exception:
        return None
    return candidate


def _coerce_payload_to_response(
    *,
    payload: Any,
    heuristic: dict[str, Any],
    page_items: list[dict[str, Any]],
) -> PdfAnalysisLLMResponse:
    if not isinstance(payload, dict):
        raise ValueError("LLM JSON payload must be a dictionary.")

    allowed_pages = {int(item["page_number"]) for item in page_items if isinstance(item.get("page_number"), int)}
    summary = _clean_paragraph(str(payload.get("summary") or ""), max_len=900) or heuristic["summary"]

    key_points_raw = payload.get("key_points")
    key_points: list[str] = []
    if isinstance(key_points_raw, list):
        key_points = [_clean_line(str(item), max_len=180) for item in key_points_raw if str(item).strip()]
        key_points = [item for item in key_points if item][:5]
    if not key_points:
        key_points = heuristic["key_points"]

    evidence_raw = payload.get("evidence_gaps")
    evidence_gaps: list[str] = []
    if isinstance(evidence_raw, list):
        evidence_gaps = [_clean_line(str(item), max_len=180) for item in evidence_raw if str(item).strip()]
        evidence_gaps = [item for item in evidence_gaps if item][:5]
    if not evidence_gaps:
        evidence_gaps = heuristic["evidence_gaps"]

    normalized_page_insights: list[dict[str, Any]] = []
    page_insights_raw = payload.get("page_insights")
    if isinstance(page_insights_raw, list):
        for item in page_insights_raw:
            if not isinstance(item, dict):
                continue
            page_number = item.get("page_number")
            try:
                page_number_int = int(page_number)
            except (TypeError, ValueError):
                continue
            if page_number_int not in allowed_pages:
                continue
            summary_text = _clean_line(str(item.get("summary") or ""), max_len=260)
            if not summary_text:
                continue
            normalized_page_insights.append(
                {
                    "page_number": page_number_int,
                    "summary": summary_text,
                }
            )
            if len(normalized_page_insights) >= 8:
                break
    if not normalized_page_insights:
        normalized_page_insights = heuristic["page_insights"]

    return PdfAnalysisLLMResponse(
        summary=summary,
        key_points=key_points,
        page_insights=normalized_page_insights,
        evidence_gaps=evidence_gaps,
    )


def _coerce_freeform_text_to_response(
    *,
    raw: str,
    heuristic: dict[str, Any],
    page_items: list[dict[str, Any]],
) -> PdfAnalysisLLMResponse | None:
    normalized = raw.replace("\r\n", "\n").strip()
    if not normalized:
        return None
    normalized = re.sub(r"[*_`#>\-]{2,}", " ", normalized)
    normalized = re.sub(r"[ \t]+", " ", normalized)

    paragraphs = [part.strip() for part in re.split(r"\n\s*\n", normalized) if part.strip()]
    summary = _clean_paragraph(paragraphs[0] if paragraphs else "", max_len=900) or heuristic["summary"]

    line_items = [line.strip(" -*•\t") for line in normalized.splitlines() if line.strip()]
    key_points: list[str] = []
    for line in line_items:
        if re.match(r"^\d+\.", line) or line.startswith("핵심") or line.startswith("요약"):
            cleaned = _clean_line(line, max_len=180)
            if cleaned:
                key_points.append(cleaned)
        if len(key_points) >= 5:
            break
    if not key_points:
        key_points = heuristic["key_points"]

    allowed_pages = {int(item["page_number"]) for item in page_items if isinstance(item.get("page_number"), int)}
    page_insights: list[dict[str, Any]] = []
    for line in line_items:
        match = re.search(r"(?P<page>\d{1,4})\s*페이지\s*[:：-]?\s*(?P<summary>.+)", line)
        if not match:
            continue
        page_number = int(match.group("page"))
        if page_number not in allowed_pages:
            continue
        page_summary = _clean_line(match.group("summary"), max_len=260)
        if not page_summary:
            continue
        page_insights.append({"page_number": page_number, "summary": page_summary})
        if len(page_insights) >= 8:
            break
    if not page_insights:
        page_insights = heuristic["page_insights"]

    evidence_gaps: list[str] = []
    for line in line_items:
        if any(keyword in line for keyword in ("부족", "한계", "확인 필요", "근거", "누락")):
            cleaned = _clean_line(line, max_len=180)
            if cleaned:
                evidence_gaps.append(cleaned)
        if len(evidence_gaps) >= 5:
            break
    if not evidence_gaps:
        evidence_gaps = heuristic["evidence_gaps"]

    return PdfAnalysisLLMResponse(
        summary=summary,
        key_points=key_points[:5],
        page_insights=page_insights[:8],
        evidence_gaps=evidence_gaps[:5],
    )


def _normalize_llm_response(
    *,
    llm_response: PdfAnalysisLLMResponse,
    heuristic: dict[str, Any],
    page_items: list[dict[str, Any]],
) -> dict[str, Any]:
    page_numbers = {item["page_number"] for item in page_items if isinstance(item.get("page_number"), int)}
    normalized_page_insights: list[dict[str, Any]] = []
    for item in llm_response.page_insights:
        if item.page_number not in page_numbers:
            continue
        summary = _clean_line(item.summary, max_len=260)
        if not summary:
            continue
        normalized_page_insights.append({"page_number": item.page_number, "summary": summary})
        if len(normalized_page_insights) >= 8:
            break

    if not normalized_page_insights:
        normalized_page_insights = heuristic["page_insights"]

    key_points = [_clean_line(line, max_len=180) for line in llm_response.key_points]
    key_points = [line for line in key_points if line][:5] or heuristic["key_points"]

    evidence_gaps = [_clean_line(line, max_len=180) for line in llm_response.evidence_gaps]
    evidence_gaps = [line for line in evidence_gaps if line][:5] or heuristic["evidence_gaps"]

    summary = _clean_paragraph(llm_response.summary, max_len=900) or heuristic["summary"]
    return {
        "summary": summary,
        "key_points": key_points,
        "page_insights": normalized_page_insights,
        "evidence_gaps": evidence_gaps,
    }


def _build_heuristic_analysis(*, parsed: ParsedDocumentPayload, page_items: list[dict[str, Any]]) -> dict[str, Any]:
    summary = (
        f"총 {parsed.page_count}페이지, 약 {parsed.word_count}단어가 추출되었습니다. "
        "문서 흐름은 업로드된 원문을 기준으로 정리되었으며, 확인된 텍스트 범위 안에서만 분석했습니다."
    )

    key_points = _extract_key_points(parsed.content_text)
    if not key_points:
        key_points = ["핵심 문장 추출 근거가 부족해 추가 확인이 필요합니다."]

    page_insights: list[dict[str, Any]] = []
    for item in page_items[:8]:
        snippet = _clean_line(str(item.get("snippet") or ""), max_len=220)
        if not snippet:
            snippet = "추출 텍스트가 짧아 핵심 요약 근거가 제한적입니다."
        page_insights.append({"page_number": int(item["page_number"]), "summary": snippet})

    evidence_gaps: list[str] = []
    if parsed.page_count == 0:
        evidence_gaps.append("페이지 추출 결과가 없어 문서 구조를 판단하기 어렵습니다.")
    if parsed.needs_review:
        evidence_gaps.append("일부 페이지에서 추출 신뢰도가 낮아 원문 확인이 필요합니다.")
    if parsed.warnings:
        evidence_gaps.append("파싱 경고가 있어 일부 문맥이 누락되었을 수 있습니다.")

    return {
        "summary": summary,
        "key_points": key_points[:5],
        "page_insights": page_insights,
        "evidence_gaps": evidence_gaps[:5],
    }


def _extract_page_items(parsed: ParsedDocumentPayload) -> list[dict[str, Any]]:
    pages = []
    candidates: list[dict[str, Any]] = []

    masked_pages = parsed.masked_artifact.get("pages") if isinstance(parsed.masked_artifact, dict) else None
    raw_pages = parsed.raw_artifact.get("pages") if isinstance(parsed.raw_artifact, dict) else None
    if isinstance(masked_pages, list):
        candidates.extend(item for item in masked_pages if isinstance(item, dict))
    elif isinstance(raw_pages, list):
        candidates.extend(item for item in raw_pages if isinstance(item, dict))

    for item in candidates:
        page_number = item.get("page_number")
        if not isinstance(page_number, int) or page_number <= 0:
            continue
        text = str(item.get("masked_text") or item.get("text") or "").strip()
        if not text:
            continue
        normalized_text = re.sub(r"\s+", " ", text)[:_MAX_PAGE_TEXT_CHARS].strip()
        if not normalized_text:
            continue
        pages.append(
            {
                "page_number": page_number,
                "text": normalized_text,
                "snippet": normalized_text[:180],
            }
        )
    return pages


def _extract_key_points(content_text: str) -> list[str]:
    lines = [line.strip() for line in re.split(r"[\n\.!?]", content_text) if line.strip()]
    dedup = OrderedDict()
    for line in lines:
        clean = _clean_line(line, max_len=180)
        if not clean:
            continue
        dedup.setdefault(clean, None)
        if len(dedup) >= 6:
            break
    return list(dedup.keys())[:5]


def _clean_line(value: str | None, *, max_len: int) -> str:
    if not value:
        return ""
    normalized = re.sub(r"\s+", " ", value).strip()
    if len(normalized) <= max_len:
        return normalized
    return f"{normalized[: max_len - 1].rstrip()}…"


def _clean_paragraph(value: str | None, *, max_len: int) -> str:
    if not value:
        return ""
    normalized = re.sub(r"\s+", " ", value).strip()
    if len(normalized) <= max_len:
        return normalized
    return f"{normalized[: max_len - 1].rstrip()}…"


def _resolve_pdf_analysis_model_name() -> str:
    settings = get_settings()
    provider = (settings.pdf_analysis_llm_provider or "ollama").strip().lower()
    if provider == "ollama":
        return settings.pdf_analysis_ollama_model or settings.ollama_model
    if provider == "gemini":
        return "gemini-1.5-pro"
    return provider or "unknown"


def _utc_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def build_student_record_canonical_metadata(
    *,
    parsed: ParsedDocumentPayload,
    pdf_analysis: dict[str, Any] | None,
    analysis_artifact: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    if parsed.source_extension.lower() != ".pdf":
        return None

    page_items = _extract_page_items(parsed)
    compact_text = re.sub(r"\s+", " ", (parsed.content_text or "").strip())
    pipeline_stages: list[dict[str, Any]] = []

    file_validation_ok = parsed.page_count >= 0 and parsed.word_count >= 0
    pipeline_stages.append(
        _build_stage_result(
            "file_validation",
            mode="deterministic_extraction",
            status="ok" if file_validation_ok else "failed",
            details={
                "source_extension": parsed.source_extension.lower(),
                "page_count": parsed.page_count,
                "word_count": parsed.word_count,
            },
        )
    )
    if not file_validation_ok:
        return {
            "schema_version": _CANONICAL_SCHEMA_VERSION,
            "record_type": "korean_student_record_pdf",
            "document_confidence": 0.0,
            "timeline_signals": [],
            "grades_subjects": [],
            "subject_special_notes": [],
            "extracurricular": [],
            "career_signals": [],
            "reading_activity": [],
            "behavior_opinion": [],
            "major_alignment_hints": [],
            "weak_or_missing_sections": [],
            "uncertainties": [
                {
                    "message": "문서 기본 검증 단계에서 오류가 감지되었습니다.",
                    "related_field": "file_validation",
                    "confidence_impact": 1.0,
                    "evidence": [],
                }
            ],
            "pipeline_stages": pipeline_stages,
        }

    raw_chars = sum(len(str(item.get("text") or "")) for item in page_items)
    pipeline_stages.append(
        _build_stage_result(
            "raw_text_ocr_extraction",
            mode="deterministic_extraction",
            status="ok" if raw_chars > 0 else "degraded",
            details={
                "page_items": len(page_items),
                "extracted_chars": raw_chars,
                "parser_name": parsed.parser_name,
            },
        )
    )

    masked_pages = parsed.masked_artifact.get("pages") if isinstance(parsed.masked_artifact, dict) else None
    mask_applied = bool(parsed.masking_status == "masked" or isinstance(masked_pages, list))
    pipeline_stages.append(
        _build_stage_result(
            "masking_privacy_pass",
            mode="deterministic_extraction",
            status="ok" if mask_applied else "degraded",
            details={
                "masking_status": parsed.masking_status,
                "masked_page_count": len(masked_pages) if isinstance(masked_pages, list) else 0,
                "needs_review": bool(parsed.needs_review),
            },
        )
    )

    normalized_pages = _normalize_page_items(page_items)
    pipeline_stages.append(
        _build_stage_result(
            "page_normalization",
            mode="deterministic_extraction",
            status="ok" if normalized_pages else "degraded",
            details={
                "normalized_pages": len(normalized_pages),
                "normalized_characters": sum(int(item.get("char_count") or 0) for item in normalized_pages),
            },
        )
    )

    section_classification = _classify_record_sections(normalized_pages)
    present_sections = [
        section
        for section, payload in section_classification.items()
        if payload.get("status") == "present"
    ]
    pipeline_stages.append(
        _build_stage_result(
            "section_classification",
            mode="heuristic_inference",
            status="ok" if section_classification else "degraded",
            details={
                "present_sections": present_sections,
                "classified_section_count": len(section_classification),
            },
        )
    )

    timeline_signals = _extract_timeline_signals(normalized_pages)
    grades_subjects = _extract_grade_subject_signals(normalized_pages)
    subject_special_notes = _extract_section_items(
        normalized_pages=normalized_pages,
        section_key="subject_special_notes",
        label_prefix="세특 신호",
    )
    extracurricular = _extract_section_items(
        normalized_pages=normalized_pages,
        section_key="extracurricular",
        label_prefix="창체 신호",
    )
    career_signals = _extract_section_items(
        normalized_pages=normalized_pages,
        section_key="career_signals",
        label_prefix="진로 신호",
    )
    reading_activity = _extract_section_items(
        normalized_pages=normalized_pages,
        section_key="reading_activity",
        label_prefix="독서 신호",
    )
    behavior_opinion = _extract_section_items(
        normalized_pages=normalized_pages,
        section_key="behavior_opinion",
        label_prefix="행동특성 신호",
    )
    major_alignment_hints = _extract_major_alignment_hints(normalized_pages)

    entity_count = (
        len(timeline_signals)
        + len(grades_subjects)
        + len(subject_special_notes)
        + len(extracurricular)
        + len(career_signals)
        + len(reading_activity)
        + len(behavior_opinion)
        + len(major_alignment_hints)
    )
    pipeline_stages.append(
        _build_stage_result(
            "entity_extraction",
            mode="heuristic_inference",
            status="ok" if entity_count > 0 else "degraded",
            details={
                "entity_count": entity_count,
                "timeline_signals": len(timeline_signals),
                "grades_subjects": len(grades_subjects),
                "major_alignment_hints": len(major_alignment_hints),
            },
        )
    )

    weak_or_missing_sections = _build_weak_or_missing_sections(
        section_classification=section_classification,
        normalized_pages=normalized_pages,
    )
    uncertainties = _build_canonical_uncertainties(
        parsed=parsed,
        pdf_analysis=pdf_analysis,
        section_classification=section_classification,
        weak_or_missing_sections=weak_or_missing_sections,
        normalized_pages=normalized_pages,
    )

    if isinstance(analysis_artifact, dict):
        _merge_analysis_artifact_into_canonical(
            analysis_artifact=analysis_artifact,
            normalized_pages=normalized_pages,
            grades_subjects=grades_subjects,
            subject_special_notes=subject_special_notes,
            extracurricular=extracurricular,
            reading_activity=reading_activity,
            behavior_opinion=behavior_opinion,
            uncertainties=uncertainties,
        )

    pipeline_stages.append(
        _build_stage_result(
            "canonical_student_record_schema_generation",
            mode="deterministic_extraction",
            status="ok",
            details={
                "schema_version": _CANONICAL_SCHEMA_VERSION,
                "required_field_count": 12,
            },
        )
    )

    evidence_link_count = _count_linked_evidence(
        timeline_signals=timeline_signals,
        grades_subjects=grades_subjects,
        subject_special_notes=subject_special_notes,
        extracurricular=extracurricular,
        career_signals=career_signals,
        reading_activity=reading_activity,
        behavior_opinion=behavior_opinion,
        major_alignment_hints=major_alignment_hints,
        weak_or_missing_sections=weak_or_missing_sections,
        uncertainties=uncertainties,
    )
    pipeline_stages.append(
        _build_stage_result(
            "evidence_span_linking",
            mode="deterministic_extraction",
            status="ok" if evidence_link_count > 0 else "degraded",
            details={
                "linked_evidence_count": evidence_link_count,
            },
        )
    )

    document_confidence = _compute_document_confidence(
        parsed=parsed,
        pdf_analysis=pdf_analysis,
        entity_count=entity_count,
        weak_or_missing_sections=weak_or_missing_sections,
        uncertainties=uncertainties,
        normalized_pages=normalized_pages,
    )
    pipeline_stages.append(
        _build_stage_result(
            "uncertainty_confidence_scoring",
            mode="heuristic_inference",
            status="ok",
            details={
                "document_confidence": document_confidence,
                "uncertainty_count": len(uncertainties),
            },
        )
    )

    return {
        "schema_version": _CANONICAL_SCHEMA_VERSION,
        "record_type": "korean_student_record_pdf",
        "document_confidence": document_confidence,
        "timeline_signals": timeline_signals,
        "grades_subjects": grades_subjects,
        "subject_special_notes": subject_special_notes,
        "extracurricular": extracurricular,
        "career_signals": career_signals,
        "reading_activity": reading_activity,
        "behavior_opinion": behavior_opinion,
        "major_alignment_hints": major_alignment_hints,
        "weak_or_missing_sections": weak_or_missing_sections,
        "uncertainties": uncertainties,
        "section_classification": section_classification,
        "pipeline_stages": pipeline_stages,
        "evidence_linked": evidence_link_count > 0,
    }


def _normalize_page_items(page_items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for page in page_items:
        page_number = page.get("page_number")
        text = str(page.get("text") or "").strip()
        if not isinstance(page_number, int) or page_number <= 0 or not text:
            continue
        normalized_text = re.sub(r"\s+", " ", text).strip()
        if not normalized_text:
            continue
        normalized.append(
            {
                "page_number": page_number,
                "text": normalized_text,
                "char_count": len(normalized_text),
                "snippet": normalized_text[:180],
            }
        )
    return normalized


def _build_stage_result(
    stage_name: str,
    *,
    mode: str,
    status: str,
    details: dict[str, Any],
) -> dict[str, Any]:
    return {
        "stage": stage_name,
        "mode": mode,
        "status": status,
        "details": details,
    }


def _classify_record_sections(normalized_pages: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    total_pages = max(len(normalized_pages), 1)
    classification: dict[str, dict[str, Any]] = {}
    for section, keywords in _SECTION_KEYWORDS.items():
        matches: list[dict[str, Any]] = []
        keyword_hits = 0
        for page in normalized_pages:
            text = str(page.get("text") or "")
            page_hits = [keyword for keyword in keywords if keyword.lower() in text.lower()]
            if not page_hits:
                continue
            keyword_hits += len(page_hits)
            matches.append(
                {
                    "page_number": page["page_number"],
                    "keywords": page_hits[:4],
                    "excerpt": _clean_line(text, max_len=180),
                }
            )

        density = round(min(1.0, len(matches) / total_pages), 3)
        confidence = round(min(0.98, 0.35 + (density * 0.45) + min(keyword_hits, 6) * 0.04), 3)
        if density == 0.0:
            status = "missing"
        elif density < 0.25:
            status = "weak"
        else:
            status = "present"
        classification[section] = {
            "density": density,
            "confidence": confidence,
            "status": status,
            "matches": matches[:6],
        }
    return classification


def _extract_timeline_signals(normalized_pages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    patterns = (
        re.compile(r"\b[1-3]학년\s*[12]학기\b"),
        re.compile(r"\b[1-3]학년\b"),
        re.compile(r"\b[12]학기\b"),
        re.compile(r"\b20\d{2}\b"),
    )
    entries: list[dict[str, Any]] = []
    seen: set[str] = set()
    for page in normalized_pages:
        text = str(page.get("text") or "")
        for pattern in patterns:
            for match in pattern.finditer(text):
                signal = match.group(0).strip()
                if not signal or signal in seen:
                    continue
                seen.add(signal)
                entries.append(
                    {
                        "signal": signal,
                        "confidence": 0.86,
                        "source": "deterministic_pattern",
                        "evidence": [
                            _build_evidence(
                                page_number=int(page["page_number"]),
                                text=text,
                                start=match.start(),
                                end=match.end(),
                            )
                        ],
                    }
                )
                if len(entries) >= _CANONICAL_MAX_ITEMS_PER_FIELD:
                    return entries
    return entries


def _extract_grade_subject_signals(normalized_pages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    signals: list[dict[str, Any]] = []
    seen_subjects: set[str] = set()
    for subject in _SUBJECT_KEYWORDS:
        evidence = _find_keyword_evidence(
            normalized_pages=normalized_pages,
            keyword=subject,
            limit=_CANONICAL_MAX_EVIDENCE_PER_ITEM,
        )
        if not evidence or subject in seen_subjects:
            continue
        seen_subjects.add(subject)
        signals.append(
            {
                "subject": subject,
                "confidence": round(min(0.95, 0.58 + len(evidence) * 0.12), 3),
                "source": "deterministic_keyword",
                "evidence": evidence,
            }
        )
        if len(signals) >= _CANONICAL_MAX_ITEMS_PER_FIELD:
            break
    return signals


def _extract_section_items(
    *,
    normalized_pages: list[dict[str, Any]],
    section_key: str,
    label_prefix: str,
) -> list[dict[str, Any]]:
    keywords = _SECTION_KEYWORDS.get(section_key, ())
    if not keywords:
        return []
    items: list[dict[str, Any]] = []
    seen_labels: set[str] = set()
    for keyword in keywords:
        evidence = _find_keyword_evidence(
            normalized_pages=normalized_pages,
            keyword=keyword,
            limit=_CANONICAL_MAX_EVIDENCE_PER_ITEM,
        )
        if not evidence:
            continue
        label = f"{label_prefix}:{keyword}"
        if label in seen_labels:
            continue
        seen_labels.add(label)
        items.append(
            {
                "label": label,
                "confidence": round(min(0.92, 0.55 + len(evidence) * 0.1), 3),
                "source": "deterministic_keyword",
                "evidence": evidence,
            }
        )
        if len(items) >= _CANONICAL_MAX_ITEMS_PER_FIELD:
            break
    return items


def _extract_major_alignment_hints(normalized_pages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    major_keywords = ("전공", "진로", "학과", "희망", "적합", "연계", "목표")
    action_keywords = ("탐구", "실험", "프로젝트", "활동", "보고서", "심화")
    hints: list[dict[str, Any]] = []
    seen_labels: set[str] = set()
    for page in normalized_pages:
        text = str(page.get("text") or "")
        lowered = text.lower()
        if not any(keyword.lower() in lowered for keyword in major_keywords):
            continue
        if not any(keyword.lower() in lowered for keyword in action_keywords):
            continue
        signal = _clean_line(text, max_len=180)
        if not signal or signal in seen_labels:
            continue
        seen_labels.add(signal)
        evidence = _find_keyword_evidence(
            normalized_pages=[page],
            keyword="전공" if "전공" in text else "진로" if "진로" in text else "학과",
            limit=1,
        )
        if not evidence:
            evidence = [
                _build_evidence(
                    page_number=int(page["page_number"]),
                    text=text,
                    start=0,
                    end=min(len(text), 50),
                )
            ]
        hints.append(
            {
                "hint": signal,
                "confidence": 0.72,
                "source": "heuristic_sentence_inference",
                "evidence": evidence,
            }
        )
        if len(hints) >= _CANONICAL_MAX_ITEMS_PER_FIELD:
            break
    return hints


def _build_weak_or_missing_sections(
    *,
    section_classification: dict[str, dict[str, Any]],
    normalized_pages: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    weak_sections: list[dict[str, Any]] = []
    for section, payload in section_classification.items():
        status = str(payload.get("status") or "")
        if status not in {"weak", "missing"}:
            continue
        matches = payload.get("matches") if isinstance(payload.get("matches"), list) else []
        evidence: list[dict[str, Any]] = []
        for match in matches[:_CANONICAL_MAX_EVIDENCE_PER_ITEM]:
            page_number = match.get("page_number")
            excerpt = str(match.get("excerpt") or "").strip()
            if not isinstance(page_number, int) or page_number <= 0:
                continue
            if not excerpt:
                page = next((item for item in normalized_pages if item.get("page_number") == page_number), None)
                if isinstance(page, dict):
                    excerpt = str(page.get("snippet") or "")
            evidence.append(
                {
                    "page_number": page_number,
                    "excerpt": _clean_line(excerpt, max_len=220),
                    "start_char": 0,
                    "end_char": min(len(excerpt), 220),
                }
            )
        if not evidence and normalized_pages:
            page = normalized_pages[0]
            fallback_excerpt = str(page.get("snippet") or "섹션 근거가 부족합니다.")
            evidence = [
                {
                    "page_number": int(page["page_number"]),
                    "excerpt": _clean_line(fallback_excerpt, max_len=220),
                    "start_char": 0,
                    "end_char": min(len(fallback_excerpt), 220),
                }
            ]
        weak_sections.append(
            {
                "section": section,
                "status": status,
                "density": round(float(payload.get("density") or 0.0), 3),
                "confidence": round(float(payload.get("confidence") or 0.0), 3),
                "evidence": evidence,
            }
        )
    return weak_sections[:_CANONICAL_MAX_ITEMS_PER_FIELD]


def _build_canonical_uncertainties(
    *,
    parsed: ParsedDocumentPayload,
    pdf_analysis: dict[str, Any] | None,
    section_classification: dict[str, dict[str, Any]],
    weak_or_missing_sections: list[dict[str, Any]],
    normalized_pages: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    uncertainties: list[dict[str, Any]] = []
    if parsed.needs_review:
        uncertainties.append(
            {
                "message": "파싱 결과에 수동 검토 필요 플래그가 있습니다.",
                "related_field": "document_confidence",
                "confidence_impact": 0.18,
                "evidence": _scope_evidence(normalized_pages),
            }
        )
    if parsed.parse_confidence < 0.6:
        uncertainties.append(
            {
                "message": "문서 파싱 confidence가 낮아 일부 추론은 보수적으로 해석해야 합니다.",
                "related_field": "document_confidence",
                "confidence_impact": 0.16,
                "evidence": _scope_evidence(normalized_pages),
            }
        )
    if pdf_analysis and pdf_analysis.get("engine") == "fallback":
        uncertainties.append(
            {
                "message": "PDF 분석이 LLM 실패 후 휴리스틱 fallback으로 생성되었습니다.",
                "related_field": "pdf_analysis",
                "confidence_impact": 0.12,
                "evidence": _scope_evidence(normalized_pages),
            }
        )
    for item in weak_or_missing_sections[:4]:
        section = str(item.get("section") or "").strip()
        status = str(item.get("status") or "").strip()
        if not section:
            continue
        uncertainties.append(
            {
                "message": f"{section} 섹션이 {status} 상태로 분류되었습니다.",
                "related_field": section,
                "confidence_impact": 0.08 if status == "weak" else 0.12,
                "evidence": item.get("evidence", [])[:_CANONICAL_MAX_EVIDENCE_PER_ITEM],
            }
        )
    for section, payload in section_classification.items():
        if payload.get("status") != "present":
            continue
        if float(payload.get("confidence") or 0.0) >= 0.55:
            continue
        uncertainties.append(
            {
                "message": f"{section} 분류 confidence가 낮아 추가 검증이 필요합니다.",
                "related_field": section,
                "confidence_impact": 0.06,
                "evidence": _scope_evidence(normalized_pages),
            }
        )

    deduped: list[dict[str, Any]] = []
    seen_messages: set[str] = set()
    for item in uncertainties:
        message = str(item.get("message") or "").strip()
        if not message or message in seen_messages:
            continue
        seen_messages.add(message)
        deduped.append(item)
        if len(deduped) >= _CANONICAL_MAX_ITEMS_PER_FIELD:
            break
    return deduped


def _merge_analysis_artifact_into_canonical(
    *,
    analysis_artifact: dict[str, Any],
    normalized_pages: list[dict[str, Any]],
    grades_subjects: list[dict[str, Any]],
    subject_special_notes: list[dict[str, Any]],
    extracurricular: list[dict[str, Any]],
    reading_activity: list[dict[str, Any]],
    behavior_opinion: list[dict[str, Any]],
    uncertainties: list[dict[str, Any]],
) -> None:
    canonical_data = analysis_artifact.get("canonical_data")
    if not isinstance(canonical_data, dict):
        return

    def _append_if_evidenced(
        *,
        target: list[dict[str, Any]],
        label_key: str,
        label_value: str,
        source_text: str,
        confidence: float,
    ) -> None:
        evidence = _find_keyword_evidence(
            normalized_pages=normalized_pages,
            keyword=source_text,
            limit=_CANONICAL_MAX_EVIDENCE_PER_ITEM,
        )
        if not evidence:
            evidence = _find_keyword_evidence(
                normalized_pages=normalized_pages,
                keyword=label_value,
                limit=_CANONICAL_MAX_EVIDENCE_PER_ITEM,
            )
        if not evidence:
            uncertainties.append(
                {
                    "message": f"analysis_artifact의 '{label_value}' 항목은 페이지 근거 링크를 찾지 못했습니다.",
                    "related_field": label_value,
                    "confidence_impact": 0.05,
                    "evidence": _scope_evidence(normalized_pages),
                }
            )
            return
        target.append(
            {
                label_key: label_value,
                "confidence": confidence,
                "source": "analysis_artifact_bridge",
                "evidence": evidence,
            }
        )

    for grade in canonical_data.get("grades", [])[:4]:
        if not isinstance(grade, dict):
            continue
        subject = str(grade.get("subject") or "").strip()
        if not subject:
            continue
        _append_if_evidenced(
            target=grades_subjects,
            label_key="subject",
            label_value=subject,
            source_text=subject,
            confidence=0.74,
        )

    subject_notes = canonical_data.get("subject_special_notes")
    if isinstance(subject_notes, dict):
        for subject, note in list(subject_notes.items())[:4]:
            subject_text = str(subject or "").strip()
            note_text = str(note or "").strip()
            if not subject_text and not note_text:
                continue
            _append_if_evidenced(
                target=subject_special_notes,
                label_key="label",
                label_value=f"세특:{subject_text or '미상 과목'}",
                source_text=note_text or subject_text,
                confidence=0.71,
            )

    extracurricular_map = canonical_data.get("extracurricular_narratives")
    if isinstance(extracurricular_map, dict):
        for name, narrative in list(extracurricular_map.items())[:4]:
            name_text = str(name or "").strip()
            narrative_text = str(narrative or "").strip()
            if not name_text and not narrative_text:
                continue
            _append_if_evidenced(
                target=extracurricular,
                label_key="label",
                label_value=f"창체:{name_text or '미상 영역'}",
                source_text=narrative_text or name_text,
                confidence=0.69,
            )

    for reading_item in canonical_data.get("reading_activities", [])[:4]:
        reading_text = str(reading_item or "").strip()
        if not reading_text:
            continue
        _append_if_evidenced(
            target=reading_activity,
            label_key="label",
            label_value="독서활동",
            source_text=reading_text,
            confidence=0.66,
        )

    behavior_text = str(canonical_data.get("behavior_opinion") or "").strip()
    if behavior_text:
        _append_if_evidenced(
            target=behavior_opinion,
            label_key="label",
            label_value="행동특성/종합의견",
            source_text=behavior_text,
            confidence=0.68,
        )


def _count_linked_evidence(**fields: list[dict[str, Any]]) -> int:
    linked = 0
    for items in fields.values():
        if not isinstance(items, list):
            continue
        for item in items:
            if not isinstance(item, dict):
                continue
            evidence = item.get("evidence")
            if isinstance(evidence, list):
                linked += len(evidence)
    return linked


def _compute_document_confidence(
    *,
    parsed: ParsedDocumentPayload,
    pdf_analysis: dict[str, Any] | None,
    entity_count: int,
    weak_or_missing_sections: list[dict[str, Any]],
    uncertainties: list[dict[str, Any]],
    normalized_pages: list[dict[str, Any]],
) -> float:
    base = 0.28
    base += min(0.32, max(0.0, float(parsed.parse_confidence)) * 0.32)
    base += min(0.16, len(normalized_pages) * 0.03)
    base += min(0.16, entity_count * 0.012)
    if pdf_analysis and pdf_analysis.get("engine") == "llm":
        base += 0.04
    if pdf_analysis and pdf_analysis.get("engine") == "fallback":
        base -= 0.06
    base -= min(0.2, len(weak_or_missing_sections) * 0.03)
    base -= min(0.22, len(uncertainties) * 0.035)
    if parsed.needs_review:
        base -= 0.08
    return round(max(0.05, min(0.98, base)), 3)


def _find_keyword_evidence(
    *,
    normalized_pages: list[dict[str, Any]],
    keyword: str,
    limit: int,
) -> list[dict[str, Any]]:
    normalized_keyword = str(keyword or "").strip()
    if not normalized_keyword:
        return []
    evidence: list[dict[str, Any]] = []
    seen: set[tuple[int, int]] = set()
    for page in normalized_pages:
        text = str(page.get("text") or "")
        if not text:
            continue
        lowered = text.lower()
        lowered_keyword = normalized_keyword.lower()
        start = lowered.find(lowered_keyword)
        while start != -1:
            key = (int(page["page_number"]), start)
            if key not in seen:
                seen.add(key)
                end = start + len(normalized_keyword)
                evidence.append(
                    _build_evidence(
                        page_number=int(page["page_number"]),
                        text=text,
                        start=start,
                        end=end,
                    )
                )
                if len(evidence) >= limit:
                    return evidence
            start = lowered.find(lowered_keyword, start + len(lowered_keyword))
    return evidence


def _build_evidence(*, page_number: int, text: str, start: int, end: int) -> dict[str, Any]:
    excerpt_start = max(0, start - 45)
    excerpt_end = min(len(text), end + 95)
    excerpt = _clean_line(text[excerpt_start:excerpt_end], max_len=220)
    return {
        "page_number": page_number,
        "excerpt": excerpt,
        "start_char": max(0, start),
        "end_char": min(len(text), max(end, start + 1)),
    }


def _scope_evidence(normalized_pages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    evidence: list[dict[str, Any]] = []
    for page in normalized_pages[:2]:
        snippet = str(page.get("snippet") or "").strip()
        if not snippet:
            continue
        evidence.append(
            {
                "page_number": int(page["page_number"]),
                "excerpt": _clean_line(snippet, max_len=220),
                "start_char": 0,
                "end_char": min(len(snippet), 220),
            }
        )
    return evidence


def build_student_record_structure_metadata(
    *,
    parsed: ParsedDocumentPayload,
    pdf_analysis: dict[str, Any] | None,
    analysis_artifact: dict[str, Any] | None = None,
    canonical_schema: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    if parsed.source_extension.lower() != ".pdf":
        return None

    page_items = _extract_page_items(parsed)
    page_count = max(parsed.page_count, len(page_items), 1)
    full_text = (parsed.content_text or "").strip()
    compact_text = re.sub(r"\s+", " ", full_text)
    resolved_canonical = (
        canonical_schema
        if isinstance(canonical_schema, dict)
        else build_student_record_canonical_metadata(
            parsed=parsed,
            pdf_analysis=pdf_analysis,
            analysis_artifact=analysis_artifact,
        )
    )
    canonical_section_density = _legacy_section_density_from_canonical(resolved_canonical)

    section_keywords: dict[str, tuple[str, ...]] = {
        "세특": ("세부능력", "특기사항", "교과학습발달상황", "subject_special_notes"),
        "창체": ("창의적 체험활동", "동아리", "봉사", "자율활동", "extracurricular"),
        "진로": ("진로", "진학", "희망학과", "career"),
        "행동특성": ("행동특성", "종합의견", "behavior"),
        "교과학습발달상황": ("교과학습발달상황", "성취도", "과목", "grades"),
        "독서": ("독서", "reading"),
    }

    section_hits: dict[str, int] = {}
    for section, keywords in section_keywords.items():
        hits = 0
        for page in page_items:
            text = str(page.get("text") or "").lower()
            if any(keyword.lower() in text for keyword in keywords):
                hits += 1
        if hits == 0 and compact_text:
            lowered = compact_text.lower()
            if any(keyword.lower() in lowered for keyword in keywords):
                hits = 1
        section_hits[section] = hits

    max_hits = max(section_hits.values()) if section_hits else 1
    section_density = {
        key: round(min(1.0, (value / max_hits) if max_hits else 0.0), 3)
        for key, value in section_hits.items()
    }
    for section, density in canonical_section_density.items():
        section_density[section] = max(section_density.get(section, 0.0), density)

    weak_sections = [
        section
        for section, density in section_density.items()
        if density <= 0.2
    ]

    timeline_patterns = (
        r"\b[1-3]학년\b",
        r"\b[12]학기\b",
        r"\b20\d{2}\b",
    )
    timeline_signals = []
    for pattern in timeline_patterns:
        for match in re.findall(pattern, compact_text):
            timeline_signals.append(str(match))
    timeline_signals.extend(_extract_canonical_string_values(resolved_canonical, "timeline_signals", "signal"))
    timeline_signals = _dedupe_list(timeline_signals, limit=10)

    activity_clusters = _extract_cluster_hints(compact_text)
    alignment_signals = _extract_alignment_hints(compact_text)
    alignment_signals.extend(_extract_canonical_string_values(resolved_canonical, "major_alignment_hints", "hint"))
    continuity_signals = _extract_keyword_sentences(
        compact_text,
        keywords=("심화", "확장", "후속", "비교", "연계", "지속"),
        limit=5,
    )
    process_reflection_signals = _extract_keyword_sentences(
        compact_text,
        keywords=("과정", "방법", "한계", "개선", "성찰", "피드백"),
        limit=5,
    )

    uncertain_items: list[str] = []
    if parsed.needs_review:
        uncertain_items.append("파싱 품질 경고가 있어 일부 섹션 분류 정확도가 낮을 수 있습니다.")
    if page_count <= 1:
        uncertain_items.append("페이지 수가 매우 적어 학기/연속성 추정의 신뢰도가 낮습니다.")
    if not compact_text:
        uncertain_items.append("추출 텍스트가 부족해 구조 추정이 제한되었습니다.")
    if pdf_analysis and pdf_analysis.get("engine") == "fallback":
        uncertain_items.append("PDF 요약이 heuristic fallback으로 생성되었습니다.")

    if isinstance(resolved_canonical, dict):
        weak_sections.extend(_extract_canonical_string_values(resolved_canonical, "weak_or_missing_sections", "section"))
        uncertain_items.extend(_extract_canonical_string_values(resolved_canonical, "uncertainties", "message"))

    if isinstance(analysis_artifact, dict):
        canonical_data = analysis_artifact.get("canonical_data")
        if isinstance(canonical_data, dict):
            if canonical_data.get("grades"):
                section_density["교과학습발달상황"] = max(section_density.get("교과학습발달상황", 0.0), 0.7)
            if canonical_data.get("extracurricular_narratives"):
                section_density["창체"] = max(section_density.get("창체", 0.0), 0.6)
            if canonical_data.get("reading_activities"):
                section_density["독서"] = max(section_density.get("독서", 0.0), 0.5)
            if canonical_data.get("behavior_opinion"):
                section_density["행동특성"] = max(section_density.get("행동특성", 0.0), 0.5)

        quality_report = analysis_artifact.get("quality_report")
        if isinstance(quality_report, dict):
            missing_sections = quality_report.get("missing_critical_sections")
            if isinstance(missing_sections, list):
                for item in missing_sections:
                    text = str(item).strip()
                    if text:
                        weak_sections.append(text)
            score = quality_report.get("overall_score")
            if isinstance(score, (int, float)) and float(score) < 0.6:
                uncertain_items.append("고급 파이프라인 품질 점수가 낮아 수동 검토가 권장됩니다.")

    return {
        "major_sections": [
            {
                "section": key,
                "density": value,
                "confidence": "high" if value >= 0.6 else "medium" if value >= 0.3 else "low",
            }
            for key, value in section_density.items()
        ],
        "section_density": section_density,
        "timeline_signals": timeline_signals,
        "activity_clusters": activity_clusters,
        "subject_major_alignment_signals": alignment_signals,
        "weak_sections": _dedupe_list(weak_sections, limit=10),
        "continuity_signals": continuity_signals,
        "process_reflection_signals": process_reflection_signals,
        "uncertain_items": _dedupe_list(uncertain_items, limit=8),
    }


def _legacy_section_density_from_canonical(canonical_schema: dict[str, Any] | None) -> dict[str, float]:
    if not isinstance(canonical_schema, dict):
        return {}
    section_classification = canonical_schema.get("section_classification")
    if not isinstance(section_classification, dict):
        return {}

    legacy_map = {
        "subject_special_notes": "세특",
        "extracurricular": "창체",
        "career_signals": "진로",
        "behavior_opinion": "행동특성",
        "grades_subjects": "교과학습발달상황",
        "reading_activity": "독서",
    }
    density: dict[str, float] = {}
    for canonical_key, legacy_key in legacy_map.items():
        payload = section_classification.get(canonical_key)
        if not isinstance(payload, dict):
            continue
        try:
            score = max(0.0, min(1.0, float(payload.get("density") or 0.0)))
        except (TypeError, ValueError):
            continue
        density[legacy_key] = max(density.get(legacy_key, 0.0), round(score, 3))
    return density


def _extract_canonical_string_values(
    canonical_schema: dict[str, Any] | None,
    field: str,
    key: str,
) -> list[str]:
    if not isinstance(canonical_schema, dict):
        return []
    raw_values = canonical_schema.get(field)
    if not isinstance(raw_values, list):
        return []
    values: list[str] = []
    for item in raw_values:
        if isinstance(item, dict):
            value = str(item.get(key) or "").strip()
            if value:
                values.append(value)
    return values


def _extract_cluster_hints(text: str) -> list[str]:
    cluster_keywords: dict[str, tuple[str, ...]] = {
        "탐구/실험": ("탐구", "실험", "가설", "검증"),
        "데이터 분석": ("데이터", "통계", "분석", "지표"),
        "프로젝트/제안": ("프로젝트", "설계", "제안", "기획"),
        "공동체/리더십": ("협업", "리더", "봉사", "공동체"),
    }
    found: list[str] = []
    lowered = text.lower()
    for label, keywords in cluster_keywords.items():
        if any(keyword.lower() in lowered for keyword in keywords):
            found.append(label)
    return _dedupe_list(found, limit=6)


def _extract_alignment_hints(text: str) -> list[str]:
    patterns = (
        "전공",
        "진로",
        "학과",
        "관심 분야",
        "희망",
        "적합",
        "연계",
    )
    hints = _extract_keyword_sentences(text, keywords=patterns, limit=6)
    if not hints:
        return ["전공 연계 문장 신호가 제한적입니다. 핵심 과목과 목표 전공 연결을 문장으로 보강하세요."]
    return hints


def _extract_keyword_sentences(text: str, *, keywords: tuple[str, ...], limit: int) -> list[str]:
    if not text:
        return []
    sentences = re.split(r"(?<=[.!?。])\s+|\n+", text)
    collected: list[str] = []
    for sentence in sentences:
        normalized = sentence.strip()
        if len(normalized) < 8:
            continue
        lowered = normalized.lower()
        if any(keyword.lower() in lowered for keyword in keywords):
            collected.append(normalized[:180])
        if len(collected) >= limit:
            break
    return _dedupe_list(collected, limit=limit)


def _dedupe_list(items: list[str], *, limit: int) -> list[str]:
    seen: set[str] = set()
    output: list[str] = []
    for raw in items:
        normalized = str(raw or "").strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        output.append(normalized)
        if len(output) >= limit:
            break
    return output
