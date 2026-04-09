from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from polio_api.db.models.parsed_document import ParsedDocument
from polio_api.db.models.diagnosis_run import DiagnosisRun
from polio_api.schemas.diagnosis import DiagnosisResultPayload


def build_diagnosis_copilot_brief(
    db: Session,
    *,
    project_id: str | None,
    max_items: int = 4,
) -> str:
    if not project_id:
        return ""

    run = db.scalar(
        select(DiagnosisRun)
        .where(
            DiagnosisRun.project_id == project_id,
            DiagnosisRun.result_payload.is_not(None),
        )
        .order_by(DiagnosisRun.created_at.desc())
        .limit(1)
    )
    if run is None or not run.result_payload:
        return ""

    try:
        payload = DiagnosisResultPayload.model_validate_json(run.result_payload)
    except Exception:  # noqa: BLE001
        return ""

    strengths = [item.strip() for item in payload.strengths[:max_items] if str(item).strip()]
    gaps = [item.strip() for item in payload.gaps[:max_items] if str(item).strip()]
    actions = [item.strip() for item in (payload.next_actions or [])[:max_items] if str(item).strip()]
    topics = [item.strip() for item in (payload.recommended_topics or [])[:max_items] if str(item).strip()]
    evidence_hooks = [
        f"{item.source_label} p.{item.page_number}" if item.page_number else item.source_label
        for item in (payload.citations or [])[:max_items]
        if item.source_label
    ]
    uncertainty_notes: list[str] = []
    if payload.document_quality and payload.document_quality.needs_review:
        uncertainty_notes.append("문서 추출 신뢰도가 낮아 일부 판단은 보수적으로 다뤄야 함.")
    if payload.fallback_used:
        uncertainty_notes.append("LLM 폴백 모드가 사용되어 설명 수준이 제한될 수 있음.")
    if not evidence_hooks:
        uncertainty_notes.append("직접 인용 가능한 증거 훅이 부족함.")

    canonical_lines: list[str] = []
    documents = list(
        db.scalars(
            select(ParsedDocument)
            .where(
                ParsedDocument.project_id == project_id,
                ParsedDocument.status.in_(["parsed", "partial"]),
            )
            .order_by(ParsedDocument.updated_at.desc())
            .limit(2)
        )
    )
    for document in documents:
        metadata = getattr(document, "parse_metadata", None)
        if not isinstance(metadata, dict):
            continue
        canonical = metadata.get("student_record_canonical")
        if not isinstance(canonical, dict):
            continue
        for field, key in (
            ("timeline_signals", "signal"),
            ("major_alignment_hints", "hint"),
            ("weak_or_missing_sections", "section"),
            ("uncertainties", "message"),
        ):
            values = canonical.get(field)
            if not isinstance(values, list):
                continue
            for item in values[:max_items]:
                if not isinstance(item, dict):
                    continue
                value = str(item.get(key) or "").strip()
                if value:
                    canonical_lines.append(value)
        if len(canonical_lines) >= max_items * 3:
            break
    if canonical_lines:
        canonical_lines = canonical_lines[: max_items * 3]

    lines = [
        "[진단 코파일럿 브리프]",
        f"- 진단 헤드라인: {payload.headline}",
        f"- 핵심 초점: {payload.recommended_focus}",
    ]
    if strengths:
        lines.append("- 강점: " + "; ".join(strengths))
    if gaps:
        lines.append("- 보완점: " + "; ".join(gaps))
    if actions:
        lines.append("- 다음 행동: " + "; ".join(actions))
    if topics:
        lines.append("- 추천 주제: " + "; ".join(topics))
    if evidence_hooks:
        lines.append("- 증거 훅: " + "; ".join(evidence_hooks))
    if uncertainty_notes:
        lines.append("- 불확실성: " + "; ".join(uncertainty_notes))
    if canonical_lines:
        lines.append("- 학생부 구조 시그널: " + "; ".join(canonical_lines))

    lines.extend(
        [
            "[코파일럿 행동 규칙]",
            "- 반드시 학생 기록/업로드 문서 기반으로만 조언한다.",
            "- 합격 보장, 외부 성과 대리작성, 허위 활동 서술을 금지한다.",
            "- 직전 답변과 표현이 반복되면 동일 의미를 더 구체적 다음 행동으로 바꿔 제안한다.",
        ]
    )
    return "\n".join(lines)
