from __future__ import annotations

import json
import secrets
from typing import AsyncIterator

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from polio_api.api.deps import get_current_user, get_db
from polio_api.db.models.project import Project
from polio_api.db.models.quest import Quest
from polio_api.db.models.user import User
from polio_api.db.models.workshop import DraftArtifact, PinnedReference, WorkshopSession, WorkshopTurn
from polio_api.schemas.workshop import (
    DraftArtifactResponse,
    FollowupChoice,
    PinnedReferenceCreate,
    QualityLevelInfo,
    RenderRequest,
    StarterChoice,
    StreamTokenResponse,
    WorkshopChoiceRequest,
    WorkshopMessageRequest,
    WorkshopQualityUpdateRequest,
    WorkshopSessionCreate,
    WorkshopSessionResponse,
    WorkshopStateResponse,
)
from polio_api.services.quality_control import (
    build_choice_acknowledgement,
    build_followup_choices,
    build_message_acknowledgement,
    build_quality_control_metadata,
    build_render_requirements,
    build_starter_choices,
    get_quality_profile,
    list_quality_level_info,
    normalize_quality_level,
    serialize_quality_level_info,
)
from polio_api.services.rag_service import RAGConfig
from polio_api.services.workshop_render_service import SSEEvent, _parse_artifact, _sse_line, stream_render
from polio_domain.enums import QualityLevel, TurnType, WorkshopStatus

router = APIRouter()


def _get_session_loaded(workshop_id: str, db: Session) -> WorkshopSession:
    stmt = (
        select(WorkshopSession)
        .options(
            joinedload(WorkshopSession.turns),
            joinedload(WorkshopSession.pinned_references),
            joinedload(WorkshopSession.draft_artifacts),
        )
        .filter(WorkshopSession.id == workshop_id)
    )
    session = db.execute(stmt).unique().scalar_one_or_none()
    if session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workshop session not found.")
    return session


def _get_project_and_quest(db: Session, session: WorkshopSession) -> tuple[Project | None, Quest | None]:
    project = db.execute(select(Project).filter(Project.id == session.project_id)).scalar_one_or_none()
    quest = None
    if session.quest_id:
        quest = db.execute(select(Quest).filter(Quest.id == session.quest_id)).scalar_one_or_none()
    return project, quest


def _latest_artifact(session: WorkshopSession) -> DraftArtifact | None:
    if not session.draft_artifacts:
        return None
    completed = [artifact for artifact in session.draft_artifacts if artifact.render_status == "completed"]
    return (completed or session.draft_artifacts)[-1]


def _sync_session_status(session: WorkshopSession) -> None:
    if session.status == WorkshopStatus.RENDERING.value:
        return
    requirements = build_render_requirements(
        quality_level=session.quality_level,
        context_score=session.context_score,
        turn_count=len(session.turns),
        reference_count=len(session.pinned_references),
    )
    session.status = (
        WorkshopStatus.DRAFTING.value if requirements["can_render"] else WorkshopStatus.COLLECTING_CONTEXT.value
    )


def _build_state_response(
    *,
    session: WorkshopSession,
    db: Session,
    message: str | None = None,
) -> WorkshopStateResponse:
    project, quest = _get_project_and_quest(db, session)
    turn_count = len(session.turns)
    reference_count = len(session.pinned_references)
    profile = get_quality_profile(session.quality_level)
    latest_artifact = _latest_artifact(session)

    starter_choices: list[StarterChoice] = []
    followup_choices: list[FollowupChoice] = []
    if turn_count == 0:
        starter_choices = [
            StarterChoice.model_validate(item)
            for item in build_starter_choices(
                quality_level=session.quality_level,
                quest_title=getattr(quest, "title", None),
                target_major=getattr(project, "target_major", None),
                recommended_output_type=getattr(quest, "recommended_output_type", None),
            )
        ]
    else:
        followup_choices = [
            FollowupChoice.model_validate(item)
            for item in build_followup_choices(quality_level=session.quality_level, turn_count=turn_count)
        ]

    requirements = build_render_requirements(
        quality_level=session.quality_level,
        context_score=session.context_score,
        turn_count=turn_count,
        reference_count=reference_count,
    )
    artifact_payload = DraftArtifactResponse.model_validate(latest_artifact) if latest_artifact else None

    default_message = (
        f"[{profile.label}] 학생 수준과 안전성을 우선으로 맥락을 모으고 있습니다."
        if session.status == WorkshopStatus.COLLECTING_CONTEXT.value
        else f"[{profile.label}] 렌더링 가능한 맥락이 확보되었습니다."
    )

    return WorkshopStateResponse(
        session=WorkshopSessionResponse.model_validate(session),
        starter_choices=starter_choices,
        followup_choices=followup_choices,
        message=message or default_message,
        quality_level_info=QualityLevelInfo.model_validate(serialize_quality_level_info(profile)),
        available_quality_levels=[
            QualityLevelInfo.model_validate(item) for item in list_quality_level_info()
        ],
        render_requirements=requirements,
        latest_artifact=artifact_payload,
    )


