from __future__ import annotations

from datetime import date

from domain.enums import ClaimType, SourceTier
from services.admissions.normalization_service import normalization_service


class QualityScoringService:
    def document_scores(
        self,
        *,
        source_tier: SourceTier,
        publication_date: date | None,
        admissions_year: int | None,
        document_type: object,
        block_count: int,
    ) -> tuple[float, float, float]:
        trust_score = {
            SourceTier.TIER_1_OFFICIAL: 1.0,
            SourceTier.TIER_2_PUBLIC_SUPPORT: 0.8,
            SourceTier.TIER_3_CONTROLLED_SECONDARY: 0.55,
            SourceTier.TIER_4_EXCLUDED: 0.0,
        }[source_tier]

        freshness_score = 0.4
        current_year = date.today().year
        if admissions_year is not None:
            delta = abs(current_year - admissions_year)
            freshness_score = max(0.0, 1.0 - delta * 0.2)
        elif publication_date is not None:
            age_days = (date.today() - publication_date).days
            freshness_score = max(0.0, 1.0 - age_days / 365.0)

        structure_bonus = min(block_count / 30.0, 0.2)
        quality_score = max(0.0, min(1.0, trust_score * 0.45 + freshness_score * 0.35 + 0.2 + structure_bonus))
        return trust_score, freshness_score, quality_score

    def claim_quality_score(
        self,
        *,
        claim_type: ClaimType,
        confidence_score: float,
        has_evidence: bool,
        source_tier: SourceTier,
        conflict_penalty: float = 0.0,
    ) -> float:
        directness_bonus = 0.1 if claim_type in {ClaimType.DOCUMENT_RULE, ClaimType.POLICY_STATEMENT} else 0.0
        evidence_bonus = 0.2 if has_evidence else -0.2
        tier_penalty = normalization_service.source_tier_penalty(source_tier)
        return max(0.0, min(1.0, confidence_score + directness_bonus + evidence_bonus - tier_penalty - conflict_penalty))


quality_scoring_service = QualityScoringService()
