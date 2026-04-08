from __future__ import annotations

from typing import Any
from pydantic import BaseModel

from polio_api.services.student_record_page_classifier_service import PageCategory, PageClassification
from polio_api.services.student_record_normalizer_service import StudentRecordCanonicalSchema


class QualityReport(BaseModel):
    overall_confidence: float
    missing_sections: list[PageCategory]
    is_sufficient_for_diagnosis: bool
    warnings: list[str]
    needs_review: bool


class StudentRecordQualityService:
    """
    Compatibility wrapper used by StudentRecordPipelineService.
    """

    def evaluate_quality(
        self,
        canonical_data: StudentRecordCanonicalSchema | dict[str, Any],
        sections: list[Any],
    ) -> dict[str, Any]:
        if isinstance(canonical_data, StudentRecordCanonicalSchema):
            canonical = canonical_data
        else:
            canonical = StudentRecordCanonicalSchema.model_validate(canonical_data)

        classifications: list[PageClassification] = []
        for section in sections:
            section_type = getattr(section, "section_type", PageCategory.UNKNOWN)
            start_page = int(getattr(section, "start_page", 1))
            end_page = int(getattr(section, "end_page", start_page))
            for page_number in range(start_page, end_page + 1):
                classifications.append(
                    PageClassification(
                        page_number=page_number,
                        category=section_type,
                        confidence=0.8,
                        matched_tokens=[],
                        is_continuation=page_number > start_page,
                    )
                )

        report = evaluate_quality(classifications, canonical)
        return {
            "overall_score": round(report.overall_confidence, 3),
            "overall_confidence": round(report.overall_confidence, 3),
            "missing_critical_sections": [item.value for item in report.missing_sections],
            "is_sufficient_for_diagnosis": report.is_sufficient_for_diagnosis,
            "warnings": report.warnings,
            "needs_review": report.needs_review,
        }


def evaluate_quality(
    classifications: list[PageClassification],
    canonical: StudentRecordCanonicalSchema
) -> QualityReport:
    """
    Evaluates the quality of the parsed student record.
    """
    warnings = []
    missing_sections = []
    
    # Required sections for a high-quality diagnosis
    required = [
        PageCategory.ATTENDANCE,
        PageCategory.GRADES_AND_NOTES,
        PageCategory.EXTRACURRICULAR,
        PageCategory.BEHAVIOR
    ]
    
    found_categories = {cls.category for cls in classifications}
    for req in required:
        if req not in found_categories:
            missing_sections.append(req)
            warnings.append(f"Essential section '{req.value}' is missing.")

    # Check for empty narratives
    if not canonical.extracurricular_narratives:
        warnings.append("No extracurricular narratives found.")
    if not canonical.subject_special_notes:
        warnings.append("No subject-specific notes (세특) found.")

    # Calculate overall confidence
    if not classifications:
        avg_confidence = 0.0
    else:
        avg_confidence = sum(cls.confidence for cls in classifications) / len(classifications)

    is_sufficient = len(missing_sections) <= 1 and avg_confidence > 0.5
    needs_review = not is_sufficient or len(warnings) > 2 or avg_confidence < 0.6

    return QualityReport(
        overall_confidence=avg_confidence,
        missing_sections=missing_sections,
        is_sufficient_for_diagnosis=is_sufficient,
        warnings=warnings,
        needs_review=needs_review
    )
