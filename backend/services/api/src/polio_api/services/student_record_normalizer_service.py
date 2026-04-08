from __future__ import annotations

import re
from typing import Any, Optional
from pydantic import BaseModel, Field

from polio_api.services.student_record_page_classifier_service import PageCategory
from polio_api.services.student_record_section_parser_service import StudentRecordSection


class GradeEntry(BaseModel):
    subject: str
    unit: Optional[int] = None
    original_score: Optional[float] = None
    average: Optional[float] = None
    standard_deviation: Optional[float] = None
    achievement: Optional[str] = None
    rank: Optional[str] = None
    number_of_students: Optional[int] = None


class AwardEntry(BaseModel):
    award_name: str
    grade: Optional[str] = None
    date: Optional[str] = None
    host: Optional[str] = None
    participation: Optional[str] = None


class AttendanceEntry(BaseModel):
    grade: int
    school_days: int
    absent_disease: int = 0
    absent_unauthorized: int = 0
    absent_etc: int = 0
    late: int = 0
    early_leave: int = 0


class StudentRecordCanonicalSchema(BaseModel):
    student_name: Optional[str] = None
    school_name: Optional[str] = None
    attendance: list[AttendanceEntry] = Field(default_factory=list)
    awards: list[AwardEntry] = Field(default_factory=list)
    grades: list[GradeEntry] = Field(default_factory=list)
    extracurricular_narratives: dict[str, str] = Field(default_factory=dict)
    subject_special_notes: dict[str, str] = Field(default_factory=dict)
    reading_activities: list[str] = Field(default_factory=list)
    behavior_opinion: Optional[str] = None


class StudentRecordNormalizerService:
    """
    Compatibility wrapper used by StudentRecordPipelineService.
    """

    def normalize_sections(self, sections: list[StudentRecordSection]) -> StudentRecordCanonicalSchema:
        return normalize_sections(sections)


def normalize_sections(sections: list[StudentRecordSection]) -> StudentRecordCanonicalSchema:
    """
    Normalizes a list of sections into a canonical schema.
    """
    canonical = StudentRecordCanonicalSchema()
    
    for section in sections:
        if section.section_type == PageCategory.ATTENDANCE:
            canonical.attendance.extend(_parse_attendance(section))
        elif section.section_type == PageCategory.AWARDS:
            canonical.awards.extend(_parse_awards(section))
        elif section.section_type == PageCategory.GRADES_AND_NOTES:
            # Separating grades (tables) and notes (text)
            canonical.grades.extend(_parse_grades(section))
            canonical.subject_special_notes.update(_parse_subject_notes(section))
        elif section.section_type == PageCategory.EXTRACURRICULAR:
            canonical.extracurricular_narratives.update(_parse_extracurricular(section))
        elif section.section_type == PageCategory.READING:
            canonical.reading_activities.extend(_parse_reading(section))
        elif section.section_type == PageCategory.BEHAVIOR:
            canonical.behavior_opinion = section.raw_text
        elif section.section_type == PageCategory.STUDENT_INFO:
            _extract_student_info(section, canonical)

    return canonical


def _parse_attendance(section: StudentRecordSection) -> list[AttendanceEntry]:
    # Placeholder: Extracting attendance info from tables or text
    entries = []
    # Implementation details would go here
    return entries


def _parse_awards(section: StudentRecordSection) -> list[AwardEntry]:
    entries = []
    for table in section.tables:
        rows = table.get("rows", [])
        if not rows:
            continue
        # Check if it looks like an award table
        # Structure: 수상명 | 등급(위) | 수상연월일 | 수여기관 | 참가대상(인원)
        for row in rows[1:]: # Skip header
             cells = [str(c.get("text", "")).strip() for c in row if isinstance(c, dict)]
             if len(cells) >= 1:
                 entries.append(AwardEntry(
                     award_name=cells[0],
                     grade=cells[1] if len(cells) >= 2 else None,
                     date=cells[2] if len(cells) >= 3 else None,
                     host=cells[3] if len(cells) >= 4 else None,
                     participation=cells[4] if len(cells) >= 5 else None,
                 ))
    return entries


def _parse_grades(section: StudentRecordSection) -> list[GradeEntry]:
    entries = []
    for table in section.tables:
        rows = table.get("rows", [])
        # Placeholder for complex grade table parsing
    return entries


def _parse_subject_notes(section: StudentRecordSection) -> dict[str, str]:
    notes = {}
    # Extract narratives like "국어: ~~~"
    text = section.raw_text
    matches = re.finditer(r"\[([^\]]+)\]\s*(.*?)(?=\[|$)", text, re.DOTALL)
    for match in matches:
        subject = match.group(1).strip()
        note = match.group(2).strip()
        if subject and note:
            notes[subject] = note
    return notes


def _parse_extracurricular(section: StudentRecordSection) -> dict[str, str]:
    narratives = {}
    text = section.raw_text
    # Common headers: 자율활동, 동아리활동, 진로활동, 봉사활동
    for header in ["자율활동", "동아리활동", "진로활동", "봉사활동"]:
        match = re.search(rf"{header}\s*(.*?)(?=자율활동|동아리활동|진로활동|봉사활동|$)", text, re.DOTALL)
        if match:
            narratives[header] = match.group(1).strip()
    return narratives


def _parse_reading(section: StudentRecordSection) -> list[str]:
    # Reading activities are usually grade-wise
    return [section.raw_text]


def _extract_student_info(section: StudentRecordSection, canonical: StudentRecordCanonicalSchema) -> None:
    text = section.raw_text
    name_match = re.search(r"성\s*명\s*:\s*([가-힣]{2,4})", text)
    if name_match:
        canonical.student_name = name_match.group(1)
    
    school_match = re.search(r"([가-힣]+고등학교)", text)
    if school_match:
        canonical.school_name = school_match.group(1)
