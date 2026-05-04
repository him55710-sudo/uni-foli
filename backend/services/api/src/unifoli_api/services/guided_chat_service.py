from __future__ import annotations

import json
from typing import Iterable, Literal, Any

from sqlalchemy.orm import Session

from unifoli_api.core.llm import LLMRequestError, get_llm_client, get_llm_temperature
from unifoli_api.db.models.user import User
from unifoli_api.schemas.guided_chat import (
    GuidedChoiceGroup,
    GuidedChoiceOption,
    GuidedConversationPhase,
    GuidedChatStartResponse,
    GuidedChatStatePayload,
    OutlineSection,
    PageRangeSelectionResponse,
    PageRangeOption,
    StructureSelectionResponse,
    TopicSelectionResponse,
    TopicSuggestion,
    TopicSuggestionResponse,
)
from unifoli_api.services.guided_chat_context_service import GuidedChatContext, build_guided_chat_context
from unifoli_api.services.guided_chat_state_service import load_guided_chat_state, save_guided_chat_state
from unifoli_api.services.topic_search_service import get_topic_search_service
from unifoli_api.services.prompt_registry import get_prompt_registry

GUIDED_CHAT_GREETING = "안녕하세요! 어떤 흥미로운 주제로 보고서를 시작해볼까요? 😊"
LIMITED_CONTEXT_NOTE = "학생부 기록이 조금 부족해서, 안전하게 시작할 수 있는 주제들로 준비했어요."
TOPIC_SUGGESTION_TARGET_COUNT = 300
TOPIC_LLM_SEED_COUNT = 9
TOPIC_REFERENCE_COUNT = 24

DEFAULT_SUBJECT_OPTIONS: list[GuidedChoiceOption] = [
    GuidedChoiceOption(id="subject-math", label="수학", value="수학"),
    GuidedChoiceOption(id="subject-math2", label="수2", value="수2"),
    GuidedChoiceOption(id="subject-chemistry", label="화학", value="화학"),
    GuidedChoiceOption(id="subject-biology", label="생명과학", value="생명과학"),
]


def start_guided_chat(*, db: Session, user: User, project_id: str | None) -> GuidedChatStartResponse:
    context = build_guided_chat_context(db=db, user=user, project_id=project_id)
    saved_state = load_guided_chat_state(db, context.project_id) if context.project_id else None
    phase = _resolve_phase_from_saved_state(saved_state)
    selected_page_label = saved_state.selected_page_range_label if saved_state else None
    selected_structure_id = saved_state.selected_structure_id if saved_state else None
    structure_options = saved_state.structure_options if saved_state else []
    next_action_options = saved_state.next_action_options if saved_state else []
    state_summary = _build_state_summary(
        context=context,
        phase=phase,
        subject=saved_state.subject if saved_state else None,
        selected_topic_id=saved_state.selected_topic_id if saved_state else None,
        selected_page_range_label=selected_page_label,
        selected_structure_id=selected_structure_id,
        suggestions=saved_state.suggestions if saved_state else [],
        page_ranges=saved_state.recommended_page_ranges if saved_state else [],
        outline=saved_state.recommended_outline if saved_state else [],
        structure_options=structure_options,
        next_action_options=next_action_options,
        starter_draft_markdown=saved_state.starter_draft_markdown if saved_state else None,
    )
    assistant_message, choice_groups = _build_start_prompt(
        phase=phase,
        context=context,
        state_summary=state_summary,
    )
    return GuidedChatStartResponse(
        greeting=GUIDED_CHAT_GREETING,
        assistant_message=assistant_message,
        phase=phase,
        project_id=context.project_id,
        evidence_gap_note=_evidence_gap_note(context),
        choice_groups=choice_groups,
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
    starred_keywords: list[str] = [],
    target_major: str | None = None,
) -> TopicSuggestionResponse:
    normalized_subject = _normalize_subject(subject)
    context = build_guided_chat_context(db=db, user=user, project_id=project_id)
    if target_major and not context.known_target_info.get("target_major"):
        context.known_target_info["target_major"] = target_major
    
    stored_keywords = _json_string_list(getattr(user, "starred_keywords_json", None))
    all_keywords = _unique_strings([*starred_keywords, *stored_keywords])
    
    llm_response, limited_reason = await _try_llm_topic_suggestions(
        subject=normalized_subject, 
        context=context,
        starred_keywords=all_keywords
    )

    normalized = _normalize_suggestions(
        suggestions=llm_response.suggestions if llm_response else [],
        subject=normalized_subject,
        context=context,
        target_count=TOPIC_SUGGESTION_TARGET_COUNT,
    )
    
    # 별표 상태 복구 (DB 기반)
    starred_topic_ids = []
    if project_id:
        from unifoli_api.db.models.project import Project
        proj = db.query(Project).filter(Project.id == project_id, Project.owner_user_id == user.id).first()
        if proj and proj.starred_topics_json:
            starred_topic_ids = _json_string_list(proj.starred_topics_json)
            
    for item in normalized:
        if item.id in starred_topic_ids:
            item.is_starred = True
    
    summary = _build_state_summary(
        context=context,
        phase="topic_selection",
        subject=normalized_subject,
        selected_topic_id=None,
        selected_page_range_label=None,
        selected_structure_id=None,
        suggestions=normalized,
        page_ranges=[],
        outline=[],
        structure_options=[],
        next_action_options=[],
        starter_draft_markdown=None,
    )
    
    limited_mode = bool(context.evidence_gaps or limited_reason)
    assistant_message = (
        f"좋아요. '{normalized_subject}'를 바탕으로 학생 기록, 관심사, 목표 전공을 섞어 "
        f"탐구 주제 {len(normalized)}개를 준비했어요.\n"
        "처음 12개는 하이라이트로 먼저 보여드리고, 아래 카드 목록에서 전체 후보를 골라 시작할 수 있습니다."
    )
    
    choice_groups = [
        GuidedChoiceGroup(
            id="topic-selection",
            title=f"추천 탐구 주제 {len(normalized)}개 중 하나를 선택해 주세요.",
            style="cards",
            options=[
                GuidedChoiceOption(
                    id=item.id,
                    label=_clip_line(item.title, f"주제 {index + 1}", 118),
                    description=_clip_line(item.why_fit_student, item.link_to_record_flow, 180),
                    value=item.id,
                )
                for index, item in enumerate(normalized)
            ],
        )
    ]

    response = TopicSuggestionResponse(
        greeting=GUIDED_CHAT_GREETING,
        assistant_message=assistant_message,
        phase="topic_selection",
        subject=normalized_subject,
        suggestions=normalized,
        evidence_gap_note=_evidence_gap_note(context) or (llm_response.evidence_gap_note if llm_response else None),
        choice_groups=choice_groups,
        limited_mode=limited_mode,
        limited_reason=limited_reason or ("evidence_gap" if context.evidence_gaps else None),
        state_summary=summary,
    )

    if context.project_id:
        save_guided_chat_state(
            db,
            context.project_id,
            GuidedChatStatePayload(
                phase="topic_selection",
                subject=response.subject,
                suggestions=response.suggestions,
                selected_topic_id=None,
                selected_page_range_label=None,
                selected_structure_id=None,
                recommended_page_ranges=[],
                recommended_outline=[],
                structure_options=[],
                next_action_options=[],
                starter_draft_markdown=None,
                state_summary=summary,
                limited_mode=response.limited_mode,
                limited_reason=response.limited_reason,
            ),
        )

    return response


