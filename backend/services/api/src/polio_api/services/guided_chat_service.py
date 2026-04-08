from __future__ import annotations

import json
from typing import Iterable

from sqlalchemy.orm import Session

from polio_api.core.llm import LLMRequestError, get_llm_client, get_llm_temperature
from polio_api.db.models.user import User
from polio_api.schemas.guided_chat import (
    GuidedChatStartResponse,
    GuidedChatStatePayload,
    OutlineSection,
    PageRangeOption,
    TopicSelectionResponse,
    TopicSuggestion,
    TopicSuggestionResponse,
)
from polio_api.services.guided_chat_context_service import GuidedChatContext, build_guided_chat_context
from polio_api.services.guided_chat_state_service import load_guided_chat_state, save_guided_chat_state
from polio_api.services.prompt_registry import get_prompt_registry

GUIDED_CHAT_GREETING = "안녕하세요. 어떤 주제의 보고서를 써볼까요?"
LIMITED_CONTEXT_NOTE = "현재 확인 가능한 학생 맥락이 제한되어 보수적으로 제안드립니다."


def start_guided_chat(*, db: Session, user: User, project_id: str | None) -> GuidedChatStartResponse:
    context = build_guided_chat_context(db=db, user=user, project_id=project_id)
    saved_state = load_guided_chat_state(db, context.project_id) if context.project_id else None
    state_summary = _build_state_summary(
        context=context,
        subject=saved_state.subject if saved_state else None,
        selected_topic_id=saved_state.selected_topic_id if saved_state else None,
        suggestions=saved_state.suggestions if saved_state else [],
        outline=saved_state.recommended_outline if saved_state else [],
        starter_draft_markdown=saved_state.starter_draft_markdown if saved_state else None,
    )
    return GuidedChatStartResponse(
        greeting=GUIDED_CHAT_GREETING,
        project_id=context.project_id,
        evidence_gap_note=_evidence_gap_note(context),
        limited_mode=bool(context.evidence_gaps),
        limited_reason="evidence_gap" if context.evidence_gaps else None,
        state_summary=state_summary,
    )


async def generate_topic_suggestions(
    *,
    db: Session,
    user: User,
    project_id: str | None,
    subject: str,
) -> TopicSuggestionResponse:
    normalized_subject = _normalize_subject(subject)
    context = build_guided_chat_context(db=db, user=user, project_id=project_id)
    llm_response, limited_reason = await _try_llm_topic_suggestions(subject=normalized_subject, context=context)

    normalized = _normalize_suggestions(
        suggestions=llm_response.suggestions if llm_response else [],
        subject=normalized_subject,
        context=context,
    )
    summary = _build_state_summary(
        context=context,
        subject=normalized_subject,
        selected_topic_id=None,
        suggestions=normalized,
        outline=[],
        starter_draft_markdown=None,
    )
    limited_mode = bool(context.evidence_gaps or limited_reason)

    response = TopicSuggestionResponse(
        greeting=GUIDED_CHAT_GREETING,
        subject=normalized_subject,
        suggestions=normalized,
        evidence_gap_note=_evidence_gap_note(context) or (llm_response.evidence_gap_note if llm_response else None),
        limited_mode=limited_mode,
        limited_reason=limited_reason or ("evidence_gap" if context.evidence_gaps else None),
        state_summary=summary,
    )

    if context.project_id:
        save_guided_chat_state(
            db,
            context.project_id,
            GuidedChatStatePayload(
                subject=response.subject,
                suggestions=response.suggestions,
                selected_topic_id=None,
                recommended_page_ranges=[],
                recommended_outline=[],
                starter_draft_markdown=None,
                state_summary=summary,
                limited_mode=response.limited_mode,
                limited_reason=response.limited_reason,
            ),
        )

    return response


