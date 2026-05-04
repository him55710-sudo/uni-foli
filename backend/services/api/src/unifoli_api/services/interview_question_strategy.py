from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Iterable


@dataclass(frozen=True)
class MajorInterviewQuestionTemplate:
    category: str
    strategy: str
    question: str
    intent: str
    answer_frame: str
    good_direction: str
    avoid: str


_MAJOR_TRACK_KEYWORDS: dict[str, tuple[str, ...]] = {
    "bio_medical": (
        "의학",
        "의예",
        "치의",
        "한의",
        "약학",
        "간호",
        "수의",
        "보건",
        "공중보건",
        "생명",
        "생명과학",
        "바이오",
        "유전",
        "세포",
        "미생물",
        "면역",
        "신경",
        "임상",
        "환자",
    ),
    "engineering_it": (
        "컴퓨터",
        "소프트웨어",
        "인공지능",
        "ai",
        "데이터",
        "통계",
        "정보",
        "전자",
        "전기",
        "기계",
        "화공",
        "산업공학",
        "로봇",
        "센서",
        "제어",
        "알고리즘",
        "반도체",
        "자동차",
        "모빌리티",
        "공학",
    ),
    "business_economics": (
        "경영",
        "경제",
        "회계",
        "금융",
        "무역",
        "마케팅",
        "소비자",
        "창업",
        "esg",
        "기업",
        "시장",
        "투자",
        "물류",
        "경영정보",
        "산업",
    ),
    "humanities_social": (
        "국어",
        "문학",
        "역사",
        "철학",
        "사회",
        "정치",
        "외교",
        "행정",
        "법학",
        "언론",
        "미디어",
        "심리",
        "사회복지",
        "문화",
        "인문",
    ),
    "education": (
        "교육",
        "사범",
        "교대",
        "유아교육",
        "초등교육",
        "특수교육",
        "교육공학",
        "학습",
        "교사",
        "수업",
    ),
    "natural_science": (
        "수학",
        "물리",
        "화학",
        "지구과학",
        "천문",
        "해양",
        "대기",
        "식품",
        "과학",
        "실험",
        "가설",
    ),
    "environment_energy": (
        "환경",
        "에너지",
        "기후",
        "탄소",
        "재생",
        "전력",
        "수소",
        "태양광",
        "풍력",
        "생태",
        "지속가능",
    ),
    "architecture_design": (
        "건축",
        "건축학",
        "건축공학",
        "도시",
        "공간",
        "토목",
        "조경",
        "디자인",
        "산업디자인",
        "시각디자인",
        "실내",
        "구조",
        "하중",
        "내진",
        "bim",
    ),
}

_TRACK_LABELS: dict[str, str] = {
    "bio_medical": "의학·보건·생명",
    "engineering_it": "공학·컴퓨터·데이터",
    "business_economics": "경영·경제",
    "humanities_social": "인문·사회·미디어",
    "education": "교육",
    "natural_science": "자연과학",
    "environment_energy": "환경·에너지",
    "architecture_design": "건축·도시·디자인",
}

