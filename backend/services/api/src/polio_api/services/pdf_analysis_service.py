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

    page_items = _extract_page_items(parsed)
    heuristic = _build_heuristic_analysis(parsed=parsed, page_items=page_items)
    model_name = _resolve_pdf_analysis_model_name()
    provider_name = (settings.pdf_analysis_llm_provider or "ollama").strip().lower()

    if not page_items:
        return {
            "provider": provider_name,
            "model": model_name,
            "engine": "fallback",
            "generated_at": _utc_iso(),
            "attempted_provider": provider_name,
            "attempted_model": model_name,
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
            "provider": provider_name,
            "model": model_name,
            "engine": "llm",
            "generated_at": _utc_iso(),
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
                "provider": provider_name,
                "model": model_name,
                "engine": "llm",
                "generated_at": _utc_iso(),
                "attempted_provider": provider_name,
                "attempted_model": model_name,
                "recovered_from_text_fallback": True,
                **normalized,
            }
        return {
            "provider": provider_name,
            "model": model_name,
            "engine": "fallback",
            "generated_at": _utc_iso(),
            "attempted_provider": provider_name,
            "attempted_model": model_name,
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


def build_student_record_structure_metadata(
    *,
    parsed: ParsedDocumentPayload,
    pdf_analysis: dict[str, Any] | None,
    analysis_artifact: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    if parsed.source_extension.lower() != ".pdf":
        return None

    page_items = _extract_page_items(parsed)
    page_count = max(parsed.page_count, len(page_items), 1)
    full_text = (parsed.content_text or "").strip()
    compact_text = re.sub(r"\s+", " ", full_text)

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
    timeline_signals = _dedupe_list(timeline_signals, limit=10)

    activity_clusters = _extract_cluster_hints(compact_text)
    alignment_signals = _extract_alignment_hints(compact_text)
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