def select_topic(
    *,
    db: Session,
    user: User,
    project_id: str | None,
    selected_topic_id: str,
    subject: str | None,
    suggestions: list[TopicSuggestion],
) -> TopicSelectionResponse:
    context = build_guided_chat_context(db=db, user=user, project_id=project_id)
    normalized_subject = _normalize_subject(subject or "탐구")
    current_suggestions = suggestions
    if not current_suggestions and context.project_id:
        saved = load_guided_chat_state(db, context.project_id)
        if saved is not None:
            current_suggestions = saved.suggestions
            if saved.subject:
                normalized_subject = _normalize_subject(saved.subject)

    normalized = _normalize_suggestions(
        suggestions=current_suggestions,
        subject=normalized_subject,
        context=context,
    )
    selected = next((item for item in normalized if item.id == selected_topic_id), normalized[0])

    page_ranges = _build_page_ranges(context=context)
    outline = _build_outline(context=context, selected=selected)
    starter_draft = _build_starter_markdown(
        subject=normalized_subject,
        selected=selected,
        outline=outline,
        context=context,
    )

    guidance_parts = [f"선택 주제는 '{selected.title}' 입니다."]
    if context.known_target_info.get("target_major"):
        guidance_parts.append(
            f"목표 전공 '{context.known_target_info['target_major']}'과 연결되는 흐름을 중심으로 구조화했습니다."
        )
    if context.evidence_gaps:
        guidance_parts.append("근거가 부족한 지점은 '추가 확인 필요'로 표기해 안전하게 확장하세요.")
    guidance_message = " ".join(guidance_parts)

    summary = _build_state_summary(
        context=context,
        subject=normalized_subject,
        selected_topic_id=selected.id,
        suggestions=normalized,
        outline=outline,
        starter_draft_markdown=starter_draft,
    )

    response = TopicSelectionResponse(
        selected_topic_id=selected.id,
        selected_title=selected.title,
        recommended_page_ranges=page_ranges,
        recommended_outline=outline,
        starter_draft_markdown=starter_draft,
        guidance_message=guidance_message,
        limited_mode=bool(context.evidence_gaps),
        limited_reason="evidence_gap" if context.evidence_gaps else None,
        state_summary=summary,
    )

    if context.project_id:
        save_guided_chat_state(
            db,
            context.project_id,
            GuidedChatStatePayload(
                subject=normalized_subject,
                suggestions=normalized,
                selected_topic_id=response.selected_topic_id,
                recommended_page_ranges=response.recommended_page_ranges,
                recommended_outline=response.recommended_outline,
                starter_draft_markdown=response.starter_draft_markdown,
                state_summary=summary,
                limited_mode=response.limited_mode,
                limited_reason=response.limited_reason,
            ),
        )
    return response


async def _try_llm_topic_suggestions(
    *,
    subject: str,
    context: GuidedChatContext,
) -> tuple[TopicSuggestionResponse | None, str | None]:
    try:
        llm = get_llm_client(profile="fast")
    except TypeError:
        # Backward compatibility for tests monkeypatching get_llm_client() without kwargs.
        llm = get_llm_client()  # type: ignore[call-arg]
    prompt = _build_topic_prompt(subject=subject, context=context)
    system_instruction = get_prompt_registry().compose_prompt("chat.guided-report-topic-orchestration")
    try:
        response = await llm.generate_json(
            prompt=prompt,
            response_model=TopicSuggestionResponse,
            system_instruction=system_instruction,
            temperature=get_llm_temperature(profile="fast"),
        )
        return response, None
    except LLMRequestError as exc:
        return None, exc.limited_reason
    except Exception:
        return None, "llm_unavailable"


def _build_topic_prompt(*, subject: str, context: GuidedChatContext) -> str:
    compact_payload = {
        "target": {
            "university": context.known_target_info.get("target_university"),
            "major": context.known_target_info.get("target_major"),
        },
        "diagnosis_summary": context.diagnosis_summary,
        "record_flow_summary": _clip_line(context.record_flow_summary, "기록 요약 없음"),
        "prior_topics": context.prior_topics[:3],
        "evidence_gaps": context.evidence_gaps[:5],
        "history": context.workshop_history[-4:],
        "discussion": context.project_discussion_log[-3:],
    }
    return (
        f"[입력 과목/주제]\n{subject}\n\n"
        "[압축 컨텍스트 JSON]\n"
        f"{json.dumps(compact_payload, ensure_ascii=False)}\n\n"
        "[요청]\n"
        "- TopicSuggestionResponse JSON만 출력하세요.\n"
        "- 정확히 3개의 서로 다른 주제를 제시하세요.\n"
        "- 학생 기록 근거가 약하면 보수적으로 제안하고 evidence_gap_note를 작성하세요.\n"
        "- 과장/합격보장 표현을 금지하세요.\n"
    )


