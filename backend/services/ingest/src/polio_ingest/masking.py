from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple, TypedDict

logger = logging.getLogger(__name__)

class RedactionReport(TypedDict):
    hard_redactions: List[str]
    generalizations: List[str]
    kept_sections: List[str]

class RedactionResponse(TypedDict):
    redacted_text: str
    redaction_report: RedactionReport
    review_flags: List[str]

@dataclass
class RedactorConfig:
    """Configuration for the Student Record Redactor."""
    academic_year_start_month: int = 3
    first_semester_end_month: int = 8
    mask_char: str = "*"

class StudentLifeRecordRedactor:
    """
    Production-grade redactor specifically designed for South Korean High School Student Records (School Life Records).
    Focuses on removing PII while preserving academic evaluation data for LLM diagnosis.
    """

    def __init__(self, config: Optional[RedactorConfig] = None):
        self.config = config or RedactorConfig()
        self._init_patterns()

    def _init_patterns(self):
        # 1. Hard Redactions (Direct Identifiers)
        self.HARD_PATTERNS = {
            "rrn": re.compile(r"\b\d{6}-?\d{7}\b"),  # Resident Registration Number
            "rrn_masked": re.compile(r"\b\d{6}-\*{6,7}\b"),
            "phone": re.compile(r"\b0\d{1,2}-\d{3,4}-\d{4}\b"),
            "doc_num": re.compile(r"(?:문서확인번호|발급번호|졸업대장번호)\s*[:：]?\s*([A-Za-z0-9-]+)"),
            "address": re.compile(r"(?:주소|거주지)\s*[:：]?\s*([^\n\r,]+(?:길|로|동|읍|면|리|구|시)\s*\d+[^(\n\r]+)"),
            "student_label": re.compile(r"(?:성명|이름)\s*[:：]?\s*([\uAC00-\uD7A3]{2,4})"),
            "staff_label": re.compile(r"(?:담임|학교장|교장|교감|행정실장|담당자|행정\s*담당)\s*(?:성명|이름)?\s*[:：]?\s*([\uAC00-\uD7A3]{2,4})"),
        }

        # 2. Generalization Patterns
        self.GEN_PATTERNS = {
            "high_school": re.compile(r"[\uAC00-\uD7A3]{2,10}(?:고등학교|공고|상고|외고|과학고|예고)\b"),
            "middle_school": re.compile(r"[\uAC00-\uD7A3]{2,10}중학교\b"),
            "class_info": re.compile(r"(\d+)\s*(?:학년|학기|반|번)\s*(\d+)?\s*(?:반|번)?"),
            "date": re.compile(r"\b(\d{4})[./-](\d{1,2})[./-](\d{1,2})\b"),
            "local_inst": re.compile(r"[\uAC00-\uD7A3]{2,5}(?:시|군|구|도)\s*(?:청|교육청|도서관|센터|기관)\b"),
        }

        # 3. Repeated Layout Patterns (Headers/Footers)
        # Typically: [School Name] [YYYY.MM.DD] [Page Num] [Student ID] [Student Name]
        self.FOOTER_PATTERN = re.compile(r"^(?:[\uAC00-\uD7A3]+\s*고등학교.*|\d{4}\.\d{2}\.\d{2}.*|.*\d+\s*/\s*\d+\s*페이지.*)$", re.MULTILINE)

    def redact(self, text: str, layout_blocks: Optional[List[Dict[str, Any]]] = None) -> RedactionResponse:
        """
        Main entry point for redaction.
        Cycles through hard redaction, generalization, and structural cleanup.
        """
        if not text:
            return {
                "redacted_text": "",
                "redaction_report": {"hard_redactions": [], "generalizations": [], "kept_sections": []},
                "review_flags": []
            }

        report = RedactionReport(hard_redactions=[], generalizations=[], kept_sections=[])
        review_flags = []
        
        working_text = text

        # Step 1: Scuff Headers/Footers based on layout/repeating patterns
        working_text = self._scrub_layout_patterns(working_text, report)

        # Step 2: Hard Redaction (Direct Identifiers)
        working_text = self._apply_hard_redactions(working_text, report, review_flags)

        # Step 3: Generalizations (Schools, Dates, Class info)
        working_text = self._apply_generalizations(working_text, report)

        # Step 4: Final Integrity Check (Flag potential leftovers)
        self._check_integrity(working_text, review_flags)

        # Identity preserved sections (for report)
        report["kept_sections"] = ["세부능력 및 특기사항", "창의적 체험활동", "성적표", "행동특성 및 종합의견"]

        return {
            "redacted_text": working_text,
            "redaction_report": report,
            "review_flags": list(set(review_flags))
        }

    def _scrub_layout_patterns(self, text: str, report: RedactionReport) -> str:
        """Removes repetitive identifying footer/header patterns."""
        count_before = len(text)
        # Remove lines that look like page footers
        lines = text.splitlines()
        filtered_lines = [line for line in lines if not self.FOOTER_PATTERN.match(line.strip())]
        
        if len(filtered_lines) < len(lines):
            report["hard_redactions"].append("Repetitive Layout Header/Footer")
            
        return "\n".join(filtered_lines)

    def _apply_hard_redactions(self, text: str, report: RedactionReport, flags: List[str]) -> str:
        res = text
        
        # Resident Registration Number
        res, count = self.HARD_PATTERNS["rrn"].subn("[주민등록번호]", res)
        if count: report["hard_redactions"].append(f"SSN Pattern ({count})")
        
        res, count = self.HARD_PATTERNS["rrn_masked"].subn("[주민등록번호]", res)
        if count: report["hard_redactions"].append(f"Masked SSN Pattern ({count})")

        # Phone Number
        res, count = self.HARD_PATTERNS["phone"].subn("[전화번호]", res)
        if count: report["hard_redactions"].append(f"Phone Number ({count})")

        # Document IDs
        res, count = self.HARD_PATTERNS["doc_num"].subn("[문서 식별 번호]", res)
        if count: report["hard_redactions"].append("Document Verification ID")

        # Address (Conditional masking to preserve city info if needed, but here we go full blind per request)
        res, count = self.HARD_PATTERNS["address"].subn("[상세 주소]", res)
        if count: report["hard_redactions"].append("Home Address Line")

        # Names (Labeled)
        def redact_name(match):
            label = match.group(0).split(':')[0].strip() if ':' in match.group(0) else ""
            if "담임" in match.group(0):
                return match.group(0).replace(match.group(1), "[담임교사]")
            return match.group(0).replace(match.group(1), "[학생명]") if any(x in match.group(0) for x in ["성명", "이름"]) else match.group(0).replace(match.group(1), "[인명]")

        res, count = self.HARD_PATTERNS["student_label"].subn(redact_name, res)
        if count: report["hard_redactions"].append(f"Student Name Labels ({count})")

        res, count = self.HARD_PATTERNS["staff_label"].subn(redact_name, res)
        if count: report["hard_redactions"].append(f"Staff Name Labels ({count})")

        return res

    def _apply_generalizations(self, text: str, report: RedactionReport) -> str:
        res = text

        # Schools
        res, count_h = self.GEN_PATTERNS["high_school"].subn("[고등학교]", res)
        res, count_m = self.GEN_PATTERNS["middle_school"].subn("[중학교]", res)
        if count_h or count_m: report["generalizations"].append("School Names")

        # Local Institutions
        res, count = self.GEN_PATTERNS["local_inst"].subn("[지역 기관]", res)
        if count: report["generalizations"].append("Region-Specific Institutions")

        # Class/Grade Info
        res, count = self.GEN_PATTERNS["class_info"].subn("[학급정보]", res)
        if count: report["generalizations"].append("Grade/Class Details")

        # Dates (Academic Normalization)
        def date_repl(match):
            year, month, _ = match.groups()
            y_int, m_int = int(year), int(month)
            
            # Simple semester heuristic per user prompt examples
            # 1st: March - August -> YYYY년 1학기
            # 2nd: September - February (academic year is y-1 if Jan/Feb) -> YYYY학년도 2학기
            if self.config.academic_year_start_month <= m_int <= self.config.first_semester_end_month:
                return f"{y_int}년 1학기"
            else:
                target_year = y_int if m_int >= self.config.academic_year_start_month else y_int - 1
                return f"{target_year}학년도 2학기"

        res, count = self.GEN_PATTERNS["date"].subn(date_repl, res)
        if count: report["generalizations"].append(f"Date Normalization ({count})")

        return res

    def _check_integrity(self, text: str, flags: List[str]):
        """Flags suspicious fragments that might need human review."""
        # Check for 3-character sequences that look like Korean names without labels
        # (Very sensitive/noisy, but good for flags)
        potential_names = re.findall(r"\b[\uAC00-\uD7A3]{3}\b", text)
        if len(potential_names) > 50: # Arbitrary threshold for diagnostic safety
             # Maybe a list of common eval terms to subtract
             pass
        
        # Check if RRN patterns still exist
        if re.search(r"\d{6}-?\d{7}", text):
            flags.append("RESIDUAL_SSN_DETECTED")
        
        # Check if too much was deleted
        if len(text) < 100 and len(text) > 0:
            flags.append("OVER_REDACTION_WARNING")

    def mock_image_masking(self, image_data: Any) -> Dict[str, Any]:
        """
        Structural placeholder for face/seal/QR detection logic.
        In a real prod env, this would use OpenCV/dlib or cloud APIs.
        """
        return {
            "detections": [
                {"type": "student_photo", "action": "blur", "confidence": 0.99},
                {"type": "seal", "action": "mask", "confidence": 0.98},
                {"type": "qr_code", "action": "mask", "confidence": 1.0}
            ],
            "status": "redacted"
        }