_TRACK_GUIDANCE: dict[str, tuple[str, ...]] = {
    "bio_medical": (
        "단순 지식보다 생명윤리, 환자 안전, 데이터의 공공성 사이의 딜레마 상황에서의 가치 판단을 집요하게 묻습니다.",
        "실험 기록이 있다면 변인 통제뿐 아니라 생물학적 변이성과 오차 원인을 어떻게 연결해 해석했는지 확인합니다.",
        "전공에 대한 '희망'보다 '과학적 사고'와 '생명에 대한 책임감'의 균형을 중점적으로 검증합니다.",
    ),
    "engineering_it": (
        "설계 과정에서 비용, 시간, 성능 중 무엇을 포기하거나 우선했는지 트레이드오프를 본인의 논리로 설명해야 합니다.",
        "사용한 알고리즘이나 기술의 한계점을 명확히 인지하고 있는지, 그리고 이를 보완하기 위한 기술적 시도를 묻습니다.",
        "단순히 '만들었다'는 결과보다 '왜 이 기술/방식이 최선이었는가'에 대한 비판적 의사결정 과정을 검증합니다.",
    ),
    "business_economics": (
        "이윤 추구와 ESG, 기업의 사회적 책임이 충돌할 때 본인만의 구체적인 판단 기준과 근거를 확인합니다.",
        "통계 자료나 시장 분석을 인용했다면 표본의 편향성, 인과관계 해석의 한계를 수학적/논리적으로 방어해야 합니다.",
        "정책이나 경영 전략이 소외시킬 수 있는 계층과 이해관계자를 고려했는지 다각도로 묻습니다.",
    ),
    "humanities_social": (
        "텍스트나 사회 현상을 다각도(비판적, 대안적)로 해석할 수 있는 역량과 논증의 일관성을 확인합니다.",
        "사회 문제 해결책을 제시했다면 해당 대안이 초래할 수 있는 또 다른 사회적 비용이나 갈등 요소를 검증합니다.",
        "보편적 가치와 특수한 사례 사이의 간극을 어떻게 메웠는지, 본인의 가치관이 형성된 과정을 묻습니다.",
    ),
    "education": (
        "학습자 다양성 존중과 평가의 형평성 사이의 충돌을 교육철학적 관점에서 어떻게 풀어낼지 묻습니다.",
        "멘토링 등 활동 기록에서 관찰-가설-적용-피드백의 순환 구조가 실질적으로 작동했는지 구체적 근거를 확인합니다.",
        "지식 전달자로서의 역량보다 학습자의 성장을 이끌어내기 위한 '개입의 적절성'을 중점적으로 검증합니다.",
    ),
    "natural_science": (
        "가설이 기각되었거나 오차가 발생했을 때, 이를 숨기지 않고 과학적으로 분석하여 후속 탐구로 연결했는지 봅니다.",
        "수학적 모델링이나 물리적 법칙을 적용했다면 해당 이론의 전제 조건과 실제 환경의 차이를 어떻게 극복했는지 묻습니다.",
        "현상의 원인을 파악하기 위한 본인만의 집요한 탐구 과정과 증명 방식을 논리적으로 검증합니다.",
    ),
    "environment_energy": (
        "환경적 지속가능성과 경제적 현실 사이의 괴리를 어떤 우선순위 지표로 해결하려 했는지 묻습니다.",
        "에너지 기술이나 환경 정책 탐구 시, 장기적인 생태적 영향과 지역사회 수용성 문제를 함께 고려했는지 확인합니다.",
        "데이터 기반의 정량적 분석과 인류 보편의 가치 사이의 균형 감각을 중점적으로 평가합니다.",
    ),
    "architecture_design": (
        "디자인의 심미성보다 구조적 안전성, 사용자 편의성, 환경적 제약 조건 내에서의 최적안 도출 과정을 묻습니다.",
        "공간이나 제품 설계 시 소외된 사용자층에 대한 고려나 재료의 물성, 시공성 등 실질적 제약 조건을 어떻게 반영했는지 확인합니다.",
        "아이디어가 실제 결과물로 구현될 때 발생하는 괴리와 이를 극복하기 위한 공학적/예술적 대안을 검증합니다.",
    ),
}

_GENERIC_GUIDANCE: tuple[str, ...] = (
    "활동의 화려함보다 '왜(Why)'와 '어떻게(How)'에 집중하여 본인의 독창적인 판단 과정을 확인합니다.",
    "성공한 결과보다는 실패와 한계를 인식하고 이를 극복하거나 후속 탐구로 연결한 '성장 동력'을 묻습니다.",
)


def _template(
    category: str,
    strategy: str,
    question: str,
    intent: str,
    answer_frame: str,
    good_direction: str,
    avoid: str,
) -> MajorInterviewQuestionTemplate:
    return MajorInterviewQuestionTemplate(
        category=category,
        strategy=strategy,
        question=question,
        intent=intent,
        answer_frame=answer_frame,
        good_direction=good_direction,
        avoid=avoid,
    )