def _normalize_suggestions(
    *,
    suggestions: Iterable[TopicSuggestion],
    subject: str,
    context: GuidedChatContext,
) -> list[TopicSuggestion]:
    normalized: list[TopicSuggestion] = []
    seen_titles: set[str] = set()

    for index, item in enumerate(suggestions):
        title = _clip_line(item.title, f"{subject} 기반 탐구 주제 {index + 1}")
        title_key = title.strip().lower()
        if title_key in seen_titles:
            continue
        seen_titles.add(title_key)

        normalized.append(
            TopicSuggestion(
                id=item.id or f"topic-{len(normalized) + 1}",
                title=title,
                why_fit_student=_clip_line(item.why_fit_student, _fallback_fit_message(context, subject)),
                link_to_record_flow=_clip_line(item.link_to_record_flow, _fallback_record_link(context)),
                link_to_target_major_or_university=_normalize_optional_text(
                    item.link_to_target_major_or_university or _fallback_target_link(context)
                ),
                novelty_point=_clip_line(item.novelty_point, _fallback_novelty_message(subject, len(normalized) + 1)),
                caution_note=_normalize_optional_text(item.caution_note or _fallback_caution(context)),
            )
        )
        if len(normalized) == 3:
            break

    if len(normalized) < 3:
        normalized.extend(_build_fallback_topics(subject=subject, context=context, existing=normalized))
    return normalized[:3]


def _build_fallback_topics(
    *,
    subject: str,
    context: GuidedChatContext,
    existing: list[TopicSuggestion],
) -> list[TopicSuggestion]:
    existing_titles = {item.title for item in existing}
    base_title = subject.strip() or "탐구"
    target_hint = context.known_target_info.get("target_major") or context.known_target_info.get("target_university")
    record_hint = context.record_flow_summary or "현재 학생부 근거가 제한적입니다."

    candidates = [
        (
            f"{base_title} 개념을 기존 활동 맥락과 연결하는 탐구 보고서",
            "기존 활동 맥락을 다시 설명해 기록 연속성을 높이는 방향입니다.",
            "추가 사실 가정 없이 확인된 활동 중심으로 확장합니다.",
        ),
        (
            f"{base_title} 관찰 결과 비교를 통한 근거 보강 보고서",
            "비교/검토 단계를 넣어 근거 밀도를 높이는 보수적 구조입니다.",
            "결론보다 과정 중심으로 구성해 과장 위험을 낮춥니다.",
        ),
        (
            f"{base_title} 후속 질문 중심의 심화 탐구 계획 보고서",
            "지금 확정 가능한 내용과 추가 검증이 필요한 내용을 분리합니다.",
            "실행 가능한 다음 질문을 명시해 실제 작성으로 이어집니다.",
        ),
    ]

    if target_hint:
        candidates[2] = (
            f"{target_hint} 연계형 {base_title} 탐구 보고서",
            "목표 진로와 연결되는 탐구 목적을 명시하되 과장 없이 작성합니다.",
            "진로 연결성을 보여주되 확인된 사실 범위를 넘지 않습니다.",
        )

    result: list[TopicSuggestion] = []
    next_index = len(existing) + 1
    for title, fit, novelty in candidates:
        if title in existing_titles:
            continue
        result.append(
            TopicSuggestion(
                id=f"topic-{next_index}",
                title=title,
                why_fit_student=fit,
                link_to_record_flow=f"기록 연결 근거: {_clip_line(record_hint, '현재 기록 근거가 제한적입니다.')}",
                link_to_target_major_or_university=_fallback_target_link(context),
                novelty_point=novelty,
                caution_note=_fallback_caution(context),
            )
        )
        next_index += 1
        if len(existing) + len(result) >= 3:
            break
    return result


