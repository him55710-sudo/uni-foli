import React, { memo, useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { AnimatePresence, motion } from 'motion/react';
import {
  BookOpen,
  Bot,
  ChevronDown,
  ChevronUp,
  CheckCircle2,
  Download,
  FileText,
  GraduationCap,
  Layers,
  Loader2,
  MessageSquare,
  PanelRightClose,
  PenSquare,
  Plus,
  Presentation,
  Save,
  Send,
  Sparkles,
  Target,
  ToggleLeft,
  ToggleRight,
  User,
  Wand2,
  X,
} from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import remarkMath from 'remark-math';
import rehypeKatex from 'rehype-katex';
import 'katex/dist/katex.min.css';
import { useLocation, useNavigate, useParams } from 'react-router-dom';
import toast from 'react-hot-toast';
import confetti from 'canvas-confetti';
import { auth } from '../lib/firebase';
import { api, resolveApiBaseUrl, resolveSameOriginApiBaseUrl } from '../lib/api';
import {
  ChatStreamError,
  consumeChatEventStream,
  openChatEventStreamWithFallback,
  resolveChatStreamFallbackHint,
  resolveChatStreamToastMessage,
  type ChatStreamMetaPayload,
} from '../lib/chatStream';
import { cn } from '../lib/cn';
import { DIAGNOSIS_STORAGE_KEY, type DiagnosisResultPayload, type DiagnosisRunResponse, type StoredDiagnosis } from '../lib/diagnosis';
import {
  deriveArchiveTitle,
  getArchiveItem,
  isGenericArchiveTitle,
  listArchiveItems,
  resolveArchiveDownloadContent,
  saveArchiveItem,
  type ArchiveItem,
} from '../lib/archiveStore';
import { readQuestStart } from '../lib/questStart';
import type { AuthTokenSource } from '../lib/requestAuth';
import { AdvancedPreview } from '../components/AdvancedPreview';
import { EvidenceDrawer } from '../components/EvidenceDrawer';
import {
  PageHeader,
  PrimaryButton,
  SecondaryButton,
  SectionCard,
  StatusBadge,
  SurfaceCard,
  WorkflowNotice,
} from '../components/primitives';
import { TiptapEditor, type TiptapEditorHandle } from '../components/editor/TiptapEditor';
import { ChatBubble as WorkshopChatBubble } from '../features/workshop/components/ChatBubble';
import { PatchReviewCard } from '../features/workshop/components/PatchReviewCard';
import { WorkshopMobileToggle } from '../features/workshop/components/WorkshopMobileToggle';
import { TiptapEditorAdapter } from '../features/workshop/adapters/TiptapEditorAdapter';
import {
  applyReportPatchToStructuredDraft,
  convertWorkshopDraftPatchToReportPatch,
  structuredDraftToReportDocumentState,
} from '../features/workshop/adapters/workshopPatchAdapter';
import type { ReportPatch, ResearchCandidate, SourceRecord } from '../features/workshop/types/reportDocument';
import type { ReviewablePatch } from '../features/workshop/utils/messageFormatters';
import {
  buildResearchQueryFromMessage,
  inferTargetSectionFromResearchMessage,
  isResearchRequestMessage,
} from '../features/workshop/utils/researchIntent';
import { validateReportPatch } from '../features/workshop/validators/reportValidation';
import type { FormatValidationResult } from '../features/workshop/validators/reportValidation';
import { useDocumentPatch } from '../features/workshop/hooks/useDocumentPatch';
import { useEditorBridge } from '../features/workshop/hooks/useEditorBridge';
import { useResearchCandidates } from '../features/workshop/hooks/useResearchCandidates';
import type { ResearchSearchSource } from '../features/workshop/api/researchClient';
import {
  TOPIC_SUGGESTION_PREVIEW_COUNT,
  limitTopicSuggestions,
  type GuidedChoiceGroup,
  type GuidedChoiceOption,
  type GuidedConversationPhase,
  type GuidedPageRangeSelectionResponse,
  type GuidedStructureOption,
  type GuidedStructureSelectionResponse,
  type GuidedTopicSelectionResponse,
  type GuidedTopicSuggestion,
  type GuidedTopicSuggestionResponse,
} from '../lib/guidedChat';
import {
  buildSpecificTopicCheckGroup,
  buildSubjectQuickPickGroup,
  inferGuidedPhase,
  isRecommendationAffirmative,
  isSpecificTopicAffirmative,
  isGuidedSetupComplete,
  looksLikeBroadSubject,
  resolvePageRangeLabel,
  resolveStructureOptionId,
} from '../lib/guidedConversation';
import {
  BLOCK_DEFINITIONS,
  WORKSHOP_MODE_OPTIONS,
  applyDraftPatch,
  createEmptyStructuredDraft,
  isPatchAcceptanceMessage,
  isSectionDraftIntent,
  markdownToStructuredDraft,
  normalizeStructuredDraft,
  structuredDraftToMarkdown,
  type WorkshopDraftAttribution,
  type WorkshopDraftBlockId,
  type WorkshopDraftPatchProposal,

  type WorkshopMode,
  type WorkshopStructuredDraftState,
} from '../lib/workshopCoauthoring';
import {
  buildDiagnosisChatStarter,
  resolveChatbotModeFromRouteContext,
  type ChatbotMode,
} from '../lib/chatbotMode';

import { MemoizedMarkdown, type MessageRole } from '../features/workshop/components/MemoizedMarkdown';

export type QualityLevel = 'low' | 'mid' | 'high';

interface Message {
  id: string;
  role: MessageRole;
  content: string;
  draftPatch?: WorkshopDraftPatchProposal;
  reportPatch?: ReportPatch;
  patchValidation?: FormatValidationResult | null;
  researchCandidates?: ResearchCandidate[];
  researchSources?: SourceRecord[];
  phase?: GuidedConversationPhase | null;
  topicSubject?: string;
  topicSuggestions?: GuidedTopicSuggestion[];
  pageRangeOptions?: GuidedTopicSelectionResponse['recommended_page_ranges'];
  structureOptions?: GuidedStructureOption[];
  nextActionOptions?: GuidedChoiceOption[];
  choiceGroups?: GuidedChoiceGroup[];
}

interface DraftArtifact {
  id: string;
  report_markdown: string;
  visual_specs: any[];
  math_expressions: any[];
  evidence_map?: Record<string, any> | null;
  structured_draft?: WorkshopStructuredDraftState | null;
  updated_at?: string | null;
}

interface WorkshopSaveDraftResponse {
  status: string;
  message: string;
  saved_updated_at: string;
  structured_draft?: WorkshopStructuredDraftState | null;
}

interface WorkshopSessionResponse {
  id: string;
  project_id: string;
  quest_id: string | null;
  status: string;
  quality_level: QualityLevel;
  turns?: Array<{
    id: string;
    turn_type: string;
    speaker_role?: string;
    query?: string;
    response?: string;
    action_payload?: Record<string, unknown> | null;
  }>;
}

export interface QualityLevelInfo {
  level: QualityLevel;
  label: string;
  emoji: string;
  color: string;
  description: string;
  detail: string;
  student_fit: string;
  safety_posture: string;
  authenticity_policy: string;
  hallucination_guardrail: string;
  advanced_features_allowed: boolean;
  minimum_turn_count: number;
  minimum_reference_count: number;
  render_threshold: number;
}

export interface RenderRequirementInfo {
  required_context_score: number;
  minimum_turn_count: number;
  minimum_reference_count: number;
  current_context_score: number;
  current_turn_count: number;
  current_reference_count: number;
  can_render: boolean;
  missing: string[];
}

interface WorkshopStateResponse {
  session: WorkshopSessionResponse;
  starter_choices: any[];
  followup_choices: any[];
  message: string | null;
  quality_level_info?: QualityLevelInfo;
  available_quality_levels?: QualityLevelInfo[];
  render_requirements?: RenderRequirementInfo;
  latest_artifact: DraftArtifact | null;
}

interface GuidedChatStartResponse {
  greeting: string;
  assistant_message?: string | null;
  phase?: GuidedConversationPhase;
  project_id: string | null;
  evidence_gap_note: string | null;
  choice_groups?: GuidedChoiceGroup[];
  limited_mode?: boolean | null;
  limited_reason?: string | null;
  state_summary?: Record<string, unknown> | null;
}

interface StreamMetaPayload extends ChatStreamMetaPayload {
  coauthoring_mode?: WorkshopMode;
}

interface StreamFoliReplyResult {
  text: string;
  authSource: AuthTokenSource;
}

interface WorkshopStreamTokenResponse {
  stream_token: string;
  workshop_id: string;
  expires_in: number;
}

interface WorkshopRenderStartResponse {
  artifact_id: string;
  status: string;
  advanced_mode?: string;
  rag_source?: string;
}

interface WorkshopArtifactReadyPayload {
  artifact_id?: string;
  report_markdown?: string;
  teacher_record_summary_500?: string;
  student_submission_note?: string;
  evidence_map?: Record<string, any> | null;
  visual_specs?: any[];
  math_expressions?: any[];
  structured_draft?: WorkshopStructuredDraftState | null;
}

type WorkshopResearchDepth = 'standard' | 'scholarly';
type RecordAreaId =
  | 'subject_specialty'
  | 'subject_activity'
  | 'club_activity'
  | 'creative_activity'
  | 'career_activity'
  | 'reading_report'
  | 'ai_auto';

type WritingGradeId = 'auto' | 'high1' | 'high2' | 'high3' | 'all';

interface RecordAreaOption {
  id: RecordAreaId;
  label: string;
  description: string;
  promptLabel: string;
  detailPlaceholder: string;
  keywords: string[];
}

interface WritingGradeOption {
  id: WritingGradeId;
  label: string;
  description: string;
}

interface WritingEvidenceItem {
  text: string;
  source: string;
  score: number;
}

interface WritingTopicSeed {
  title: string;
  reason: string;
  evidenceHooks: string[];
}

interface WritingCandidate {
  id: string;
  title: string;
  areaId: RecordAreaId;
  areaLabel: string;
  reason: string;
  evidence: string;
  source: string;
  gradeFit: string;
  caution: string;
}

interface AccumulationStep {
  id: string;
  label: string;
  description: string;
  blockId: WorkshopDraftBlockId;
  instruction: string;
  subheading?: string;
}

type StoredDiagnosisLike = Partial<StoredDiagnosis> & {
  diagnosis?: (Partial<DiagnosisResultPayload> & Record<string, unknown>) | null;
  diagnosisRunId?: string | null;
};

const RECORD_AREA_OPTIONS: RecordAreaOption[] = [
  {
    id: 'subject_specialty',
    label: '과목 세특',
    description: '특정 과목 세특 문장을 탐구 보고서의 출발점으로 씁니다.',
    promptLabel: '과목 세특',
    detailPlaceholder: '예: 생명과학 세특, 수학 세특',
    keywords: ['세특', '교과', '과목', '수학', '국어', '영어', '과학', '사회', '기술', '정보', '생명', '화학', '물리'],
  },
  {
    id: 'subject_activity',
    label: '교과활동',
    description: '수업 중 발표, 실험, 프로젝트, 수행평가 기록을 확장합니다.',
    promptLabel: '교과활동',
    detailPlaceholder: '예: 통계 프로젝트, 과학 실험 발표',
    keywords: ['교과', '수업', '발표', '수행', '실험', '프로젝트', '탐구'],
  },
  {
    id: 'club_activity',
    label: '동아리활동',
    description: '동아리 안에서 맡은 역할과 산출물을 보고서 주제로 연결합니다.',
    promptLabel: '동아리활동',
    detailPlaceholder: '예: 생명과학 동아리, 경영 동아리',
    keywords: ['동아리', '자율동아리', '부원', '부장', '활동'],
  },
  {
    id: 'creative_activity',
    label: '창체활동',
    description: '자율, 봉사, 진로, 행사 등 창체 기록의 성장 흐름을 씁니다.',
    promptLabel: '창체활동',
    detailPlaceholder: '예: 자율활동, 봉사활동, 학교 행사',
    keywords: ['창체', '자율', '봉사', '행사', '공동체', '협업'],
  },
  {
    id: 'career_activity',
    label: '진로활동',
    description: '진로 탐색, 전공 관심, 후속 계획을 중심으로 구성합니다.',
    promptLabel: '진로활동',
    detailPlaceholder: '예: 의생명 진로탐색, 건축 진로활동',
    keywords: ['진로', '전공', '학과', '직업', '멘토링', '탐색'],
  },
  {
    id: 'reading_report',
    label: '독서/보고서',
    description: '독서 기록이나 기존 보고서를 세특/전공 맥락과 엮습니다.',
    promptLabel: '독서/보고서',
    detailPlaceholder: '예: 읽은 책 제목, 기존 탐구 보고서',
    keywords: ['독서', '책', '보고서', '논문', '자료', '출처'],
  },
  {
    id: 'ai_auto',
    label: 'AI가 알아서 선택',
    description: '생기부 근거가 가장 많은 영역을 AI가 먼저 고릅니다.',
    promptLabel: 'AI 자동 선택',
    detailPlaceholder: '원하는 방향이 있으면 한 줄만 적어도 됩니다.',
    keywords: [],
  },
];

const WRITING_GRADE_OPTIONS: WritingGradeOption[] = [
  { id: 'auto', label: '진단 기준', description: '생기부에 드러난 학년 흐름을 자동 반영' },
  { id: 'high1', label: '고1', description: '관심 형성과 기본 개념 이해 중심' },
  { id: 'high2', label: '고2', description: '과정, 방법, 실패와 보완 중심' },
  { id: 'high3', label: '고3', description: '전공 수렴, 결과 해석, 면접 방어 중심' },
  { id: 'all', label: '전체', description: '학년 간 성장 흐름을 연결' },
];

const ACCUMULATION_STEPS: AccumulationStep[] = [
  {
    id: 'intro',
    label: '서론',
    description: '동기, 문제의식, 생기부 출발점',
    blockId: 'introduction_background',
    instruction: '서론만 작성하세요. 학생부 근거에서 출발한 동기와 탐구 질문이 자연스럽게 이어져야 합니다.',
  },
  {
    id: 'body1',
    label: '본론 1',
    description: '핵심 개념과 배경 정리',
    blockId: 'body_section_1',
    instruction: '본론 1만 작성하세요. 핵심 개념, 배경, 고교 수준에서 설명 가능한 원리를 정리하세요.',
  },
  {
    id: 'body2',
    label: '본론 2',
    description: '방법, 과정, 학생의 판단',
    blockId: 'body_section_2',
    instruction: '본론 2만 작성하세요. 학생이 선택한 방법, 의사결정 근거, 한계 보완 과정을 중심으로 쓰세요.',
  },
  {
    id: 'body3',
    label: '본론 3',
    description: '결과 해석과 전공 연결',
    blockId: 'body_section_3',
    instruction: '본론 3만 작성하세요. 결과 해석, 의미, 전공 또는 진로와의 연결을 구체화하세요.',
  },
  {
    id: 'conclusion',
    label: '결론',
    description: '핵심 주장과 후속 탐구',
    blockId: 'conclusion_reflection_next_step',
    instruction: '결론 부분만 작성하세요. 보고서의 핵심 주장, 한계, 후속 탐구 방향을 정리하세요.',
    subheading: '결론',
  },
  {
    id: 'reflection',
    label: '느낀 점',
    description: '배운 점, 성장, 다음 질문',
    blockId: 'conclusion_reflection_next_step',
    instruction: '느낀 점 부분만 작성하세요. 학생의 생각, 배운 점, 다음 활동으로 이어진 지적 자극을 분리해 쓰세요.',
    subheading: '느낀 점',
  },
  {
    id: 'references',
    label: '출처',
    description: '생기부 p.X와 참고자료 목록',
    blockId: 'conclusion_reflection_next_step',
    instruction: '출처 부분만 작성하세요. 생기부 근거는 [출처: 생기부 p.X] 형식으로 남기고, 외부 자료가 필요하면 후보만 제안하세요.',
    subheading: '출처',
  },
];

function getAccumulationStepById(stepId: string | null | undefined): AccumulationStep | null {
  if (!stepId) return null;
  return ACCUMULATION_STEPS.find((step) => step.id === stepId) || null;
}

function getNextAccumulationStep(step: AccumulationStep | null): AccumulationStep | null {
  if (!step) return null;
  const index = ACCUMULATION_STEPS.findIndex((item) => item.id === step.id);
  if (index < 0) return null;
  return ACCUMULATION_STEPS[index + 1] || null;
}

function isAccumulationStepComplete(step: AccumulationStep, structuredDraft: WorkshopStructuredDraftState): boolean {
  const content = structuredDraft.blocks.find((block) => block.block_id === step.blockId)?.content_markdown || '';
  return step.subheading
    ? content.includes(step.subheading) || content.trim().length >= 240
    : content.trim().length >= 80;
}

function inferCurrentAccumulationStepId(structuredDraft: WorkshopStructuredDraftState): string {
  return ACCUMULATION_STEPS.find((step) => !isAccumulationStepComplete(step, structuredDraft))?.id || ACCUMULATION_STEPS[0].id;
}

function resolveAppliedAccumulationStep(
  patch: WorkshopDraftPatchProposal,
  activeStepId: string | null,
): AccumulationStep | null {
  const activeStep = getAccumulationStepById(activeStepId);
  if (activeStep?.blockId === patch.block_id) return activeStep;

  return (
    ACCUMULATION_STEPS.find((step) => {
      if (step.blockId !== patch.block_id) return false;
      return step.subheading ? patch.content_markdown.includes(step.subheading) : true;
    }) || null
  );
}

function buildAccumulationNextChoiceGroup(currentStep: AccumulationStep, nextStep: AccumulationStep): GuidedChoiceGroup {
  return {
    id: 'accumulation-next-step',
    title: '다음 작성 단계',
    style: 'buttons',
    options: [
      {
        id: `next-${nextStep.id}`,
        label: `다음 단계: ${nextStep.label}`,
        description: `${nextStep.description}에 대해 먼저 대화하고, 확정 가능한 문장만 제안합니다.`,
        value: `next:${nextStep.id}`,
      },
      {
        id: `revise-${currentStep.id}`,
        label: `${currentStep.label} 보강`,
        description: '방금 반영한 단계만 더 다듬습니다.',
        value: `revise:${currentStep.id}`,
      },
    ],
  };
}

const QUALITY_META_MAP: Record<QualityLevel, { label: string; status: 'success' | 'active' | 'warning' }> = {
  low: { label: '빠른 응답', status: 'success' },
  mid: { label: '균형 모드', status: 'active' },
  high: { label: '심화 모드', status: 'warning' },
};

const GUIDED_CHAT_GREETING = '안녕하세요. 어떤 주제로 보고서를 작성해볼까요?';
const DIAGNOSIS_RISK_LABEL_MAP: Record<string, string> = {
  safe: '근거 충분',
  warning: '보완 필요',
  danger: '집중 보완 필요',
};

function formatDiagnosisRiskLabel(value: string | undefined): string {
  const key = String(value || '').trim().toLowerCase();
  return DIAGNOSIS_RISK_LABEL_MAP[key] || '보완 필요';
}

function formatDraftAttributionLabel(attribution: WorkshopDraftAttribution): string {
  if (attribution === 'student-authored') return '학생 작성';
  if (attribution === 'ai-inserted-after-approval') return '승인 후 AI 반영';
  return 'AI 제안';
}

function asPlainRecord(value: unknown): Record<string, unknown> | null {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return null;
  return value as Record<string, unknown>;
}

function asCleanText(value: unknown): string | null {
  if (typeof value !== 'string') return null;
  const trimmed = value.replace(/\s+/g, ' ').trim();
  return trimmed || null;
}

function clipWritingText(value: string, limit = 180): string {
  const normalized = value.replace(/\s+/g, ' ').trim();
  if (normalized.length <= limit) return normalized;
  return `${normalized.slice(0, limit).trim()}...`;
}

function uniquePush(items: string[], value: unknown, limit = 8) {
  const text = asCleanText(value);
  if (!text || items.length >= limit) return;
  const key = text.toLowerCase();
  if (items.some((item) => item.toLowerCase() === key)) return;
  items.push(text);
}

function collectWritingTextList(value: unknown, limit = 6): string[] {
  const out: string[] = [];
  const pushFromRecord = (record: Record<string, unknown>) => {
    for (const key of ['title', 'label', 'summary', 'description', 'why_it_fits', 'why_now', 'rationale', 'note', 'evidence_hint']) {
      uniquePush(out, record[key], limit);
      if (out.length >= limit) return;
    }
  };

  if (typeof value === 'string') {
    uniquePush(out, value, limit);
    return out;
  }
  if (!Array.isArray(value)) return out;

  for (const item of value) {
    if (typeof item === 'string') {
      uniquePush(out, item, limit);
    } else {
      const record = asPlainRecord(item);
      if (record) pushFromRecord(record);
    }
    if (out.length >= limit) break;
  }
  return out;
}

function toDiagnosisPayloadRecord(value: unknown): (Partial<DiagnosisResultPayload> & Record<string, unknown>) | null {
  const record = asPlainRecord(value);
  if (!record) return null;
  return record as Partial<DiagnosisResultPayload> & Record<string, unknown>;
}

function readStoredDiagnosisSnapshot(): StoredDiagnosisLike | null {
  if (typeof window === 'undefined') return null;
  try {
    const raw = window.localStorage.getItem(DIAGNOSIS_STORAGE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as StoredDiagnosisLike;
    return parsed && typeof parsed === 'object' ? parsed : null;
  } catch {
    return null;
  }
}

function resolveRecordAreaOption(areaId: RecordAreaId): RecordAreaOption {
  return RECORD_AREA_OPTIONS.find((item) => item.id === areaId) || RECORD_AREA_OPTIONS[0];
}

function scoreTextForArea(text: string, area: RecordAreaOption, detail: string): number {
  const haystack = text.toLowerCase();
  let score = 0;
  for (const keyword of area.keywords) {
    if (keyword && haystack.includes(keyword.toLowerCase())) score += 2;
  }
  for (const token of detail.split(/[\s,./]+/).map((item) => item.trim()).filter(Boolean)) {
    if (token.length >= 2 && haystack.includes(token.toLowerCase())) score += 4;
  }
  return score;
}

function collectWritingEvidence(
  payload: (Partial<DiagnosisResultPayload> & Record<string, unknown>) | null,
  areaId: RecordAreaId,
  detail: string,
  limit = 8,
): WritingEvidenceItem[] {
  const area = resolveRecordAreaOption(areaId === 'ai_auto' ? 'subject_specialty' : areaId);
  const evidence: WritingEvidenceItem[] = [];
  const seen = new Set<string>();

  const push = (textValue: unknown, sourceValue: unknown = '진단 요약') => {
    const text = asCleanText(textValue);
    if (!text) return;
    const source = asCleanText(sourceValue) || '진단 요약';
    const clipped = clipWritingText(text, 220);
    const key = `${source}:${clipped}`.toLowerCase();
    if (seen.has(key)) return;
    seen.add(key);
    evidence.push({
      text: clipped,
      source,
      score: scoreTextForArea(`${source} ${clipped}`, area, detail),
    });
  };

  if (!payload) return evidence;

  if (Array.isArray(payload.citations)) {
    payload.citations.forEach((citation) => {
      const record = asPlainRecord(citation);
      if (!record) return;
      const page = typeof record.page_number === 'number' ? ` p.${record.page_number}` : '';
      push(record.excerpt, `${asCleanText(record.source_label) || '생기부'}${page}`);
    });
  }

  if (Array.isArray(payload.admission_axes)) {
    payload.admission_axes.forEach((axis) => {
      const record = asPlainRecord(axis);
      if (!record) return;
      const label = asCleanText(record.label) || '평가축';
      if (Array.isArray(record.evidence_hints)) {
        record.evidence_hints.forEach((hint) => push(hint, label));
      }
      push(record.rationale, label);
    });
  }

  const graph = asPlainRecord(payload.relational_graph);
  const clusters = Array.isArray(graph?.theme_clusters) ? graph?.theme_clusters : [];
  clusters.forEach((cluster) => {
    const record = asPlainRecord(cluster);
    if (!record) return;
    const theme = asCleanText(record.theme) || '주제 클러스터';
    if (Array.isArray(record.evidence)) {
      record.evidence.forEach((item) => push(item, theme));
    }
  });

  collectWritingTextList(payload.strengths, 5).forEach((item) => push(item, '강점 분석'));
  collectWritingTextList(payload.gaps, 5).forEach((item) => push(item, '보완점 분석'));
  push(payload.recommended_focus, '추천 초점');
  push(payload.headline, '진단 헤드라인');

  return evidence
    .sort((a, b) => b.score - a.score)
    .slice(0, limit);
}

function collectWritingTopicSeeds(
  payload: (Partial<DiagnosisResultPayload> & Record<string, unknown>) | null,
  limit = 6,
): WritingTopicSeed[] {
  const seeds: WritingTopicSeed[] = [];
  const seen = new Set<string>();
  const push = (titleValue: unknown, reasonValue?: unknown, evidenceHooksValue?: unknown) => {
    const title = asCleanText(titleValue);
    if (!title) return;
    const key = title.toLowerCase();
    if (seen.has(key)) return;
    seen.add(key);
    const evidenceHooks = Array.isArray(evidenceHooksValue)
      ? evidenceHooksValue.map(asCleanText).filter((item): item is string => Boolean(item)).slice(0, 3)
      : [];
    seeds.push({
      title: clipWritingText(title, 120),
      reason: asCleanText(reasonValue) || '생기부 진단에서 확장 가능성이 높은 후보로 감지되었습니다.',
      evidenceHooks,
    });
  };

  if (!payload) return seeds;

  if (Array.isArray(payload.recommended_directions)) {
    payload.recommended_directions.forEach((direction) => {
      const directionRecord = asPlainRecord(direction);
      if (!directionRecord) return;
      if (Array.isArray(directionRecord.topic_candidates)) {
        directionRecord.topic_candidates.forEach((topic) => {
          const topicRecord = asPlainRecord(topic);
          if (!topicRecord) return;
          push(topicRecord.title, topicRecord.why_it_fits || directionRecord.why_now || directionRecord.summary, topicRecord.evidence_hooks);
        });
      }
      push(directionRecord.label, directionRecord.why_now || directionRecord.summary);
    });
  }

  collectWritingTextList(payload.recommended_topics, limit).forEach((topic) => push(topic, payload.recommended_focus));
  push(payload.recommended_focus, payload.headline || payload.overview);
  push(payload.headline, payload.overview);

  return seeds.slice(0, limit);
}

function inferGradeFromDiagnosisPayload(payload: (Partial<DiagnosisResultPayload> & Record<string, unknown>) | null): string {
  if (!payload) return '전체 학년';
  const snippets: string[] = [];
  uniquePush(snippets, payload.headline, 20);
  uniquePush(snippets, payload.overview, 20);
  uniquePush(snippets, payload.recommended_focus, 20);
  collectWritingEvidence(payload, 'ai_auto', '', 12).forEach((item) => uniquePush(snippets, `${item.source} ${item.text}`, 20));
  const text = snippets.join(' ');
  const has1 = /(1학년|고1|1 학년)/.test(text);
  const has2 = /(2학년|고2|2 학년)/.test(text);
  const has3 = /(3학년|고3|3 학년)/.test(text);
  const count = [has1, has2, has3].filter(Boolean).length;
  if (count !== 1) return '전체 학년';
  if (has3) return '고3';
  if (has2) return '고2';
  return '고1';
}

function resolveWritingGradeLabel(gradeId: WritingGradeId, inferredGrade: string): string {
  if (gradeId === 'auto') return inferredGrade || '전체 학년';
  if (gradeId === 'high1') return '고1';
  if (gradeId === 'high2') return '고2';
  if (gradeId === 'high3') return '고3';
  return '전체 학년';
}

function buildGradeFitText(gradeLabel: string, index: number): string {
  if (gradeLabel === '고1') {
    return index === 0
      ? '고1 기록은 관심이 처음 생긴 이유와 기본 개념 이해를 선명하게 보여주는 쪽이 좋습니다.'
      : '고1 단계에서는 무리한 심화보다 질문이 생긴 과정과 배운 점을 정직하게 드러내는 구성이 안전합니다.';
  }
  if (gradeLabel === '고2') {
    return index === 1
      ? '고2 기록은 방법 선택, 시행착오, 결과 해석을 구체화하면 세특의 과정성이 살아납니다.'
      : '고2 단계에서는 교과 개념을 활동 과정으로 옮긴 장면을 근거로 잡는 것이 좋습니다.';
  }
  if (gradeLabel === '고3') {
    return index === 2
      ? '고3 기록은 전공 수렴, 한계 인식, 후속 탐구 계획까지 정리해야 면접 방어력이 생깁니다.'
      : '고3 단계에서는 결과의 의미와 전공 적합성을 분명히 연결하는 후보가 유리합니다.';
  }
  return '여러 학년 기록을 동기-과정-결과-후속 질문의 흐름으로 연결하기 좋습니다.';
}

function inferBestRecordArea(
  payload: (Partial<DiagnosisResultPayload> & Record<string, unknown>) | null,
  detail: string,
): RecordAreaId {
  if (!payload) return 'subject_specialty';
  const scored = RECORD_AREA_OPTIONS
    .filter((item) => item.id !== 'ai_auto')
    .map((area) => {
      const evidence = collectWritingEvidence(payload, area.id, detail, 12);
      return {
        areaId: area.id,
        score: evidence.reduce((sum, item) => sum + item.score, 0) + evidence.length,
      };
    })
    .sort((a, b) => b.score - a.score);
  return scored[0]?.areaId || 'subject_specialty';
}

function buildWritingCandidates(options: {
  payload: (Partial<DiagnosisResultPayload> & Record<string, unknown>) | null;
  areaId: RecordAreaId;
  detail: string;
  gradeLabel: string;
  targetMajor: string;
  fallbackTopic?: string | null;
}): WritingCandidate[] {
  const resolvedAreaId = options.areaId === 'ai_auto' ? inferBestRecordArea(options.payload, options.detail) : options.areaId;
  const area = resolveRecordAreaOption(resolvedAreaId);
  const detailLabel = options.detail.trim() || area.promptLabel;
  const targetMajor = options.targetMajor.trim() || '목표 전공';
  const topicSeeds = collectWritingTopicSeeds(options.payload, 6);
  const evidenceItems = collectWritingEvidence(options.payload, resolvedAreaId, options.detail, 8);
  const strengths = collectWritingTextList(options.payload?.strengths, 4);
  const gaps = collectWritingTextList(options.payload?.gaps, 4);
  const focus = asCleanText(options.payload?.recommended_focus) || asCleanText(options.payload?.headline) || options.fallbackTopic || '';
  const fallbackEvidence = evidenceItems[0]?.text || strengths[0] || '아직 생기부 원문 근거가 충분히 연결되지 않았습니다.';
  const fallbackSource = evidenceItems[0]?.source || '진단 요약';

  const templates = [
    {
      id: 'evidence',
      title:
        topicSeeds[0]?.title ||
        `${detailLabel}에서 출발한 ${targetMajor} 탐구 질문`,
      reason:
        topicSeeds[0]?.reason ||
        `${detailLabel} 기록과 ${targetMajor} 관심을 가장 직접적으로 연결할 수 있어 첫 보고서 후보로 적합합니다.`,
      evidence: topicSeeds[0]?.evidenceHooks[0] || evidenceItems[0]?.text || fallbackEvidence,
      source: evidenceItems[0]?.source || fallbackSource,
      caution: '활동을 과장하지 말고 본인이 실제로 판단한 과정과 사용한 개념을 먼저 확인해야 합니다.',
    },
    {
      id: 'process',
      title:
        topicSeeds[1]?.title ||
        `${detailLabel} 활동 과정의 선택과 한계 분석`,
      reason:
        topicSeeds[1]?.reason ||
        `${strengths[0] || focus || '강점 기록'}을 단순 결과가 아니라 과정 중심으로 풀어낼 수 있는 후보입니다.`,
      evidence: topicSeeds[1]?.evidenceHooks[0] || evidenceItems[1]?.text || fallbackEvidence,
      source: evidenceItems[1]?.source || fallbackSource,
      caution: '방법, 변인, 자료 선택의 이유가 비어 있으면 AI가 먼저 질문을 던지도록 두는 편이 좋습니다.',
    },
    {
      id: 'defense',
      title:
        topicSeeds[2]?.title ||
        `${targetMajor} 관점에서 본 ${detailLabel}의 보완 탐구`,
      reason:
        topicSeeds[2]?.reason ||
        `${gaps[0] || '보완이 필요한 지점'}을 결론과 후속 탐구로 전환하면 성장 서사가 만들어집니다.`,
      evidence: topicSeeds[2]?.evidenceHooks[0] || evidenceItems[2]?.text || fallbackEvidence,
      source: evidenceItems[2]?.source || fallbackSource,
      caution: '약점을 숨기기보다 왜 한계가 생겼고 다음 탐구에서 어떻게 보완할지 분명히 써야 합니다.',
    },
  ];

  return templates.map((template, index) => ({
    id: `${resolvedAreaId}-${template.id}`,
    title: clipWritingText(template.title, 100),
    areaId: resolvedAreaId,
    areaLabel: area.label,
    reason: clipWritingText(template.reason, 220),
    evidence: clipWritingText(template.evidence, 220),
    source: template.source,
    gradeFit: buildGradeFitText(options.gradeLabel, index),
    caution: template.caution,
  }));
}

function buildWritingPlanPrompt(options: {
  area: RecordAreaOption;
  detail: string;
  gradeLabel: string;
  targetMajor: string;
  candidate: WritingCandidate;
  preference: string;
  aiAutoSelect: boolean;
}): string {
  const detail = options.detail.trim() || options.area.promptLabel;
  const preference = options.preference.trim();
  return [
    '[문서작성 설정]',
    `- 작성 영역: ${options.area.label}`,
    `- 세부 과목/활동: ${detail}`,
    `- 학생 학년: ${options.gradeLabel}`,
    `- 목표 전공/방향: ${options.targetMajor || '미정'}`,
    `- 선택 후보: ${options.candidate.title}`,
    `- 후보 추천 이유: ${options.candidate.reason}`,
    `- 생기부 기반 근거: ${options.candidate.source}: ${options.candidate.evidence}`,
    `- 학년 반영 포인트: ${options.candidate.gradeFit}`,
    `- 학생 선호/의견: ${preference || (options.aiAutoSelect ? 'AI가 알아서 방향을 선택해도 됨' : '아직 입력 없음')}`,
    '',
    '[작성 규칙]',
    '1. 전체 보고서를 한 번에 완성하지 말고, 먼저 제목 후보와 서론만 다룹니다.',
    '2. 학생 의견이 부족하면 질문을 1개만 먼저 물어보고, AI 자동 선택이 허용된 경우에는 보수적인 가정을 명시한 뒤 진행합니다.',
    '3. 생기부에 없는 활동, 수상, 실험 결과, 수치, 논문명은 만들지 마세요.',
    '4. 작성 가능하면 [DRAFT_PATCH] JSON [/DRAFT_PATCH]를 정확히 1개만 포함하고 block_id는 introduction_background로 하세요.',
    '5. 서론에는 동기, 문제의식, 탐구 질문, 생기부 근거의 연결만 담고 본론/결론은 다음 단계로 남겨두세요.',
  ].join('\n');
}

function buildAccumulationPrompt(options: {
  step: AccumulationStep;
  candidate: WritingCandidate | null;
  area: RecordAreaOption;
  detail: string;
  gradeLabel: string;
  targetMajor: string;
  preference: string;
  currentBlockContent: string;
}): string {
  const detail = options.detail.trim() || options.area.promptLabel;
  const currentPreview = options.currentBlockContent.trim()
    ? clipWritingText(options.currentBlockContent, 360)
    : '아직 작성된 내용 없음';
  return [
    '[적립식 문서작성]',
    `- 이번에 쓸 부분: ${options.step.label}`,
    `- 목표 block_id: ${options.step.blockId}`,
    options.step.subheading ? `- 이 블록 안의 소제목: ${options.step.subheading}` : null,
    `- 작성 영역: ${options.area.label} / ${detail}`,
    `- 학생 학년: ${options.gradeLabel}`,
    `- 목표 전공/방향: ${options.targetMajor || '미정'}`,
    options.candidate ? `- 선택 후보: ${options.candidate.title}` : null,
    options.candidate ? `- 생기부 근거: ${options.candidate.source}: ${options.candidate.evidence}` : null,
    `- 학생 선호/의견: ${options.preference.trim() || '없으면 AI가 보수적으로 질문하거나 가정'}`,
    `- 현재 블록 내용: ${currentPreview}`,
    '',
    '[이번 단계 지시]',
    options.step.instruction,
    '전체 보고서를 한 번에 쓰지 말고 이번 섹션만 작성하거나 보강하세요.',
    '학생의 생각이 필요한 지점은 질문 1개를 먼저 던지되, 바로 작성 가능한 문장만 DRAFT_PATCH로 제안하세요.',
    `가능하면 [DRAFT_PATCH] JSON [/DRAFT_PATCH]를 정확히 1개만 포함하고 block_id는 ${options.step.blockId}로 하세요.`,
    '이미 있는 학생 작성 문장은 덮어쓰지 말고 뒤에 자연스럽게 이어 붙이는 방식으로 제안하세요.',
  ].filter(Boolean).join('\n');
}

function normalizeGuidedSuggestions(response: GuidedTopicSuggestionResponse): GuidedTopicSuggestion[] {
  return limitTopicSuggestions(response).suggestions;
}

function formatGuidedSuggestionMessage(response: GuidedTopicSuggestionResponse) {
  const suggestions = normalizeGuidedSuggestions(response);
  const preview = suggestions.slice(0, TOPIC_SUGGESTION_PREVIEW_COUNT);
  const lines = [
    `좋아요. '${response.subject}'을 바탕으로 학생 기록 흐름에 맞는 주제 ${suggestions.length}개를 준비했어요.`,
    `아래는 먼저 볼 만한 ${preview.length}개 하이라이트이고, 카드 목록에서는 전체 후보를 바로 선택할 수 있어요.`,
    '',
    ...preview.flatMap((item, index) => {
      const chunk = [
        `${index + 1}. **${item.title}**`,
        `- 추천 이유: ${item.why_fit_student}`,
        `- 기록 연결: ${item.link_to_record_flow}`,
      ];
      if (item.link_to_target_major_or_university) {
        chunk.push(`- 진로 연계: ${item.link_to_target_major_or_university}`);
      }
      if (item.caution_note) {
        chunk.push(`- 주의: ${item.caution_note}`);
      }
      return chunk;
    }),
  ];
  if (response.evidence_gap_note) {
    lines.push('', `참고: ${response.evidence_gap_note}`);
  }
  lines.push('', '아래 카드에서 가장 마음에 드는 주제를 골라주세요.');
  return lines.join('\n');
}

function formatGuidedSelectionMessage(response: GuidedTopicSelectionResponse) {
  const lines = [
    `선택한 주제는 **${response.selected_title}**입니다.`,
    '',
    response.guidance_message,
    '',
    '이제 진행할 보고서 분량을 고르면 바로 개요를 잡아드릴게요.',
  ];
  return lines.join('\n');
}

function formatGuidedPageRangeMessage(response: GuidedPageRangeSelectionResponse) {
  const lines = [
    response.assistant_message,
    '',
    `선택한 분량: **${response.selected_page_range_label}**`,
  ];
  if (response.selected_page_range_note) {
    lines.push(`- 참고: ${response.selected_page_range_note}`);
  }
  lines.push('', '다음으로 구성 유형을 골라주세요.');
  return lines.join('\n');
}

function formatGuidedStructureMessage(response: GuidedStructureSelectionResponse) {
  return [
    response.assistant_message,
    '',
    `선택한 구성: **${response.selected_structure_label}**`,
    '',
    '가이드 설정이 거의 끝났습니다. 다음으로 무엇을 쓰고 싶은지 알려주세요.',
  ].join('\n');
}

function formatAssistantMessageWithEvidenceNote(
  assistantMessage: string | null | undefined,
  evidenceGapNote: string | null | undefined,
) {
  const base = (assistantMessage || '').trim();
  const note = (evidenceGapNote || '').trim();
  if (base && note) return `${base}\n\n참고: ${note}`;
  if (base) return base;
  if (note) return `참고: ${note}`;
  return GUIDED_CHAT_GREETING;
}

function buildTopicChoiceGroup(suggestions: GuidedTopicSuggestion[]): GuidedChoiceGroup {
  return {
    id: 'topic-selection',
    title: `추천 탐구 주제 ${suggestions.length}개 중 하나를 골라주세요.`,
    style: 'cards',
    options: suggestions.map((topic) => ({
      id: topic.id,
      label: topic.title,
      description: topic.why_fit_student,
      value: topic.id,
    })),
  };
}

function buildPageRangeChoiceGroup(
  pageRanges: GuidedTopicSelectionResponse['recommended_page_ranges'],
): GuidedChoiceGroup {
  return {
    id: 'page-range-selection',
    title: '보고서 분량을 선택해 주세요.',
    style: 'cards',
    options: pageRanges.map((range) => ({
      id: `page-range-${range.label}`,
      label: range.label,
      description: range.why_this_length,
      value: range.label,
    })),
  };
}

function buildStructureChoiceGroup(options: GuidedStructureOption[]): GuidedChoiceGroup {
  return {
    id: 'structure-selection',
    title: '구성 유형을 골라주세요.',
    style: 'cards',
    options,
  };
}

function buildNextActionChoiceGroup(options: GuidedChoiceOption[]): GuidedChoiceGroup {
  return {
    id: 'next-action-selection',
    title: '다음으로 무엇을 할까요?',
    style: 'chips',
    options,
  };
}

function resolveGuidedSelectionFromText(text: string, suggestions: GuidedTopicSuggestion[]): GuidedTopicSuggestion | null {
  if (!suggestions.length) {
    return null;
  }
  const normalized = (text || '').trim().toLowerCase();
  if (!normalized) {
    return null;
  }
  const numberMatch = normalized.match(/^([1-3])$/);
  if (numberMatch) {
    const index = Number(numberMatch[1]) - 1;
    return suggestions[index] ?? null;
  }
  const topicIdMatch = normalized.match(/^topic-([1-3])$/);
  if (topicIdMatch) {
    const index = Number(topicIdMatch[1]) - 1;
    return suggestions[index] ?? null;
  }
  return (
    suggestions.find(
      item =>
        normalized === item.id.toLowerCase() ||
        normalized === item.title.toLowerCase() ||
        normalized.includes(item.title.toLowerCase()),
    ) ?? null
  );
}

function buildFoliFallback(message: string) {
  const readableFallback = buildReadableFoliFallback(message);
  if (readableFallback) return readableFallback;

  const clean = (message || '').toLowerCase().trim();
  const greetings = ['안녕', 'hi', 'hello', 'hey', 'good morning', 'good evening'];

  if (greetings.some(token => clean.includes(token))) {
    return [
      '안녕하세요. UniFoli 워크숍 도우미입니다.',
      '',
      '지금은 AI 연결이 잠시 불안정해서 초안 구조 정리와 다음 질문 안내를 중심으로 안전하게 이어갈게요.',
    ].join('\n');
  }

  return [
    '현재 AI 응답이 잠시 지연되어 기본 안내 모드로 전환되었어요.',
    '',
    '아래 순서대로 보내 주시면 초안 작성 흐름을 계속 이어갈 수 있어요.',
    '1. 이번 글에서 다루려는 주제를 한 문장으로 적어 주세요.',
    '2. 그 주제를 정한 이유를 간단히 알려 주세요.',
    '3. 마지막으로 보고서에 꼭 포함하고 싶은 키워드 3가지를 말해 주세요.',
  ].join('\n');
}

function buildReadableFoliFallback(message: string): string {
  const clean = (message || '').toLowerCase().trim();
  const isGreeting = ['안녕', 'hi', 'hello', 'hey', 'good morning', 'good evening'].some((token) =>
    clean.includes(token),
  );

  if (isGreeting) {
    return [
      '안녕하세요. UniFoli 워크숍입니다.',
      '',
      '지금 Gemini 기반 AI 응답 연결이 잠시 불안정해서 로컬 안내 모드로 전환했어요. 대화와 작성 흐름은 유지되니 그대로 이어가면 됩니다.',
      '',
      '바로 이어갈 수 있는 방법',
      '1. 과목이나 주제를 한 문장으로 보내 주세요.',
      '2. 이미 주제가 있으면 “이 주제로 보고서 써줘”라고 말해 주세요.',
      '3. 자료가 필요하면 “웹 자료 찾아줘” 또는 “논문 근거 찾아줘”처럼 원하는 리서치 범위를 구분해 주세요.',
    ].join('\n');
  }

  return [
    '현재 AI 응답이 지연되어 로컬 안내 모드로 전환했어요.',
    '',
    '초안 작성 흐름은 계속 이어갈 수 있습니다. 제가 받은 메시지를 바탕으로 다음 작업을 준비해둘게요.',
    '',
    '바로 이어갈 수 있는 방법',
    '1. 보고서 주제를 한 문장으로 알려 주세요.',
    '2. 원하는 분량이나 학교 과목을 같이 적어 주세요.',
    '3. 리서치가 필요하면 웹 자료, 논문, 또는 둘 다 중 원하는 범위를 말해 주세요.',
  ].join('\n');
}

function wantsScholarlyResearch(text: string): boolean {
  return /논문|학술|선행\s*연구|저널|학회|kci|semantic\s*scholar|paper|scholar|doi/i.test(text);
}

function wantsLiveWebResearch(text: string): boolean {
  return /웹|웹리서치|인터넷|최신|최근|뉴스|기사|통계|자료|출처|근거|검색|사이트|공식|정책|web|internet|latest|news|source|evidence|data|statistics/i.test(
    text,
  );
}

function resolveWorkshopResearchDepth(text: string): WorkshopResearchDepth {
  return wantsScholarlyResearch(text) ? 'scholarly' : 'standard';
}

function resolveWorkshopResearchSource(text: string, advancedMode: boolean): ResearchSearchSource {
  if (wantsScholarlyResearch(text)) {
    return 'both';
  }
  if (wantsLiveWebResearch(text)) {
    return 'live_web';
  }
  return advancedMode ? 'live_web' : 'semantic';
}

function formatResearchSourceLabel(source: ResearchSearchSource): string {
  if (source === 'live_web') return '웹 자료';
  if (source === 'both') return '논문/학술 자료';
  if (source === 'kci') return 'KCI 논문';
  return '내부/학술 인덱스';
}

function buildResearchPendingMessage(sourceLabel: string): string {
  return `${sourceLabel}를 찾고 있어요. 검색 결과가 나오면 바로 문서에 반영할 수 있는 근거 카드로 정리해드릴게요.`;
}

function buildResearchResultMessage(candidateCount: number, sourceLabel: string): string {
  if (candidateCount > 0) {
    return `${sourceLabel} 후보 ${candidateCount}개를 찾았어요. 필요한 근거를 고르면 문서 반영 제안 카드로 바로 이어갈 수 있습니다.`;
  }
  return `${sourceLabel} 후보를 찾지 못했어요. 주제, 과목, 핵심 키워드를 조금 더 구체적으로 적어 주세요.`;
}

function buildResearchErrorMessage(message: string): string {
  return `자료 검색에 실패했어요.\n\n${message}\n\n잠시 후 다시 시도하거나 검색어를 더 구체적으로 바꿔 주세요.`;
}

function showReadableLimitedModeToast(reason: string | null): boolean {
  if (reason === 'llm_unavailable') {
    toast.error('Gemini 기반 AI 모델 연결이 불안정해 안전 안내 모드로 전환했어요.');
    return true;
  }
  if (reason === 'llm_not_configured') {
    toast.error('Gemini API 키 또는 LLM 서버 설정이 없어 안전 안내 모드로 전환했어요.');
    return true;
  }
  if (reason === 'llm_timeout') {
    toast.error('AI 응답이 시간 안에 도착하지 않아 안전 안내 모드로 전환했어요.');
    return true;
  }
  return false;
}

interface StreamFoliReplyResult {
  text: string;
  authSource: AuthTokenSource;
}

function normalizeStructuredDraftPatch(patch: unknown): WorkshopDraftPatchProposal | null {
  if (!patch || typeof patch !== 'object') return null;
  const p = patch as any;
  if (!p.content_markdown) return null;
  return {
    mode: p.mode || 'planning',
    block_id: p.block_id || 'body_section_1',
    heading: p.heading || null,
    content_markdown: String(p.content_markdown || ''),
    rationale: p.rationale || null,
    evidence_boundary_note: p.evidence_boundary_note || null,
    requires_approval: p.requires_approval ?? true,
  };
}

function extractPatchTagFromRaw(raw: string): { cleaned: string; patch: WorkshopDraftPatchProposal | null } {
  const markerPairs = [
    ['<workshop-patch>', '</workshop-patch>'],
    ['[DRAFT_PATCH]', '[/DRAFT_PATCH]'],
  ] as const;
  const pair = markerPairs.find(([start, end]) => raw.indexOf(start) !== -1 && raw.indexOf(end) > raw.indexOf(start));

  if (!pair) {
    return { cleaned: raw, patch: null };
  }

  const [markerStart, markerEnd] = pair;
  const startIdx = raw.indexOf(markerStart);
  const endIdx = raw.indexOf(markerEnd);
  const jsonStr = raw.slice(startIdx + markerStart.length, endIdx).trim();
  const cleaned = (raw.slice(0, startIdx) + raw.slice(endIdx + markerEnd.length)).trim();

  try {
    const rawPatch = JSON.parse(jsonStr);
    return { cleaned, patch: normalizeStructuredDraftPatch(rawPatch) };
  } catch (e) {
    console.error('Failed to parse patch JSON from stream:', e);
    return { cleaned: raw, patch: null };
  }
}

async function streamFoliReply(
  projectId: string | undefined,
  workshopId: string | undefined,
  text: string,
  documentContent: string,
  mode: WorkshopMode,
  structuredDraft: WorkshopStructuredDraftState,
  researchDepth: WorkshopResearchDepth,
  onToken: (token: string) => void,
  onMeta: (meta: ChatStreamMetaPayload) => void,
  onPatch: (patch: any) => void,
): Promise<StreamFoliReplyResult> {
  if (!workshopId) {
    throw new Error('Workshop chat session is not initialized.');
  }

  const chatPath = `/api/v1/workshops/${encodeURIComponent(workshopId)}/chat/stream`;
  const primaryBaseUrl = resolveApiBaseUrl();
  const sameOriginBaseUrl = resolveSameOriginApiBaseUrl();
  const endpointCandidates = [`${primaryBaseUrl}${chatPath}`];
  if (sameOriginBaseUrl && sameOriginBaseUrl !== primaryBaseUrl) {
    endpointCandidates.push(`${sameOriginBaseUrl}${chatPath}`);
  }

  try {
    const { endpoint, response, authSource } = await openChatEventStreamWithFallback({
      endpoints: endpointCandidates,
      firebaseUser: auth?.currentUser,
      payload: {
        project_id: projectId,
        workshop_id: workshopId,
        message: text,
        document_content: documentContent,
        mode,
        structured_draft: structuredDraft,
        response_depth: 'report_long',
        research_depth: researchDepth,
      },
    });

    const fullText = await consumeChatEventStream({
      endpoint,
      response,
      authSource,
      onDelta: onToken,
      onMeta: (meta) => {
        onMeta(meta);
        if ((meta as any).patch) {
          onPatch((meta as any).patch);
        }
      },
      onDraftPatch: onPatch,
    });

    return { text: fullText, authSource };
  } catch (err) {
    if (err instanceof ChatStreamError) {
      throw err;
    }
    throw err;
  }
}

function buildWorkshopEventsUrl(
  workshopId: string,
  streamToken: string,
  artifactId: string,
  advancedMode: boolean,
  ragSource: string,
) {
  const baseUrl = resolveApiBaseUrl() || (typeof window !== 'undefined' ? window.location.origin : 'http://localhost:8000');
  const url = new URL(`/api/v1/workshops/${encodeURIComponent(workshopId)}/events`, baseUrl);
  url.searchParams.set('stream_token', streamToken);
  url.searchParams.set('artifact_id', artifactId);
  url.searchParams.set('advanced_mode', advancedMode ? 'true' : 'false');
  url.searchParams.set('rag_source', ragSource);
  return url.toString();
}

function createDraftArtifactFromPayload(payload: WorkshopArtifactReadyPayload, fallbackArtifactId: string): DraftArtifact {
  const reportMarkdown = String(payload.report_markdown || '');
  const structuredDraft =
    payload.structured_draft || (reportMarkdown ? markdownToStructuredDraft(reportMarkdown, 'revision') : null);

  return {
    id: String(payload.artifact_id || fallbackArtifactId),
    report_markdown: reportMarkdown,
    visual_specs: Array.isArray(payload.visual_specs) ? payload.visual_specs : [],
    math_expressions: Array.isArray(payload.math_expressions) ? payload.math_expressions : [],
    evidence_map: payload.evidence_map && typeof payload.evidence_map === 'object' ? payload.evidence_map : {},
    structured_draft: structuredDraft,
    updated_at: new Date().toISOString(),
  };
}

function downloadMarkdownFile(filename: string, content: string) {
  const blob = new Blob([content], { type: 'text/markdown;charset=utf-8' });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement('a');
  anchor.href = url;
  anchor.download = filename.endsWith('.md') ? filename : `${filename}.md`;
  anchor.click();
  URL.revokeObjectURL(url);
}

function sanitizeArchiveFilename(title: string): string {
  return (title || '생기부_기반_탐구_보고서').replace(/[^\w\-\uAC00-\uD7A3]+/g, '_').replace(/^_+|_+$/g, '') || '생기부_기반_탐구_보고서';
}

function serializeWorkshopMessages(messages: Message[]): ArchiveItem['chatMessages'] {
  return messages
    .filter((message) => message.content.trim())
    .map((message) => ({
      id: message.id,
      role: message.role === 'user' ? 'user' : 'foli',
      content: message.content,
      createdAt: new Date().toISOString(),
    }));
}

function restoreMessagesFromArchive(item: ArchiveItem): Message[] {
  const savedMessages = item.chatMessages || [];
  if (savedMessages.length > 0) {
    return savedMessages.map((message) => ({
      id: message.id || crypto.randomUUID(),
      role: message.role === 'user' ? 'user' : 'foli',
      content: message.content || '',
    }));
  }

  return [
    {
      id: `archive-${item.id}-intro`,
      role: 'foli',
      content: '저장된 작업을 불러왔어요. 이어서 수정하거나 보고서 생성을 계속할 수 있습니다.',
    },
  ];
}

interface ConversationHistoryPanelProps {
  items: ArchiveItem[];
  activeId: string | null;
  disabled?: boolean;
  onNewChat: () => void;
  onResume: (item: ArchiveItem) => void;
}

function ConversationHistoryPanel({ items, activeId, disabled, onNewChat, onResume }: ConversationHistoryPanelProps) {
  return (
    <aside className="flex h-full w-full flex-col overflow-hidden rounded-[28px] border border-slate-200 bg-white/90 shadow-sm backdrop-blur">
      <div className="border-b border-slate-100 p-4">
        <button
          type="button"
          onClick={onNewChat}
          disabled={disabled}
          className="flex w-full items-center justify-center gap-2 rounded-2xl bg-slate-900 px-4 py-3 text-sm font-black text-white shadow-sm transition-all hover:bg-black disabled:opacity-50"
        >
          <Plus size={16} />
          새 채팅
        </button>
      </div>
      <div className="min-h-0 flex-1 overflow-y-auto p-3">
        <div className="mb-2 flex items-center gap-2 px-2 text-xs font-black uppercase tracking-wide text-slate-400">
          <MessageSquare size={14} />
          이전 대화
        </div>
        <div className="space-y-2">
          {items.length === 0 ? (
            <div className="rounded-2xl border border-dashed border-slate-200 p-4 text-sm font-semibold text-slate-500">
              저장된 워크숍 대화가 아직 없습니다.
            </div>
          ) : (
            items.map((item) => {
              const isActive = item.id === activeId;
              return (
                <button
                  key={item.id}
                  type="button"
                  onClick={() => onResume(item)}
                  disabled={disabled}
                  className={cn(
                    'w-full rounded-2xl border p-3 text-left transition-all disabled:opacity-50',
                    isActive
                      ? 'border-indigo-200 bg-indigo-50 text-indigo-900 shadow-sm'
                      : 'border-slate-100 bg-white text-slate-700 hover:border-indigo-200 hover:bg-slate-50',
                  )}
                >
                  <div className="line-clamp-2 text-sm font-black leading-snug">{item.title}</div>
                  <div className="mt-1 flex items-center justify-between gap-2 text-[11px] font-bold text-slate-400">
                    <span className="truncate">{item.subject || '탐구'}</span>
                    <span className="shrink-0">{new Date(item.updatedAt || item.createdAt).toLocaleDateString('ko-KR')}</span>
                  </div>
                </button>
              );
            })
          )}
        </div>
      </div>
    </aside>
  );
}

interface WritingPlannerPanelProps {
  areaId: RecordAreaId;
  onAreaChange: (areaId: RecordAreaId) => void;
  detail: string;
  onDetailChange: (value: string) => void;
  gradeId: WritingGradeId;
  onGradeChange: (gradeId: WritingGradeId) => void;
  inferredGrade: string;
  gradeLabel: string;
  candidates: WritingCandidate[];
  selectedCandidateId: string | null;
  onCandidateSelect: (candidateId: string) => void;
  preference: string;
  onPreferenceChange: (value: string) => void;
  aiAutoSelect: boolean;
  onAutoSelectChange: (value: boolean) => void;
  onStart: () => void;
  disabled: boolean;
}

function WritingPlannerPanel({
  areaId,
  onAreaChange,
  detail,
  onDetailChange,
  gradeId,
  onGradeChange,
  inferredGrade,
  gradeLabel,
  candidates,
  selectedCandidateId,
  onCandidateSelect,
  preference,
  onPreferenceChange,
  aiAutoSelect,
  onAutoSelectChange,
  onStart,
  disabled,
}: WritingPlannerPanelProps) {
  const activeArea = resolveRecordAreaOption(areaId);
  const selectedCandidate = aiAutoSelect ? candidates[0] : candidates.find((item) => item.id === selectedCandidateId) || candidates[0];

  return (
    <SurfaceCard className="border-slate-200 bg-white/95 p-4 shadow-sm">
      <div className="flex flex-col gap-4">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <p className="inline-flex items-center gap-2 text-xs font-black uppercase tracking-wide text-indigo-600">
              <Sparkles size={14} />
              문서작성 설정
            </p>
            <h3 className="mt-1 text-lg font-black text-slate-900">생기부 근거로 먼저 방향을 고릅니다</h3>
          </div>
          <button
            type="button"
            onClick={() => onAutoSelectChange(!aiAutoSelect)}
            className={cn(
              'inline-flex min-h-10 items-center gap-2 rounded-2xl border px-3 py-2 text-xs font-black transition-all',
              aiAutoSelect
                ? 'border-indigo-200 bg-indigo-50 text-indigo-700'
                : 'border-slate-200 bg-white text-slate-600 hover:border-indigo-200 hover:text-indigo-700',
            )}
          >
            <Wand2 size={15} />
            AI 자동 선택 {aiAutoSelect ? 'ON' : 'OFF'}
          </button>
        </div>

        <div className="grid gap-3 lg:grid-cols-[1.1fr_0.9fr]">
          <div className="space-y-3">
            <div className="grid gap-2 sm:grid-cols-2">
              {RECORD_AREA_OPTIONS.map((option) => {
                const selected = option.id === areaId;
                return (
                  <button
                    key={option.id}
                    type="button"
                    onClick={() => onAreaChange(option.id)}
                    className={cn(
                      'min-h-[76px] rounded-2xl border p-3 text-left transition-all',
                      selected
                        ? 'border-indigo-400 bg-indigo-50 text-indigo-800 shadow-sm'
                        : 'border-slate-200 bg-white text-slate-700 hover:border-indigo-200 hover:bg-slate-50',
                    )}
                  >
                    <span className="flex items-center justify-between gap-2">
                      <span className="text-sm font-black">{option.label}</span>
                      {selected ? <CheckCircle2 size={16} className="text-indigo-600" /> : null}
                    </span>
                    <span className="mt-1 block text-xs font-semibold leading-5 text-slate-500">{option.description}</span>
                  </button>
                );
              })}
            </div>

            <input
              value={detail}
              onChange={(event) => onDetailChange(event.target.value)}
              placeholder={activeArea.detailPlaceholder}
              className="h-12 w-full rounded-2xl border border-slate-200 bg-white px-4 text-sm font-bold text-slate-800 outline-none transition focus:border-indigo-300 focus:ring-4 focus:ring-indigo-50"
            />
          </div>

          <div className="space-y-3">
            <div>
              <p className="mb-2 flex items-center gap-2 text-xs font-black text-slate-600">
                <GraduationCap size={15} className="text-indigo-500" />
                학년 반영
                <span className="rounded-full bg-slate-100 px-2 py-0.5 text-[11px] text-slate-500">추천 {inferredGrade}</span>
              </p>
              <div className="flex flex-wrap gap-2">
                {WRITING_GRADE_OPTIONS.map((option) => {
                  const selected = option.id === gradeId;
                  return (
                    <button
                      key={option.id}
                      type="button"
                      title={option.description}
                      onClick={() => onGradeChange(option.id)}
                      className={cn(
                        'rounded-full border px-3 py-1.5 text-xs font-black transition-all',
                        selected
                          ? 'border-slate-900 bg-slate-900 text-white'
                          : 'border-slate-200 bg-white text-slate-600 hover:border-indigo-200 hover:text-indigo-700',
                      )}
                    >
                      {option.id === 'auto' ? `${option.label}(${gradeLabel})` : option.label}
                    </button>
                  );
                })}
              </div>
            </div>

            <label className="block">
              <span className="mb-2 flex items-center gap-2 text-xs font-black text-slate-600">
                <MessageSquare size={15} className="text-indigo-500" />
                학생 선호와 생각
              </span>
              <textarea
                value={preference}
                onChange={(event) => onPreferenceChange(event.target.value)}
                placeholder="예: 너무 어려운 주제는 싫어요. 실험보다 자료 분석이 좋아요. 느낀 점은 진솔하게 쓰고 싶어요."
                rows={4}
                className="w-full resize-none rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm font-semibold leading-6 text-slate-800 outline-none transition focus:border-indigo-300 focus:ring-4 focus:ring-indigo-50"
              />
            </label>
          </div>
        </div>

        <div>
          <div className="mb-2 flex items-center justify-between gap-3">
            <p className="flex items-center gap-2 text-xs font-black text-slate-600">
              <Target size={15} className="text-indigo-500" />
              생기부 기반 후보
            </p>
            <span className="text-[11px] font-bold text-slate-400">선택 후보: {selectedCandidate?.title || '없음'}</span>
          </div>
          <div className="grid gap-3 lg:grid-cols-3">
            {candidates.map((candidate) => {
              const selected = aiAutoSelect ? candidate.id === candidates[0]?.id : candidate.id === selectedCandidate?.id;
              return (
                <button
                  key={candidate.id}
                  type="button"
                  onClick={() => {
                    onAutoSelectChange(false);
                    onCandidateSelect(candidate.id);
                  }}
                  className={cn(
                    'min-h-[188px] rounded-2xl border p-4 text-left transition-all',
                    selected
                      ? 'border-indigo-400 bg-indigo-50 shadow-sm'
                      : 'border-slate-200 bg-white hover:border-indigo-200 hover:bg-slate-50',
                  )}
                >
                  <span className="flex items-start justify-between gap-2">
                    <span className="text-sm font-black leading-5 text-slate-900">{candidate.title}</span>
                    {selected ? <CheckCircle2 size={17} className="shrink-0 text-indigo-600" /> : null}
                  </span>
                  <span className="mt-2 block text-xs font-bold text-indigo-700">{candidate.areaLabel}</span>
                  <span className="mt-2 block text-xs font-semibold leading-5 text-slate-600">{candidate.reason}</span>
                  <span className="mt-3 block rounded-xl bg-white/80 px-3 py-2 text-[11px] font-semibold leading-5 text-slate-500">
                    {candidate.source}: {candidate.evidence}
                  </span>
                </button>
              );
            })}
          </div>
        </div>

        <div className="flex flex-col gap-3 rounded-2xl border border-slate-100 bg-slate-50 px-4 py-3 sm:flex-row sm:items-center sm:justify-between">
          <p className="text-xs font-semibold leading-5 text-slate-600">
            {selectedCandidate?.gradeFit || '학년 정보를 반영해 후보를 정리합니다.'}
          </p>
          <PrimaryButton
            type="button"
            size="sm"
            onClick={onStart}
            disabled={disabled || !selectedCandidate}
            className="min-h-10 shrink-0 rounded-2xl px-4 text-xs font-black"
          >
            <PenSquare size={15} className="mr-1.5" />
            이 후보로 서론 시작
          </PrimaryButton>
        </div>
      </div>
    </SurfaceCard>
  );
}

interface DraftAccumulationPanelProps {
  steps: AccumulationStep[];
  structuredDraft: WorkshopStructuredDraftState;
  activeStepId: string | null;
  completedStepId: string | null;
  onStepRequest: (step: AccumulationStep) => void;
  onNextStep: (step: AccumulationStep) => void;
  disabled: boolean;
}

function DraftAccumulationPanel({
  steps,
  structuredDraft,
  activeStepId,
  completedStepId,
  onStepRequest,
  onNextStep,
  disabled,
}: DraftAccumulationPanelProps) {
  const activeStep = getAccumulationStepById(activeStepId) || steps[0] || null;
  const completedStep = getAccumulationStepById(completedStepId);
  const nextStep = completedStep ? getNextAccumulationStep(completedStep) : null;

  return (
    <SurfaceCard className="border-slate-200 bg-white/95 p-4 shadow-sm">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <p className="inline-flex items-center gap-2 text-xs font-black uppercase tracking-wide text-indigo-600">
            <Layers size={14} />
            적립식 작성
          </p>
          <h3 className="mt-1 text-base font-black text-slate-900">서론부터 출처까지 한 칸씩 쌓기</h3>
        </div>
        <span className="rounded-full bg-slate-100 px-3 py-1 text-[11px] font-black text-slate-500">API 부담 완화용 섹션 생성</span>
      </div>
      <div className="mt-4 flex flex-col gap-3 rounded-2xl border border-slate-100 bg-slate-50 p-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <p className="text-[11px] font-black uppercase tracking-wide text-slate-400">현재 작성 단계</p>
          <p className="mt-1 text-sm font-black text-slate-900">
            {completedStep && nextStep
              ? `${completedStep.label} 반영 완료`
              : activeStep
                ? `${activeStep.label} 작성 중`
                : '단계 준비 중'}
          </p>
          <p className="mt-1 text-xs font-semibold leading-5 text-slate-500">
            {completedStep && nextStep
              ? '내용을 확인했다면 다음 단계로 넘어가 본론 대화를 이어갈 수 있습니다.'
              : activeStep?.description || '서론부터 순서대로 한 칸씩 쌓습니다.'}
          </p>
        </div>
        {completedStep && nextStep ? (
          <PrimaryButton
            type="button"
            size="sm"
            onClick={() => onNextStep(nextStep)}
            disabled={disabled}
            className="min-h-10 shrink-0 rounded-2xl px-4 text-xs font-black"
          >
            <ChevronDown size={15} className="mr-1.5 -rotate-90" />
            다음 단계: {nextStep.label}
          </PrimaryButton>
        ) : null}
      </div>
      <div className="mt-4 grid gap-2 md:grid-cols-2 xl:grid-cols-4">
        {steps.map((step) => {
          const isDone = isAccumulationStepComplete(step, structuredDraft);
          const isActive = step.id === activeStepId;
          return (
            <button
              key={step.id}
              type="button"
              onClick={() => onStepRequest(step)}
              disabled={disabled}
              className={cn(
                'min-h-[92px] rounded-2xl border p-3 text-left transition-all disabled:opacity-50',
                isActive
                  ? 'border-indigo-300 bg-indigo-50 text-indigo-900 shadow-sm'
                  : isDone
                  ? 'border-emerald-200 bg-emerald-50 text-emerald-800'
                  : 'border-slate-200 bg-white text-slate-700 hover:border-indigo-200 hover:bg-slate-50',
              )}
            >
              <span className="flex items-center justify-between gap-2">
                <span className="text-sm font-black">{step.label}</span>
                {isDone ? <CheckCircle2 size={16} /> : <PenSquare size={15} className={isActive ? 'text-indigo-500' : 'text-slate-400'} />}
              </span>
              <span className="mt-1 block text-xs font-semibold leading-5 text-slate-500">{step.description}</span>
              <span className="mt-2 inline-flex rounded-full bg-white/80 px-2 py-0.5 text-[11px] font-black text-slate-500">
                {isActive ? '진행 중' : isDone ? '보강' : '작성'}
              </span>
            </button>
          );
        })}
      </div>
    </SurfaceCard>
  );
}

interface ChatBubbleProps {
  message: Message;
  onApplyDraftPatch: (patch: WorkshopDraftPatchProposal) => void | Promise<void>;
  onRejectDraftPatch: (messageId: string) => void;
  onRequestDraftPatchRewrite: (patch: WorkshopDraftPatchProposal, tone: 'simpler' | 'professional' | 'custom') => void;
  onGuidedChoiceSelect: (groupId: string, option: GuidedChoiceOption, message: Message) => void;
  isGuidedActionLoading?: boolean;
  selectingTopicId?: string | null;
}

const ChatBubble = memo(function ChatBubble({
  message,
  onApplyDraftPatch,
  onRejectDraftPatch,
  onRequestDraftPatchRewrite,
  onGuidedChoiceSelect,
  isGuidedActionLoading,
  selectingTopicId,
}: ChatBubbleProps) {
  const isUser = message.role === 'user';
  const isStreaming = !!(message as any).isStreaming;
  const topicSuggestions = message.topicSuggestions || [];

  const interactiveGroups = useMemo(() => {
    let groups = message.choiceGroups || [];
    if (message.phase === 'topic_selection' && topicSuggestions.length > 0 && groups.length === 0) {
      groups = [
        {
          id: 'topic-selection',
          title: '이 중에서 가장 마음에 드는 주제를 골라주세요.',
          style: 'cards',
          options: topicSuggestions.map((topic) => ({
            id: topic.id,
            label: topic.title,
            description: topic.why_fit_student,
            value: topic.id,
          })),
        },
      ];
    }
    return groups;
  }, [message.choiceGroups, message.phase, topicSuggestions]);

  const reportPatch = useMemo<ReportPatch | null>(
    () => (message.draftPatch ? convertWorkshopDraftPatchToReportPatch(message.draftPatch) : null),
    [message.draftPatch],
  );

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      className={cn('flex w-full px-2', isUser ? 'justify-end' : 'justify-start')}
    >
      <div
        className={cn(
          'max-w-[92%] rounded-2xl border px-4 py-3 shadow-sm',
          isUser
            ? 'border-indigo-600 bg-indigo-600 text-white shadow-indigo-200/40'
            : 'border-slate-100 bg-white text-slate-900',
        )}
      >
        <div className={cn("mb-2 flex items-center gap-2 text-[11px] font-black uppercase tracking-wider", isUser ? "text-indigo-100" : "text-indigo-600")}>
          {isUser ? <User size={12} /> : <Bot size={12} />}
          <span>{isUser ? 'ME' : 'UNIFOLI'}</span>
        </div>

        {isStreaming ? (
          <div className="flex items-center gap-2 text-sm font-medium py-1">
            <Loader2 size={14} className="animate-spin" />
            <span>분석하고 있어요...</span>
          </div>
        ) : message.content ? (
          <MemoizedMarkdown content={message.content} role={message.role} />
        ) : null}

        {message.draftPatch && reportPatch ? (
          <PatchReviewCard
            className="mt-4"
            patch={reportPatch}
            onApply={() => void onApplyDraftPatch(message.draftPatch!)}
            onReject={() => onRejectDraftPatch(message.id)}
            onRequestRewrite={(_, tone) => onRequestDraftPatchRewrite(message.draftPatch!, tone)}
          />
        ) : null}

        {false && message.draftPatch ? (
          <div className="mt-4 rounded-xl border border-indigo-100 bg-indigo-50/50 p-3 shadow-inner">
            <p className="text-xs font-bold text-slate-600 mb-3 flex items-center gap-2">
              <span className="inline-flex h-4 w-4 items-center justify-center rounded bg-indigo-600 text-[10px] text-white shadow-sm">AI</span>
              보고서 구성 제안이 도착했어요.
            </p>
            <PrimaryButton
              size="sm"
              className="w-full text-xs py-2 h-auto rounded-lg"
              onClick={() => onApplyDraftPatch(message.draftPatch!)}
            >
              제안 내용을 문서에 반영하기
            </PrimaryButton>
          </div>
        ) : null}

        {interactiveGroups.length > 0 && (
          <div className="mt-4 space-y-3">
            {interactiveGroups.map((group) => (
              <div key={group.id} className="rounded-xl border border-slate-100 bg-slate-50/50 p-3">
                <p className="text-[11px] font-black text-indigo-600/70 mb-2">{group.title}</p>
                <div
                  className={cn(
                    'grid gap-2',
                    group.style === 'chips' ? 'flex flex-wrap gap-2' : 'grid-cols-1',
                    group.style === 'buttons' ? 'sm:grid-cols-2' : null,
                    group.id === 'topic-selection' && group.options.length > 24 ? 'max-h-[520px] overflow-y-auto pr-1' : null,
                  )}
                >
                  {group.options.map((option) => {
                    const optionValue = String(option.value || option.id);
                    const isBusyTopic = group.id === 'topic-selection' && selectingTopicId === optionValue;
                    const disabled = isGuidedActionLoading || isBusyTopic;
                    
                    if (group.style === 'chips') {
                      return (
                        <button
                          key={`${group.id}:${option.id}`}
                          type="button"
                          onClick={() => onGuidedChoiceSelect(group.id, option, message)}
                          disabled={disabled}
                          className="rounded-full border border-slate-200 bg-white px-3 py-1.5 text-xs font-bold text-slate-700 transition-all hover:border-indigo-400 hover:text-indigo-600 hover:bg-white disabled:opacity-50"
                        >
                          {option.label}
                        </button>
                      );
                    }

                    return (
                      <button
                        key={`${group.id}:${option.id}`}
                        type="button"
                        onClick={() => onGuidedChoiceSelect(group.id, option, message)}
                        disabled={disabled}
                        className="w-full rounded-xl border border-slate-100 bg-white p-3 text-left transition-all hover:border-indigo-400 hover:shadow-md disabled:opacity-50 group/opt"
                      >
                        <div className="flex justify-between items-start gap-2">
                          <p className="text-sm font-black text-slate-800 group-hover/opt:text-indigo-600">
                            {option.label}
                          </p>
                        </div>
                        {option.description && (
                          <p className="mt-1 text-xs font-medium text-slate-500 leading-relaxed">{option.description}</p>
                        )}
                      </button>
                    );
                  })}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </motion.div>
  );
});

interface WorkshopLocationState {
  major?: string;
  chatbotMode?: ChatbotMode;
  fromDiagnosis?: boolean;
  diagnosisRunId?: string | null;
}

function readStoredWorkshopProjectId(): string | null {
  if (typeof window === 'undefined') return null;
  try {
    const raw = window.localStorage.getItem(DIAGNOSIS_STORAGE_KEY);
    if (!raw) return null;
    const stored = JSON.parse(raw) as Partial<StoredDiagnosis>;
    const projectId = typeof stored.projectId === 'string' ? stored.projectId.trim() : '';
    return projectId || null;
  } catch {
    return null;
  }
}

export function Workshop() {
  const navigate = useNavigate();
  const { projectId } = useParams<{ projectId: string }>();
  const location = useLocation();
  const workshopLocationState = (location.state as WorkshopLocationState | null) ?? null;
  const archiveResumeId = useMemo(() => new URLSearchParams(location.search).get('archiveId'), [location.search]);
  const storedWorkshopProjectId = useMemo(() => readStoredWorkshopProjectId(), []);
  const requestedChatbotMode = useMemo(
    () =>
      resolveChatbotModeFromRouteContext({
        pathname: location.pathname,
        routeState: location.state,
      }),
    [location.pathname, location.state],
  );

  const [workshopState, setWorkshopState] = useState<WorkshopStateResponse | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [isTyping, setIsTyping] = useState(false);
  const [isSessionLoading, setIsSessionLoading] = useState(true);
  const [documentContent, setDocumentContent] = useState('');
  const [qualityLevel, setQualityLevel] = useState<QualityLevel>('mid');
  const [advancedMode, setAdvancedMode] = useState(false);
  const [renderArtifact, setRenderArtifact] = useState<DraftArtifact | null>(null);
  const [latestDraftUpdatedAt, setLatestDraftUpdatedAt] = useState<string | null>(null);
  const [isDraftOutOfSync, setIsDraftOutOfSync] = useState(false);
  const [lastLocalSnapshotAt, setLastLocalSnapshotAt] = useState<string | null>(null);
  const [activeArchiveId, setActiveArchiveId] = useState<string | null>(archiveResumeId);
  const [archivePanelRefreshKey, setArchivePanelRefreshKey] = useState(0);
  const [workshopMode, setWorkshopMode] = useState<WorkshopMode>('planning');
  const [showDraftControls, setShowDraftControls] = useState(false);
  const [showAdvancedTools, setShowAdvancedTools] = useState(false);
  const [structuredDraft, setStructuredDraft] = useState<WorkshopStructuredDraftState>(() =>
    createEmptyStructuredDraft('planning'),
  );
  const [pendingDraftPatch, setPendingDraftPatch] = useState<WorkshopDraftPatchProposal | null>(null);

  const [diagnosisReport, setDiagnosisReport] = useState<Record<string, unknown> | null>(null);
  const [showDiagnosis, setShowDiagnosis] = useState(false);
  const [isRendering, setIsRendering] = useState(false);
  const [renderProgressMessage, setRenderProgressMessage] = useState<string | null>(null);
  const [guidedSubject, setGuidedSubject] = useState<string | null>(null);
  const [guidedSuggestions, setGuidedSuggestions] = useState<GuidedTopicSuggestion[]>([]);
  const [guidedPhase, setGuidedPhase] = useState<GuidedConversationPhase>('subject_input');
  const [guidedPageRanges, setGuidedPageRanges] = useState<GuidedTopicSelectionResponse['recommended_page_ranges']>([]);
  const [guidedStructureOptions, setGuidedStructureOptions] = useState<GuidedStructureOption[]>([]);
  const [guidedNextActionOptions, setGuidedNextActionOptions] = useState<GuidedChoiceOption[]>([]);
  const [isGuidedTopicSelected, setIsGuidedTopicSelected] = useState(false);
  const [isSelectingGuidedTopicId, setIsSelectingGuidedTopicId] = useState<string | null>(null);
  const [isGuidedActionLoading, setIsGuidedActionLoading] = useState(false);
  const [chatbotMode, setChatbotMode] = useState<ChatbotMode>(requestedChatbotMode);
  const [chatMeta, setChatMeta] = useState<ChatStreamMetaPayload | null>(null);
  const [mobileView, setMobileView] = useState<'chat' | 'draft'>('chat');
  const [isEditorOpen, setIsEditorOpen] = useState(false);
  const [writingAreaId, setWritingAreaId] = useState<RecordAreaId>('subject_specialty');
  const [writingDetail, setWritingDetail] = useState('');
  const [writingGradeId, setWritingGradeId] = useState<WritingGradeId>('auto');
  const [writingPreference, setWritingPreference] = useState('');
  const [aiAutoSelectWriting, setAiAutoSelectWriting] = useState(true);
  const [selectedWritingCandidateId, setSelectedWritingCandidateId] = useState<string | null>(null);
  const [activeAccumulationStepId, setActiveAccumulationStepId] = useState<string>(ACCUMULATION_STEPS[0].id);
  const [completedAccumulationStepId, setCompletedAccumulationStepId] = useState<string | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const editorRef = useRef<TiptapEditorHandle | null>(null);
  const reportDocumentState = useMemo(() => structuredDraftToReportDocumentState(structuredDraft), [structuredDraft]);
  const editorBridge = useEditorBridge({
    editorRef,
    documentState: reportDocumentState,
    structuredDraft,
    setStructuredDraft,
  });
  const documentPatch = useDocumentPatch({
    getEditorAdapter: editorBridge.getEditorAdapter,
    structuredDraft,
    documentState: reportDocumentState,
  });

  const questStart = useMemo(() => readQuestStart(), []);
  const initialMajor = useMemo(() => workshopLocationState?.major || '미정', [workshopLocationState]);
  const preferredDiagnosisRunId = workshopLocationState?.diagnosisRunId ?? null;
  const openedFromDiagnosis = workshopLocationState?.fromDiagnosis === true;
  const isProjectBacked = Boolean(projectId && projectId !== 'demo');
  const shouldRedirectToStoredProject = !archiveResumeId && !isProjectBacked && Boolean(storedWorkshopProjectId);
  const guidedProjectId = isProjectBacked ? projectId ?? null : null;
  const reportDownloadContent = useMemo(
    () => (renderArtifact?.report_markdown || documentContent || '').trim(),
    [documentContent, renderArtifact?.report_markdown],
  );
  const inferredWorkshopTitle = useMemo(
    () =>
      deriveArchiveTitle({
        contentMarkdown: reportDownloadContent || structuredDraftToMarkdown(structuredDraft),
        structuredDraft,
        fallbackTitle: questStart?.title || guidedSubject || initialMajor,
        subject: initialMajor || guidedSubject || '탐구',
      }),
    [guidedSubject, initialMajor, questStart?.title, reportDownloadContent, structuredDraft],
  );
  const fileName = useMemo(() => `${sanitizeArchiveFilename(inferredWorkshopTitle)}.hwpx`, [inferredWorkshopTitle]);
  const storedDiagnosisSnapshot = useMemo(() => readStoredDiagnosisSnapshot(), []);
  const activeDiagnosisPayload = useMemo(
    () =>
      toDiagnosisPayloadRecord(diagnosisReport) ||
      toDiagnosisPayloadRecord(storedDiagnosisSnapshot?.diagnosis) ||
      null,
    [diagnosisReport, storedDiagnosisSnapshot],
  );
  const inferredWritingGrade = useMemo(
    () => inferGradeFromDiagnosisPayload(activeDiagnosisPayload),
    [activeDiagnosisPayload],
  );
  const resolvedWritingGradeLabel = useMemo(
    () => resolveWritingGradeLabel(writingGradeId, inferredWritingGrade),
    [inferredWritingGrade, writingGradeId],
  );
  const targetMajorForWriting = useMemo(
    () =>
      asCleanText(workshopLocationState?.major) ||
      asCleanText(storedDiagnosisSnapshot?.targetMajor) ||
      asCleanText(storedDiagnosisSnapshot?.target_major) ||
      asCleanText(storedDiagnosisSnapshot?.major) ||
      (initialMajor === '미정' ? '목표 전공' : initialMajor) ||
      '목표 전공',
    [initialMajor, storedDiagnosisSnapshot, workshopLocationState?.major],
  );
  const writingAreaOption = useMemo(() => resolveRecordAreaOption(writingAreaId), [writingAreaId]);
  const writingCandidates = useMemo(
    () =>
      buildWritingCandidates({
        payload: activeDiagnosisPayload,
        areaId: writingAreaId,
        detail: writingDetail,
        gradeLabel: resolvedWritingGradeLabel,
        targetMajor: targetMajorForWriting,
        fallbackTopic: questStart?.title || null,
      }),
    [activeDiagnosisPayload, questStart?.title, resolvedWritingGradeLabel, targetMajorForWriting, writingAreaId, writingDetail],
  );
  const selectedWritingCandidate = useMemo(
    () =>
      aiAutoSelectWriting
        ? writingCandidates[0] || null
        : writingCandidates.find((candidate) => candidate.id === selectedWritingCandidateId) || writingCandidates[0] || null,
    [aiAutoSelectWriting, selectedWritingCandidateId, writingCandidates],
  );
  const archivedConversations = useMemo(
    () =>
      listArchiveItems()
        .filter((item) => item.kind === 'workshop' || Boolean(item.workshopId) || Boolean(item.chatMessages?.length))
        .slice(0, 30),
    [archivePanelRefreshKey, lastLocalSnapshotAt],
  );
  const researchCandidates = useResearchCandidates({
    projectId: guidedProjectId,
    selectedTopic: guidedSubject || questStart?.title || null,
    selectedOutline: structuredDraftToMarkdown(structuredDraft),
    reportDocumentState,
    formatProfile: reportDocumentState.formatProfile,
    existingSources: reportDocumentState.sources,
  });

  const initWorkshop = useCallback(async () => {
    setIsSessionLoading(true);
    setGuidedSubject(null);
    setGuidedSuggestions([]);
    setGuidedPhase('subject_input');
    setGuidedPageRanges([]);
    setGuidedStructureOptions([]);
    setGuidedNextActionOptions([]);
    setIsGuidedTopicSelected(false);
    setIsSelectingGuidedTopicId(null);
    setIsGuidedActionLoading(false);
    setChatMeta(null);
    setLatestDraftUpdatedAt(null);
    setLastLocalSnapshotAt(null);
    setIsDraftOutOfSync(false);
    setPendingDraftPatch(null);
    setShowDraftControls(false);
    setShowAdvancedTools(false);
    setWorkshopMode('planning');
    setChatbotMode(requestedChatbotMode);
    setStructuredDraft(createEmptyStructuredDraft('planning'));
    setDiagnosisReport(null);
    setShowDiagnosis(false);
    try {
      const archivedResume = archiveResumeId ? getArchiveItem(archiveResumeId) : null;
      const sessions = await api.get<WorkshopSessionResponse[]>(`/api/v1/workshops?project_id=${projectId}`);
      const active = sessions.find(session => session.status !== 'completed');
      const preferredQuality = localStorage.getItem('uni_foli_quality_level');
      const createQuality: QualityLevel =
        preferredQuality === 'low' || preferredQuality === 'mid' || preferredQuality === 'high'
          ? preferredQuality
          : 'mid';
      const state = archivedResume?.workshopId
        ? await api.get<WorkshopStateResponse>(`/api/v1/workshops/${archivedResume.workshopId}`)
        : active
          ? await api.get<WorkshopStateResponse>(`/api/v1/workshops/${active.id}`)
          : await api.post<WorkshopStateResponse>('/api/v1/workshops', { project_id: projectId, quality_level: createQuality });

      setWorkshopState(state);
      setQualityLevel(state.session.quality_level);
      setActiveArchiveId(archiveResumeId || `workshop-${state.session.id}`);

      let latestDiagnosisRun: DiagnosisRunResponse | null = null;
      if (isProjectBacked && preferredDiagnosisRunId) {
        try {
          const run = await api.get<DiagnosisRunResponse>(`/api/v1/diagnosis/${preferredDiagnosisRunId}`);
          if (!projectId || run.project_id === projectId) {
            latestDiagnosisRun = run;
          }
        } catch {
          latestDiagnosisRun = null;
        }
      }
      if (!latestDiagnosisRun && isProjectBacked && projectId) {
        try {
          latestDiagnosisRun = await api.get<DiagnosisRunResponse>(`/api/v1/diagnosis/project/${projectId}/latest`);
        } catch {
          latestDiagnosisRun = null;
        }
      }
      if (latestDiagnosisRun?.result_payload) {
        setDiagnosisReport(latestDiagnosisRun.result_payload as unknown as Record<string, unknown>);
        setShowDiagnosis(true);
      }

      const diagnosisStarter = buildDiagnosisChatStarter(latestDiagnosisRun?.result_payload);
      setChatbotMode(diagnosisStarter ? 'diagnosis' : requestedChatbotMode);

      if (state.latest_artifact) {
        setRenderArtifact(state.latest_artifact);
        const fromArtifact =
          normalizeStructuredDraft(
            state.latest_artifact.structured_draft ||
              state.latest_artifact.evidence_map?.coauthoring?.structured_draft,
          ) ||
          markdownToStructuredDraft(String(state.latest_artifact.report_markdown || ''), 'planning');
        setStructuredDraft(fromArtifact);
        setWorkshopMode(fromArtifact.mode);
        setDocumentContent(structuredDraftToMarkdown(fromArtifact));
        setActiveAccumulationStepId(inferCurrentAccumulationStepId(fromArtifact));
        setCompletedAccumulationStepId(null);
        setLatestDraftUpdatedAt(state.latest_artifact.updated_at ?? null);
        setIsDraftOutOfSync(false);
      }

      if (archivedResume) {
        const restoredStructured =
          normalizeStructuredDraft(archivedResume.structuredDraft, 'revision') ||
          markdownToStructuredDraft(resolveArchiveDownloadContent(archivedResume) || '', 'revision');
        setStructuredDraft(restoredStructured);
        setWorkshopMode(restoredStructured.mode);
        setDocumentContent(resolveArchiveDownloadContent(archivedResume) || structuredDraftToMarkdown(restoredStructured));
        setMessages(restoreMessagesFromArchive(archivedResume));
        setActiveAccumulationStepId(inferCurrentAccumulationStepId(restoredStructured));
        setCompletedAccumulationStepId(null);
        setLatestDraftUpdatedAt(archivedResume.updatedAt || archivedResume.createdAt);
        setLastLocalSnapshotAt(archivedResume.updatedAt || archivedResume.createdAt);
        setActiveArchiveId(archivedResume.id);
        setGuidedPhase('freeform_coauthoring');
        setIsGuidedTopicSelected(true);
        return;
      }

      const turns = state.session.turns || [];
      const loadedMessages: Message[] = [];
      turns.forEach(turn => {
        const role: MessageRole = (turn.speaker_role === 'assistant' || turn.speaker_role === 'bot') ? 'foli' : 'user';
        const content = (role === 'foli' ? (turn.response || turn.query) : turn.query) || '';
        const draftPatch = normalizeStructuredDraftPatch(turn.action_payload?.draft_patch);
        
        if (role === 'foli') {
          loadedMessages.push({ id: turn.id, role: 'foli', content, draftPatch: draftPatch || undefined });
        } else {
          loadedMessages.push({ id: turn.id, role: 'user', content });
          if (turn.response) {
            loadedMessages.push({ id: `${turn.id}-A`, role: 'foli', content: turn.response });
          }
        }
      });

      if (loadedMessages.length) {
        if (openedFromDiagnosis && diagnosisStarter) {
          loadedMessages.push({
            id: `diagnosis-starter-${latestDiagnosisRun?.id ?? 'latest'}`,
            role: 'foli',
            content: diagnosisStarter.briefing,
            phase: 'freeform_coauthoring',
            choiceGroups: [diagnosisStarter.quickActionGroup],
          });
        }
        setMessages(loadedMessages);
        setGuidedPhase('freeform_coauthoring');
        setIsGuidedTopicSelected(true);
      } else if (diagnosisStarter) {
        setGuidedPhase('freeform_coauthoring');
        setIsGuidedTopicSelected(true);
        setMessages([
          {
            id: 'diagnosis-starter',
            role: 'foli',
            content: diagnosisStarter.briefing,
            phase: 'freeform_coauthoring',
            choiceGroups: [diagnosisStarter.quickActionGroup],
          },
        ]);
      } else {
        try {
          const guidedStart = await api.post<GuidedChatStartResponse>('/api/v1/guided-chat/start', {
            project_id: projectId,
          });
          const greeting = ((guidedStart?.greeting || GUIDED_CHAT_GREETING) ?? '').trim();
          const stateSummary = guidedStart.state_summary || {};
          const resolvedPhase = guidedStart.phase || inferGuidedPhase(stateSummary);
          const greetingMessage = formatAssistantMessageWithEvidenceNote(
            guidedStart.assistant_message || greeting,
            guidedStart.evidence_gap_note,
          );

          const cachedStarter =
            typeof stateSummary.starter_draft_markdown === 'string' && stateSummary.starter_draft_markdown.trim()
              ? stateSummary.starter_draft_markdown
              : null;
          const cachedSubject =
            typeof stateSummary.subject === 'string' && stateSummary.subject.trim()
              ? stateSummary.subject
              : null;
          const cachedSuggestions = Array.isArray(stateSummary.suggestions)
            ? normalizeGuidedSuggestions({
                greeting,
                subject: cachedSubject || '탐구',
                suggestions: stateSummary.suggestions as GuidedTopicSuggestion[],
                evidence_gap_note: guidedStart.evidence_gap_note,
              })
            : [];
          const cachedPageRanges = Array.isArray(stateSummary.recommended_page_ranges)
            ? (stateSummary.recommended_page_ranges as GuidedTopicSelectionResponse['recommended_page_ranges'])
            : [];
          const cachedStructureOptions = Array.isArray(stateSummary.structure_options)
            ? (stateSummary.structure_options as GuidedStructureOption[])
            : [];
          const cachedNextActionOptions = Array.isArray(stateSummary.next_action_options)
            ? (stateSummary.next_action_options as GuidedChoiceOption[])
            : [];

          const restoredChoiceGroups =
            guidedStart.choice_groups && guidedStart.choice_groups.length > 0
              ? guidedStart.choice_groups
              : resolvedPhase === 'specific_topic_check'
                ? [buildSpecificTopicCheckGroup()]
                : resolvedPhase === 'subject_input'
                  ? [buildSubjectQuickPickGroup()]
                  : resolvedPhase === 'topic_selection' && cachedSuggestions.length > 0
                    ? [buildTopicChoiceGroup(cachedSuggestions)]
                    : resolvedPhase === 'page_range_selection' && cachedPageRanges.length > 0
                      ? [buildPageRangeChoiceGroup(cachedPageRanges)]
                      : resolvedPhase === 'structure_selection' && cachedStructureOptions.length > 0
                        ? [buildStructureChoiceGroup(cachedStructureOptions)]
                        : resolvedPhase === 'drafting_next_step' && cachedNextActionOptions.length > 0
                          ? [buildNextActionChoiceGroup(cachedNextActionOptions)]
                          : [];

          if (guidedStart.limited_mode) {
            setChatMeta({
              profile: 'standard',
              limited_mode: true,
              limited_reason: guidedStart.limited_reason || 'limited_context',
            });
          }

          setGuidedPhase(resolvedPhase);
          setIsGuidedTopicSelected(isGuidedSetupComplete(resolvedPhase));
          setGuidedSubject(cachedSubject);
          setGuidedSuggestions(cachedSuggestions);
          setGuidedPageRanges(cachedPageRanges);
          setGuidedStructureOptions(cachedStructureOptions);
          setGuidedNextActionOptions(cachedNextActionOptions);

          if (cachedStarter && !state.latest_artifact) {
            const derived = markdownToStructuredDraft(cachedStarter, 'planning');
            setStructuredDraft(derived);
            setWorkshopMode(derived.mode);
            setDocumentContent(structuredDraftToMarkdown(derived));
          }

          setMessages([
            {
              id: 'init',
              role: 'foli',
              content: greetingMessage,
              phase: resolvedPhase,
              topicSubject: cachedSubject || undefined,
              topicSuggestions: resolvedPhase === 'topic_selection' ? cachedSuggestions : undefined,
              pageRangeOptions: resolvedPhase === 'page_range_selection' ? cachedPageRanges : undefined,
              structureOptions:
                resolvedPhase === 'structure_selection' || resolvedPhase === 'drafting_next_step'
                  ? cachedStructureOptions
                  : undefined,
              nextActionOptions: resolvedPhase === 'drafting_next_step' ? cachedNextActionOptions : undefined,
              choiceGroups: restoredChoiceGroups,
            },
          ]);
        } catch {
          setMessages([
            {
              id: 'init',
              role: 'foli',
              content: GUIDED_CHAT_GREETING,
              phase: 'subject_input',
              choiceGroups: [buildSubjectQuickPickGroup()],
            },
          ]);
        }
      }
    } catch (error) {
      console.error('Workshop init failed:', error);
      toast.error('워크숍을 불러오지 못했어요. 로컬 모드로 전환합니다.');
      setGuidedPhase('freeform_coauthoring');
      setIsGuidedTopicSelected(true);
      setMessages([
        {
          id: 'fallback',
          role: 'foli',
          content:
            '세션 연결에 실패했습니다. 로컬에서 초안 작성은 계속 진행할 수 있어요. 백엔드 연결이 복구되면 Gemini 기반 응답과 저장 흐름으로 다시 이어집니다.',
        },
      ]);
    } finally {
      setIsSessionLoading(false);
    }
  }, [archiveResumeId, isProjectBacked, openedFromDiagnosis, preferredDiagnosisRunId, projectId, requestedChatbotMode]);

  useEffect(() => {
    if (!shouldRedirectToStoredProject || !storedWorkshopProjectId) return;
    navigate(`/app/workshop/${encodeURIComponent(storedWorkshopProjectId)}${location.search}`, {
      replace: true,
      state: workshopLocationState ?? undefined,
    });
  }, [location.search, navigate, shouldRedirectToStoredProject, storedWorkshopProjectId, workshopLocationState]);

  useEffect(() => {
    if (archiveResumeId) {
      setActiveArchiveId(archiveResumeId);
    }
  }, [archiveResumeId]);

  useEffect(() => {
    if (shouldRedirectToStoredProject) {
      return;
    }
    const savedLevel = localStorage.getItem('uni_foli_quality_level');
    if (savedLevel === 'low' || savedLevel === 'mid' || savedLevel === 'high') {
      setQualityLevel(savedLevel as QualityLevel);
    }
    if (!documentContent) {
      const seed =
        questStart?.document_seed_markdown ||
        `# [탐구 초안] ${questStart?.title || '새 주제'}\n\n## 배경 및 문제의식\n\n## 핵심 탐구 내용 1\n\n## 핵심 탐구 내용 2\n\n## 핵심 탐구 내용 3\n\n## 결론 및 다음 단계`;
      const derived = markdownToStructuredDraft(seed, 'planning');
      setStructuredDraft(derived);
      setWorkshopMode(derived.mode);
      setDocumentContent(structuredDraftToMarkdown(derived));
    }

    if (isProjectBacked) {
      void initWorkshop();
    } else {
      const archived = archiveResumeId ? getArchiveItem(archiveResumeId) : null;
      if (archived) {
        const restoredStructured =
          normalizeStructuredDraft(archived.structuredDraft, 'revision') ||
          markdownToStructuredDraft(resolveArchiveDownloadContent(archived) || '', 'revision');
        setDocumentContent(resolveArchiveDownloadContent(archived) || structuredDraftToMarkdown(restoredStructured));
        setStructuredDraft(restoredStructured);
        setWorkshopMode(restoredStructured.mode);
        setMessages(restoreMessagesFromArchive(archived));
        setActiveAccumulationStepId(inferCurrentAccumulationStepId(restoredStructured));
        setCompletedAccumulationStepId(null);
        setLatestDraftUpdatedAt(archived.updatedAt || archived.createdAt);
        setLastLocalSnapshotAt(archived.updatedAt || archived.createdAt);
        setActiveArchiveId(archived.id);
        setArchivePanelRefreshKey((prev) => prev + 1);
        setIsEditorOpen(true);
        setMobileView('draft');
      } else {
        setMessages([{ id: 'demo-init', role: 'foli', content: '데모 모드입니다. 질문을 보내면 초안 작성을 이어갈 수 있게 도와드릴게요.' }]);
      }
      setIsSessionLoading(false);
      setGuidedPhase('freeform_coauthoring');
      setIsGuidedTopicSelected(true);
    }
  }, [archiveResumeId, initialMajor, isProjectBacked, initWorkshop, questStart, shouldRedirectToStoredProject]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const saveDraftWithSync = useCallback(
    async (content: string, expectedUpdatedAt: string | null, retryOnConflict = true) => {
      if (!workshopState?.session.id) return;

      const attemptSave = async (
        nextContent: string,
        nextExpectedUpdatedAt: string | null,
        canRetry: boolean,
      ): Promise<void> => {
        try {
          const saved = await api.put<WorkshopSaveDraftResponse>(
            `/api/v1/workshops/${workshopState.session.id}/drafts/latest`,
            {
              document_content: nextContent,
              expected_updated_at: nextExpectedUpdatedAt ?? undefined,
              mode: workshopMode,
              structured_draft: structuredDraft,
            },
          );
          setLatestDraftUpdatedAt(saved.saved_updated_at);
          if (saved.structured_draft) {
            const normalized = normalizeStructuredDraft(saved.structured_draft, workshopMode);
            if (normalized) {
              setStructuredDraft(normalized);
              setWorkshopMode(normalized.mode);
            }
          }
          setIsDraftOutOfSync(false);
          return;
        } catch (error: any) {
          const conflictDetail = error?.response?.status === 409 ? error?.response?.data?.detail : null;
          if (
            canRetry &&
            conflictDetail &&
            typeof conflictDetail === 'object' &&
            typeof conflictDetail.latest_document_content === 'string' &&
            typeof conflictDetail.latest_updated_at === 'string'
          ) {
            const remoteContent = String(conflictDetail.latest_document_content || '');
            const remoteUpdatedAt = String(conflictDetail.latest_updated_at || '');
            const remoteStructured = normalizeStructuredDraft(
              conflictDetail.latest_structured_draft,
              workshopMode,
            );
            const mergedContent =
              remoteContent.trim() === nextContent.trim() || remoteContent.includes(nextContent.trim())
                ? remoteContent
                : `${remoteContent}\n\n${nextContent}`;

            setDocumentContent(mergedContent);
            if (remoteStructured) {
              setStructuredDraft(remoteStructured);
              setWorkshopMode(remoteStructured.mode);
            } else {
              const mergedStructured = markdownToStructuredDraft(mergedContent, workshopMode);
              setStructuredDraft(mergedStructured);
            }
            setLatestDraftUpdatedAt(remoteUpdatedAt);
            setIsDraftOutOfSync(true);
            toast('다른 곳에서 초안이 변경되어 최신 내용을 병합한 뒤 다시 저장했습니다.');
            await attemptSave(mergedContent, remoteUpdatedAt, false);
            return;
          }
          console.error('Autosave failed:', error);
        }
      };

      await attemptSave(content, expectedUpdatedAt, retryOnConflict);
    },
    [workshopState?.session.id, structuredDraft, workshopMode],
  );

  useEffect(() => {
    if (!workshopState?.session.id || !documentContent) return;
    const timeout = setTimeout(() => {
      void saveDraftWithSync(documentContent, latestDraftUpdatedAt);
    }, 3000);
    return () => clearTimeout(timeout);
  }, [documentContent, latestDraftUpdatedAt, saveDraftWithSync, workshopState?.session.id]);

  const persistWorkshopSnapshot = useCallback(
    (reason: 'auto' | 'manual' = 'auto') => {
      const content = (documentContent || structuredDraftToMarkdown(structuredDraft)).trim();
      const hasConversation = messages.some((message) => message.content.trim());
      if (!content && !hasConversation) return null;

      const now = new Date().toISOString();
      const sessionId = workshopState?.session.id ?? null;
      const snapshotId = sessionId
        ? `workshop-${sessionId}`
        : activeArchiveId || archiveResumeId || `workshop-local-${projectId || 'draft'}`;
      const previous = getArchiveItem(snapshotId);
      const inferredTitle = deriveArchiveTitle({
        contentMarkdown: content,
        structuredDraft,
        fallbackTitle: inferredWorkshopTitle,
        subject: initialMajor || guidedSubject || '탐구',
      });
      const titleBase = previous && !isGenericArchiveTitle(previous.title) ? previous.title : inferredTitle;

      saveArchiveItem({
        id: snapshotId,
        kind: 'workshop',
        projectId: isProjectBacked ? projectId ?? workshopState?.session.project_id ?? null : null,
        workshopId: sessionId,
        title: titleBase,
        subject: initialMajor || guidedSubject || '탐구',
        createdAt: previous?.createdAt || now,
        updatedAt: now,
        contentMarkdown: content,
        structuredDraft,
        chatMessages: serializeWorkshopMessages(messages),
      });
      setActiveArchiveId(snapshotId);
      setLastLocalSnapshotAt(now);
      setArchivePanelRefreshKey((prev) => prev + 1);
      return { id: snapshotId, reason };
    },
    [
      activeArchiveId,
      archiveResumeId,
      documentContent,
      guidedSubject,
      inferredWorkshopTitle,
      initialMajor,
      isProjectBacked,
      messages,
      projectId,
      structuredDraft,
      workshopState?.session.id,
      workshopState?.session.project_id,
    ],
  );

  useEffect(() => {
    if (!documentContent.trim() && messages.length <= 1) return;
    const timeout = window.setTimeout(() => {
      persistWorkshopSnapshot('auto');
    }, 5000);
    return () => window.clearTimeout(timeout);
  }, [documentContent, messages, persistWorkshopSnapshot]);

  const resetConversationDraft = useCallback((mode: WorkshopMode = 'planning') => {
    const emptyDraft = createEmptyStructuredDraft(mode);
    setStructuredDraft(emptyDraft);
    setWorkshopMode(emptyDraft.mode);
    setDocumentContent(structuredDraftToMarkdown(emptyDraft));
    setRenderArtifact(null);
    setLatestDraftUpdatedAt(null);
    setIsDraftOutOfSync(false);
    setPendingDraftPatch(null);
    setGuidedPhase('freeform_coauthoring');
    setIsGuidedTopicSelected(true);
    setGuidedSubject(null);
    setGuidedSuggestions([]);
    setGuidedPageRanges([]);
    setGuidedStructureOptions([]);
    setGuidedNextActionOptions([]);
    setInput('');
    setActiveAccumulationStepId(ACCUMULATION_STEPS[0].id);
    setCompletedAccumulationStepId(null);
  }, []);

  const handleNewConversation = useCallback(async () => {
    persistWorkshopSnapshot('manual');
    const localArchiveId = `workshop-local-${crypto.randomUUID()}`;
    resetConversationDraft('planning');
    setActiveArchiveId(localArchiveId);
    setMessages([
      {
        id: `new-chat-${Date.now()}`,
        role: 'foli',
        content: '새 문서작성 대화를 시작했어요. 어떤 과목 세특, 동아리, 창체, 교과활동을 다룰지부터 정해볼게요.',
      },
    ]);
    setArchivePanelRefreshKey((prev) => prev + 1);

    if (!isProjectBacked || !projectId) return;

    setIsSessionLoading(true);
    try {
      const state = await api.post<WorkshopStateResponse>('/api/v1/workshops', {
        project_id: projectId,
        quality_level: qualityLevel,
      });
      setWorkshopState(state);
      setQualityLevel(state.session.quality_level);
      setActiveArchiveId(`workshop-${state.session.id}`);
      toast.success('새 채팅을 시작했습니다.');
    } catch (error) {
      console.error('Create new workshop chat failed:', error);
      toast.error('새 서버 세션을 만들지 못해 로컬 대화로 시작합니다.');
    } finally {
      setIsSessionLoading(false);
    }
  }, [isProjectBacked, persistWorkshopSnapshot, projectId, qualityLevel, resetConversationDraft]);

  const handleResumeArchivedConversation = useCallback(
    async (item: ArchiveItem) => {
      persistWorkshopSnapshot('manual');

      if (item.projectId && projectId && item.projectId !== projectId) {
        navigate(`/app/workshop/${encodeURIComponent(item.projectId)}?archiveId=${encodeURIComponent(item.id)}`);
        return;
      }

      setIsSessionLoading(true);
      try {
        if (item.workshopId && isProjectBacked) {
          const state = await api.get<WorkshopStateResponse>(`/api/v1/workshops/${item.workshopId}`);
          setWorkshopState(state);
          setQualityLevel(state.session.quality_level);
          setRenderArtifact(state.latest_artifact || null);
        }

        const restoredStructured =
          normalizeStructuredDraft(item.structuredDraft, 'revision') ||
          markdownToStructuredDraft(resolveArchiveDownloadContent(item) || '', 'revision');
        setStructuredDraft(restoredStructured);
        setWorkshopMode(restoredStructured.mode);
        setDocumentContent(resolveArchiveDownloadContent(item) || structuredDraftToMarkdown(restoredStructured));
        setMessages(restoreMessagesFromArchive(item));
        setActiveAccumulationStepId(inferCurrentAccumulationStepId(restoredStructured));
        setCompletedAccumulationStepId(null);
        setActiveArchiveId(item.id);
        setLatestDraftUpdatedAt(item.updatedAt || item.createdAt);
        setLastLocalSnapshotAt(item.updatedAt || item.createdAt);
        setGuidedPhase('freeform_coauthoring');
        setIsGuidedTopicSelected(true);
        setArchivePanelRefreshKey((prev) => prev + 1);
        toast.success('이전 대화를 불러왔습니다.');
      } catch (error) {
        console.error('Resume archived conversation failed:', error);
        toast.error('이전 대화를 불러오지 못했습니다.');
      } finally {
        setIsSessionLoading(false);
      }
    },
    [isProjectBacked, navigate, persistWorkshopSnapshot, projectId],
  );

  useEffect(() => {
    const nextMarkdown = structuredDraftToMarkdown(structuredDraft);
    setDocumentContent(nextMarkdown);
    editorRef.current?.setContent(nextMarkdown);
  }, [structuredDraft]);


  const pushGuidedAssistantMessage = useCallback((nextMessage: Omit<Message, 'id' | 'role'> & { content: string }) => {
    setMessages((prev) => [
      ...prev,
      {
        id: crypto.randomUUID(),
        role: 'foli',
        ...nextMessage,
      },
    ]);
  }, []);

  const handleGuidedTopicSelection = useCallback(
    async (
      topicId: string,
      subjectFromMessage?: string,
      suggestionsOverride?: GuidedTopicSuggestion[],
    ) => {
      const currentSuggestions = suggestionsOverride?.length ? suggestionsOverride : guidedSuggestions;
      if (!currentSuggestions.length || !guidedProjectId) return;

      setIsGuidedActionLoading(true);
      setIsSelectingGuidedTopicId(topicId);
      try {
        const response = await api.post<GuidedTopicSelectionResponse>('/api/v1/guided-chat/topic-selection', {
          project_id: guidedProjectId,
          selected_topic_id: topicId,
          subject: subjectFromMessage || guidedSubject || undefined,
          suggestions: currentSuggestions,
        });
        if (response.limited_mode) {
          setChatMeta({
            profile: 'fast',
            limited_mode: true,
            limited_reason: response.limited_reason || 'limited_context',
          });
        }

        const derived = markdownToStructuredDraft(response.starter_draft_markdown, 'outline');
        setStructuredDraft(derived);
        setWorkshopMode(derived.mode);
        setDocumentContent(structuredDraftToMarkdown(derived));
        setLatestDraftUpdatedAt(null);
        setIsDraftOutOfSync(false);

        const nextPhase = response.phase || 'page_range_selection';
        const pageRanges = response.recommended_page_ranges || [];
        const structureOptions = response.structure_options || [];
        const nextActions = response.next_action_options || [];

        setGuidedPhase(nextPhase);
        setIsGuidedTopicSelected(false);
        setGuidedSuggestions(currentSuggestions);
        setGuidedPageRanges(pageRanges);
        setGuidedStructureOptions(structureOptions);
        setGuidedNextActionOptions(nextActions);

        pushGuidedAssistantMessage({
          content: [response.assistant_message || '', formatGuidedSelectionMessage(response)].filter(Boolean).join('\n\n'),
          phase: nextPhase,
          pageRangeOptions: pageRanges,
          structureOptions,
          nextActionOptions: nextActions,
          choiceGroups:
            response.choice_groups && response.choice_groups.length > 0
              ? response.choice_groups
              : [buildPageRangeChoiceGroup(pageRanges)],
        });
        toast.success('주제 선택을 반영했어요. 이제 분량을 정해볼게요.');
      } catch (error) {
        console.error('Guided topic selection failed:', error);
        toast.error('주제 선택을 반영하지 못했습니다. 다시 시도해 주세요.');
      } finally {
        setIsSelectingGuidedTopicId(null);
        setIsGuidedActionLoading(false);
      }
    },
    [guidedProjectId, guidedSubject, guidedSuggestions, pushGuidedAssistantMessage],
  );

  const handleGuidedPageRangeSelection = useCallback(
    async (selectedPageRangeLabel: string) => {
      if (!guidedProjectId) return;

      setIsGuidedActionLoading(true);
      try {
        const response = await api.post<GuidedPageRangeSelectionResponse>('/api/v1/guided-chat/page-range-selection', {
          project_id: guidedProjectId,
          selected_page_range_label: selectedPageRangeLabel,
        });

        if (response.limited_mode) {
          setChatMeta({
            profile: 'fast',
            limited_mode: true,
            limited_reason: response.limited_reason || 'limited_context',
          });
        }

        const nextPhase = response.phase || 'structure_selection';
        const nextStructureOptions = response.structure_options || guidedStructureOptions;

        setGuidedPhase(nextPhase);
        setIsGuidedTopicSelected(false);
        setGuidedStructureOptions(nextStructureOptions);

        pushGuidedAssistantMessage({
          content: formatGuidedPageRangeMessage(response),
          phase: nextPhase,
          structureOptions: nextStructureOptions,
          choiceGroups:
            response.choice_groups && response.choice_groups.length > 0
              ? response.choice_groups
              : [buildStructureChoiceGroup(nextStructureOptions)],
        });
      } catch (error) {
        console.error('Guided page-range selection failed:', error);
        toast.error('분량 선택을 반영하지 못했습니다. 다시 시도해 주세요.');
      } finally {
        setIsGuidedActionLoading(false);
      }
    },
    [guidedProjectId, guidedStructureOptions, pushGuidedAssistantMessage],
  );

  const handleGuidedStructureSelection = useCallback(
    async (selectedStructureId: string) => {
      if (!guidedProjectId) return;

      setIsGuidedActionLoading(true);
      try {
        const response = await api.post<GuidedStructureSelectionResponse>('/api/v1/guided-chat/structure-selection', {
          project_id: guidedProjectId,
          selected_structure_id: selectedStructureId,
        });

        if (response.limited_mode) {
          setChatMeta({
            profile: 'fast',
            limited_mode: true,
            limited_reason: response.limited_reason || 'limited_context',
          });
        }

        const nextPhase = response.phase || 'drafting_next_step';
        const nextActions = response.next_action_options || [];

        setGuidedPhase(nextPhase);
        setGuidedNextActionOptions(nextActions);
        setIsGuidedTopicSelected(true);

        pushGuidedAssistantMessage({
          content: formatGuidedStructureMessage(response),
          phase: nextPhase,
          nextActionOptions: nextActions,
          choiceGroups:
            response.choice_groups && response.choice_groups.length > 0
              ? response.choice_groups
              : [buildNextActionChoiceGroup(nextActions)],
        });
      } catch (error) {
        console.error('Guided structure selection failed:', error);
        toast.error('구성 선택을 반영하지 못했습니다. 다시 시도해 주세요.');
      } finally {
        setIsGuidedActionLoading(false);
      }
    },
    [guidedProjectId, pushGuidedAssistantMessage],
  );

  const requestGuidedSuggestions = useCallback(
    async (subjectText: string) => {
      if (!guidedProjectId) return;
      const pendingId = crypto.randomUUID();
      setIsGuidedActionLoading(true);
      setMessages((prev) => [
        ...prev,
        {
          id: pendingId,
          role: 'foli',
          content: '학생 기록을 바탕으로 주제 300개 이상을 정리하고 있어요. 잠시만 기다려 주세요.',
        },
      ]);
      try {
        const response = await api.post<GuidedTopicSuggestionResponse>('/api/v1/guided-chat/topic-suggestions', {
          project_id: guidedProjectId,
          subject: subjectText,
        });
        const normalizedSuggestions = normalizeGuidedSuggestions(response);
        if (response.limited_mode) {
          setChatMeta({
            profile: 'fast',
            limited_mode: true,
            limited_reason: response.limited_reason || 'limited_context',
          });
        }

        const nextPhase = response.phase || 'topic_selection';
        const choiceGroups =
          response.choice_groups && response.choice_groups.length > 0
            ? response.choice_groups
            : [buildTopicChoiceGroup(normalizedSuggestions)];

        setGuidedPhase(nextPhase);
        setIsGuidedTopicSelected(false);
        setGuidedSubject(response.subject);
        setGuidedSuggestions(normalizedSuggestions);
        setGuidedPageRanges([]);
        setGuidedStructureOptions([]);
        setGuidedNextActionOptions([]);

        setMessages((prev) =>
          prev.map((message) =>
            message.id === pendingId
              ? {
                  ...message,
                  content: [response.assistant_message || '', formatGuidedSuggestionMessage(response)]
                    .filter(Boolean)
                    .join('\n\n'),
                  phase: nextPhase,
                  topicSubject: response.subject,
                  topicSuggestions: normalizedSuggestions,
                  choiceGroups,
                }
              : message,
          ),
        );
      } catch (error) {
        setMessages((prev) => prev.filter((message) => message.id !== pendingId));
        throw error;
      } finally {
        setIsGuidedActionLoading(false);
      }
    },
    [guidedProjectId],
  );
  const handleOpenProfessionalEditor = useCallback(() => {
    navigate(`/app/editor/${projectId || 'demo'}`, {
      state: {
        seedMarkdown: documentContent,
      },
    });
  }, [documentContent, navigate, projectId]);

  const coauthoringTier = useMemo<'basic' | 'plus' | 'pro'>(() => {
    if (qualityLevel === 'high') return 'pro';
    if (qualityLevel === 'mid') return 'plus';
    return 'basic';
  }, [qualityLevel]);

  const applyPatchToDraft = useCallback(
    (patch: WorkshopDraftPatchProposal, approved: boolean, allowOverwriteStudentContent = false) => {
      let applied = false;
      let blockedReason: string | undefined;
      setStructuredDraft((prev) => {
        const result = applyDraftPatch(prev, patch, {
          approved,
          allowOverwriteStudentContent,
        });
        applied = result.applied;
        blockedReason = result.blockedReason;
        if (result.applied) {
          setWorkshopMode(result.next.mode);
        }
        return result.next;
      });
      if (applied) {
        setPendingDraftPatch(null);
        if (approved) {
          toast.success('승인한 섹션 제안을 문서 초안에 반영했습니다.');
        }
      } else if (blockedReason === 'student_content_protected') {
        toast('학생이 직접 작성한 섹션은 자동 덮어쓰기를 막고 있어요. 내용을 확인한 뒤 수동으로 반영해 주세요.');
      }
      return applied;
    },
    [],
  );

  const updateDraftBlock = useCallback((blockId: string, nextContent: string) => {
    setStructuredDraft((prev) => ({
      ...prev,
      blocks: prev.blocks.map((block) =>
        block.block_id === blockId
          ? {
              ...block,
              content_markdown: nextContent,
              attribution: 'student-authored',
              updated_at: new Date().toISOString(),
            }
          : block,
      ),
    }));
  }, []);

  const applyPatchThroughReportPipeline = useCallback(
    async (patch: WorkshopDraftPatchProposal) => {
      const reportPatch = {
        ...convertWorkshopDraftPatchToReportPatch(patch, { structuredDraft }),
        status: 'accepted' as const,
      };
      const validation = validateReportPatch(reportPatch, structuredDraftToReportDocumentState(structuredDraft));
      if (!validation.valid) {
        toast.error(validation.errors[0] || '문서 반영 제안을 다시 확인해 주세요.');
        return false;
      }

      const result = applyReportPatchToStructuredDraft(structuredDraft, reportPatch, { approved: true });
      if (!result.applied) {
        toast.error('학생 작성 내용 보호 정책 때문에 제안을 바로 반영하지 못했습니다.');
        return false;
      }

      if (editorRef.current) {
        new TiptapEditorAdapter(editorRef.current).applyReportPatch(reportPatch);
      }
      setStructuredDraft(result.next);
      setWorkshopMode(result.next.mode);
      setDocumentContent(structuredDraftToMarkdown(result.next));
      setPendingDraftPatch(null);
      toast.success('확인한 내용을 문서에 반영했습니다.');
      return true;
    },
    [structuredDraft],
  );

  const announceAccumulationStepApplied = useCallback(
    (patch: WorkshopDraftPatchProposal) => {
      const appliedStep = resolveAppliedAccumulationStep(patch, activeAccumulationStepId);
      if (!appliedStep) return;

      const nextStep = getNextAccumulationStep(appliedStep);
      setActiveAccumulationStepId(appliedStep.id);
      setCompletedAccumulationStepId(appliedStep.id);
      setMessages((prev) => [
        ...prev,
        {
          id: `step-applied-${appliedStep.id}-${Date.now()}`,
          role: 'foli',
          content: nextStep
            ? `${appliedStep.label}을 문서에 반영했어요. 확인이 끝났다면 아래 버튼으로 ${nextStep.label} 대화로 넘어갈 수 있습니다.`
            : `${appliedStep.label}까지 반영했어요. 이제 전체 문서 흐름을 읽고 문장 연결이나 근거 표현을 다듬으면 됩니다.`,
          phase: 'freeform_coauthoring',
          choiceGroups: nextStep ? [buildAccumulationNextChoiceGroup(appliedStep, nextStep)] : [],
        },
      ]);
    },
    [activeAccumulationStepId],
  );

  const updateDraftHeading = useCallback((blockId: string, nextHeading: string) => {
    setStructuredDraft((prev) => ({
      ...prev,
      blocks: prev.blocks.map((block) =>
        block.block_id === blockId
          ? {
              ...block,
              heading: nextHeading || block.heading,
              attribution: block.attribution,
              updated_at: new Date().toISOString(),
            }
          : block,
      ),
    }));
  }, []);

  const handleResearchRequestIfNeeded = useCallback(
    async (text: string) => {
      if (!isResearchRequestMessage(text)) {
        return false;
      }

      const targetSection = inferTargetSectionFromResearchMessage(text) || 'background_theory';
      const query = buildResearchQueryFromMessage(text, {
        selectedTopic: guidedSubject || questStart?.title || null,
        selectedOutline: structuredDraftToMarkdown(structuredDraft),
        targetMajor: initialMajor,
        currentSectionId: targetSection,
      });
      const researchSource = resolveWorkshopResearchSource(text, advancedMode);
      const researchSourceLabel = formatResearchSourceLabel(researchSource);

      setIsTyping(true);
      const pendingId = crypto.randomUUID();
      setMessages((prev) => [
        ...prev,
        {
          id: pendingId,
          role: 'foli',
          content: '관련 논문과 자료를 찾고 있어요. 검토 결과를 바로 문서에 넣을 수 있는 후보 카드로 보여드릴게요.',
        },
      ]);
      setMessages((prev) =>
        prev.map((message) =>
          message.id === pendingId ? { ...message, content: buildResearchPendingMessage(researchSourceLabel) } : message,
        ),
      );

      try {
        const result = await researchCandidates.searchCandidates(query || text, {
          targetSection,
          source: researchSource,
          limit: advancedMode ? 12 : 8,
        });
        setMessages((prev) =>
          prev.map((message) =>
            message.id === pendingId
              ? {
                  ...message,
                  content: result.candidates.length
                    ? `자료 후보 ${result.candidates.length}개를 찾았어요. 사용할 후보를 고르면 문서 반영 제안 카드로 바꿔 보여드릴게요.`
                    : '검증된 자료 후보가 적어요. 주제나 키워드를 조금 더 구체적으로 말해 주세요.',
                  researchCandidates: result.candidates,
                  researchSources: result.sources,
                }
              : message,
          ),
        );
        setMessages((prev) =>
          prev.map((message) =>
            message.id === pendingId
              ? { ...message, content: buildResearchResultMessage(result.candidates.length, researchSourceLabel) }
              : message,
          ),
        );
      } catch (error) {
        const message = error instanceof Error ? error.message : '자료 검색 중 오류가 발생했습니다.';
        console.error('Research candidate search failed:', error);
        toast.error(message);
        setMessages((prev) =>
          prev.map((item) =>
            item.id === pendingId
              ? {
                  ...item,
                  content: `자료 검색에 실패했어요.\n\n${message}\n\n잠시 후 다시 시도하거나 검색어를 더 구체적으로 바꿔 주세요.`,
                }
              : item,
          ),
        );
        setMessages((prev) =>
          prev.map((item) =>
            item.id === pendingId ? { ...item, content: buildResearchErrorMessage(message) } : item,
          ),
        );
      } finally {
        setIsTyping(false);
      }

      return true;
    },
    [advancedMode, guidedSubject, initialMajor, questStart?.title, researchCandidates, structuredDraft],
  );

  const handleSend = async (
    overriddenText?: string,
    options?: { displayText?: string; skipResearchDetection?: boolean; forceFreeform?: boolean },
  ) => {
    const text = (overriddenText ?? input ?? '').trim();
    const displayText = (options?.displayText || text).trim();
    if (!text || isTyping || isSelectingGuidedTopicId || isGuidedActionLoading) return;
    if (!overriddenText) setInput('');

    if (pendingDraftPatch && isPatchAcceptanceMessage(text)) {
      const patchToApply = pendingDraftPatch;
      setMessages(prev => [...prev, { id: crypto.randomUUID(), role: 'user', content: displayText || text }]);
      const applied = await applyPatchThroughReportPipeline(patchToApply);
      if (applied) {
        announceAccumulationStepApplied(patchToApply);
      }
      return;
    }

    setMessages(prev => [...prev, { id: crypto.randomUUID(), role: 'user', content: displayText || text }]);

    if (!options?.skipResearchDetection && await handleResearchRequestIfNeeded(text)) {
      return;
    }

    if (isProjectBacked && !options?.forceFreeform && !isGuidedSetupComplete(guidedPhase)) {
      setIsTyping(true);
      try {
        if (guidedPhase === 'subject_input') {
          const normalizedSubject = text.trim();
          const broadSubject = looksLikeBroadSubject(normalizedSubject);
          setGuidedSubject(normalizedSubject);
          setGuidedPhase('specific_topic_check');
          pushGuidedAssistantMessage({
            content: broadSubject
              ? `좋아요. ${normalizedSubject}로 진행해볼게요.\n특별히 생각해 둔 주제가 있을까요? 아직 없다면 학생 기록 기반으로 300개 이상 추천해드릴게요.`
              : `좋아요. ${normalizedSubject} 방향으로 진행해볼게요.\n이미 생각해 둔 탐구 질문이 있다면 알려주세요. 없으면 학생 기록을 바탕으로 300개 이상 추천해드릴게요.`,
            phase: 'specific_topic_check',
            topicSubject: normalizedSubject,
            choiceGroups: [buildSpecificTopicCheckGroup()],
          });
          return;
        }

        if (guidedPhase === 'specific_topic_check') {
          if (isRecommendationAffirmative(text)) {
            await requestGuidedSuggestions(guidedSubject || text);
            return;
          }
          if (isSpecificTopicAffirmative(text)) {
            pushGuidedAssistantMessage({
              content: '좋아요. 생각해 둔 주제를 한 문장으로 적어주시면 그 방향까지 반영해서 주제 300개 이상을 제안할게요.',
              phase: 'specific_topic_check',
              topicSubject: guidedSubject || undefined,
              choiceGroups: [buildSpecificTopicCheckGroup()],
            });
            return;
          }
          await requestGuidedSuggestions(text);
          return;
        }

        if (guidedPhase === 'topic_selection' || guidedPhase === 'topic_recommendation') {
          const selectedFromText = resolveGuidedSelectionFromText(text, guidedSuggestions);
          if (selectedFromText) {
            await handleGuidedTopicSelection(selectedFromText.id, guidedSubject || undefined);
          } else {
            pushGuidedAssistantMessage({
              content: '주제 카드를 눌러 선택하면 바로 분량과 구성 단계로 이어갈게요.',
              phase: 'topic_selection',
              topicSubject: guidedSubject || undefined,
              topicSuggestions: guidedSuggestions,
              choiceGroups: [buildTopicChoiceGroup(guidedSuggestions)],
            });
          }
          return;
        }

        if (guidedPhase === 'page_range_selection') {
          const selectedPageLabel = resolvePageRangeLabel(text, guidedPageRanges);
          if (selectedPageLabel) {
            await handleGuidedPageRangeSelection(selectedPageLabel);
          } else {
            pushGuidedAssistantMessage({
              content: '분량 카드를 눌러 선택해 주세요. 선택 후 바로 구성 유형을 물어볼게요.',
              phase: 'page_range_selection',
              pageRangeOptions: guidedPageRanges,
              choiceGroups: [buildPageRangeChoiceGroup(guidedPageRanges)],
            });
          }
          return;
        }

        if (guidedPhase === 'structure_selection') {
          const selectedStructureId = resolveStructureOptionId(text, guidedStructureOptions);
          if (selectedStructureId) {
            await handleGuidedStructureSelection(selectedStructureId);
          } else {
            pushGuidedAssistantMessage({
              content: '구성 유형 카드를 눌러 선택해 주세요.',
              phase: 'structure_selection',
              structureOptions: guidedStructureOptions,
              choiceGroups: [buildStructureChoiceGroup(guidedStructureOptions)],
            });
          }
          return;
        }
      } catch (error) {
        console.error('Guided setup flow failed:', error);
        toast.error('가이드 설정 중 오류가 발생했습니다. 다시 시도해 주세요.');
      } finally {
        setIsTyping(false);
      }
      return;
    }

    if (isProjectBacked && (options?.forceFreeform || guidedPhase === 'drafting_next_step')) {
      setGuidedPhase('freeform_coauthoring');
      setIsGuidedTopicSelected(true);
    }

    setIsTyping(true);
    setChatMeta(null);

    const foliId = crypto.randomUUID();
    setMessages(prev => [...prev, { id: foliId, role: 'foli', content: '' }]);

    let accumulated = '';
    let pendingDelta = '';
    let streamedPatch: WorkshopDraftPatchProposal | null = null;
    let streamAuthSource: AuthTokenSource | null = null;
    let streamLimitedReason: string | null = null;
    let flushTimer: number | null = null;
    const researchDepth = resolveWorkshopResearchDepth(text);

    const flushBufferedDelta = () => {
      if (!pendingDelta) {
        flushTimer = null;
        return;
      }
      accumulated += pendingDelta;
      pendingDelta = '';
      flushTimer = null;
      setMessages(prev => prev.map(message => (message.id === foliId ? { ...message, content: accumulated } : message)));
    };

    try {
      const streamResult = await streamFoliReply(
        isProjectBacked ? projectId : undefined,
        workshopState?.session.id,
        text,
        documentContent,
        workshopMode,
        structuredDraft,
        researchDepth,
        delta => {
          pendingDelta += delta;
          if (flushTimer === null) {
            flushTimer = window.setTimeout(flushBufferedDelta, 40);
          }
        },
        meta => {
          setChatMeta(meta);
          if (meta.limited_mode) {
            streamLimitedReason = String(meta.limited_reason || 'limited_context');
          }
          if (
            meta.coauthoring_mode === 'planning' ||
            meta.coauthoring_mode === 'outline' ||
            meta.coauthoring_mode === 'section_drafting' ||
            meta.coauthoring_mode === 'revision'
          ) {
            setWorkshopMode(meta.coauthoring_mode);
            setStructuredDraft((prev) => ({ ...prev, mode: meta.coauthoring_mode as WorkshopMode }));
          }
        },
        patch => {
          try {
            const normalizedPatch = normalizeStructuredDraftPatch(patch);
            if (normalizedPatch) {
              streamedPatch = normalizedPatch;
              documentPatch.receivePatch(normalizedPatch);
              setPendingDraftPatch(normalizedPatch);
            }
          } catch (patchError) {
            console.error('Workshop chat patch handling failed; keeping text response.', patchError);
          }
        },
      );
      streamAuthSource = streamResult.authSource;
      const raw = streamResult.text;

      if (flushTimer !== null) {
        window.clearTimeout(flushTimer);
        flushTimer = null;
      }
      flushBufferedDelta();

      if (streamLimitedReason) {
        console.warn('Workshop chat stream returned limited_mode fallback.', {
          reason: streamLimitedReason,
          auth_source: streamAuthSource,
          project_id: projectId ?? null,
          workshop_id: workshopState?.session.id ?? null,
        });
        const handledLimitedModeToast = showReadableLimitedModeToast(streamLimitedReason);
        if (!handledLimitedModeToast && streamLimitedReason === 'llm_unavailable') {
          toast.error('AI 모델 연결이 불안정해 제한 모드 안내로 전환되었어요.');
        } else if (!handledLimitedModeToast && streamLimitedReason === 'llm_not_configured') {
          toast.error('AI 모델 또는 서버 설정이 없어 제한 모드로 전환되었습니다.');
        }
      }

      const extracted = extractPatchTagFromRaw(raw);
      const resolvedPatch = streamedPatch || extracted.patch;
      const responseContent = extracted.cleaned || raw || accumulated || '응답을 생성하지 못했어요.';
      setMessages(prev =>
        prev.map(message =>
          message.id === foliId
            ? {
                ...message,
                content: responseContent,
                draftPatch: resolvedPatch || undefined,
              }
            : message,
        ),
      );
    } catch (error) {
      if (flushTimer !== null) {
        window.clearTimeout(flushTimer);
        flushTimer = null;
      }
      flushBufferedDelta();

      let fallbackContent = buildFoliFallback(text);
      if (error instanceof ChatStreamError) {
        console.error('Workshop chat stream failed with classified transport error.', {
          code: error.code,
          endpoint: error.endpoint,
          status: error.status,
          content_type: error.contentType,
          detail: error.detail,
          auth_source: error.authSource ?? streamAuthSource,
          project_id: projectId ?? null,
          workshop_id: workshopState?.session.id ?? null,
        });
        toast.error(resolveChatStreamToastMessage(error));
        const hint = resolveChatStreamFallbackHint(error);
        const readableHint = hint ? `${fallbackContent}\n\n참고 안내: ${hint}` : null;
        if (readableHint) {
          fallbackContent = readableHint;
        }
        if (!readableHint && hint) {
          fallbackContent = `${fallbackContent}\n\n참고 안내: ${hint}`;
        }
      } else {
        console.error('AI reply stream failed with unexpected error:', error);
        toast.error('채팅 응답 생성에 실패했어요. 잠시 후 다시 시도해 주세요.');
      }
      setMessages(prev =>
        prev.map(message =>
          message.id === foliId
            ? {
                ...message,
                content: fallbackContent,
              }
            : message,
        ),
      );
    } finally {
      setIsTyping(false);
    }
  };

  const handleStartWritingPlan = useCallback(async () => {
    const candidate = selectedWritingCandidate || writingCandidates[0];
    if (!candidate) {
      toast.error('먼저 문서작성 후보를 선택해 주세요.');
      return;
    }
    setGuidedPhase('freeform_coauthoring');
    setIsGuidedTopicSelected(true);
    setWorkshopMode('section_drafting');
    setActiveAccumulationStepId('intro');
    setCompletedAccumulationStepId(null);
    const prompt = buildWritingPlanPrompt({
      area: candidate.areaId === writingAreaId ? writingAreaOption : resolveRecordAreaOption(candidate.areaId),
      detail: writingDetail,
      gradeLabel: resolvedWritingGradeLabel,
      targetMajor: targetMajorForWriting,
      candidate,
      preference: writingPreference,
      aiAutoSelect: aiAutoSelectWriting,
    });
    await handleSend(prompt, {
      displayText: `${candidate.title} 후보로 서론부터 시작`,
      skipResearchDetection: true,
      forceFreeform: true,
    });
  }, [
    aiAutoSelectWriting,
    handleSend,
    resolvedWritingGradeLabel,
    selectedWritingCandidate,
    targetMajorForWriting,
    writingAreaId,
    writingAreaOption,
    writingCandidates,
    writingDetail,
    writingPreference,
  ]);

  const handleAccumulationStepRequest = useCallback(
    async (step: AccumulationStep) => {
      const currentBlockContent =
        structuredDraft.blocks.find((block) => block.block_id === step.blockId)?.content_markdown || '';
      const candidate = selectedWritingCandidate || writingCandidates[0] || null;
      setGuidedPhase('freeform_coauthoring');
      setIsGuidedTopicSelected(true);
      setWorkshopMode('section_drafting');
      setActiveAccumulationStepId(step.id);
      setCompletedAccumulationStepId(null);
      const prompt = buildAccumulationPrompt({
        step,
        candidate,
        area: candidate?.areaId ? resolveRecordAreaOption(candidate.areaId) : writingAreaOption,
        detail: writingDetail,
        gradeLabel: resolvedWritingGradeLabel,
        targetMajor: targetMajorForWriting,
        preference: writingPreference,
        currentBlockContent,
      });
      await handleSend(prompt, {
        displayText: `${step.label}만 작성/보강`,
        skipResearchDetection: true,
        forceFreeform: true,
      });
    },
    [
      handleSend,
      resolvedWritingGradeLabel,
      selectedWritingCandidate,
      structuredDraft.blocks,
      targetMajorForWriting,
      writingAreaOption,
      writingCandidates,
      writingDetail,
      writingPreference,
    ],
  );

  const handleGuidedChoiceSelect = useCallback(
    async (groupId: string, option: GuidedChoiceOption, sourceMessage: Message) => {
      const rawValue = String(option.value || option.label || option.id || '').trim();
      if (!rawValue) return;

      if (groupId === 'accumulation-next-step') {
        const [action, stepId] = rawValue.includes(':') ? rawValue.split(':', 2) : ['next', rawValue];
        const targetStep = getAccumulationStepById(stepId);
        if (!targetStep) {
          toast.error('다음 작성 단계를 찾지 못했습니다.');
          return;
        }
        await handleAccumulationStepRequest(targetStep);
        if (action === 'next') {
          toast.success(`${targetStep.label} 단계로 넘어갑니다.`);
        }
        return;
      }

      if (groupId === 'next-action-selection') {
        setGuidedPhase('freeform_coauthoring');
        setIsGuidedTopicSelected(true);
        await handleSend(rawValue);
        return;
      }

      if (groupId === 'diagnosis-quick-actions') {
        setChatbotMode('diagnosis');
        setGuidedPhase('freeform_coauthoring');
        setIsGuidedTopicSelected(true);
        await handleSend(rawValue, { displayText: option.label || rawValue, skipResearchDetection: true });
        return;
      }

      setMessages((prev) => [...prev, { id: crypto.randomUUID(), role: 'user', content: option.label || rawValue }]);

      if (groupId === 'subject-quick-picks') {
        setGuidedSubject(rawValue);
        setGuidedPhase('specific_topic_check');
        pushGuidedAssistantMessage({
          content: `좋아요. ${rawValue}로 진행해볼게요.\n특별히 생각해 둔 주제가 있을까요? 아직 없다면 학생 기록 기반으로 300개 이상 추천해드릴게요.`,
          phase: 'specific_topic_check',
          topicSubject: rawValue,
          choiceGroups: [buildSpecificTopicCheckGroup()],
        });
        return;
      }

      if (groupId === 'specific-topic-check') {
        if (option.id.includes('no')) {
          try {
            await requestGuidedSuggestions(guidedSubject || rawValue);
          } catch (error) {
            console.error('Guided suggestion failed from choice:', error);
            toast.error('주제 추천을 불러오지 못했습니다. 다시 시도해 주세요.');
          }
          return;
        }
        pushGuidedAssistantMessage({
          content: '좋아요. 생각해 둔 주제를 한 문장으로 적어주시면 그 방향까지 반영해서 300개 이상 주제를 제안할게요.',
          phase: 'specific_topic_check',
          topicSubject: guidedSubject || undefined,
          choiceGroups: [buildSpecificTopicCheckGroup()],
        });
        return;
      }

      if (groupId === 'topic-selection') {
        await handleGuidedTopicSelection(
          rawValue,
          sourceMessage.topicSubject || guidedSubject || undefined,
          sourceMessage.topicSuggestions || guidedSuggestions,
        );
        return;
      }

      if (groupId === 'page-range-selection') {
        await handleGuidedPageRangeSelection(rawValue);
        return;
      }

      if (groupId === 'structure-selection') {
        await handleGuidedStructureSelection(option.id);
        return;
      }
    },
    [
      guidedSubject,
      guidedSuggestions,
      handleSend,
      handleAccumulationStepRequest,
      handleGuidedPageRangeSelection,
      handleGuidedStructureSelection,
      handleGuidedTopicSelection,
      pushGuidedAssistantMessage,
      requestGuidedSuggestions,
    ],
  );

  const handleApplyPatchFromMessage = useCallback(
    async (patch: ReviewablePatch, message?: Message) => {
      if ('block_id' in patch) {
        setPendingDraftPatch(patch);
        const applied = await applyPatchThroughReportPipeline(patch);
        if (applied) {
          if (message?.id) {
            setMessages((prev) =>
              prev.map((item) =>
                item.id === message.id
                  ? { ...item, draftPatch: undefined, reportPatch: undefined, patchValidation: null }
                  : item,
              ),
            );
          }
          announceAccumulationStepApplied(patch);
        }
        return;
      }
      const lifecycle = await documentPatch.applyPatch({ ...patch, status: 'accepted' });
      if (message?.id && lifecycle.validation.valid) {
        setMessages((prev) =>
          prev.map((item) =>
            item.id === message.id
              ? { ...item, reportPatch: lifecycle.patch, patchValidation: lifecycle.validation }
              : item,
          ),
        );
      }
    },
    [announceAccumulationStepApplied, applyPatchThroughReportPipeline, documentPatch],
  );

  const handleRejectPatchFromMessage = useCallback((patch: ReviewablePatch, message?: Message) => {
    const messageId = message?.id;
    if (messageId) {
      setMessages((prev) =>
        prev.map((item) =>
          item.id === messageId
            ? { ...item, draftPatch: undefined, reportPatch: undefined, patchValidation: null }
            : item,
        ),
      );
    }
    if ('block_id' in patch) {
      setPendingDraftPatch(null);
    } else {
      documentPatch.rejectPatch(patch);
    }
    toast('문서 반영 제안을 거절했습니다.');
  }, [documentPatch]);

  const handleRejectPatchByMessageId = useCallback((messageId: string) => {
    setMessages((prev) =>
      prev.map((message) =>
        message.id === messageId
          ? { ...message, draftPatch: undefined, reportPatch: undefined, patchValidation: null }
          : message,
      ),
    );
    setPendingDraftPatch(null);
    toast('문서 반영 제안을 거절했습니다.');
  }, []);

  const handleRequestPatchRewrite = useCallback(
    (patch: ReviewablePatch, tone: 'simpler' | 'professional' | 'custom') => {
      const instruction =
        tone === 'simpler'
          ? '방금 문서 반영 제안을 더 쉽게 다시 써줘. 문서에는 아직 반영하지 말고 새 패치만 제안해줘.'
          : tone === 'professional'
            ? '방금 문서 반영 제안을 더 전문적인 보고서 문체로 다시 써줘. 문서에는 아직 반영하지 말고 새 패치만 제안해줘.'
            : '방금 문서 반영 제안을 내가 수정해서 확인할 수 있도록 같은 범위의 새 패치를 다시 제안해줘.';
      if ('block_id' in patch) {
        setPendingDraftPatch(patch);
      } else {
        documentPatch.requestPatchRewrite(patch, tone);
      }
      void handleSend(instruction, { displayText: instruction });
    },
    [documentPatch, handleSend],
  );

  const handleUseResearchCandidate = useCallback(
    (candidateId: string, message: Message) => {
      const candidate = message.researchCandidates?.find((item) => item.id === candidateId);
      if (!candidate) {
        toast.error('선택한 자료 후보를 찾을 수 없습니다.');
        return;
      }
      const patch = researchCandidates.convertCandidateToPatch(candidate);
      const lifecycle = documentPatch.receivePatch(patch);
      setMessages((prev) =>
        prev.map((item) =>
          item.id === message.id
            ? {
                ...item,
                reportPatch: lifecycle.patch,
                patchValidation: lifecycle.validation,
              }
            : item,
        ),
      );
      toast.success('자료 후보를 문서 반영 제안으로 바꿨어요. 검토 후 확인하면 문서에 들어갑니다.');
    },
    [documentPatch, researchCandidates],
  );

  const handleRefineResearchCandidate = useCallback(
    async (candidateId: string, message: Message) => {
      const candidate = message.researchCandidates?.find((item) => item.id === candidateId);
      if (!candidate) return;
      try {
        const result = await researchCandidates.refineCandidate(candidateId, `${candidate.title} 더 구체적인 근거`);
        if (!result) return;
        setMessages((prev) =>
          prev.map((item) =>
            item.id === message.id
              ? {
                  ...item,
                  content: `더 구체적인 자료 후보 ${result.candidates.length}개를 다시 찾았어요.`,
                  researchCandidates: result.candidates,
                  researchSources: result.sources,
                  reportPatch: undefined,
                  patchValidation: null,
                }
              : item,
          ),
        );
      } catch (error) {
        console.error('Research candidate refine failed:', error);
        toast.error(error instanceof Error ? error.message : '자료 후보를 구체화하지 못했어요.');
      }
    },
    [researchCandidates],
  );

  const handleExcludeResearchCandidate = useCallback(
    (candidateId: string, message: Message) => {
      researchCandidates.rejectCandidate(candidateId);
      setMessages((prev) =>
        prev.map((item) =>
          item.id === message.id
            ? {
                ...item,
                researchCandidates: item.researchCandidates?.filter((candidate) => candidate.id !== candidateId),
              }
            : item,
        ),
      );
    },
    [researchCandidates],
  );

  const handleToggleDeepResearchMode = useCallback(async () => {
    const nextValue = !advancedMode;
    setAdvancedMode(nextValue);
    if (!nextValue || !workshopState?.session.id || qualityLevel === 'high') {
      return;
    }

    try {
      const nextState = await api.patch<WorkshopStateResponse>(
        `/api/v1/workshops/${workshopState.session.id}/quality-level`,
        { quality_level: 'high' },
      );
      setWorkshopState(nextState);
      setQualityLevel(nextState.session.quality_level);
      localStorage.setItem('uni_foli_quality_level', nextState.session.quality_level);
    } catch (error) {
      console.warn('Failed to upgrade workshop quality level for deep research:', error);
      toast.error('웹/논문 리서치 모드를 켰지만 품질 단계 변경에 실패했어요. 보고서 생성 때 다시 시도할게요.');
    }
  }, [advancedMode, qualityLevel, workshopState?.session.id]);

  const handleDownloadReport = useCallback(() => {
    if (!reportDownloadContent) {
      toast.error('다운로드할 보고서 내용이 아직 없어요.');
      return;
    }
    downloadMarkdownFile(fileName.replace('.hwpx', '_report.md'), reportDownloadContent);
  }, [fileName, reportDownloadContent]);

  const handleGenerateDraft = async () => {
    if (!workshopState || isRendering) return;

    setIsRendering(true);
    setRenderProgressMessage('대화 내용을 정리해 보고서 생성을 시작하고 있어요.');

    try {
      let activeState = workshopState;
      if (advancedMode && qualityLevel !== 'high') {
        const nextState = await api.patch<WorkshopStateResponse>(
          `/api/v1/workshops/${workshopState.session.id}/quality-level`,
          { quality_level: 'high' },
        );
        activeState = nextState;
        setWorkshopState(nextState);
        setQualityLevel(nextState.session.quality_level);
        localStorage.setItem('uni_foli_quality_level', nextState.session.quality_level);
      }

      const workshopId = activeState.session.id;
      const deepResearchEnabled = advancedMode || activeState.session.quality_level === 'high';
      const ragSource = deepResearchEnabled ? 'both' : 'semantic';
      const tokenResponse = await api.post<WorkshopStreamTokenResponse>(`/api/v1/workshops/${workshopId}/stream-token`);
      const renderResponse = await api.post<WorkshopRenderStartResponse>(`/api/v1/workshops/${workshopId}/render`, {
        force: true,
        advanced_mode: deepResearchEnabled,
        rag_source: ragSource,
      });
      const artifactId = renderResponse.artifact_id;
      const eventsUrl = buildWorkshopEventsUrl(
        workshopId,
        tokenResponse.stream_token,
        artifactId,
        deepResearchEnabled,
        ragSource,
      );

      await new Promise<void>((resolve, reject) => {
        const source = new EventSource(eventsUrl);
        let artifactReady = false;

        const close = () => {
          source.close();
        };
        const parseData = <T,>(event: MessageEvent<string>): T | null => {
          try {
            return JSON.parse(event.data || '{}') as T;
          } catch {
            return null;
          }
        };

        source.addEventListener('render.started', (event) => {
          const payload = parseData<{ message?: string }>(event as MessageEvent<string>);
          setRenderProgressMessage(payload?.message || '보고서 렌더링을 시작했어요.');
        });

        source.addEventListener('render.progress', (event) => {
          const payload = parseData<{ message?: string; chars_generated?: number }>(event as MessageEvent<string>);
          const generated = payload?.chars_generated ? ` (${payload.chars_generated}자 생성)` : '';
          setRenderProgressMessage(`${payload?.message || '보고서를 쓰는 중이에요.'}${generated}`);
        });

        source.addEventListener('artifact.ready', (event) => {
          const payload = parseData<WorkshopArtifactReadyPayload>(event as MessageEvent<string>);
          if (!payload) return;

          const nextArtifact = createDraftArtifactFromPayload(payload, artifactId);
          const nextStructuredDraft =
            nextArtifact.structured_draft || markdownToStructuredDraft(nextArtifact.report_markdown, 'revision');

          artifactReady = true;
          setRenderArtifact(nextArtifact);
          setDocumentContent(nextArtifact.report_markdown);
          setStructuredDraft(nextStructuredDraft);
          setWorkshopMode(nextStructuredDraft.mode);
          setLatestDraftUpdatedAt(nextArtifact.updated_at || new Date().toISOString());
          setIsDraftOutOfSync(false);
          setIsEditorOpen(true);
          setMobileView('draft');
          setWorkshopState((prev) =>
            prev
              ? {
                  ...prev,
                  session: { ...prev.session, status: 'done' },
                  latest_artifact: nextArtifact,
                }
              : prev,
          );
          setRenderProgressMessage('보고서가 완성됐어요. 오른쪽 문서 패널에서 확인하고 다운로드할 수 있어요.');
        });

        source.addEventListener('render.completed', () => {
          close();
          resolve();
        });

        source.addEventListener('error', (event) => {
          close();
          if (artifactReady) {
            resolve();
          } else {
            reject(event);
          }
        });
      });

      toast.success('보고서가 완성됐어요. 다운로드할 수 있습니다.');
    } catch (error) {
      console.error('Failed to render draft:', error);
      toast.error('보고서 생성에 실패했어요. 대화 내용을 조금 더 보강한 뒤 다시 시도해 주세요.');
      setRenderProgressMessage('보고서 생성에 실패했어요. 다시 시도해 주세요.');
    } finally {
      setIsRendering(false);
    }
  };

  const handleSaveDraft = async () => {
    const snapshot = persistWorkshopSnapshot('manual');
    if (workshopState?.session.id && documentContent.trim()) {
      await saveDraftWithSync(documentContent, latestDraftUpdatedAt);
    }
    toast.success(snapshot ? '대화와 초안을 저장했어요. 아카이브에서 이어서 작업할 수 있습니다.' : '저장할 내용이 아직 없어요.');
    confetti({ particleCount: 80, spread: 62, origin: { y: 0.65 } });
  };

  const handleUpdateVisualStatus = async (visualId: string, status: string) => {
    if (!workshopState?.session.id || !workshopState.latest_artifact?.id) return;
    try {
      const response = await api.patch(
        `/api/v1/workshops/${workshopState.session.id}/artifacts/${workshopState.latest_artifact.id}/visuals/${visualId}`,
        { approval_status: status }
      );
      setWorkshopState(response.data);
      toast.success('상태를 업데이트했습니다.');
    } catch (error) {
      console.error('Failed to update visual status:', error);
      toast.error('상태 업데이트에 실패했습니다.');
    }
  };

  const handleReplaceVisual = async (visualId: string) => {
    if (!workshopState?.session.id || !workshopState.latest_artifact?.id) return;
    try {
      const response = await api.post(
        `/api/v1/workshops/${workshopState.session.id}/artifacts/${workshopState.latest_artifact.id}/visuals/${visualId}/replace`
      );
      setWorkshopState(response.data);
      toast.success('새로운 시각 자료를 생성했습니다.');
    } catch (error) {
      console.error('Failed to replace visual:', error);
      toast.error('시각 자료 생성에 실패했습니다.');
    }
  };

  const qualityMeta = QUALITY_META_MAP[qualityLevel];
  const diagnosisSummary = ((diagnosisReport?.diagnosis_summary_json ??
    diagnosisReport?.summary ??
    {}) as Record<string, unknown>) ?? {};
  const diagnosisChatbotContext = (diagnosisReport?.chatbot_context_json ?? {}) as Record<string, unknown>;
  const diagnosisHeadline =
    typeof diagnosisSummary.headline === 'string' && diagnosisSummary.headline.trim()
      ? diagnosisSummary.headline
      : undefined;
  const diagnosisRisk = typeof diagnosisSummary.risk_level === 'string' ? diagnosisSummary.risk_level : undefined;
  const diagnosisRiskKey = typeof diagnosisRisk === 'string' ? diagnosisRisk.toLowerCase() : '';
  const diagnosisRiskLabel = formatDiagnosisRiskLabel(typeof diagnosisRisk === 'string' ? diagnosisRisk : undefined);
  const diagnosisRiskStatus = diagnosisRiskKey === 'safe' ? 'success' : diagnosisRiskKey === 'danger' ? 'danger' : 'warning';
  const summaryGaps = Array.isArray(diagnosisSummary.gaps) ? diagnosisSummary.gaps : [];
  const contextWeaknesses = Array.isArray(diagnosisChatbotContext.key_weaknesses)
    ? diagnosisChatbotContext.key_weaknesses
    : [];
  const diagnosisGapCount = summaryGaps.length || contextWeaknesses.length;
  const limitedReason = chatMeta?.limited_reason || null;
  const limitedModeNotice = useMemo(() => {
    if (!chatMeta?.limited_mode) return null;
    if (limitedReason === 'evidence_gap') {
      return {
        title: '근거 보완 모드가 활성화되었습니다.',
        description: '현재 확인 가능한 학생 기록의 우선 해결 및 보수적인 대안 중심으로 안내하고 있습니다.',
      };
    }
    if (limitedReason === 'llm_unavailable') {
      return {
        title: 'AI 연결이 일시적으로 제한되었습니다.',
        description: 'Gemini/LLM 연결이 불안정하여 더 안전하고 제한된 응답으로 전환했습니다.',
      };
    }
    if (limitedReason === 'llm_not_configured') {
      return {
        title: '백엔드 AI 모델이 아직 설정되지 않았습니다.',
        description:
          '백엔드 환경 변수(LLM_PROVIDER=gemini, GEMINI_API_KEY) 또는 원격 OLLAMA_BASE_URL을 설정해 주세요.',
      };
    }
    return {
      title: '제한 모드가 활성화되었습니다.',
      description: '모델 연결이 불안정할 때는 구조 정리와 다음 질문 안내 중심으로 응답합니다.',
    };
  }, [chatMeta?.limited_mode, limitedReason]);
  const guidedSetupComplete = isGuidedSetupComplete(guidedPhase) || isGuidedTopicSelected;
  const guidedPhaseLabel =
    guidedPhase === 'subject_input'
      ? '과목 선택'
      : guidedPhase === 'specific_topic_check'
        ? '주제 구체화'
        : guidedPhase === 'topic_selection' || guidedPhase === 'topic_recommendation'
          ? '주제 선택'
          : guidedPhase === 'page_range_selection'
            ? '분량 선택'
            : guidedPhase === 'structure_selection'
              ? '구성 선택'
              : guidedSetupComplete
                ? '설정 완료'
                : '가이드 진행';
  const inputPlaceholder =
    isProjectBacked && !guidedSetupComplete
      ? '과목 카드부터 고르면 바로 시작합니다.'
      : '진단 결과를 반영해서 탐구 주제와 개요를 잡아줘';
  const quickPromptOptions = useMemo(() => {
    if (chatbotMode === 'diagnosis') return [];
    if (isProjectBacked && !guidedSetupComplete) return [];

    const prefix = diagnosisHeadline
      ? '최근 진단 아티팩트를 기반으로 '
      : '현재 기록과 대화 문맥을 기반으로 ';

    return [
      {
        label: '주제 설계',
        prompt: `${prefix}탐구 주제 후보를 최소 300개 이상 넓게 제안하고, 먼저 볼 만한 하이라이트와 각각의 작성 방향을 제안해줘.`,
      },
      {
        label: '개요 작성',
        prompt: `${prefix}가장 적합한 주제 하나를 골라 서론, 본론, 결론 개요를 잡아줘.`,
      },
      {
        label: '첫 문단',
        prompt: `${prefix}탐구 동기와 문제의식이 드러나는 첫 문단을 써줘.`,
      },
      {
        label: '보완 반영',
        prompt: `${prefix}현재 초안을 더 설득력 있게 고치는 순서를 제안해줘.`,
      },
    ];
  }, [chatbotMode, diagnosisHeadline, guidedSetupComplete, isProjectBacked]);

  return (
    <div className={cn("mx-auto flex h-full min-h-0 w-full max-w-[1800px] flex-col overflow-hidden px-2 py-2 transition-all duration-700 sm:px-4 sm:py-4", advancedMode && "rounded-[32px] bg-[linear-gradient(145deg,rgba(124,58,237,0.06)_0%,rgba(6,182,212,0.05)_100%)] shadow-[inset_0_0_100px_rgba(124,58,237,0.06)] sm:rounded-[48px]")}>
      <motion.div
        className="flex min-h-0 flex-1 flex-col"
        animate={advancedMode ? { y: [0, -2, 0] } : {}}
        transition={{ duration: 4, repeat: Infinity, ease: "easeInOut" }}
      >



        <div className="mt-6 lg:hidden">
          <WorkshopMobileToggle value={mobileView} onChange={setMobileView} />
        </div>

        <div className="relative mt-2 flex min-h-0 flex-1 justify-center overflow-hidden">
          <div className="hidden w-72 shrink-0 pr-3 xl:flex">
            <ConversationHistoryPanel
              items={archivedConversations}
              activeId={activeArchiveId}
              disabled={isSessionLoading || isTyping}
              onNewChat={() => void handleNewConversation()}
              onResume={(item) => void handleResumeArchivedConversation(item)}
            />
          </div>
          <div className={cn("flex flex-col min-h-0 flex-1 transition-all duration-500 items-center w-full", isEditorOpen ? "lg:mr-[400px] xl:mr-[500px]" : "")}>
            <div className="w-full max-w-4xl flex-1 flex flex-col relative h-full">
              <div className="absolute top-2 right-4 z-20 hidden lg:flex items-center gap-2">
                <button
                  type="button"
                  onClick={() => void handleToggleDeepResearchMode()}
                  className={cn(
                    "flex items-center gap-2 px-4 py-2 border rounded-full text-sm font-bold shadow-sm transition-all",
                    advancedMode
                      ? "bg-slate-900 border-slate-900 text-white hover:bg-slate-800"
                      : "bg-white border-slate-200 text-slate-700 hover:bg-slate-50 hover:text-indigo-600",
                  )}
                >
                  <BookOpen size={16} />
                  웹/논문 리서치 {advancedMode ? 'ON' : 'OFF'}
                </button>
                <button
                  type="button"
                  onClick={() => void handleGenerateDraft()}
                  disabled={isRendering || !workshopState}
                  className="flex items-center gap-2 px-4 py-2 bg-indigo-600 border border-indigo-600 rounded-full text-sm font-bold text-white shadow-sm hover:bg-indigo-700 disabled:bg-slate-200 disabled:border-slate-200 disabled:text-slate-500 transition-all"
                >
                  {isRendering ? <Loader2 size={16} className="animate-spin" /> : <Presentation size={16} />}
                  대화 종료·보고서 생성
                </button>
                <button
                  type="button"
                  onClick={handleDownloadReport}
                  disabled={!reportDownloadContent}
                  className="flex items-center gap-2 px-4 py-2 bg-white border border-slate-200 rounded-full text-sm font-bold text-slate-700 shadow-sm hover:bg-slate-50 hover:text-indigo-600 disabled:opacity-50 transition-all"
                >
                  <Download size={16} />
                  보고서 다운로드
                </button>
                <button
                  type="button"
                  onClick={() => setIsEditorOpen(!isEditorOpen)}
                  className="flex items-center gap-2 px-4 py-2 bg-white border border-slate-200 rounded-full text-sm font-bold text-slate-700 shadow-sm hover:bg-slate-50 hover:text-indigo-600 transition-all"
                >
                  <FileText size={16} className={isEditorOpen ? "text-indigo-600" : ""} />
                  {isEditorOpen ? '문서 닫기' : '작성한 문서 보기'}
                </button>
              </div>
                            <SectionCard
                className={cn(
                  'flex min-h-0 flex-col h-full border-none shadow-none bg-transparent overflow-hidden',
                  mobileView !== 'chat' && 'hidden lg:flex'
                )}
                bodyClassName="relative flex min-h-0 flex-1 flex-col overflow-hidden p-0 bg-transparent"
              >
                <div className="flex flex-col h-full bg-slate-50/10 backdrop-blur-md overflow-hidden">
                  {/* Chat Header Section */}
                  <div className="flex-shrink-0 flex items-center justify-between px-6 py-4 border-b border-slate-200/50 bg-white/60 backdrop-blur-xl z-10">
                    <div className="flex items-center gap-3 overflow-hidden">
                      <div className="flex-shrink-0 w-9 h-9 rounded-xl bg-indigo-50 flex items-center justify-center shadow-sm border border-indigo-100/50">
                        <MessageSquare size={18} className="text-indigo-600" />
                      </div>
                      <div className="flex flex-col overflow-hidden">
                        <p className="text-[10px] font-black uppercase tracking-widest text-indigo-500/80 mb-0.5">탐구 워크숍</p>
                        <h3 className="text-sm font-black text-slate-800 truncate max-w-[280px] sm:max-w-[400px]">
                          {(() => {
                            const title = structuredDraft.blocks.find(b => b.block_id === 'title')?.content_markdown?.trim();
                            if (title && title !== '제목' && title !== '') return title;
                            return '새로운 탐구 보고서 작성';
                          })()}
                        </h3>
                      </div>
                    </div>
                    <div className="flex items-center gap-3">
                      <StatusBadge status="active" className="text-[10px] h-5 px-2 font-black tracking-tight">
                        실시간 공동작성 중
                      </StatusBadge>
                    </div>
                  </div>

                  {/* Messages Area */}
                  <div className="flex-1 overflow-y-auto custom-scrollbar scroll-smooth bg-transparent px-4 sm:px-6">
                    <div className="max-w-4xl mx-auto w-full flex flex-col min-h-full py-10">
                      {messages.length === 0 && !isSessionLoading ? (
                        <div className="flex-1 flex flex-col items-center justify-center p-8 text-center animate-in fade-in slide-in-from-bottom-8 duration-1000 my-auto">
                          <div className="relative mb-12">
                            <div className="absolute -inset-8 bg-gradient-to-r from-violet-500 to-indigo-600 rounded-[48px] blur-3xl opacity-20 animate-pulse"></div>
                            <div className="relative w-32 h-32 rounded-[42px] bg-gradient-to-br from-violet-600 to-indigo-700 flex items-center justify-center shadow-2xl ring-[12px] ring-indigo-50/50">
                              <Bot size={64} className="text-white" />
                            </div>
                          </div>
                          
                          <h2 className="text-4xl font-black text-slate-900 mb-6 tracking-tight">
                            반가워요! 무엇을 도와드릴까요?
                          </h2>
                          <div className="space-y-2 mb-14">
                            <p className="text-slate-500 max-w-lg leading-relaxed text-lg font-medium">
                              생기부 근거를 바탕으로 나만의 독창적인<br />
                              탐구 보고서를 함께 완성해 나갑니다.
                            </p>
                            <p className="text-slate-400 max-w-lg leading-relaxed text-base font-medium">
                              학생부 분석부터 리포트 작성까지,<br />
                              당신의 대입 성공을 위한 AI 코파일럿 <span className="text-violet-600 font-bold">Foli</span>입니다.
                            </p>
                          </div>
                          
                          {quickPromptOptions.length > 0 && (
                            <div className="grid grid-cols-1 md:grid-cols-2 gap-5 w-full max-w-3xl px-4">
                              {quickPromptOptions.map((option) => (
                                <button
                                  key={option.label}
                                  onClick={() => void handleSend(option.prompt)}
                                  className="group flex items-start gap-5 p-7 text-left bg-white/60 backdrop-blur-md border border-slate-200/60 rounded-[32px] hover:border-violet-400 hover:bg-white hover:shadow-2xl hover:shadow-violet-200/30 transition-all duration-300 transform hover:-translate-y-1.5"
                                >
                                  <div className="mt-1 w-12 h-12 rounded-[20px] bg-slate-50 flex items-center justify-center group-hover:bg-violet-50 transition-colors shadow-inner border border-slate-100/50">
                                    <PenSquare size={22} className="text-slate-400 group-hover:text-violet-600" />
                                  </div>
                                  <div className="flex-1 overflow-hidden">
                                    <div className="font-black text-slate-800 text-lg mb-1.5 group-hover:text-violet-700 transition-colors truncate">{option.label}</div>
                                    <div className="text-slate-400 text-sm font-semibold tracking-tight uppercase opacity-80">분석 시작하기</div>
                                  </div>
                                </button>
                              ))}
                            </div>
                          )}
                        </div>
                      ) : (
                        <div className="px-6 py-10 space-y-10">
                          {limitedModeNotice && (
                            <WorkflowNotice
                              tone="warning"
                              title={limitedModeNotice.title}
                              description={limitedModeNotice.description}
                              className="rounded-[28px] border-amber-100 bg-amber-50/80 backdrop-blur-sm shadow-sm"
                            />
                          )}

                          {!isSessionLoading && (
                            <div className="space-y-4">
                              <WritingPlannerPanel
                                areaId={writingAreaId}
                                onAreaChange={(nextAreaId) => {
                                  setWritingAreaId(nextAreaId);
                                  setSelectedWritingCandidateId(null);
                                }}
                                detail={writingDetail}
                                onDetailChange={(value) => {
                                  setWritingDetail(value);
                                  setSelectedWritingCandidateId(null);
                                }}
                                gradeId={writingGradeId}
                                onGradeChange={setWritingGradeId}
                                inferredGrade={inferredWritingGrade}
                                gradeLabel={resolvedWritingGradeLabel}
                                candidates={writingCandidates}
                                selectedCandidateId={selectedWritingCandidateId}
                                onCandidateSelect={setSelectedWritingCandidateId}
                                preference={writingPreference}
                                onPreferenceChange={setWritingPreference}
                                aiAutoSelect={aiAutoSelectWriting}
                                onAutoSelectChange={setAiAutoSelectWriting}
                                onStart={() => void handleStartWritingPlan()}
                                disabled={isTyping || isGuidedActionLoading || !!isSelectingGuidedTopicId || !workshopState?.session.id}
                              />
                              <DraftAccumulationPanel
                                steps={ACCUMULATION_STEPS}
                                structuredDraft={structuredDraft}
                                activeStepId={activeAccumulationStepId}
                                completedStepId={completedAccumulationStepId}
                                onStepRequest={(step) => void handleAccumulationStepRequest(step)}
                                onNextStep={(step) => void handleAccumulationStepRequest(step)}
                                disabled={isTyping || isGuidedActionLoading || !!isSelectingGuidedTopicId || !workshopState?.session.id}
                              />
                            </div>
                          )}

                          {!isSessionLoading ? (
                            <div className="space-y-10">
                              {messages.map((message) => (
                                <WorkshopChatBubble
                                  key={message.id}
                                  message={message}
                                  onApplyPatch={handleApplyPatchFromMessage}
                                  onRejectPatch={handleRejectPatchFromMessage}
                                  onRequestPatchRewrite={handleRequestPatchRewrite}
                                  onUseResearchCandidate={handleUseResearchCandidate}
                                  onRefineResearchCandidate={handleRefineResearchCandidate}
                                  onExcludeResearchCandidate={handleExcludeResearchCandidate}
                                  onGuidedChoiceSelect={handleGuidedChoiceSelect}
                                  isGuidedActionLoading={isGuidedActionLoading}
                                  selectingTopicId={isSelectingGuidedTopicId}
                                />
                              ))}
                              <div ref={messagesEndRef} />
                            </div>
                          ) : (
                            <div className="flex h-96 items-center justify-center">
                              <div className="flex flex-col items-center gap-6">
                                <div className="relative">
                                  <div className="absolute inset-0 rounded-full bg-violet-400 blur-xl opacity-20 animate-pulse"></div>
                                  <Loader2 size={40} className="animate-spin text-violet-600 relative" />
                                </div>
                                <p className="text-slate-400 font-bold text-lg animate-pulse tracking-wide">AI 분석 세션 연결 중...</p>
                              </div>
                            </div>
                          )}
                        </div>
                      )}
                    </div>
                  </div>

                  {/* Input Area */}
                  <div className="px-4 pb-8 pt-4 bg-gradient-to-t from-slate-50/50 to-transparent">
                    <div className="max-w-4xl mx-auto w-full">
                      <div className="mb-3 flex gap-2 lg:hidden">
                        <button
                          type="button"
                          onClick={() => void handleToggleDeepResearchMode()}
                          className={cn(
                            "flex h-10 w-10 items-center justify-center rounded-2xl border shadow-sm",
                            advancedMode
                              ? "bg-slate-900 border-slate-900 text-white"
                              : "bg-white border-slate-200 text-slate-700",
                          )}
                          aria-label="웹/논문 리서치 모드 전환"
                        >
                          <BookOpen size={17} />
                        </button>
                        <button
                          type="button"
                          onClick={() => void handleGenerateDraft()}
                          disabled={isRendering || !workshopState}
                          className="flex flex-1 items-center justify-center gap-2 rounded-2xl bg-indigo-600 px-3 py-2 text-sm font-black text-white shadow-sm disabled:bg-slate-200 disabled:text-slate-500"
                        >
                          {isRendering ? <Loader2 size={16} className="animate-spin" /> : <Presentation size={16} />}
                          보고서 생성
                        </button>
                        <button
                          type="button"
                          onClick={handleDownloadReport}
                          disabled={!reportDownloadContent}
                          className="flex h-10 w-10 items-center justify-center rounded-2xl border border-slate-200 bg-white text-slate-700 shadow-sm disabled:opacity-40"
                          aria-label="보고서 다운로드"
                        >
                          <Download size={17} />
                        </button>
                      </div>
                      {renderProgressMessage && (
                        <div className="mb-3 flex items-center justify-between gap-3 rounded-2xl border border-indigo-100 bg-white/90 px-4 py-3 text-sm font-semibold text-slate-700 shadow-sm">
                          <span className="flex items-center gap-2">
                            {isRendering ? (
                              <Loader2 size={16} className="animate-spin text-indigo-600" />
                            ) : (
                              <FileText size={16} className="text-indigo-600" />
                            )}
                            {renderProgressMessage}
                          </span>
                          {reportDownloadContent && !isRendering && (
                            <button
                              type="button"
                              onClick={handleDownloadReport}
                              className="shrink-0 rounded-full border border-slate-200 px-3 py-1.5 text-xs font-black text-slate-700 hover:border-indigo-200 hover:text-indigo-600"
                            >
                              다운로드
                            </button>
                          )}
                        </div>
                      )}
                      <div className="relative group">
                        <div className="absolute -inset-1 bg-gradient-to-r from-violet-500 via-indigo-500 to-cyan-500 rounded-[32px] opacity-15 group-focus-within:opacity-30 transition duration-500 blur-md"></div>
                        <div className="relative flex items-center gap-3 bg-white p-2.5 pl-7 rounded-[30px] border border-slate-200/80 shadow-2xl shadow-indigo-100/30 transition-all duration-300 group-focus-within:border-violet-300 group-focus-within:shadow-violet-200/40">
                          <input
                            value={input}
                            onChange={(e) => setInput(e.target.value)}
                            onKeyDown={(e) => {
                              if (e.key === 'Enter' && !e.shiftKey) {
                                e.preventDefault();
                                void handleSend();
                              }
                            }}
                            placeholder={inputPlaceholder}
                            disabled={isTyping || !!isSelectingGuidedTopicId || isGuidedActionLoading}
                            className="flex-1 py-4 bg-transparent text-[17px] font-semibold text-slate-900 outline-none placeholder:text-slate-400 disabled:opacity-50"
                          />
                          <button
                            type="button"
                            onClick={() => void handleSend()}
                            disabled={!input.trim() || isTyping || !!isSelectingGuidedTopicId || isGuidedActionLoading}
                            className="flex h-14 w-14 items-center justify-center rounded-[24px] bg-slate-900 text-white shadow-xl transition-all duration-300 hover:bg-violet-600 disabled:bg-slate-100 disabled:text-slate-400"
                          >
                            <Send size={24} />
                          </button>
                        </div>
                      </div>
                      <p className="mt-4 text-center text-[12px] text-slate-400 font-bold tracking-tight opacity-70">
                        Foli는 AI 기술을 통해 분석을 돕지만, 최종 결정은 사용자에게 있습니다.
                      </p>
                    </div>
                  </div>
                </div>
              </SectionCard>
            </div>
          </div>

          <div
            className={cn(
              'flex min-h-0 flex-col h-full bg-white lg:border-l border-slate-200 lg:shadow-[-10px_0_30px_-10px_rgba(0,0,0,0.05)] transition-all duration-500 absolute right-0 top-0 bottom-0 z-10 w-full lg:w-[400px] xl:w-[500px]',
              mobileView !== 'draft' && 'hidden lg:flex',
              !isEditorOpen && 'lg:translate-x-full lg:opacity-0 lg:invisible',
              isEditorOpen && 'lg:translate-x-0 lg:opacity-100 lg:visible'
            )}
          >
            <div className="flex items-center justify-between px-4 py-3 border-b border-slate-100 bg-slate-50/80 backdrop-blur">
              <h2 className="text-sm font-black text-slate-800 flex items-center gap-2">
                <FileText size={16} className="text-indigo-600"/>
                문서 편집기
              </h2>
              {lastLocalSnapshotAt && (
                <span className="hidden rounded-full bg-emerald-50 px-2.5 py-1 text-[11px] font-black text-emerald-700 sm:inline-flex">
                  자동 저장 {new Date(lastLocalSnapshotAt).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                </span>
              )}
              <div className="flex items-center gap-2">
                <PrimaryButton size="sm" onClick={() => void handleSaveDraft()} className="shadow-sm py-1.5 px-3 h-auto text-xs">
                  <Save size={14} className="mr-1.5" />
                  저장
                </PrimaryButton>
                <SecondaryButton
                  size="sm"
                  className="shadow-sm bg-white py-1.5 px-3 h-auto text-xs"
                  onClick={handleDownloadReport}
                  disabled={!reportDownloadContent}
                >
                  <Download size={14} className="mr-1.5" />
                  보고서 다운로드
                </SecondaryButton>
                <button 
                  onClick={() => setIsEditorOpen(false)}
                  className="p-1.5 text-slate-400 hover:text-slate-700 hover:bg-slate-200 rounded-full transition-colors hidden lg:block ml-1"
                >
                  <X size={16} />
                </button>
              </div>
            </div>
            
            <div className="flex flex-1 flex-col overflow-hidden p-2 sm:p-4 pt-4 sm:pt-4">
              {isDraftOutOfSync && (
                <WorkflowNotice
                  tone="warning"
                  title="동기화 알림"
                  description="다른 기기에서 수정된 내용이 병합되었습니다."
                  className="mb-4"
                />
              )}

              <div className="flex-1 overflow-hidden rounded-[24px] border border-slate-200 bg-white shadow-sm ring-1 ring-slate-200/50 transition-all focus-within:ring-indigo-500/30">
                <TiptapEditor
                  ref={editorRef}
                  initialContent={documentContent}
                  onUpdate={(json, html, text) => {
                    // Simple text update for documentContent to keep it synced
                    // In a real app, you'd convert HTML to Markdown properly
                    setDocumentContent(text);
                  }}
                />
              </div>

              {advancedMode && (
                <div className="mt-4 flex flex-col gap-4 overflow-y-auto pr-1 custom-scrollbar">
                  <EvidenceDrawer evidenceMap={renderArtifact?.evidence_map ?? null} />
                  <SurfaceCard className="border-indigo-100 bg-indigo-50/30 p-4">
                    <AdvancedPreview
                      workshopId={workshopState?.session.id || ''}
                      artifactId={workshopState?.latest_artifact?.id || ''}
                      isAdvancedMode={advancedMode}
                      visualSpecs={renderArtifact?.visual_specs ?? []}
                      mathExpressions={renderArtifact?.math_expressions ?? []}
                      onUpdateVisualStatus={handleUpdateVisualStatus}
                      onReplaceVisual={handleReplaceVisual}
                    />
                  </SurfaceCard>
                </div>
              )}
            </div>
          </div>
        </div>
      </motion.div>
    </div>
  );
}
