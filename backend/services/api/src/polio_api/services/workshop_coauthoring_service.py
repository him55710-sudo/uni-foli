from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from typing import Any

from pydantic import ValidationError

from polio_api.schemas.workshop import (
    WorkshopDraftPatchProposal,
    WorkshopMode,
    WorkshopStructuredDraftState,
)

DEFAULT_BLOCK_DEFINITIONS: tuple[tuple[str, str], ...] = (
    ("title", "제목"),
    ("introduction_background", "도입 / 배경"),
    ("body_section_1", "본론 1"),
    ("body_section_2", "본론 2"),
    ("body_section_3", "본론 3"),
    ("conclusion_reflection_next_step", "결론 / 성찰 / 다음 단계"),
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
        "[워크숍 공동작성 모드]",
        f"- 현재 모드: {mode}",
        "- 기본 섹션 구조: title, introduction/background, body1, body2, body3, conclusion/reflection/next step",
        "- 섹션 제안을 할 때는 본문 설명 뒤에 [DRAFT_PATCH] JSON [/DRAFT_PATCH] 블록을 추가할 수 있습니다.",
        "- DRAFT_PATCH JSON 형식:",
        (
            '  {"mode":"section_drafting","block_id":"body_section_1","heading":"선택","content_markdown":"본문",'
            '"rationale":"왜 이 섹션인지","evidence_boundary_note":"근거 경계","requires_approval":true}'
        ),
        "- 승인 전에는 학생 작성 내용을 덮어쓰지 말고 제안으로 유지하세요.",
        "- 학생 활동/성과를 추정 생성하지 마세요.",
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

