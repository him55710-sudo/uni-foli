from __future__ import annotations

import re
from typing import Any

from unifoli_api.schemas.diagnosis import (
    ConsultantDiagnosisSection,
    ConsultantInterviewQuestionFrame,
    ConsultantRecordNetwork,
    ConsultantReportQualityGate,
    ConsultantResearchTopicRecommendation,
    ConsultantSubjectSpecialtyAnalysis,
)


def _clean_line(value: Any, *, max_len: int = 220) -> str:
    normalized = " ".join(str(value or "").split()).strip()
    if len(normalized) <= max_len:
        return normalized
    return f"{normalized[: max_len - 3].rstrip()}..."


def _unique_evidence_pages(evidence_bank: list[dict[str, Any]]) -> set[int]:
    pages: set[int] = set()
    for item in evidence_bank:
        page = item.get("page") or item.get("page_number")
        try:
            parsed = int(page)
        except (TypeError, ValueError):
            continue
        if parsed > 0:
            pages.add(parsed)
    return pages


def _has_repeated_sentences(
    sections: list[ConsultantDiagnosisSection],
    topics: list[ConsultantResearchTopicRecommendation],
) -> bool:
    counts: dict[str, int] = {}
    texts = [section.body_markdown for section in sections] + [topic.title for topic in topics]
    for text in texts:
        for sentence in re.split(r"[.!?\n。]+", str(text or "")):
            normalized = re.sub(r"\s+", " ", sentence).strip()
            if len(normalized) < 18:
                continue
            counts[normalized] = counts.get(normalized, 0) + 1
            if counts[normalized] >= 3:
                return True
    return False


def build_report_quality_gates(
    *,
    report_mode: str,
    mode_spec: dict[str, Any],
    evidence_bank: list[dict[str, Any]],
    subject_analyses: list[ConsultantSubjectSpecialtyAnalysis],
    record_network: ConsultantRecordNetwork,
    research_topics: list[ConsultantResearchTopicRecommendation],
    interview_questions: list[ConsultantInterviewQuestionFrame],
    sections: list[ConsultantDiagnosisSection],
    reanalysis_required: bool,
) -> list[ConsultantReportQualityGate]:
    unique_anchor_ids = {
        str(item.get("anchor_id") or "").strip()
        for item in evidence_bank
        if str(item.get("anchor_id") or "").strip()
    }
    unique_pages = _unique_evidence_pages(evidence_bank)
    min_topics = 8 if report_mode in {"premium", "consultant"} else 3
    min_questions = 12 if report_mode in {"premium", "consultant"} else 5
    return [
        ConsultantReportQualityGate(
            key="page_count",
            label="페이지 구성",
            passed=True,
            message=(
                f"{mode_spec['label']} 기준 {mode_spec['min_pages']}~{mode_spec['max_pages']}쪽 범위로 렌더링합니다."
            ),
        ),
        ConsultantReportQualityGate(
            key="evidence",
            label="근거 밀도",
            passed=not reanalysis_required and (len(unique_anchor_ids) >= 8 or len(unique_pages) >= 5),
            message=(
                f"확인 가능한 근거가 {len(unique_anchor_ids)}개, 페이지 분산이 {len(unique_pages)}쪽입니다."
                if evidence_bank
                else "원문 근거가 부족해 일부 해석은 보수적으로 표시합니다."
            ),
        ),
        ConsultantReportQualityGate(
            key="topics",
            label="추천 탐구 수",
            passed=len(research_topics) >= min_topics,
            message=f"추천 탐구 {len(research_topics)}개를 생성했습니다.",
        ),
        ConsultantReportQualityGate(
            key="interview",
            label="면접 질문 수",
            passed=len(interview_questions) >= min_questions,
            message=f"면접 질문 {len(interview_questions)}개를 전공 적합성/탐구 검증/약점 방어로 나눴습니다.",
        ),
        ConsultantReportQualityGate(
            key="subjects",
            label="과목별 세특",
            passed=len(subject_analyses) >= 5 and all(item.score >= 0 for item in subject_analyses),
            message=f"과목/영역 {len(subject_analyses)}개를 점수와 해석으로 분석했습니다.",
        ),
        ConsultantReportQualityGate(
            key="network",
            label="연결망 분석",
            passed=len(record_network.nodes) >= 8 and len(record_network.edges) >= 10,
            message=f"노드 {len(record_network.nodes)}개, 연결 {len(record_network.edges)}개를 추출했습니다.",
        ),
        ConsultantReportQualityGate(
            key="repetition",
            label="반복 문장",
            passed=not _has_repeated_sentences(sections, research_topics),
            message=_clean_line("동일 문장이 3회 이상 반복되지 않도록 카드형 문장을 분산했습니다."),
        ),
    ]