_GENERIC_QUESTION_BANK: tuple[MajorInterviewQuestionTemplate, ...] = (
    _template(
        "탐구 과정 검증",
        "프로세스 디테일",
        "이 활동에서 본인이 직접 내린 핵심 의사결정 하나와 당시 배제한 대안은 무엇이었나요?",
        "활동 참여 여부가 아니라 학생 본인의 판단 과정을 확인합니다.",
        "[동기] 문제 상황 - [과정] 선택지 간 비교 - [결과] 선택 근거와 결과 - [느낀점] 한계 인식과 배운 점 순서로 답변합니다.",
        "결과를 자랑하기보다 판단 기준과 한계 인식을 먼저 제시합니다.",
        "팀이 했다, 열심히 했다처럼 본인 판단이 드러나지 않는 답변",
    ),
    _template(
        "전공 적합성",
        "전공 심화",
        "{major} 지원자로서 이 활동의 핵심 원리를 한 문장으로 정의하고, 그 원리가 결과 해석에 어떻게 영향을 줬나요?",
        "활동과 전공을 이름만 연결한 것인지, 원리 수준으로 이해했는지 검증합니다.",
        "[동기] 원리에 대한 관심 - [과정] 원리의 활동 적용 - [결과] 해석의 변화 - [느낀점] 전공적 통찰 순서로 답변합니다.",
        "고교 수준 개념으로 명료하게 설명하고 과장된 전문용어는 줄입니다.",
        "전공과 관련 있다고만 말하고 원리나 해석을 설명하지 않는 답변",
    ),
    _template(
        "전공 적합성",
        "So-What",
        "이 탐구가 끝난 뒤 {major}를 바라보는 관점이나 사회적 책임 인식은 어떻게 달라졌나요?",
        "일회성 활동이 아니라 전공관의 변화와 성숙으로 이어졌는지 확인합니다.",
        "[동기] 초기 관점 - [과정] 활동 중 발생한 인식의 충돌 - [결과] 변화된 기준 - [느낀점] 향후 전공자로서의 다짐 순서로 답변합니다.",
        "느낀 점을 추상적으로 말하지 말고 판단 기준의 변화로 설명합니다.",
        "도움이 됐다, 관심이 커졌다 같은 감상 중심 답변",
    ),
    _template(
        "약점 방어",
        "약점 보완",
        "기록에서 깊이나 연속성이 부족하다는 지적을 받으면 어떤 원문 근거와 후속 계획으로 방어하겠습니까?",
        "약점을 숨기지 않고 확인 가능한 근거와 다음 행동으로 전환하는지 봅니다.",
        "[동기] 부족함 인정 - [과정] 보완을 위한 추가 노력 - [결과] 현재 도달한 수준 - [느낀점] 입학 후 심화 계획 순서로 답변합니다.",
        "방어보다 보완 계획과 근거의 신뢰도를 중심에 둡니다.",
        "약점이 없다고 부정하거나 학생부에 없는 성과를 덧붙이는 답변",
    ),
)

