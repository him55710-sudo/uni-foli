export type PreUploadQuickActionId =
  | 'major_decision'
  | 'record_preparation'
  | 'report_direction'
  | 'upload_record';

export interface PreUploadQuickAction {
  id: PreUploadQuickActionId;
  label: string;
  prompt: string;
}

export interface PreUploadGuideContext {
  input: string;
  targetMajor?: string | null;
  currentConcern?: string | null;
}

export interface PreUploadGuideReply {
  message: string;
  offTopicRedirected: boolean;
}

type PreUploadIntent =
  | 'major_decision'
  | 'record_preparation'
  | 'report_direction'
  | 'upload_record'
  | 'anxiety'
  | 'off_topic'
  | 'general';

export const PRE_UPLOAD_GUIDE_OPENING = [
  '업로드 전 상담 모드입니다. 전공, 학생부 준비, 탐구 방향부터 짧게 정리해드릴게요.',
  '아직 학생부 원문을 보지 않았기 때문에 지금은 일반 가이드만 제공하고, PDF 업로드 후 근거 기반 진단이 시작됩니다.',
].join('\n');

export const PRE_UPLOAD_GUIDE_QUICK_ACTIONS: PreUploadQuickAction[] = [
  {
    id: 'major_decision',
    label: '전공 정하기',
    prompt: '전공 정하기를 도와줘',
  },
  {
    id: 'record_preparation',
    label: '학생부 어떻게 준비할지',
    prompt: '학생부 어떻게 준비할지 알려줘',
  },
  {
    id: 'report_direction',
    label: '탐구보고서 방향',
    prompt: '탐구보고서 방향을 알려줘',
  },
  {
    id: 'upload_record',
    label: '학생부 업로드하기',
    prompt: '학생부 업로드를 시작할게',
  },
];

const EDUCATION_KEYWORDS = [
  '전공',
  '학과',
  '진로',
  '학교생활',
  '학교 생활',
  '학생부',
  '생기부',
  '입시',
  '대학',
  '동아리',
  '시간관리',
  '학습계획',
  '교과',
  '세특',
  '창체',
  '출결',
  '독서',
  '탐구',
  '보고서',
  '면접',
  '수시',
  '정시',
  '학업',
];

const OFF_TOPIC_KEYWORDS = [
  '주식',
  '코인',
  '날씨',
  '연애',
  '게임 공략',
  '영화 추천',
  '정치 뉴스',
  '축구',
  '야구',
  '다이어트',
  '쇼핑',
  '여행지',
];

const ANXIETY_KEYWORDS = [
  '불안',
  '걱정',
  '막막',
  '스트레스',
  '자신 없어',
  '자신없',
  '무서워',
  '떨려',
];

function normalize(value: string): string {
  return String(value || '')
    .toLowerCase()
    .replace(/\s+/g, ' ')
    .trim();
}

function includesAny(text: string, keywords: string[]): boolean {
  return keywords.some((keyword) => text.includes(keyword));
}

function resolveIntent(text: string): PreUploadIntent {
  const normalized = normalize(text);

  if (!normalized) return 'general';
  if (normalized.includes('업로드')) return 'upload_record';
  if (normalized.includes('탐구') || normalized.includes('보고서')) return 'report_direction';
  if (normalized.includes('학생부') || normalized.includes('생기부') || normalized.includes('세특') || normalized.includes('창체')) {
    return 'record_preparation';
  }
  if (normalized.includes('전공') || normalized.includes('학과') || normalized.includes('진로')) return 'major_decision';
  if (includesAny(normalized, ANXIETY_KEYWORDS)) return 'anxiety';

  if (includesAny(normalized, OFF_TOPIC_KEYWORDS) && !includesAny(normalized, EDUCATION_KEYWORDS)) return 'off_topic';
  if (!includesAny(normalized, EDUCATION_KEYWORDS)) return 'off_topic';

  return 'general';
}

function majorHint(targetMajor?: string | null): string {
  const major = (targetMajor || '').trim();
  if (!major) return '목표 전공이 아직 없으면 관심 전공 2~3개 후보부터 잡아보겠습니다.';
  return `현재 목표 전공은 ${major} 기준으로 안내합니다.`;
}