def toggle_topic_star(
    *,
    db: Session,
    user: User,
    project_id: str | None,
    topic_id: str,
    is_starred: bool,
    topic_title: str | None = None,
) -> dict[str, Any]:
    # 1. 프로젝트 업데이트
    if project_id:
        from unifoli_api.db.models.project import Project
        project = db.query(Project).filter(Project.id == project_id, Project.owner_user_id == user.id).first()
        if project:
            try:
                starred = _json_string_list(project.starred_topics_json)
            except Exception:
                starred = []
            
            if is_starred:
                if topic_id not in starred:
                    starred.append(topic_id)
            else:
                if topic_id in starred:
                    starred.remove(topic_id)
            project.starred_topics_json = json.dumps(starred, ensure_ascii=False)
    
    # 2. 사용자 전역 관심사(키워드) 업데이트
    if topic_title:
        try:
            current_keywords = _json_string_list(getattr(user, "starred_keywords_json", None))
        except Exception:
            current_keywords = []
            
        if is_starred:
            if topic_title not in current_keywords:
                current_keywords.append(topic_title)
        else:
            if topic_title in current_keywords:
                current_keywords.remove(topic_title)
        user.starred_keywords_json = json.dumps(current_keywords, ensure_ascii=False)
    
    db.commit()
    return {"status": "success", "is_starred": is_starred}


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
    structure_options = _build_structure_options(context=context)
    next_action_options = _build_next_action_options(context=context)
    starter_draft = _build_starter_markdown(
        subject=normalized_subject,
        selected=selected,
        outline=outline,
        context=context,
    )

    guidance_parts = [f"좋아요. 선택한 주제는 '{selected.title}'예요."]
    if context.known_target_info.get("target_major"):
        guidance_parts.append(
            f"목표 전공 '{context.known_target_info['target_major']}'과 연결되는 흐름으로 구조화했습니다."
        )
    if context.evidence_gaps:
        guidance_parts.append("근거가 부족한 지점은 '추가 확인 필요'로 표시해 안전하게 확장하세요.")
    guidance_parts.append("먼저 보고서 분량을 정하면 바로 개요를 고정해드릴게요.")
    guidance_message = " ".join(guidance_parts)

    summary = _build_state_summary(
        context=context,
        phase="page_range_selection",
        subject=normalized_subject,
        selected_topic_id=selected.id,
        selected_page_range_label=None,
        selected_structure_id=None,
        suggestions=normalized,
        page_ranges=page_ranges,
        outline=outline,
        structure_options=structure_options,
        next_action_options=next_action_options,
        starter_draft_markdown=starter_draft,
    )
    page_range_choice_group = GuidedChoiceGroup(
        id="page-range-selection",
        title="보고서 분량을 선택해 주세요.",
        style="cards",
        options=[
            GuidedChoiceOption(
                id=f"page-range-{option.label}",
                label=f"{option.min_pages}~{option.max_pages}쪽",
                description=option.why_this_length,
                value=option.label,
            )
            for option in page_ranges
        ],
    )

    response = TopicSelectionResponse(
        phase="page_range_selection",
        assistant_message="좋아요. 이제 분량을 정해볼게요. 원하는 분량 카드를 눌러주세요.",
        selected_topic_id=selected.id,
        selected_title=selected.title,
        recommended_page_ranges=page_ranges,
        recommended_outline=outline,
        starter_draft_markdown=starter_draft,
        guidance_message=guidance_message,
        structure_options=structure_options,
        next_action_options=next_action_options,
        choice_groups=[page_range_choice_group],
        limited_mode=bool(context.evidence_gaps),
        limited_reason="evidence_gap" if context.evidence_gaps else None,
        state_summary=summary,
    )

    if context.project_id:
        save_guided_chat_state(
            db,
            context.project_id,
            GuidedChatStatePayload(
                phase="page_range_selection",
                subject=normalized_subject,
                suggestions=normalized,
                selected_topic_id=response.selected_topic_id,
                selected_page_range_label=None,
                selected_structure_id=None,
                recommended_page_ranges=response.recommended_page_ranges,
                recommended_outline=response.recommended_outline,
                structure_options=structure_options,
                next_action_options=next_action_options,
                starter_draft_markdown=response.starter_draft_markdown,
                state_summary=summary,
                limited_mode=response.limited_mode,
                limited_reason=response.limited_reason,
            ),
        )
    return response