_MAJOR_QUESTION_BANK: dict[str, tuple[MajorInterviewQuestionTemplate, ...]] = {
    "bio_medical": (
        _template(
            "전공 적합성",
            "전공 철학",
            "환자의 자기결정권과 전문가의 의학적 판단이 충돌할 때, 본인이 세울 우선순위 기준은 무엇인가요?",
            "의학·보건 계열 지원자의 윤리적 판단 기준과 책임감을 확인합니다.",
            "[동기] 윤리적 딜레마 인식 - [과정] 가치 간 충돌 분석 - [결과] 본인의 판단 원칙 - [느낀점] 전문가의 사회적 책무 순서로 답변합니다.",
            "정답을 단정하기보다 근거 기반 의사결정 절차를 제시합니다.",
            "생명을 살리는 것이 무조건 우선이라는 식의 단선적 답변",
        ),
        _template(
            "탐구 과정 검증",
            "Logic Trap",
            "학생부에 기록된 생명과학 개념의 작동 원리를 고교 수준으로 설명하고, 실험 오차 원인을 생물학적 변이성과 연결해 말해 보세요.",
            "심화 개념을 실제로 이해했는지, 용어만 사용한 것은 아닌지와 생물학적 변이성까지 검증합니다.",
            "[동기] 개념 탐구 계기 - [과정] 원리 분석 및 변이성 통제 - [결과] 오차 원인과 한계 - [느낀점] 과학적 엄밀성의 중요성 순서로 답변합니다.",
            "모르는 전문 영역은 인정하고 고교 수준에서 확실한 원리와 오차 해석을 정확히 설명합니다.",
            "전문용어를 나열하지만 원리, 변이성, 오차 원인을 설명하지 못하는 답변",
        ),
    ),
    "engineering_it": (
        _template(
            "탐구 과정 검증",
            "Logic Trap",
            "사용한 알고리즘, 센서, 모델, 장치의 입력-처리-출력 구조와 오류 원인을 설명해 보세요.",
            "공학·IT 활동의 구현 원리와 오류 분석 역량을 확인합니다.",
            "[동기] 구현 목표 - [과정] 설계 및 디버깅 과정 - [결과] 성능 지표와 오류 원인 - [느낀점] 기술적 한계 극복 경험 순서로 답변합니다.",
            "성공 결과보다 실패 조건과 개선 기준을 함께 설명합니다.",
            "작동했다는 결과만 말하고 원리나 오류 원인을 생략하는 답변",
        ),
        _template(
            "전공 적합성",
            "전공 철학",
            "설계 과정에서 비용, 시간, 성능 중 하나를 포기해야 했다면 무엇을 포기했고, 그 판단 기준은 무엇이었나요?",
            "기술적 효율성과 책임 있는 설계 태도를 함께 평가합니다.",
            "[동기] 설계 제약 조건 - [과정] 트레이드오프 분석 - [결과] 최종 의사결정 근거 - [느낀점] 공학자의 윤리적 태도 순서로 답변합니다.",
            "정량 지표와 사용자·사회적 영향을 함께 고려합니다.",
            "성능이 가장 중요하다는 식으로 비용과 시간 제약을 무시하는 답변",
        ),
    ),
    "business_economics": (
        _template(
            "전공 적합성",
            "전공 철학",
            "본인이 제안한 정책이나 경영 전략이 소외시킬 수 있는 계층은 누구이며, 그 부작용을 줄이기 위한 기준은 무엇인가요?",
            "경영·경제 계열 지원자의 이해관계자 관점과 소외 계층 고려 여부를 확인합니다.",
            "[동기] 이해관계자 갈등 인식 - [과정] 소외 가능 계층과 사회적 비용 분석 - [결과] 상생을 위한 대안 - [느낀점] 지속가능한 경영의 본질 순서로 답변합니다.",
            "기업 관점과 사회적 비용을 함께 고려한 기준을 제시합니다.",
            "착한 경영이 중요하다는 선언만 하고 소외될 계층을 특정하지 못하는 답변",
        ),
        _template(
            "탐구 과정 검증",
            "프로세스 디테일",
            "자료 분석에서 사용한 표본, 지표, 비교 기준이 결론을 왜곡할 가능성을 어떻게 줄였나요?",
            "통계·시장 분석 기록의 신뢰도와 인과 해석 능력을 확인합니다.",
            "[동기] 분석의 필요성 - [과정] 데이터 수집 및 전처리 - [결과] 분석 결과와 신뢰도 검증 - [느낀점] 통계적 사고의 유의점 순서로 답변합니다.",
            "상관관계와 인과관계를 분리해 설명합니다.",
            "그래프나 수치가 있으니 객관적이라는 식의 답변",
        ),
    ),
    "humanities_social": (
        _template(
            "탐구 과정 검증",
            "비판적 시각",
            "같은 자료를 반대 관점에서 읽으면 어떤 해석이 가능하며, 본인의 결론은 왜 더 설득력 있나요?",
            "인문·사회 계열의 비판적 독해와 논증 균형감을 확인합니다.",
            "[동기] 자료 선택 계기 - [과정] 다각도 분석 및 비교 - [결과] 본인 논증의 근거 - [느낀점] 비판적 사고의 확장성 순서로 답변합니다.",
            "상대 관점을 먼저 공정하게 설명한 뒤 자신의 근거를 제시합니다.",
            "반대 의견을 단순히 틀렸다고 처리하는 답변",
        ),
        _template(
            "전공 적합성",
            "사회적 가치",
            "본인이 다룬 사회 문제에서 개인 경험, 사례, 통계 중 어느 근거가 가장 취약했고 어떻게 보완해야 하나요?",
            "사회 문제 탐구가 주장 중심에 그치지 않고 근거 비판으로 이어졌는지 봅니다.",
            "[동기] 사회 문제 포착 - [과정] 근거 수집 및 비판 - [결과] 보완된 결론 - [느낀점] 사회 과학적 탐구의 한계 인정 순서로 답변합니다.",
            "근거의 한계를 인정하면서 더 정교한 후속 탐구를 제시합니다.",
            "사회적으로 중요하다는 주장만 반복하는 답변",
        ),
    ),
    "education": (
        _template(
            "전공 적합성",
            "전공 철학",
            "학습자의 다양성과 평가의 공정성이 충돌할 때, 교사는 어떤 기준으로 개입해야 한다고 보나요?",
            "교육 계열 지원자의 교육철학과 공정성 판단을 확인합니다.",
            "[동기] 교실 내 갈등 상황 - [과정] 교육적 대안 탐색 - [결과] 본인의 교육적 개입 원칙 - [느낀점] 예비 교사로서의 가치관 순서로 답변합니다.",
            "학생 개별성 존중과 평가 기준의 일관성을 함께 설명합니다.",
            "학생을 잘 도와야 한다는 추상적 답변",
        ),
        _template(
            "탐구 과정 검증",
            "프로세스 디테일",
            "멘토링이나 교육 활동에서 학습자의 변화를 어떤 관찰 근거로 확인했고, 수업 방식을 어떻게 바꿨나요?",
            "교육 활동의 진정성과 피드백 기반 개선을 확인합니다.",
            "[동기] 학습자 분석 - [과정] 교수 학습 전략 적용 - [결과] 피드백을 통한 개선 - [느낀점] 교육 현장의 역동성 체득 순서로 답변합니다.",
            "도움을 줬다는 결과보다 관찰과 조정 과정을 구체화합니다.",
            "보람 있었다는 감상만 말하는 답변",
        ),
    ),
    "natural_science": (
        _template(
            "탐구 과정 검증",
            "프로세스 디테일",
            "가설이 예상과 다르게 나왔을 때 새로 세운 가설과 검증 방법은 무엇이었나요?",
            "과학 탐구가 결과 확인이 아니라 가설 수정으로 이어졌는지 확인합니다.",
            "[동기] 초기 가설 설정 - [과정] 실험 및 데이터 분석 - [결과] 예상 밖의 결과와 재가설 - [느낀점] 과학적 탐구의 본질 이해 순서로 답변합니다.",
            "실패를 숨기지 말고 탐구 설계의 변화로 설명합니다.",
            "실패 원인을 외부 조건 탓으로만 돌리는 답변",
        ),
        _template(
            "탐구 과정 검증",
            "Logic Trap",
            "변인 통제, 반복 측정, 오차 처리를 위해 본인이 직접 세운 기준은 무엇이었나요?",
            "자연과학 탐구의 방법론적 엄밀성을 확인합니다.",
            "[동기] 실험 설계 목적 - [과정] 변인 통제 및 측정 기준 - [결과] 데이터의 신뢰도 확보 - [느낀점] 실험 과학의 정밀성 학습 순서로 답변합니다.",
            "수치가 없다면 어떤 자료가 추가로 필요했는지까지 말합니다.",
            "실험을 했다는 사실만 말하고 신뢰도 기준을 설명하지 않는 답변",
        ),
    ),
    "environment_energy": (
        _template(
            "전공 적합성",
            "사회적 가치",
            "효율, 비용, 지속가능성, 지역사회 수용성이 충돌할 때 어떤 지표를 우선해 판단하겠습니까?",
            "환경·에너지 문제를 다기준 의사결정으로 바라보는지 확인합니다.",
            "[동기] 자원 배분 갈등 - [과정] 정량/정성 지표 비교 - [결과] 최적 의사결정 근거 - [느낀점] 환경 문제의 복합성 인식 순서로 답변합니다.",
            "정량 지표와 사회적 수용성을 함께 고려합니다.",
            "친환경이므로 무조건 좋다는 답변",
        ),
        _template(
            "탐구 과정 검증",
            "프로세스 디테일",
            "환경 개선 효과를 주장하려면 어떤 기준선과 비교군을 설정해야 하나요?",
            "환경 탐구의 효과 검증과 과장 방지 능력을 확인합니다.",
            "[동기] 환경 변화 포착 - [과정] 대조군 및 지표 설정 - [결과] 개선 효과의 정량적 검증 - [느낀점] 데이터 기반 환경 감수성 순서로 답변합니다.",
            "효과를 크게 보이게 하는 조건을 스스로 경계합니다.",
            "사례 하나만으로 일반화하는 답변",
        ),
    ),
    "architecture_design": (
        _template(
            "전공 적합성",
            "전공 심화",
            "이 활동을 조형 아이디어가 아니라 구조, 사용자, 환경, 안전 기준으로 다시 설명하면 핵심 쟁점은 무엇인가요?",
            "건축·디자인 활동을 미감보다 문제 해결 기준으로 설명할 수 있는지 봅니다.",
            "[동기] 공간/디자인의 문제의식 - [과정] 실질적 제약 조건 분석 - [결과] 기능적 해결안 도출 - [느낀점] 사용자 중심의 공학적 설계 순서로 답변합니다.",
            "공간의 아름다움보다 검증 가능한 조건을 먼저 제시합니다.",
            "멋있어서, 창의적이어서처럼 감상 중심으로 설명하는 답변",
        ),
        _template(
            "탐구 과정 검증",
            "Logic Trap",
            "모델링이나 제작 과정에서 재료, 하중, 동선, 환기 중 하나를 실제로 어떤 기준으로 검토했나요?",
            "건축·디자인 산출물이 실제 조건 검토까지 이어졌는지 확인합니다.",
            "[동기] 구현 가능성 검토 - [과정] 물리적/공간적 수치 계산 - [결과] 재료 및 동선 선택 - [느낀점] 실제 환경과의 상호작용 학습 순서로 답변합니다.",
            "확인한 기준과 확인하지 못한 기준을 분리해 말합니다.",
            "완성도 높은 결과물만 강조하고 검증 기준을 말하지 않는 답변",
        ),
    ),
}


