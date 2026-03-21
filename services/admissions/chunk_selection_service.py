from __future__ import annotations

from dataclasses import dataclass

from db.models.content import Document, DocumentChunk
from domain.enums import DocumentType, SourceTier


EVALUATION_TERMS = (
    "평가",
    "평가기준",
    "평가요소",
    "서류평가",
    "학업역량",
    "전공적합성",
    "공동체역량",
    "자기주도",
    "진로",
    "세특",
    "학생부종합",
    "admission",
    "criterion",
    "eligibility",
    "evaluation",
)

NOISE_TERMS = (
    "문의",
    "연락처",
    "전화",
    "fax",
    "copyright",
    "all rights reserved",
    "목차",
    "page ",
    "유의사항",
    "개인정보 처리방침",
)

HEADING_PRIORITY_TERMS = ("평가", "전형", "faq", "학생부종합", "eligibility", "criteria")


@dataclass(slots=True)
class ChunkSelectionDecisionDraft:
    chunk: DocumentChunk
    selected: bool
    priority_score: float
    reason_codes: list[str]
    strategy_key: str


class ChunkSelectionService:
    def resolve_strategy(self, *, document: Document, override: str | None = None) -> str:
        if override:
            return override
        if document.document_type in {DocumentType.EVALUATION_GUIDE, DocumentType.POLICY}:
            return "official_evaluation_focus"
        if document.document_type in {DocumentType.FAQ, DocumentType.ANNOUNCEMENT}:
            return "faq_policy_focus"
        if document.source_tier == SourceTier.TIER_3_CONTROLLED_SECONDARY:
            return "secondary_strict"
        return "official_default"

    def evaluate(
        self,
        *,
        document: Document,
        chunks: list[DocumentChunk],
        strategy_key: str,
        manual_chunk_indexes: list[int] | None = None,
    ) -> list[ChunkSelectionDecisionDraft]:
        manual_set = set(manual_chunk_indexes or [])
        decisions: list[ChunkSelectionDecisionDraft] = []
        threshold = {
            "official_evaluation_focus": 0.45,
            "faq_policy_focus": 0.35,
            "secondary_strict": 0.60,
            "official_default": 0.50,
        }.get(strategy_key, 0.50)

        for chunk in chunks:
            reasons: list[str] = []
            score = 0.0
            text = (chunk.content_text or "").strip()
            heading = " ".join(chunk.heading_path).strip()
            basis = f"{heading}\n{text}".lower()

            if manual_chunk_indexes is not None:
                selected = chunk.chunk_index in manual_set
                reasons.append("manual_override_selected" if selected else "manual_override_skipped")
                decisions.append(
                    ChunkSelectionDecisionDraft(
                        chunk=chunk,
                        selected=selected,
                        priority_score=1.0 if selected else 0.0,
                        reason_codes=reasons,
                        strategy_key=strategy_key,
                    )
                )
                continue

            if document.source_tier == SourceTier.TIER_1_OFFICIAL:
                score += 0.20
                reasons.append("official_source")
            elif document.source_tier == SourceTier.TIER_2_PUBLIC_SUPPORT:
                score += 0.10
                reasons.append("public_support_source")

            if document.is_current_cycle:
                score += 0.15
                reasons.append("current_cycle")

            if any(term in basis for term in EVALUATION_TERMS):
                score += 0.45
                reasons.append("evaluation_terms")

            if heading and any(term in heading.lower() for term in HEADING_PRIORITY_TERMS):
                score += 0.15
                reasons.append("heading_match")

            if len(text) < 80:
                score -= 0.30
                reasons.append("too_short")

            if any(term in basis for term in NOISE_TERMS):
                score -= 0.45
                reasons.append("boilerplate_or_noise")

            if chunk.page_start and chunk.page_start > 20 and document.document_type == DocumentType.GUIDEBOOK:
                score -= 0.05
                reasons.append("late_section_penalty")

            selected = score >= threshold
            if not selected and "evaluation_terms" in reasons and score >= threshold - 0.10:
                selected = True
                reasons.append("near_threshold_keep")

            decisions.append(
                ChunkSelectionDecisionDraft(
                    chunk=chunk,
                    selected=selected,
                    priority_score=max(0.0, round(score, 4)),
                    reason_codes=reasons or ["default_skip"],
                    strategy_key=strategy_key,
                )
            )

        return decisions


chunk_selection_service = ChunkSelectionService()
