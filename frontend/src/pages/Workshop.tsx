import React, { memo, useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { AnimatePresence, motion } from 'motion/react';
import {
  Bot,
  ChevronDown,
  ChevronUp,
  Download,
  FileText,
  Loader2,
  PanelRightClose,
  PenSquare,
  Presentation,
  Save,
  Send,
  ToggleLeft,
  ToggleRight,
  User,
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
  low: { label: '빠른 ?�답', status: 'success' },
  mid: { label: '균형 모드', status: 'active' },
  high: { label: '?�화 모드', status: 'warning' },
};

const GUIDED_CHAT_GREETING = '?�녕?�세?? ?�떤 주제�?보고?��? ?�성?�볼까요?';
const DIAGNOSIS_RISK_LABEL_MAP: Record<string, string> = {
  safe: '근거 충분',
  warning: '보완 ?�요',
  danger: '집중 보완 ?�요',
};

function formatDiagnosisRiskLabel(value: string | undefined): string {
  const key = String(value || '').trim().toLowerCase();
  return DIAGNOSIS_RISK_LABEL_MAP[key] || '보완 ?�요';
}

function formatDraftAttributionLabel(attribution: WorkshopDraftAttribution): string {
  if (attribution === 'student-authored') return '?�생 ?�성';
  if (attribution === 'ai-inserted-after-approval') return '?�인 ??AI 반영';
  return 'AI ?�안';
}

function normalizeGuidedSuggestions(response: GuidedTopicSuggestionResponse): GuidedTopicSuggestion[] {
  return ensureThreeSuggestions(response).suggestions.slice(0, 3);
}

function formatGuidedSuggestionMessage(response: GuidedTopicSuggestionResponse) {
  const suggestions = normalizeGuidedSuggestions(response);
  const lines = [
    `좋아?? '${response.subject}'�?바탕?�로 ?�생 기록 ?�름??맞는 주제 3가지�?준비했?�요.`,
    '',
    ...suggestions.flatMap((item, index) => {
      const chunk = [
        `${index + 1}. **${item.title}**`,
        `- 추천 ?�유: ${item.why_fit_student}`,
        `- 기록 ?�결: ${item.link_to_record_flow}`,
      ];
      if (item.link_to_target_major_or_university) {
        chunk.push(`- 진로 ?�계: ${item.link_to_target_major_or_university}`);
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
  lines.push('', '??중에??가??마음??가??주제�?골라주세??');
  return lines.join('\n');
}

function formatGuidedSelectionMessage(response: GuidedTopicSelectionResponse) {
  const lines = [
    `?�택??주제??**${response.selected_title}**?�니??`,
    '',
    response.guidance_message,
    '',
    '?�제 진행?�고 ?��? 보고??분량??고르�?바로 개요�??�아?�릴게요.',
  ];
  return lines.join('\n');
}

function formatGuidedPageRangeMessage(response: GuidedPageRangeSelectionResponse) {
  const lines = [
    response.assistant_message,
    '',
    `?�택??분량: **${response.selected_page_range_label}**`,
  ];
  if (response.selected_page_range_note) {
    lines.push(`- 참고: ${response.selected_page_range_note}`);
  }
  lines.push('', '?�음?�로 구성 ?��??�을 골라주세??');
  return lines.join('\n');
}

function formatGuidedStructureMessage(response: GuidedStructureSelectionResponse) {
  return [
    response.assistant_message,
    '',
    `?�택??구성: **${response.selected_structure_label}**`,
    '',
    '가?�드가 거의 ?�났?�니?? ?�음?�로 무엇???�고 ?��?지 ?�려주세??',
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
    title: '??중에??가??마음???�는 주제�?골라주세??',
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
    title: '보고??분량???�택??주세??',
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
    title: '구성 ?��??�을 골라주세??',
    style: 'cards',
    options,
  };
}

function buildNextActionChoiceGroup(options: GuidedChoiceOption[]): GuidedChoiceGroup {
  return {
    id: 'next-action-selection',
    title: '?�음?�로 무엇???�까??',
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
  const greetings = ['?�녕', 'hi', 'hello', 'hey', 'good morning', 'good evening'];

  if (greetings.some(token => clean.includes(token))) {
    return [
      '?�녕?�세?? ?�니?�리 ?�크???�우미입?�다.',
      '',
      '지금�? AI ?�결???�시 불안?�해?? 초안 구조 ?�리?� ?�음 질문 ?�내�?중심?�로 ?�전?�게 ?�어갈게??',
    ].join('\n');
  }

  return [
    '?�재 AI ?�답???�시 지?�되??기본 ?�내 모드�??�환?�어??',
    '',
    '?�래 ?�서?��?보내 주시�?초안 ?�성 ?�름??계속 ?�어�????�어??',
    '1. ?�번 글?�서 ?�루?�는 주제�???문장?�로 ?�어 주세??',
    '2. �?주제�??�정???�유�?간단???�려 주세??',
    '3. 마�?막으�?보고?�에 �??�함?�고 ?��? ?�워??3가지�?말�???주세??',
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
      firebaseUser: auth?.currentUser,
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
          title: '??중에??가??마음???�는 주제�?골라주세??',
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
            <span>분석?�고 ?�어??..</span>
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
              보고??구성 ?�안???�착?�어??
            </p>
            <PrimaryButton
              size="sm"
              className="w-full text-xs py-2 h-auto rounded-lg"
              onClick={() => onApplyDraftPatch(message.draftPatch!)}
            >
              ?�안 ?�용??문서??반영?�기
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
  const [isEditorOpen, setIsEditorOpen] = useState(false);
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
                subject: cachedSubject || '?�구',
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
      toast.error('?�크?�을 불러?��? 못했?�니?? 로컬 모드�??�환?�니??');
      setGuidedPhase('freeform_coauthoring');
      setIsGuidedTopicSelected(true);
      setMessages([{ id: 'fallback', role: 'foli', content: '?�션 ?�결???�패?�습?�다. 로컬?�서 초안 ?�성??진행?�실 ???�습?�다.' }]);
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
        `# [?�구 초안] ${questStart?.title || '??주제'}\n\n## 배경 �?문제?�식\n\n## ?�심 ?�구 ?�용 1\n\n## ?�심 ?�구 ?�용 2\n\n## ?�심 ?�구 ?�용 3\n\n## 결론 �??�음 ?�계`;
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
      setMessages([{ id: 'demo-init', role: 'foli', content: '?�모 모드?�니?? ?�니?�리?�게 질문?�면 초안 ?�성???�어???��??�릴게요.' }]);
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
            toast('?�른 ??��??초안??변경되??최신 ?�용??병합?????�시 ?�?�했?�니??');
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
        toast.success('주제 ?�택??반영?�었?�요. ?�제 분량???�해볼게??');
      } catch (error) {
        console.error('Guided topic selection failed:', error);
        toast.error('주제 ?�택??반영?��? 못했?�니?? ?�시 ?�도??주세??');
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
        toast.error('분량 ?�택??반영?��? 못했?�니?? ?�시 ?�도??주세??');
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
        toast.error('구성 ?�택??반영?��? 못했?�니?? ?�시 ?�도??주세??');
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
          content: '?�생 기록??바탕?�로 주제 3가지�??�리?�고 ?�어?? ?�시�?기다?�주?�요.',
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
          toast.success('?�인???�션 ?�안???�측 구조 초안??반영?�었?�니??');
        }
      } else if (blockedReason === 'student_content_protected') {
        toast('?�생??직접 ?�성???�션?� ?�동 ??��?�기�?막고 ?�어?? ?�용???�인?????�동?�로 반영??주세??');
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
        toast.error(validation.errors[0] || '문서 반영 ?�안??검?�해???�니??');
        return false;
      }

      const result = applyReportPatchToStructuredDraft(structuredDraft, reportPatch, { approved: true });
      if (!result.applied) {
        toast.error('?�생 ?�성 ?�용 보호 ?�책 ?�문??patch�?바로 반영?��? 못했?�니??');
        return false;
      }

      if (editorRef.current) {
        new TiptapEditorAdapter(editorRef.current).applyReportPatch(reportPatch);
      }
      setStructuredDraft(result.next);
      setWorkshopMode(result.next.mode);
      setDocumentContent(structuredDraftToMarkdown(result.next));
      setPendingDraftPatch(null);
      toast.success('?�인??문서 patch�?반영?�습?�다.');
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
          content: '관???�문�??�료�?찾고 ?�어?? 검??결과??바로 문서???��? ?�고 ?�보 카드�?보여?�릴게요.',
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
                    ? `?�료 ?�보 ${result.candidates.length}개�? 찾았?�요. ?�용???�보�?고르�?먼�? 문서 반영 ?�안 카드�?바꿔??보여?�릴게요.`
                    : '검?�된 ?�료 ?�보가 ?�어?? 주제???�워?��? 조금 ??구체?�으�?말해 주세??',
                  researchCandidates: result.candidates,
                  researchSources: result.sources,
                }
              : message,
          ),
        );
      } catch (error) {
        const message = error instanceof Error ? error.message : '?�료 검??�??�류가 발생?�습?�다.';
        console.error('Research candidate search failed:', error);
        toast.error(message);
        setMessages((prev) =>
          prev.map((item) =>
            item.id === pendingId
              ? {
                  ...item,
                  content: `?�료 검?�에 ?�패?�어??\n\n${message}\n\n?�시 ???�시 ?�도?�거??검?�어�???구체?�으�?바꿔 주세??`,
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
              ? `좋아?? ${normalizedSubject}�?진행?�볼게요.\n?�별???�각????주제가 ?�을까요? ?�직 ?�다�??�생 기록 기반?�로 3�?추천?�드릴게??`
              : `좋아?? ${normalizedSubject} 방향?�로 진행?�볼게요.\n?��? ?�각?�둔 ?�구 질문???�다�??�려주세?? ?�으�??�생 기록??바탕?�로 3�?추천?�드릴게??`,
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
              content: '좋아?? ?�각?�둔 주제�???문장?�로 ?�어주시�? �?방향까�? 반영?�서 주제 3가지�??�안?�게??',
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
              content: '주제 카드�??�러 ?�택?�면 바로 분량/구성 ?�계�??�어갈게??',
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
              content: '분량 카드�??�러 ?�택??주세?? ?�택 ??바로 구성 ?��??�을 물어볼게??',
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
              content: '구성 ?��???카드�??�러 ?�택??주세??',
              phase: 'structure_selection',
              structureOptions: guidedStructureOptions,
              choiceGroups: [buildStructureChoiceGroup(guidedStructureOptions)],
            });
          }
          return;
        }
      } catch (error) {
        console.error('Guided setup flow failed:', error);
        toast.error('가?�드 ?�정 �??�류가 발생?�습?�다. ?�시 ?�도??주세??');
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
          toast.error('AI 모델 ?�결??불안?�하???�한 모드 ?�내�??�환?�었?�요.');
        } else if (streamLimitedReason === 'llm_not_configured') {
          toast.error('AI 모델 ?��? ?�버???�정?��? ?�아 ?�한 모드�??�환?�었?�니??');
        }
      }

      const extracted = extractPatchTagFromRaw(raw);
      const resolvedPatch = streamedPatch || extracted.patch;
      const responseContent = extracted.cleaned || raw || accumulated || '?��????�성?��? 못했?�니??';
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
          fallbackContent = `${fallbackContent}\n\n참고 ?�내: ${hint}`;
        }
      } else {
        console.error('AI reply stream failed with unexpected error:', error);
        toast.error('채팅 ?�답 ?�성???�패?�습?�다. ?�시 ???�시 ?�도??주세??');
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
          content: `좋아?? ${rawValue}�?진행?�볼게요.\n?�별???�각????주제가 ?�을까요? ?�직 ?�다�??�생 기록 기반?�로 3�?추천?�드릴게??`,
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
            toast.error('주제 추천??불러?��? 못했?�니?? ?�시 ?�도??주세??');
          }
          return;
        }
        pushGuidedAssistantMessage({
          content: '좋아?? ?�각?�둔 주제�???문장?�로 ?�어주시�?�?방향까�? 반영?�서 3�?주제�??�안?�게??',
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
    toast('문서 반영 ?�안??거절?�습?�다.');
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
    toast('문서 반영 ?�안??거절?�습?�다.');
  }, []);

  const handleRequestPatchRewrite = useCallback(
    (patch: ReviewablePatch, tone: 'simpler' | 'professional' | 'custom') => {
      const instruction =
        tone === 'simpler'
          ? '방금 문서 반영 ?�안?????�게 ?�시 ?�줘. 문서?�는 ?�직 반영?��? 말고 ??patch�??�안?�줘.'
          : tone === 'professional'
            ? '방금 문서 반영 ?�안?????�문?�인 보고??문체�??�시 ?�줘. 문서?�는 ?�직 반영?��? 말고 ??patch�??�안?�줘.'
            : '방금 문서 반영 ?�안???��? ?�정?�서 ?�인?????�도�????��? ?�위??patch�??�시 ?�안?�줘.';
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
        toast.error('?�택???�료 ?�보�?찾을 ???�습?�다.');
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
      toast.success('?�료 ?�보�?문서 반영 ?�안?�로 바꿨?�요. 검?????�인?�면 문서???�어갑니??');
    },
    [documentPatch, researchCandidates],
  );

  const handleRefineResearchCandidate = useCallback(
    async (candidateId: string, message: Message) => {
      const candidate = message.researchCandidates?.find((item) => item.id === candidateId);
      if (!candidate) return;
      try {
        const result = await researchCandidates.refineCandidate(candidateId, `${candidate.title} ??구체?�인 근거`);
        if (!result) return;
        setMessages((prev) =>
          prev.map((item) =>
            item.id === message.id
              ? {
                  ...item,
                  content: `??구체?�한 ?�료 ?�보 ${result.candidates.length}개�? ?�시 찾았?�요.`,
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
        toast.error(error instanceof Error ? error.message : '?�료 ?�보�?구체?�하지 못했?�니??');
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
      toast.success('결과�??�성???�청?�습?�다.');
    } catch (error) {
      console.error('Failed to render draft:', error);
      toast.error('?�성 ?�청???�패?�습?�다.');
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
    toast.success('?�크??초안???�?�했?�요.');
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
      toast.success('?�태�??�데?�트?�습?�다.');
    } catch (error) {
      console.error('Failed to update visual status:', error);
      toast.error('?�태 ?�데?�트 ?�패');
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
      toast.error('?�각 ?�료 ?�성 ?�패');
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
      : '내 핵심 강점 3가지를 근거와 함께 정리해줘';
  const quickPromptOptions = useMemo(() => {
    if (chatbotMode === 'diagnosis') return [];
    if (isProjectBacked && !guidedSetupComplete) return [];

    const prefix = diagnosisHeadline
      ? '최근 진단 아티팩트를 기반으로 '
      : '현재 기록과 대화 문맥을 기반으로 ';

    return [
      {
        label: '강점 요약',
        prompt: `${prefix}학생부 핵심 강점 3가지를 근거와 함께 정리해줘.`,
      },
      {
        label: '약점 보완',
        prompt: `${prefix}가장 먼저 보완해야 할 약점 3가지를 근거와 함께 설명해줘.`,
      },
      {
        label: '탐구 주제',
        prompt: `${prefix}지금 바로 시도할 탐구 주제 3개를 추천해줘.`,
      },
      {
        label: '다음 단계',
        prompt: `${prefix}다음 활동 계획을 주차별로 정리해줘.`,
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
          <div className={cn("flex flex-col min-h-0 flex-1 transition-all duration-500 items-center w-full", isEditorOpen ? "lg:mr-[400px] xl:mr-[500px]" : "")}>
            <div className="w-full max-w-4xl flex-1 flex flex-col relative h-full">
              <div className="absolute top-2 right-4 z-20 hidden lg:block">
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
                  'flex min-h-0 flex-col h-full border-none shadow-none bg-transparent',
                  mobileView !== 'chat' && 'hidden lg:flex'
                )}
                bodyClassName="relative flex min-h-0 flex-1 flex-col overflow-hidden p-0 bg-transparent"
              >
                <div className="flex flex-col h-full bg-slate-50/10 backdrop-blur-md">
                  {/* Messages Area */}
                  <div className="flex-1 overflow-y-auto custom-scrollbar scroll-smooth">
                    <div className="max-w-4xl mx-auto w-full flex flex-col min-h-full">
                      {messages.length === 0 && !isSessionLoading ? (
                        <div className="flex-1 flex flex-col items-center justify-center p-8 text-center animate-in fade-in slide-in-from-bottom-8 duration-1000">
                          <div className="relative mb-10">
                            <div className="absolute -inset-4 bg-gradient-to-r from-violet-500 to-indigo-600 rounded-[36px] blur-2xl opacity-20 animate-pulse"></div>
                            <div className="relative w-24 h-24 rounded-[32px] bg-gradient-to-br from-violet-600 to-indigo-700 flex items-center justify-center shadow-2xl ring-8 ring-indigo-50/50">
                              <Bot size={48} className="text-white" />
                            </div>
                          </div>
                          
                          <h2 className="text-4xl font-black text-slate-900 mb-4 tracking-tight">
                            반가워요! 무엇을 도와드릴까요?
                          </h2>
                          <p className="text-slate-500 max-w-lg leading-relaxed mb-12 text-lg font-medium">
                            학생부 분석부터 리포트 작성까지,<br />
                            당신의 대입 성공을 위한 AI 코파일럿 <span className="text-violet-600 font-bold">Foli</span>입니다.
                          </p>
                          
                          {quickPromptOptions.length > 0 && (
                            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 w-full max-w-2xl px-4">
                              {quickPromptOptions.map((option) => (
                                <button
                                  key={option.label}
                                  onClick={() => void handleSend(option.prompt)}
                                  className="group flex items-start gap-4 p-6 text-left bg-white/80 backdrop-blur-sm border border-slate-200 rounded-[28px] hover:border-violet-400 hover:bg-white hover:shadow-2xl hover:shadow-violet-200/40 transition-all duration-300 transform hover:-translate-y-1"
                                >
                                  <div className="mt-1 w-10 h-10 rounded-2xl bg-slate-50 flex items-center justify-center group-hover:bg-violet-50 transition-colors">
                                    <PenSquare size={20} className="text-slate-400 group-hover:text-violet-600" />
                                  </div>
                                  <div className="flex-1">
                                    <div className="font-bold text-slate-800 text-lg mb-1 group-hover:text-violet-700 transition-colors">{option.label}</div>
                                    <div className="text-slate-400 text-sm font-medium">맞춤형 분석을 시작합니다</div>
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
              <div className="flex items-center gap-2">
                <PrimaryButton size="sm" onClick={handleSaveDraft} className="shadow-sm py-1.5 px-3 h-auto text-xs">
                  <Save size={14} className="mr-1.5" />
                  저장
                </PrimaryButton>
                <SecondaryButton size="sm" className="shadow-sm bg-white py-1.5 px-3 h-auto text-xs" onClick={() => {
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






