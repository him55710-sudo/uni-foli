import logging
import re
from typing import Any, List, Literal
from pydantic import BaseModel, Field
from unifoli_api.core.llm import get_llm_client, resolve_llm_runtime
from unifoli_api.services.diagnosis_service import DiagnosisResult
from unifoli_api.services.interview_question_strategy import (
    infer_major_track_from_texts,
    major_question_templates_for_context,
    major_strategy_prompt_block,
    render_question_template,
    track_label,
)

logger = logging.getLogger(__name__)

class InterviewQuestion(BaseModel):
    id: str
    category: str = "탐구 과정 검증"
    strategy: str = "근거 검증"
    question: str
    rationale: str
    answer_frame: str = ""
    avoid: str = ""
    expected_evidence_ids: List[str] = Field(default_factory=list)

class InterviewEvaluation(BaseModel):
    score: int = Field(ge=0, le=100)
    grade: Literal["S", "A", "B", "C"] = "C"
    grade_label: str = ""
    axes_scores: dict[str, int] = Field(default_factory=dict)
    feedback: str
    coaching_advice: str
    follow_up_questions: List[str] = Field(default_factory=list)


class InterviewQuestionSet(BaseModel):
    questions: List[InterviewQuestion] = Field(default_factory=list)


_RUBRIC_AXES = ("구체성", "진정성", "학생부 근거 활용", "전공 연결성", "논리적 인과관계")
_GRADE_LABELS = {
    "S": "S 등급 - 입학사정관 압박 질문에도 즉시 방어 가능한 답변",
    "A": "A 등급 - 근거와 논리는 좋으나 꼬리 질문 대비 보강 필요",
    "B": "B 등급 - 활동 설명은 가능하지만 과정·한계·전공 연결이 약함",
    "C": "C 등급 - 학생부 근거와 본인 역할을 다시 구성해야 함",
}
_FOLLOW_UP_STOPWORDS = {
    "그리고",
    "그래서",
    "하지만",
    "때문에",
    "통해서",
    "했습니다",
    "했습니다",
    "있습니다",
    "생각",
    "활동",
    "결과",
    "과정",
    "전공",
    "학생부",
    "보고서",
    "탐구",
}


def _grade_for_score(score: int | float | None) -> Literal["S", "A", "B", "C"]:
    try:
        value = int(score or 0)
    except (TypeError, ValueError):
        value = 0
    if value >= 90:
        return "S"
    if value >= 80:
        return "A"
    if value >= 70:
        return "B"
    return "C"


def _clip(text: Any, limit: int = 220) -> str:
    normalized = " ".join(str(text or "").split()).strip()
    if len(normalized) <= limit:
        return normalized
    return f"{normalized[: limit - 3].rstrip()}..."


def _dedupe_texts(values: list[str], *, limit: int) -> list[str]:
    seen: set[str] = set()
    output: list[str] = []
    for value in values:
        text = _clip(value, 240)
        key = text.lower()
        if not text or key in seen:
            continue
        seen.add(key)
        output.append(text)
        if len(output) >= limit:
            break
    return output


def _evidence_lines_from_diagnosis(diagnosis: DiagnosisResult, *, limit: int = 8) -> list[str]:
    lines: list[str] = []
    for citation in diagnosis.citations[:limit]:
        excerpt = _clip(getattr(citation, "excerpt", ""), 180)
        if not excerpt:
            continue
        page = getattr(citation, "page_number", None)
        source = _clip(getattr(citation, "source_label", "학생부 근거"), 80)
        prefix = f"{source} p.{page}" if isinstance(page, int) else source
        lines.append(f"{prefix}: {excerpt}")

    summary_json = diagnosis.diagnosis_summary_json if isinstance(diagnosis.diagnosis_summary_json, dict) else {}
    evidence_refs = summary_json.get("evidence_references")
    if isinstance(evidence_refs, list):
        for item in evidence_refs[:limit]:
            if not isinstance(item, dict):
                continue
            excerpt = _clip(item.get("excerpt"), 180)
            if not excerpt:
                continue
            page = item.get("page_number")
            source = _clip(item.get("source_label") or "학생부 근거", 80)
            prefix = f"{source} p.{page}" if isinstance(page, int) else source
            lines.append(f"{prefix}: {excerpt}")

    return _dedupe_texts(lines, limit=limit)


