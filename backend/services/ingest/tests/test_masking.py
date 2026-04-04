import pytest
import json
from polio_ingest.masking import StudentLifeRecordRedactor, process_student_record

def test_hard_redactions():
    sample = "성명: 김철수, 주민등록번호: 060101-3123456, 연락처: 010-1234-5678"
    result = process_student_record(sample)
    
    assert "[학생명]" in result["redacted_text"]
    assert "[주민등록번호]" in result["redacted_text"]
    assert "[전화번호]" in result["redacted_text"]
    assert "김철수" not in result["redacted_text"]
    assert "060101-3123456" not in result["redacted_text"]

def test_date_generalization():
    redactor = StudentLifeRecordRedactor()
    
    # 1st Semester (March)
    res1 = redactor.redact("2024.03.15")
    assert "2024학년도 1학기" in res1["redacted_text"]
    
    # 2nd Semester (October)
    res2 = redactor.redact("2024.10.10")
    assert "2024학년도 2학기" in res2["redacted_text"]
    
    # 2nd Semester (January next year - belongs to prev academic year)
    res3 = redactor.redact("2025.01.20")
    assert "2024학년도 2학기" in res3["redacted_text"]

def test_school_generalization():
    sample = "서울과학고등학교 졸업 후 한국대학교 진학"
    result = process_student_record(sample)
    
    assert "[고등학교]" in result["redacted_text"]
    assert "서울과학고등학교" not in result["redacted_text"]

def test_preservation_of_academic_data():
    sample = "[성적표] 국어: 원점수 95, 석차등급 1. [세부능력] 기후변화 탐구 수행."
    result = process_student_record(sample)
    
    assert "95" in result["redacted_text"]
    assert "석차등급 1" in result["redacted_text"]
    assert "기후변화 탐구" in result["redacted_text"]

def test_footer_removal():
    sample = "본문 내용\n서울고등학교 2024.05.15 1 / 15 페이지\n다음 본문"
    result = process_student_record(sample)
    
    assert "서울고등학교" not in result["redacted_text"]
    assert "페이지" not in result["redacted_text"]
    assert "본문 내용" in result["redacted_text"]
    assert "다음 본문" in result["redacted_text"]

def test_redaction_report_structure():
    sample = "성명: 김철수, 주소: 서울시 강남구"
    result = process_student_record(sample)
    
    assert "redacted_text" in result
    assert "redaction_report" in result
    assert "review_flags" in result
    assert "hard_redactions" in result["redaction_report"]
    assert len(result["redaction_report"]["hard_redactions"]) > 0

if __name__ == "__main__":
    # If running as a script, just execute one to see output
    res = process_student_record("이름: 이영희, 주민번호: 070202-4567890")
    print(json.dumps(res, indent=2, ensure_ascii=False))