def _compact_text(value: object) -> str:
    return " ".join(str(value or "").split()).strip()


def infer_major_track_from_texts(*texts: object) -> str | None:
    haystack = " ".join(_compact_text(text).lower() for text in texts if _compact_text(text))
    if not haystack:
        return None

    scores: dict[str, int] = {}
    for track, keywords in _MAJOR_TRACK_KEYWORDS.items():
        score = 0
        for keyword in keywords:
            normalized = keyword.lower()
            if normalized and normalized in haystack:
                score += 1 + min(len(normalized), 6) // 3
        if score:
            scores[track] = score
    if not scores:
        return None
    return max(scores.items(), key=lambda item: item[1])[0]


def track_label(track: str | None) -> str:
    return _TRACK_LABELS.get(str(track or ""), "지원 전공")


def render_question_template(
    template: MajorInterviewQuestionTemplate,
    *,
    major_label: str,
) -> MajorInterviewQuestionTemplate:
    def render(value: str) -> str:
        return value.format(major=major_label or "지원 전공")

    return replace(
        template,
        question=render(template.question),
        answer_frame=render(template.answer_frame),
        good_direction=render(template.good_direction),
        avoid=render(template.avoid),
    )


def major_question_templates_for_context(
    *,
    target_context: object = "",
    evidence_texts: Iterable[object] | None = None,
    limit: int = 4,
) -> list[MajorInterviewQuestionTemplate]:
    evidence_values = list(evidence_texts or [])
    track = infer_major_track_from_texts(target_context, *evidence_values)
    templates = list(_MAJOR_QUESTION_BANK.get(str(track or ""), ()))
    templates.extend(_GENERIC_QUESTION_BANK)
    return templates[: max(0, limit)]


def major_strategy_prompt_block(
    *,
    target_context: object = "",
    evidence_texts: Iterable[object] | None = None,
    limit: int = 4,
) -> str:
    evidence_values = list(evidence_texts or [])
    track = infer_major_track_from_texts(target_context, *evidence_values)
    label = track_label(track)
    guidance = _TRACK_GUIDANCE.get(str(track or ""), _GENERIC_GUIDANCE)
    templates = [
        render_question_template(template, major_label=label)
        for template in major_question_templates_for_context(
            target_context=target_context,
            evidence_texts=evidence_values,
            limit=limit,
        )
    ]
    lines = [f"추정 전공군: {label}", "전공별 압박 포인트:"]
    lines.extend(f"- {item}" for item in guidance)
    lines.append("전공별 Killer Question 예시:")
    lines.extend(f"- [{item.strategy}] {item.question}" for item in templates)
    return "\n".join(lines)
