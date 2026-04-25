from __future__ import annotations

from types import SimpleNamespace

from unifoli_api.services.workshop_document_grounding_service import (
    _format_chunk_evidence_block,
    _format_document_analysis_block,
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
                "summary": "문서 전체 흐름은 탐구 동기, 실험 과정, 결론 순서로 구성되었습니다.",
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
    assert "탐구 동기, 실험 과정, 결론" in block
    assert "핵심 포인트" in block
    assert "근거 공백" in block
    assert "??" not in block


def test_format_document_analysis_block_includes_canonical_signals() -> None:
    document = SimpleNamespace(
        original_filename="학생부.pdf",
        page_count=4,
        word_count=980,
        status="parsed",
        parse_metadata={
            "student_record_canonical": {
                "document_confidence": 0.73,
                "timeline_signals": [{"signal": "2학년 1학기"}],
                "major_alignment_hints": [{"hint": "전공 연계 활동 문장"}],
                "weak_or_missing_sections": [{"section": "독서", "status": "missing"}],
                "uncertainties": [{"message": "독서 관련 근거가 제한적입니다."}],
            }
        },
        content_markdown="",
        content_text="",
    )

    block = _format_document_analysis_block([document])

    assert "구조 신뢰도" in block
    assert "학기/연도 신호" in block
    assert "전공 연계 힌트" in block
    assert "보강 필요 섹션" in block
    assert "불확실성" in block
    assert "??" not in block


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
        user_message="문서 근거를 알려줘",
    )

    assert "연결된 프로젝트가 없어" in context
    assert "문서 근거 사용 원칙" in context
    assert "추측으로 학생 활동을 만들지 않습니다" in context
    assert "??" not in context


def test_format_chunk_evidence_block_handles_empty() -> None:
    block = _format_chunk_evidence_block([])

    assert "질문 관련 문서 발췌" in block
    assert "찾지 못했습니다" in block
    assert "??" not in block


def test_grounding_profile_limits_fast_and_render(monkeypatch) -> None:
    import unifoli_api.services.workshop_document_grounding_service as svc

    captured: dict[str, int] = {}

    def fake_docs(*, db, project_id, limit):  # noqa: ANN001
        captured["docs"] = limit
        return []

    def fake_chunks(*, db, project_id, limit):  # noqa: ANN001
        captured["chunk_pool"] = limit
        return []

    monkeypatch.setattr(svc, "_load_recent_documents", fake_docs)
    monkeypatch.setattr(svc, "_load_recent_chunks", fake_chunks)

    project = SimpleNamespace(id="project-1")
    svc.build_workshop_document_grounding_context(db=None, project=project, user_message="질문", profile="fast")
    assert captured["docs"] == 1

    svc.build_workshop_document_grounding_context(db=None, project=project, user_message="질문", profile="render")
    assert captured["docs"] == 3
