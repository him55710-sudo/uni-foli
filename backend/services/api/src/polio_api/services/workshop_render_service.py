from __future__ import annotations

import json
import os
from typing import Any, AsyncIterator

import google.generativeai as genai

from polio_api.services.quality_control import (
    build_quality_control_metadata,
    get_quality_profile,
    resolve_advanced_features,
)
from polio_api.services.rag_service import (
    RAGConfig,
    RAGContext,
    build_rag_context,
    build_rag_injection_prompt,
    extract_query_keywords,
)
from polio_api.services.safety_guard import SafetyFlag, run_safety_check
from polio_domain.enums import QualityLevel

genai.configure(api_key=os.environ.get("GEMINI_API_KEY", "DUMMY_KEY"))


class SSEEvent:
    SESSION_READY = "session.ready"
    CONTEXT_UPDATED = "context.updated"
    SUGGESTIONS_UPDATED = "suggestions.updated"
    DRAFT_DELTA = "draft.delta"
    DRAFT_COMPLETED = "draft.completed"
    RENDER_STARTED = "render.started"
    RENDER_PROGRESS = "render.progress"
    RENDER_COMPLETED = "render.completed"
    ARTIFACT_READY = "artifact.ready"
    SAFETY_CHECKED = "safety.checked"
    ERROR = "error"


def _sse_line(event: str, data: dict[str, Any]) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


_GUARDRAILS: dict[str, str] = {
    QualityLevel.LOW.value: """
[안전형 가드레일]
- 교과 개념과 학생이 실제로 한 활동만 사용한다.
- 없는 실험, 없는 수치, 없는 인터뷰를 절대 만들지 않는다.
- 심화 이론이나 화려한 표현보다 정확성과 수행 가능성을 우선한다.
- 근거가 부족하면 '추가 확인 필요'처럼 보수적으로 쓴다.
""",
    QualityLevel.MID.value: """
[표준형 가드레일]
- 교과 응용은 허용하되 고교 학생이 직접 설명 가능한 범위를 넘지 않는다.
- 결론은 약하게, 근거는 구체적으로 쓴다.
- 학생이 실제로 하지 않은 행동은 결과가 아니라 계획 또는 확인 필요 사항으로 돌린다.
- 참고자료는 필요할 때만 정확한 출처와 함께 쓴다.
""",
    QualityLevel.HIGH.value: """
[심화형 가드레일]
- 심화 개념은 학생이 실제로 말한 맥락과 참고자료가 있을 때만 사용한다.
- 핵심 주장마다 근거 또는 출처를 붙인다.
- 학생 경험, 해석, 외부 지식을 반드시 분리한다.
- 근거가 빈약하면 더 안전한 수준으로 자동 교체된다.
""",
}


def _supports_live_generation() -> bool:
    api_key = os.environ.get("GEMINI_API_KEY")
    return bool(api_key and api_key != "DUMMY_KEY")


def _clip(text: str, *, length: int = 160) -> str:
    normalized = " ".join((text or "").split())
    if len(normalized) <= length:
        return normalized
    return f"{normalized[:length].rstrip()}..."


def _turn_display_text(turn: Any) -> str:
    if getattr(turn, "action_payload", None) and isinstance(turn.action_payload, dict):
        display_label = turn.action_payload.get("display_label")
        if display_label:
            return str(display_label)
    return _clip(getattr(turn, "query", "") or "", length=140)


def _serialize_turns(turns: list[Any]) -> str:
    if not turns:
        return "(대화 기록 없음)"
    parts: list[str] = []
    for turn in turns:
        role = {"starter": "선택(시작)", "follow_up": "선택(후속)", "message": "직접 입력"}.get(
            getattr(turn, "turn_type", ""),
            getattr(turn, "turn_type", "message"),
        )
        parts.append(f"[{role}] 학생: {_clip(getattr(turn, 'query', '') or '', length=220)}")
    return "\n".join(parts)


def _serialize_references(references: list[Any]) -> str:
    if not references:
        return "(핀된 참고자료 없음)"
    return "\n".join(
        f"- [{getattr(reference, 'source_type', 'reference')}] {_clip(getattr(reference, 'text_content', '') or '', length=260)}"
        for reference in references
    )


def _grounded_points(turns: list[Any], references: list[Any], *, limit: int = 4) -> list[tuple[str, str]]:
    points: list[tuple[str, str]] = []
    seen: set[str] = set()
    for turn in turns:
        text = _turn_display_text(turn)
        key = text.lower()
        if key in seen or not text:
            continue
        seen.add(key)
        points.append((text, f"turn:{getattr(turn, 'id', '')}"))
        if len(points) >= limit:
            return points
    for reference in references:
        text = _clip(getattr(reference, "text_content", "") or "", length=120)
        key = text.lower()
        if key in seen or not text:
            continue
        seen.add(key)
        points.append((text, f"reference:{getattr(reference, 'id', '')}"))
        if len(points) >= limit:
            return points
    return points


