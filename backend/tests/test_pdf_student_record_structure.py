from __future__ import annotations

from unifoli_api.services.pdf_analysis_service import build_student_record_structure_metadata
from unifoli_ingest.models import ParsedChunkPayload, ParsedDocumentPayload


def test_build_student_record_structure_metadata_extracts_core_fields() -> None:
    parsed = ParsedDocumentPayload(
        parser_name="neis",
        source_extension=".pdf",
        page_count=3,
        word_count=300,
        content_text=(
            "2학년 1학기 교과학습발달상황에서 데이터 분석 탐구를 수행했다. "
            "연속 활동으로 비교 실험을 진행하고 과정과 한계를 성찰했다. "
            "진로 연계 문장을 통해 전공 적합성을 설명했다."
        ),
        content_markdown="",
        metadata={},
        chunks=[
            ParsedChunkPayload(
                chunk_index=0,
                page_number=1,
                char_start=0,
                char_end=120,
                token_estimate=40,
                content_text="교과학습발달상황 데이터 분석 탐구",
            )
        ],
        raw_artifact={
            "pages": [
                {"page_number": 1, "text": "교과학습발달상황 세부능력 및 특기사항 데이터 분석 탐구"},
                {"page_number": 2, "text": "창의적 체험활동 동아리 진로활동 비교 실험"},
                {"page_number": 3, "text": "행동특성 및 종합의견 과정 성찰 전공 적합성"},
            ]
        },
        masked_artifact={},
        analysis_artifact={},
        parse_confidence=0.8,
        needs_review=False,
    )

    structure = build_student_record_structure_metadata(
        parsed=parsed,
        pdf_analysis={"engine": "llm", "summary": "요약"},
        analysis_artifact=None,
    )

    assert structure is not None
    assert "major_sections" in structure
    assert "section_density" in structure
    assert "timeline_signals" in structure
    assert "subject_major_alignment_signals" in structure
    assert "continuity_signals" in structure
    assert "process_reflection_signals" in structure
    assert structure["evidence_bank"]