function concernHint(currentConcern?: string | null): string {
  const concern = (currentConcern || '').trim();
  if (!concern) return '현재 가장 큰 고민 1가지를 알려주시면 우선순위를 바로 정리해드릴게요.';
  return `지금 고민은 "${concern}"으로 이해하고 이어가겠습니다.`;
}

function appendEvidenceBoundaryLine(message: string): string {
  return `${message}\n\n참고: 업로드 전이라 실제 학생부 문장 분석은 하지 않으며, PDF 업로드 후 근거 기반 진단으로 전환됩니다.`;
}

export function buildPreUploadGuideReply(context: PreUploadGuideContext): PreUploadGuideReply {
  const intent = resolveIntent(context.input);
  const majorLine = majorHint(context.targetMajor);
  const concernLine = concernHint(context.currentConcern);

  if (intent === 'major_decision') {
    return {
      message: appendEvidenceBoundaryLine(
        [
          '전공 정하기는 3단계로 가겠습니다.',
          `1) ${majorLine}`,
          '2) 좋아하는 교과 2개와 버거운 교과 1개를 적기',
          '3) 최근 활동에서 몰입한 경험 2개를 전공 후보와 연결하기',
        ].join('\n'),
      ),
      offTopicRedirected: false,
    };
  }

  if (intent === 'record_preparation') {
    return {
      message: appendEvidenceBoundaryLine(
        [
          '학생부 준비는 기록의 양보다 연결성이 중요합니다.',
          '- 교과/세특: 수업 내용 -> 질문 -> 확장 활동 흐름 1개씩',
          '- 창체/독서: 전공과 연결되는 이유를 한 줄로 명확화',
          '- 행동특성: 협업/주도성 사례를 구체 사건 중심으로 정리',
        ].join('\n'),
      ),
      offTopicRedirected: false,
    };
  }

  if (intent === 'report_direction') {
    return {
      message: appendEvidenceBoundaryLine(
        [
          '탐구보고서는 전공 연결성과 실행 흔적 중심으로 잡겠습니다.',
          `- 시작점: ${majorLine}`,
          '- 질문 1개, 방법 1개(실험/자료분석/설문), 산출물 1개로 간단히 설계',
          '- 결과보다 과정 기록과 다음 확장 계획을 먼저 준비',
        ].join('\n'),
      ),
      offTopicRedirected: false,
    };
  }

  if (intent === 'upload_record') {
    return {
      message: [
        '좋습니다. 지금 PDF를 올리면 진단이 근거 기반 모드로 전환됩니다.',
        '업로드 후에는 실제 학생부 문장을 기준으로 강점/약점/전공적합성 안내를 드리겠습니다.',
      ].join('\n'),
      offTopicRedirected: false,
    };
  }

  if (intent === 'anxiety') {
    return {
      message: appendEvidenceBoundaryLine(
        [
          '불안을 느끼는 건 자연스러운 단계입니다. 지금은 한 번에 완성하지 않고 우선순위 1개부터 정리하면 됩니다.',
          `- ${concernLine}`,
          '- 원하면 2주 단위로 실행 가능한 준비 순서를 바로 제시해드릴게요.',
        ].join('\n'),
      ),
      offTopicRedirected: false,
    };
  }

  if (intent === 'off_topic') {
    return {
      message: [
        '이 모드에서는 진로, 입시, 학생부, 탐구 준비 중심으로 안내하고 있습니다.',
        '원하면 "전공 정하기" 또는 "학생부 어떻게 준비할지"부터 바로 도와드릴게요.',
        '학생부 PDF를 업로드하면 실제 기록 근거로 더 정확한 진단이 가능합니다.',
      ].join('\n'),
      offTopicRedirected: true,
    };
  }

  return {
    message: appendEvidenceBoundaryLine(
      [
        '좋아요. 업로드 전에는 방향 설정 중심으로 빠르게 도와드릴게요.',
        `- ${majorLine}`,
        `- ${concernLine}`,
        '- 아래 칩을 눌러 원하는 주제로 바로 진행해 주세요.',
      ].join('\n'),
    ),
    offTopicRedirected: false,
  };
}
