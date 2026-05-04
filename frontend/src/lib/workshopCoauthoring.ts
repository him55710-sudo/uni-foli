export type WorkshopMode = 'planning' | 'outline' | 'section_drafting' | 'revision';

export type WorkshopDraftBlockId =
  | 'title'
  | 'introduction_background'
  | 'body_section_1'
  | 'body_section_2'
  | 'body_section_3'
  | 'conclusion_reflection_next_step';

export type WorkshopDraftAttribution =
  | 'student-authored'
  | 'ai-suggested'
  | 'ai-inserted-after-approval';

export interface WorkshopDraftBlock {
  block_id: WorkshopDraftBlockId;
  heading: string;
  content_markdown: string;
  attribution: WorkshopDraftAttribution;
  updated_at?: string | null;
}

export interface WorkshopStructuredDraftState {
  mode: WorkshopMode;
  blocks: WorkshopDraftBlock[];
  last_synced_turn_id?: string | null;
  source?: 'structured' | 'derived';
}

export interface WorkshopDraftPatchProposal {
  mode: WorkshopMode;
  block_id: WorkshopDraftBlockId;
  heading?: string | null;
  content_markdown: string;
  rationale?: string | null;
  evidence_boundary_note?: string | null;
  requires_approval: boolean;
}

export const WORKSHOP_MODE_OPTIONS: Array<{ id: WorkshopMode; label: string; description: string }> = [
  { id: 'planning', label: 'Planning', description: '목표·근거·전략을 합의합니다.' },
  { id: 'outline', label: 'Outline', description: '섹션 구조를 고정합니다.' },
  { id: 'section_drafting', label: 'Section Drafting', description: '섹션별로 실제 문장을 작성합니다.' },
  { id: 'revision', label: 'Revision', description: '문장 품질과 근거 경계를 정리합니다.' },
];

export const BLOCK_DEFINITIONS: Array<{ id: WorkshopDraftBlockId; heading: string }> = [
  { id: 'title', heading: '제목' },
  { id: 'introduction_background', heading: '서론 / 문제의식' },
  { id: 'body_section_1', heading: '본론 1 / 개념과 배경' },
  { id: 'body_section_2', heading: '본론 2 / 방법과 과정' },
  { id: 'body_section_3', heading: '본론 3 / 결과와 해석' },
  { id: 'conclusion_reflection_next_step', heading: '결론 / 느낀 점 / 출처' },
];

const HEADING_KEYWORDS: Record<WorkshopDraftBlockId, string[]> = {
  title: ['title', '제목'],
  introduction_background: ['introduction', 'background', '도입', '배경', '서론'],
  body_section_1: ['body section 1', '본론 1', '본론1'],
  body_section_2: ['body section 2', '본론 2', '본론2'],
  body_section_3: ['body section 3', '본론 3', '본론3'],
  conclusion_reflection_next_step: ['conclusion', 'reflection', 'next step', '결론', '성찰', '다음 단계'],
};

const EXTRA_HEADING_KEYWORDS: Record<WorkshopDraftBlockId, string[]> = {
  title: ['\uC81C\uBAA9'],
  introduction_background: ['\uC11C\uB860', '\uB3C4\uC785', '\uBB38\uC81C\uC758\uC2DD', '\uB3D9\uAE30'],
  body_section_1: ['\uBCF8\uB860 1', '\uBCF8\uB8601', '\uAC1C\uB150', '\uBC30\uACBD'],
  body_section_2: ['\uBCF8\uB860 2', '\uBCF8\uB8602', '\uBC29\uBC95', '\uACFC\uC815', '\uD310\uB2E8'],
  body_section_3: ['\uBCF8\uB860 3', '\uBCF8\uB8603', '\uACB0\uACFC', '\uD574\uC11D', '\uBD84\uC11D'],
  conclusion_reflection_next_step: [
    '\uACB0\uB860',
    '\uB290\uB080 \uC810',
    '\uB290\uB080\uC810',
    '\uCD9C\uCC98',
    '\uCC38\uACE0\uBB38\uD5CC',
    '\uD6C4\uC18D',
    'references',
  ],
};

