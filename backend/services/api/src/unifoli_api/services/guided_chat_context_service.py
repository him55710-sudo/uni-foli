# -*- coding: latin-1 -*-
from __future__ import annotations

import json

from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from unifoli_api.db.models.diagnosis_run import DiagnosisRun
from unifoli_api.db.models.draft import Draft
from unifoli_api.db.models.parsed_document import ParsedDocument
from unifoli_api.db.models.project import Project
from unifoli_api.db.models.user import User
from unifoli_api.db.models.workshop import WorkshopSession, WorkshopTurn
from unifoli_api.services.diagnosis_artifact_service import extract_diagnosis_summary_text
from unifoli_api.services.guided_chat_state_service import GUIDED_CHAT_STATE_DRAFT_TITLE, load_guided_chat_state
from unifoli_api.services.project_service import list_project_discussion_log


def _clip(text: str | None, limit: int = 420) -> str:
    normalized = " ".join((text or "").strip().split())
    if len(normalized) <= limit:
        return normalized
    return f"{normalized[: limit - 3].rstrip()}..."


class GuidedChatContext(BaseModel):
    project_id: str | None = None
    known_student_profile: dict[str, str] = Field(default_factory=dict)
    known_target_info: dict[str, str] = Field(default_factory=dict)
    diagnosis_summary: str | None = None
    record_flow_summary: str | None = None
    prior_topics: list[str] = Field(default_factory=list)
    prior_draft_signals: list[str] = Field(default_factory=list)
    workshop_history: list[str] = Field(default_factory=list)
    project_discussion_log: list[str] = Field(default_factory=list)
    evidence_gaps: list[str] = Field(default_factory=list)


def build_guided_chat_context(
    *,
    db: Session,
    user: User,
    project_id: str | None,
) -> GuidedChatContext:
    project, invalid_project_requested = _resolve_project(db=db, user_id=user.id, project_id=project_id)
    context = GuidedChatContext(project_id=project.id if project else None)

    context.known_student_profile = _build_student_profile(user)
    context.known_target_info = _build_target_info(user=user, project=project)
    context.diagnosis_summary = _load_diagnosis_summary(db=db, project=project)
    context.record_flow_summary = _load_record_flow_summary(db=db, project=project)
    context.workshop_history = _load_workshop_history(db=db, project=project)
    context.prior_draft_signals = _load_prior_draft_signals(db=db, project=project)
    context.project_discussion_log = list_project_discussion_log(project) if project else []
    context.prior_topics = _load_prior_topics(db=db, project=project)
    context.evidence_gaps = _derive_evidence_gaps(
        user=user,
        context=context,
        project=project,
        invalid_project_requested=invalid_project_requested,
    )
    return context


def _resolve_project(*, db: Session, user_id: str, project_id: str | None) -> tuple[Project | None, bool]:
    if project_id:
        requested = db.execute(
            select(Project).where(Project.id == project_id, Project.owner_user_id == user_id).limit(1)
        ).scalar_one_or_none()
        if requested is not None:
            return requested, False
        fallback = db.execute(
            select(Project).where(Project.owner_user_id == user_id).order_by(Project.updated_at.desc()).limit(1)
        ).scalar_one_or_none()
        return fallback, True

    latest = db.execute(
        select(Project).where(Project.owner_user_id == user_id).order_by(Project.updated_at.desc()).limit(1)
    ).scalar_one_or_none()
    return latest, False


def _build_student_profile(user: User) -> dict[str, str]:
    profile: dict[str, str] = {}
    if user.grade:
        profile["grade"] = user.grade
    if user.track:
        profile["track"] = user.track
    if user.career:
        profile["career"] = user.career
    if user.admission_type:
        profile["admission_type"] = user.admission_type
    return profile


def _build_target_info(*, user: User, project: Project | None) -> dict[str, str]:
    target_university = (project.target_university if project else None) or user.target_university
    target_major = (project.target_major if project else None) or user.target_major

    info: dict[str, str] = {}
    if target_university:
        info["target_university"] = target_university
    if target_major:
        info["target_major"] = target_major
    return info


