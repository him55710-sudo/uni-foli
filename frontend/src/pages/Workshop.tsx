import React, { useEffect, useMemo, useRef, useState } from 'react';
import { AnimatePresence, motion } from 'motion/react';
import {
  Bot,
  BookOpen,
  Download,
  FlaskConical,
  Lock,
  Send,
  Shield,
  ShieldAlert,
  ShieldCheck,
  Sparkles,
  Target,
  ToggleLeft,
  ToggleRight,
  User,
  WandSparkles,
} from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import remarkMath from 'remark-math';
import rehypeKatex from 'rehype-katex';
import 'katex/dist/katex.min.css';
import { useLocation, useParams, useSearchParams } from 'react-router-dom';
import toast from 'react-hot-toast';
import confetti from 'canvas-confetti';
import { auth } from '../lib/firebase';
import { api } from '../lib/api';
import { saveArchiveItem } from '../lib/archiveStore';
import { type QuestStartPayload, readQuestStart, saveQuestStart } from '../lib/questStart';
import { AdvancedPreview } from '../components/AdvancedPreview';
import { ReferenceSearchPanel } from '../components/ReferenceSearchPanel';

export type QualityLevel = 'low' | 'mid' | 'high';

type MessageRole = 'user' | 'poli';

interface Message {
  id: string;
  role: MessageRole;
  content: string;
  suggestedContent?: string;
}

interface WorkshopChoice {
  id: string;
  label: string;
  description?: string | null;
  payload?: Record<string, unknown> | null;
}

interface WorkshopTurn {
  id: string;
  turn_type: string;
  query: string;
  response?: string | null;
  action_payload?: Record<string, unknown> | null;
}

interface PinnedReference {
  id: string;
  text_content: string;
  source_type?: string | null;
  source_id?: string | null;
}

interface WorkshopSession {
  id: string;
  project_id: string;
  quest_id?: string | null;
  status: string;
  context_score: number;
  quality_level: QualityLevel;
  turns: WorkshopTurn[];
  pinned_references: PinnedReference[];
  created_at: string;
  updated_at: string;
}

interface QualityLevelInfo {
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
  starter_mode: string;
  followup_mode: string;
  reference_policy: string;
  reference_intensity: string;
  render_depth: string;
  expression_policy: string;
  advanced_features_allowed: boolean;
  minimum_turn_count: number;
  minimum_reference_count: number;
  render_threshold: number;
}

interface RenderRequirements {
  required_context_score: number;
  minimum_turn_count: number;
  minimum_reference_count: number;
  current_context_score: number;
  current_turn_count: number;
  current_reference_count: number;
  can_render: boolean;
  missing: string[];
}

interface SafetyCheckDimension {
  key: string;
  label: string;
  score: number;
  status: 'ok' | 'warning' | 'critical';
  detail: string;
  matched_count?: number;
  unsupported_count?: number;
}

interface QualityControlMeta {
  schema_version: string;
  requested_level: QualityLevel;
  requested_label: string;
  applied_level: QualityLevel;
  applied_label: string;
  student_fit: string;
  safety_posture: string;
  authenticity_policy: string;
  hallucination_guardrail: string;
  starter_mode: string;
  followup_mode: string;
  reference_policy: string;
  reference_intensity: string;
  render_depth: string;
  expression_policy: string;
  advanced_features_allowed: boolean;
  advanced_features_requested: boolean;
  advanced_features_applied: boolean;
  advanced_features_reason?: string | null;
  minimum_turn_count: number;
  minimum_reference_count: number;
  turn_count: number;
  reference_count: number;
  safety_score?: number | null;
  downgraded: boolean;
  summary?: string | null;
  flags: Record<string, string>;
  checks: Record<string, SafetyCheckDimension>;
  repair_applied: boolean;
  repair_strategy?: string | null;
}

interface VisualSpec {
  type: string;
  chart_spec?: {
    title: string;
    type: 'bar' | 'line';
    data: { name: string; value: number }[];
  };
}

interface MathExpression {
  label: string;
  latex: string;
  context?: string;
}

interface DraftArtifact {
  id?: string;
  report_markdown?: string | null;
  teacher_record_summary_500?: string | null;
  student_submission_note?: string | null;
  evidence_map?: Record<string, { 근거?: string; 출처?: string }>;
  visual_specs?: VisualSpec[];
  math_expressions?: MathExpression[];
  quality_level_applied?: string | null;
  safety_score?: number | null;
  safety_flags?: Record<string, string> | null;
  quality_downgraded?: boolean;
  quality_control_meta?: QualityControlMeta | null;
}

interface SafetyMeta {
  safety_score: number;
  flags: Record<string, string>;
  recommended_level: QualityLevel;
  downgraded: boolean;
  summary: string;
  checks?: Record<string, SafetyCheckDimension>;
}

interface WorkshopStateResponse {
  session: WorkshopSession;
  starter_choices: WorkshopChoice[];
  followup_choices: WorkshopChoice[];
  message?: string | null;
  quality_level_info: QualityLevelInfo;
  available_quality_levels: QualityLevelInfo[];
  render_requirements: RenderRequirements;
  latest_artifact?: DraftArtifact | null;
}

interface StreamTokenResponse {
  stream_token: string;
  workshop_id: string;
  expires_in: number;
}

const QUALITY_META: Record<
  QualityLevel,
  {
    border: string;
    bg: string;
    text: string;
    accent: string;
  }
> = {
  low: {
    border: 'border-emerald-200',
    bg: 'bg-emerald-50',
    text: 'text-emerald-700',
    accent: 'bg-emerald-500',
  },
  mid: {
    border: 'border-blue-200',
    bg: 'bg-blue-50',
    text: 'text-blue-700',
    accent: 'bg-blue-500',
  },
  high: {
    border: 'border-violet-200',
    bg: 'bg-violet-50',
    text: 'text-violet-700',
    accent: 'bg-violet-500',
  },
};