def _validate_quest_belongs_to_project(quest: Quest | None, project_id: str) -> None:
    if quest is None:
        return
    blueprint = getattr(quest, "blueprint", None)
    blueprint_project_id = getattr(blueprint, "project_id", None)
    if blueprint_project_id and blueprint_project_id != project_id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Quest does not belong to the requested project.",
        )


@router.get("/quality-levels", response_model=list[QualityLevelInfo])
def list_quality_levels_route() -> list[QualityLevelInfo]:
    return [QualityLevelInfo.model_validate(item) for item in list_quality_level_info()]


@router.post("", response_model=WorkshopStateResponse, status_code=status.HTTP_201_CREATED)
def create_workshop_route(
    payload: WorkshopSessionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> WorkshopStateResponse:
    del current_user
    project = db.execute(select(Project).filter(Project.id == payload.project_id)).scalar_one_or_none()
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found.")

    quest = None
    if payload.quest_id:
        quest = db.execute(select(Quest).filter(Quest.id == payload.quest_id)).scalar_one_or_none()
        if quest is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Quest not found.")
        _validate_quest_belongs_to_project(quest, payload.project_id)

    session = WorkshopSession(
        project_id=payload.project_id,
        quest_id=payload.quest_id,
        status=WorkshopStatus.COLLECTING_CONTEXT.value,
        context_score=10,
        quality_level=normalize_quality_level(payload.quality_level),
    )
    db.add(session)
    db.commit()

    loaded_session = _get_session_loaded(session.id, db)
    profile = get_quality_profile(loaded_session.quality_level)
    return _build_state_response(
        session=loaded_session,
        db=db,
        message=f"[{profile.label}] 어떤 방식으로 시작할지 고르면, 그 수준에 맞는 안전한 워크샵 흐름으로 이어집니다.",
    )


@router.get("/{workshop_id}", response_model=WorkshopStateResponse)
def get_workshop_route(
    workshop_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> WorkshopStateResponse:
    del current_user
    session = _get_session_loaded(workshop_id, db)
    _sync_session_status(session)
    db.commit()
    return _build_state_response(session=session, db=db)


@router.patch("/{workshop_id}/quality-level", response_model=WorkshopStateResponse)
def update_quality_level_route(
    workshop_id: str,
    payload: WorkshopQualityUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> WorkshopStateResponse:
    del current_user
    session = _get_session_loaded(workshop_id, db)
    session.quality_level = normalize_quality_level(payload.quality_level)
    _sync_session_status(session)
    db.commit()
    db.refresh(session)
    loaded_session = _get_session_loaded(workshop_id, db)
    profile = get_quality_profile(loaded_session.quality_level)
    return _build_state_response(
        session=loaded_session,
        db=db,
        message=f"[{profile.label}] 수준을 변경했습니다. starter/follow-up 제안과 렌더 조건도 함께 조정됩니다.",
    )


@router.post("/{workshop_id}/choices", response_model=WorkshopStateResponse)
def record_choice_route(
    workshop_id: str,
    payload: WorkshopChoiceRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> WorkshopStateResponse:
    del current_user
    session = _get_session_loaded(workshop_id, db)
    turn_type = TurnType.STARTER.value if not session.turns else TurnType.FOLLOW_UP.value
    query_text = payload.label
    if payload.payload and payload.payload.get("prompt"):
        query_text = str(payload.payload["prompt"])

    turn = WorkshopTurn(
        session_id=session.id,
        turn_type=turn_type,
        query=query_text,
        action_payload={
            **(payload.payload or {}),
            "choice_id": payload.choice_id,
            "display_label": payload.label,
        },
        response=build_choice_acknowledgement(quality_level=session.quality_level, label=payload.label),
    )
    db.add(turn)
    session.context_score += 15 if turn_type == TurnType.STARTER.value else 12
    _sync_session_status(session)
    db.commit()

    loaded_session = _get_session_loaded(workshop_id, db)
    _sync_session_status(loaded_session)
    db.commit()
    return _build_state_response(session=loaded_session, db=db, message=turn.response)


@router.post("/{workshop_id}/messages", response_model=WorkshopStateResponse)
def record_message_route(
    workshop_id: str,
    payload: WorkshopMessageRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> WorkshopStateResponse:
    del current_user
    session = _get_session_loaded(workshop_id, db)
    followup_choices = build_followup_choices(quality_level=session.quality_level, turn_count=len(session.turns) + 1)
    next_label = followup_choices[0]["label"] if followup_choices else None
    ai_response = build_message_acknowledgement(
        quality_level=session.quality_level,
        next_choice_label=next_label,
    )

    turn = WorkshopTurn(
        session_id=session.id,
        turn_type=TurnType.MESSAGE.value,
        query=payload.message.strip(),
        response=ai_response,
    )
    db.add(turn)
    session.context_score += 12 if len(payload.message.strip()) < 100 else 16
    _sync_session_status(session)
    db.commit()

    loaded_session = _get_session_loaded(workshop_id, db)
    _sync_session_status(loaded_session)
    db.commit()
    return _build_state_response(session=loaded_session, db=db, message=ai_response)


@router.post("/{workshop_id}/references/pin", response_model=WorkshopStateResponse)
def pin_reference_route(
    workshop_id: str,
    payload: PinnedReferenceCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> WorkshopStateResponse:
    del current_user
    session = _get_session_loaded(workshop_id, db)

    reference = PinnedReference(
        session_id=workshop_id,
        text_content=payload.text_content,
        source_type=payload.source_type,
        source_id=payload.source_id,
    )
    db.add(reference)
    session.context_score += 10
    _sync_session_status(session)
    db.commit()

    loaded_session = _get_session_loaded(workshop_id, db)
    _sync_session_status(loaded_session)
    db.commit()
    return _build_state_response(
        session=loaded_session,
        db=db,
        message="참고자료를 고정했습니다. 현재 품질 수준의 참고자료 사용 강도에 맞춰 렌더링에 반영됩니다.",
    )


@router.post("/{workshop_id}/stream-token", response_model=StreamTokenResponse)
def create_stream_token(
    workshop_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> StreamTokenResponse:
    del current_user
    session = db.execute(select(WorkshopSession).filter(WorkshopSession.id == workshop_id)).scalar_one_or_none()
    if session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found.")

    token = secrets.token_urlsafe(48)
    session.stream_token = token
    db.commit()
    return StreamTokenResponse(stream_token=token, workshop_id=workshop_id, expires_in=300)


@router.post("/{workshop_id}/render", response_model=dict[str, str])
def trigger_render(
    workshop_id: str,
    payload: RenderRequest = RenderRequest(),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, str]:
    del current_user
    session = _get_session_loaded(workshop_id, db)
    requirements = build_render_requirements(
        quality_level=session.quality_level,
        context_score=session.context_score,
        turn_count=len(session.turns),
        reference_count=len(session.pinned_references),
    )

    if not requirements["can_render"] and not payload.force:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "code": "CONTEXT_INSUFFICIENT",
                "message": "현재 품질 수준 기준으로 아직 렌더링에 필요한 맥락이 부족합니다.",
                **requirements,
            },
        )

    existing = next(
        (artifact for artifact in session.draft_artifacts if artifact.render_status in {"pending", "streaming"}),
        None,
    )
    if existing is not None:
        return {"artifact_id": existing.id, "status": existing.render_status}

    artifact = DraftArtifact(
        session_id=workshop_id,
        render_status="pending",
    )
    db.add(artifact)
    session.status = WorkshopStatus.RENDERING.value
    db.commit()
    db.refresh(artifact)
    return {
        "artifact_id": artifact.id,
        "status": artifact.render_status,
        "advanced_mode": str(payload.advanced_mode),
        "rag_source": payload.rag_source,
    }


@router.get("/{workshop_id}/events")
async def sse_events(
    workshop_id: str,
    stream_token: str = Query(...),
    artifact_id: str = Query(...),
    advanced_mode: bool = Query(False),
    rag_source: str = Query("semantic"),
    db: Session = Depends(get_db),
) -> StreamingResponse:
    session = db.execute(
        select(WorkshopSession).filter(WorkshopSession.id == workshop_id, WorkshopSession.stream_token == stream_token)
    ).scalar_one_or_none()
    if session is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired stream token.")

    artifact = db.execute(
        select(DraftArtifact).filter(DraftArtifact.id == artifact_id, DraftArtifact.session_id == workshop_id)
    ).scalar_one_or_none()
    if artifact is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Artifact not found.")

    if artifact.render_status == "completed":
        async def already_done() -> AsyncIterator[str]:
            yield _sse_line(
                SSEEvent.ARTIFACT_READY,
                {
                    "artifact_id": artifact.id,
                    "report_markdown": artifact.report_markdown,
                    "teacher_record_summary_500": artifact.teacher_record_summary_500,
                    "student_submission_note": artifact.student_submission_note,
                    "evidence_map": artifact.evidence_map or {},
                    "visual_specs": [],
                    "math_expressions": [],
                    "safety": {
                        "score": artifact.safety_score,
                        "flags": artifact.safety_flags or {},
                        "recommended_level": artifact.quality_level_applied,
                        "downgraded": artifact.quality_downgraded,
                    },
                    "quality_control": artifact.quality_control_meta or {},
                },
            )
            yield _sse_line(
                SSEEvent.RENDER_COMPLETED,
                {
                    "artifact_id": artifact.id,
                    "status": "completed",
                    "quality_level": artifact.quality_level_applied,
                    "safety_score": artifact.safety_score,
                },
            )

        return StreamingResponse(already_done(), media_type="text/event-stream")

    full_session = _get_session_loaded(workshop_id, db)
    project = db.execute(select(Project).filter(Project.id == full_session.project_id)).scalar_one_or_none()

    artifact.render_status = "streaming"
    db.commit()

    requested_advanced_mode = bool(advanced_mode and full_session.quality_level == QualityLevel.HIGH.value)

    # Build RAG config if advanced mode is detected
    rag_cfg = RAGConfig(
        enabled=requested_advanced_mode and len(full_session.pinned_references) > 0,
        source=rag_source if rag_source in {"semantic", "kci", "both", "internal"} else "semantic",
        max_papers=3,
        pin_required=True,
    )

    async def generate() -> AsyncIterator[str]:
        collected: dict[str, object] = {}
        safety_meta: dict[str, object] = {}
        quality_control_meta: dict[str, object] = {}
        try:
            async for sse_bytes in stream_render(
                db=db,
                session_id=workshop_id,
                project_id=full_session.project_id,
                turns=full_session.turns,
                references=full_session.pinned_references,
                target_major=getattr(project, "target_major", None),
                target_university=getattr(project, "target_university", None),
                artifact_id=artifact_id,
                quality_level=full_session.quality_level or QualityLevel.MID.value,
                advanced_mode=requested_advanced_mode,
                rag_config=rag_cfg,
            ):
                yield sse_bytes
                if SSEEvent.ARTIFACT_READY in sse_bytes:
                    try:
                        raw_event = sse_bytes.split("data: ", 1)[1].strip()
                        collected = json.loads(raw_event)
                        safety_meta = collected.pop("safety", {})
                        quality_control_meta = collected.pop("quality_control", {})
                    except Exception:
                        collected = {}
        except Exception as exc:  # noqa: BLE001
            yield _sse_line(SSEEvent.ERROR, {"message": str(exc)})
        finally:
            artifact_db = db.execute(select(DraftArtifact).filter(DraftArtifact.id == artifact_id)).scalar_one_or_none()
            if artifact_db is not None and collected:
                artifact_db.report_markdown = collected.get("report_markdown", "")
                artifact_db.teacher_record_summary_500 = collected.get("teacher_record_summary_500", "")
                artifact_db.student_submission_note = collected.get("student_submission_note", "")
                artifact_db.evidence_map = collected.get("evidence_map", {})
                artifact_db.render_status = "completed"
                artifact_db.quality_level_applied = str(
                    safety_meta.get("quality_level_applied") or quality_control_meta.get("applied_level") or full_session.quality_level
                )
                artifact_db.safety_score = safety_meta.get("score")
                artifact_db.safety_flags = safety_meta.get("flags", {})
                artifact_db.quality_downgraded = bool(safety_meta.get("downgraded", False))
                artifact_db.quality_control_meta = quality_control_meta or build_quality_control_metadata(
                    requested_level=full_session.quality_level,
                    applied_level=full_session.quality_level,
                    turn_count=len(full_session.turns),
                    reference_count=len(full_session.pinned_references),
                )
                full_session.status = WorkshopStatus.DONE.value
            elif artifact_db is not None:
                artifact_db.render_status = "failed"
                artifact_db.error_message = "렌더링 결과를 안전하게 파싱하지 못했습니다."
                full_session.status = WorkshopStatus.COLLECTING_CONTEXT.value

            full_session.stream_token = None
            db.commit()

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
