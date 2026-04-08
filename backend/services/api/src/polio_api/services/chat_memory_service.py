from __future__ import annotations

import json
from typing import Any

from polio_api.schemas.guided_chat import GuidedChatStatePayload
from polio_api.db.models.workshop import WorkshopSession


def _clip(value: str | None, limit: int = 220) -> str:
    normalized = " ".join((value or "").split()).strip()
    if len(normalized) <= limit:
        return normalized
    return f"{normalized[: limit - 3].rstrip()}..."


def _latest_user_message(session: WorkshopSession) -> str | None:
    for turn in reversed(session.turns or []):
        if getattr(turn, "speaker_role", "") == "user" and (turn.query or "").strip():
            return turn.query
    return None


def _infer_thesis_question(session: WorkshopSession, guided_state: GuidedChatStatePayload | None) -> str | None:
    if guided_state:
        candidate = str(guided_state.state_summary.get("thesis_question") or "").strip()
        if candidate:
            return _clip(candidate, 180)

    for turn in reversed(session.turns or []):
        if getattr(turn, "speaker_role", "") != "user":
            continue
        text = (turn.query or "").strip()
        if not text:
            continue
        if "?" in text or "질문" in text or "탐구" in text:
            return _clip(text, 180)
    return None


def _collect_user_preferences(session: WorkshopSession) -> list[str]:
    keywords = ("톤", "문체", "분량", "길이", "형식", "구성", "표현")
    preferences: list[str] = []
    for turn in reversed(session.turns or []):
        if getattr(turn, "speaker_role", "") != "user":
            continue
        query = (turn.query or "").strip()
        if not query:
            continue
        if any(key in query for key in keywords):
            preferences.append(_clip(query, 140))
        if len(preferences) >= 4:
            break
    return list(reversed(preferences))


def _collect_confirmed_evidence_points(session: WorkshopSession) -> list[str]:
    points: list[str] = []

    for ref in session.pinned_references or []:
        text = _clip(getattr(ref, "text_content", None), 160)
        if text:
            points.append(f"고정 참고자료: {text}")
        if len(points) >= 4:
            return points

    for turn in reversed(session.turns or []):
        if getattr(turn, "speaker_role", "") != "user":
            continue
        query = (turn.query or "").strip()
        if not query:
            continue
        if "근거" in query or "기록" in query or "문서" in query:
            points.append(_clip(query, 160))
        if len(points) >= 4:
            break

    return list(reversed(points))


def _collect_unresolved_gaps(session: WorkshopSession, guided_state: GuidedChatStatePayload | None) -> list[str]:
    gaps: list[str] = []

    if guided_state:
        raw = guided_state.state_summary.get("unresolved_evidence_gaps")
        if isinstance(raw, list):
            for item in raw:
                text = _clip(str(item), 160)
                if text:
                    gaps.append(text)

    for turn in reversed(session.turns or []):
        content = (turn.query or "") if getattr(turn, "speaker_role", "") == "user" else (turn.response or "")
        text = (content or "").strip()
        if not text:
            continue
        if "추가 확인 필요" in text or "보강 필요" in text:
            gaps.append(_clip(text, 160))
        if len(gaps) >= 4:
            break

    deduped: list[str] = []
    seen: set[str] = set()
    for item in gaps:
        if item in seen:
            continue
        seen.add(item)
        deduped.append(item)
    return deduped[:4]


def build_workshop_memory_summary(
    session: WorkshopSession,
    *,
    guided_state: GuidedChatStatePayload | None = None,
) -> dict[str, Any]:
    selected_topic = None
    accepted_outline: list[str] = []
    if guided_state:
        selected_topic = next(
            (
                item.title
                for item in guided_state.suggestions
                if item.id == guided_state.selected_topic_id and item.title
            ),
            None,
        )
        accepted_outline = [section.title for section in guided_state.recommended_outline if section.title][:8]

    draft_intent = _latest_user_message(session)

    summary = {
        "subject": guided_state.subject if guided_state else None,
        "selected_topic": selected_topic,
        "thesis_question": _infer_thesis_question(session, guided_state),
        "accepted_outline": accepted_outline,
        "confirmed_evidence_points": _collect_confirmed_evidence_points(session),
        "unresolved_evidence_gaps": _collect_unresolved_gaps(session, guided_state),
        "draft_intent": _clip(draft_intent, 180) if draft_intent else None,
        "user_preferences": _collect_user_preferences(session),
        "starter_draft_markdown": guided_state.starter_draft_markdown if guided_state else None,
    }

    return summary


def build_workshop_memory_payload(
    session: WorkshopSession,
    project: Any,
    quest: Any,
    *,
    max_recent_turns: int = 6,
    guided_state: GuidedChatStatePayload | None = None,
) -> tuple[str, dict[str, Any]]:
    summary = build_workshop_memory_summary(session, guided_state=guided_state)

    blocks: list[str] = []
    goal_lines = [
        f"목표 대학: {getattr(project, 'target_university', None) or '미정'}",
        f"목표 전공: {getattr(project, 'target_major', None) or '미정'}",
    ]
    if quest and getattr(quest, "title", None):
        goal_lines.append(f"목표 산출물: {quest.title}")
    blocks.append("[프로젝트/세션 목표]\n" + "\n".join(goal_lines))

    blocks.append("[가이드드 드래프팅 상태]\n" + json.dumps(summary, ensure_ascii=False, indent=2))

    valid_turns = [turn for turn in session.turns or [] if (turn.query or "").strip()]
    if not valid_turns:
        blocks.append("[최근 대화]\n아직 대화가 없습니다.")
        return "\n\n".join(blocks), summary

    recent_turns = valid_turns[-max_recent_turns:]
    older_count = max(0, len(valid_turns) - len(recent_turns))
    if older_count:
        blocks.append(f"[이전 대화 요약]\n총 {older_count}개의 이전 턴이 진행되었습니다. (생략됨)")

    turn_lines = ["[최근 대화]"]
    for turn in recent_turns:
        role = getattr(turn, "speaker_role", "user")
        if role == "assistant":
            content = (turn.response or turn.query or "").strip()
            if content:
                turn_lines.append(f"Assistant: {_clip(content, 220)}")
        else:
            turn_lines.append(f"Student: {_clip(turn.query, 220)}")

    blocks.append("\n".join(turn_lines))
    return "\n\n".join(blocks), summary


def build_workshop_memory_context(
    session: WorkshopSession,
    project: Any,
    quest: Any,
    max_recent_turns: int = 6,
    guided_state: GuidedChatStatePayload | None = None,
) -> str:
    context, _ = build_workshop_memory_payload(
        session,
        project,
        quest,
        max_recent_turns=max_recent_turns,
        guided_state=guided_state,
    )
    return context
