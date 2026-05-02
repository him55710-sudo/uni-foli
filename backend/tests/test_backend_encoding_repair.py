from __future__ import annotations

from pathlib import Path

import pytest

from unifoli_api.api.routes.workshops import (
    _build_chat_system_instruction,
    _build_draft_snapshot_context,
    _build_user_message_prompt,
)
from unifoli_api.services.document_service import _is_student_record_candidate

BACKEND_ROOT = Path(__file__).resolve().parents[1]
TARGET_FILES = {
    "llm": BACKEND_ROOT / "services/api/src/unifoli_api/core/llm.py",
    "workshops": BACKEND_ROOT / "services/api/src/unifoli_api/api/routes/workshops.py",
    "document_service": BACKEND_ROOT / "services/api/src/unifoli_api/services/document_service.py",
    "pdf_analysis_service": BACKEND_ROOT / "services/api/src/unifoli_api/services/pdf_analysis_service.py",
}
EXPECTED_SNIPPETS = {
    "llm": (
        "LLM 응답이 비어 있어 제한 모드로 전환합니다.",
        "응답 형식을 해석하지 못해 제한 모드로 전환합니다.",
        "AI 응답이 지연되어 안전 모드로 전환합니다.",
    ),
    "workshops": (
        "[유저 최신 초안 스냅샷]",
        "[현재 사용자 메시지]",
    ),
    "document_service": (
        "학교생활기록부",
        "생활기록부",
        "생기부",
    ),
    "pdf_analysis_service": (
        "PDF 텍스트를 충분히 추출하지 못해 문서 요약 근거가 제한적입니다.",
        "페이지 문서에서 핵심 흐름을 정리했습니다.",
        "학생명|성명",
        "고등학교",
    ),
}
MOJIBAKE_MARKERS = (
    "�",
    "??답??",
    "??청 구성",
    "?교?활기록부",
    "?활기록부",
    "[?좎?",
    "[?꾩옱",
    "理쒖떊",
    "硫붿떆吏",
)


def test_target_backend_files_are_utf8_and_without_mojibake_markers() -> None:
    for key, path in TARGET_FILES.items():
        content = path.read_bytes().decode("utf-8")
        for marker in MOJIBAKE_MARKERS:
            assert marker not in content, f"{path} contains mojibake marker: {marker}"
        for snippet in EXPECTED_SNIPPETS[key]:
            assert snippet in content


def test_workshop_korean_prompt_snapshot() -> None:
    snapshot = "가" * 5002
    assert _build_draft_snapshot_context(snapshot) == f"[유저 최신 초안 스냅샷]\n{'가' * 5000}..."
    assert _build_draft_snapshot_context("   ") == ""
    prompt = _build_user_message_prompt("  안녕하세요  ")
    assert "Latest student message:" in prompt
    assert "안녕하세요" in prompt
    assert "report coauthor" in prompt


def test_workshop_chat_instruction_defaults_to_long_report_coauthoring() -> None:
    instruction = _build_chat_system_instruction(
        base_instruction="base",
        memory_context="memory",
        document_grounding_context="grounding",
        diagnosis_copilot_brief="diagnosis",
        draft_snapshot_context="draft",
        coauthoring_context="coauthoring",
        response_depth="report_long",
        research_depth="scholarly",
    )

    assert "900-1500 Korean characters" in instruction
    assert "paper-level lens" in instruction
    assert "concise Korean" not in instruction


@pytest.mark.parametrize(
    ("parser_name", "content_text", "expected"),
    [
        ("neis", "", True),
        ("pdfplumber", "학교생활기록부 원문 일부", True),
        ("pdfplumber", "생활기록부 요약", True),
        ("pdfplumber", "학생부 파일 텍스트", True),
        ("pdfplumber", "생기부 분석 메모", True),
        ("pdfplumber", "일반 활동 보고서", False),
    ],
)
def test_student_record_candidate_keyword_detection(parser_name: str, content_text: str, expected: bool) -> None:
    assert _is_student_record_candidate(parser_name=parser_name, content_text=content_text) is expected
