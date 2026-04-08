from __future__ import annotations

from collections import Counter
import re
from typing import Any

from pydantic import BaseModel, Field


_SECTION_KEYS = (
    "교과학습발달상황",
    "창의적체험활동",
    "행동특성 및 종합의견",
    "독서활동",
    "수상경력",
)
_TOKEN_RE = re.compile(r"[A-Za-z가-힣]{2,}")


class StudentRecordFeatures(BaseModel):
    source_mode: str
    document_count: int
    total_word_count: int
    total_records: int
    section_presence: dict[str, bool] = Field(default_factory=dict)
    section_record_counts: dict[str, int] = Field(default_factory=dict)
    subject_distribution: dict[str, int] = Field(default_factory=dict)
    unique_subject_count: int = 0
    narrative_char_count: int = 0
    narrative_density: float = 0.0
    evidence_reference_count: int = 0
    evidence_density: float = 0.0
    repeated_subject_ratio: float = 0.0
    major_term_overlap_ratio: float = 0.0
    avg_parse_confidence: float = 0.0
    reliability_score: float = 0.0
    needs_review: bool = False
    needs_review_documents: int = 0
    risk_flags: list[str] = Field(default_factory=list)


def extract_student_record_features(
    *,
    documents: list[Any],
    full_text: str,
    target_major: str | None,
    career_direction: str | None,
) -> StudentRecordFeatures:
    section_presence = {key: False for key in _SECTION_KEYS}
    section_record_counts = {key: 0 for key in _SECTION_KEYS}
    subject_counter: Counter[str] = Counter()
    parse_confidences: list[float] = []
    all_text_parts: list[str] = []
    total_word_count = 0
    total_records = 0
    narrative_char_count = 0
    evidence_reference_count = 0
    needs_review_documents = 0
    saw_neis = False

    for document in documents:
        text = str(getattr(document, "content_text", "") or getattr(document, "content_markdown", "") or "")
        metadata = getattr(document, "parse_metadata", None) or {}
        if not isinstance(metadata, dict):
            metadata = {}

        total_word_count += len(text.split())
        if text.strip():
            all_text_parts.append(text)

        parse_confidence = _coerce_float(metadata.get("parse_confidence"), default=0.55)
        parse_confidences.append(parse_confidence)
        if bool(metadata.get("needs_review")):
            needs_review_documents += 1

        # Structured Data Extraction (New Pipeline or Legacy NEIS)
        structured_data = _extract_structured_data(metadata)
        if structured_data:
            saw_neis = True
            # New Pipeline Structure (v2.0.0+)
            if "canonical_data" in structured_data:
                canonical = structured_data["canonical_data"]
                quality_report = structured_data.get("quality_report") or {}
                
                # Update confidence and reliability from quality report
                if quality_report and "overall_score" in quality_report:
                    parse_confidences.append(float(quality_report["overall_score"]))
                
                # Section mapping and record counting
                # Attendance
                if canonical.get("attendance"):
                    section_presence["교과학습발달상황"] = True # Attendance usually in the same section or nearby
                    section_record_counts["교과학습발달상황"] += len(canonical["attendance"])
                
                # Awards
                if canonical.get("awards"):
                    section_presence["수상경력"] = True
                    section_record_counts["수상경력"] += len(canonical["awards"])
                    total_records += len(canonical["awards"])
                
                # Grades
                grades = canonical.get("grades") or []
                if grades:
                    section_presence["교과학습발달상황"] = True
                    section_record_counts["교과학습발달상황"] += len(grades)
                    total_records += len(grades)
                    for g in grades:
                        subj = _normalize_subject(g.get("subject"))
                        if subj:
                            subject_counter[subj] += 1
                
                # Narratives (Extracurricular)
                extra = canonical.get("extracurricular_narratives") or {}
                if extra:
                    section_presence["창의적체험활동"] = True
                    section_record_counts["창의적체험활동"] += len(extra)
                    for k, v in extra.items():
                        narrative_char_count += len(str(v).strip())
                
                # Subject Notes
                subj_notes = canonical.get("subject_special_notes") or {}
                if subj_notes:
                    section_presence["교과학습발달상황"] = True
                    section_record_counts["교과학습발달상황"] += len(subj_notes)
                    for k, v in subj_notes.items():
                        narrative_char_count += len(str(v).strip())
                
                # Reading
                reading = canonical.get("reading_activities") or []
                if reading:
                    section_presence["독서활동"] = True
                    section_record_counts["독서활동"] += len(reading)
                    for r in reading:
                        narrative_char_count += len(str(r).strip())
                
                # Behavior
                behavior = canonical.get("behavior_opinion")
                if behavior:
                    section_presence["행동특성 및 종합의견"] = True
                    section_record_counts["행동특성 및 종합의견"] += 1
                    narrative_char_count += len(str(behavior).strip())
                
                continue # Skip fallback text inference

            # Legacy NEIS Structure
            sections = structured_data.get("sections")
            if isinstance(sections, list):
                for section in sections:
                    if not isinstance(section, dict):
                        continue
                    section_key = _normalize_section_type(section.get("section_type"))
                    records = section.get("records")
                    record_items = records if isinstance(records, list) else []
                    if section_key in section_presence:
                        section_presence[section_key] = True
                        section_record_counts[section_key] += len(record_items)
                    total_records += len(record_items)

                    for record in record_items:
                        if not isinstance(record, dict):
                            continue
                        subject_name = _normalize_subject(record.get("subject_name"))
                        if subject_name:
                            subject_counter[subject_name] += 1
                        narrative = _first_non_empty(
                            record.get("special_notes_text"),
                            record.get("masked_text"),
                            record.get("normalized_text"),
                            "",
                        )
                        narrative_char_count += len(str(narrative).strip())

            evidence_refs = structured_data.get("evidence_references")
            if isinstance(evidence_refs, list):
                evidence_reference_count += len(evidence_refs)
            continue

        total_records += max(1, min(12, len(text) // 280))
        evidence_reference_count += max(1, len(text) // 600)
        narrative_char_count += min(len(text), 1800)
        _infer_sections_from_text(text, section_presence, section_record_counts)

    if not all_text_parts and full_text.strip():
        all_text_parts.append(full_text)
    if total_word_count == 0 and full_text.strip():
        total_word_count = len(full_text.split())
    if total_records == 0:
        total_records = max(1, len(full_text) // 240)
    if evidence_reference_count == 0:
        evidence_reference_count = max(1, len(full_text) // 700)

    total_subject_mentions = sum(subject_counter.values())
    repeated_subject_mentions = sum(count for count in subject_counter.values() if count >= 2)
    repeated_subject_ratio = (
        _clamp(repeated_subject_mentions / total_subject_mentions)
        if total_subject_mentions > 0
        else 0.0
    )
    evidence_density = _clamp(evidence_reference_count / max(total_records, 1))
    narrative_density = _clamp(narrative_char_count / max(total_word_count * 6, 1))

    major_terms = _major_terms(target_major=target_major, career_direction=career_direction)
    overlap_ratio = _major_overlap_ratio(major_terms=major_terms, corpus=" ".join(all_text_parts))

    avg_parse_confidence = sum(parse_confidences) / max(len(parse_confidences), 1)
    review_ratio = needs_review_documents / max(len(documents), 1)
    reliability_score = _clamp(avg_parse_confidence * (1.0 - review_ratio * 0.45))

    risk_flags: list[str] = []
    if needs_review_documents > 0:
        risk_flags.append("일부 문서가 needs_review 상태입니다.")
    if evidence_density < 0.35:
        risk_flags.append("근거 밀도가 낮아 주장 검증 여유가 부족합니다.")
    if overlap_ratio < 0.25 and major_terms:
        risk_flags.append("목표 전공 관련 키워드가 기록 전반에 충분히 드러나지 않습니다.")

    source_mode = "neis" if saw_neis else "text"
    if saw_neis and needs_review_documents > 0:
        source_mode = "mixed"

    return StudentRecordFeatures(
        source_mode=source_mode,
        document_count=len(documents),
        total_word_count=total_word_count,
        total_records=total_records,
        section_presence=section_presence,
        section_record_counts=section_record_counts,
        subject_distribution=dict(subject_counter.most_common(30)),
        unique_subject_count=len(subject_counter),
        narrative_char_count=narrative_char_count,
        narrative_density=narrative_density,
        evidence_reference_count=evidence_reference_count,
        evidence_density=evidence_density,
        repeated_subject_ratio=repeated_subject_ratio,
        major_term_overlap_ratio=overlap_ratio,
        avg_parse_confidence=round(avg_parse_confidence, 3),
        reliability_score=round(reliability_score, 3),
        needs_review=needs_review_documents > 0,
        needs_review_documents=needs_review_documents,
        risk_flags=risk_flags,
    )


def _extract_structured_data(metadata: dict[str, Any]) -> dict[str, Any] | None:
    """
    Extracts structured parsing data from document metadata.
    Supports both the new semantic pipeline (v2.0.0+) and legacy NEIS formats.
    """
    candidates: list[Any] = [
        metadata.get("analysis_artifact"),
        metadata.get("student_artifact_parse"),
    ]
    for artifact in candidates:
        if not isinstance(artifact, dict):
            continue
        
        # New Pipeline: check for 'canonical_data'
        if "canonical_data" in artifact:
            return artifact
            
        # Standard/Legacy: check for 'neis_document' wrapping
        neis_document = artifact.get("neis_document")
        if isinstance(neis_document, dict):
            return neis_document
            
        # Legacy: direct identification
        if artifact.get("document_type") == "neis_student_record" and isinstance(artifact.get("sections"), list):
            return artifact
            
    return None


def _normalize_section_type(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    for key in _SECTION_KEYS:
        if key in text:
            return key
    return text


def _normalize_subject(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    return re.sub(r"\s+", " ", text)[:80]


def _infer_sections_from_text(
    text: str,
    section_presence: dict[str, bool],
    section_record_counts: dict[str, int],
) -> None:
    if not text:
        return
    compact = re.sub(r"\s+", " ", text)
    for key in _SECTION_KEYS:
        if key in compact:
            section_presence[key] = True
            section_record_counts[key] = max(section_record_counts[key], 1)


def _major_terms(*, target_major: str | None, career_direction: str | None) -> list[str]:
    merged = f"{target_major or ''} {career_direction or ''}".strip()
    if not merged:
        return []
    tokens = [token.lower() for token in _TOKEN_RE.findall(merged) if len(token) >= 2]
    dedup: list[str] = []
    seen: set[str] = set()
    for token in tokens:
        if token in seen:
            continue
        seen.add(token)
        dedup.append(token)
    return dedup[:12]


def _major_overlap_ratio(*, major_terms: list[str], corpus: str) -> float:
    if not major_terms:
        return 0.0
    lowered = corpus.lower()
    hit_count = sum(1 for term in major_terms if term in lowered)
    return _clamp(hit_count / len(major_terms))


def _coerce_float(value: Any, *, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _first_non_empty(*values: Any) -> str:
    for item in values:
        text = str(item or "").strip()
        if text:
            return text
    return ""


def _clamp(value: float, minimum: float = 0.0, maximum: float = 1.0) -> float:
    return max(minimum, min(maximum, value))
