from __future__ import annotations

from collections import Counter
import logging
import re
from typing import Any

from pydantic import BaseModel, Field


_SECTION_KEYS = (
    "교과학습발달상황",
    "창의적 체험활동",
    "행동특성 및 종합의견",
    "독서활동",
    "수상경력",
)
_TOKEN_RE = re.compile(r"[A-Za-z가-힣]{2,}")
logger = logging.getLogger("unifoli.api.student_record_features")

_MAJOR_TRACK_KEYWORDS: dict[str, tuple[str, ...]] = {
    "architecture": (
        "건축",
        "건축학",
        "건축공학",
        "건축환경",
        "스마트빌딩",
        "구조설계",
        "구조 안전",
        "도시설계",
        "공간설계",
        "건축자재",
        "하중",
        "내진",
        "제진",
        "면진",
        "BIM",
        "CLT",
    ),
    "mechanical_computer": (
        "기계",
        "기계공학",
        "전자",
        "전자공학",
        "컴퓨터",
        "컴퓨터공학",
        "하드웨어",
        "소프트웨어",
        "프로그래밍",
        "알고리즘",
        "전동화",
        "배터리",
        "반도체",
        "공정",
        "센서",
        "제어",
        "로봇",
        "모빌리티",
        "자동차",
    ),
    "bio_medical": (
        "생명",
        "생명과학",
        "의학",
        "의료",
        "간호",
        "바이오",
        "유전",
        "세포",
        "질병",
        "약학",
    ),
    "business_social": (
        "경영",
        "경제",
        "회계",
        "마케팅",
        "사회",
        "정책",
        "행정",
        "법학",
        "국제",
        "무역",
    ),
    "humanities_education": (
        "국어",
        "문학",
        "역사",
        "철학",
        "교육",
        "심리",
        "언어",
        "영어",
        "인문",
    ),
    "energy_environment": (
        "환경",
        "에너지",
        "기후",
        "탄소",
        "재생",
        "전력",
        "수소",
        "태양광",
        "풍력",
    ),
}
_MAJOR_TRACK_LABELS: dict[str, str] = {
    "architecture": "건축·도시",
    "mechanical_computer": "기계·컴퓨터",
    "bio_medical": "생명·의학",
    "business_social": "경영·사회",
    "humanities_education": "인문·교육",
    "energy_environment": "환경·에너지",
}


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
    major_signal_counts: dict[str, int] = Field(default_factory=dict)
    target_major_track: str | None = None
    target_major_track_label: str | None = None
    dominant_major_track: str | None = None
    dominant_major_track_label: str | None = None
    target_major_evidence_count: int = 0
    target_major_alignment_level: str = "unknown"
    target_major_alignment_note: str | None = None
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
    saw_structured = False

    for document in documents:
        text = str(getattr(document, "content_text", "") or getattr(document, "content_markdown", "") or "")
        metadata = getattr(document, "parse_metadata", None)
        if not isinstance(metadata, dict):
            metadata = {}

        if text.strip():
            all_text_parts.append(text)
            total_word_count += len(text.split())

        parse_confidence = _coerce_float(metadata.get("parse_confidence"), default=0.55)
        parse_confidences.append(parse_confidence)
        if bool(metadata.get("needs_review")):
            needs_review_documents += 1

        structured_data = _extract_structured_data(metadata)
        if structured_data:
            saw_structured = True
            evidence_ref = [evidence_reference_count]
            total_ref = [total_records]
            narrative_ref = [narrative_char_count]
            if _consume_canonical_data(
                structured_data=structured_data,
                section_presence=section_presence,
                section_record_counts=section_record_counts,
                subject_counter=subject_counter,
                evidence_reference_count_ref=evidence_ref,
                total_records_ref=total_ref,
                narrative_char_count_ref=narrative_ref,
            ):
                evidence_reference_count = max(0, int(evidence_ref[0]))
                total_records = max(0, int(total_ref[0]))
                narrative_char_count = max(0, int(narrative_ref[0]))
                continue

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

        # Text fallback path
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

    corpus = " ".join(all_text_parts)
    major_terms = _major_terms(target_major=target_major, career_direction=career_direction)
    overlap_ratio = _major_overlap_ratio(major_terms=major_terms, corpus=corpus)
    signal_counts = _major_signal_counts(corpus)
    target_track = _infer_major_track(f"{target_major or ''} {career_direction or ''}")
    dominant_track = _dominant_major_track(signal_counts)
    alignment_level, alignment_note = _major_alignment(
        target_major=target_major,
        target_track=target_track,
        dominant_track=dominant_track,
        signal_counts=signal_counts,
    )
    target_evidence_count = int(signal_counts.get(target_track or "", 0)) if target_track else 0

    avg_parse_confidence = sum(parse_confidences) / max(len(parse_confidences), 1)
    review_ratio = needs_review_documents / max(len(documents), 1)
    reliability_score = _clamp(avg_parse_confidence * (1.0 - review_ratio * 0.45))

    risk_flags: list[str] = []
    if needs_review_documents > 0:
        risk_flags.append("일부 문서가 needs_review 상태입니다.")
    if evidence_density < 0.35:
        risk_flags.append("학생부 근거가 충분히 자주, 구체적으로 드러나지 않아 주요 주장 검증 신뢰가 부족합니다.")
    if overlap_ratio < 0.25 and major_terms:
        risk_flags.append("목표 전공 관련 키워드가 기록 전반에 충분히 드러나지 않습니다.")
    if alignment_level in {"mismatch", "weak"} and alignment_note:
        risk_flags.append(alignment_note)

    source_mode = "structured" if saw_structured else "text"
    if saw_structured and needs_review_documents > 0:
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
        major_signal_counts=signal_counts,
        target_major_track=target_track,
        target_major_track_label=_MAJOR_TRACK_LABELS.get(target_track or ""),
        dominant_major_track=dominant_track,
        dominant_major_track_label=_MAJOR_TRACK_LABELS.get(dominant_track or ""),
        target_major_evidence_count=target_evidence_count,
        target_major_alignment_level=alignment_level,
        target_major_alignment_note=alignment_note,
        avg_parse_confidence=round(avg_parse_confidence, 3),
        reliability_score=round(reliability_score, 3),
        needs_review=needs_review_documents > 0,
        needs_review_documents=needs_review_documents,
        risk_flags=risk_flags,
    )


