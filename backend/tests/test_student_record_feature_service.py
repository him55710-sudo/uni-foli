from __future__ import annotations

from types import SimpleNamespace

from polio_api.services.student_record_feature_service import extract_student_record_features


def test_extract_features_from_neis_like_metadata() -> None:
    neis_document = {
        "sections": [
            {
                "section_type": "교과학습발달상황",
                "records": [
                    {"subject_name": "수학", "special_notes_text": "문제 해결 과정을 정리함"},
                    {"subject_name": "물리", "special_notes_text": "실험 결과를 비교함"},
                ],
            },
            {
                "section_type": "창의적체험활동",
                "records": [
                    {"subject_name": "동아리", "special_notes_text": "프로젝트 리더 역할 수행"},
                ],
            },
        ],
        "evidence_references": [{"id": "ref-1"}, {"id": "ref-2"}, {"id": "ref-3"}],
    }
    document = SimpleNamespace(
        content_text="교과학습발달상황 기록과 창의적체험활동 기록",
        content_markdown="",
        parse_metadata={
            "parse_confidence": 0.82,
            "needs_review": False,
            "analysis_artifact": {"neis_document": neis_document},
        },
    )

    features = extract_student_record_features(
        documents=[document],
        full_text=document.content_text,
        target_major="컴퓨터공학",
        career_direction="소프트웨어 개발",
    )

    assert features.source_mode == "neis"
    assert features.section_presence["교과학습발달상황"] is True
    assert features.section_presence["창의적체험활동"] is True
    assert features.section_record_counts["교과학습발달상황"] == 2
    assert features.total_records >= 3
    assert features.evidence_reference_count == 3
    assert "수학" in features.subject_distribution
    assert features.reliability_score > 0.7


def test_extract_features_gracefully_without_neis_structure() -> None:
    document = SimpleNamespace(
        content_text="행동특성 및 종합의견에 탐구 과정과 반성이 정리되어 있음",
        content_markdown="",
        parse_metadata={"parse_confidence": 0.6, "needs_review": True},
    )

    features = extract_student_record_features(
        documents=[document],
        full_text=document.content_text,
        target_major="경영학",
        career_direction="데이터 분석",
    )

    assert features.source_mode == "text"
    assert features.total_records >= 1
    assert features.evidence_reference_count >= 1
    assert features.needs_review is True
    assert features.needs_review_documents == 1
