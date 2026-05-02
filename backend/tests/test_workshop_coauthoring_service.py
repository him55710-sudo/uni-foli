from __future__ import annotations

from unifoli_api.services.workshop_coauthoring_service import (
    build_default_structured_draft,
    extract_draft_patch_from_response,
    extract_structured_draft_from_evidence_map,
    merge_structured_draft_into_evidence_map,
)


def test_extract_draft_patch_from_response_parses_patch_block() -> None:
    response = """
안내 문장입니다.
[DRAFT_PATCH]
{
  "mode": "section_drafting",
  "block_id": "body_section_1",
  "heading": "Body Section 1",
  "content_markdown": "근거 중심 본문 초안입니다.",
  "rationale": "학생 기록의 강점을 본문 1에 배치",
  "evidence_boundary_note": "추정 성과는 포함하지 않음",
  "requires_approval": true
}
[/DRAFT_PATCH]
"""

    cleaned, patch = extract_draft_patch_from_response(response)

    assert patch is not None
    assert patch.block_id == "body_section_1"
    assert patch.mode == "section_drafting"
    assert "DRAFT_PATCH" not in cleaned
    assert "안내 문장" in cleaned


def test_structured_draft_roundtrip_via_evidence_map() -> None:
    structured = build_default_structured_draft(mode="outline", source="structured")
    merged = merge_structured_draft_into_evidence_map(evidence_map=None, structured_draft=structured)
    restored = extract_structured_draft_from_evidence_map(merged)

    assert restored is not None
    assert restored.mode == "outline"
    assert len(restored.blocks) == 6