def _build_render_prompt(
    *,
    turns_text: str,
    references_text: str,
    target_major: str | None,
    target_university: str | None,
    quality_level: str,
    advanced_mode: bool = False,
    rag_injection: str = "",
) -> str:
    profile = get_quality_profile(quality_level)
    guardrail = _GUARDRAILS[profile.level]

    # 심화 모드 확장 출력 스펙
    advanced_output_spec = ""
    if advanced_mode:
        advanced_output_spec = """
  "visual_specs": [
    {
      "type": "chart",
      "chart_spec": {
        "title": "차트 제목",
        "type": "bar 또는 line",
        "data": [{"name": "항목", "value": 숫자}]
      }
    }
  ],
  "math_expressions": [
    {
      "label": "수식 설명",
      "latex": "LaTeX 수식 문자열",
      "context": "이 수식이 사용되는 맥락"
    }
  ],"""

    rag_section = ""
    if rag_injection:
        rag_section = f"\n{rag_injection}\n"

    return f"""
당신은 대한민국 고등학생 기록용 탐구 보고서를 작성하는 도우미입니다.
목표는 최고의 글이 아니라, 학생에게 가장 적합하고 가장 안전한 결과를 만드는 것입니다.

[현재 품질 수준]
- 수준: {profile.label} ({profile.level})
- 학생 적합성 기준: {profile.student_fit}
- 안전 우선도: {profile.safety_posture}
- 실제성 규칙: {profile.authenticity_policy}
- 허위 경험 가드레일: {profile.hallucination_guardrail}
- 렌더 깊이: {profile.render_depth}
- 표현 원칙: {profile.expression_policy}
- 참고자료 강도: {profile.reference_intensity}
- 심화 모드: {'활성' if advanced_mode else '비활성'}

[학생 목표]
- 목표 대학: {target_university or '미정'}
- 목표 전공: {target_major or '미정'}

[학생이 실제로 말한 워크샵 맥락]
{turns_text}

[핀된 참고자료]
{references_text}
{rag_section}
{guardrail}

[반드시 지킬 규칙]
- 위 맥락에 없는 경험, 수치, 실험 결과, 인터뷰, 논문 읽은 사실을 절대 생성하지 마라.
- 근거가 부족한 내용은 완료된 활동처럼 쓰지 말고 '추가 확인 필요' 또는 '추가로 살펴볼 점'으로 처리하라.
- 학생이 실제로 한 것과 외부 자료 해석을 섞지 마라.
- JSON 외의 텍스트를 출력하지 마라.
{'- 심화 모드에서는 데이터 시각화(chart_spec)와 수식(math_expressions)을 가능한 경우에만 추가하라.' if advanced_mode else ''}
{'- 차트/수식이 필요 없으면 빈 배열로 두라.' if advanced_mode else ''}

[출력 JSON]
{{
  "report_markdown": "## 탐구 보고서\\n\\n학생 수준과 실제 맥락에 맞는 본문",
  "teacher_record_summary_500": "교사가 기록에 반영할 수 있는 500자 이내 요약",
  "student_submission_note": "학생 제출 전 점검 메모",
  "evidence_map": {{
    "주장 1": {{"근거": "워크샵 대화 또는 참고자료", "출처": "turn:... 또는 reference:..."}}
  }},{advanced_output_spec}
}}
""".strip()