def select_page_range(
    *,
    db: Session,
    user: User,
    project_id: str | None,
    selected_page_range_label: str,
    selected_topic_id: str | None = None,
) -> PageRangeSelectionResponse:
    context = build_guided_chat_context(db=db, user=user, project_id=project_id)
    saved_state = load_guided_chat_state(db, context.project_id) if context.project_id else None
    if saved_state is None:
        saved_state = GuidedChatStatePayload(
            phase="page_range_selection",
            subject=_normalize_subject("탐구"),
            suggestions=[],
            recommended_page_ranges=_build_page_ranges(context=context),
            recommended_outline=[],
            structure_options=_build_structure_options(context=context),
            next_action_options=_build_next_action_options(context=context),
            starter_draft_markdown=None,
            state_summary={},
            limited_mode=bool(context.evidence_gaps),
            limited_reason="evidence_gap" if context.evidence_gaps else None,
        )

    page_ranges = list(saved_state.recommended_page_ranges or _build_page_ranges(context=context))
    selected = next((item for item in page_ranges if item.label == selected_page_range_label), page_ranges[0])
    structure_options = list(saved_state.structure_options or _build_structure_options(context=context))

    summary = _build_state_summary(
        context=context,
        phase="structure_selection",
        subject=saved_state.subject,
        selected_topic_id=selected_topic_id or saved_state.selected_topic_id,
        selected_page_range_label=selected.label,
        selected_structure_id=saved_state.selected_structure_id,
        suggestions=saved_state.suggestions,
        page_ranges=page_ranges,
        outline=saved_state.recommended_outline,
        structure_options=structure_options,
        next_action_options=saved_state.next_action_options,
        starter_draft_markdown=saved_state.starter_draft_markdown,
    )
    structure_choice_group = GuidedChoiceGroup(
        id="structure-selection",
        title="구성 스타일을 골라주세요.",
        style="cards",
        options=structure_options,
    )
    response = PageRangeSelectionResponse(
        phase="structure_selection",
        assistant_message=(
            f"좋아요. 분량은 '{selected.min_pages}~{selected.max_pages}쪽'으로 진행할게요. "
            "이제 구성 스타일을 선택하면 바로 개요와 초안 방향을 고정해드릴게요."
        ),
        selected_page_range_label=selected.label,
        selected_page_range_note=selected.why_this_length,
        structure_options=structure_options,
        choice_groups=[structure_choice_group],
        limited_mode=bool(context.evidence_gaps),
        limited_reason="evidence_gap" if context.evidence_gaps else None,
        state_summary=summary,
    )

    if context.project_id:
        save_guided_chat_state(
            db,
            context.project_id,
            GuidedChatStatePayload(
                phase="structure_selection",
                subject=saved_state.subject,
                suggestions=saved_state.suggestions,
                selected_topic_id=selected_topic_id or saved_state.selected_topic_id,
                selected_page_range_label=selected.label,
                selected_structure_id=saved_state.selected_structure_id,
                recommended_page_ranges=page_ranges,
                recommended_outline=saved_state.recommended_outline,
                structure_options=structure_options,
                next_action_options=saved_state.next_action_options,
                starter_draft_markdown=saved_state.starter_draft_markdown,
                state_summary=summary,
                limited_mode=response.limited_mode,
                limited_reason=response.limited_reason,
            ),
        )
    return response