def _consume_canonical_data(
    *,
    structured_data: dict[str, Any],
    section_presence: dict[str, bool],
    section_record_counts: dict[str, int],
    subject_counter: Counter[str],
    evidence_reference_count_ref: list[int],
    total_records_ref: list[int],
    narrative_char_count_ref: list[int],
) -> bool:
    canonical = structured_data.get("canonical_data")
    if not isinstance(canonical, dict):
        return False

    quality_report = structured_data.get("quality_report")
    if isinstance(quality_report, dict):
        quality_score = _coerce_optional_float(quality_report.get("overall_score"))
        if quality_score is not None:
            # This value is consumed upstream as additional parse confidence.
            pass

    attendance = _ensure_list(canonical.get("attendance"))
    if attendance:
        section_presence["교과학습발달상황"] = True
        section_record_counts["교과학습발달상황"] += len(attendance)
        total_records_ref[0] += len(attendance)

    awards = _ensure_list(canonical.get("awards"))
    if awards:
        section_presence["수상경력"] = True
        section_record_counts["수상경력"] += len(awards)
        total_records_ref[0] += len(awards)

    grades = _ensure_list(canonical.get("grades"))
    if grades:
        section_presence["교과학습발달상황"] = True
        section_record_counts["교과학습발달상황"] += len(grades)
        total_records_ref[0] += len(grades)
        for item in grades:
            if not isinstance(item, dict):
                continue
            subject_name = _normalize_subject(item.get("subject"))
            if subject_name:
                subject_counter[subject_name] += 1

    extra = canonical.get("extracurricular_narratives")
    extra_items = _ensure_list(extra) if isinstance(extra, list) else list(_ensure_dict(extra).values())
    if extra_items:
        section_presence["창의적 체험활동"] = True
        section_record_counts["창의적 체험활동"] += len(extra_items)
        total_records_ref[0] += len(extra_items)
        for value in extra_items:
            narrative_char_count_ref[0] += len(str(value).strip())

    raw_subj_notes = canonical.get("subject_special_notes")
    subj_notes = _ensure_dict(raw_subj_notes)
    if isinstance(raw_subj_notes, list):
        subj_notes = {
            str(item.get("subject") or item.get("label") or index): item.get("label") or item.get("detail") or item
            for index, item in enumerate(raw_subj_notes)
            if isinstance(item, dict)
        }
    if subj_notes:
        section_presence["교과학습발달상황"] = True
        section_record_counts["교과학습발달상황"] += len(subj_notes)
        total_records_ref[0] += len(subj_notes)
        for value in subj_notes.values():
            narrative_char_count_ref[0] += len(str(value).strip())

    reading = _ensure_list(canonical.get("reading_activities"))
    if reading:
        section_presence["독서활동"] = True
        section_record_counts["독서활동"] += len(reading)
        total_records_ref[0] += len(reading)
        for value in reading:
            narrative_char_count_ref[0] += len(str(value).strip())

    behavior = canonical.get("behavior_opinion")
    if behavior:
        section_presence["행동특성 및 종합의견"] = True
        section_record_counts["행동특성 및 종합의견"] += 1
        total_records_ref[0] += 1
        narrative_char_count_ref[0] += len(str(behavior).strip())

    evidence_refs = structured_data.get("evidence_references")
    if not isinstance(evidence_refs, list):
        evidence_refs = canonical.get("evidence_bank")
    if isinstance(evidence_refs, list):
        evidence_reference_count_ref[0] += len(evidence_refs)

    return True


