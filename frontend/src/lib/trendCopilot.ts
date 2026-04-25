export type TrendMajorKey = '건축' | '컴공' | '바이오' | '경영' | '사회과학' | '디자인' | '국어' | '수학' | '영어' | '과학탐구' | '사회탐구';
export type TrendLens = 'flow' | 'question' | 'activity';

export interface MajorTrendTopic {
  id: string;
  title: string;
  flow: string;
  question: string;
  activity: string;
}

const DEFAULT_MAJOR_CHIPS: TrendMajorKey[] = ['건축', '컴공', '바이오', '경영', '사회과학', '디자인', '국어', '수학', '영어', '과학탐구', '사회탐구'];

const MAJOR_KEYWORD_MAP: Array<{ key: TrendMajorKey; keywords: string[] }> = [
  { key: '건축', keywords: ['건축', '도시', '공간', '조경', '설계'] },
  { key: '컴공', keywords: ['컴공', '컴퓨터', '소프트웨어', 'sw', 'ai', '데이터', '인공지능'] },
  { key: '바이오', keywords: ['바이오', '생명', '의생명', '유전', '생명공학', '의학', '보건'] },
  { key: '경영', keywords: ['경영', '경제', '회계', '마케팅', 'esg', '창업', '금융'] },
  { key: '사회과학', keywords: ['사회과학', '사회', '정치', '행정', '심리', '교육', '법'] },
  { key: '디자인', keywords: ['디자인', '산업디자인', 'ux', 'ui', '시각', '브랜딩', '미디어'] },
  { key: '국어', keywords: ['국어', '문학', '화법', '작문', '언어', '매체', '독서'] },
  { key: '수학', keywords: ['수학', '미적분', '기하', '확률', '통계'] },
  { key: '영어', keywords: ['영어', '회화', '독해', '영작'] },
  { key: '과학탐구', keywords: ['물리', '화학', '생명과학', '지구과학', '과학', '통합과학'] },
  { key: '사회탐구', keywords: ['사회탐구', '역사', '지리', '윤리', '통합사회', '경제', '정치와 법', '생활과 윤리'] },
];

function normalizeLabel(value: string): string {
  return value.trim().replace(/\s+/g, ' ');
}

function pushUnique(values: string[], value: string, seen: Set<string>): void {
  const normalized = normalizeLabel(value);
  if (!normalized) return;
  const key = normalized.toLowerCase();
  if (seen.has(key)) return;
  seen.add(key);
  values.push(normalized);
}

export function resolveTrendMajorKey(label: string | null | undefined): TrendMajorKey {
  const normalized = (label || '').trim().toLowerCase();
  if (!normalized) return '컴공';
  const matched = MAJOR_KEYWORD_MAP.find(({ keywords }) =>
    keywords.some((keyword) => normalized.includes(keyword)),
  );
  return matched?.key ?? '컴공';
}

export function buildMajorChipLabels(params: {
  explicitMajor?: string | null;
  inferredMajors?: string[];
  limit?: number;
}): string[] {
  const { explicitMajor = null, inferredMajors = [], limit = 8 } = params;
  const labels: string[] = [];
  const seen = new Set<string>();

  if (explicitMajor) {
    pushUnique(labels, explicitMajor, seen);
  }

  for (const inferredMajor of inferredMajors) {
    pushUnique(labels, inferredMajor, seen);
    if (labels.length >= limit) return labels;
  }

  for (const fallbackMajor of DEFAULT_MAJOR_CHIPS) {
    pushUnique(labels, fallbackMajor, seen);
    if (labels.length >= limit) break;
  }

  return labels;
}

export function buildWorkshopPrompt(topic: MajorTrendTopic, majorLabel: string): string {
  return [
    `${majorLabel} 전공을 기준으로 아래 탐구주제를 학생부형 보고서로 구체화해줘.`,
    `주제: ${topic.title}`,
    `핵심 흐름: ${topic.flow}`,
    `탐구 질문: ${topic.question}`,
    `활동 연결: ${topic.activity}`,
    '요구사항: 1) 활동 근거 2) 세특 문장 포인트 3) 다음 실행 2주 계획',
  ].join('\n');
}