def select_structure(
    *,
    db: Session,
    user: User,
    project_id: str | None,
    selected_structure_id: str,
) -> StructureSelectionResponse:
    context = build_guided_chat_context(db=db, user=user, project_id=project_id)
    saved_state = load_guided_chat_state(db, context.project_id) if context.project_id else None
    if saved_state is None:
        saved_state = GuidedChatStatePayload(
            phase="structure_selection",
            subject=_normalize_subject("탐구"),
            suggestions=[],
            selected_topic_id=None,
            selected_page_range_label="3~5쪽",
            recommended_page_ranges=_build_page_ranges(context=context),
            recommended_outline=[],
            structure_options=_build_structure_options(context=context),
            next_action_options=_build_next_action_options(context=context),
            starter_draft_markdown=None,
            state_summary={},
            limited_mode=bool(context.evidence_gaps),
            limited_reason="evidence_gap" if context.evidence_gaps else None,
        )

    structure_options = list(saved_state.structure_options or _build_structure_options(context=context))
    selected = next((item for item in structure_options if item.id == selected_structure_id), structure_options[0])
    next_action_options = _build_next_action_options(context=context)

    summary = _build_state_summary(
        context=context,
        phase="drafting_next_step",
        subject=saved_state.subject,
        selected_topic_id=saved_state.selected_topic_id,
        selected_page_range_label=saved_state.selected_page_range_label,
        selected_structure_id=selected.id,
        suggestions=saved_state.suggestions,
        page_ranges=saved_state.recommended_page_ranges,
        outline=saved_state.recommended_outline,
        structure_options=structure_options,
        next_action_options=next_action_options,
        starter_draft_markdown=saved_state.starter_draft_markdown,
    )
    next_action_group = GuidedChoiceGroup(
        id="next-action-selection",
        title="다음으로 무엇을 할까요?",
        style="chips",
        options=next_action_options,
    )

    response = StructureSelectionResponse(
        phase="drafting_next_step",
        assistant_message=(
            f"좋아요. '{selected.label}' 스타일로 진행할게요. "
            "아래에서 다음 작업을 눌러 바로 이어가세요."
        ),
        selected_structure_id=selected.id,
        selected_structure_label=selected.label,
        next_action_options=next_action_options,
        choice_groups=[next_action_group],
        limited_mode=bool(context.evidence_gaps),
        limited_reason="evidence_gap" if context.evidence_gaps else None,
        state_summary=summary,
    )

    if context.project_id:
        save_guided_chat_state(
            db,
            context.project_id,
            GuidedChatStatePayload(
                phase="drafting_next_step",
                subject=saved_state.subject,
                suggestions=saved_state.suggestions,
                selected_topic_id=saved_state.selected_topic_id,
                selected_page_range_label=saved_state.selected_page_range_label,
                selected_structure_id=selected.id,
                recommended_page_ranges=saved_state.recommended_page_ranges,
                recommended_outline=saved_state.recommended_outline,
                structure_options=structure_options,
                next_action_options=next_action_options,
                starter_draft_markdown=saved_state.starter_draft_markdown,
                state_summary=summary,
                limited_mode=response.limited_mode,
                limited_reason=response.limited_reason,
            ),
        )
    return response


def _resolve_phase_from_saved_state(saved_state: GuidedChatStatePayload | None) -> GuidedConversationPhase:
    if saved_state is None:
        return "subject_input"
    if saved_state.phase:
        return saved_state.phase
    if saved_state.selected_structure_id:
        return "drafting_next_step"
    if saved_state.selected_page_range_label:
        return "structure_selection"
    if saved_state.selected_topic_id:
        return "page_range_selection"
    if saved_state.suggestions:
        return "topic_selection"
    if saved_state.subject:
        return "specific_topic_check"
    return "subject_input"