def _target_context_from_diagnosis(diagnosis: DiagnosisResult, target_context: str | None = None) -> str:
    candidates: list[str] = []
    if target_context:
        candidates.append(str(target_context))
    for payload in (
        diagnosis.diagnosis_summary_json,
        diagnosis.diagnosis_result_json,
        diagnosis.chatbot_context_json,
    ):
        if not isinstance(payload, dict):
            continue
        for key in (
            "target_context",
            "target_major",
            "major",
            "student_target_context",
            "target_university",
        ):
            value = payload.get(key)
            if isinstance(value, str) and value.strip():
                candidates.append(value)
    return " / ".join(_dedupe_texts(candidates, limit=4))


def _major_label_for_diagnosis(diagnosis: DiagnosisResult, target_context: str | None = None) -> str:
    evidence = _evidence_lines_from_diagnosis(diagnosis, limit=8)
    context = _target_context_from_diagnosis(diagnosis, target_context)
    track = infer_major_track_from_texts(
        context,
        diagnosis.headline,
        diagnosis.recommended_focus,
        *diagnosis.strengths,
        *diagnosis.gaps,
        *diagnosis.risks,
        *evidence,
    )
    return track_label(track)


def _diagnosis_context(diagnosis: DiagnosisResult, target_context: str | None = None) -> str:
    strengths = _dedupe_texts([str(item) for item in diagnosis.strengths], limit=5)
    gaps = _dedupe_texts([str(item) for item in diagnosis.gaps], limit=5)
    risks = _dedupe_texts([str(item) for item in diagnosis.risks], limit=5)
    evidence = _evidence_lines_from_diagnosis(diagnosis, limit=8)
    resolved_target_context = _target_context_from_diagnosis(diagnosis, target_context)
    parts = [
        f"진단 헤드라인: {_clip(diagnosis.headline, 260)}",
        f"추천 보완 초점: {_clip(diagnosis.recommended_focus, 260)}",
        f"기록 상태: {diagnosis.record_completion_state}",
    ]
    if resolved_target_context:
        parts.append(f"지원 맥락: {_clip(resolved_target_context, 320)}")
    if strengths:
        parts.append("강점:\n- " + "\n- ".join(strengths))
    if gaps:
        parts.append("보완점:\n- " + "\n- ".join(gaps))
    if risks:
        parts.append("리스크:\n- " + "\n- ".join(risks))
    if evidence:
        parts.append("학생부 직접 근거:\n- " + "\n- ".join(evidence))
    else:
        parts.append("학생부 직접 근거: 인용 근거가 제한적이므로 질문은 검증형으로 작성해야 함")
    return "\n\n".join(parts)


