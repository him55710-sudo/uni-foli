import type {
  GuidedChoiceGroup,
  GuidedChoiceOption,
  GuidedConversationPhase,
  GuidedPageRangeOption,
  GuidedStructureOption,
} from './guidedChat';

const KNOWN_PHASES: ReadonlySet<GuidedConversationPhase> = new Set([
  'subject_input',
  'specific_topic_check',
  'topic_recommendation',
  'topic_selection',
  'page_range_selection',
  'structure_selection',
  'drafting_next_step',
  'freeform_coauthoring',
]);

const KR_MATH = '\uc218\ud559';
const KR_MATH2 = '\uc2182';
const KR_CHEMISTRY = '\ud654\ud559';
const KR_BIOLOGY = '\uc0dd\uba85\uacfc\ud559';
const KR_SPECIFIC_TOPIC_TITLE = '\ud2b9\ubcc4\ud788 \uc0dd\uac01\ud574\ub454 \uc8fc\uc81c\uac00 \uc788\ub098\uc694?';
const KR_HAS_TOPIC = '\uc8fc\uc81c\uac00 \uc788\uc5b4\uc694';
const KR_RECOMMEND_THREE = '\ucd94\ucc9c 3\uac1c \ubc1b\uc544\ubcf4\uae30';
const KR_SUBJECT_QUICK_TITLE = '\uc790\uc8fc \uc120\ud0dd\ud558\ub294 \uacfc\ubaa9';

const BROAD_SUBJECT_KEYWORDS = [
  KR_MATH,
  '\uc2181',
  KR_MATH2,
  '\ubbf8\uc801\ubd84',
  '\ud1b5\uacc4',
  '\ubb3c\ub9ac',
  KR_CHEMISTRY,
  '\uc0dd\uba85',
  KR_BIOLOGY,
  '\uc9c0\uad6c\uacfc\ud559',
  'math',
  'physics',
  'chemistry',
  'biology',
];

export const DEFAULT_SUBJECT_CHIPS: GuidedChoiceOption[] = [
  { id: 'subject-math', label: KR_MATH, value: KR_MATH },
  { id: 'subject-math2', label: KR_MATH2, value: KR_MATH2 },
  { id: 'subject-chemistry', label: KR_CHEMISTRY, value: KR_CHEMISTRY },
  { id: 'subject-biology', label: KR_BIOLOGY, value: KR_BIOLOGY },
];

export function inferGuidedPhase(stateSummary: Record<string, unknown> | null | undefined): GuidedConversationPhase {
  const explicit = String(stateSummary?.phase || '').trim() as GuidedConversationPhase;
  if (explicit && KNOWN_PHASES.has(explicit)) {
    return explicit;
  }
  if (stateSummary?.selected_structure_id) return 'drafting_next_step';
  if (stateSummary?.selected_page_range_label) return 'structure_selection';
  if (stateSummary?.selected_topic_id) return 'page_range_selection';
  if (Array.isArray(stateSummary?.suggestions) && stateSummary.suggestions.length > 0) return 'topic_selection';
  const subject = String(stateSummary?.subject || '').trim();
  if (subject) return 'specific_topic_check';
  return 'subject_input';
}

export function isGuidedSetupComplete(phase: GuidedConversationPhase): boolean {
  return phase === 'drafting_next_step' || phase === 'freeform_coauthoring';
}

export function looksLikeBroadSubject(input: string): boolean {
  const normalized = input.trim().toLowerCase();
  if (!normalized) return false;
  if (normalized.length <= 4) return true;
  return BROAD_SUBJECT_KEYWORDS.some((keyword) => normalized.includes(keyword));
}

export function isRecommendationAffirmative(input: string): boolean {
  const text = input.trim().toLowerCase();
  if (!text) return false;
  return (
    text.includes('\ucd94\ucc9c') ||
    text.includes('\uc5c6') ||
    text.includes('\uc815\ud574\uc9c4 \uac8c') ||
    text.includes('\uc5c6\uc5b4\uc694') ||
    text.includes('\ucd94\ucc9c\ud574')
  );
}

export function isSpecificTopicAffirmative(input: string): boolean {
  const text = input.trim().toLowerCase();
  if (!text) return false;
  return (
    text.includes('\uc788\uc5b4') ||
    text.includes('\uc788\uc2b5\ub2c8\ub2e4') ||
    text.includes('\uc815\ud588') ||
    text.includes('already have') ||
    text.includes('\uc788\uc74c')
  );
}

export function resolvePageRangeLabel(input: string, options: GuidedPageRangeOption[]): string | null {
  const text = input.trim();
  if (!text) return null;
  const normalized = text.replace(/\s+/g, '');
  for (const option of options) {
    const compactLabel = option.label.replace(/\s+/g, '');
    const compactRange = `${option.min_pages}~${option.max_pages}`.replace(/\s+/g, '');
    if (normalized === compactLabel || normalized.includes(compactLabel) || normalized.includes(compactRange)) {
      return option.label;
    }
  }
  return null;
}

export function resolveStructureOptionId(input: string, options: GuidedStructureOption[]): string | null {
  const normalized = input.trim().toLowerCase();
  if (!normalized) return null;
  for (const option of options) {
    const label = option.label.toLowerCase();
    if (
      normalized === option.id.toLowerCase() ||
      normalized === label ||
      normalized.includes(label) ||
      label.includes(normalized)
    ) {
      return option.id;
    }
  }
  return null;
}

export function buildSpecificTopicCheckGroup(): GuidedChoiceGroup {
  return {
    id: 'specific-topic-check',
    title: KR_SPECIFIC_TOPIC_TITLE,
    style: 'buttons',
    options: [
      {
        id: 'specific-yes',
        label: KR_HAS_TOPIC,
        description: '\uc0dd\uac01\ud574\ub454 \uc8fc\uc81c\ub97c \uc9c1\uc811 \uc785\ub825\ud560\uac8c\uc694.',
        value: KR_HAS_TOPIC,
      },
      {
        id: 'specific-no-recommend',
        label: KR_RECOMMEND_THREE,
        description: '\ud559\uc0dd \uae30\ub85d\uc744 \ubc14\ud0d5\uc73c\ub85c \ucd94\ucc9c\ubc1b\uc744\uac8c\uc694.',
        value: KR_RECOMMEND_THREE,
      },
    ],
  };
}

export function buildSubjectQuickPickGroup(): GuidedChoiceGroup {
  return {
    id: 'subject-quick-picks',
    title: KR_SUBJECT_QUICK_TITLE,
    style: 'chips',
    options: DEFAULT_SUBJECT_CHIPS,
  };
}