def _build_start_prompt(
    *,
    phase: GuidedConversationPhase,
    context: GuidedChatContext,
    state_summary: dict[str, object],
) -> tuple[str, list[GuidedChoiceGroup]]:
    subject = str(state_summary.get("subject") or "").strip()
    selected_topic = str(state_summary.get("selected_topic") or "").strip()
    choice_groups: list[GuidedChoiceGroup] = []

    if phase == "subject_input":
        choice_groups.append(
            GuidedChoiceGroup(
                id="subject-quick-picks",
                title="자주 선택하는 과목",
                style="chips",
                options=DEFAULT_SUBJECT_OPTIONS,
            )
        )
        return (
            "안녕하세요. 어떤 과목의 탐구보고서를 준비하고 계신가요?\n"
            "예를 들어 수학, 수2, 화학, 생명과학처럼 편하게 적어주세요.",
            choice_groups,
        )

    if phase == "specific_topic_check":
        choice_groups.append(
            GuidedChoiceGroup(
                id="specific-topic-check",
                title="특별히 생각해둔 주제가 있나요?",
                style="buttons",
                options=[
                    GuidedChoiceOption(
                        id="specific-yes",
                        label="주제가 있어요",
                        description="생각해둔 주제를 바로 입력할게요.",
                        value="주제가 있어요",
                    ),
                    GuidedChoiceOption(
                        id="specific-no-recommend",
                        label="추천 300개 받아보기",
                        description="학생 기록과 목표를 바탕으로 넓게 추천받을게요.",
                        value="추천 300개 받아보기",
                    ),
                ],
            )
        )
        return (
            f"좋아요. {subject or '해당 과목'}로 진행해볼게요.\n"
            "특별히 생각해 둔 주제가 있을까요? 아직 없다면 학생 기록을 바탕으로 300개 이상 추천해드릴게요.",
            choice_groups,
        )

    if phase == "topic_selection":
        raw_suggestions = state_summary.get("suggestions")
        if isinstance(raw_suggestions, list) and raw_suggestions:
            choice_groups.append(
                GuidedChoiceGroup(
                    id="topic-selection",
                    title=f"추천 탐구 주제 {len(raw_suggestions)}개 중 하나를 골라주세요.",
                    style="cards",
                    options=[
                        GuidedChoiceOption(
                            id=str(item.get("id") or f"topic-{index + 1}"),
                            label=_clip_line(str(item.get("title") or ""), f"주제 {index + 1}", 118),
                            description=_clip_line(
                                str(item.get("why_fit_student") or ""),
                                str(item.get("link_to_record_flow") or ""),
                                180,
                            ),
                            value=str(item.get("id") or f"topic-{index + 1}"),
                        )
                        for index, item in enumerate(raw_suggestions)
                        if isinstance(item, dict)
                    ],
                )
            )
        return (
            "이 중에서 어떤 방향이 가장 마음에 드시나요?\n바로 시작할 수 있게 개요와 초안도 잡아드릴까요?",
            choice_groups,
        )

    if phase == "page_range_selection":
        raw_page_ranges = state_summary.get("recommended_page_ranges")
        if isinstance(raw_page_ranges, list) and raw_page_ranges:
            choice_groups.append(
                GuidedChoiceGroup(
                    id="page-range-selection",
                    title="보고서 분량을 선택해 주세요.",
                    style="cards",
                    options=[
                        GuidedChoiceOption(
                            id=f"page-range-{str(item.get('label') or index + 1)}",
                            label=str(item.get("label") or f"{item.get('min_pages', 1)}~{item.get('max_pages', 3)}쪽"),
                            description=str(item.get("why_this_length") or ""),
                            value=str(item.get("label") or ""),
                        )
                        for index, item in enumerate(raw_page_ranges)
                        if isinstance(item, dict)
                    ],
                )
            )
        return (
            f"좋아요. '{selected_topic or '선택한 주제'}'로 진행할게요.\n"
            "보고서 분량은 어느 정도를 원하시나요?",
            choice_groups,
        )

    if phase == "structure_selection":
        raw_structure_options = state_summary.get("structure_options")
        if isinstance(raw_structure_options, list) and raw_structure_options:
            choice_groups.append(
                GuidedChoiceGroup(
                    id="structure-selection",
                    title="구성 스타일을 골라주세요.",
                    style="cards",
                    options=[
                        GuidedChoiceOption(
                            id=str(item.get("id") or f"structure-{index + 1}"),
                            label=str(item.get("label") or f"구성 {index + 1}"),
                            description=str(item.get("description") or ""),
                            value=str(item.get("value") or item.get("id") or ""),
                        )
                        for index, item in enumerate(raw_structure_options)
                        if isinstance(item, dict)
                    ],
                )
            )
        return ("구성 방식도 골라주시면 바로 개요를 잡아드릴게요.", choice_groups)

    if phase == "drafting_next_step":
        raw_next_actions = state_summary.get("next_action_options")
        if isinstance(raw_next_actions, list) and raw_next_actions:
            choice_groups.append(
                GuidedChoiceGroup(
                    id="next-action-selection",
                    title="다음으로 무엇을 할까요?",
                    style="chips",
                    options=[
                        GuidedChoiceOption(
                            id=str(item.get("id") or f"next-{index + 1}"),
                            label=str(item.get("label") or f"다음 작업 {index + 1}"),
                            description=str(item.get("description") or ""),
                            value=str(item.get("value") or item.get("label") or ""),
                        )
                        for index, item in enumerate(raw_next_actions)
                        if isinstance(item, dict)
                    ],
                )
            )
        return ("다음으로 무엇을 할까요? 아래 옵션을 누르면 바로 이어서 도와드릴게요.", choice_groups)

    if context.evidence_gaps:
        return ("근거가 부족한 부분을 먼저 보완하면서 안전하게 진행해볼게요.", choice_groups)
    return ("원하시는 방향으로 이어서 코칭해드릴게요.", choice_groups)


async def _try_llm_topic_suggestions(
    *,
    subject: str,
    context: GuidedChatContext,
    starred_keywords: list[str],
) -> tuple[TopicSuggestionResponse | None, str | None]:
    try:
        llm = get_llm_client(profile="fast", concern="guided_chat")
    except TypeError:
        llm = get_llm_client()  # type: ignore[call-arg]
    except RuntimeError as exc:
        if "No valid LLM client" in str(exc):
            return None, "llm_not_configured"
        return None, "llm_unavailable"

    prompt = _build_topic_prompt(subject=subject, context=context, starred_keywords=starred_keywords)
    try:
        system_instruction = get_prompt_registry().compose_prompt("chat.guided-report-topic-orchestration")
    except Exception:
        system_instruction = None

    try:
        return (
            await llm.generate_json(
                prompt=prompt,
                response_model=TopicSuggestionResponse,
                system_instruction=system_instruction,
                temperature=get_llm_temperature(profile="fast", concern="guided_chat"),
            ),
            None,
        )
    except LLMRequestError as exc:
        return None, exc.limited_reason
    except RuntimeError as exc:
        if "No valid LLM client" in str(exc):
            return None, "llm_not_configured"
        return None, "llm_unavailable"
    except Exception:
        return None, "llm_unavailable"