def _fallback_questions(
    diagnosis: DiagnosisResult,
    *,
    target_context: str | None = None,
    limit: int = 5,
) -> list[InterviewQuestion]:
    strengths = _dedupe_texts([str(item) for item in diagnosis.strengths], limit=3)
    gaps = _dedupe_texts([str(item) for item in diagnosis.gaps], limit=3)
    evidence = _evidence_lines_from_diagnosis(diagnosis, limit=3)
    main_strength = strengths[0] if strengths else "가장 의미 있었던 학생부 활동"
    main_gap = gaps[0] if gaps else "보완이 필요한 근거"
    main_evidence = evidence[0] if evidence else "학생부에 남아 있는 직접 근거"
    major_label = _major_label_for_diagnosis(diagnosis, target_context)
    major_templates = [
        render_question_template(template, major_label=major_label)
        for template in major_question_templates_for_context(
            target_context=_target_context_from_diagnosis(diagnosis, target_context),
            evidence_texts=[*strengths, *gaps, *evidence],
            limit=2,
        )
    ]
    questions = [
        InterviewQuestion(
            id="iq-grounded-1",
            category="탐구 과정 검증",
            strategy="프로세스 디테일",
            question=(
                f"{main_strength}와 관련해 동기-과정-결과-배운점 중 '과정'에서 본인이 맡은 구체적 역할은 무엇이고, "
                "왜 그 방법을 선택했으며 당시 배제한 대안은 무엇이었나요?"
            ),
            rationale="강점으로 제시된 기록을 학생의 실제 의사결정 과정으로 방어할 수 있는지 확인합니다.",
            answer_frame="문제 상황 - 선택한 방법 - 배제한 대안 - 결과와 한계 - 다음 탐구 순서로 답변합니다.",
            avoid="활동을 했다는 사실이나 결과만 말하고 본인의 판단 기준을 생략하는 답변",
            expected_evidence_ids=[main_evidence],
        ),
        InterviewQuestion(
            id="iq-grounded-2",
            category="전공 적합성",
            strategy="전공 심화",
            question=f"{main_evidence} 근거를 기준으로, 이 활동에서 사용한 전문 용어의 근본 원리를 고교 수준으로 설명하고 {major_label} 역량으로 이어지는 지점을 말해 주세요.",
            rationale="학생부 원문 근거와 전공 적합성을 원리 수준으로 연결하는 답변력을 평가합니다.",
            answer_frame="원문 근거 - 핵심 개념 정의 - 활동 적용 - 전공 역량 연결 순서로 답변합니다.",
            avoid="전공과 관련 있다고만 말하고 개념의 원리나 적용 지점을 설명하지 않는 답변",
            expected_evidence_ids=[main_evidence],
        ),
        InterviewQuestion(
            id="iq-grounded-3",
            category="약점 방어",
            strategy="약점 보완",
            question=f"진단에서 '{main_gap}'이 보완점으로 잡혔습니다. 면접에서 이 약점을 질문받는다면 어떤 사실, 원인 분석, 후속 행동으로 방어하겠습니까?",
            rationale="약점 은폐가 아니라 확인 가능한 근거와 다음 행동으로 방어하는지 봅니다.",
            answer_frame="인정할 부분 - 실제 남은 근거 - 부족했던 원인 - 보완 행동 순서로 답변합니다.",
            avoid="약점이 없다고 부정하거나 학생부에 없는 성과를 덧붙이는 답변",
            expected_evidence_ids=evidence[:2],
        ),
        InterviewQuestion(
            id="iq-grounded-4",
            category="탐구 과정 검증",
            strategy="Logic Trap",
            question="만약 조건 A가 바뀌었다면 결과가 어떻게 달라졌을까요? 본인이 사용한 방법의 치명적인 한계점과 함께 설명해 주세요.",
            rationale="성공 결과만 말하는 답변을 막고 가설적 상황에서의 순발력과 논증력을 검증합니다.",
            answer_frame="예상 - 실제 결과 - 해석 충돌 - 새 가설 - 다음 검증 방법 순서로 답변합니다.",
            avoid="예상대로 잘 됐다고만 말하고 해석의 흔들림이나 한계를 숨기는 답변",
            expected_evidence_ids=evidence[:2],
        ),
        InterviewQuestion(
            id="iq-grounded-5",
            category="전공 적합성",
            strategy="So-What",
            question=f"학생부에 기록된 여러 활동 중 하나만 대표 사례로 골라야 한다면 무엇을 고르고, 그 경험이 {major_label}를 바라보는 관점을 어떻게 바꿨나요?",
            rationale="활동 나열이 아니라 일관된 성장 서사와 전공관 변화를 구성할 수 있는지 확인합니다.",
            answer_frame="대표 활동 - 선택 이유 - 다른 활동과의 연결 - 전공관 변화 순서로 답변합니다.",
            avoid="여러 활동을 나열만 하고 핵심 사례와 변화 지점을 정하지 못하는 답변",
            expected_evidence_ids=evidence[:3],
        ),
    ]
    for index, template in enumerate(major_templates, start=1):
        questions.insert(
            min(index + 1, len(questions)),
            InterviewQuestion(
                id=f"iq-major-{index}",
                category=template.category,
                strategy=template.strategy,
                question=template.question,
                rationale=template.intent,
                answer_frame=template.answer_frame,
                avoid=template.avoid,
                expected_evidence_ids=evidence[:2],
            ),
        )
    return questions[:limit]


def _normalize_questions(
    raw_questions: list[InterviewQuestion],
    diagnosis: DiagnosisResult,
    target_context: str | None = None,
) -> list[InterviewQuestion]:
    fallback = _fallback_questions(diagnosis, target_context=target_context)
    combined = [*raw_questions, *fallback]
    normalized: list[InterviewQuestion] = []
    seen: set[str] = set()
    for index, item in enumerate(combined, start=1):
        question = _clip(item.question, 320)
        if not question:
            continue
        key = question.lower()
        if key in seen:
            continue
        seen.add(key)
        normalized.append(
            InterviewQuestion(
                id=_clip(item.id, 60) or f"iq-{index}",
                category=_clip(item.category, 40) or "탐구 과정 검증",
                strategy=_clip(item.strategy, 60) or "근거 검증",
                question=question,
                rationale=_clip(item.rationale, 260) or "학생부 근거 기반 면접 검증 질문입니다.",
                answer_frame=_clip(item.answer_frame, 360),
                avoid=_clip(item.avoid, 260),
                expected_evidence_ids=_dedupe_texts(
                    [str(value) for value in item.expected_evidence_ids],
                    limit=4,
                ),
            )
        )
        if len(normalized) >= 5:
            break
    return normalized


