from __future__ import annotations

import json
from typing import Any, AsyncIterator

from unifoli_api.core.config import get_settings
from unifoli_api.core.llm import LLMRuntimeResolution, get_llm_client, get_llm_temperature, resolve_llm_runtime

from unifoli_api.services.quality_control import (
    build_quality_control_metadata,
    get_quality_profile,
    resolve_advanced_features,
)
from unifoli_api.services.llm_cache_service import CacheRequest, fetch_cached_response, store_cached_response
from unifoli_api.services.prompt_registry import get_prompt_registry
from unifoli_api.services.rag_service import (
    RAGConfig,
    RAGContext,
    build_rag_context,
    build_rag_injection_prompt,
    extract_query_keywords,
)
from unifoli_api.services.search_provider_service import normalize_grounding_source_type
from unifoli_api.services.safety_guard import SafetyFlag, run_safety_check
from unifoli_api.services.visual_support_service import build_visual_support_plan
from unifoli_domain.enums import QualityLevel

_QUALITY_GUARDRAIL_PROMPTS: dict[str, str] = {
    QualityLevel.LOW.value: "system.guardrails.render-quality-low",
    QualityLevel.MID.value: "system.guardrails.render-quality-mid",
    QualityLevel.HIGH.value: "system.guardrails.render-quality-high",
}



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




def _supports_live_generation(resolution: LLMRuntimeResolution | None = None) -> bool:
    resolved = resolution or resolve_llm_runtime(profile="render", concern="render")
    return resolved.client is not None


def _current_model_name(resolution: LLMRuntimeResolution | None = None) -> str:
    resolved = resolution or resolve_llm_runtime(profile="render", concern="render")
    return resolved.actual_model or resolved.attempted_model or "deterministic-render"


def _clip(text: str, *, length: int = 2000) -> str:
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
        parts.append(f"[{role}] 학생: {_clip(getattr(turn, 'query', '') or '', length=2000)}")
    return "\n".join(parts)