@dataclass(slots=True)
class MaskingResult:
    """Compatibility structure for existing pipelines."""
    text: str
    method: str = "student_record_redactor_v2"
    replacements: int = 0
    applied_presidio: bool = False
    applied_regex: bool = True
    pattern_hits: Dict[str, int] = field(default_factory=dict)
    warnings: List[str] = field(default_factory=list)

class MaskingPipeline:
    """Wrapper for backward compatibility with existing ingest services."""
    def __init__(self, config: Optional[RedactorConfig] = None):
        self.redactor = StudentLifeRecordRedactor(config)

    def apply_masking(self, text: str) -> str:
        res = self.redactor.redact(text)
        return res["redacted_text"]

    def mask_text(self, text: str) -> MaskingResult:
        res = self.redactor.redact(text)
        report = res["redaction_report"]
        
        # Map report to pattern hits for compatibility
        pattern_hits = {item: 1 for item in report["hard_redactions"] + report["generalizations"]}
        
        return MaskingResult(
            text=res["redacted_text"],
            pattern_hits=pattern_hits,
            warnings=res["review_flags"]
        )

def process_student_record(ocr_text: str) -> RedactionResponse:
    """Helper function to run the redaction pipeline."""
    redactor = StudentLifeRecordRedactor()
    return redactor.redact(ocr_text)

# --- Test Case ---
if __name__ == "__main__":
    sample_text = """
    문서확인번호: 1234-5678-ABCD
    서울고등학교 2024.05.15 1 / 15 페이지 3학년 2반 15번 김철수
    
    [성적표]
    국어: 원점수 95, 과목평균 72.5, 표준편차 15.2, 성취도 A, 석차등급 1
    
    [세부능력 및 특기사항]
    기후변화와 경제를 연결한 탐구 주제(2024.06.10)에서 탄소국경세의 국내 파급효과를 분석함.
    담임교사: 홍길동 (인)
    
    학생 주소: 서울특별시 강남구 테헤란로 123, 456호
    연락처: 010-1234-5678
    주민등록번호: 060101-3123456
    """
    
    processed = process_student_record(sample_text)
    import json
    print(json.dumps(processed, indent=2, ensure_ascii=False))