def _extract_follow_up_keywords(answer: str, context: str, *, limit: int = 3) -> list[str]:
    tokens = re.findall(r"[A-Za-z가-힣0-9]{2,}", str(answer or ""))
    context_text = str(context or "")
    seen: set[str] = set()
    scored: list[tuple[int, int, str]] = []
    for index, token in enumerate(tokens):
        text = token.strip()
        key = text.lower()
        if key in seen or key in _FOLLOW_UP_STOPWORDS or len(text) < 2:
            continue
        seen.add(key)
        score = 0
        if text in context_text:
            score += 4
        if re.search(r"[A-Za-z0-9]", text):
            score += 2
        if len(text) >= 4:
            score += 1
        scored.append((score, -index, text))
    scored.sort(reverse=True)
    return [item[2] for item in scored[:limit]]


def _fallback_follow_up_questions(question: str, answer: str, context: str, *, limit: int = 3) -> list[str]:
    keywords = _extract_follow_up_keywords(answer, context, limit=limit) or ["방금 언급한 핵심 개념"]
    first = keywords[0]
    candidates = [
        f"방금 '{first}'를 언급했는데, 그 개념의 근본 원리를 고교 수준에서 설명하고 어떤 학생부 근거로 확인할 수 있나요?",
        f"'{first}'와 관련해 조건 A가 바뀐다면 결과가 어떻게 달라질까요? 그 방법의 치명적인 한계까지 함께 말해 보세요.",
    ]
    if len(keywords) >= 2:
        candidates.append(
            f"'{keywords[1]}'이 다음 활동이나 후속 탐구에 준 지적 자극은 무엇이었고, 실제로 바꾼 질문이나 방법은 무엇인가요?"
        )
    else:
        candidates.append(
            "답변에서 말한 활동이 다음 활동이나 독서로 이어졌다면, 구체적으로 어떤 자료를 참고했고 질문이 어떻게 바뀌었나요?"
        )
    return candidates[:limit]