def _load_diagnosis_summary(*, db: Session, project: Project | None) -> str | None:
    if project is None:
        return None
    run = db.execute(
        select(DiagnosisRun)
        .where(DiagnosisRun.project_id == project.id, DiagnosisRun.result_payload.isnot(None))
        .order_by(DiagnosisRun.created_at.desc())
        .limit(1)
    ).scalar_one_or_none()
    if run is None or not run.result_payload:
        return None
    try:
        payload = json.loads(run.result_payload)
    except json.JSONDecodeError:
        return None
    if not isinstance(payload, dict):
        return None

    persisted_summary = extract_diagnosis_summary_text(payload)
    if persisted_summary:
        return persisted_summary

    headline = _clip(str(payload.get("headline") or ""))
    recommended_focus = _clip(str(payload.get("recommended_focus") or ""))
    strengths = payload.get("strengths")
    first_strength = _clip(str(strengths[0])) if isinstance(strengths, list) and strengths else ""

    parts = [part for part in [headline, recommended_focus, first_strength] if part]
    if not parts:
        return None
    return " / ".join(parts[:3])


def _load_record_flow_summary(*, db: Session, project: Project | None) -> str | None:
    if project is None:
        return None
    documents = list(
        db.execute(
            select(ParsedDocument)
            .where(ParsedDocument.project_id == project.id)
            .order_by(ParsedDocument.updated_at.desc())
            .limit(2)
        ).scalars()
    )
    snippets: list[str] = []
    for doc in documents:
        source = _clip(doc.original_filename or "업로드 문서", 80)
        body = _clip(doc.content_markdown or doc.content_text, 260)
        if body:
            snippets.append(f"{source}: {body}")
    if not snippets:
        return None
    return " | ".join(snippets)


def _load_workshop_history(*, db: Session, project: Project | None) -> list[str]:
    if project is None:
        return []
    session = db.execute(
        select(WorkshopSession)
        .where(WorkshopSession.project_id == project.id)
        .order_by(WorkshopSession.updated_at.desc())
        .limit(1)
    ).scalar_one_or_none()
    if session is None:
        return []

    turns = list(
        db.execute(
            select(WorkshopTurn)
            .where(WorkshopTurn.session_id == session.id)
            .order_by(WorkshopTurn.created_at.desc())
            .limit(6)
        ).scalars()
    )
    history: list[str] = []
    for turn in reversed(turns):
        prefix = "학생" if turn.speaker_role == "user" else "코치"
        value = _clip(turn.query or turn.response or "", 200)
        if value:
            history.append(f"{prefix}: {value}")
    return history


def _load_prior_draft_signals(*, db: Session, project: Project | None) -> list[str]:
    if project is None:
        return []
    drafts = list(
        db.execute(
            select(Draft)
            .where(
                Draft.project_id == project.id,
                Draft.title != GUIDED_CHAT_STATE_DRAFT_TITLE,
            )
            .order_by(Draft.updated_at.desc())
            .limit(4)
        ).scalars()
    )
    return [_clip(item.title, 80) for item in drafts if item.title]


def _load_prior_topics(*, db: Session, project: Project | None) -> list[str]:
    if project is None:
        return []
    state = load_guided_chat_state(db, project.id)
    if state is None:
        return []
    topic_titles = [item.title for item in state.suggestions if item.title]
    if state.selected_topic_id:
        selected = next((item.title for item in state.suggestions if item.id == state.selected_topic_id), None)
        if selected:
            topic_titles.insert(0, selected)
    seen: set[str] = set()
    ordered: list[str] = []
    for title in topic_titles:
        if title in seen:
            continue
        seen.add(title)
        ordered.append(title)
    return ordered[:5]


def _derive_evidence_gaps(
    *,
    user: User,
    context: GuidedChatContext,
    project: Project | None,
    invalid_project_requested: bool,
) -> list[str]:
    gaps: list[str] = []
    if invalid_project_requested:
        gaps.append("요청하신 프로젝트를 찾지 못해 최근 프로젝트 기준으로 안내합니다.")
    if project is None:
        gaps.append("프로젝트 맥락이 없어 기본 정보 기준으로 안내합니다.")
    if not context.known_target_info.get("target_university") and not context.known_target_info.get("target_major"):
        gaps.append("목표 대학과 전공 정보가 확인되지 않았습니다.")
    if context.diagnosis_summary is None:
        gaps.append("진단 결과가 없어 일반 제안으로 안내합니다.")
    if context.record_flow_summary is None:
        gaps.append("학생부 문서 근거가 충분하지 않습니다.")
    if not context.workshop_history and not context.prior_draft_signals:
        gaps.append("기존 작성 흐름 신호가 없어 보수적으로 제안합니다.")
    if not context.known_student_profile and not user.name:
        gaps.append("학생 프로필 정보가 제한적입니다.")
    return gaps