def _build_page_ranges(*, context: GuidedChatContext) -> list[PageRangeOption]:
    limited = bool(context.evidence_gaps)
    return [
        PageRangeOption(
            label="핵심형",
            min_pages=3,
            max_pages=4,
            why_this_length="핵심 근거와 질문을 빠르게 정리할 때 적합합니다.",
        ),
        PageRangeOption(
            label="표준형",
            min_pages=4,
            max_pages=5,
            why_this_length="배경-근거-해석-후속계획을 균형 있게 담기 좋습니다.",
        ),
        PageRangeOption(
            label="심화형" if not limited else "안전 심화형",
            min_pages=5 if not limited else 4,
            max_pages=6 if not limited else 5,
            why_this_length=(
                "비교/검증 단계를 포함한 심화 서술에 적합합니다."
                if not limited
                else "근거 부족 구간을 명시적으로 분리해 안전하게 심화합니다."
            ),
        ),
    ]


def _build_outline(*, context: GuidedChatContext, selected: TopicSuggestion) -> list[OutlineSection]:
    outline = [
        OutlineSection(title="1. 주제 선정 배경", purpose="왜 이 주제가 현재 학생 맥락에 적합한지 설명합니다."),
        OutlineSection(title="2. 중심 질문과 탐구 목적", purpose="한 문장 중심 질문을 제시하고 보고서 목표를 명확히 합니다."),
        OutlineSection(title="3. 확인 가능한 근거", purpose="학생부/문서에서 확인 가능한 사실만 정리합니다."),
        OutlineSection(title="4. 분석과 해석", purpose="근거 기반 해석과 주장 경계를 구분해 작성합니다."),
        OutlineSection(title="5. 추가 검증 계획", purpose="추가 확인이 필요한 항목과 보강 계획을 적습니다."),
    ]
    if context.known_target_info.get("target_major") or context.known_target_info.get("target_university"):
        outline.insert(
            4,
            OutlineSection(title="4-2. 진로/전공 연결", purpose="목표 방향과 연결되는 학습 의도를 사실 기반으로 제시합니다."),
        )
    return outline


def _build_starter_markdown(
    *,
    subject: str,
    selected: TopicSuggestion,
    outline: list[OutlineSection],
    context: GuidedChatContext,
) -> str:
    major = context.known_target_info.get("target_major")
    university = context.known_target_info.get("target_university")
    target_line = " / ".join([value for value in [university, major] if value]) or "미설정"
    limited_note = _evidence_gap_note(context)

    safe_claims: list[str] = []
    if context.record_flow_summary:
        safe_claims.append(_clip_line(context.record_flow_summary, "기록 요약 기반 근거"))
    if selected.link_to_record_flow:
        safe_claims.append(_clip_line(selected.link_to_record_flow, "기록 연결 근거"))

    unresolved = context.evidence_gaps[:4] or ["추가 확인 필요"]

    lines = [
        f"# {selected.title}",
        "",
        f"- 과목: {subject}",
        f"- 보고서 목표: {target_line} 방향과 연결되는 탐구 역량을 근거 기반으로 정리",
        f"- 중심 질문(1문장): {selected.novelty_point}",
        "",
        "## 왜 이 주제가 학생에게 맞는가",
        f"- {selected.why_fit_student}",
        f"- 기록 연결: {selected.link_to_record_flow}",
    ]
    if selected.link_to_target_major_or_university:
        lines.append(f"- 목표 연결: {selected.link_to_target_major_or_university}")

    lines.extend(
        [
            "",
            "## 증거-안전 작성 경계",
            "- 확인된 학생 기록 범위를 넘는 단정은 하지 않습니다.",
            "- 미확인 내용은 반드시 '추가 확인 필요' 또는 '구체 사례 보강 필요'로 표기합니다.",
        ]
    )
    if limited_note:
        lines.append(f"- 제한 맥락 안내: {limited_note}")

    lines.extend(["", "## 권장 개요와 섹션별 작성 의도"])
    for section in outline:
        lines.append(f"### {section.title}")
        lines.append(section.purpose)

    lines.extend(["", "## 지금 안전하게 주장 가능한 사실"])
    if safe_claims:
        for claim in safe_claims[:4]:
            lines.append(f"- {claim}")
    else:
        lines.append("- 추가 확인 필요")

    lines.extend(["", "## 추가 확인 필요 / 구체 사례 보강 필요"])
    for gap in unresolved:
        lines.append(f"- {gap}")

    lines.extend(
        [
            "",
            "## 도입 문단(초안)",
            (
                f"본 보고서는 '{selected.title}'를 중심으로, 현재까지 확인 가능한 학생 기록과 문서 근거를 토대로 "
                "탐구의 방향과 의미를 정리한다. 우선 확인된 사실을 바탕으로 주제 선정의 타당성을 설명하고, "
                "근거가 부족한 항목은 '추가 확인 필요'로 분리해 과장 없이 확장 가능한 작성 구조를 제시한다."
            ),
            "",
            "## Evidence Memo",
            "- 외부 자료는 비교/해석 보조로만 사용하고 학생 수행 사실로 전환하지 않습니다.",
            "- 문장 확정 전 출처/기록 일치 여부를 확인합니다.",
            "",
            "## 최종화 전 확인 질문",
            "- 중심 질문이 보고서 전체 문단에 일관되게 반영되는가?",
            "- 각 단락에 근거 출처가 명시되는가?",
            "- 미확인 주장에 '추가 확인 필요' 표기가 남아있는가?",
        ]
    )

    return "\n".join(lines).strip()


