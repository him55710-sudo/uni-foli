export interface FaqItem {
  id: string;
  category: string;
  question: string;
  answer: string;
}

export const faqItems: FaqItem[] = [
  {
    id: 'overview-1',
    category: '서비스 개요',
    question: 'Uni Folia는 어떤 서비스인가요?',
    answer:
      'Uni Folia는 학생의 생기부와 실제 활동 기록을 중심으로 AI 진단, 탐구 플랜, 작업실 drafting까지 이어지는 기록 중심 워크플로를 제공하는 도구입니다.',
  },
  {
    id: 'overview-2',
    category: '서비스 개요',
    question: '일반 챗봇과 무엇이 다른가요?',
    answer:
      '일반적인 챗봇처럼 막연한 문장을 만드는 데서 끝나지 않고, 기록을 먼저 확인한 뒤 부족한 근거는 보완 행동으로 연결하는 school-record-first 흐름을 지향합니다.',
  },
  {
    id: 'guest-1',
    category: '게스트 사용',
    question: '게스트로도 써볼 수 있나요?',
    answer:
      '환경 설정에 따라 게스트 체험이 열려 있는 경우 바로 워크플로를 확인할 수 있습니다. 다만 기록 저장과 연속 작업을 안정적으로 이어가려면 로그인 연결을 권장합니다.',
  },
  {
    id: 'guest-2',
    category: '어떻게 사용하는지',
    question: '로그인하면 어디부터 시작하나요?',
    answer:
      '기본 흐름은 목표 설정, 생기부 업로드, AI 진단, 작업실 순서입니다. 대시보드와 빈 상태 카드가 다음 행동을 먼저 안내하도록 설계되어 있습니다.',
  },
  {
    id: 'privacy-1',
    category: '기록과 개인정보',
    question: '업로드한 생기부와 개인정보는 어떻게 다루나요?',
    answer:
      '기록은 분석 전에 마스킹과 검토 단계를 거치며, 제품 워크플로에 필요한 범위 안에서만 처리합니다. 저장과 접근은 현재 서비스 설정과 백엔드 보안 규칙을 따릅니다.',
  },
  {
    id: 'privacy-2',
    category: '기록이 부족할 때',
    question: '기록이 부족해도 억지로 결과를 만들어주나요?',
    answer:
      '아닙니다. 기록이 충분하지 않으면 과장된 문장을 채우기보다, 어떤 활동과 근거를 더 쌓아야 하는지 다음 행동을 제안하는 방향을 우선합니다.',
  },
  {
    id: 'trust-1',
    category: '합격 보장 여부',
    question: '합격을 보장해주나요?',
    answer:
      '아닙니다. Uni Folia는 합격을 약속하는 서비스가 아니라 더 나은 준비를 돕는 도구입니다. 실제 기록을 바탕으로 판단과 실행을 돕는 데 초점을 둡니다.',
  },
  {
    id: 'trust-2',
    category: '결과물의 신뢰성',
    question: '하지 않은 활동을 만들어서 써주나요?',
    answer:
      '아닙니다. 허위 활동 생성이나 근거 없는 미화는 제품 원칙에 어긋납니다. 실제 기록과 확인 가능한 활동을 기준으로만 drafting을 돕습니다.',
  },
  {
    id: 'trust-3',
    category: '결과물의 신뢰성',
    question: '결과물은 얼마나 믿을 수 있나요?',
    answer:
      '작업실과 진단 화면은 가능한 한 출처, 근거, 상태 정보를 함께 보여주도록 설계되어 있습니다. 최종 제출 전에는 학생과 보호자, 교사가 직접 검토해야 합니다.',
  },
  {
    id: 'fit-1',
    category: '서비스 개요',
    question: '어떤 학생에게 특히 도움이 되나요?',
    answer:
      '기록을 바탕으로 탐구 흐름을 정리하고 싶거나, 다음 활동을 어떻게 설계해야 할지 막막한 학생에게 유용합니다. 이미 기록이 있는 학생뿐 아니라 방향을 잡는 초기 단계에도 맞습니다.',
  },
  {
    id: 'workflow-1',
    category: '어떻게 사용하는지',
    question: '탐구 플랜과 퀘스트는 무엇을 해주나요?',
    answer:
      '진단 이후에 바로 문장만 뽑아내는 대신, 어떤 주제를 더 파고들고 어떤 근거를 보완해야 하는지 실행 가능한 다음 행동으로 정리해 주는 구조입니다.',
  },
  {
    id: 'partnership-1',
    category: '학교/학원 협업문의',
    question: '학교나 학원 단위 협업도 가능한가요?',
    answer:
      '가능성을 열어두고 있습니다. 현재는 문의 허브에서 협업/도입 문의를 받고 있으며, 운영 방식과 적용 범위는 기관 상황에 맞춰 논의하는 단계입니다.',
  },
  {
    id: 'support-1',
    category: '문의와 지원',
    question: '문의는 어디로 하면 되나요?',
    answer:
      '공개 문의 허브에서 1:1 문의, 협업/도입 문의, 버그·기능 제안을 구분해 접수할 수 있습니다. 상황에 따라 이메일이나 연락처를 통해 답변을 드립니다.',
  },
  {
    id: 'pricing-1',
    category: '결제/도입 관련 준비중 항목',
    question: '결제나 기관 도입 체계는 준비되어 있나요?',
    answer:
      '공개된 결제 시스템과 정식 도입 패키지는 아직 준비 중입니다. 현재는 문의를 통해 사용 목적과 운영 조건을 먼저 확인하는 방식으로 안내하고 있습니다.',
  },
];

export const faqPreviewItems = faqItems.filter(item =>
  ['overview-1', 'overview-2', 'guest-1', 'privacy-2', 'trust-1', 'trust-3'].includes(item.id),
);
