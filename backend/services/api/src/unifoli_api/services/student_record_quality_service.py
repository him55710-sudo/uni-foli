from __future__ import annotations

from typing import Any
from pydantic import BaseModel

from unifoli_api.services.student_record_page_classifier_service import PageCategory, PageClassification
from unifoli_api.services.student_record_normalizer_service import StudentRecordCanonicalSchema


class QualityReport(BaseModel):
    overall_confidence: float
    missing_sections: list[PageCategory]
    is_sufficient_for_diagnosis: bool
    warnings: list[str]
    needs_review: bool
    
    # Task 2: Additional scores
    text_coverage_score: float = 0.0
    section_coverage_score: float = 0.0
    is_provisional: bool = False


class StudentRecordQualityService:
    """
    Quality evaluation service for student records.
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
        
        # Calculate granular scores for Task 2
        section_coverage_score = 1.0 - (len(report.missing_sections) / 5.0) # Assume 5 critical sections
        section_coverage_score = max(0.0, min(1.0, section_coverage_score))
        
        return {
            "overall_score": round(report.overall_confidence, 3),
            "text_coverage_score": round(report.text_coverage_score, 3),
            "section_coverage_score": round(section_coverage_score, 3),
            "missing_critical_sections": [item.value for item in report.missing_sections],
            "is_sufficient_for_diagnosis": report.is_sufficient_for_diagnosis,
            "is_provisional": report.is_provisional,
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
        PageCategory.BEHAVIOR,
        PageCategory.CAREER # Added for Task 2
    ]
    
    found_categories = {cls.category for cls in classifications}
    for req in required:
        if req not in found_categories:
            missing_sections.append(req)
            warnings.append(f"Essential section '{req.value}' is missing.")

    # Check for empty narratives
    has_narratives = False
    if canonical.extracurricular_narratives:
        has_narratives = True
    else:
        warnings.append("No extracurricular narratives found.")
        
    if not canonical.subject_special_notes:
        warnings.append("No subject-specific notes (세특) found.")

    # Calculate overall confidence
    if not classifications:
        avg_confidence = 0.0
    else:
        avg_confidence = sum(cls.confidence for cls in classifications) / len(classifications)

    # Task 2: Calculate text coverage based on field population
    populated_fields = 0
    total_fields = 5
    if canonical.student_name: populated_fields += 1
    if canonical.grades: populated_fields += 1
    if canonical.subject_special_notes: populated_fields += 1
    if canonical.extracurricular_narratives: populated_fields += 1
    if canonical.behavior_opinion: populated_fields += 1
    text_coverage = populated_fields / total_fields

    is_sufficient = len(missing_sections) <= 1 and avg_confidence > 0.5
    is_provisional = len(missing_sections) >= 3 or text_coverage < 0.4
    needs_review = not is_sufficient or len(warnings) > 2 or avg_confidence < 0.6 or is_provisional

    return QualityReport(
        overall_confidence=avg_confidence,
        missing_sections=missing_sections,
        is_sufficient_for_diagnosis=is_sufficient,
        warnings=warnings,
        needs_review=needs_review,
        text_coverage_score=text_coverage,
        is_provisional=is_provisional
    )