def _extract_structured_data(metadata: dict[str, Any]) -> dict[str, Any] | None:
    """Extract structured parsing data from metadata.

    Supports the semantic pipeline (`canonical_data`) and legacy NEIS-like payloads.
    """
    candidates: list[Any] = [
        {"canonical_data": metadata.get("student_record_canonical")}
        if (
            isinstance(metadata.get("student_record_canonical"), dict)
            and metadata["student_record_canonical"].get("is_primary_student_record") is not False
        )
        else None,
        metadata.get("student_record_structure"),
        metadata.get("analysis_artifact"),
        metadata.get("student_artifact_parse"),
    ]
    for artifact in candidates:
        if not isinstance(artifact, dict):
            continue
        if "canonical_data" in artifact:
            return artifact

        neis_document = artifact.get("neis_document")
        if isinstance(neis_document, dict):
            return neis_document

        if artifact.get("document_type") == "neis_student_record" and isinstance(artifact.get("sections"), list):
            return artifact
    return None


def _normalize_section_type(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""

    alias = {
        "grades_subjects": "교과학습발달상황",
        "subject_special_notes": "교과학습발달상황",
        "creative_activities": "창의적 체험활동",
        "extracurricular": "창의적 체험활동",
        "career_signals": "행동특성 및 종합의견",
        "reading": "독서활동",
        "reading_activity": "독서활동",
        "awards": "수상경력",
    }
    normalized = alias.get(text, text)
    for key in _SECTION_KEYS:
        if key in normalized:
            return key
    return normalized


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


def _major_signal_counts(corpus: str) -> dict[str, int]:
    text = str(corpus or "").lower()
    counts: dict[str, int] = {}
    if not text:
        return {track: 0 for track in _MAJOR_TRACK_KEYWORDS}
    for track, keywords in _MAJOR_TRACK_KEYWORDS.items():
        score = 0
        for keyword in keywords:
            normalized = str(keyword).lower()
            if not normalized:
                continue
            occurrences = len(re.findall(re.escape(normalized), text))
            # 반복 OCR 조각 하나가 계열 판단을 과도하게 지배하지 않도록 키워드별 가중치를 제한합니다.
            score += min(occurrences, 3)
        counts[track] = score
    return counts


def _infer_major_track(text: str | None) -> str | None:
    counts = _major_signal_counts(str(text or ""))
    return _dominant_major_track(counts)


def _dominant_major_track(counts: dict[str, int]) -> str | None:
    if not counts:
        return None
    track, count = max(counts.items(), key=lambda item: item[1])
    return track if count > 0 else None


def _major_alignment(
    *,
    target_major: str | None,
    target_track: str | None,
    dominant_track: str | None,
    signal_counts: dict[str, int],
) -> tuple[str, str | None]:
    if not target_track:
        return "unknown", None

    target_count = int(signal_counts.get(target_track, 0))
    dominant_count = int(signal_counts.get(dominant_track or "", 0)) if dominant_track else 0
    target_label = _MAJOR_TRACK_LABELS.get(target_track, "목표 전공")
    dominant_label = _MAJOR_TRACK_LABELS.get(dominant_track or "", "다른 계열")
    target_name = (target_major or target_label).strip()

    if dominant_track and dominant_track != target_track and dominant_count >= max(3, target_count + 2):
        return (
            "mismatch",
            f"입력 목표는 {target_name}이지만 학생부 원문에서는 {dominant_label} 계열 단서가 더 강합니다. "
            f"{target_label} 연결 근거를 새로 설계해야 합니다.",
        )
    if target_count >= 3 and (not dominant_track or dominant_track == target_track or target_count >= dominant_count - 1):
        return "strong", None
    if target_count >= 2:
        return (
            "partial",
            f"{target_label} 관련 단서는 일부 확인되지만, 대표 활동과 정량 산출물로 더 선명하게 연결해야 합니다.",
        )
    return (
        "weak",
        f"학생부 원문에서 {target_label} 계열 근거가 부족합니다. 목표 전공과 연결되는 새 탐구 질문이 필요합니다.",
    )


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


def _coerce_optional_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _ensure_list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    return []


def _ensure_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return {str(key): item for key, item in value.items()}
    return {}


def _first_non_empty(*values: Any) -> str:
    for item in values:
        text = str(item or "").strip()
        if text:
            return text
    return ""


def _clamp(value: float, minimum: float = 0.0, maximum: float = 1.0) -> float:
    return max(minimum, min(maximum, value))
