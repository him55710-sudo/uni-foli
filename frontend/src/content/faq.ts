export interface FaqItem {
  id: string;
  category: string;
  question: string;
  answer: string;
}

export const faqItems: FaqItem[] = [
  {
    id: 'service-1',
    category: '서비스 소개',
    question: '이 앱은 정확히 무엇을 도와주나요?',
    answer:
      '목표 학과 정리, 학생부 파일 확인, 진단 결과 점검, 문서 초안 작성까지 한 흐름으로 연결해 주는 앱입니다. 무엇을 먼저 해야 할지 순서가 정리되어 있어 준비가 훨씬 쉬워집니다.',
  },
  {
    id: 'service-2',
    category: '서비스 소개',
    question: '그냥 채팅으로 물어보는 것과 뭐가 다른가요?',
    answer:
      '막연한 답변보다 학생부 내용과 목표에 맞춰 필요한 점검 항목을 먼저 보여줍니다. 그래서 “어떻게 써야 하지?”보다 “지금 무엇을 고치면 되는지”를 바로 알 수 있습니다.',
  },
  {
    id: 'upload-1',
    category: '기록 업로드',
    question: '학생부는 어떤 파일로 올리면 되나요?',
    answer:
      'PDF 파일로 올리면 됩니다. 용량은 50MB 이하를 권장하며, 분석을 위해 페이지가 빠지지 않게 전체를 포함해 주세요.',
  },
  {
    id: 'upload-2',
    category: '기록 업로드',
    question: '업로드가 실패하면 어떻게 해야 하나요?',
    answer:
      '파일이 PDF인지, 용량이 큰지, 인터넷 연결이 안정적인지 먼저 확인해 주세요. 계속 실패하면 문의 허브에서 파일 상태를 함께 알려 주시면 빠르게 확인해 드립니다.',
  },
  {
    id: 'privacy-1',
    category: '개인정보',
    question: '이름이나 연락처 같은 개인정보는 안전한가요?',
    answer:
      '분석 전에 개인정보를 숨기는 처리를 먼저 진행합니다. 처리 상태와 결과를 화면에서 직접 확인할 수 있어요.',
  },
  {
    id: 'goal-1',
    category: '목표 설정',
    question: '목표 학과를 아직 못 정했는데 사용해도 되나요?',
    answer:
      '가능합니다. 다만 목표를 정할수록 진단 기준과 작성 방향이 더 정확해집니다. 처음에는 후보를 2~3개로 좁혀서 시작해 보세요.',
  },
  {
    id: 'diagnosis-1',
    category: '진단',
    question: '진단 결과는 어디까지 믿어도 되나요?',
    answer:
      '진단은 준비를 도와주는 참고 도구입니다. 최종 문서는 반드시 본인이 직접 읽고 고쳐야 하며, 학교/담임 선생님과 함께 점검하면 더 안전합니다.',
  },
  {
    id: 'writing-1',
    category: '문서 작성',
    question: '문장을 자동으로 다 써주나요?',
    answer:
      '초안 작성을 도와주지만, 그대로 제출하는 용도가 아닙니다. 내 활동 사실과 맞는지 확인하고 내 말투로 다듬어 완성하는 방식이 가장 좋습니다.',
  },
  {
    id: 'account-1',
    category: '계정',
    question: '로그인이 안 될 때는 어떻게 하나요?',
    answer:
      '브라우저 팝업 차단을 해제하고 다시 시도해 주세요. 그래도 안 되면 문의 허브에 화면 캡처와 함께 접속 주소를 알려 주시면 빠르게 확인해 드립니다.',
  },
  {
    id: 'plan-1',
    category: '요금제',
    question: '플러스/프로는 어떤 학생에게 맞나요?',
    answer:
      '기본 기능만 써도 준비는 가능합니다. 더 자주 진단하고 작성 기록을 꾸준히 관리하고 싶다면 플러스/프로가 도움이 됩니다.',
  },
  {
    id: 'contact-1',
    category: '문의',
    question: '원하는 답을 못 찾았어요. 어디로 문의하나요?',
    answer:
      '문의 허브에서 1:1 문의를 남겨 주세요. 어떤 화면에서 막혔는지, 어떤 버튼을 눌렀는지 적어 주시면 더 빠르게 도와드릴 수 있습니다.',
  },
  {
    id: 'school-1',
    category: '기관 문의',
    question: '학교나 학원 단위로도 도입할 수 있나요?',
    answer:
      '가능합니다. 기관 문의 탭에서 학교/학원 정보와 원하는 운영 방식(인원, 기간, 목적)을 남겨 주시면 맞춤 안내를 드립니다.',
  },
];

export const faqPreviewItems = faqItems.filter(item =>
  ['service-1', 'service-2', 'upload-2', 'privacy-1', 'diagnosis-1', 'contact-1'].includes(item.id),
);