def _build_topic_prompt(*, subject: str, context: GuidedChatContext, starred_keywords: list[str]) -> str:
    # RAG: 학생부 맥락과 가장 유사한 주제 라이브러리 사례를 넉넉히 추출
    search_service = get_topic_search_service()
    search_query = f"{subject} {context.record_flow_summary or ''} {' '.join(starred_keywords)}"
    reference_topics = search_service.search(search_query, limit=TOPIC_REFERENCE_COUNT)
    
    reference_text = "\n".join([
        f"- {t['label']} (사유: {t['reason']})" for t in reference_topics
    ])

    compact_payload = {
        "target": {
            "university": context.known_target_info.get("target_university"),
            "major": context.known_target_info.get("target_major"),
        },
        "diagnosis_summary": context.diagnosis_summary,
        "record_flow_summary": _clip_line(context.record_flow_summary, "기록 요약 없음"),
        "starred_keywords": starred_keywords,
        "prior_topics": context.prior_topics[:3],
        "evidence_gaps": context.evidence_gaps[:5],
        "history": context.workshop_history[-4:],
        "discussion": context.project_discussion_log[-3:],
    }

    return (
        f"[학습 목표 과목]\n{subject}\n\n"
        "[학생부 및 관심사 데이터]\n"
        f"{json.dumps(compact_payload, ensure_ascii=False)}\n\n"
        "[참고할 만한 우수 탐구 사례 (Reference Library)]\n"
        f"{reference_text}\n\n"
        "[추천 주제 생성 지침]\n"
        "위 '우수 탐구 사례'들의 수준과 설득력을 참고하여, 학생의 개별 맥락에 최적화된 독창적인 탐구 주제 씨앗을 제안하세요.\n"
        "단순히 사례를 복사하지 말고, 학생의 구체적인 기록(record_flow_summary)과 목표 학과를 반영하여 변형/창조해야 합니다.\n\n"
        "카테고리별로 최소 3개씩 생성하세요:\n"
        f"1. [interest] 사용자 관심형: 학생의 키워드({', '.join(starred_keywords) or '없음'})와 기록을 연결한 주제\n"
        f"2. [subject] 교과과목 심화형: '{subject}' 과목의 핵심 개념을 심화 탐구하는 주제\n"
        f"3. [major] 목표학과 융합형: 목표 대학/전공 방향과 '{subject}' 과목을 유기적으로 엮은 주제\n\n"
        "[출력 규칙]\n"
        "- TopicSuggestionResponse JSON 형식으로만 응답하세요.\n"
        f"- suggestions는 가능하면 {TOPIC_LLM_SEED_COUNT}개를 반환하세요. 서버가 고품질 라이브러리 후보를 합쳐 최종 300개로 확장합니다.\n"
        "- suggestion_type 필드에는 'interest', 'subject', 'major' 중 하나를 넣으세요.\n"
        "- 학생 기록 근거가 약하면 보수적으로 제안하고 evidence_gap_note를 작성하세요.\n"
    )


def _normalize_suggestions(
    *,
    suggestions: Iterable[TopicSuggestion],
    subject: str,
    context: GuidedChatContext,
    target_count: int = TOPIC_SUGGESTION_TARGET_COUNT,
) -> list[TopicSuggestion]:
    normalized: list[TopicSuggestion] = []
    seen_titles: set[str] = set()
    seen_ids: set[str] = set()

    for index, item in enumerate(suggestions):
        title = _clip_line(item.title, f"{subject} 기반 탐구 주제 {index + 1}", 118)
        title_key = title.strip().lower()
        if title_key in seen_titles:
            continue
        seen_titles.add(title_key)
        suggestion_type = item.suggestion_type or (["interest", "subject", "major"][len(normalized) % 3])
        topic_id = item.id or f"topic-{len(normalized) + 1}"
        if topic_id in seen_ids:
            topic_id = f"{topic_id}-{len(normalized) + 1}"
        seen_ids.add(topic_id)

        normalized.append(
            TopicSuggestion(
                id=topic_id,
                title=title,
                why_fit_student=_clip_line(item.why_fit_student, _fallback_fit_message(context, subject)),
                link_to_record_flow=_clip_line(item.link_to_record_flow, _fallback_record_link(context)),
                link_to_target_major_or_university=_normalize_optional_text(
                    item.link_to_target_major_or_university or _fallback_target_link(context)
                ),
                novelty_point=_clip_line(item.novelty_point, _fallback_novelty_message(subject, len(normalized) + 1)),
                caution_note=_normalize_optional_text(item.caution_note or _fallback_caution(context)),
                suggestion_type=suggestion_type,
                is_starred=item.is_starred,
            )
        )
        if len(normalized) >= target_count:
            break

    if len(normalized) < target_count:
        normalized.extend(
            _build_fallback_topics(
                subject=subject,
                context=context,
                existing=normalized,
                target_count=target_count,
            )
        )
    return normalized[:target_count]