export const MAJOR_TREND_PLAYBOOK: Record<TrendMajorKey, MajorTrendTopic[]> = {
  건축: [
    {
      id: 'arch-climate-adaptive',
      title: '기후적응형 공공건축 설계',
      flow: '탄소중립 건축 규정과 지역 미기후 데이터를 함께 보는 흐름',
      question: '우리 지역 공공건축은 폭염·집중호우 대응 설계가 얼마나 반영되어 있는가?',
      activity: '학교 주변 공공시설 3곳을 체크리스트로 조사해 설계 개선안을 제안',
    },
    {
      id: 'arch-aging-city',
      title: '고령사회 보행친화 도시공간',
      flow: '유니버설 디자인 + 생활권 보행 데이터 결합',
      question: '고령층 이동권 관점에서 생활권 동선의 병목은 어디에서 발생하는가?',
      activity: '실측 동선 맵을 만들고 위험구간 개선 시나리오를 비교',
    },
    {
      id: 'arch-material-cycle',
      title: '순환건축과 재료 생애주기',
      flow: '건축재료 LCA와 폐기물 저감 설계가 연결되는 흐름',
      question: '학교 건축·인테리어 사례에서 순환재료 적용의 현실적 기준은 무엇인가?',
      activity: '재료별 장단점 매트릭스를 작성해 적용 우선순위를 도출',
    },
  ],
  컴공: [
    {
      id: 'cs-local-llm',
      title: '로컬 LLM 기반 학습도우미',
      flow: '개인정보 보호형 AI 활용이 학교 현장에서 확산되는 흐름',
      question: '클라우드 AI 대비 로컬 LLM의 장단점은 학습환경에서 어떻게 달라지는가?',
      activity: '요약/질문생성 태스크를 기준으로 품질·속도·프라이버시를 비교',
    },
    {
      id: 'cs-trustworthy-ai',
      title: '설명가능 AI와 신뢰성 평가',
      flow: '정확도 중심에서 신뢰성·설명가능성 중심으로 이동하는 흐름',
      question: '학생 대상 추천 시스템에서 설명가능성은 실제 수용도에 어떤 영향을 주는가?',
      activity: '간단한 추천 프로토타입을 만들고 사용자 피드백을 측정',
    },
    {
      id: 'cs-energy-efficient',
      title: '에너지 효율형 알고리즘 선택',
      flow: '그린 컴퓨팅 이슈로 연산 비용 최적화가 중요해지는 흐름',
      question: '같은 문제를 해결하는 알고리즘 중 에너지 효율이 높은 방식은 무엇인가?',
      activity: '복잡도/실행시간/전력 추정표를 만들어 선택 근거를 정리',
    },
  ],
  바이오: [
    {
      id: 'bio-singlecell',
      title: '단일세포 데이터 기반 질환 이해',
      flow: '정밀의료에서 단일세포 분석 활용이 늘어나는 흐름',
      question: '질환군별 세포군집 특성은 치료 전략에 어떤 힌트를 주는가?',
      activity: '공개 데이터 리포트를 읽고 핵심 바이오마커를 비교 정리',
    },
    {
      id: 'bio-microbiome',
      title: '마이크로바이옴과 생활습관',
      flow: '식습관·장내미생물·건강지표 연계 연구가 확장되는 흐름',
      question: '생활습관 변화는 장내미생물 다양성 지표에 어떤 가설을 만들 수 있는가?',
      activity: '문헌 3편을 근거로 변수·결과지표를 표준화해 탐구 설계',
    },
    {
      id: 'bio-bioethics-ai',
      title: '생명정보 AI와 생명윤리',
      flow: '바이오AI 확산에 따라 데이터 윤리 이슈가 동반되는 흐름',
      question: '유전체 데이터 활용에서 동의·익명화 기준은 어디까지 필요한가?',
      activity: '국내외 가이드라인을 비교하고 학교 발표용 권고안을 작성',
    },
  ],
  경영: [
    {
      id: 'biz-esg-sme',
      title: '중소기업 ESG 실행전략',
      flow: '대기업 중심 ESG에서 공급망 전반 실행으로 이동하는 흐름',
      question: '중소기업이 실행 가능한 ESG 지표는 무엇이며 우선순위는 어떻게 정할까?',
      activity: '가상 기업 케이스를 만들어 비용 대비 효과 시나리오를 설계',
    },
    {
      id: 'biz-ai-marketing',
      title: 'AI 기반 고객경험 설계',
      flow: '개인화 마케팅이 생성형 AI와 결합되는 흐름',
      question: '개인화 추천이 고객 충성도에 미치는 효과를 어떻게 검증할 수 있을까?',
      activity: '가설-지표-실험안 1페이지 플랜으로 정리',
    },
    {
      id: 'biz-platform-trust',
      title: '플랫폼 신뢰와 수익모델',
      flow: '플랫폼 경쟁에서 신뢰 설계가 핵심 성과요인으로 부상하는 흐름',
      question: '수익화 정책 변화가 사용자 신뢰와 잔존율에 어떤 영향을 줄까?',
      activity: '플랫폼 사례 2개를 비교해 정책 변화 타임라인을 작성',
    },
  ],
  사회과학: [
    {
      id: 'soc-digital-governance',
      title: '디지털 행정서비스 접근성',
      flow: '공공서비스의 디지털 전환과 접근성 격차 이슈가 커지는 흐름',
      question: '디지털 행정서비스는 어떤 집단에서 이용 장벽이 크게 나타나는가?',
      activity: '민원서비스 UX를 분석하고 개선 제안을 정책 메모로 정리',
    },
    {
      id: 'soc-local-population',
      title: '지역 인구구조 변화와 정책',
      flow: '저출생·고령화에 맞춘 생활권 정책 재설계 흐름',
      question: '인구구조 변화가 지역 생활 인프라 수요를 어떻게 바꾸는가?',
      activity: '통계청 공개지표 기반으로 지역별 수요 변화를 시각화',
    },
    {
      id: 'soc-media-polarization',
      title: '미디어 소비와 사회 양극화',
      flow: '알고리즘 미디어 환경에서 정보편향 연구가 확장되는 흐름',
      question: '미디어 소비 패턴 차이가 사회적 인식 격차를 확대하는가?',
      activity: '뉴스 소비 설문을 설계하고 결과를 간단히 코딩해 해석',
    },
  ],
  디자인: [
    {
      id: 'design-inclusive-ui',
      title: '포용적 UX/UI 디자인',
      flow: '접근성 기준 준수에서 포용적 경험 설계로 확장되는 흐름',
      question: '동일 서비스에서 사용자군별 인터랙션 장벽은 어떻게 다르게 나타나는가?',
      activity: '접근성 체크리스트 기반으로 화면 개선 전후를 비교',
    },
    {
      id: 'design-sustainable-brand',
      title: '지속가능 브랜드 아이덴티티',
      flow: '브랜드 표현에서 친환경 스토리텔링과 증거 제시가 중요해지는 흐름',
      question: '지속가능성을 브랜드 시각언어로 설득력 있게 전달하는 요소는 무엇인가?',
      activity: '브랜드 사례 2개를 분석해 리디자인 컨셉 보드를 제작',
    },
    {
      id: 'design-data-storytelling',
      title: '데이터 스토리텔링 시각화',
      flow: '정보디자인에서 데이터 기반 서사 구조가 강화되는 흐름',
      question: '동일 데이터라도 시각화 프레임에 따라 메시지 해석이 어떻게 달라지는가?',
      activity: '한 주제를 서로 다른 레이아웃으로 시각화해 전달력 비교',
    },
  ],
  국어: [
    {
      id: 'kor-media-literacy',
      title: '디지털 매체 리터러시와 가짜뉴스',
      flow: '매체 언어의 영향력과 비판적 수용이 중요해지는 흐름',
      question: '가짜뉴스의 언어적 특성은 어떻게 독자의 확증 편향을 강화하는가?',
      activity: '뉴스 기사 3건을 비교 분석하여 비판적 읽기 가이드라인 제작',
    },
    {
      id: 'kor-modern-lit',
      title: '현대문학과 사회적 소수자',
      flow: '문학 작품을 통한 공감과 타자 이해 능력이 강조되는 흐름',
      question: '현대소설 속 소수자 재현 방식은 시대별로 어떻게 변화했는가?',
      activity: '작품 간 비교를 통해 사회적 배경과 인물 묘사의 상관관계 분석',
    }
  ],
  수학: [
    {
      id: 'math-epidemic',
      title: '전염병 확산 모델과 미적분',
      flow: '수학적 모델링을 통한 실생활 문제 해결 역량이 중시되는 흐름',
      question: 'SIR 모델의 미분방정식은 확산 예측에 어떻게 기여하는가?',
      activity: '기본 SIR 모델 방정식을 세우고 변수에 따른 확산 그래프 시뮬레이션',
    },
    {
      id: 'math-data-stat',
      title: '빅데이터와 통계적 추론의 함정',
      flow: '데이터 기반 의사결정에서 통계적 오류 파악이 중요한 흐름',
      question: '심슨의 역설 등 통계적 착시는 실제 여론조사에서 어떻게 나타나는가?',
      activity: '모순되는 통계 기사 사례를 찾아 데이터 해석의 오류 지적',
    }
  ],
  영어: [
    {
      id: 'eng-global-issue',
      title: '글로벌 환경 이슈와 영문 에세이',
      flow: '글로벌 이슈에 대한 영어 표현력과 논리적 사고가 요구되는 흐름',
      question: '기후위기 대응 방안을 영어로 어떻게 논리적으로 설득할 것인가?',
      activity: '영문 기사 요약 후 자신의 견해를 담은 짧은 에세이 작성',
    },
    {
      id: 'eng-cultural-translation',
      title: '문화적 맥락과 번역의 차이',
      flow: '단순 해석을 넘어 문화적 맥락을 반영한 이해가 강조되는 흐름',
      question: '관용구나 문화적 비유는 어떻게 번역해야 원문의 의도를 살리는가?',
      activity: '영미권 영화/드라마 자막의 오역 사례를 찾아 올바른 맥락으로 재번역',
    }
  ],
  과학탐구: [
    {
      id: 'sci-renewable-energy',
      title: '신재생에너지 효율 비교',
      flow: '탄소중립을 위한 에너지 전환 기술이 주목받는 흐름',
      question: '우리 지역 환경에 가장 적합한 신재생에너지 효율 조건은 무엇인가?',
      activity: '지역 일조량/풍량 데이터를 기반으로 발전 효율 간이 비교',
    },
    {
      id: 'sci-genetic-tech',
      title: '크리스퍼 유전자가위와 생명윤리',
      flow: '첨단 생명과학 기술의 원리와 윤리적 쟁점이 동시 부각되는 흐름',
      question: '유전자 편집 기술의 한계와 상용화를 위한 조건은 무엇인가?',
      activity: '기술적 장단점 및 윤리적 찬반 의견을 담은 보고서 작성',
    }
  ],
  사회탐구: [
    {
      id: 'soc-welfare-policy',
      title: '복지 사각지대와 선별/보편적 복지',
      flow: '사회적 불평등 해소를 위한 복지 제도의 효과성 분석 흐름',
      question: '특정 지역의 복지 사각지대 발생 원인과 해결책은 무엇인가?',
      activity: '지자체 복지 예산 통계를 활용하여 정책 효과성 분석',
    },
    {
      id: 'soc-gig-economy',
      title: '플랫폼 노동과 긱 경제의 그림자',
      flow: '새로운 노동 형태 등장과 법적 보호망의 한계가 논의되는 흐름',
      question: '플랫폼 노동자의 법적 지위는 기존 노동법으로 보호 가능한가?',
      activity: '관련 법적 쟁점 요약 및 노동권 보장을 위한 개선안 제안',
    }
  ]
};