export function createEmptyStructuredDraft(mode: WorkshopMode = 'planning'): WorkshopStructuredDraftState {
  return {
    mode,
    source: 'structured',
    blocks: BLOCK_DEFINITIONS.map((item) => ({
      block_id: item.id,
      heading: item.heading,
      content_markdown: '',
      attribution: 'student-authored',
      updated_at: null,
    })),
  };
}

export function normalizeStructuredDraft(
  raw: unknown,
  fallbackMode: WorkshopMode = 'planning',
): WorkshopStructuredDraftState | null {
  if (!raw || typeof raw !== 'object') return null;
  const candidate = raw as Record<string, unknown>;
  const mode = normalizeMode(candidate.mode) ?? fallbackMode;
  const blocksRaw = Array.isArray(candidate.blocks) ? candidate.blocks : [];
  if (!blocksRaw.length) return createEmptyStructuredDraft(mode);

  const byId = new Map<WorkshopDraftBlockId, WorkshopDraftBlock>();
  for (const item of blocksRaw) {
    if (!item || typeof item !== 'object') continue;
    const block = item as Record<string, unknown>;
    const blockId = normalizeBlockId(block.block_id);
    if (!blockId) continue;
    byId.set(blockId, {
      block_id: blockId,
      heading: String(block.heading || findHeadingById(blockId)),
      content_markdown: String(block.content_markdown || ''),
      attribution: normalizeAttribution(block.attribution),
      updated_at: block.updated_at ? String(block.updated_at) : null,
    });
  }

  return {
    mode,
    source: candidate.source === 'derived' ? 'derived' : 'structured',
    last_synced_turn_id: candidate.last_synced_turn_id ? String(candidate.last_synced_turn_id) : null,
    blocks: BLOCK_DEFINITIONS.map((item) => byId.get(item.id) || {
      block_id: item.id,
      heading: item.heading,
      content_markdown: '',
      attribution: 'student-authored',
      updated_at: null,
    }),
  };
}

export function structuredDraftToMarkdown(state: WorkshopStructuredDraftState): string {
  const lines: string[] = [];
  const titleBlock = state.blocks.find((item) => item.block_id === 'title');
  const title = (titleBlock?.content_markdown || '').trim() || (titleBlock?.heading || 'Draft');
  lines.push(`# ${title}`);

  for (const block of state.blocks) {
    if (block.block_id === 'title') continue;
    lines.push('');
    lines.push(`## ${block.heading}`);
    lines.push(block.content_markdown || '');
  }
  return lines.join('\n').trim();
}

