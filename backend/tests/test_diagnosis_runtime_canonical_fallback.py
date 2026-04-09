from __future__ import annotations

from types import SimpleNamespace

from polio_api.services.diagnosis_runtime_service import _extract_document_text


def test_extract_document_text_prefers_canonical_metadata_when_primary_text_missing() -> None:
    document = SimpleNamespace(
        content_text="",
        content_markdown="",
        parse_metadata={
            "student_record_canonical": {
                "document_confidence": 0.71,
                "timeline_signals": [{"signal": "2학년 1학기"}],
                "major_alignment_hints": [{"hint": "전공 연계 실험 활동"}],
                "grades_subjects": [{"subject": "수학"}],
                "uncertainties": [{"message": "일부 근거는 추가 확인 필요"}],
            }
        },
    )

    text = _extract_document_text(document)

    assert "student_record_confidence" in text
    assert "2학년 1학기" in text
    assert "전공 연계 실험 활동" in text
    assert "수학" in text
