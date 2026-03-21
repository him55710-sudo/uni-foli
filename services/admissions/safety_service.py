from __future__ import annotations

from dataclasses import dataclass
import re

from domain.enums import PolicyFlagCode


@dataclass(slots=True)
class SafetyFlagDraft:
    flag_code: PolicyFlagCode
    severity_score: float
    message: str
    evidence_json: dict[str, object]


class SafetyService:
    fabrication_patterns = [
        (
            PolicyFlagCode.FABRICATION_REQUEST,
            0.95,
            re.compile(r"(없는\s*활동|fabricat|invent|지어내|꾸며\s*쓰|허위)", re.IGNORECASE),
        ),
        (
            PolicyFlagCode.DECEPTIVE_POSITIONING,
            0.90,
            re.compile(r"(합격하게\s*보이|best possible narrative|과장|deceptive|좋아\s*보이게)", re.IGNORECASE),
        ),
        (
            PolicyFlagCode.INSUFFICIENT_EVIDENCE,
            0.55,
            re.compile(r"(근거\s*없이|unsupported|증거\s*없이)", re.IGNORECASE),
        ),
    ]

    vague_terms = ("성실", "적극", "리더십", "창의", "열정", "주도성", "관심이 많")
    process_verbs_pattern = re.compile(r"(분석|비교|검증|설계|수정|적용|탐구|실험|조사)")

    def evaluate_query_text(self, query_text: str) -> list[SafetyFlagDraft]:
        flags: list[SafetyFlagDraft] = []
        lowered = query_text.strip()
        for flag_code, severity, pattern in self.fabrication_patterns:
            match = pattern.search(lowered)
            if match:
                flags.append(
                    SafetyFlagDraft(
                        flag_code=flag_code,
                        severity_score=severity,
                        message=f"Potential unsafe request detected: {match.group(0)}",
                        evidence_json={"match": match.group(0)},
                    )
                )
        return flags

    def weak_evidence_reasons(self, text: str) -> list[str]:
        reasons: list[str] = []
        if len(text.strip()) < 40:
            reasons.append("too_short")
        if any(term in text for term in self.vague_terms):
            reasons.append("contains_vague_language")
        if not self.process_verbs_pattern.search(text):
            reasons.append("missing_process_verbs")
        return reasons


safety_service = SafetyService()
