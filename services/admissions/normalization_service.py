from __future__ import annotations

import re

from domain.enums import DocumentType, SourceTier, StudentArtifactType


class AdmissionsNormalizationService:
    YEAR_PATTERN = re.compile(r"(20\d{2})\s*(학년도|입시|전형)?")
    FAQ_TERMS = ("faq", "자주 묻는 질문", "자주묻는질문")
    GUIDEBOOK_TERMS = ("모집요강", "guidebook", "전형요강", "전형 안내")
    EVALUATION_GUIDE_TERMS = ("평가기준", "평가요소", "평가 안내", "evaluation guide")
    BRIEFING_TERMS = ("설명회", "입학설명회", "briefing")
    POLICY_TERMS = ("시행계획", "정책", "지침", "안내사항")
    ANNOUNCEMENT_TERMS = ("공지", "announcement", "공고")
    SCHOOL_RECORD_TERMS = ("학교생활기록부", "학생부")

    def extract_admissions_year(self, text: str | None) -> int | None:
        if not text:
            return None
        match = self.YEAR_PATTERN.search(text)
        if match:
            return int(match.group(1))
        return None

    def classify_document_type(self, title: str | None, filename: str) -> DocumentType:
        haystack = f"{title or ''} {filename}".lower()
        if any(term in haystack for term in self.FAQ_TERMS):
            return DocumentType.FAQ
        if any(term in haystack for term in self.SCHOOL_RECORD_TERMS):
            return DocumentType.SCHOOL_RECORD_GUIDE
        if any(term in haystack for term in self.GUIDEBOOK_TERMS):
            return DocumentType.GUIDEBOOK
        if any(term in haystack for term in self.EVALUATION_GUIDE_TERMS):
            return DocumentType.EVALUATION_GUIDE
        if any(term in haystack for term in self.BRIEFING_TERMS):
            return DocumentType.BRIEFING_MATERIAL
        if any(term in haystack for term in self.POLICY_TERMS):
            return DocumentType.POLICY
        if any(term in haystack for term in self.ANNOUNCEMENT_TERMS):
            return DocumentType.ANNOUNCEMENT
        return DocumentType.OTHER

    def classify_student_artifact_type(self, filename: str, mime_type: str | None = None) -> StudentArtifactType:
        lowered = filename.lower()
        if "학교생활기록부" in filename or "학생부" in filename or "school-record" in lowered:
            return StudentArtifactType.SCHOOL_RECORD
        if "report" in lowered or "탐구" in filename or "보고서" in filename:
            return StudentArtifactType.INQUIRY_REPORT
        if "club" in lowered or "동아리" in filename or "project" in lowered:
            return StudentArtifactType.CLUB_PROJECT
        if "reflection" in lowered or "소감" in filename or "회고" in filename:
            return StudentArtifactType.REFLECTION_NOTE
        if lowered.endswith(".pptx") or "portfolio" in lowered:
            return StudentArtifactType.PORTFOLIO
        return StudentArtifactType.OTHER

    def source_tier_penalty(self, source_tier: SourceTier) -> float:
        penalties = {
            SourceTier.TIER_1_OFFICIAL: 0.0,
            SourceTier.TIER_2_PUBLIC_SUPPORT: 0.1,
            SourceTier.TIER_3_CONTROLLED_SECONDARY: 0.25,
            SourceTier.TIER_4_EXCLUDED: 1.0,
        }
        return penalties[source_tier]


normalization_service = AdmissionsNormalizationService()