const FALLBACK_QUALITY_OPTIONS: QualityLevelInfo[] = [
  {
    level: 'low',
    label: '안전형',
    emoji: '🛡️',
    color: 'emerald',
    description: '교과 개념 중심, 검증 가능한 사실 우선',
    detail: '학생이 실제로 할 수 있는 범위만 남깁니다.',
    student_fit: '교과 개념 충실, 안전형',
    safety_posture: '교과 개념과 검증 가능성을 최우선으로 둡니다.',
    authenticity_policy: '학생이 실제로 한 활동과 확인된 사실만 남깁니다.',
    hallucination_guardrail: '없는 실험, 없는 수치, 없는 경험은 자동 차단합니다.',
    starter_mode: '핵심 개념과 수행 가능 범위를 먼저 정리',
    followup_mode: '용어를 쉽게 풀고 다음 행동을 좁게 제안',
    reference_policy: 'optional',
    reference_intensity: 'none',
    render_depth: '교과 개념 설명 + 가능한 활동 정리',
    expression_policy: '짧고 정확한 문장',
    advanced_features_allowed: false,
    minimum_turn_count: 2,
    minimum_reference_count: 0,
    render_threshold: 45,
  },
  {
    level: 'mid',
    label: '표준형',
    emoji: '📝',
    color: 'blue',
    description: '교과 응용과 간단한 확장을 균형 있게 반영',
    detail: '한 학기 안에 끝낼 수 있는 범위를 전제로 합니다.',
    student_fit: '교과 응용 + 간단한 확장',
    safety_posture: '응용은 허용하되 결론의 세기를 보수적으로 유지합니다.',
    authenticity_policy: '학생이 말한 활동과 간단한 자료 해석만 허용합니다.',
    hallucination_guardrail: '수행과 계획, 사실과 해석을 분리해서 서술합니다.',
    starter_mode: '질문 구체화와 증거 계획 설계 중심',
    followup_mode: '근거 보강과 결론 세기 조절 중심',
    reference_policy: 'recommended',
    reference_intensity: 'light',
    render_depth: '교과 응용 + 간단한 분석',
    expression_policy: '설명과 해석의 균형',
    advanced_features_allowed: false,
    minimum_turn_count: 3,
    minimum_reference_count: 0,
    render_threshold: 60,
  },
  {
    level: 'high',
    label: '심화형',
    emoji: '🔬',
    color: 'violet',
    description: '심화형이지만 학생 실제 맥락과 근거에만 기대어 작성',
    detail: '참고자료와 실제 경험이 없으면 더 안전한 수준으로 자동 조정됩니다.',
    student_fit: '심화형이지만 학생 실제 맥락 기반',
    safety_posture: '심화 연결은 허용하지만 학생 맥락과 출처 분리를 강제합니다.',
    authenticity_policy: '학생 경험, 해석, 외부 근거를 반드시 분리합니다.',
    hallucination_guardrail: '근거가 빈약하면 자동 강등 후 안전 재작성합니다.',
    starter_mode: '심화 질문을 실제 경험과 자료로 좁힘',
    followup_mode: '주장·근거·출처를 분리해 심화를 안전하게 유지',
    reference_policy: 'required',
    reference_intensity: 'required',
    render_depth: '심화 연결 + 출처 기반 해석',
    expression_policy: '전문성보다 학생 현실감 우선',
    advanced_features_allowed: true,
    minimum_turn_count: 4,
    minimum_reference_count: 1,
    render_threshold: 75,
  },
];

function extractSuggestedContent(raw: string): { clean: string; suggestion?: string } {
  const match = raw.match(/\[CONTENT\]([\s\S]*?)\[\/CONTENT\]/i);
  if (!match) {
    return { clean: raw.trim() };
  }

  const clean = raw.replace(match[0], '').trim();
  return {
    clean: clean || '문서에 바로 넣을 수 있는 초안을 준비했습니다.',
    suggestion: match[1].trim(),
  };
}

async function streamPoliReply(projectId: string | undefined, message: string): Promise<string> {
  const baseUrl = import.meta.env.VITE_API_URL || 'http://localhost:8000';
  const token = auth?.currentUser ? await auth.currentUser.getIdToken() : null;
  const response = await fetch(`${baseUrl}/api/v1/drafts/chat/stream`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: JSON.stringify({ project_id: projectId, message, reference_materials: [] }),
  });

  if (!response.ok || !response.body) {
    throw new Error(`Chat stream failed with status ${response.status}`);
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';
  let full = '';

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const events = buffer.split('\n\n');
    buffer = events.pop() ?? '';

    for (const event of events) {
      const line = event.split('\n').find((entry) => entry.trim().startsWith('data:'));
      if (!line) continue;
      try {
        const parsed = JSON.parse(line.replace(/^data:\s*/, '')) as { token?: string };
        if (parsed.token) full += parsed.token;
      } catch {
        // Ignore malformed chunks.
      }
    }
  }

  return full.trim();
}

function resolveQuestStart(projectId: string | undefined, routeState: unknown): QuestStartPayload | null {
  const stateQuestStart = (routeState as { questStart?: QuestStartPayload } | null)?.questStart;
  return stateQuestStart || readQuestStart(projectId);
}

function getApiBaseUrl() {
  return import.meta.env.VITE_API_URL || 'http://localhost:8000';
}

function workshopStorageKey(projectId?: string, questId?: string | null) {
  return `polio_workshop_session:${projectId ?? 'none'}:${questId ?? 'none'}`;
}

function parseApiError(error: unknown, fallback: string) {
  const typed = error as { response?: { data?: { detail?: unknown } } };
  const detail = typed.response?.data?.detail;
  if (typeof detail === 'string') return detail;
  if (detail && typeof detail === 'object') {
    const message = (detail as { message?: string }).message;
    if (message) return message;
  }
  return fallback;
}

function buildInitialDocument(questStart: QuestStartPayload | null, initialMajor: string) {
  return (
    questStart?.document_seed_markdown ||
    [`# ${initialMajor} 탐구 보고서`, '', '## 1. 탐구 동기', '', '(여기에 안전 점검을 거친 초안이 채워집니다)'].join('\n')
  );
}

function buildWelcomeMessage(questStart: QuestStartPayload | null, initialMajor: string, extra?: string | null) {
  const base = questStart
    ? `${questStart.workshop_intro}\n\n학생 수준과 안전성을 우선으로 starter choice부터 좁혀 보겠습니다.`
    : `${initialMajor} 주제로 학생 수준에 맞는 안전한 탐구 초안을 만들어 봅시다.`;
  return extra ? `${base}\n\n${extra}` : base;
}

function messagesFromTurns(
  turns: WorkshopTurn[],
  welcome: string,
): Message[] {
  const items: Message[] = [{ id: 'welcome', role: 'poli', content: welcome }];
  turns.forEach((turn) => {
    items.push({
      id: `user-${turn.id}`,
      role: 'user',
      content: String(turn.action_payload?.display_label || turn.query),
    });
    if (turn.response) {
      items.push({
        id: `poli-${turn.id}`,
        role: 'poli',
        content: turn.response,
      });
    }
  });
  return items;
}

function qualityInfoMap(options: QualityLevelInfo[]) {
  return options.reduce<Record<QualityLevel, QualityLevelInfo>>((acc, option) => {
    acc[option.level] = option;
    return acc;
  }, {} as Record<QualityLevel, QualityLevelInfo>);
}

