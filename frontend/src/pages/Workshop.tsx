import React, { memo, useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { AnimatePresence, motion } from 'motion/react';
import {
  Bot,
  ChevronDown,
  ChevronUp,
  Download,
  Loader2,
  PenSquare,
  Presentation,
  Save,
  Send,
  ToggleLeft,
  ToggleRight,
  User,
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
import { DIAGNOSIS_STORAGE_KEY, type DiagnosisRunResponse, type StoredDiagnosis } from '../lib/diagnosis';
import { saveArchiveItem } from '../lib/archiveStore';
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
import { WorkshopProgress } from '../components/WorkshopProgress';
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
import {
  ensureThreeSuggestions,
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

const QUALITY_META_MAP: Record<QualityLevel, { label: string; status: 'success' | 'active' | 'warning' }> = {
  low: { label: '빠른 응답', status: 'success' },
  mid: { label: '균형 모드', status: 'active' },
  high: { label: '심화 모드', status: 'warning' },
};

const GUIDED_CHAT_GREETING = '안녕하세요! 어떤 주제로 보고서를 완성해볼까요?';
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

function normalizeGuidedSuggestions(response: GuidedTopicSuggestionResponse): GuidedTopicSuggestion[] {
  return ensureThreeSuggestions(response).suggestions.slice(0, 3);
}

function formatGuidedSuggestionMessage(response: GuidedTopicSuggestionResponse) {
  const suggestions = normalizeGuidedSuggestions(response);
  const lines = [
    `좋아요. '${response.subject}'를 바탕으로 학생 기록 흐름에 맞는 주제 3가지를 준비했어요.`,
    '',
    ...suggestions.flatMap((item, index) => {
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
  lines.push('', '이 중에서 가장 마음이 가는 주제를 골라주세요.');
  return lines.join('\n');
}

function formatGuidedSelectionMessage(response: GuidedTopicSelectionResponse) {
  const lines = [
    `선택한 주제는 **${response.selected_title}**입니다.`,
    '',
    response.guidance_message,
    '',
    '이제 진행하고 싶은 보고서 분량을 고르면 바로 개요를 잡아드릴게요.',
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
  lines.push('', '다음으로 구성 스타일을 골라주세요.');
  return lines.join('\n');
}

function formatGuidedStructureMessage(response: GuidedStructureSelectionResponse) {
  return [
    response.assistant_message,
    '',
    `선택한 구성: **${response.selected_structure_label}**`,
    '',
    '가이드가 거의 끝났습니다. 다음으로 무엇을 하고 싶은지 알려주세요.',
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
    title: '이 중에서 가장 마음에 드는 주제를 골라주세요.',
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
    title: '구성 스타일을 골라주세요.',
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
  const clean = (message || '').toLowerCase().trim();
  const greetings = ['안녕', 'hi', 'hello', 'hey', 'good morning', 'good evening'];

  if (greetings.some(token => clean.includes(token))) {
    return [
      '안녕하세요! 유니폴리 워크숍 도우미입니다.',
      '',
      '지금은 AI 연결이 잠시 불안정해서, 초안 구조 정리와 다음 질문 안내를 중심으로 안전하게 이어갈게요.',
    ].join('\n');
  }

  return [
    '현재 AI 응답이 잠시 지연되어 기본 안내 모드로 전환했어요.',
    '',
    '아래 순서대로 보내 주시면 초안 작성 흐름을 계속 이어갈 수 있어요.',
    '1. 이번 글에서 다루려는 주제를 한 문장으로 적어 주세요.',
    '2. 그 주제를 선정한 이유를 간단히 알려 주세요.',
    '3. 마지막으로 보고서에 꼭 포함하고 싶은 키워드 3가지만 말씀해 주세요.',
  ].join('\n');
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
  const markerStart = '<workshop-patch>';
  const markerEnd = '</workshop-patch>';
  const startIdx = raw.indexOf(markerStart);
  const endIdx = raw.indexOf(markerEnd);

  if (startIdx === -1 || endIdx === -1 || endIdx < startIdx) {
    return { cleaned: raw, patch: null };
  }

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
      payload: {
        project_id: projectId,
        workshop_id: workshopId,
        message: text,
        document_content: documentContent,
        mode,
        structured_draft: structuredDraft,
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
  const shouldRedirectToStoredProject = !isProjectBacked && Boolean(storedWorkshopProjectId);
  const guidedProjectId = isProjectBacked ? projectId ?? null : null;
  const fileName = useMemo(() => `${(questStart?.title || 'draft').replace(/\s+/g, '_')}.hwpx`, [questStart]);
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
      const sessions = await api.get<WorkshopSessionResponse[]>(`/api/v1/workshops?project_id=${projectId}`);
      const active = sessions.find(session => session.status !== 'completed');
      const preferredQuality = localStorage.getItem('uni_foli_quality_level');
      const createQuality: QualityLevel =
        preferredQuality === 'low' || preferredQuality === 'mid' || preferredQuality === 'high'
          ? preferredQuality
          : 'mid';
      const state = active
        ? await api.get<WorkshopStateResponse>(`/api/v1/workshops/${active.id}`)
        : await api.post<WorkshopStateResponse>('/api/v1/workshops', { project_id: projectId, quality_level: createQuality });

      setWorkshopState(state);
      setQualityLevel(state.session.quality_level);

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
        setLatestDraftUpdatedAt(state.latest_artifact.updated_at ?? null);
        setIsDraftOutOfSync(false);
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
      toast.error('워크숍을 불러오지 못했습니다. 로컬 모드로 전환합니다.');
      setGuidedPhase('freeform_coauthoring');
      setIsGuidedTopicSelected(true);
      setMessages([{ id: 'fallback', role: 'foli', content: '세션 연결에 실패했습니다. 로컬에서 초안 작성을 진행하실 수 있습니다.' }]);
    } finally {
      setIsSessionLoading(false);
    }
  }, [isProjectBacked, openedFromDiagnosis, preferredDiagnosisRunId, projectId, requestedChatbotMode]);

  useEffect(() => {
    if (!shouldRedirectToStoredProject || !storedWorkshopProjectId) return;
    navigate(`/app/workshop/${encodeURIComponent(storedWorkshopProjectId)}${location.search}`, {
      replace: true,
      state: workshopLocationState ?? undefined,
    });
  }, [location.search, navigate, shouldRedirectToStoredProject, storedWorkshopProjectId, workshopLocationState]);

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
      setIsSessionLoading(false);
      setGuidedPhase('freeform_coauthoring');
      setIsGuidedTopicSelected(true);
      setMessages([{ id: 'demo-init', role: 'foli', content: '데모 모드입니다. 유니폴리에게 질문하면 초안 작성을 이어서 도와드릴게요.' }]);
    }
  }, [initialMajor, isProjectBacked, initWorkshop, questStart, shouldRedirectToStoredProject]);

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
            toast('다른 탭에서 초안이 변경되어 최신 내용을 병합한 뒤 다시 저장했습니다.');
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
        toast.success('주제 선택이 반영되었어요. 이제 분량을 정해볼게요.');
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
          content: '학생 기록을 바탕으로 주제 3가지를 정리하고 있어요. 잠시만 기다려주세요.',
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
          toast.success('승인된 섹션 제안이 우측 구조 초안에 반영되었습니다.');
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
        toast.error(validation.errors[0] || '문서 반영 제안을 검토해야 합니다.');
        return false;
      }

      const result = applyReportPatchToStructuredDraft(structuredDraft, reportPatch, { approved: true });
      if (!result.applied) {
        toast.error('학생 작성 내용 보호 정책 때문에 patch를 바로 반영하지 못했습니다.');
        return false;
      }

      if (editorRef.current) {
        new TiptapEditorAdapter(editorRef.current).applyReportPatch(reportPatch);
      }
      setStructuredDraft(result.next);
      setWorkshopMode(result.next.mode);
      setDocumentContent(structuredDraftToMarkdown(result.next));
      setPendingDraftPatch(null);
      toast.success('승인된 문서 patch를 반영했습니다.');
      return true;
    },
    [structuredDraft],
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

      setIsTyping(true);
      const pendingId = crypto.randomUUID();
      setMessages((prev) => [
        ...prev,
        {
          id: pendingId,
          role: 'foli',
          content: '관련 논문과 자료를 찾고 있어요. 검색 결과는 바로 문서에 넣지 않고 후보 카드로 보여드릴게요.',
        },
      ]);

      try {
        const result = await researchCandidates.searchCandidates(query || text, {
          targetSection,
          source: 'both',
          limit: 5,
        });
        setMessages((prev) =>
          prev.map((message) =>
            message.id === pendingId
              ? {
                  ...message,
                  content: result.candidates.length
                    ? `자료 후보 ${result.candidates.length}개를 찾았어요. 사용할 후보를 고르면 먼저 문서 반영 제안 카드로 바꿔서 보여드릴게요.`
                    : '검색된 자료 후보가 없어요. 주제나 키워드를 조금 더 구체적으로 말해 주세요.',
                  researchCandidates: result.candidates,
                  researchSources: result.sources,
                }
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
                  content: `자료 검색에 실패했어요.\n\n${message}\n\n잠시 뒤 다시 시도하거나 검색어를 더 구체적으로 바꿔 주세요.`,
                }
              : item,
          ),
        );
      } finally {
        setIsTyping(false);
      }

      return true;
    },
    [guidedSubject, initialMajor, questStart?.title, researchCandidates, structuredDraft],
  );

  const handleSend = async (overriddenText?: string, options?: { displayText?: string }) => {
    const text = (overriddenText ?? input ?? '').trim();
    const displayText = (options?.displayText || text).trim();
    if (!text || isTyping || isSelectingGuidedTopicId || isGuidedActionLoading) return;
    if (!overriddenText) setInput('');

    if (pendingDraftPatch && isPatchAcceptanceMessage(text)) {
      await applyPatchThroughReportPipeline(pendingDraftPatch);
    }

    setMessages(prev => [...prev, { id: crypto.randomUUID(), role: 'user', content: displayText || text }]);

    if (await handleResearchRequestIfNeeded(text)) {
      return;
    }

    if (isProjectBacked && !isGuidedSetupComplete(guidedPhase)) {
      setIsTyping(true);
      try {
        if (guidedPhase === 'subject_input') {
          const normalizedSubject = text.trim();
          const broadSubject = looksLikeBroadSubject(normalizedSubject);
          setGuidedSubject(normalizedSubject);
          setGuidedPhase('specific_topic_check');
          pushGuidedAssistantMessage({
            content: broadSubject
              ? `좋아요. ${normalizedSubject}로 진행해볼게요.\n특별히 생각해 둔 주제가 있을까요? 아직 없다면 학생 기록 기반으로 3개 추천해드릴게요.`
              : `좋아요. ${normalizedSubject} 방향으로 진행해볼게요.\n이미 생각해둔 탐구 질문이 있다면 알려주세요. 없으면 학생 기록을 바탕으로 3개 추천해드릴게요.`,
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
              content: '좋아요. 생각해둔 주제를 한 문장으로 적어주시면, 그 방향까지 반영해서 주제 3가지를 제안할게요.',
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
              content: '주제 카드를 눌러 선택하면 바로 분량/구성 단계로 이어갈게요.',
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
              content: '분량 카드를 눌러 선택해 주세요. 선택 후 바로 구성 스타일을 물어볼게요.',
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
              content: '구성 스타일 카드를 눌러 선택해 주세요.',
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

    if (isProjectBacked && guidedPhase === 'drafting_next_step') {
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
        if (streamLimitedReason === 'llm_unavailable') {
          toast.error('AI 모델 연결이 불안정하여 제한 모드 안내로 전환되었어요.');
        } else if (streamLimitedReason === 'llm_not_configured') {
          toast.error('AI 모델 키가 서버에 설정되지 않아 제한 모드로 전환되었습니다.');
        }
      }

      const extracted = extractPatchTagFromRaw(raw);
      const resolvedPatch = streamedPatch || extracted.patch;
      const responseContent = extracted.cleaned || raw || accumulated || '답변을 생성하지 못했습니다.';
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
        if (hint) {
          fallbackContent = `${fallbackContent}\n\n참고 안내: ${hint}`;
        }
      } else {
        console.error('AI reply stream failed with unexpected error:', error);
        toast.error('채팅 응답 생성에 실패했습니다. 잠시 후 다시 시도해 주세요.');
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

  const handleGuidedChoiceSelect = useCallback(
    async (groupId: string, option: GuidedChoiceOption, sourceMessage: Message) => {
      const rawValue = String(option.value || option.label || option.id || '').trim();
      if (!rawValue) return;

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
        await handleSend(rawValue, { displayText: option.label || rawValue });
        return;
      }

      setMessages((prev) => [...prev, { id: crypto.randomUUID(), role: 'user', content: option.label || rawValue }]);

      if (groupId === 'subject-quick-picks') {
        setGuidedSubject(rawValue);
        setGuidedPhase('specific_topic_check');
        pushGuidedAssistantMessage({
          content: `좋아요. ${rawValue}로 진행해볼게요.\n특별히 생각해 둔 주제가 있을까요? 아직 없다면 학생 기록 기반으로 3개 추천해드릴게요.`,
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
          content: '좋아요. 생각해둔 주제를 한 문장으로 적어주시면 그 방향까지 반영해서 3개 주제를 제안할게요.',
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
        await applyPatchThroughReportPipeline(patch);
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
    [applyPatchThroughReportPipeline, documentPatch],
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
          ? '방금 문서 반영 제안을 더 쉽게 다시 써줘. 문서에는 아직 반영하지 말고 새 patch로 제안해줘.'
          : tone === 'professional'
            ? '방금 문서 반영 제안을 더 전문적인 보고서 문체로 다시 써줘. 문서에는 아직 반영하지 말고 새 patch로 제안해줘.'
            : '방금 문서 반영 제안을 내가 수정해서 승인할 수 있도록 더 작은 단위의 patch로 다시 제안해줘.';
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
      toast.success('자료 후보를 문서 반영 제안으로 바꿨어요. 검토 후 승인하면 문서에 들어갑니다.');
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
                  content: `더 구체화한 자료 후보 ${result.candidates.length}개를 다시 찾았어요.`,
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
        toast.error(error instanceof Error ? error.message : '자료 후보를 구체화하지 못했습니다.');
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

  const handleGenerateDraft = async () => {
    if (!workshopState || isRendering) return;
    setIsRendering(true);
    try {
      await api.post(`/api/v1/workshops/${workshopState.session.id}/render`);
      toast.success('결과물 생성을 요청했습니다.');
    } catch (error) {
      console.error('Failed to render draft:', error);
      toast.error('생성 요청에 실패했습니다.');
    } finally {
      setIsRendering(false);
    }
  };

  const handleSaveDraft = () => {
    saveArchiveItem({
      id: crypto.randomUUID(),
      projectId: projectId ?? null,
      title: fileName.replace('.hwpx', ''),
      subject: initialMajor,
      createdAt: new Date().toISOString(),
      contentMarkdown: documentContent,
    });
    toast.success('워크숍 초안을 저장했어요.');
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
      toast.error('상태 업데이트 실패');
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
      toast.error('시각 자료 생성 실패');
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
        description: '현재 확인 가능한 학생 기록만 우선 연결해, 보수적인 제안 중심으로 안내하고 있어요.',
      };
    }
    if (limitedReason === 'llm_unavailable') {
      return {
        title: 'AI 연결이 일시적으로 제한되었습니다.',
        description: 'Gemini/LLM 연결이 불안정해 더 안전한 제한 응답으로 전환했습니다.',
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
      ? '과목 카드부터 고르면 바로 시작됩니다.'
      : '예: 내 약점 3가지를 근거와 함께 정리해줘';
  const quickPromptOptions = useMemo(() => {
    if (chatbotMode === 'diagnosis') return [];
    if (isProjectBacked && !guidedSetupComplete) return [];

    const prefix = diagnosisHeadline
      ? '최근 진단 아티팩트를 기준으로 '
      : '현재 기록과 대화 문맥을 기준으로 ';

    return [
      {
        label: '강점 요약',
        prompt: `${prefix}내 생기부의 핵심 강점 3가지를 근거와 함께 정리해줘.`,
      },
      {
        label: '약점 보완',
        prompt: `${prefix}내가 먼저 보완해야 할 약점 3가지를 근거와 함께 설명해줘.`,
      },
      {
        label: '탐구 주제',
        prompt: `${prefix}지금 바로 시도할 탐구 주제 3개를 추천해줘.`,
      },
      {
        label: '다음 한 달',
        prompt: `${prefix}다음 한 달 행동 계획을 주차별로 정리해줘.`,
      },
    ];
  }, [chatbotMode, diagnosisHeadline, guidedSetupComplete, isProjectBacked]);

  return (
    <div className={cn("mx-auto h-[100dvh] flex flex-col max-w-[1800px] px-2 sm:px-4 py-2 sm:py-4 transition-all duration-700", advancedMode && "rounded-[32px] bg-[linear-gradient(145deg,rgba(124,58,237,0.06)_0%,rgba(6,182,212,0.05)_100%)] shadow-[inset_0_0_100px_rgba(124,58,237,0.06)] sm:rounded-[48px]")}>
      <motion.div
        animate={advancedMode ? { y: [0, -2, 0] } : {}}
        transition={{ duration: 4, repeat: Infinity, ease: "easeInOut" }}
      >

        {quickPromptOptions.length > 0 && messages.length <= 4 && (
          <div className="mt-4 flex flex-wrap gap-2">
            {quickPromptOptions.map((option) => (
              <button
                key={option.label}
                type="button"
                onClick={() => void handleSend(option.prompt)}
                disabled={isTyping || !!isSelectingGuidedTopicId || isGuidedActionLoading}
                className="inline-flex items-center gap-2 rounded-full border border-slate-200 bg-white px-4 py-2 text-sm font-bold text-slate-700 transition-colors hover:border-violet-300 hover:bg-violet-50 hover:text-violet-700 disabled:cursor-not-allowed disabled:opacity-50"
              >
                {option.label}
              </button>
            ))}
          </div>
        )}

        <div className="mt-6 lg:hidden">
          <WorkshopMobileToggle value={mobileView} onChange={setMobileView} />
          <div className="hidden w-full items-center gap-1 rounded-2xl border border-slate-200 bg-white p-1 shadow-sm">
            <button
              type="button"
              onClick={() => setMobileView('chat')}
              className={cn(
                'h-10 flex-1 rounded-xl px-3 text-sm font-bold transition-all',
                mobileView === 'chat' ? 'bg-[linear-gradient(135deg,#7c3aed_0%,#06b6d4_100%)] text-white shadow-md' : 'text-slate-600 hover:bg-slate-50',
              )}
            >
              채팅
            </button>
            <button
              type="button"
              onClick={() => setMobileView('draft')}
              className={cn(
                'h-10 flex-1 rounded-xl px-3 text-sm font-bold transition-all',
                mobileView === 'draft' ? 'bg-[linear-gradient(135deg,#7c3aed_0%,#06b6d4_100%)] text-white shadow-md' : 'text-slate-600 hover:bg-slate-50',
              )}
            >
              문서
            </button>
          </div>
        </div>

        <div className="mt-2 flex-1 min-h-0 grid gap-4 lg:grid-cols-[380px_minmax(0,1fr)] xl:grid-cols-[420px_minmax(0,1fr)]">
          <SectionCard
            title="코파일럿"
            eyebrow="대화"
            className={cn(
              'flex min-h-0 flex-col min-h-[70dvh] max-h-[calc(100dvh-12rem)] lg:h-[calc(100dvh-16rem)] lg:min-h-[600px] lg:max-h-[900px]',
              mobileView !== 'chat' && 'hidden lg:flex'
            )}
            bodyClassName="relative flex min-h-0 flex-1 flex-col overflow-hidden p-0"
          >
            <div className="flex h-full flex-col">
              <div className="flex-1 space-y-6 overflow-y-auto px-4 py-4 scroll-smooth">
                {workshopState?.render_requirements && (
                  <div className="mb-4 border-b border-slate-50 bg-slate-50/50 px-4 py-4 rounded-2xl">
                    <WorkshopProgress 
                      requirements={workshopState.render_requirements} 
                      qualityInfo={workshopState.quality_level_info}
                    />
                  </div>
                )}

                {diagnosisReport && (
                  <SurfaceCard tone="muted" padding="none" className="mb-4 overflow-hidden border-violet-100 bg-violet-50/40">
                    <button
                      type="button"
                      onClick={() => setShowDiagnosis(prev => !prev)}
                      className="flex w-full items-center justify-between px-4 py-3 text-left text-sm font-bold text-slate-700 hover:bg-violet-100/50"
                    >
                      <span className="inline-flex items-center gap-2">
                        <div className="h-2 w-2 rounded-full bg-violet-500 shadow-sm shadow-violet-500/30" />
                        진단 결과 요약
                      </span>
                      {showDiagnosis ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
                    </button>
                    <AnimatePresence>
                      {showDiagnosis && (
                        <motion.div
                          initial={{ height: 0, opacity: 0 }}
                          animate={{ height: 'auto', opacity: 1 }}
                          exit={{ height: 0, opacity: 0 }}
                          className="overflow-hidden border-t border-violet-100 px-4 pb-4"
                        >
                          <div className="mt-3 space-y-2">
                            <p className="text-sm font-bold text-slate-900 leading-snug">{diagnosisHeadline}</p>
                            <div className="flex flex-wrap items-center gap-2">
                              {diagnosisRisk && <StatusBadge status={diagnosisRiskStatus}>{diagnosisRiskLabel}</StatusBadge>}
                              <StatusBadge status="neutral">보완 {diagnosisGapCount}개</StatusBadge>
                            </div>
                          </div>
                        </motion.div>
                      )}
                    </AnimatePresence>
                  </SurfaceCard>
                )}

                {limitedModeNotice && (
                  <WorkflowNotice
                    tone="warning"
                    title={limitedModeNotice.title}
                    description={limitedModeNotice.description}
                    className="mb-4 rounded-2xl"
                  />
                )}

                {!isSessionLoading ? (
                  <div className="space-y-6 pb-6">
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
                  <div className="flex h-full items-center justify-center py-20">
                    <Loader2 size={24} className="animate-spin text-blue-600" />
                  </div>
                )}
              </div>

              <div className="border-t border-slate-100 bg-white p-4">
                <div className="flex items-center gap-3">
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
                    className="flex-1 h-12 rounded-2xl border-2 border-slate-200 bg-slate-50 px-4 text-[15px] font-medium text-slate-900 outline-none transition-all placeholder:text-slate-400 focus:border-blue-400 focus:bg-white disabled:opacity-50"
                  />
                  <button
                    type="button"
                    onClick={() => void handleSend()}
                    disabled={!input.trim() || isTyping || !!isSelectingGuidedTopicId || isGuidedActionLoading}
                    className="flex h-12 w-12 items-center justify-center rounded-2xl bg-[#3182f6] text-white shadow-lg shadow-blue-100 transition-all hover:bg-[#1b64da] disabled:bg-slate-200"
                  >
                    {isTyping ? <Loader2 size={20} className="animate-spin" /> : <Send size={20} />}
                  </button>
                </div>
              </div>
            </div>
          </SectionCard>

          <div
            className={cn(
              'flex min-h-0 flex-col h-full bg-slate-50/50 rounded-[2rem] border border-slate-200 overflow-hidden relative',
              mobileView !== 'draft' && 'hidden lg:flex'
            )}
          >
            <div className="absolute top-4 right-6 z-10 flex items-center gap-2">
              <PrimaryButton size="sm" onClick={handleSaveDraft} className="shadow-md">
                <Save size={14} className="mr-1.5" />
                저장
              </PrimaryButton>
              <SecondaryButton size="sm" className="shadow-md bg-white" onClick={() => {
                const blob = new Blob([documentContent], { type: 'text/markdown' });
                const url = URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = fileName.replace('.hwpx', '.md');
                a.click();
                URL.revokeObjectURL(url);
              }}>
                <Download size={14} className="mr-1.5" />
                내보내기
              </SecondaryButton>
            </div>
            
            <div className="flex flex-1 flex-col overflow-hidden p-2 sm:p-4 pt-16 sm:pt-16">
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