def _serialize_references(references: list[Any]) -> str:
    if not references:
        return "(참고자료 없음)"
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
    guardrail = _build_quality_guardrail(profile.level)
    base_instruction = _build_render_base_instruction()
    advanced_output_spec = """
  "visual_specs": [
    {
      "type": "chart",
      "chart_spec": {
        "title": "차트 제목",
        "type": "bar",
        "data": [{"name": "항목", "value": 1}]
      }
    }
  ],
  "math_expressions": [
    {
      "label": "수식 설명",
      "latex": "y = mx + b",
      "context": "본문에서 수식이 실제로 필요한 경우에만 포함"
    }
  ],"""
    if not advanced_mode:
        advanced_output_spec = """
  "visual_specs": [],
  "math_expressions": [],"""

    rag_section = f"\n{rag_injection}\n" if rag_injection else ""
    advanced_mode_label = "활성" if advanced_mode else "비활성"
    advanced_rules = [
        "- 차트와 수식은 실제 근거가 있고 설명 가치가 있을 때만 추가합니다.",
        "- 필요하지 않으면 visual_specs와 math_expressions는 빈 배열로 둡니다.",
    ] if advanced_mode else []
    scholarly_rules = [
        "- In advanced mode, structure report_markdown like a concise academic report: research question, background/literature lens, student evidence, analysis, limitations, and next research step.",
        "- Use EXTERNAL_RESEARCH only for theory, comparisons, trends, or recommendation rationale; never use it as proof of what the student did.",
        "- Include a short '검증할 참고문헌 후보' subsection only when external research context is provided, and mark unverified bibliographic details as '출처 확인 필요'.",
        "- Prefer depth over brevity: produce enough Korean body text for the student to keep writing, while staying inside the evidence boundary.",
    ] if advanced_mode else []

    rule_lines = [
        "- 대한민국 대학 입학사정관의 시각에서 학생의 지적 호기심과 전공 탐구 역량이 돋보이도록 작성하세요.",
        "- teacher_record_summary_500은 학교생활기록부 기재 요령에 맞춰 '...함', '...임'과 같은 명조체/개조식 문체를 사용하세요.",
        "- 학생이 말하지 않은 경험, 수치, 실험 결과, 인터뷰, 논문 사실을 새로 만들지 마세요.",
        "- 근거가 부족한 내용은 단정하지 말고 '추가 확인 필요'처럼 보수적으로 처리하세요.",
        "- 학생 발화와 참고자료 해석을 섞지 말고 출처를 evidence_map에 남기세요.",
        "- JSON 외의 설명 텍스트는 출력하지 마세요.",
        *advanced_rules,
        *scholarly_rules,
    ]
    rendered_rules = "\n".join(rule_lines)

    return f"""
{base_instruction}

[현재 품질 프로필]
- 레벨: {profile.label} ({profile.level})
- 학생 적합 기준: {profile.student_fit}
- 안전 우선순위: {profile.safety_posture}
- 진정성 규칙: {profile.authenticity_policy}
- 과장 방지 가드레일: {profile.hallucination_guardrail}
- 렌더 깊이: {profile.render_depth}
- 표현 원칙: {profile.expression_policy}
- 참고자료 강도: {profile.reference_intensity}
- 고급 모드: {advanced_mode_label}

[학생 목표]
- 목표 대학: {target_university or '미정'}
- 목표 전공: {target_major or '미정'}

[학생이 직접 말한 워크숍 맥락]
{turns_text}

[참고자료]
{references_text}
{rag_section}
{guardrail}

[반드시 지킬 규칙]
{rendered_rules}

[출력 JSON]
{{
  "report_markdown": "## 탐구 보고서\\n\\n학생 맥락에 맞는 본문",
  "teacher_record_summary_500": "교사가 기록에 반영할 수 있는 500자 이내 요약",
  "student_submission_note": "학생 제출 전 확인 메모",
  "evidence_map": {{
    "주장 1": {{"근거": "워크숍 또는 참고자료 근거", "출처": "turn:... 또는 reference:..."}}
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
    point_lines = [f"- {text}" for text, _ in points] or ["- 학생 워크숍 대화에서 확인 가능한 맥락을 더 모을 필요가 있습니다."]
    reference_lines = [
        f"- {_clip(getattr(reference, 'text_content', '') or '', length=110)}"
        for reference in references[:2]
    ] or ["- 현재 고정된 참고자료가 없습니다."]
    evidence_map = {
        f"주장 {index}": {"근거": text, "출처": source}
        for index, (text, source) in enumerate(points, start=1)
    }
    if not evidence_map:
        evidence_map["주장 1"] = {"근거": "워크숍 맥락 추가 확보 필요", "출처": "turn:none"}

    intro = f"{target_major or '희망 전공'} 맥락에서 이번 탐구의 방향을 정리합니다."
    verification_line = summary_note or "확인되지 않은 인용, 수치, 출처는 반드시 다시 점검하고 필요 시 추가 확인 필요로 표시합니다."

    if profile.level == QualityLevel.LOW.value:
        report_markdown = "\n".join(
            [
                "## 탐구 보고서",
                "",
                "### 1. 탐구 방향",
                intro,
                "",
                "### 2. 실제 확인된 맥락",
                *point_lines,
                "",
                "### 3. 다음 학기 실천",
                "- 교과 개념과 직접 연결되는 활동만 남깁니다.",
                "- 학생이 직접 설명 가능한 과정만 기록합니다.",
                "",
                "### 4. 확인 메모",
                f"- {verification_line}",
            ]
        )
        teacher_summary = (
            f"{target_major or '관심 전공'} 관련 탐구를 교과 개념 중심으로 정리했고, "
            f"{' '.join(text for text, _ in points[:2]) or '현재 확인된 탐구 맥락'}을 바탕으로 "
            "학생이 실제로 설명 가능한 수준의 안전한 기록 방향을 제안합니다."
        )
    elif profile.level == QualityLevel.HIGH.value:
        report_markdown = "\n".join(
            [
                "## 탐구 보고서",
                "",
                "### 1. 과제 맥락 기반 심화 질문",
                intro,
                "",
                "### 2. 학생이 직접 말한 핵심 맥락",
                *point_lines,
                "",
                "### 3. 참고자료 연결 해석",
                *reference_lines,
                "",
                "### 4. 과장 방지 메모",
                f"- {verification_line}",
                "- 학생 발화와 참고자료 해석을 분리해서 기록합니다.",
            ]
        )
        teacher_summary = (
            f"{target_major or '희망 전공'}과 연결되는 탐구를 학생 발화와 참고자료 근거로 나누어 정리했습니다. "
            f"{' '.join(text for text, _ in points[:2]) or '워크숍 맥락'}을 중심으로 "
            "학생 수준에 맞는 심화 표현만 허용하고 과장 가능성은 줄였습니다."
        )
    else:
        report_markdown = "\n".join(
            [
                "## 탐구 보고서",
                "",
                "### 1. 탐구 질문",
                intro,
                "",
                "### 2. 확보한 근거",
                *point_lines,
                "",
                "### 3. 간단한 해석과 다음 단계",
                "- 교과 내용 범위 안에서 비교와 해석을 시도합니다.",
                "- 결론은 과장하지 않고 관찰 가능한 범위에서 정리합니다.",
                "",
                "### 4. 확인 메모",
                f"- {verification_line}",
            ]
        )
        teacher_summary = (
            f"{target_major or '관심 전공'} 관련 탐구를 교과 내용 수준으로 구체화했고 "
            f"{' '.join(text for text, _ in points[:2]) or '학생이 제시한 탐구 방향'}을 바탕으로 "
            "무리 없는 기록 흐름과 다음 단계를 제시합니다."
        )

    note_lines = [
        "- 확인되지 않은 활동, 수치, 출처는 반드시 다시 확인하거나 '추가 확인 필요'로 표시하세요.",
        f"- 현재 품질 레벨은 {profile.label}이며 참고자료 활용 강도는 {profile.reference_intensity}입니다.",
        f"- 과장 방지 가드레일: {profile.hallucination_guardrail}",
        "- 교사가 보기에도 학생이 직접 수행한 활동처럼 보이는지 최종 확인하세요.",
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


async def _generate_with_llm(
    *,
    prompt: str,
    quality_level: str,
    resolution: LLMRuntimeResolution | None = None,
) -> AsyncIterator[str]:
    profile = get_quality_profile(quality_level)
    llm = resolution.client if resolution and resolution.client is not None else get_llm_client(profile="render", concern="render")
    system_instruction = _build_render_system_instruction(quality_level=profile.level)
    async for token in llm.stream_chat(
        prompt=prompt,
        system_instruction=system_instruction,
        temperature=max(
            profile.temperature,
            get_llm_temperature(profile="render", concern="render", resolution=resolution),
        ),
    ):
        yield token


async def stream_render(
    db: Session,
    session_id: str,
    project_id: str,
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
    advanced_reference_count = len(references)
    if rag_config and rag_config.enabled and not rag_config.pin_required:
        advanced_reference_count = max(advanced_reference_count, 1)
    effective_advanced_mode, advanced_reason = resolve_advanced_features(
        requested=requested_advanced_mode,
        quality_level=profile.level,
        reference_count=advanced_reference_count,
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
            db,
            project_id=project_id,
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
    settings = get_settings()
    render_resolution = resolve_llm_runtime(profile="render", concern="render")
    cache_request = CacheRequest(
        feature_name="workshop_render.stream_render",
        model_name=_current_model_name(render_resolution),
        scope_key=f"project:{project_id}",
        config_version=settings.llm_cache_version,
        ttl_seconds=settings.llm_cache_ttl_seconds if settings.llm_cache_enabled else 0,
        bypass=not settings.llm_cache_enabled,
        response_format="text",
        evidence_keys=[
            *(f"turn:{getattr(turn, 'id', '')}" for turn in turns),
            *(f"reference:{getattr(reference, 'id', '')}" for reference in references),
            *((rag_context.evidence_keys if rag_context else [])),
        ],
        payload={
            "prompt": prompt,
            "quality_level": profile.level,
            "advanced_mode_requested": requested_advanced_mode,
            "advanced_mode": effective_advanced_mode,
        },
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
            "message": f"[{profile.label}]{' 심화' if effective_advanced_mode else ''} 안전 중심 렌더링을 시작합니다.",
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
    used_fallback = not _supports_live_generation(render_resolution)
    cached_text = fetch_cached_response(db, cache_request)
    if cached_text:
        full_text = cached_text
        used_fallback = False

    if not full_text and _supports_live_generation(render_resolution):
        try:
            chunk_count = 0
            async for token in _generate_with_llm(
                prompt=prompt,
                quality_level=profile.level,
                resolution=render_resolution,
            ):
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
                "message": "실시간 생성이 어려워 안전 초안으로 구성했습니다.",
            },
        )

    if full_text:
        store_cached_response(db, cache_request, response_payload=full_text)

    if buffer:
        yield _sse_line(SSEEvent.DRAFT_DELTA, {"delta": buffer})
    elif cached_text:
        for start in range(0, len(full_text), 240):
            yield _sse_line(SSEEvent.DRAFT_DELTA, {"delta": full_text[start : start + 240]})

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

    planned_visual_support = build_visual_support_plan(
        report_markdown=str(parsed.get("report_markdown", "") or ""),
        evidence_map=parsed.get("evidence_map") or {},
        student_submission_note=str(parsed.get("student_submission_note", "") or ""),
        turns=turns,
        references=references,
        advanced_mode=effective_advanced_mode and not repair_applied,
        target_major=target_major,
    )
    parsed["visual_specs"] = planned_visual_support.get("visual_specs", [])
    parsed["math_expressions"] = planned_visual_support.get("math_expressions", [])

    advanced_features_applied = bool(parsed.get("visual_specs") or parsed.get("math_expressions"))
    if requested_advanced_mode and repair_applied:
        advanced_reason = "안전 재작성 과정에서 고급 확장 요소를 줄이고 학생 맥락 중심 결과로 돌렸습니다."
    elif requested_advanced_mode and used_fallback and not advanced_features_applied:
        advanced_reason = "안전 결정에 따라 렌더링 중 고급 확장 요소를 적용하지 않았습니다."
    elif requested_advanced_mode and effective_advanced_mode and not advanced_features_applied:
        advanced_reason = "고급 확장을 요청했지만 현재 맥락에서는 텍스트 기반 결과가 더 안전해 차트/수식은 생략했습니다."

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


def _build_render_base_instruction() -> str:
    return get_prompt_registry().compose_prompt("drafting.report-render")


def _build_render_system_instruction(*, quality_level: str) -> str:
    profile = get_quality_profile(quality_level)
    return (
        f"{get_prompt_registry().compose_prompt('drafting.provenance-boundary')}\n\n"
        f"Current quality level: {profile.label} ({profile.level}). "
        "Return only valid JSON that matches the requested artifact contract."
    )


def _build_quality_guardrail(quality_level: str) -> str:
    prompt_name = _QUALITY_GUARDRAIL_PROMPTS.get(
        quality_level,
        _QUALITY_GUARDRAIL_PROMPTS[QualityLevel.MID.value],
    )
    return get_prompt_registry().compose_prompt(prompt_name)