def _build_state_summary(
    *,
    context: GuidedChatContext,
    subject: str | None,
    selected_topic_id: str | None,
    suggestions: list[TopicSuggestion],
    outline: list[OutlineSection],
    starter_draft_markdown: str | None,
) -> dict[str, object]:
    selected_title = next((item.title for item in suggestions if item.id == selected_topic_id), None)
    confirmed_points = []
    if context.record_flow_summary:
        confirmed_points.append(_clip_line(context.record_flow_summary, "", 160))
    return {
        "subject": subject,
        "selected_topic": selected_title,
        "selected_topic_id": selected_topic_id,
        "thesis_question": selected_title,
        "accepted_outline": [item.title for item in outline],
        "confirmed_evidence_points": confirmed_points,
        "unresolved_evidence_gaps": context.evidence_gaps[:6],
        "draft_intent": context.project_discussion_log[-1] if context.project_discussion_log else None,
        "user_preferences": context.workshop_history[-2:],
        "starter_draft_markdown": starter_draft_markdown,
    }


def _normalize_subject(subject: str) -> str:
    clean = " ".join(subject.strip().split())
    return clean or "탐구"


def _fallback_fit_message(context: GuidedChatContext, subject: str) -> str:
    if context.record_flow_summary:
        return f"기존 기록 흐름을 바탕으로 {subject} 주제를 안전하게 확장할 수 있습니다."
    return f"현재 정보 범위 안에서 {subject} 주제를 보수적으로 구성하기에 적합합니다."


def _fallback_record_link(context: GuidedChatContext) -> str:
    if context.record_flow_summary:
        return f"확인된 기록 요약: {_clip_line(context.record_flow_summary, '기록 요약이 존재합니다.')}"
    return "학생부 문서 근거가 제한적이어서 확인 가능한 범위만 사용합니다."


def _fallback_target_link(context: GuidedChatContext) -> str | None:
    major = context.known_target_info.get("target_major")
    university = context.known_target_info.get("target_university")
    if major and university:
        return f"{university} {major} 방향과 연결 가능한 주제로 설계했습니다."
    if major:
        return f"{major} 목표 방향을 반영한 주제입니다."
    if university:
        return f"{university} 지원 방향을 고려해 구성했습니다."
    return None


def _fallback_novelty_message(subject: str, index: int) -> str:
    if index == 1:
        return f"{subject} 주제에서 기존 활동의 맥락을 구조적으로 설명합니다."
    if index == 2:
        return f"{subject} 주제에서 비교/검증 단계를 포함합니다."
    return f"{subject} 주제에서 후속 탐구 질문을 명시합니다."


def _fallback_caution(context: GuidedChatContext) -> str | None:
    if context.evidence_gaps:
        return "미확인 사실을 단정하지 말고 부족 근거를 분리 표기하세요."
    return None


def _evidence_gap_note(context: GuidedChatContext) -> str | None:
    if context.evidence_gaps:
        return LIMITED_CONTEXT_NOTE
    return None


def _clip_line(value: str | None, fallback: str, limit: int = 160) -> str:
    text = " ".join((value or "").split()).strip()
    if not text:
        return fallback
    if len(text) <= limit:
        return text
    return f"{text[: limit - 3].rstrip()}..."


def _normalize_optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    text = " ".join(value.split()).strip()
    return text or None