def _build_safe_artifact(
    *,
    turns: list[Any],
    references: list[Any],
    target_major: str | None,
    target_university: str | None,
    quality_level: str,
    summary_note: str | None = None,
) -> dict[str, Any]:
    profile = get_quality_profile(quality_level)
    points = _grounded_points(turns, references)
    point_lines = [f"- {text}" for text, _ in points] or ["- 학생이 워크샵에서 제공한 맥락을 더 모을 필요가 있습니다."]
    reference_lines = [
        f"- {_clip(getattr(reference, 'text_content', '') or '', length=110)}"
        for reference in references[:2]
    ] or ["- 현재 고정된 참고자료가 없습니다."]
    evidence_map = {
        f"주장 {index}": {"근거": text, "출처": source}
        for index, (text, source) in enumerate(points, start=1)
    }
    if not evidence_map:
        evidence_map["주장 1"] = {"근거": "워크샵 맥락 추가 필요", "출처": "turn:none"}

    intro = f"{target_major or '희망 전공'} 맥락에서 이번 탐구를 정리합니다."
    verification_line = summary_note or "실제로 확인한 내용만 남기고, 확인되지 않은 내용은 계획 또는 추가 확인 항목으로 둡니다."

    if profile.level == QualityLevel.LOW.value:
        report_markdown = "\n".join(
            [
                "## 탐구 보고서",
                "",
                "### 1. 탐구 방향",
                intro,
                "",
                "### 2. 실제로 확인된 맥락",
                *point_lines,
                "",
                "### 3. 이번 학기 안에 가능한 수행",
                "- 교과 개념과 직접 연결되는 활동만 남깁니다.",
                "- 학생이 직접 설명 가능한 과정만 기록합니다.",
                "",
                "### 4. 점검 메모",
                f"- {verification_line}",
            ]
        )
        teacher_summary = (
            f"{target_major or '관심 전공'} 관련 탐구를 교과 개념 중심으로 정리하며, "
            f"워크샵에서 확인된 활동과 표현만 남겨 학생 수준에 맞는 안전한 기록 방향을 설계함. "
            f"{' '.join(text for text, _ in points[:2]) or '탐구 맥락을 추가 확인하는 태도'}를 바탕으로 과장 없는 세특 문장 구성이 가능함."
        )
    elif profile.level == QualityLevel.HIGH.value:
        report_markdown = "\n".join(
            [
                "## 탐구 보고서",
                "",
                "### 1. 실제 맥락 기반 심화 질문",
                intro,
                "",
                "### 2. 학생이 직접 말한 핵심 맥락",
                *point_lines,
                "",
                "### 3. 참고자료와 연결한 해석",
                *reference_lines,
                "",
                "### 4. 과장 방지 메모",
                f"- {verification_line}",
                "- 학생이 실제로 한 것과 외부 자료 해석을 분리해서 기록합니다.",
            ]
        )
        teacher_summary = (
            f"{target_major or '희망 전공'}와 연결되는 탐구를 실제 수행 맥락과 참고자료로 구분해 정리하며, "
            f"학생이 직접 한 활동과 해석의 경계를 명확히 세움. "
            f"{' '.join(text for text, _ in points[:2]) or '워크샵 맥락'}을 중심으로 심화형 표현을 학생 수준에 맞게 통제함."
        )
    else:
        report_markdown = "\n".join(
            [
                "## 탐구 보고서",
                "",
                "### 1. 탐구 질문",
                intro,
                "",
                "### 2. 확보된 근거",
                *point_lines,
                "",
                "### 3. 간단한 해석과 다음 단계",
                "- 교과 응용 범위에서 비교와 해석을 시도합니다.",
                "- 결론은 과장하지 않고 관찰 가능한 범위에서만 정리합니다.",
                "",
                "### 4. 점검 메모",
                f"- {verification_line}",
            ]
        )
        teacher_summary = (
            f"{target_major or '관심 전공'} 관련 탐구를 교과 응용 수준으로 구체화하며, "
            f"워크샵에서 확보된 근거를 바탕으로 간단한 해석과 다음 단계를 설계함. "
            f"{' '.join(text for text, _ in points[:2]) or '학생이 제시한 탐구 방향'}을 중심으로 실제 수행 가능한 기록 흐름을 만듦."
        )

    note_lines = [
        "- 실제로 하지 않은 활동, 수치, 출처는 반드시 삭제하거나 '추가 확인 필요'로 수정하세요.",
        f"- 현재 품질 수준은 {profile.label}이며, 참고자료 사용 강도는 {profile.reference_intensity}입니다.",
        f"- 허위 경험 가드레일: {profile.hallucination_guardrail}",
        "- 교사가 읽었을 때 학생이 직접 한 활동으로 보이는지 최종 확인하세요.",
    ]
    if target_university:
        note_lines.append(f"- 목표 대학({target_university}) 맞춤 표현보다 실제 수행 사실을 우선하세요.")

    return {
        "report_markdown": report_markdown.strip(),
        "teacher_record_summary_500": _clip(teacher_summary, length=500),
        "student_submission_note": "\n".join(note_lines),
        "evidence_map": evidence_map,
        "visual_specs": [],
        "math_expressions": [],
    }


def _serialize_checks(checks: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        key: {
            "key": value.key,
            "label": value.label,
            "score": value.score,
            "status": value.status,
            "detail": value.detail,
            "matched_count": value.matched_count,
            "unsupported_count": value.unsupported_count,
        }
        for key, value in checks.items()
    }


