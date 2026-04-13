from __future__ import annotations

from types import SimpleNamespace

from unifoli_api.services import diagnosis_report_service as report_service


def test_collect_student_record_structure_reads_canonical_metadata() -> None:
    document = SimpleNamespace(
        parse_metadata={
            "student_record_canonical": {
                "timeline_signals": [{"signal": "2학년 1학기", "evidence": [{"page_number": 1}]}],
                "major_alignment_hints": [{"hint": "건축 관련 활동 강화", "evidence": [{"page_number": 2}]}],
                "weak_or_missing_sections": [{"section": "독서", "status": "missing", "evidence": [{"page_number": 3}]}],
                "uncertainties": [{"message": "일부 근거가 누락되었습니다.", "evidence": [{"page_number": 3}]}],
                "extracurricular": [{"label": "창체 활동:동아리", "evidence": [{"page_number": 2}]}],
                "subject_special_notes": [{"label": "세특 활동:탐구역량", "evidence": [{"page_number": 1}]}],
                "career_signals": [{"label": "진로 활동:건축", "evidence": [{"page_number": 2}]}],
                "section_classification": {
                    "grades_subjects": {"density": 0.7},
                    "subject_special_notes": {"density": 0.8},
                    "extracurricular": {"density": 0.6},
                    "career_signals": {"density": 0.5},
                    "reading_activity": {"density": 0.2},
                    "behavior_opinion": {"density": 0.4},
                },
            }
        }
    )

    structure = report_service._collect_student_record_structure([document])

    assert structure["section_density"]["교과학습발달상황"] == 0.7
    assert structure["section_density"]["세특"] == 0.8
    assert "독서" in structure["weak_sections"]
    assert "2학년 1학기" in structure["timeline_signals"]
    assert "건축 관련 활동 강화" in structure["subject_major_alignment_signals"]
    assert any("누락" in item for item in structure["uncertain_items"])