def _build_fallback_topics(
    *,
    subject: str,
    context: GuidedChatContext,
    existing: list[TopicSuggestion],
    target_count: int = TOPIC_SUGGESTION_TARGET_COUNT,
) -> list[TopicSuggestion]:
    existing_titles = {item.title for item in existing}
    existing_ids = {item.id for item in existing}
    target_hint = context.known_target_info.get("target_major") or context.known_target_info.get("target_university") or ""
    record_hint = context.record_flow_summary or "현재 학생부 근거가 제한적입니다."

    search_service = get_topic_search_service()
    query = f"{subject} {target_hint} {record_hint}"
    needed = max(target_count - len(existing), 0)
    search_results = search_service.search(query, limit=max(target_count + 80, needed + 80))

    result: list[TopicSuggestion] = []
    for item in search_results:
        title = _clip_line(str(item.get("label") or ""), f"{subject} 기반 탐구 주제", 118)
        if title in existing_titles:
            continue
        raw_id = str(item.get("id") or f"library-{len(result) + 1}")
        topic_id = raw_id if raw_id.startswith("library-") else f"library-{raw_id}"
        if topic_id in existing_ids:
            topic_id = f"{topic_id}-{len(result) + 1}"
        existing_ids.add(topic_id)
        existing_titles.add(title)
        suggestion_type = str(item.get("suggestion_type") or "subject")
        if suggestion_type not in {"interest", "subject", "major"}:
            suggestion_type = "subject"
        subject_hint = str(item.get("subject") or subject)
        major_hint = str(item.get("major") or target_hint or "목표 전공")
        result.append(
            TopicSuggestion(
                id=topic_id,
                title=title,
                why_fit_student=_clip_line(
                    str(item.get("reason") or ""),
                    _fallback_fit_message(context, subject),
                    180,
                ),
                link_to_record_flow=f"기록 연결 근거: {_clip_line(record_hint, '현재 기록 근거가 제한적입니다.')}",
                link_to_target_major_or_university=_normalize_optional_text(
                    _fallback_target_link(context) or f"{major_hint} 방향으로 확장 가능한 탐구입니다."
                ),
                novelty_point=f"{subject_hint}의 개념을 {major_hint} 맥락으로 옮겨 실제 자료, 한계, 개선안을 함께 다룹니다.",
                caution_note=_fallback_caution(context),
                suggestion_type=suggestion_type,  # type: ignore[arg-type]
            )
        )
        if len(existing) + len(result) >= target_count:
            break
    return result


def _build_page_ranges(*, context: GuidedChatContext) -> list[PageRangeOption]:
    limited = bool(context.evidence_gaps)
    return [
        PageRangeOption(
            label="1~3쪽",
            min_pages=1,
            max_pages=3,
            why_this_length="핵심 질문과 결론만 빠르게 정리할 때 적합합니다.",
        ),
        PageRangeOption(
            label="3~5쪽",
            min_pages=3,
            max_pages=5,
            why_this_length="근거, 분석, 결론을 균형 있게 담기 좋습니다.",
        ),
        PageRangeOption(
            label="5~10쪽",
            min_pages=5,
            max_pages=10,
            why_this_length=(
                "비교, 검증, 확장까지 포함한 심화 탐구형 보고서에 적합합니다."
                if not limited
                else "근거 경계를 분리해 보수적으로 심화 내용을 담을 수 있습니다."
            ),
        ),
    ]


def _build_structure_options(*, context: GuidedChatContext) -> list[GuidedChoiceOption]:
    return [
        GuidedChoiceOption(
            id="structure-quick-core",
            label="빠르게 핵심만 정리형",
            description="핵심 주장과 근거를 짧고 명확하게 정리합니다.",
        ),
        GuidedChoiceOption(
            id="structure-balanced",
            label="균형형",
            description="배경, 근거, 해석, 결론을 균형 있게 구성합니다.",
        ),
        GuidedChoiceOption(
            id="structure-deep-inquiry",
            label="심화 탐구형",
            description="비교, 검증, 한계 분석까지 깊게 다룹니다.",
        ),
        GuidedChoiceOption(
            id="structure-record-linked",
            label="세특 연결 강조형",
            description="학생부 기록 흐름과의 연결을 전면에 배치합니다.",
        ),
        GuidedChoiceOption(
            id="structure-career-linked",
            label="진로 연계 강조형",
            description="희망 전공/진로 맥락을 사실 기반으로 연결합니다.",
        ),
    ]


def _build_next_action_options(*, context: GuidedChatContext) -> list[GuidedChoiceOption]:
    return [
        GuidedChoiceOption(
            id="next-outline-first",
            label="개요 먼저 잡기",
            description="섹션별 핵심 문장을 먼저 고정합니다.",
            value="다음으로 개요를 먼저 잡아볼까요?",
        ),
        GuidedChoiceOption(
            id="next-intro-first",
            label="도입 문단부터 쓰기",
            description="첫 문단을 작성하고 전체 톤을 맞춥니다.",
            value="도입 문단부터 써볼까요?",
        ),
        GuidedChoiceOption(
            id="next-thesis-one-line",
            label="탐구 질문 한 문장 정리",
            description="보고서의 중심 질문을 한 문장으로 확정합니다.",
            value="탐구 질문을 먼저 한 문장으로 정리할까요?",
        ),
        GuidedChoiceOption(
            id="next-evidence-gaps",
            label="근거 부족 부분 보완",
            description="근거가 약한 부분을 먼저 안전하게 보강합니다.",
            value="근거가 부족한 부분부터 보완할까요?",
        ),
    ]