export function Workshop() {
  const { projectId } = useParams();
  const [searchParams] = useSearchParams();
  const location = useLocation();
  const questStart = useMemo(() => resolveQuestStart(projectId, location.state), [location.state, projectId]);
  const initialMajor = searchParams.get('major') || questStart?.target_major || '희망 전공';

  const [messages, setMessages] = useState<Message[]>(() => [
    {
      id: 'welcome',
      role: 'poli',
      content: buildWelcomeMessage(questStart, initialMajor),
    },
  ]);
  const [input, setInput] = useState('');
  const [referenceInput, setReferenceInput] = useState('');
  const [isTyping, setIsTyping] = useState(false);
  const [isExporting, setIsExporting] = useState(false);
  const [isRendering, setIsRendering] = useState(false);
  const [isSessionLoading, setIsSessionLoading] = useState(false);
  const [qualityLevel, setQualityLevel] = useState<QualityLevel>(() => {
    return (localStorage.getItem('polio_quality_level') as QualityLevel) || 'mid';
  });
  const [showQualityPanel, setShowQualityPanel] = useState(false);
  const [workshopState, setWorkshopState] = useState<WorkshopStateResponse | null>(null);
  const [renderArtifact, setRenderArtifact] = useState<DraftArtifact | null>(null);
  const [safetyMeta, setSafetyMeta] = useState<SafetyMeta | null>(null);
  const [renderStatusText, setRenderStatusText] = useState('안전 점검 기반 렌더를 아직 시작하지 않았습니다.');
  const [documentContent, setDocumentContent] = useState<string>(() => buildInitialDocument(questStart, initialMajor));
  const [flyingBlock, setFlyingBlock] = useState<{ id: string; content: string } | null>(null);
  const [advancedMode, setAdvancedMode] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const eventSourceRef = useRef<EventSource | null>(null);

  const fileName = useMemo(() => {
    const base = (questStart?.title || initialMajor).replace(/[^\w\-\uAC00-\uD7A3]+/g, '_');
    return `${base || 'polio'}_보고서.hwpx`;
  }, [initialMajor, questStart?.title]);

  const qualityOptions = workshopState?.available_quality_levels?.length
    ? workshopState.available_quality_levels
    : FALLBACK_QUALITY_OPTIONS;
  const qualityInfoByLevel = useMemo(() => qualityInfoMap(qualityOptions), [qualityOptions]);
  const activeQualityInfo = qualityInfoByLevel[qualityLevel] || FALLBACK_QUALITY_OPTIONS[1];
  const canUseAdvancedMode = qualityLevel === 'high' && activeQualityInfo.advanced_features_allowed;
  const starterChoices = workshopState?.starter_choices ?? [];
  const followupChoices = workshopState?.followup_choices ?? [];
  const pinnedReferences = workshopState?.session.pinned_references ?? [];
  const renderRequirements = workshopState?.render_requirements ?? {
    required_context_score: activeQualityInfo.render_threshold,
    minimum_turn_count: activeQualityInfo.minimum_turn_count,
    minimum_reference_count: activeQualityInfo.minimum_reference_count,
    current_context_score: 0,
    current_turn_count: 0,
    current_reference_count: 0,
    can_render: false,
    missing: [],
  };
  const qualityChecks = Object.values(renderArtifact?.quality_control_meta?.checks || safetyMeta?.checks || {});
  const isProjectBacked = Boolean(projectId);

  useEffect(() => {
    if (questStart) saveQuestStart(questStart);
  }, [questStart]);

  useEffect(() => {
    if (!canUseAdvancedMode && advancedMode) {
      setAdvancedMode(false);
    }
  }, [advancedMode, canUseAdvancedMode]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isTyping]);

  useEffect(() => {
    return () => {
      eventSourceRef.current?.close();
    };
  }, []);

  useEffect(() => {
    if (!projectId) return;

    const key = workshopStorageKey(projectId, questStart?.quest_id);
    const savedWorkshopId = sessionStorage.getItem(key);
    setIsSessionLoading(true);

    const loadExisting = async (workshopId: string) => {
      const state = await api.get<WorkshopStateResponse>(`/api/v1/workshops/${workshopId}`);
      setWorkshopState(state);
      setQualityLevel(state.session.quality_level);
      localStorage.setItem('polio_quality_level', state.session.quality_level);
      setMessages(messagesFromTurns(state.session.turns, buildWelcomeMessage(questStart, initialMajor, state.message)));
      if (state.latest_artifact?.report_markdown) {
        setDocumentContent(state.latest_artifact.report_markdown);
        setRenderArtifact(state.latest_artifact);
        if (state.latest_artifact.safety_score != null) {
          setSafetyMeta({
            safety_score: state.latest_artifact.safety_score,
            flags: state.latest_artifact.safety_flags || {},
            recommended_level: (state.latest_artifact.quality_level_applied as QualityLevel) || state.session.quality_level,
            downgraded: Boolean(state.latest_artifact.quality_downgraded),
            summary: state.latest_artifact.quality_control_meta?.summary || '저장된 안전 점검 결과를 불러왔습니다.',
            checks: state.latest_artifact.quality_control_meta?.checks || {},
          });
        }
      }
      setRenderStatusText(
        state.latest_artifact?.quality_control_meta?.summary ||
          '현재 세션 기준으로 안전 점검 메타데이터를 불러왔습니다.',
      );
    };

    const createNew = async () => {
      const state = await api.post<WorkshopStateResponse>('/api/v1/workshops', {
        project_id: projectId,
        quest_id: questStart?.quest_id || null,
        quality_level: qualityLevel,
      });
      sessionStorage.setItem(key, state.session.id);
      setWorkshopState(state);
      setQualityLevel(state.session.quality_level);
      localStorage.setItem('polio_quality_level', state.session.quality_level);
      setMessages([{ id: 'welcome', role: 'poli', content: buildWelcomeMessage(questStart, initialMajor, state.message) }]);
      setRenderStatusText('워크샵 세션을 만들었습니다. 맥락을 모은 뒤 안전 초안을 생성할 수 있습니다.');
    };

    const run = async () => {
      try {
        if (savedWorkshopId) {
          await loadExisting(savedWorkshopId);
          return;
        }
        await createNew();
      } catch (error) {
        console.error('Failed to initialize workshop:', error);
        sessionStorage.removeItem(key);
        toast.error('워크샵 세션을 불러오지 못했습니다.');
      } finally {
        setIsSessionLoading(false);
      }
    };

    void run();
  }, [initialMajor, projectId, questStart]);

  const applyContentToDocument = (content: string) => {
    setFlyingBlock({ id: crypto.randomUUID(), content });
    setTimeout(() => {
      setDocumentContent((prev) =>
        prev.includes('(여기에 안전 점검을 거친 초안이 채워집니다)')
          ? prev.replace('(여기에 안전 점검을 거친 초안이 채워집니다)', `${content}\n\n(여기에 안전 점검을 거친 초안이 채워집니다)`)
          : `${prev}\n\n${content}`,
      );
      setFlyingBlock(null);
    }, 700);
  };

  const appendConversation = (userContent: string, poliContent: string) => {
    setMessages((prev) => [
      ...prev,
      { id: crypto.randomUUID(), role: 'user', content: userContent },
      { id: crypto.randomUUID(), role: 'poli', content: poliContent },
    ]);
  };

  const syncStateAfterInteraction = (state: WorkshopStateResponse) => {
    const wasReady = workshopState?.render_requirements.can_render;
    setWorkshopState(state);
    if (!wasReady && state.render_requirements.can_render) {
      toast.success('현재 수준 기준으로 렌더링 가능한 맥락이 모였습니다.');
    }
  };

  const handleChoiceSelect = async (choice: WorkshopChoice) => {
    if (!workshopState || isTyping) return;
    setIsTyping(true);
    try {
      const state = await api.post<WorkshopStateResponse>(
        `/api/v1/workshops/${workshopState.session.id}/choices`,
        {
          choice_id: choice.id,
          label: choice.label,
          payload: choice.payload,
        },
      );
      appendConversation(choice.label, state.message || '선택 내용을 반영했습니다.');
      syncStateAfterInteraction(state);
    } catch (error) {
      console.error('Failed to record choice:', error);
      toast.error(parseApiError(error, '선택 내용을 저장하지 못했습니다.'));
    } finally {
      setIsTyping(false);
    }
  };

  const handleSend = async (overrideMessage?: string) => {
    const userText = (overrideMessage ?? input).trim();
    if (!userText || isTyping) return;
    if (!overrideMessage) setInput('');

    if (!isProjectBacked || !workshopState) {
      setMessages((prev) => [...prev, { id: crypto.randomUUID(), role: 'user', content: userText }]);
      setIsTyping(true);
      const draftId = crypto.randomUUID();
      setMessages((prev) => [...prev, { id: draftId, role: 'poli', content: '' }]);
      try {
        const rawReply = await streamPoliReply(projectId, userText);
        const parsed = extractSuggestedContent(rawReply || '지원 가능한 초안을 만들지 못했습니다.');
        setMessages((prev) =>
          prev.map((message) =>
            message.id === draftId
              ? { ...message, content: parsed.clean, suggestedContent: parsed.suggestion }
              : message,
          ),
        );
      } catch (error) {
        console.error('Chat error:', error);
        setMessages((prev) =>
          prev.map((message) =>
            message.id === draftId
              ? { ...message, content: '응답을 가져오지 못했습니다. 입력을 조금 더 구체적으로 다시 보내 주세요.' }
              : message,
          ),
        );
        toast.error('워크샵 응답을 가져오지 못했습니다.');
      } finally {
        setIsTyping(false);
      }
      return;
    }

    setIsTyping(true);
    try {
      const state = await api.post<WorkshopStateResponse>(
        `/api/v1/workshops/${workshopState.session.id}/messages`,
        { message: userText },
      );
      appendConversation(userText, state.message || '입력한 내용을 워크샵 맥락에 반영했습니다.');
      syncStateAfterInteraction(state);
    } catch (error) {
      console.error('Failed to send workshop message:', error);
      toast.error(parseApiError(error, '메시지를 저장하지 못했습니다.'));
    } finally {
      setIsTyping(false);
    }
  };

  const handlePinReference = async () => {
    const text = referenceInput.trim();
    if (!text || !workshopState) return;
    try {
      const state = await api.post<WorkshopStateResponse>(
        `/api/v1/workshops/${workshopState.session.id}/references/pin`,
        {
          text_content: text,
          source_type: 'manual_note',
        },
      );
      setReferenceInput('');
      syncStateAfterInteraction(state);
      toast.success('참고자료를 고정했습니다.');
    } catch (error) {
      console.error('Failed to pin reference:', error);
      toast.error(parseApiError(error, '참고자료를 고정하지 못했습니다.'));
    }
  };

  const handleQualityChange = async (level: QualityLevel) => {
    localStorage.setItem('polio_quality_level', level);
    setQualityLevel(level);
    setShowQualityPanel(false);

    if (!workshopState) {
      toast(`${qualityInfoByLevel[level]?.emoji || '📝'} ${qualityInfoByLevel[level]?.label || level}`, {
        duration: 1800,
      });
      return;
    }

    try {
      const state = await api.patch<WorkshopStateResponse>(
        `/api/v1/workshops/${workshopState.session.id}/quality-level`,
        { quality_level: level },
      );
      setWorkshopState(state);
      setQualityLevel(state.session.quality_level);
      toast.success(
        `${state.quality_level_info.label} 기준으로 starter/follow-up과 렌더 조건을 다시 맞췄습니다.`,
      );
    } catch (error) {
      console.error('Failed to change quality level:', error);
      toast.error(parseApiError(error, '품질 수준을 변경하지 못했습니다.'));
    }
  };

  const handleRender = async () => {
    if (!workshopState || isRendering) return;
    const requestedAdvancedMode = canUseAdvancedMode && advancedMode;
    const ragSource = requestedAdvancedMode ? 'both' : 'semantic';
    setIsRendering(true);
    setRenderStatusText('안전 점검 기반 렌더링을 준비하고 있습니다.');
    setSafetyMeta(null);
    eventSourceRef.current?.close();

    try {
      const render = await api.post<{ artifact_id: string; status: string }>(
        `/api/v1/workshops/${workshopState.session.id}/render`,
        { force: false, advanced_mode: requestedAdvancedMode, rag_source: ragSource },
      );
      const tokenPayload = await api.post<StreamTokenResponse>(
        `/api/v1/workshops/${workshopState.session.id}/stream-token`,
      );
      const url = `${getApiBaseUrl()}/api/v1/workshops/${workshopState.session.id}/events?stream_token=${encodeURIComponent(
        tokenPayload.stream_token,
      )}&artifact_id=${encodeURIComponent(render.artifact_id)}&advanced_mode=${requestedAdvancedMode ? 'true' : 'false'}&rag_source=${encodeURIComponent(ragSource)}`;
      const source = new EventSource(url);
      eventSourceRef.current = source;

      source.addEventListener('render.started', (event) => {
        const payload = JSON.parse((event as MessageEvent).data) as { message?: string };
        setRenderStatusText(payload.message || '렌더링을 시작했습니다.');
      });

      source.addEventListener('render.progress', (event) => {
        const payload = JSON.parse((event as MessageEvent).data) as { message?: string };
        setRenderStatusText(payload.message || '렌더링 중입니다.');
      });

      source.addEventListener('safety.checked', (event) => {
        const payload = JSON.parse((event as MessageEvent).data) as SafetyMeta;
        setSafetyMeta(payload);
        setRenderStatusText(payload.summary || '안전성 점검을 완료했습니다.');
      });

      source.addEventListener('artifact.ready', (event) => {
        const payload = JSON.parse((event as MessageEvent).data) as DraftArtifact & {
          quality_control?: QualityControlMeta;
          safety?: {
            score: number;
            flags: Record<string, string>;
            recommended_level: QualityLevel;
            downgraded: boolean;
            summary: string;
            checks?: Record<string, SafetyCheckDimension>;
          };
        };
        setDocumentContent(
          payload.report_markdown || buildInitialDocument(questStart, initialMajor),
        );
        const nextArtifact: DraftArtifact = {
          report_markdown: payload.report_markdown,
          teacher_record_summary_500: payload.teacher_record_summary_500,
          student_submission_note: payload.student_submission_note,
          evidence_map: payload.evidence_map,
          visual_specs: payload.visual_specs,
          math_expressions: payload.math_expressions,
          quality_control_meta: payload.quality_control || null,
        };
        setRenderArtifact(nextArtifact);
        if (payload.safety) {
          setSafetyMeta({
            safety_score: payload.safety.score,
            flags: payload.safety.flags,
            recommended_level: payload.safety.recommended_level,
            downgraded: payload.safety.downgraded,
            summary: payload.safety.summary,
            checks: payload.safety.checks,
          });
        }
        setMessages((prev) => [
          ...prev,
          {
            id: crypto.randomUUID(),
            role: 'poli',
            content:
              payload.quality_control?.summary ||
              '안전 점검을 거친 최종 초안을 문서 프리뷰에 반영했습니다.',
          },
        ]);
      });

      source.addEventListener('render.completed', () => {
        setIsRendering(false);
        setRenderStatusText('안전 점검을 마친 초안이 준비되었습니다.');
        source.close();
        eventSourceRef.current = null;
        toast.success('안전 점검을 거친 초안을 생성했습니다.');
      });

      source.onerror = () => {
        setIsRendering(false);
        setRenderStatusText('이벤트 스트림 연결이 종료되었습니다.');
        source.close();
        eventSourceRef.current = null;
      };
    } catch (error) {
      console.error('Failed to render workshop artifact:', error);
      setIsRendering(false);
      setRenderStatusText('렌더링을 시작하지 못했습니다.');
      toast.error(parseApiError(error, '안전 초안을 생성하지 못했습니다.'));
    }
  };

  const handleExport = async () => {
    if (isExporting) return;
    setIsExporting(true);
    const loadingId = toast.loading('문서를 내보내는 중입니다...');

    try {
      if (projectId) {
        const blob = await api.post<Blob>(
          `/api/v1/projects/${projectId}/export`,
          { content_markdown: documentContent },
          { responseType: 'blob' },
        );
        const url = window.URL.createObjectURL(new Blob([blob]));
        const link = document.createElement('a');
        link.href = url;
        link.download = fileName;
        document.body.appendChild(link);
        link.click();
        link.remove();
        window.URL.revokeObjectURL(url);
      } else {
        const fallbackBlob = new Blob([documentContent], { type: 'text/plain;charset=utf-8' });
        const url = window.URL.createObjectURL(fallbackBlob);
        const link = document.createElement('a');
        link.href = url;
        link.download = fileName;
        document.body.appendChild(link);
        link.click();
        link.remove();
        window.URL.revokeObjectURL(url);
      }

      saveArchiveItem({
        id: crypto.randomUUID(),
        projectId: projectId ?? null,
        title: fileName.replace('.hwpx', ''),
        subject: initialMajor,
        createdAt: new Date().toISOString(),
        contentMarkdown: documentContent,
      });

      toast.success('문서를 저장했습니다.', { id: loadingId });
      confetti({ particleCount: 100, spread: 56, origin: { y: 0.62 } });
    } catch (error) {
      console.error('Export error:', error);
      toast.error('문서를 내보내지 못했습니다.', { id: loadingId });
    } finally {
      setIsExporting(false);
    }
  };

  return (
    <div className="mx-auto flex h-[calc(100vh-8rem)] max-w-7xl flex-col gap-6 overflow-hidden px-4 pb-8 sm:px-6 lg:flex-row lg:px-8">
      <div className="flex h-[50vh] w-full flex-col overflow-hidden rounded-3xl border border-slate-100 bg-white shadow-sm lg:h-full lg:w-[38%]">
        <div className="border-b border-slate-100 bg-white/90 px-6 py-5 backdrop-blur-sm">
          {questStart ? (
            <div className="mb-4 rounded-3xl border border-blue-200 bg-blue-50 p-4">
              <div className="mb-2 flex items-center justify-between gap-3">
                <div>
                  <p className="text-xs font-black uppercase tracking-[0.18em] text-blue-500">Quest Start</p>
                  <h2 className="break-keep text-lg font-black text-slate-900">{questStart.title}</h2>
                </div>
                <div className="rounded-full border border-blue-200 bg-white px-3 py-1 text-xs font-black text-blue-700">
                  {questStart.subject}
                </div>
              </div>
              <p className="text-sm font-medium leading-relaxed text-slate-700">{questStart.expected_record_impact}</p>
            </div>
          ) : null}

          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl border border-blue-100 bg-blue-50 text-blue-500 shadow-sm">
              <Bot size={20} />
            </div>
            <div className="min-w-0 flex-1">
              <h2 className="text-base font-extrabold text-slate-800">Poli 작업실</h2>
              <p className="text-xs font-medium text-slate-500">학생 수준 맞춤 + 안전성 기반 워크샵</p>
            </div>
            <div className="relative">
              <button
                type="button"
                onClick={() => setShowQualityPanel((previous) => !previous)}
                className={`flex items-center gap-1.5 rounded-xl border px-2.5 py-1.5 text-xs font-extrabold transition-all ${
                  QUALITY_META[qualityLevel].border
                } ${QUALITY_META[qualityLevel].bg} ${QUALITY_META[qualityLevel].text}`}
              >
                <span>{activeQualityInfo.emoji}</span>
                <span>{activeQualityInfo.label}</span>
              </button>
              <AnimatePresence>
                {showQualityPanel ? (
                  <motion.div
                    initial={{ opacity: 0, y: -6, scale: 0.97 }}
                    animate={{ opacity: 1, y: 0, scale: 1 }}
                    exit={{ opacity: 0, y: -4, scale: 0.97 }}
                    className="absolute right-0 top-10 z-50 w-80 rounded-2xl border border-slate-100 bg-white p-3 shadow-2xl"
                  >
                    <p className="mb-2 px-1 text-[10px] font-black uppercase tracking-widest text-slate-400">수준 선택</p>
                    {qualityOptions.map((option) => {
                      const tone = QUALITY_META[option.level];
                      const active = qualityLevel === option.level;
                      return (
                        <button
                          key={option.level}
                          type="button"
                          onClick={() => {
                            void handleQualityChange(option.level);
                          }}
                          className={`mb-1.5 flex w-full items-start gap-3 rounded-xl border px-3 py-2.5 text-left transition-all last:mb-0 ${
                            active ? `${tone.border} ${tone.bg}` : 'border-transparent hover:bg-slate-50'
                          }`}
                        >
                          <span className="mt-0.5 text-lg">{option.emoji}</span>
                          <div className="min-w-0">
                            <p className={`text-sm font-extrabold ${active ? tone.text : 'text-slate-700'}`}>
                              {option.label}
                            </p>
                            <p className="mt-0.5 text-[11px] font-medium leading-snug text-slate-500">
                              {option.detail}
                            </p>
                            <p className="mt-1 text-[11px] font-medium leading-snug text-slate-500">
                              {option.safety_posture}
                            </p>
                            <p className="mt-1 text-[10px] font-bold uppercase tracking-[0.18em] text-slate-400">
                              {option.reference_intensity} refs · {option.minimum_turn_count} turns minimum · {option.advanced_features_allowed ? 'advanced on' : 'advanced off'}
                            </p>
                          </div>
                          {active ? <div className={`ml-auto mt-2 h-2.5 w-2.5 rounded-full ${tone.accent}`} /> : null}
                        </button>
                      );
                    })}
                  </motion.div>
                ) : null}
              </AnimatePresence>
            </div>
          </div>

          <div className={`mt-4 rounded-2xl border px-4 py-3 ${QUALITY_META[qualityLevel].border} ${QUALITY_META[qualityLevel].bg}`}>
            <div className="flex items-center justify-between gap-3">
              <div>
                <p className={`text-xs font-black uppercase tracking-[0.18em] ${QUALITY_META[qualityLevel].text}`}>
                  {activeQualityInfo.student_fit}
                </p>
                <p className="mt-1 text-sm font-medium leading-relaxed text-slate-600">
                  {activeQualityInfo.description}
                </p>
              </div>
              <div className="rounded-full border border-white/80 bg-white px-3 py-1 text-[11px] font-black text-slate-600">
                {renderRequirements.current_turn_count}/{renderRequirements.minimum_turn_count} turns
              </div>
            </div>
            <div className="mt-3 grid gap-2 text-[11px] font-bold text-slate-500 sm:grid-cols-2">
              <div className="rounded-xl border border-white/80 bg-white/90 px-3 py-2">
                Starter: {activeQualityInfo.starter_mode}
              </div>
              <div className="rounded-xl border border-white/80 bg-white/90 px-3 py-2">
                Render: {activeQualityInfo.render_depth}
              </div>
              <div className="rounded-xl border border-white/80 bg-white/90 px-3 py-2">
                Realism: {activeQualityInfo.authenticity_policy}
              </div>
              <div className="rounded-xl border border-white/80 bg-white/90 px-3 py-2">
                Guardrail: {activeQualityInfo.hallucination_guardrail}
              </div>
            </div>
          </div>
        </div>

        <div className="hide-scrollbar flex-1 space-y-6 overflow-y-auto bg-slate-50/50 p-4 sm:p-6">
          {!isProjectBacked ? (
            <div className="rounded-2xl border border-amber-200 bg-amber-50 p-4 text-sm font-medium leading-relaxed text-amber-900">
              프로젝트 없이 들어온 빠른 대화 모드입니다. 학생 수준 맞춤 렌더링, 참고자료 고정, 안전 점검 메타데이터는
              프로젝트 기반 워크샵에서만 활성화됩니다.
            </div>
          ) : null}

          <AnimatePresence>
            {messages.map((message) => (
              <motion.div
                key={message.id}
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                className={`flex gap-3 ${message.role === 'user' ? 'flex-row-reverse' : ''}`}
              >
                <div
                  className={`flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-xl ${
                    message.role === 'user'
                      ? 'border border-slate-200 bg-white text-slate-400'
                      : 'bg-blue-500 text-white'
                  }`}
                >
                  {message.role === 'user' ? <User size={18} /> : <span className="text-lg font-extrabold">P</span>}
                </div>
                <div
                  className={`max-w-[82%] rounded-2xl p-4 text-sm leading-relaxed shadow-sm ${
                    message.role === 'user'
                      ? 'rounded-tr-sm bg-slate-800 text-white'
                      : 'rounded-tl-sm border border-slate-100 bg-white text-slate-700'
                  }`}
                >
                  <ReactMarkdown remarkPlugins={[remarkMath]} rehypePlugins={[rehypeKatex]}>
                    {message.content}
                  </ReactMarkdown>
                  {message.suggestedContent ? (
                    <div className="mt-4 border-t border-slate-100 pt-4 text-right">
                      <button
                        type="button"
                        onClick={() => applyContentToDocument(message.suggestedContent!)}
                        className="inline-flex items-center gap-1.5 rounded-xl border border-blue-100 bg-blue-50 px-3 py-2 text-xs font-black text-blue-600"
                      >
                        <Sparkles size={14} />
                        문서에 적용
                      </button>
                    </div>
                  ) : null}
                </div>
              </motion.div>
            ))}
          </AnimatePresence>

          {isTyping ? (
            <div className="flex gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-blue-500 text-white">
                <span className="text-lg font-extrabold">P</span>
              </div>
              <div className="flex items-center gap-1.5 rounded-2xl border border-slate-100 bg-white p-5">
                <div className="h-2.5 w-2.5 animate-bounce rounded-full bg-blue-200" />
                <div className="h-2.5 w-2.5 animate-bounce rounded-full bg-blue-300 [animation-delay:150ms]" />
                <div className="h-2.5 w-2.5 animate-bounce rounded-full bg-blue-400 [animation-delay:300ms]" />
              </div>
            </div>
          ) : null}

          <div ref={messagesEndRef} />
        </div>

        {isProjectBacked ? (
          <div className="space-y-3 border-t border-slate-100 bg-white px-4 py-4">
            <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
              <div className="mb-3 flex items-center gap-2 text-xs font-black uppercase tracking-[0.18em] text-slate-400">
                <Target size={14} />
                {starterChoices.length ? 'Starter Choices' : 'Follow-up Suggestions'}
              </div>
              {isSessionLoading ? (
                <div className="text-sm font-medium text-slate-500">워크샵 세션을 준비 중입니다...</div>
              ) : starterChoices.length || followupChoices.length ? (
                <div className="grid gap-2 sm:grid-cols-2">
                  {(starterChoices.length ? starterChoices : followupChoices).map((choice) => (
                    <button
                      key={choice.id}
                      type="button"
                      onClick={() => {
                        void handleChoiceSelect(choice);
                      }}
                      disabled={isTyping}
                      className="rounded-2xl border border-slate-200 bg-white px-4 py-3 text-left shadow-sm transition-colors hover:border-blue-200 hover:bg-blue-50 disabled:opacity-60"
                    >
                      <p className="text-sm font-extrabold text-slate-800">{choice.label}</p>
                      {choice.description ? (
                        <p className="mt-1 text-[12px] font-medium leading-relaxed text-slate-500">
                          {choice.description}
                        </p>
                      ) : null}
                    </button>
                  ))}
                </div>
              ) : (
                <div className="text-sm font-medium text-slate-500">
                  현재 대화 맥락에 맞는 추천 버튼을 준비 중입니다.
                </div>
              )}
            </div>

            <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
              <div className="mb-3 flex items-center gap-2 text-xs font-black uppercase tracking-[0.18em] text-slate-400">
                <BookOpen size={14} />
                참고자료 고정
              </div>
              <div className="mb-3 flex items-center justify-between text-xs font-bold text-slate-500">
                <span>
                  고정된 자료 {pinnedReferences.length}개 · 현재 요구치 {renderRequirements.minimum_reference_count}개
                </span>
                <span className="rounded-full border border-slate-200 bg-white px-2 py-0.5">
                  {activeQualityInfo.reference_intensity}
                </span>
              </div>
              <textarea
                value={referenceInput}
                onChange={(event) => setReferenceInput(event.target.value)}
                placeholder="논문 요약, 기사 핵심 문장, 교과서 개념 메모를 붙여 넣으면 고정됩니다."
                className="min-h-24 w-full rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm font-medium text-slate-700 focus:border-blue-400 focus:outline-none"
              />
              <div className="mt-3 flex items-center justify-between gap-3">
                <div className="line-clamp-2 text-[12px] font-medium leading-relaxed text-slate-500">
                  심화형은 최소 {activeQualityInfo.minimum_reference_count}개의 자료가 있어야 렌더링됩니다.
                </div>
                <button
                  type="button"
                  onClick={() => {
                    void handlePinReference();
                  }}
                  disabled={!referenceInput.trim()}
                  className="rounded-xl border border-blue-200 bg-blue-50 px-3 py-2 text-xs font-black text-blue-700 disabled:opacity-60"
                >
                  자료 고정
                </button>
              </div>
              {pinnedReferences.length ? (
                <div className="mt-3 space-y-2">
                  {pinnedReferences.slice(-2).map((reference) => (
                    <div key={reference.id} className="rounded-xl border border-white bg-white px-3 py-2 text-[12px] font-medium text-slate-600">
                      {reference.text_content}
                    </div>
                  ))}
                </div>
              ) : null}
            </div>

            {/* 심화 모드 토글 */}
            <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <FlaskConical size={14} className="text-indigo-500" />
                  <span className="text-xs font-black uppercase tracking-[0.18em] text-slate-400">
                    심화 모드
                  </span>
                </div>
                <button
                  type="button"
                  onClick={() => {
                    if (!canUseAdvancedMode) return;
                    setAdvancedMode((prev) => !prev);
                    toast(
                      advancedMode
                        ? '심화 모드를 해제했습니다.'
                        : '심화 모드를 활성화했습니다. 참고자료 검색과 차트/수식 생성이 가능합니다.',
                      { icon: advancedMode ? '📦' : '🔬', duration: 2500 },
                    );
                  }}
                  className={`flex items-center gap-1.5 rounded-xl border px-3 py-1.5 text-xs font-extrabold transition-all ${
                    advancedMode
                      ? 'border-indigo-300 bg-indigo-100 text-indigo-700'
                      : canUseAdvancedMode
                      ? 'border-slate-200 bg-white text-slate-500'
                      : 'cursor-not-allowed border-slate-200 bg-slate-100 text-slate-400'
                  }`}
                  disabled={!canUseAdvancedMode}
                >
                  {advancedMode ? <ToggleRight size={16} /> : <ToggleLeft size={16} />}
                  {advancedMode ? '활성' : '비활성'}
                </button>
              </div>
              {!canUseAdvancedMode ? (
                <p className="mt-3 text-xs font-medium leading-relaxed text-slate-500">
                  심화 모드는 <span className="font-black text-slate-700">심화형</span> 수준에서만 켤 수 있습니다.
                  품질 수준이 먼저 학생 적합성과 안전성을 결정하고, 그 위에서만 추가 확장을 허용합니다.
                </p>
              ) : null}
              {advancedMode && (
                <motion.div
                  initial={{ opacity: 0, height: 0 }}
                  animate={{ opacity: 1, height: 'auto' }}
                  className="mt-3"
                >
                  <p className="text-xs font-medium leading-relaxed text-slate-500">
                    심화 모드에서는 논문 검색, 데이터 시각화, 수식 생성이 자동으로 포함됩니다.
                    참고자료를 핀으로 고정하면 더 정확한 근거를 얻을 수 있습니다.
                  </p>
                  <div className="mt-3">
                    <ReferenceSearchPanel
                      onPinReference={async (text, sourceType) => {
                        if (!workshopState) return;
                        const state = await api.post<WorkshopStateResponse>(
                          `/api/v1/workshops/${workshopState.session.id}/references/pin`,
                          { text_content: text, source_type: sourceType },
                        );
                        syncStateAfterInteraction(state);
                      }}
                      isAdvancedMode={advancedMode}
                    />
                  </div>
                </motion.div>
              )}
            </div>
          </div>
        ) : null}

        <div className="border-t border-slate-100 bg-white p-4">
          <div className="relative flex items-center">
            <input
              type="text"
              value={input}
              onChange={(event) => setInput(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === 'Enter') void handleSend();
              }}
              placeholder="메시지를 입력해 학생 실제 맥락을 더 모아 보세요."
              className="w-full rounded-2xl border-2 border-slate-100 bg-slate-50 py-3.5 pl-5 pr-14 text-[15px] font-medium text-slate-700 focus:border-blue-400 focus:outline-none focus:ring-4 focus:ring-blue-100"
            />
            <button
              type="button"
              onClick={() => {
                void handleSend();
              }}
              disabled={!input.trim() || isTyping}
              className="absolute right-2 flex h-10 w-10 items-center justify-center rounded-xl bg-blue-500 text-white disabled:bg-slate-300"
            >
              <Send size={18} className="ml-0.5" />
            </button>
          </div>
        </div>
      </div>

      <div className="relative flex h-[50vh] w-full flex-col overflow-hidden rounded-3xl border border-slate-700 bg-slate-800 shadow-sm lg:h-full lg:w-[62%]">
        <div className="flex h-14 items-center justify-between border-b border-slate-700 bg-slate-900 px-6">
          <div className="flex min-w-0 items-center gap-2">
            <div className="truncate text-sm font-black text-slate-300">{fileName}</div>
            <span className={`rounded-full border px-2 py-0.5 text-[11px] font-extrabold ${QUALITY_META[qualityLevel].border} ${QUALITY_META[qualityLevel].bg} ${QUALITY_META[qualityLevel].text}`}>
              {activeQualityInfo.emoji} {activeQualityInfo.label}
            </span>
          </div>
          <div className="flex items-center gap-2">
            {safetyMeta ? (
              <AnimatePresence>
                <motion.div
                  initial={{ opacity: 0, scale: 0.9 }}
                  animate={{ opacity: 1, scale: 1 }}
                  className={`flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-[11px] font-extrabold ${
                    safetyMeta.safety_score >= 80
                      ? 'border-emerald-700 bg-emerald-900/40 text-emerald-300'
                      : safetyMeta.safety_score >= 60
                      ? 'border-amber-700 bg-amber-900/40 text-amber-300'
                      : 'border-red-700 bg-red-900/40 text-red-300'
                  }`}
                >
                  {safetyMeta.safety_score >= 80 ? (
                    <ShieldCheck size={12} />
                  ) : safetyMeta.safety_score >= 60 ? (
                    <Shield size={12} />
                  ) : (
                    <ShieldAlert size={12} />
                  )}
                  <span>안전 {safetyMeta.safety_score}/100</span>
                  {safetyMeta.downgraded ? (
                    <span className="ml-1 rounded bg-amber-900/60 px-1 py-0.5 text-[9px] text-amber-200">강등</span>
                  ) : null}
                </motion.div>
              </AnimatePresence>
            ) : null}
            {isProjectBacked ? (
              <button
                type="button"
                onClick={() => {
                  void handleRender();
                }}
                disabled={isRendering || isSessionLoading}
                className="inline-flex items-center gap-2 rounded-xl bg-blue-500 px-4 py-2 text-xs font-black text-white disabled:opacity-60"
              >
                <WandSparkles size={14} />
                {isRendering ? '렌더링 중...' : '안전 초안 생성'}
              </button>
            ) : null}
            <button
              type="button"
              onClick={handleExport}
              disabled={isExporting}
              className="inline-flex items-center gap-2 rounded-xl bg-white px-4 py-2 text-xs font-black text-slate-800 disabled:opacity-60"
            >
              <Download size={14} />
              {isExporting ? '내보내는 중...' : 'HWPX 다운로드'}
              <Lock size={12} />
            </button>
          </div>
        </div>

        <div className="relative flex-1 overflow-y-auto p-4 sm:p-8">
          <div className="mx-auto mb-4 max-w-[210mm] space-y-4">
            <div className="grid gap-3 md:grid-cols-3">
              <div className="rounded-2xl border border-slate-700 bg-slate-900/70 p-4">
                <p className="text-[11px] font-black uppercase tracking-[0.18em] text-slate-500">렌더 상태</p>
                <p className="mt-2 text-sm font-bold leading-relaxed text-slate-200">{renderStatusText}</p>
              </div>
              <div className="rounded-2xl border border-slate-700 bg-slate-900/70 p-4">
                <p className="text-[11px] font-black uppercase tracking-[0.18em] text-slate-500">요청 수준</p>
                <p className="mt-2 text-sm font-bold text-slate-200">
                  {activeQualityInfo.label} · {activeQualityInfo.render_depth}
                </p>
              </div>
              <div className="rounded-2xl border border-slate-700 bg-slate-900/70 p-4">
                <p className="text-[11px] font-black uppercase tracking-[0.18em] text-slate-500">현재 조건</p>
                <p className="mt-2 text-sm font-bold text-slate-200">
                  점수 {renderRequirements.current_context_score}/{renderRequirements.required_context_score}
                </p>
                <p className="mt-1 text-[12px] font-medium leading-relaxed text-slate-400">
                  턴 {renderRequirements.current_turn_count}/{renderRequirements.minimum_turn_count} · 자료 {renderRequirements.current_reference_count}/{renderRequirements.minimum_reference_count}
                </p>
              </div>
            </div>

            {renderArtifact?.quality_control_meta ? (
              <div className="grid gap-3 md:grid-cols-[1.1fr_0.9fr]">
                <div className="rounded-2xl border border-slate-700 bg-slate-900/70 p-4">
                  <p className="text-[11px] font-black uppercase tracking-[0.18em] text-slate-500">품질 제어 메타데이터</p>
                  <div className="mt-3 grid gap-2 sm:grid-cols-2">
                    <div className="rounded-xl border border-slate-700 bg-slate-800 px-3 py-2 text-sm font-bold text-slate-200">
                      요청: {renderArtifact.quality_control_meta.requested_label}
                    </div>
                    <div className="rounded-xl border border-slate-700 bg-slate-800 px-3 py-2 text-sm font-bold text-slate-200">
                      적용: {renderArtifact.quality_control_meta.applied_label}
                    </div>
                    <div className="rounded-xl border border-slate-700 bg-slate-800 px-3 py-2 text-sm font-bold text-slate-200">
                      참고자료: {renderArtifact.quality_control_meta.reference_intensity}
                    </div>
                    <div className="rounded-xl border border-slate-700 bg-slate-800 px-3 py-2 text-sm font-bold text-slate-200">
                      렌더 깊이: {renderArtifact.quality_control_meta.render_depth}
                    </div>
                    <div className="rounded-xl border border-slate-700 bg-slate-800 px-3 py-2 text-sm font-bold text-slate-200">
                      안전 우선: {renderArtifact.quality_control_meta.safety_posture}
                    </div>
                    <div className="rounded-xl border border-slate-700 bg-slate-800 px-3 py-2 text-sm font-bold text-slate-200">
                      실제성: {renderArtifact.quality_control_meta.authenticity_policy}
                    </div>
                    <div className="rounded-xl border border-slate-700 bg-slate-800 px-3 py-2 text-sm font-bold text-slate-200">
                      허위 경험 차단: {renderArtifact.quality_control_meta.hallucination_guardrail}
                    </div>
                    <div className="rounded-xl border border-slate-700 bg-slate-800 px-3 py-2 text-sm font-bold text-slate-200">
                      스키마: {renderArtifact.quality_control_meta.schema_version}
                    </div>
                  </div>
                  <p className="mt-3 text-sm font-medium leading-relaxed text-slate-400">
                    {renderArtifact.quality_control_meta.summary}
                  </p>
                </div>
                <div className="rounded-2xl border border-slate-700 bg-slate-900/70 p-4">
                  <p className="text-[11px] font-black uppercase tracking-[0.18em] text-slate-500">가드레일 처리</p>
                  <p className="mt-2 text-sm font-bold text-slate-200">
                    {renderArtifact.quality_control_meta.repair_applied ? '안전 재작성 적용' : '추가 재작성 없음'}
                  </p>
                  <p className="mt-1 text-[12px] font-medium leading-relaxed text-slate-400">
                    {renderArtifact.quality_control_meta.repair_strategy || '기본 렌더 결과를 유지했습니다.'}
                  </p>
                  <div className="mt-4 rounded-xl border border-slate-700 bg-slate-800 px-3 py-3">
                    <p className="text-[11px] font-black uppercase tracking-[0.18em] text-slate-500">고급 확장</p>
                    <p className="mt-2 text-sm font-bold text-slate-200">
                      {renderArtifact.quality_control_meta.advanced_features_applied ? '적용됨' : '미적용'}
                    </p>
                    <p className="mt-1 text-[12px] font-medium leading-relaxed text-slate-400">
                      {renderArtifact.quality_control_meta.advanced_features_reason ||
                        '품질 수준과 참고자료 조건에 따라 자동으로 판정했습니다.'}
                    </p>
                  </div>
                </div>
              </div>
            ) : null}
          </div>

          <div className="mx-auto min-h-[297mm] max-w-[210mm] rounded-sm bg-white p-8 shadow-2xl sm:p-12 md:p-16">
            <div className="prose prose-sm max-w-none prose-headings:font-extrabold prose-headings:text-slate-900 prose-p:leading-loose prose-p:text-slate-700 sm:prose-base">
              <ReactMarkdown remarkPlugins={[remarkMath]} rehypePlugins={[rehypeKatex]}>
                {documentContent}
              </ReactMarkdown>
            </div>
          </div>

          <AnimatePresence>
            {flyingBlock ? (
              <motion.div
                initial={{ opacity: 0, x: -120, y: 40, scale: 0.8 }}
                animate={{ opacity: 1, x: 0, y: 0, scale: 1 }}
                exit={{ opacity: 0, scale: 1.05 }}
                className="absolute left-10 top-10 rounded-2xl border border-blue-200 bg-blue-50 px-5 py-4 text-sm font-black text-blue-700 shadow-xl"
              >
                <Sparkles size={16} className="mr-2 inline" />
                문서 초안에 반영 중입니다.
              </motion.div>
            ) : null}
          </AnimatePresence>

          {/* 심화 모드 미리보기 */}
          <AdvancedPreview
            visualSpecs={renderArtifact?.visual_specs ?? []}
            mathExpressions={renderArtifact?.math_expressions ?? []}
            isAdvancedMode={Boolean(renderArtifact?.quality_control_meta?.advanced_features_applied)}
          />

          <div className="mx-auto mt-6 max-w-[210mm] space-y-4">
            {qualityChecks.length ? (
              <div className="rounded-3xl border border-slate-700 bg-slate-900/70 p-5">
                <p className="mb-4 text-[11px] font-black uppercase tracking-[0.18em] text-slate-500">안전성 체크리스트</p>
                <div className="grid gap-3 md:grid-cols-2">
                  {qualityChecks.map((check) => (
                    <div key={check.key} className="rounded-2xl border border-slate-700 bg-slate-800 p-4">
                      <div className="flex items-center justify-between gap-3">
                        <p className="text-sm font-black text-slate-100">{check.label}</p>
                        <span
                          className={`rounded-full px-2 py-0.5 text-[10px] font-black ${
                            check.status === 'ok'
                              ? 'bg-emerald-500/20 text-emerald-300'
                              : check.status === 'warning'
                              ? 'bg-amber-500/20 text-amber-300'
                              : 'bg-red-500/20 text-red-300'
                          }`}
                        >
                          {check.score}/100
                        </span>
                      </div>
                      <p className="mt-2 text-[12px] font-medium leading-relaxed text-slate-400">{check.detail}</p>
                      {check.matched_count || check.unsupported_count ? (
                        <p className="mt-2 text-[11px] font-bold uppercase tracking-[0.18em] text-slate-500">
                          감지 {check.matched_count ?? 0} · 비지지 {check.unsupported_count ?? 0}
                        </p>
                      ) : null}
                    </div>
                  ))}
                </div>
              </div>
            ) : null}

            {renderArtifact?.teacher_record_summary_500 ? (
              <div className="rounded-3xl border border-slate-700 bg-slate-900/70 p-5">
                <p className="text-[11px] font-black uppercase tracking-[0.18em] text-slate-500">교사용 500자 요약</p>
                <p className="mt-3 text-sm font-medium leading-relaxed text-slate-200">
                  {renderArtifact.teacher_record_summary_500}
                </p>
              </div>
            ) : null}

            {renderArtifact?.evidence_map && Object.keys(renderArtifact.evidence_map).length ? (
              <div className="rounded-3xl border border-slate-700 bg-slate-900/70 p-5">
                <p className="text-[11px] font-black uppercase tracking-[0.18em] text-slate-500">근거 맵</p>
                <div className="mt-3 space-y-3">
                  {Object.entries(renderArtifact.evidence_map).map(([claim, evidence]) => (
                    <div key={claim} className="rounded-2xl border border-slate-700 bg-slate-800 p-4">
                      <p className="text-sm font-black text-slate-100">{claim}</p>
                      <p className="mt-2 text-sm font-medium leading-relaxed text-slate-300">
                        {evidence.근거 || '근거 정보 없음'}
                      </p>
                      <p className="mt-2 text-[11px] font-bold uppercase tracking-[0.18em] text-slate-500">
                        {evidence.출처 || '출처 미기록'}
                      </p>
                    </div>
                  ))}
                </div>
              </div>
            ) : null}

            {renderArtifact?.student_submission_note ? (
              <div className="rounded-3xl border border-slate-700 bg-slate-900/70 p-5">
                <p className="text-[11px] font-black uppercase tracking-[0.18em] text-slate-500">학생 제출 전 점검</p>
                <pre className="mt-3 whitespace-pre-wrap text-sm font-medium leading-relaxed text-slate-200">
                  {renderArtifact.student_submission_note}
                </pre>
              </div>
            ) : null}
          </div>
        </div>
      </div>
    </div>
  );
}
