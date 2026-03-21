import json
import os
import google.generativeai as genai
from pydantic import BaseModel, Field
from typing import Literal

genai.configure(api_key=os.environ.get("GEMINI_API_KEY", "DUMMY_KEY"))

class OverallEval(BaseModel):
    score: int = Field(description="0~100 사이의 전공 적합도 점수 (정수)")
    summary: str = Field(description="1줄 종합 평가 (예: ⚠️ 위험: 경영학 지원자이나 수리적 통계 분석 경험이 전무함)")

class SubjectEval(BaseModel):
    name: str = Field(description="과목명 (예: 수학, 생명과학)")
    status: Literal['safe', 'warning', 'danger']
    feedback: str = Field(description="사정관 시점의 팩트 폭행 코멘트 (50자 이내)")

class PrescriptionEval(BaseModel):
    message: str = Field(description="모달 최하단에 띄울 Poli의 제안 문구")
    recommendedTopic: str = Field(description="추천하는 구체적인 탐구 보고서 주제 1개")

class DiagnosisResult(BaseModel):
    overall: OverallEval
    subjects: list[SubjectEval]
    prescription: PrescriptionEval

async def evaluate_student_record(
    user_major: str,
    masked_text: str,
    target_university: str | None = None,
    target_major: str | None = None,
) -> DiagnosisResult:
    """
    Pydantic 기반의 Structured Output을 사용하여 생기부(NEIS)를 진단합니다.
    Gemini API에 response_schema를 강제 주입하여 무조건 파싱 가능한 JSON 객체만 반환하도록 방어합니다.
    """
    system_instruction = (
        "당신은 대한민국 명문대(서울대, 연세대, 고려대) 학생부 종합 전형의 평가 기준을 완벽하게 꿰뚫고 있는 "
        "냉혹하고 예리한 입시 컨설턴트입니다. 입력된 학생의 목표 학과와 마스킹된 생기부 세특 텍스트를 분석하여, "
        "학생의 강점과 치명적인 약점을 진단하고 주어진 JSON 구조에 맞추어 평가를 반환하세요."
    )
    target_context = (
        f"Target University (목표 대학): {target_university or '미정'}\n"
        f"Target Major (희망 전공): {target_major or user_major}"
    )
    
    # 요구사항의 "Gemini 3.1 Pro" 대응. 현재 SDK에서 Structured Output을 지원하는 gemini-1.5-pro 모델 사용
    model = genai.GenerativeModel(
        model_name="gemini-1.5-pro",
        system_instruction=system_instruction
    )
    
    try:
        response = await model.generate_content_async(
            f"{target_context}\nPrimary Major Context (진단 기준 전공): {user_major}\nMasked NEIS Text (생기부 텍스트): {masked_text}",
            generation_config=genai.GenerationConfig(
                response_mime_type="application/json",
                response_schema=DiagnosisResult,
                temperature=0.2 # 평가의 일관성을 위해 낮은 temperature 적용
            )
        )
        
        # 100% 보장된 JSON 스키마를 Pydantic 객체로 재검증 및 반환
        return DiagnosisResult.model_validate_json(response.text)
        
    except Exception as e:
        # API Limit, Timeout, 파싱 에러 발생 시 프론트엔드 크래시를 막기 위한 리턴 방어벽
        return DiagnosisResult(
            overall=OverallEval(score=0, summary=f"시스템 오류로 진단에 실패했습니다. (Error: {str(e)})"),
            subjects=[],
            prescription=PrescriptionEval(
                message="서버와 연결을 다시 시도해주세요.",
                recommendedTopic="없음"
            )
        )
