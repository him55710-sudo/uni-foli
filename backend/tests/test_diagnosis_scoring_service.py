from __future__ import annotations

from polio_api.services.diagnosis_scoring_service import build_diagnosis_scoring_sheet
from polio_api.services.student_record_feature_service import StudentRecordFeatures


def _sample_features() -> StudentRecordFeatures:
    return StudentRecordFeatures(
        source_mode="neis",
        document_count=1,
        total_word_count=1800,
        total_records=14,
        section_presence={
            "교과학습발달상황": True,
            "창의적체험활동": True,
            "행동특성 및 종합의견": True,
            "독서활동": False,
            "수상경력": True,
        },
        section_record_counts={
            "교과학습발달상황": 7,
            "창의적체험활동": 3,
            "행동특성 및 종합의견": 2,
            "독서활동": 0,
            "수상경력": 2,
        },
        subject_distribution={"수학": 4, "물리": 3, "정보": 3},
        unique_subject_count=3,
        narrative_char_count=4200,
        narrative_density=0.58,
        evidence_reference_count=11,
        evidence_density=0.72,
        repeated_subject_ratio=0.55,
        major_term_overlap_ratio=0.62,
        avg_parse_confidence=0.81,
        reliability_score=0.79,
        needs_review=False,
        needs_review_documents=0,
        risk_flags=[],
    )


def test_scoring_service_is_deterministic() -> None:
    features = _sample_features()

    first = build_diagnosis_scoring_sheet(
        features=features,
        project_title="determinism-check",
        target_major="컴퓨터공학",
        target_university="테스트대학교",
    )
    second = build_diagnosis_scoring_sheet(
        features=features,
        project_title="determinism-check",
        target_major="컴퓨터공학",
        target_university="테스트대학교",
    )

    assert first.model_dump() == second.model_dump()
    assert len(first.admission_axes) == 5
    assert {axis.key for axis in first.admission_axes} == {
        "major_alignment",
        "inquiry_continuity",
        "evidence_density",
        "process_explanation",
        "authenticity_risk",
    }
    assert all(0 <= axis.score <= 100 for axis in first.admission_axes)
    assert first.document_quality.parse_reliability_score >= 0