async def _generate_with_gemini(
    *,
    prompt: str,
    quality_level: str,
) -> AsyncIterator[str]:
    profile = get_quality_profile(quality_level)
    model = genai.GenerativeModel(
        model_name="gemini-1.5-pro",
        system_instruction=(
            f"너는 학생 탐구 보고서 생성기다. 현재 수준은 {profile.label}이다. "
            "허위 경험, 과장된 수치, 근거 없는 실험 결과를 절대 만들지 말고, 유효한 JSON만 출력하라."
        ),
    )
    response_stream = await model.generate_content_async(
        contents=prompt,
        stream=True,
        generation_config=genai.GenerationConfig(
            temperature=profile.temperature,
            response_mime_type="application/json",
        ),
    )
    async for chunk in response_stream:
        token = getattr(chunk, "text", None)
        if token:
            yield token


async def stream_render(
    session_id: str,
    turns: list[Any],
    references: list[Any],
    target_major: str | None,
    target_university: str | None,
    artifact_id: str,
    quality_level: str = QualityLevel.MID.value,
    advanced_mode: bool = False,
    rag_config: RAGConfig | None = None,
) -> AsyncIterator[str]:
    profile = get_quality_profile(quality_level)
    turns_text = _serialize_turns(turns)
    references_text = _serialize_references(references)
    requested_advanced_mode = advanced_mode
    effective_advanced_mode, advanced_reason = resolve_advanced_features(
        requested=requested_advanced_mode,
        quality_level=profile.level,
        reference_count=len(references),
    )

    # 심화 모드 RAG 컨텍스트 빌드
    rag_injection = ""
    rag_context: RAGContext | None = None
    if effective_advanced_mode and rag_config and rag_config.enabled:
        keywords = extract_query_keywords(
            target_major=target_major,
            turns=turns,
        )
        rag_context = await build_rag_context(
            query_keywords=keywords,
            pinned_references=references,
            config=rag_config,
        )
        rag_injection = build_rag_injection_prompt(rag_context)

    prompt = _build_render_prompt(
        turns_text=turns_text,
        references_text=references_text,
        target_major=target_major,
        target_university=target_university,
        quality_level=profile.level,
        advanced_mode=effective_advanced_mode,
        rag_injection=rag_injection,
    )

    yield _sse_line(
        SSEEvent.RENDER_STARTED,
        {
            "artifact_id": artifact_id,
            "session_id": session_id,
            "quality_level": profile.level,
            "quality_label": profile.label,
            "advanced_mode_requested": requested_advanced_mode,
            "advanced_mode": effective_advanced_mode,
            "advanced_reason": advanced_reason,
            "rag_enhanced": bool(rag_context and rag_context.is_enhanced),
            "message": f"[{profile.label}]{' 🔬심화' if effective_advanced_mode else ''} 안전 중심 렌더링을 시작합니다.",
        },
    )
    yield _sse_line(
        SSEEvent.CONTEXT_UPDATED,
        {
            "turn_count": len(turns),
            "reference_count": len(references),
            "quality_level": profile.level,
            "advanced_mode_requested": requested_advanced_mode,
            "advanced_mode": effective_advanced_mode,
            "rag_papers_count": len(rag_context.papers) if rag_context else 0,
        },
    )

    full_text = ""
    buffer = ""
    used_fallback = not _supports_live_generation()

    if _supports_live_generation():
        try:
            chunk_count = 0
            async for token in _generate_with_gemini(prompt=prompt, quality_level=profile.level):
                full_text += token
                buffer += token
                chunk_count += 1
                if len(buffer) >= 240:
                    yield _sse_line(SSEEvent.DRAFT_DELTA, {"delta": buffer})
                    buffer = ""
                if chunk_count % 24 == 0:
                    yield _sse_line(
                        SSEEvent.RENDER_PROGRESS,
                        {
                            "chars_generated": len(full_text),
                            "message": f"{len(full_text)}자 생성 중입니다.",
                        },
                    )
        except Exception:
            used_fallback = True

    if used_fallback:
        fallback_artifact = _build_safe_artifact(
            turns=turns,
            references=references,
            target_major=target_major,
            target_university=target_university,
            quality_level=profile.level,
        )
        full_text = json.dumps(fallback_artifact, ensure_ascii=False)
        yield _sse_line(
            SSEEvent.RENDER_PROGRESS,
            {
                "chars_generated": len(full_text),
                "message": "외부 생성기 없이 안전 초안을 구성했습니다.",
            },
        )

    if buffer:
        yield _sse_line(SSEEvent.DRAFT_DELTA, {"delta": buffer})

    yield _sse_line(SSEEvent.DRAFT_COMPLETED, {"total_chars": len(full_text)})

    parsed = _parse_artifact(full_text)
    safety = run_safety_check(
        report_markdown=parsed.get("report_markdown", ""),
        teacher_summary=parsed.get("teacher_record_summary_500", ""),
        requested_level=profile.level,
        turn_count=len(turns),
        reference_count=len(references),
        turns_text=turns_text,
        references_text=references_text,
    )

    repair_applied = False
    repair_strategy: str | None = None
    critical_flags = {
        SafetyFlag.FABRICATION_RISK.value,
        SafetyFlag.FEASIBILITY_RISK.value,
        SafetyFlag.LEVEL_OVERFLOW.value,
    }
    if safety.downgraded or any(flag in critical_flags for flag in safety.flags):
        repair_applied = True
        repair_strategy = "deterministic_safe_rewrite"
        repaired_level = safety.recommended_level
        parsed = _build_safe_artifact(
            turns=turns,
            references=references,
            target_major=target_major,
            target_university=target_university,
            quality_level=repaired_level,
            summary_note=safety.summary,
        )
        safety = run_safety_check(
            report_markdown=parsed.get("report_markdown", ""),
            teacher_summary=parsed.get("teacher_record_summary_500", ""),
            requested_level=repaired_level,
            turn_count=len(turns),
            reference_count=len(references),
            turns_text=turns_text,
            references_text=references_text,
        )

    advanced_features_applied = bool(parsed.get("visual_specs") or parsed.get("math_expressions"))
    if requested_advanced_mode and repair_applied:
        advanced_reason = "안전 재작성 과정에서 고급 확장을 제거하고 학생 수준 중심 결과로 되돌렸습니다."
    elif requested_advanced_mode and used_fallback and not advanced_features_applied:
        advanced_reason = "안전형 결정적 렌더를 사용해 고급 확장을 적용하지 않았습니다."
    elif requested_advanced_mode and effective_advanced_mode and not advanced_features_applied:
        advanced_reason = "고급 확장을 요청했지만 현재 맥락에서는 텍스트 기반 결과가 더 안전해 차트/수식을 생략했습니다."

    checks_payload = _serialize_checks(safety.checks)
    yield _sse_line(
        SSEEvent.SAFETY_CHECKED,
        {
            "safety_score": safety.safety_score,
            "flags": safety.flags,
            "recommended_level": safety.recommended_level,
            "downgraded": safety.downgraded,
            "summary": safety.summary,
            "checks": checks_payload,
        },
    )

    quality_control = build_quality_control_metadata(
        requested_level=profile.level,
        applied_level=safety.recommended_level,
        turn_count=len(turns),
        reference_count=len(references),
        safety_score=safety.safety_score,
        downgraded=safety.downgraded,
        summary=safety.summary,
        flags=safety.flags,
        checks=checks_payload,
        repair_applied=repair_applied or used_fallback,
        repair_strategy=repair_strategy or ("direct_safe_render" if used_fallback else None),
        advanced_features_requested=requested_advanced_mode,
        advanced_features_applied=advanced_features_applied,
        advanced_features_reason=advanced_reason,
    )

    artifact_payload = {
        "artifact_id": artifact_id,
        **parsed,
        "safety": {
            "score": safety.safety_score,
            "flags": safety.flags,
            "recommended_level": safety.recommended_level,
            "downgraded": safety.downgraded,
            "summary": safety.summary,
            "quality_level_applied": safety.recommended_level,
            "checks": checks_payload,
        },
        "quality_control": quality_control,
    }

    yield _sse_line(SSEEvent.ARTIFACT_READY, artifact_payload)
    yield _sse_line(
        SSEEvent.RENDER_COMPLETED,
        {
            "artifact_id": artifact_id,
            "status": "completed",
            "quality_level": safety.recommended_level,
            "safety_score": safety.safety_score,
        },
    )


def _parse_artifact(raw: str) -> dict[str, Any]:
    try:
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            lines = [line for line in cleaned.split("\n") if not line.startswith("```")]
            cleaned = "\n".join(lines).strip()
        parsed = json.loads(cleaned)
        return {
            "report_markdown": parsed.get("report_markdown", ""),
            "teacher_record_summary_500": parsed.get("teacher_record_summary_500", ""),
            "student_submission_note": parsed.get("student_submission_note", ""),
            "evidence_map": parsed.get("evidence_map", {}),
            "visual_specs": parsed.get("visual_specs", []),
            "math_expressions": parsed.get("math_expressions", []),
        }
    except Exception:
        return {
            "report_markdown": raw,
            "teacher_record_summary_500": "",
            "student_submission_note": "",
            "evidence_map": {},
            "visual_specs": [],
            "math_expressions": [],
        }
