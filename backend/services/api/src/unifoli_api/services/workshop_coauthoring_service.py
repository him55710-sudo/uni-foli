from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from typing import Any

from pydantic import ValidationError

from unifoli_api.schemas.workshop import (
    WorkshopDraftPatchProposal,
    WorkshopMode,
    WorkshopStructuredDraftState,
)

DEFAULT_BLOCK_DEFINITIONS: tuple[tuple[str, str], ...] = (
    ("title", "\uc81c\ubaa9"),
    ("introduction_background", "\uc11c\ub860 / \ubb38\uc81c\uc758\uc2dd"),
    ("body_section_1", "\ubcf8\ub860 1 / \uac1c\ub150\uacfc \ubc30\uacbd"),
    ("body_section_2", "\ubcf8\ub860 2 / \ubc29\ubc95\uacfc \uacfc\uc815"),
    ("body_section_3", "\ubcf8\ub860 3 / \uacb0\uacfc\uc640 \ud574\uc11d"),
    ("conclusion_reflection_next_step", "\uacb0\ub860 / \ub290\ub080 \uc810 / \ucd9c\ucc98"),
)

_PATCH_PATTERN = re.compile(r"\[DRAFT_PATCH\]([\s\S]*?)\[/DRAFT_PATCH\]", re.IGNORECASE)


def build_default_structured_draft(
    *,
    mode: WorkshopMode = "planning",
    source: str = "derived",
) -> WorkshopStructuredDraftState:
    return WorkshopStructuredDraftState(
        mode=mode,
        source="structured" if source == "structured" else "derived",
        blocks=[
            {
                "block_id": block_id,
                "heading": heading,
                "content_markdown": "",
                "attribution": "student-authored",
                "updated_at": None,
            }
            for block_id, heading in DEFAULT_BLOCK_DEFINITIONS
        ],
    )


def extract_structured_draft_from_evidence_map(
    evidence_map: dict[str, Any] | None,
) -> WorkshopStructuredDraftState | None:
    if not isinstance(evidence_map, dict):
        return None
    coauthoring = evidence_map.get("coauthoring")
    if not isinstance(coauthoring, dict):
        return None
    raw = coauthoring.get("structured_draft")
    if not isinstance(raw, dict):
        return None
    try:
        return WorkshopStructuredDraftState.model_validate(raw)
    except ValidationError:
        return None


def merge_structured_draft_into_evidence_map(
    *,
    evidence_map: dict[str, Any] | None,
    structured_draft: WorkshopStructuredDraftState,
) -> dict[str, Any]:
    merged = dict(evidence_map or {})
    coauthoring = dict(merged.get("coauthoring") or {})
    coauthoring["structured_draft"] = structured_draft.model_dump(mode="json")
    coauthoring["updated_at"] = datetime.now(timezone.utc).isoformat()
    merged["coauthoring"] = coauthoring
    return merged


def build_coauthoring_system_context(
    *,
    mode: WorkshopMode,
    structured_draft: WorkshopStructuredDraftState | None,
) -> str:
    if structured_draft is None:
        structured_draft = build_default_structured_draft(mode=mode, source="derived")

    lines = [
        "[Section accumulation rules]",
        "- The user may ask for one section at a time: intro, body1, body2, body3, conclusion, reflection, or references.",
        "- Do not draft the full report in one response. Propose only one DRAFT_PATCH for the requested block_id.",
        "- For reflection/references, append under a clear subheading inside conclusion_reflection_next_step instead of overwriting existing text.",
        "- Ask at most one student-preference question when personal opinion is needed; if the user allowed AI auto-selection, make a conservative assumption and state it.",
        "- Student record evidence must be cited as [source: student record p.X] when page evidence is available.",
        "",
        "[초안 공동작성 모드]",
        f"- 현재 모드: {mode}",
        "- 기본 초안 구조: title, introduction/background, body1, body2, body3, conclusion/reflection/next step",
        "- 사용자가 본문 작성을 요청하면 실제 답변을 먼저 쓰고, 삽입 가능한 경우 [DRAFT_PATCH] JSON [/DRAFT_PATCH] 블록을 정확히 1개만 제안할 수 있습니다.",
        "- DRAFT_PATCH JSON 예시:",
        (
            '  {"mode":"section_drafting","block_id":"body_section_1","heading":"소제목",'
            '"content_markdown":"본문","rationale":"이 블록에 들어가는 이유",'
            '"evidence_boundary_note":"근거 경계와 추가 확인 필요 사항","requires_approval":true}'
        ),
        "- 학생이 직접 쓴 문장을 임의로 덮어쓰지 말고, 제안은 반드시 승인 전 상태로 둡니다.",
        "- 생기부에 없는 활동, 수상, 실험, 독서, 성과를 추정해서 만들지 마세요.",
        "",
        "[현재 구조화 초안 상태]",
    ]
    for block in structured_draft.blocks:
        preview = (block.content_markdown or "").strip().replace("\n", " ")
        if len(preview) > 100:
            preview = f"{preview[:100].rstrip()}..."
        lines.append(f"- {block.block_id} | {block.heading} | {block.attribution} | {preview or '(empty)'}")
    return "\n".join(lines)


def extract_draft_patch_from_response(raw_response: str) -> tuple[str, WorkshopDraftPatchProposal | None]:
    if not raw_response:
        return "", None
    matches = _PATCH_PATTERN.findall(raw_response)
    cleaned = _PATCH_PATTERN.sub("", raw_response).strip()
    if not matches:
        return cleaned, None
    for candidate in reversed(matches):
        payload = candidate.strip()
        if payload.startswith("```"):
            payload = payload.strip("`")
            payload = payload.replace("json", "", 1).strip()
        try:
            decoded = json.loads(payload)
        except json.JSONDecodeError:
            continue
        try:
            patch = WorkshopDraftPatchProposal.model_validate(decoded)
        except ValidationError:
            continue
        return cleaned, patch
    return cleaned, None
