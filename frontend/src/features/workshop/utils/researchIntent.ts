import type { UniFoliReportSectionId } from '../types/reportDocument';

const RESEARCH_KEYWORDS = [
  '자료',
  '논문',
  '웹',
  '웹리서치',
  '인터넷',
  '출처',
  '근거',
  '조사',
  '찾아줘',
  '찾아 줘',
  '참고문헌',
  '선행연구',
  '보고서',
  '통계',
  '최신',
  '최근',
  '뉴스',
  '기사',
  '공식',
  '정책',
  'research',
  'paper',
  'web',
  'source',
  'evidence',
  'statistics',
  'data',
];

const REQUEST_VERB_PATTERN = /찾아|찾아줘|해줘|해 줘|보완|연결|근거|출처|조사|추천|검색|알려|리서치|research|search|find|cite|source/i;

export interface ResearchQueryContext {
  selectedTopic?: string | null;
  selectedOutline?: string | null;
  targetMajor?: string | null;
  currentSectionId?: UniFoliReportSectionId | null;
}

export function isResearchRequestMessage(text: string): boolean {
  const normalized = text.toLowerCase();
  const hasResearchKeyword = RESEARCH_KEYWORDS.some((keyword) => normalized.includes(keyword.toLowerCase()));
  const hasRequestVerb = REQUEST_VERB_PATTERN.test(text);
  return hasResearchKeyword && hasRequestVerb;
}

export function buildResearchQueryFromMessage(text: string, context: ResearchQueryContext = {}): string {
  const parts = [
    stripCommandWords(text),
    context.selectedTopic || '',
    context.targetMajor ? `${context.targetMajor} 관련` : '',
  ].filter(Boolean);
  return uniqueWords(parts.join(' ')).slice(0, 180);
}

export function inferTargetSectionFromResearchMessage(text: string): UniFoliReportSectionId | null {
  if (/이론|배경|개념|원리/.test(text)) return 'background_theory';
  if (/선행|논문|기존 연구|학술/.test(text)) return 'prior_research';
  if (/방법|실험|측정|설문|절차/.test(text)) return 'research_method';
  if (/분석|데이터|통계|계산/.test(text)) return 'data_analysis';
  if (/결과|효과|영향/.test(text)) return 'result';
  if (/결론|제언|한계|후속/.test(text)) return 'conclusion';
  if (/진로|학과|전공|건축|생기부|세특/.test(text)) return 'student_record_connection';
  return null;
}

function stripCommandWords(text: string): string {
  return text
    .replace(/찾아\s*줘|찾아줘|조사해\s*줘|추천해\s*줘|보완해\s*줘|검색해\s*줘/g, '')
    .replace(/자료|논문|웹리서치|웹|인터넷|출처|근거|참고문헌|선행연구/g, '')
    .trim();
}

function uniqueWords(text: string): string {
  const seen = new Set<string>();
  return text
    .split(/\s+/)
    .filter((word) => {
      if (!word) return false;
      const key = word.toLowerCase();
      if (seen.has(key)) return false;
      seen.add(key);
      return true;
    })
    .join(' ');
}