def _build_outline(*, context: GuidedChatContext, selected: TopicSuggestion) -> list[OutlineSection]:
    outline = [
        OutlineSection(title="1. 주제 선정 배경", purpose="왜 이 주제가 현재 학생 맥락과 맞는지 설명합니다."),
        OutlineSection(title="2. 중심 질문과 탐구 목적", purpose="한 문장 중심 질문을 제시하고 보고서 목표를 명확히 합니다."),
        OutlineSection(title="3. 확인 가능한 근거", purpose="학생부/문서에서 확인 가능한 사실만 정리합니다."),
        OutlineSection(title="4. 분석과 해석", purpose="근거 기반 해석과 주장 경계를 구분해 작성합니다."),
        OutlineSection(title="5. 추가 검증 계획", purpose="추가 확인이 필요한 항목과 보강 계획을 적습니다."),
    ]
    if context.known_target_info.get("target_major") or context.known_target_info.get("target_university"):
        outline.insert(
            4,
            OutlineSection(title="4-2. 진로/전공 연결", purpose="목표 방향과 연결되는 학습 태도를 사실 기반으로 제시합니다."),
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
        f"- 보고서 목표: {target_line} 방향과 연결되는 탐구 흐름을 근거 기반으로 정리",
        f"- 중심 질문(1문장): {selected.novelty_point or selected.title}",
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
            "- 확인된 학생 기록 범위를 넘는 가정은 하지 않습니다.",
            "- 미확인 내용은 반드시 '추가 확인 필요' 또는 '구체 근거 보강 필요'로 표기합니다.",
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

    lines.extend(["", "## 추가 확인 필요 / 구체 근거 보강 필요"])
    for gap in unresolved:
        lines.append(f"- {gap}")

    lines.extend(
        [
            "",
            "## 도입 문단(초안)",
            (
                f"본 보고서는 '{selected.title}'를 중심으로, 현재까지 확인 가능한 학생 기록과 문서 근거를 바탕으로 "
                "탐구의 방향과 범위를 정리합니다. 우선 확인된 사실을 바탕으로 주제 선정의 타당성을 설명하고, "
                "근거가 부족한 항목은 '추가 확인 필요'로 분리해 과장 없는 안전한 작성 구조를 제시합니다."
            ),
            "",
            "## 근거 메모",
            "- 외부 자료는 비교/해석 보조로만 사용하고 학생 수행 사실로 치환하지 않습니다.",
            "- 문장 확정 전 출처/기록 일치 여부를 확인합니다.",
            "",
            "## 최종 확인 질문",
            "- 중심 질문이 보고서 전체 문단에 일관되게 반영되는가?",
            "- 각 문단에 근거 출처가 명시되는가?",
            "- 미확인 주장은 '추가 확인 필요' 표기가 남아있는가?",
        ]
    )

    return "\n".join(lines).strip()


def _build_state_summary(
    *,
    context: GuidedChatContext,
    phase: GuidedConversationPhase,
    subject: str | None,
    selected_topic_id: str | None,
    selected_page_range_label: str | None,
    selected_structure_id: str | None,
    suggestions: list[TopicSuggestion],
    page_ranges: list[PageRangeOption],
    outline: list[OutlineSection],
    structure_options: list[GuidedChoiceOption],
    next_action_options: list[GuidedChoiceOption],
    starter_draft_markdown: str | None,
) -> dict[str, object]:
    selected_title = next((item.title for item in suggestions if item.id == selected_topic_id), None)
    confirmed_points = []
    if context.record_flow_summary:
        confirmed_points.append(_clip_line(context.record_flow_summary, "", 160))
    return {
        "phase": phase,
        "subject": subject,
        "selected_topic": selected_title,
        "selected_topic_id": selected_topic_id,
        "selected_page_range_label": selected_page_range_label,
        "suggestions": [item.model_dump(mode="json") for item in suggestions],
        "recommended_page_ranges": [item.model_dump(mode="json") for item in page_ranges],
        "structure_options": [item.model_dump(mode="json") for item in structure_options],
        "selected_structure_id": selected_structure_id,
        "selected_structure_label": next(
            (item.label for item in structure_options if item.id == selected_structure_id),
            None,
        ),
        "thesis_question": selected_title,
        "accepted_outline": [item.title for item in outline],
        "next_action_options": [item.model_dump(mode="json") for item in next_action_options],
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
        return "미확인 사실은 가정하지 말고 부족 근거를 분리 표기하세요."
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


def _json_string_list(value: str | None) -> list[str]:
    if not value:
        return []
    try:
        parsed = json.loads(value)
    except (TypeError, ValueError):
        return []
    if not isinstance(parsed, list):
        return []
    return _unique_strings(str(item) for item in parsed)


def _unique_strings(values: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        text = " ".join(str(value).split()).strip()
        if not text or text in seen:
            continue
        seen.add(text)
        result.append(text)
    return result[:50]
