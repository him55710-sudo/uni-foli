from __future__ import annotations

from unifoli_api.services.document_service import (
    _apply_degraded_flags_to_student_record_metadata,
    _mark_advanced_pipeline_degraded,
)


def test_advanced_pipeline_failure_sets_provisional_quality_flags() -> None:
    metadata = {
        "warnings": [],
        "student_record_canonical": {
            "record_type": "korean_student_record_pdf",
            "quality_gates": {
                "evidence_anchor_count": 6,
                "evidence_page_count": 4,
                "reanalysis_required": False,
            },
        },
        "student_record_structure": {"major_sections": []},
    }

    _mark_advanced_pipeline_degraded(metadata, "table parser crashed")
    _apply_degraded_flags_to_student_record_metadata(metadata)

    assert metadata["pipeline_status"] == "failed"
    assert metadata["needs_review"] is True
    assert metadata["parse_quality"]["is_provisional"] is True
    assert "student_record_structure" in metadata["diagnosis_disabled_sections"]
    assert metadata["student_record_structure_disabled"] is True
    assert metadata["student_record_canonical"]["quality_gates"]["reanalysis_required"] is True
    assert metadata["student_record_canonical"]["quality_gates"]["advanced_pipeline_degraded"] is True
    assert metadata["student_record_canonical"]["uncertainties"]
