from __future__ import annotations

import re
from typing import Optional

from pydantic import BaseModel, Field

from unifoli_api.services.student_record_page_classifier_service import PageCategory
from unifoli_api.services.student_record_section_parser_service import StudentRecordSection


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
    """Compatibility wrapper used by StudentRecordPipelineService."""

    def normalize_sections(self, sections: list[StudentRecordSection]) -> StudentRecordCanonicalSchema:
        return normalize_sections(sections)


def normalize_sections(sections: list[StudentRecordSection]) -> StudentRecordCanonicalSchema:
    canonical = StudentRecordCanonicalSchema()

    for section in sections:
        if section.section_type == PageCategory.ATTENDANCE:
            canonical.attendance.extend(_parse_attendance(section))
        elif section.section_type == PageCategory.AWARDS:
            canonical.awards.extend(_parse_awards(section))
        elif section.section_type == PageCategory.GRADES_AND_NOTES:
            canonical.grades.extend(_parse_grades(section))
            canonical.subject_special_notes.update(_parse_subject_notes(section))
        elif section.section_type == PageCategory.EXTRACURRICULAR:
            canonical.extracurricular_narratives.update(_parse_extracurricular(section))
        elif section.section_type == PageCategory.READING:
            canonical.reading_activities.extend(_parse_reading(section))
        elif section.section_type == PageCategory.BEHAVIOR:
            canonical.behavior_opinion = (section.raw_text or "").strip() or None
        elif section.section_type == PageCategory.STUDENT_INFO:
            _extract_student_info(section, canonical)

    return canonical


def _parse_attendance(section: StudentRecordSection) -> list[AttendanceEntry]:
    entries: list[AttendanceEntry] = []
    for match in re.finditer(r"(\d)학년", section.raw_text or ""):
        entries.append(AttendanceEntry(grade=int(match.group(1)), school_days=0))
    return entries


def _parse_awards(section: StudentRecordSection) -> list[AwardEntry]:
    entries: list[AwardEntry] = []
    for table in section.tables:
        rows = table.get("rows", [])
        if not rows:
            continue
        for row in rows[1:]:
            cells = [str(cell.get("text", "")).strip() for cell in row if isinstance(cell, dict)]
            if not cells or not cells[0]:
                continue
            entries.append(
                AwardEntry(
                    award_name=cells[0],
                    grade=cells[1] if len(cells) >= 2 else None,
                    date=cells[2] if len(cells) >= 3 else None,
                    host=cells[3] if len(cells) >= 4 else None,
                    participation=cells[4] if len(cells) >= 5 else None,
                )
            )
    return entries


def _parse_grades(section: StudentRecordSection) -> list[GradeEntry]:
    entries: list[GradeEntry] = []
    for table in section.tables:
        rows = table.get("rows", [])
        for row in rows[1:]:
            cells = [str(cell.get("text", "")).strip() for cell in row if isinstance(cell, dict)]
            if not cells or not cells[0]:
                continue
            unit = _to_int(cells[1]) if len(cells) >= 2 else None
            entries.append(
                GradeEntry(
                    subject=cells[0],
                    unit=unit,
                    original_score=_to_float(cells[2]) if len(cells) >= 3 else None,
                    average=_to_float(cells[3]) if len(cells) >= 4 else None,
                    achievement=cells[4] if len(cells) >= 5 else None,
                    rank=cells[5] if len(cells) >= 6 else None,
                )
            )
    return entries


def _parse_subject_notes(section: StudentRecordSection) -> dict[str, str]:
    notes: dict[str, str] = {}
    text = section.raw_text or ""
    matches = re.finditer(r"\[([^\]]+)\]\s*(.*?)(?=\[[^\]]+\]|$)", text, re.DOTALL)
    for match in matches:
        subject = match.group(1).strip()
        note = match.group(2).strip()
        if subject and note:
            notes[subject] = note
    return notes


def _parse_extracurricular(section: StudentRecordSection) -> dict[str, str]:
    narratives: dict[str, str] = {}
    text = section.raw_text or ""
    headers = ["자율활동", "동아리활동", "진로활동", "봉사활동"]
    for header in headers:
        match = re.search(
            rf"{re.escape(header)}\s*(.*?)(?={'|'.join(re.escape(value) for value in headers)}|$)",
            text,
            re.DOTALL,
        )
        if match:
            content = match.group(1).strip()
            if content:
                narratives[header] = content
    return narratives


def _parse_reading(section: StudentRecordSection) -> list[str]:
    text = (section.raw_text or "").strip()
    return [text] if text else []


def _extract_student_info(section: StudentRecordSection, canonical: StudentRecordCanonicalSchema) -> None:
    text = section.raw_text or ""

    name_match = re.search(
        r"(?:학생정보|인적[·ㆍ.\s]*학적사항)?.{0,180}?(?<!담임)성\s*명\s*[:：]?\s*(?:\|\s*)?([가-힣]{2,5})(?=\s*(?:\||성별|주민|$))",
        re.sub(r"\s+", " ", text),
    )
    if name_match:
        canonical.student_name = name_match.group(1)

    school_match = re.search(r"([가-힣A-Za-z0-9 ]+고등학교)", text)
    if school_match:
        canonical.school_name = school_match.group(1).strip()


def _to_int(value: str | None) -> int | None:
    if not value:
        return None
    digits = re.sub(r"[^\d-]", "", value)
    if not digits:
        return None
    try:
        return int(digits)
    except ValueError:
        return None


def _to_float(value: str | None) -> float | None:
    if not value:
        return None
    normalized = re.sub(r"[^0-9.\-]", "", value)
    if not normalized:
        return None
    try:
        return float(normalized)
    except ValueError:
        return None
