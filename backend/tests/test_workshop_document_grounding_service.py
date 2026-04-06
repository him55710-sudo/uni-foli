from __future__ import annotations

from types import SimpleNamespace

from polio_api.services.workshop_document_grounding_service import (
    _format_document_analysis_block,
    _format_chunk_evidence_block,
    _select_lexical_chunks,
    build_workshop_document_grounding_context,
)


def test_format_document_analysis_block_prefers_pdf_analysis_summary() -> None:
    document = SimpleNamespace(
        original_filename="학생부.pdf",
        page_count=5,
        word_count=1200,
        status="parsed",
        parse_metadata={
            "pdf_analysis": {
                "summary": "문서 전체 흐름은 탐구 동기-실험 과정-결론 순서로 구성되어 있습니다.",
                "key_points": ["탐구 질문이 명확합니다.", "실험 절차가 단계별로 제시됩니다."],
                "evidence_gaps": ["결과 수치의 출처 확인이 필요합니다."],
            }
        },
        content_markdown="",
        content_text="",
    )

    block = _format_document_analysis_block([document])

    assert "업로드 문서 분석 요약" in block
    assert "분석 요약" in block
    assert "탐구 동기-실험 과정-결론" in block
    assert "핵심 포인트" in block
    assert "근거 한계" in block


def test_select_lexical_chunks_prefers_query_overlap() -> None:
    matching = SimpleNamespace(
        id="chunk-1",
        chunk_index=3,
        content_text="수학 모델링 과정에서 변수 통제와 오차 분석을 수행했습니다.",
        page_number=2,
        document=SimpleNamespace(original_filename="기록A.pdf"),
    )
    non_matching = SimpleNamespace(
        id="chunk-2",
        chunk_index=4,
        content_text="역사 과목 발표 준비 내용입니다.",
        page_number=3,
        document=SimpleNamespace(original_filename="기록B.pdf"),
    )

    selected = _select_lexical_chunks(
        chunks=[non_matching, matching],
        query="수학 모델링 오차",
        limit=2,
    )

    assert selected
    assert selected[0].id == "chunk-1"


def test_build_document_grounding_context_handles_missing_project() -> None:
    context = build_workshop_document_grounding_context(
        db=None,  # type: ignore[arg-type]
        project=None,
        user_message="이 문서의 핵심을 알려줘",
    )

    assert "연결된 프로젝트가 없어" in context
    assert "문서 근거 사용 원칙" in context
    assert "추측으로 학생 활동을 만들지 않습니다" in context


def test_format_chunk_evidence_block_handles_empty() -> None:
    block = _format_chunk_evidence_block([])
    assert "질문 관련 문서 발췌" in block
    assert "찾지 못했습니다" in block

