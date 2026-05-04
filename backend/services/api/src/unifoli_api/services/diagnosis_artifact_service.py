from __future__ import annotations

from typing import Any, Iterable


DIAGNOSIS_ARTIFACT_SCHEMA_VERSION = "2026-04-15-diagnosis-artifacts-v1"
_ARTIFACT_FIELDS = {
    "diagnosis_result_json",
    "diagnosis_report_markdown",
    "diagnosis_summary_json",
    "chatbot_context_json",
}


def _payload_dict(payload: Any, *, exclude_artifact_fields: bool = False) -> dict[str, Any]:
    if payload is None:
        return {}
    if hasattr(payload, "model_dump"):
        data = payload.model_dump(mode="json")
    elif isinstance(payload, dict):
        data = dict(payload)
    else:
        return {}
    if exclude_artifact_fields:
        for field_name in _ARTIFACT_FIELDS:
            data.pop(field_name, None)
    return data


def _normalize_text(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def _string_list(values: Any, *, limit: int) -> list[str]:
    if not isinstance(values, list):
        return []
    normalized: list[str] = []
    seen: set[str] = set()
    for raw in values:
        text = _normalize_text(raw)
        if not text:
            continue
        key = text.lower()
        if key in seen:
            continue
        seen.add(key)
        normalized.append(text)
        if len(normalized) >= limit:
            break
    return normalized


def _extract_labeled_list(values: Any, *, key: str, limit: int) -> list[str]:
    if not isinstance(values, list):
        return []
    normalized: list[str] = []
    seen: set[str] = set()
    for item in values:
        if not isinstance(item, dict):
            continue
        text = _normalize_text(item.get(key))
        if not text:
            continue
        lowered = text.lower()
        if lowered in seen:
            continue
        seen.add(lowered)
        normalized.append(text)
        if len(normalized) >= limit:
            break
    return normalized


def _extend_unique(target: list[str], values: Iterable[str], *, limit: int) -> list[str]:
    seen = {item.lower() for item in target}
    for raw in values:
        text = _normalize_text(raw)
        if not text:
            continue
        lowered = text.lower()
        if lowered in seen:
            continue
        seen.add(lowered)
        target.append(text)
        if len(target) >= limit:
            break
    return target


def _collect_canonical_metadata(documents: list[Any]) -> dict[str, Any]:
    for document in documents:
        metadata = getattr(document, "parse_metadata", None)
        if not isinstance(metadata, dict):
            continue
        candidate = metadata.get("student_record_canonical")
        if isinstance(candidate, dict) and candidate and candidate.get("is_primary_student_record") is not False:
            return candidate
    return {}


def _build_evidence_references(result_payload: dict[str, Any], *, limit: int = 8) -> list[dict[str, Any]]:
    citations = result_payload.get("citations")
    if not isinstance(citations, list):
        return []

    references: list[dict[str, Any]] = []
    seen: set[tuple[str, int | None, str]] = set()
    for item in citations:
        if not isinstance(item, dict):
            continue
        source_label = _normalize_text(item.get("source_label"))
        excerpt = _normalize_text(item.get("excerpt"))
        if not source_label and not excerpt:
            continue
        page_number = item.get("page_number")
        if not isinstance(page_number, int):
            page_number = None
        key = (source_label, page_number, excerpt)
        if key in seen:
            continue
        seen.add(key)
        references.append(
            {
                "source_label": source_label or "Document evidence",
                "section_label": _normalize_text(item.get("section_label")),
                "item_label": _normalize_text(item.get("item_label")),
                "page_number": page_number,
                "excerpt": excerpt,
                "relevance_score": float(item.get("relevance_score") or 0.0),
            }
        )
        if len(references) >= limit:
            break
    return references


def _private_to_bounded_score(value: Any, *, default: int = 55) -> int:
    try:
        return max(0, min(100, int(round(float(value)))))
    except (TypeError, ValueError):
        return default


def _private_score_label(score: int) -> str:
    if score >= 85:
        return "매우 우수"
    if score >= 70:
        return "우수"
    if score >= 55:
        return "보통"
    if score >= 40:
        return "보완 필요"
    return "집중 보완 필요"


def _private_average_score(values: list[int], *, default: int = 55) -> int:
    if not values:
        return default
    return _private_to_bounded_score(sum(values) / len(values), default=default)


def _private_coerce_float(value: Any) -> float | None:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    if parsed != parsed:
        return None
    return parsed


def _private_coerce_int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _private_list_values(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _private_quality_gate_payload(canonical_metadata: dict[str, Any]) -> dict[str, Any]:
    value = canonical_metadata.get("quality_gates")
    return value if isinstance(value, dict) else {}


def _private_section_coverage_payload(canonical_metadata: dict[str, Any]) -> dict[str, Any]:
    value = canonical_metadata.get("section_coverage")
    return value if isinstance(value, dict) else {}


def _private_score_quality_gate(
    *,
    canonical_metadata: dict[str, Any],
    evidence_references: list[dict[str, Any]],
) -> dict[str, Any]:
    if not canonical_metadata:
        return {
            "score_cap": 45,
            "score_validity": "unverified_source",
            "quality_gate_notes": [
                "원본 학교생활기록부 구조를 확인하지 못해 점수는 참고용 상한으로 제한했습니다."
            ],
            "document_confidence": None,
            "coverage_score": None,
            "evidence_anchor_count": 0,
            "evidence_page_count": 0,
            "missing_required_sections": [],
            "reanalysis_required": True,
        }

    quality_gates = _private_quality_gate_payload(canonical_metadata)
    section_coverage = _private_section_coverage_payload(canonical_metadata)
    evidence_bank = _private_list_values(canonical_metadata.get("evidence_bank"))

    document_confidence = _private_coerce_float(canonical_metadata.get("document_confidence"))
    coverage_score = _private_coerce_float(quality_gates.get("coverage_score"))
    if coverage_score is None:
        coverage_score = _private_coerce_float(section_coverage.get("coverage_score"))
    evidence_anchor_count = (
        _private_coerce_int(quality_gates.get("evidence_anchor_count"))
        if quality_gates.get("evidence_anchor_count") is not None
        else len(evidence_bank)
    )
    evidence_page_count = _private_coerce_int(quality_gates.get("evidence_page_count"))
    if evidence_page_count is None:
        pages: set[int] = set()
        for item in evidence_bank:
            if not isinstance(item, dict):
                continue
            page = _private_coerce_int(item.get("page") or item.get("page_number"))
            if page is not None and page > 0:
                pages.add(page)
        evidence_page_count = len(pages)

    missing_required_sections = _private_list_values(
        quality_gates.get("missing_required_sections")
        or section_coverage.get("missing_required_sections")
        or section_coverage.get("missing_sections")
    )
    reanalysis_required = bool(quality_gates.get("reanalysis_required") or section_coverage.get("reanalysis_required"))

    score_cap = 100
    notes: list[str] = []

    if reanalysis_required:
        score_cap = min(score_cap, 60)
        notes.append("재분석이 필요한 학생부 구조로 판별되어 고득점 판정을 제한했습니다.")
    if document_confidence is not None:
        if document_confidence < 0.55:
            score_cap = min(score_cap, 55)
            notes.append("문서 유형 신뢰도가 낮아 점수 상한을 55점으로 제한했습니다.")
        elif document_confidence < 0.68:
            score_cap = min(score_cap, 72)
            notes.append("문서 유형 신뢰도가 보통 이하라 70점대 이상 판정을 제한했습니다.")
    if coverage_score is not None:
        if coverage_score < 0.35:
            score_cap = min(score_cap, 58)
            notes.append("학생부 필수 섹션 커버리지가 부족해 점수를 보수적으로 제한했습니다.")
        elif coverage_score < 0.55:
            score_cap = min(score_cap, 72)
            notes.append("필수 섹션 일부가 약해 점수 상한을 적용했습니다.")
    if evidence_anchor_count < 3:
        score_cap = min(score_cap, 55)
        notes.append("직접 근거 앵커가 3개 미만이라 정량 점수를 참고용으로 제한했습니다.")
    elif evidence_anchor_count < 6:
        score_cap = min(score_cap, 70)
        notes.append("직접 근거 앵커가 충분하지 않아 고득점 판정을 제한했습니다.")
    if evidence_page_count < 2:
        score_cap = min(score_cap, 60)
        notes.append("근거가 2페이지 미만에 몰려 있어 페이지 다양성 기준을 통과하지 못했습니다.")
    elif evidence_page_count < 4:
        score_cap = min(score_cap, 78)
        notes.append("근거 페이지 다양성이 제한되어 80점 이상 판정을 막았습니다.")
    if len(missing_required_sections) >= 4:
        score_cap = min(score_cap, 60)
        notes.append("누락된 필수 학생부 섹션이 많아 점수 상한을 적용했습니다.")
    elif len(missing_required_sections) >= 2:
        score_cap = min(score_cap, 72)
        notes.append("일부 필수 학생부 섹션이 누락되어 점수 상한을 적용했습니다.")
    if not evidence_references and evidence_anchor_count < 3:
        score_cap = min(score_cap, 55)

    score_cap = _private_to_bounded_score(score_cap)
    if score_cap >= 85 and not notes:
        score_validity = "verified_student_record"
        notes.append("원본 학생부 구조와 근거 앵커 기준을 통과한 점수입니다.")
    elif score_cap >= 70:
        score_validity = "limited_evidence"
    else:
        score_validity = "reference_only"

    return {
        "score_cap": score_cap,
        "score_validity": score_validity,
        "quality_gate_notes": notes[:6],
        "document_confidence": round(document_confidence, 3) if document_confidence is not None else None,
        "coverage_score": round(coverage_score, 3) if coverage_score is not None else None,
        "evidence_anchor_count": max(0, evidence_anchor_count),
        "evidence_page_count": max(0, evidence_page_count),
        "missing_required_sections": [str(item) for item in missing_required_sections[:8]],
        "reanalysis_required": reanalysis_required,
    }


def _private_merge_scores(primary: int | None, secondary: int | None, *, default: int = 55) -> int:
    scores = [item for item in [primary, secondary] if isinstance(item, int)]
    return _private_average_score(scores, default=default)


def _private_is_award_or_achievement_section(value: Any) -> bool:
    normalized = _normalize_text(value).lower()
    if not normalized:
        return False
    keywords = (
        "수상",
        "awards",
        "award",
        "scholarship",
        "장학",
        "포상",
    )
    return any(token in normalized for token in keywords)


def _private_collect_axis_index(result_payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    axes = result_payload.get("admission_axes")
    if not isinstance(axes, list):
        return {}
    output: dict[str, dict[str, Any]] = {}
    for item in axes:
        if not isinstance(item, dict):
            continue
        key = _normalize_text(item.get("key")).lower()
        if not key:
            continue
        output[key] = {
            "score": _private_to_bounded_score(item.get("score")),
            "rationale": _normalize_text(item.get("rationale")) or None,
        }
    return output


def _private_collect_section_index(
    *,
    result_payload: dict[str, Any],
    canonical_metadata: dict[str, Any],
) -> dict[str, int]:
    section_index = {
        "교과학습발달상황": 0,
        "창의적 체험활동": 0,
        "행동특성 및 종합의견": 0,
        "독서활동": 0,
        "출결": 0,
    }

    section_analysis = result_payload.get("section_analysis")
    if isinstance(section_analysis, list):
        for row in section_analysis:
            if not isinstance(row, dict):
                continue
            if _private_is_award_or_achievement_section(row.get("key")) or _private_is_award_or_achievement_section(
                row.get("label")
            ):
                continue
            label = _normalize_text(row.get("label") or row.get("key"))
            record_count = max(0, _private_to_bounded_score(row.get("record_count"), default=0))
            if "교과" in label or "세특" in label:
                section_index["교과학습발달상황"] += record_count
            elif "창의적 체험활동" in label or "창체" in label:
                section_index["창의적 체험활동"] += record_count
            elif "행동특성" in label or "종합의견" in label:
                section_index["행동특성 및 종합의견"] += record_count
            elif "독서" in label:
                section_index["독서활동"] += record_count
            elif "출결" in label:
                section_index["출결"] += record_count

    attendance = canonical_metadata.get("attendance")
    if isinstance(attendance, list):
        section_index["출결"] = max(section_index["출결"], len(attendance))
    elif isinstance(attendance, dict):
        section_index["출결"] = max(section_index["출결"], len(attendance.keys()))

    return section_index


def _private_section_count_score(count: int) -> int:
    if count >= 6:
        return 88
    if count >= 4:
        return 78
    if count >= 2:
        return 68
    if count == 1:
        return 58
    return 42


def _private_extract_major_direction_candidates(result_payload: dict[str, Any], *, limit: int = 3) -> list[dict[str, str]]:
    candidates = result_payload.get("recommended_directions")
    if not isinstance(candidates, list):
        return []
    output: list[dict[str, str]] = []
    seen: set[str] = set()
    for item in candidates:
        if not isinstance(item, dict):
            continue
        direction_id = _normalize_text(item.get("id"))
        label = _normalize_text(item.get("label"))
        summary = _normalize_text(item.get("summary"))
        unique_key = (direction_id or label or summary).lower()
        if not unique_key or unique_key in seen:
            continue
        seen.add(unique_key)
        output.append(
            {
                "id": direction_id or f"direction-{len(output) + 1}",
                "label": label or "진로 방향",
                "summary": summary or "기록 근거 기반 보완 방향",
            }
        )
        if len(output) >= limit:
            break
    return output


def _private_resolve_completion_state(result_payload: dict[str, Any]) -> str:
    raw = _normalize_text(result_payload.get("record_completion_state")).lower()
    if raw == "finalized":
        return "finalized"
    if raw == "ongoing":
        return "ongoing"
    return "unknown"


def _private_build_stage_mode(completion_state: str) -> tuple[str, str]:
    if completion_state == "finalized":
        return (
            "finalized",
            "완성된 기록의 정합성 점검과 설득력 강화 중심으로 추천합니다.",
        )
    return (
        "ongoing",
        "보완 가능한 항목을 우선 강화하는 개선 중심 추천 모드입니다.",
    )


def _private_build_score_ready_summary_fields(
    *,
    result_payload: dict[str, Any],
    canonical_metadata: dict[str, Any],
    evidence_references: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    axis_index = _private_collect_axis_index(result_payload)
    section_index = _private_collect_section_index(result_payload=result_payload, canonical_metadata=canonical_metadata)
    quality_gate = _private_score_quality_gate(
        canonical_metadata=canonical_metadata,
        evidence_references=evidence_references or [],
    )
    score_cap = int(quality_gate["score_cap"])

    rigor_score = axis_index.get("universal_rigor", {}).get("score")
    specificity_score = axis_index.get("universal_specificity", {}).get("score")
    narrative_score = axis_index.get("relational_narrative", {}).get("score")
    continuity_score = axis_index.get("relational_continuity", {}).get("score")
    depth_score = axis_index.get("cluster_depth", {}).get("score")
    suitability_score = axis_index.get("cluster_suitability", {}).get("score")
    community_score = axis_index.get("community_contribution", {}).get("score")

    raw_category_scores: dict[str, int] = {
        "교과/세특": _private_merge_scores(
            _private_average_score(
                [item for item in [rigor_score, specificity_score] if isinstance(item, int)],
                default=60,
            ),
            _private_section_count_score(section_index["교과학습발달상황"]),
            default=60,
        ),
        "창체": _private_merge_scores(
            _private_section_count_score(section_index["창의적 체험활동"]),
            narrative_score if isinstance(narrative_score, int) else None,
            default=58,
        ),
        "행동특성/종합의견": _private_merge_scores(
            _private_section_count_score(section_index["행동특성 및 종합의견"]),
            community_score if isinstance(community_score, int) else suitability_score if isinstance(suitability_score, int) else None,
            default=56,
        ),
        "독서": _private_merge_scores(
            _private_section_count_score(section_index["독서활동"]),
            specificity_score if isinstance(specificity_score, int) else None,
            default=55,
        ),
        "출결": _private_merge_scores(
            _private_section_count_score(section_index["출결"]),
            rigor_score if isinstance(rigor_score, int) else None,
            default=58,
        ),
        "항목 간 연계성": _private_average_score(
            [item for item in [narrative_score, continuity_score] if isinstance(item, int)],
            default=57,
        ),
        "종합 진로연계성": _private_average_score(
            [item for item in [depth_score, suitability_score] if isinstance(item, int)],
            default=57,
        ),
    }
    category_scores = {key: min(value, score_cap) for key, value in raw_category_scores.items()}

    total_score = _private_average_score(list(category_scores.values()), default=57)
    total_score = min(total_score, score_cap)
    score_labels = {"총점": _private_score_label(total_score)}
    score_labels.update({key: _private_score_label(value) for key, value in category_scores.items()})

    completion_state = _private_resolve_completion_state(result_payload)
    stage_mode, stage_note = _private_build_stage_mode(completion_state)

    explanations = {
        "교과/세특": _normalize_text(axis_index.get("universal_rigor", {}).get("rationale")) or "교과 근거 밀도 중심 평가",
        "창체": _normalize_text(axis_index.get("relational_narrative", {}).get("rationale")) or "창체 활동의 서사 연결 평가",
        "행동특성/종합의견": _normalize_text(axis_index.get("community_contribution", {}).get("rationale"))
        or _normalize_text(axis_index.get("cluster_suitability", {}).get("rationale"))
        or "행동특성·종합의견 기록의 공동체 기여 평가",
        "독서": _normalize_text(axis_index.get("universal_specificity", {}).get("rationale")) or "독서 활동의 근거 구체성 평가",
        "출결": "출결 기록 존재 여부와 기초 학업 신뢰도 중심 평가",
        "항목 간 연계성": _normalize_text(axis_index.get("relational_continuity", {}).get("rationale"))
        or "섹션 간 흐름의 일관성 평가",
        "종합 진로연계성": _normalize_text(axis_index.get("cluster_depth", {}).get("rationale"))
        or "전공 연계 단서의 종합 평가",
    }

    return {
        "total_score": total_score,
        "category_scores": category_scores,
        "score_labels": score_labels,
        "score_explanations": explanations,
        "major_direction_candidates_top3": _private_extract_major_direction_candidates(result_payload),
        "completion_state": completion_state,
        "stage_aware_recommendation_mode": stage_mode,
        "stage_aware_recommendation_note": stage_note,
        "scoring_policy": {
            "awards_excluded": True,
            "grade_trend_analysis_included": False,
            "recommended_universities_included": False,
            "basis": "student_record_evidence_quality_gate",
            "source_validation": "primary_student_record_only",
            "evidence_quality_score_cap": score_cap,
            "score_validity": quality_gate["score_validity"],
            "quality_gate_notes": quality_gate["quality_gate_notes"],
            "raw_category_scores_before_quality_cap": raw_category_scores,
            "document_confidence": quality_gate["document_confidence"],
            "coverage_score": quality_gate["coverage_score"],
            "evidence_anchor_count": quality_gate["evidence_anchor_count"],
            "evidence_page_count": quality_gate["evidence_page_count"],
            "missing_required_sections": quality_gate["missing_required_sections"],
            "reanalysis_required": quality_gate["reanalysis_required"],
        },
    }


def _build_summary_json(
    *,
    run_id: str,
    project_id: str,
    result_payload: dict[str, Any],
    canonical_metadata: dict[str, Any],
    evidence_references: list[dict[str, Any]],
) -> dict[str, Any]:
    score_ready_fields = _private_build_score_ready_summary_fields(
        result_payload=result_payload,
        canonical_metadata=canonical_metadata,
        evidence_references=evidence_references,
    )
    return {
        "schema_version": DIAGNOSIS_ARTIFACT_SCHEMA_VERSION,
        "diagnosis_run_id": run_id,
        "project_id": project_id,
        "headline": _normalize_text(result_payload.get("headline")),
        "overview": _normalize_text(result_payload.get("overview")) or None,
        "recommended_focus": _normalize_text(result_payload.get("recommended_focus")),
        "risk_level": _normalize_text(result_payload.get("risk_level")) or "warning",
        "strengths": _string_list(result_payload.get("strengths"), limit=6),
        "gaps": _string_list(result_payload.get("gaps"), limit=6),
        "next_actions": _string_list(result_payload.get("next_actions"), limit=6),
        "recommended_topics": _string_list(result_payload.get("recommended_topics"), limit=6),
        "fallback_used": bool(result_payload.get("fallback_used")),
        "fallback_reason": _normalize_text(result_payload.get("fallback_reason")) or None,
        "evidence_references": evidence_references,
        **score_ready_fields,
    }


def _build_chatbot_context_json(
    *,
    run_id: str,
    project_id: str,
    result_payload: dict[str, Any],
    canonical_metadata: dict[str, Any],
    evidence_references: list[dict[str, Any]],
) -> dict[str, Any]:
    missing_sections = _string_list(
        (canonical_metadata.get("section_coverage") or {}).get("missing_sections"),
        limit=6,
    )
    weak_sections = _extract_labeled_list(canonical_metadata.get("weak_or_missing_sections"), key="section", limit=6)
    target_risks = _string_list(result_payload.get("risks"), limit=6)
    if not target_risks:
        target_risks = _string_list(result_payload.get("gaps"), limit=6)

    caution_points: list[str] = []
    _extend_unique(caution_points, weak_sections, limit=8)
    _extend_unique(caution_points, missing_sections, limit=8)
    if bool(result_payload.get("fallback_used")):
        _extend_unique(
            caution_points,
            ["Deterministic fallback was used for part of the diagnosis pipeline."],
            limit=8,
        )
    document_quality = result_payload.get("document_quality")
    if isinstance(document_quality, dict) and bool(document_quality.get("needs_review")):
        _extend_unique(
            caution_points,
            ["The uploaded record still needs manual verification before making high-confidence claims."],
            limit=8,
        )

    score_ready_fields = _private_build_score_ready_summary_fields(
        result_payload=result_payload,
        canonical_metadata=canonical_metadata,
        evidence_references=evidence_references,
    )

    return {
        "schema_version": DIAGNOSIS_ARTIFACT_SCHEMA_VERSION,
        "diagnosis_run_id": run_id,
        "project_id": project_id,
        "key_strengths": _string_list(result_payload.get("strengths"), limit=6),
        "key_weaknesses": _string_list(result_payload.get("gaps"), limit=6),
        "target_risks": target_risks,
        "recommended_activity_topics": _string_list(result_payload.get("recommended_topics"), limit=6),
        "caution_points": caution_points,
        "missing_sections": missing_sections,
        "major_alignment_hints": _extract_labeled_list(
            canonical_metadata.get("major_alignment_hints"),
            key="hint",
            limit=6,
        ),
        "timeline_signals": _extract_labeled_list(
            canonical_metadata.get("timeline_signals"),
            key="signal",
            limit=6,
        ),
        "evidence_references": evidence_references,
        "score_snapshot": {
            "total_score": score_ready_fields["total_score"],
            "category_scores": score_ready_fields["category_scores"],
            "score_labels": score_ready_fields["score_labels"],
            "completion_state": score_ready_fields["completion_state"],
            "stage_aware_recommendation_mode": score_ready_fields["stage_aware_recommendation_mode"],
            "major_direction_candidates_top3": score_ready_fields["major_direction_candidates_top3"],
        },
    }


def _build_report_markdown(
    *,
    summary_json: dict[str, Any],
    chatbot_context_json: dict[str, Any],
) -> str:
    lines = [
        "# Student Record Diagnosis",
        "",
        f"## Headline",
        summary_json.get("headline") or "Diagnosis summary unavailable",
        "",
        "## Recommended Focus",
        summary_json.get("recommended_focus") or "No recommended focus was generated.",
        "",
    ]

    overview = _normalize_text(summary_json.get("overview"))
    if overview:
        lines.extend(["## Overview", overview, ""])

    total_score = summary_json.get("total_score")
    if total_score is not None:
        lines.append("## Admissions Dashboard Metrics")
        risk_level = _normalize_text(summary_json.get("risk_level")) or "warning"
        lines.append(f"- **Total Score**: {total_score} points (Risk Level: {risk_level})")
        category_scores = summary_json.get("category_scores")
        if isinstance(category_scores, dict):
            for cat, points in category_scores.items():
                lines.append(f"  - {cat}: {points} / 100")
        lines.append("")

    major_directions = summary_json.get("major_direction_candidates_top3")
    if isinstance(major_directions, list) and major_directions:
        lines.extend(["## AI Major Direction Candidates (Top 3)"])
        for idx, direction in enumerate(major_directions):
            if isinstance(direction, dict):
                label = direction.get("label", "Unknown")
                summary = direction.get("summary", "")
                lines.append(f"{idx + 1}. **{label}**: {summary}")
        lines.append("")

    state = summary_json.get("completion_state")
    if state:
        stage_mode = summary_json.get("stage_aware_recommendation_mode")
        stage_note = summary_json.get("stage_aware_recommendation_note")
        lines.extend([
            "## Stage-Aware Recommendation",
            f"- **Record State**: {state}",
        ])
        if stage_mode:
            lines.append(f"- **Recommendation Mode**: {stage_mode}")
        if stage_note:
            lines.append(f"- **Strategy Note**: {stage_note}")
        lines.append("")

    strengths = _string_list(summary_json.get("strengths"), limit=6)
    if strengths:
        lines.append("## Strengths")
        lines.extend(f"- {item}" for item in strengths)
        lines.append("")

    weaknesses = _string_list(chatbot_context_json.get("key_weaknesses"), limit=6)
    if weaknesses:
        lines.append("## Weaknesses")
        lines.extend(f"- {item}" for item in weaknesses)
        lines.append("")

    risks = _string_list(chatbot_context_json.get("target_risks"), limit=6)
    if risks:
        lines.append("## Target Risks")
        lines.extend(f"- {item}" for item in risks)
        lines.append("")

    actions = _string_list(summary_json.get("next_actions"), limit=6)
    if actions:
        lines.append("## Next Actions")
        lines.extend(f"- {item}" for item in actions)
        lines.append("")

    topics = _string_list(chatbot_context_json.get("recommended_activity_topics"), limit=6)
    if topics:
        lines.append("## Recommended Activity Topics")
        lines.extend(f"- {item}" for item in topics)
        lines.append("")

    cautions = _string_list(chatbot_context_json.get("caution_points"), limit=8)
    if cautions:
        lines.append("## Caution Points")
        lines.extend(f"- {item}" for item in cautions)
        lines.append("")

    evidence = chatbot_context_json.get("evidence_references")
    if isinstance(evidence, list) and evidence:
        lines.append("## Evidence References")
        for item in evidence[:8]:
            if not isinstance(item, dict):
                continue
            source_label = _normalize_text(item.get("source_label")) or "Document evidence"
            section_label = _normalize_text(item.get("section_label"))
            excerpt = _normalize_text(item.get("excerpt"))
            page_number = item.get("page_number")
            
            label_parts = []
            if section_label:
                label_parts.append(f"[{section_label}]")
            label_parts.append(source_label)
            full_label = " ".join(label_parts)
            
            page_suffix = f" (p.{page_number})" if isinstance(page_number, int) else ""
            if excerpt:
                lines.append(f"- {full_label}{page_suffix}: {excerpt}")
            else:
                lines.append(f"- {full_label}{page_suffix}")
        lines.append("")

    return "\n".join(lines).strip()


def build_diagnosis_artifact_bundle(
    *,
    run_id: str,
    project_id: str,
    result: Any,
    documents: list[Any],
) -> dict[str, Any]:
    result_payload = _payload_dict(result, exclude_artifact_fields=True)
    evidence_references = _build_evidence_references(result_payload)
    canonical_metadata = _collect_canonical_metadata(documents)
    summary_json = _build_summary_json(
        run_id=run_id,
        project_id=project_id,
        result_payload=result_payload,
        canonical_metadata=canonical_metadata,
        evidence_references=evidence_references,
    )
    chatbot_context_json = _build_chatbot_context_json(
        run_id=run_id,
        project_id=project_id,
        result_payload=result_payload,
        canonical_metadata=canonical_metadata,
        evidence_references=evidence_references,
    )
    report_markdown = _build_report_markdown(
        summary_json=summary_json,
        chatbot_context_json=chatbot_context_json,
    )
    return {
        "diagnosis_result_json": result_payload,
        "diagnosis_summary_json": summary_json,
        "diagnosis_report_markdown": report_markdown,
        "chatbot_context_json": chatbot_context_json,
    }


def build_diagnosis_copilot_brief(payload: Any, *, max_items: int = 4) -> str:
    data = _payload_dict(payload)
    if not data:
        return ""

    summary_json = data.get("diagnosis_summary_json")
    chatbot_context_json = data.get("chatbot_context_json")
    if not isinstance(summary_json, dict) or not isinstance(chatbot_context_json, dict):
        return ""

    headline = _normalize_text(summary_json.get("headline"))
    recommended_focus = _normalize_text(summary_json.get("recommended_focus"))
    strengths = _string_list(chatbot_context_json.get("key_strengths"), limit=max_items)
    weaknesses = _string_list(chatbot_context_json.get("key_weaknesses"), limit=max_items)
    risks = _string_list(chatbot_context_json.get("target_risks"), limit=max_items)
    topics = _string_list(chatbot_context_json.get("recommended_activity_topics"), limit=max_items)
    cautions = _string_list(chatbot_context_json.get("caution_points"), limit=max_items)

    evidence_lines: list[str] = []
    evidence_references = chatbot_context_json.get("evidence_references")
    if isinstance(evidence_references, list):
        for item in evidence_references[:max_items]:
            if not isinstance(item, dict):
                continue
            source_label = _normalize_text(item.get("source_label")) or "Document evidence"
            excerpt = _normalize_text(item.get("excerpt"))
            page_number = item.get("page_number")
            page_suffix = f" p.{page_number}" if isinstance(page_number, int) else ""
            evidence_lines.append(f"{source_label}{page_suffix}: {excerpt}" if excerpt else f"{source_label}{page_suffix}")

    lines = ["[Diagnosis Artifact Brief]"]
    if headline:
        lines.append(f"- Headline: {headline}")
    if recommended_focus:
        lines.append(f"- Recommended focus: {recommended_focus}")
    if strengths:
        lines.append("- Strengths: " + "; ".join(strengths))
    if weaknesses:
        lines.append("- Weaknesses: " + "; ".join(weaknesses))
    if risks:
        lines.append("- Target risks: " + "; ".join(risks))
    if topics:
        lines.append("- Recommended topics: " + "; ".join(topics))
    if cautions:
        lines.append("- Caution points: " + "; ".join(cautions))
    if evidence_lines:
        lines.append("- Evidence: " + "; ".join(evidence_lines))
    lines.extend(
        [
            "[Grounding Rules]",
            "- Answer from the persisted diagnosis artifact first.",
            "- Prefer evidence references over fresh speculation.",
            "- State uncertainty clearly when evidence is missing.",
        ]
    )
    return "\n".join(lines)


def extract_diagnosis_summary_text(payload: Any) -> str | None:
    data = _payload_dict(payload)
    summary_json = data.get("diagnosis_summary_json")
    if not isinstance(summary_json, dict):
        return None

    headline = _normalize_text(summary_json.get("headline"))
    recommended_focus = _normalize_text(summary_json.get("recommended_focus"))
    strengths = _string_list(summary_json.get("strengths"), limit=1)
    parts = [part for part in [headline, recommended_focus, *strengths] if part]
    if not parts:
        return None
    return " / ".join(parts[:3])