def _fallback_evaluation(question: str, answer: str, context: str) -> InterviewEvaluation:
    normalized_answer = " ".join(str(answer or "").split()).strip()
    normalized_context = " ".join(str(context or "").split()).strip()
    lowered_answer = normalized_answer.lower()
    context_terms = [
        term
        for term in set(str(context or "").replace("\n", " ").split())
        if len(term) >= 3 and term in normalized_answer
    ]
    specificity = min(88, 35 + len(normalized_answer) // 12)
    authenticity = 78 if any(token in normalized_answer for token in ("느꼈", "배웠", "어려움", "한계", "개선")) else 58
    evidence_usage = min(88, 45 + len(context_terms) * 8)
    if any(token in normalized_answer for token in ("활동", "보고서", "실험", "탐구", "세특", "학생부")):
        evidence_usage = max(evidence_usage, 68)
    major_alignment = 80 if any(token in normalized_answer for token in ("전공", "학과", "진로", "지원")) else 58
    if any(token in lowered_answer for token in ("because", "method", "result", "limit")):
        specificity = max(specificity, 68)
    causal_markers = (
        "왜",
        "때문",
        "근거",
        "따라서",
        "그래서",
        "원인",
        "결과",
        "한계",
        "대안",
        "판단",
        "비교",
        "검증",
        "변인",
    )
    causal_hits = sum(1 for token in causal_markers if token in normalized_answer)
    causal_logic = min(90, 40 + causal_hits * 7)
    if all(token in normalized_answer for token in ("방법", "결과", "한계")):
        causal_logic = max(causal_logic, 78)

    axes_scores = {
        "구체성": max(0, min(100, specificity)),
        "진정성": max(0, min(100, authenticity)),
        "학생부 근거 활용": max(0, min(100, evidence_usage)),
        "전공 연결성": max(0, min(100, major_alignment)),
        "논리적 인과관계": max(0, min(100, causal_logic)),
    }
    total_score = int(sum(axes_scores.values()) / len(axes_scores))
    grade = _grade_for_score(total_score)
    feedback_parts = []
    if len(normalized_answer) < 180:
        feedback_parts.append("답변 길이가 짧아 활동 배경, 본인 역할, 결과 해석이 충분히 분리되지 않았습니다.")
    if evidence_usage < 65:
        feedback_parts.append("학생부 원문 근거를 직접 인용하거나 활동명을 명확히 연결해야 합니다.")
    if major_alignment < 65:
        feedback_parts.append("지원 전공에서 요구하는 개념이나 역량과의 연결을 한 문장 더 보강하세요.")
    if causal_logic < 65:
        feedback_parts.append("왜 그 방법을 선택했는지, 대안은 무엇이었는지, 결과가 다음 판단으로 어떻게 이어졌는지를 분리하세요.")
    if not feedback_parts:
        feedback_parts.append("답변이 학생부 근거와 개인 성찰을 비교적 안정적으로 연결하고 있습니다.")

    return InterviewEvaluation(
        score=total_score,
        grade=grade,
        grade_label=_GRADE_LABELS[grade],
        axes_scores=axes_scores,
        feedback=" ".join(feedback_parts),
        coaching_advice=(
            "다음 답변은 '활동명 또는 원문 근거 -> 내가 한 판단/방법 -> 결과와 한계 -> 전공 연결' "
            "순서로 4문장 안에 압축해 보세요."
        ),
        follow_up_questions=_fallback_follow_up_questions(question, answer, context),
    )


def _normalize_evaluation(
    value: InterviewEvaluation,
    *,
    question: str = "",
    answer: str = "",
    context: str = "",
) -> InterviewEvaluation:
    axes_scores: dict[str, int] = {}
    try:
        fallback_score = max(0, min(100, int(value.score)))
    except (TypeError, ValueError):
        fallback_score = 0
    for axis in _RUBRIC_AXES:
        raw = value.axes_scores.get(axis, fallback_score)
        try:
            score = int(raw)
        except (TypeError, ValueError):
            score = 0
        axes_scores[axis] = max(0, min(100, score))
    score = value.score
    if axes_scores:
        score = int(sum(axes_scores.values()) / len(axes_scores))
    grade = _grade_for_score(score)
    follow_ups = _dedupe_texts([str(item) for item in value.follow_up_questions], limit=3)
    if not follow_ups and answer:
        follow_ups = _fallback_follow_up_questions(question, answer, context)
    return InterviewEvaluation(
        score=max(0, min(100, int(score))),
        grade=grade,
        grade_label=_GRADE_LABELS[grade],
        axes_scores=axes_scores,
        feedback=_clip(value.feedback, 700) or "평가 피드백을 생성하지 못했습니다.",
        coaching_advice=_clip(value.coaching_advice, 700) or "학생부 근거와 본인 역할을 더 구체적으로 연결하세요.",
        follow_up_questions=follow_ups,
    )


class InterviewService:
    async def generate_questions(
        self,
        diagnosis: DiagnosisResult,
        target_major: str | None = None,
        *,
        target_context: str | None = None,
    ) -> List[InterviewQuestion]:
        """
        Generates grounded interview questions based on the diagnosis result and evidence.
        """
        try:
            runtime = resolve_llm_runtime(profile="standard", concern="diagnosis")
            client = runtime.client or get_llm_client(profile="standard", concern="diagnosis")
        except Exception as exc:  # noqa: BLE001
            logger.warning("Interview question LLM unavailable; using grounded fallback: %s", exc)
            return _fallback_questions(diagnosis, target_context=target_context or target_major)

        resolved_target_context = _target_context_from_diagnosis(diagnosis, target_context or target_major)
        evidence = _evidence_lines_from_diagnosis(diagnosis, limit=8)
        strategy_block = major_strategy_prompt_block(
            target_context=resolved_target_context,
            evidence_texts=[
                diagnosis.headline,
                diagnosis.recommended_focus,
                *diagnosis.strengths,
                *diagnosis.gaps,
                *diagnosis.risks,
                *evidence,
            ],
            limit=5,
        )
        system_instruction = (
            "당신은 10년 차 이상의 대한민국 주요 대학 베테랑 입학사정관입니다. "
            "학생부종합전형의 핵심인 '학업역량, 전공적합성, 발전가능성, 인성'을 날카롭게 검증하세요. "
            "[입학사정관 페르소나 강화 규칙] "
            "1. 서류 진실성 검증: 학생부 활동의 동기-과정-결과-배운점 중 특히 과정에서의 구체적 역할을 묻고, "
            "학생이 사용한 전문 용어의 근본 원리를 고교 수준에서 설명하게 해 대필 여부를 확인합니다. "
            "2. 논리적 함정: 학생이 성공 결과만 말하지 못하도록 '만약 조건 A가 바뀌었다면 결과가 어떻게 달라졌는가' "
            "또는 '그 방법의 치명적인 한계점은 무엇인가'를 묻습니다. "
            "3. 전공 적합성 뉘앙스: 공학은 비용·시간·성능 중 포기한 가치, 의생명은 생물학적 변이성과 오차 원인, "
            "경영/사회는 정책·전략이 소외시킬 수 있는 계층을 반드시 고려합니다. "
            "4. 꼬리 질문 감각: 답변 속 핵심 단어를 포착해 참고 자료, 후속 탐구, 다음 활동으로 이어진 지적 자극을 파고듭니다. "
            "1. WHY-HOW-LEARN 프레임워크: 단순히 활동 사실을 묻지 말고, '왜(동기) -> 어떻게(구체적 과정/판단) -> 무엇을(배운 점/생각의 변화)'의 인과관계를 집요하게 묻습니다. "
            "2. Logic Trap(논리적 함정): 생기부에 기재된 심화 개념이나 화려한 실험 결과에 대해, 실제 원리 수준의 이해도가 있는지 확인하는 원리 검증 질문을 반드시 포함하세요. "
            "3. 성장 궤적 확인: 활동이 일회성으로 끝나지 않고, 다음 탐구나 독서, 혹은 다른 과목과의 융합으로 어떻게 확장되었는지(Academic Linkage) 질문하세요. "
            "4. 전공별 핀셋 전략: \n"
            "   - 의학/보건: 생명윤리적 가치 충돌 상황에서의 의사결정 기준\n"
            "   - 공학/IT: 설계 과정의 수치적 근거, 예외 상황 처리, 기술의 한계 인식\n"
            "   - 경영/경제: 지표 해석의 오류 가능성, 이해관계자 간의 갈등 조정\n"
            "   - 인문/사회: 보편적 가치에 대한 비판적 재해석, 사회적 책임과 실천\n"
            "   - 교육: 학습자 다양성 고려, 교육의 공정성과 현장 적용성\n"
            "5. 근거 기반: 모든 질문은 반드시 제공된 학생부 텍스트 근거 내에서만 생성하며, 허구의 상황을 가정하지 않습니다."
        )
        
        prompt = (
            "제공된 학생부 근거를 바탕으로 5개의 Killer Questions를 생성하세요. "
            "각 질문은 아래 전략 중 하나 이상을 포함해야 합니다.\n"
            "- [전공 심화]: 지원 전공의 핵심 원리와 활동을 연결하여 논리적 일관성을 검증\n"
            "- [프로세스 디테일]: 활동 중 본인이 내린 의사결정의 근거와 한계점 극복 과정 확인\n"
            "- [사회적 가치]: 전공 지식을 활용해 사회적 문제를 해결하려는 태도 확인\n"
            "- [약점 보완]: 기록에서 보이는 학업적/활동적 공백을 방어할 기회 제공\n"
            "- [Logic Trap]: 고교 수준을 넘어서는 심화 개념의 원리, 한계, 실제 이해 여부 검증\n\n"
            "반드시 최소 1개 질문은 '조건 A가 바뀌었다면' 또는 '치명적인 한계점' 형식의 가설적 논리 함정을 포함하세요. "
            "반드시 최소 1개 질문은 전문 용어의 근본 원리를 고교 수준으로 설명하게 하는 서류 진실성 검증 질문이어야 합니다. "
            "전공군에 따라 공학은 비용·시간·성능의 트레이드오프, 의생명은 생물학적 변이성과 오차 원인, "
            "경영/사회는 소외될 수 있는 계층이나 이해관계자를 반영하세요.\n\n"
            "응답의 각 질문에는 category, strategy, question, rationale, answer_frame, avoid, expected_evidence_ids를 채우세요. "
            "answer_frame은 답변 순서를, avoid는 피해야 할 답변 방식을 구체적으로 쓰세요.\n\n"
            f"[전공별 질문 전략]\n{strategy_block}\n\n"
            f"[진단 데이터 및 근거]\n{_diagnosis_context(diagnosis, resolved_target_context)}"
        )
        
        try:
            response = await client.generate_json(
                prompt=prompt,
                response_model=InterviewQuestionSet,
                system_instruction=system_instruction,
                temperature=0.15,
            )
            return _normalize_questions(response.questions, diagnosis, resolved_target_context)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Failed to generate structured interview questions; using fallback: %s", exc)
            return _fallback_questions(diagnosis, target_context=resolved_target_context)

    async def evaluate_answer(self, question: str, answer: str, context: str) -> InterviewEvaluation:
        """
        Evaluates the student's answer based on the interview rubric axes.
        """
        if not str(answer or "").strip():
            return InterviewEvaluation(
                score=0,
                grade="C",
                grade_label=_GRADE_LABELS["C"],
                axes_scores={axis: 0 for axis in _RUBRIC_AXES},
                feedback="답변이 비어 있어 평가할 수 없습니다.",
                coaching_advice="질문과 연결되는 학생부 활동명, 본인 역할, 결과와 배운 점을 먼저 3문장으로 작성하세요.",
            )

        try:
            runtime = resolve_llm_runtime(profile="standard", concern="diagnosis")
            client = runtime.client or get_llm_client(profile="standard", concern="diagnosis")
        except Exception as exc:  # noqa: BLE001
            logger.warning("Interview evaluation LLM unavailable; using rubric fallback: %s", exc)
            return _fallback_evaluation(question, answer, context)

        system_instruction = (
            "당신은 학생부종합전형 면접 답변을 채점하는 입학사정관입니다. "
            "학생부 근거 밖의 사실(허위 사실)을 답변에 포함했을 경우 엄격하게 감점하세요. "
            "답변의 논리 구조가 '동기-과정-판단 근거-결과-한계-성찰'을 갖추었는지, "
            "질문의 의도를 정확히 파악했는지 보수적으로 평가합니다. "
            "답변에서 핵심 단어를 포착해 참고 자료, 후속 탐구, 조건 변화, 치명적 한계점을 묻는 꼬리 질문을 생성하세요."
        )
        prompt = (
            "다음 면접 답변을 평가 축별로 0~100점 채점하세요.\n"
            "채점 기준:\n"
            "- 90점 이상: 활동의 원리, 의사결정 근거, 본인의 역할, 결과 해석, 한계, 전공 연결이 인과적으로 연결됨.\n"
            "- 70~80점: 내용은 구체적이나 대안 검토, 한계 분석, 전공적 의미가 일부 평이함.\n"
            "- 60점 이하: 답변이 추상적이거나 학생부 근거를 단순히 나열만 함.\n"
            "- 40점 이하: 질문과 상관없는 답변을 하거나 근거 없는 사실을 주장함.\n\n"
            "특히 '논리적 인과관계'는 왜 그 방법을 선택했는지, 대안은 무엇이었는지, 결과가 다음 판단으로 "
            "어떻게 이어졌는지까지 확인해 엄격히 채점하세요.\n\n"
            "follow_up_questions에는 이전 답변의 핵심 단어를 잡아 2~3개의 꼬리 질문을 작성하세요. "
            "꼬리 질문은 '어떤 논문/자료/원문 근거를 참고했는가', '다음 활동에 어떤 지적 자극을 줬는가', "
            "'조건이 바뀌면 결과가 어떻게 달라지는가', '치명적인 한계는 무엇인가' 중 최소 2개 관점을 포함해야 합니다.\n\n"
            f"[질문]\n{_clip(question, 600)}\n\n"
            f"[학생 답변]\n{_clip(answer, 2400)}\n\n"
            f"[학생부/진단 근거]\n{_clip(context, 2400)}\n\n"
            f"[평가 축]\n{', '.join(_RUBRIC_AXES)}"
        )

        try:
            evaluation = await client.generate_json(
                prompt=prompt,
                response_model=InterviewEvaluation,
                system_instruction=system_instruction,
                temperature=0.0,
            )
            return _normalize_evaluation(evaluation, question=question, answer=answer, context=context)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Failed to evaluate interview answer with LLM; using rubric fallback: %s", exc)
            return _fallback_evaluation(question, answer, context)