export function markdownToStructuredDraft(
  markdown: string,
  mode: WorkshopMode = 'planning',
): WorkshopStructuredDraftState {
  const seed = createEmptyStructuredDraft(mode);
  const source = String(markdown || '').replace(/\r\n/g, '\n').trim();
  if (!source) return seed;

  const lines = source.split('\n');
  const titleLine = lines.find((line) => line.startsWith('# '));
  if (titleLine) {
    seed.blocks[0] = {
      ...seed.blocks[0],
      content_markdown: titleLine.replace(/^#\s*/, '').trim(),
    };
  }

  const sections = splitMarkdownSections(source);
  if (!sections.length) {
    seed.blocks[1] = {
      ...seed.blocks[1],
      content_markdown: source.replace(/^#.*$/m, '').trim(),
    };
    return seed;
  }

  for (const section of sections) {
    const matchedId = matchSectionToBlock(section.heading);
    if (!matchedId) continue;
    const target = seed.blocks.find((item) => item.block_id === matchedId);
    if (!target) continue;
    target.heading = section.heading;
    target.content_markdown = (section.content || '').trim();
  }

  return seed;
}

export function applyDraftPatch(
  state: WorkshopStructuredDraftState,
  patch: WorkshopDraftPatchProposal,
  options?: { approved?: boolean; allowOverwriteStudentContent?: boolean },
): { next: WorkshopStructuredDraftState; applied: boolean; blockedReason?: string } {
  const approved = options?.approved ?? false;
  const allowOverwrite = options?.allowOverwriteStudentContent ?? false;
  const target = state.blocks.find((block) => block.block_id === patch.block_id);
  if (!target) {
    return { next: state, applied: false, blockedReason: 'unknown_block' };
  }

  const hasSubstantialStudentContent =
    target.attribution === 'student-authored' && (target.content_markdown || '').trim().length >= 180;
  if (approved && hasSubstantialStudentContent && !allowOverwrite) {
    return { next: state, applied: false, blockedReason: 'student_content_protected' };
  }

  const nextBlocks = state.blocks.map((block) => {
    if (block.block_id !== patch.block_id) return block;

    const nextHeading = patch.heading?.trim() ? patch.heading.trim() : block.heading;
    const patchContent = (patch.content_markdown || '').trim();
    let nextContent = block.content_markdown || '';
    if (!nextContent.trim()) {
      nextContent = patchContent;
    } else if (nextContent.includes(patchContent)) {
      nextContent = nextContent;
    } else if (approved && block.attribution !== 'student-authored') {
      nextContent = patchContent;
    } else {
      nextContent = `${nextContent.trim()}\n\n${patchContent}`;
    }

    const nextAttribution: WorkshopDraftAttribution = approved
      ? 'ai-inserted-after-approval'
      : 'ai-suggested';

    return {
      ...block,
      heading: nextHeading,
      content_markdown: nextContent,
      attribution: nextAttribution,
      updated_at: new Date().toISOString(),
    };
  });

  return {
    next: {
      ...state,
      mode: patch.mode || state.mode,
      blocks: nextBlocks,
      source: 'structured',
    },
    applied: true,
  };
}

export function isPatchAcceptanceMessage(text: string): boolean {
  const normalized = (text || '').trim().toLowerCase();
  if (!normalized) return false;
  return /(반영|적용|좋아|진행|확정|그대로|ok|okay|yes|accept|approve|continue|계속)/i.test(normalized);
}

export function isSectionDraftIntent(text: string): boolean {
  const normalized = (text || '').trim().toLowerCase();
  if (!normalized) return false;
  return /(작성|써줘|초안|draft|section|문단|본문|본론|서론|결론|느낀 점|느낀점|출처|outline|개요)/i.test(normalized);
}

function findHeadingById(id: WorkshopDraftBlockId): string {
  return BLOCK_DEFINITIONS.find((item) => item.id === id)?.heading || id;
}

function normalizeMode(value: unknown): WorkshopMode | null {
  if (value === 'planning' || value === 'outline' || value === 'section_drafting' || value === 'revision') {
    return value;
  }
  return null;
}

function normalizeBlockId(value: unknown): WorkshopDraftBlockId | null {
  if (
    value === 'title' ||
    value === 'introduction_background' ||
    value === 'body_section_1' ||
    value === 'body_section_2' ||
    value === 'body_section_3' ||
    value === 'conclusion_reflection_next_step'
  ) {
    return value;
  }
  return null;
}

function normalizeAttribution(value: unknown): WorkshopDraftAttribution {
  if (value === 'ai-suggested' || value === 'ai-inserted-after-approval' || value === 'student-authored') {
    return value;
  }
  return 'student-authored';
}

function splitMarkdownSections(markdown: string): Array<{ heading: string; content: string }> {
  const normalized = markdown.replace(/\r\n/g, '\n');
  const regex = /^##\s+(.+)$/gm;
  const matches = [...normalized.matchAll(regex)];
  if (!matches.length) return [];

  const sections: Array<{ heading: string; content: string }> = [];
  for (let i = 0; i < matches.length; i += 1) {
    const heading = matches[i][1].trim();
    const start = (matches[i].index || 0) + matches[i][0].length;
    const end = i + 1 < matches.length ? matches[i + 1].index || normalized.length : normalized.length;
    const content = normalized.slice(start, end).trim();
    sections.push({ heading, content });
  }
  return sections;
}

function matchSectionToBlock(heading: string): WorkshopDraftBlockId | null {
  const normalized = heading.trim().toLowerCase();
  for (const [blockId, keywords] of Object.entries(HEADING_KEYWORDS) as Array<[WorkshopDraftBlockId, string[]]>) {
    const expandedKeywords = [...keywords, ...(EXTRA_HEADING_KEYWORDS[blockId] || [])];
    if (expandedKeywords.some((keyword) => normalized.includes(keyword.toLowerCase()))) {
      return blockId;
    }
  }
  return null;
}
