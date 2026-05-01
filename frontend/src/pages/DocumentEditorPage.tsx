import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useLocation, useNavigate, useParams } from 'react-router-dom';
import {
  AlertTriangle,
  BookOpen,
  Check,
  ChevronLeft,
  ClipboardList,
  Download,
  FileText,
  Loader2,
  PlusCircle,
  RefreshCw,
  Save,
  Send,
  Sparkles,
  Target,
} from 'lucide-react';
import toast from 'react-hot-toast';
import type { JSONContent } from '@tiptap/react';
import { api, getResolvedApiBaseUrl } from '../lib/api';
import { fetchWithAuth } from '../lib/requestAuth';
import type { DiagnosisResultPayload, DiagnosisRunResponse } from '../types/api';
import { TiptapEditor, type TiptapEditorHandle } from '../components/editor/TiptapEditor';
import { ExportModal } from '../components/editor/ExportModal';
import { PrimaryButton, SecondaryButton, StatusBadge } from '../components/primitives';

interface Draft {
  id: string;
  project_id: string;
  title: string;
  content_markdown: string;
  content_json: string | null;
  status: string;
}

interface EditorLocationState {
  seedMarkdown?: string;
}

interface EditorInsights {
  headline: string;
  focus: string;
  strengths: string[];
  risks: string[];
  actions: string[];
  evidenceCount: number;
}

const LOCAL_DRAFT_TITLE = '탐구 보고서 초안';
const PROJECT_DRAFT_TITLE = '생기부 기반 탐구 보고서';

function asRecord(value: unknown): Record<string, unknown> | null {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return null;
  return value as Record<string, unknown>;
}

function asText(value: unknown): string | null {
  if (typeof value !== 'string') return null;
  const trimmed = value.trim();
  return trimmed || null;
}

function clipText(value: string, limit = 220): string {
  const normalized = value.replace(/\s+/g, ' ').trim();
  if (normalized.length <= limit) return normalized;
  return `${normalized.slice(0, limit).trim()}...`;
}

function collectTextList(value: unknown, limit = 5): string[] {
  if (!Array.isArray(value)) return [];

  const out: string[] = [];
  const seen = new Set<string>();

  for (const item of value) {
    let candidate: string | null = null;
    if (typeof item === 'string') {
      candidate = asText(item);
    } else {
      const record = asRecord(item);
      candidate =
        asText(record?.title) ??
        asText(record?.label) ??
        asText(record?.description) ??
        asText(record?.summary) ??
        asText(record?.rationale) ??
        asText(record?.note) ??
        asText(record?.evidence_hint);
    }

    if (!candidate) continue;
    const key = candidate.toLowerCase();
    if (seen.has(key)) continue;
    seen.add(key);
    out.push(candidate);
    if (out.length >= limit) break;
  }

  return out;
}

function collectEvidenceItems(payload: DiagnosisResultPayload | null | undefined, limit = 8): string[] {
  if (!payload) return [];

  const items: string[] = [];
  const seen = new Set<string>();
  const push = (value: unknown) => {
    const text = asText(value);
    if (!text) return;
    const clipped = clipText(text, 180);
    const key = clipped.toLowerCase();
    if (seen.has(key)) return;
    seen.add(key);
    items.push(clipped);
  };

  payload.citations?.forEach((citation) => {
    const page = citation.page_number ? `${citation.page_number}쪽` : '쪽수 미상';
    push(`${citation.source_label || '학생부 근거'} ${page}: ${citation.excerpt}`);
  });

  payload.admission_axes?.forEach((axis) => axis.evidence_hints?.forEach(push));
  payload.relational_graph?.theme_clusters?.forEach((cluster) => {
    cluster.evidence?.forEach((evidence) => push(`${cluster.theme}: ${evidence}`));
  });

  return items.slice(0, limit);
}

function collectRecommendedTopics(payload: DiagnosisResultPayload | null | undefined, limit = 5): string[] {
  if (!payload) return [];

  const topics = collectTextList(payload.recommended_topics, limit);
  if (topics.length) return topics;

  const fromDirections: string[] = [];
  payload.recommended_directions?.forEach((direction) => {
    direction.topic_candidates?.forEach((topic) => {
      if (topic.title) fromDirections.push(topic.title);
    });
  });
  return collectTextList(fromDirections, limit);
}

function createResearchQuestion(payload: DiagnosisResultPayload | null | undefined): string {
  const firstTopic = collectRecommendedTopics(payload, 1)[0];
  if (firstTopic) return `${firstTopic}을 학생부 근거와 연결해 어떤 탐구 문제로 발전시킬 수 있는가?`;
  const focus = payload?.recommended_focus || payload?.headline;
  if (focus) return `${focus}를 구체적인 탐구 질문과 산출물로 어떻게 전환할 수 있는가?`;
  return '학생부에서 확인되는 관심사를 목표 전공의 탐구 문제로 어떻게 발전시킬 수 있는가?';
}

function buildLocalTemplate(): string {
  return [
    '# 탐구 보고서 초안',
    '',
    '## 1. 탐구 주제',
    '- 주제: 학생부 활동과 목표 전공을 연결한 탐구 주제를 입력하세요.',
    '- 핵심 질문: 이 탐구가 해결하려는 문제를 한 문장으로 적으세요.',
    '',
    '## 2. 생기부 기반 문제의식',
    '학생부에서 확인되는 활동, 수업, 진로 경험 중 탐구 출발점이 되는 근거를 정리하세요.',
    '',
    '## 3. 핵심 근거',
    '- 근거 1:',
    '- 근거 2:',
    '- 근거 3:',
    '',
    '## 4. 탐구 방법',
    '- 문헌조사:',
    '- 실험 또는 비교 분석:',
    '- 결과 정리 방식:',
    '',
    '## 5. 예상 결과와 한계',
    '예상되는 결과, 부족한 점, 후속 탐구 방향을 함께 작성하세요.',
    '',
    '## 6. 전공 연결 및 면접 활용',
    '이 보고서가 목표 학과에서 어떤 역량을 보여주는지 정리하세요.',
  ].join('\n');
}

function buildReportMarkdownFromDiagnosis(
  payload: DiagnosisResultPayload | null | undefined,
  options: { title?: string; targetMajor?: string | null } = {},
): string {
  if (!payload) return buildLocalTemplate();

  const title = options.title || PROJECT_DRAFT_TITLE;
  const targetMajor = options.targetMajor || '목표 전공';
  const evidenceItems = collectEvidenceItems(payload, 8);
  const strengths = collectTextList(payload.strengths, 5);
  const risks = collectTextList(payload.gaps, 5);
  const actions = collectTextList(payload.next_actions ?? payload.action_plan, 5);
  const topics = collectRecommendedTopics(payload, 6);
  const axes = payload.admission_axes || [];
  const question = createResearchQuestion(payload);

  const lines = [
    `# ${title}`,
    '',
    `- 목표 전공: ${targetMajor}`,
    `- 작성일: ${new Date().toLocaleDateString('ko-KR')}`,
    '- 작성 기준: 업로드된 학생부 진단 결과와 추출 근거',
    '',
    '## 1. 탐구 주제',
    topics[0] ? `**${topics[0]}**` : `**${payload.recommended_focus || payload.headline}**`,
    '',
    '## 2. 생기부 기반 문제의식',
    payload.headline ? `- 핵심 진단: ${payload.headline}` : null,
    payload.overview ? `- 전체 해석: ${payload.overview}` : null,
    payload.recommended_focus ? `- 집중 방향: ${payload.recommended_focus}` : null,
    '',
    '## 3. 핵심 근거',
    ...(evidenceItems.length
      ? evidenceItems.map((item) => `- ${item}`)
      : ['- 아직 문장 근거가 충분히 연결되지 않았습니다. 학생부 원문에서 활동명, 과목명, 결과를 보강하세요.']),
    '',
    '## 4. 전공 적합성 해석',
    ...(axes.length
      ? axes.slice(0, 5).map((axis) => `- ${axis.label} ${axis.score}점: ${axis.rationale}`)
      : strengths.map((strength) => `- ${strength}`)),
    '',
    '## 5. 탐구 질문',
    `- ${question}`,
    '- 이 질문은 학생부에 이미 등장한 활동을 확장하되, 결과를 수치나 비교표로 검증할 수 있어야 합니다.',
    '',
    '## 6. 탐구 방법',
    '- 문헌조사: 전공 개념, 선행 연구, 공신력 있는 통계 또는 기준을 정리합니다.',
    '- 비교분석: 학생부 활동에서 확인된 사례와 새 탐구 대상을 같은 기준으로 비교합니다.',
    '- 산출물: 보고서, 표, 그래프, 설계안, 면접 답변 프레임 중 최소 2개를 남깁니다.',
    '',
    '## 7. 예상 결과와 한계',
    ...(risks.length ? risks.map((risk) => `- 보완 필요: ${risk}`) : ['- 탐구 결과가 추상적으로 끝나지 않도록 변수, 기준, 한계를 명확히 적어야 합니다.']),
    '',
    '## 8. 면접 대비 질문',
    '- 이 주제를 선택한 이유는 무엇인가요?',
    '- 학생부의 어떤 활동이 이 탐구로 이어졌나요?',
    '- 탐구 과정에서 사용한 전공 개념이나 수학/과학 개념은 무엇인가요?',
    '- 결과가 예상과 다르게 나왔을 때 어떻게 해석할 수 있나요?',
    '',
    '## 9. 30일 보완 계획',
    ...(actions.length
      ? actions.map((action, index) => `- ${index + 1}주차: ${action}`)
      : [
          '- 1주차: 학생부 근거 3개를 골라 탐구 질문을 확정합니다.',
          '- 2주차: 자료 조사와 비교 기준을 정리합니다.',
          '- 3주차: 결과표, 그래프, 도면 등 산출물을 제작합니다.',
          '- 4주차: 보고서 결론과 면접 답변 5개를 완성합니다.',
        ]),
    '',
    '## 10. 참고 근거',
    ...(payload.citations?.length
      ? payload.citations.slice(0, 6).map((citation) => {
          const page = citation.page_number ? `${citation.page_number}쪽` : '쪽수 미상';
          return `- ${citation.source_label || '학생부'} ${page}: ${clipText(citation.excerpt, 160)}`;
        })
      : ['- 참고 근거는 학생부 원문, 수업 활동, 진로 활동, 후속 탐구 자료를 기준으로 추가하세요.']),
  ].filter((line): line is string => line !== null);

  return lines.join('\n');
}

function buildInsights(payload: DiagnosisResultPayload | null): EditorInsights {
  return {
    headline: payload?.headline || '진단 결과를 기반으로 탐구 보고서 초안을 준비합니다.',
    focus: payload?.recommended_focus || '학생부 근거를 탐구 질문, 방법, 산출물로 연결하세요.',
    strengths: collectTextList(payload?.strengths, 5),
    risks: collectTextList(payload?.gaps, 5),
    actions: collectTextList(payload?.next_actions ?? payload?.action_plan, 5),
    evidenceCount: payload?.citations?.length || collectEvidenceItems(payload).length,
  };
}

function getInitialContent(draft: Draft | null, seedMarkdown: string): JSONContent | string | null {
  if (!draft?.content_json) {
    return draft?.content_markdown || seedMarkdown || null;
  }

  try {
    return JSON.parse(draft.content_json) as JSONContent;
  } catch (error) {
    console.error('Failed to parse saved editor JSON:', error);
    return draft.content_markdown || seedMarkdown || null;
  }
}

export function DocumentEditorPage() {
  const { projectId } = useParams<{ projectId: string }>();
  const navigate = useNavigate();
  const location = useLocation();

  const [draft, setDraft] = useState<Draft | null>(null);
  const [latestDiagnosis, setLatestDiagnosis] = useState<DiagnosisRunResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [isRegenerating, setIsRegenerating] = useState(false);
  const [isAssistantRunning, setIsAssistantRunning] = useState(false);
  const [lastSaved, setLastSaved] = useState<Date | null>(null);
  const [isExportOpen, setIsExportOpen] = useState(false);
  const [editorVersion, setEditorVersion] = useState(0);
  const [assistantPrompt, setAssistantPrompt] = useState(
    '이 초안에서 학생부 근거가 약한 부분과 다음에 써야 할 문단을 구체적으로 제안해줘.',
  );
  const [assistantResponse, setAssistantResponse] = useState('');
  const [assistantError, setAssistantError] = useState<string | null>(null);

  const editorRef = useRef<TiptapEditorHandle>(null);
  const pendingContentRef = useRef<JSONContent | null>(null);
  const saveTimerRef = useRef<number | null>(null);
  const assistantAbortRef = useRef<AbortController | null>(null);

  const seedMarkdown = ((location.state as EditorLocationState | null)?.seedMarkdown || '').trim();
  const isLocalMode = !projectId || projectId === 'demo' || projectId === 'undefined';

  const fetchLatestDiagnosis = useCallback(async (): Promise<DiagnosisRunResponse | null> => {
    if (!projectId || isLocalMode) return null;
    try {
      const run = await api.get<DiagnosisRunResponse>(`/api/v1/diagnosis/project/${projectId}/latest`);
      setLatestDiagnosis(run);
      return run;
    } catch (error) {
      console.warn('Latest diagnosis was not available for editor seed:', error);
      setLatestDiagnosis(null);
      return null;
    }
  }, [isLocalMode, projectId]);

  useEffect(() => {
    async function load() {
      setIsLoading(true);

      if (isLocalMode) {
        setDraft({
          id: 'local',
          project_id: projectId ?? 'demo',
          title: LOCAL_DRAFT_TITLE,
          content_markdown: seedMarkdown || buildLocalTemplate(),
          content_json: null,
          status: 'in_progress',
        });
        setIsLoading(false);
        return;
      }

      try {
        const [drafts, diagnosisRun] = await Promise.all([
          api.get<Draft[]>(`/api/v1/projects/${projectId}/drafts`),
          fetchLatestDiagnosis(),
        ]);

        const generatedMarkdown = seedMarkdown || buildReportMarkdownFromDiagnosis(diagnosisRun?.result_payload, {
          targetMajor: diagnosisRun?.result_payload?.diagnosis_summary?.target_context || null,
        });

        if (drafts && drafts.length > 0) {
          const selected = drafts[0];
          if (!selected.content_markdown?.trim() && !selected.content_json) {
            const updated = await api.patch<Draft>(`/api/v1/projects/${projectId}/drafts/${selected.id}`, {
              title: selected.title || PROJECT_DRAFT_TITLE,
              content_markdown: generatedMarkdown,
              content_json: null,
              status: 'in_progress',
            });
            setDraft(updated);
          } else {
            setDraft(selected);
          }
        } else {
          const newDraft = await api.post<Draft>(`/api/v1/projects/${projectId}/drafts`, {
            title: PROJECT_DRAFT_TITLE,
            content_markdown: generatedMarkdown,
            content_json: null,
          });
          setDraft(newDraft);
        }
      } catch (err) {
        console.error('Load draft failed:', err);
        setDraft({
          id: 'local',
          project_id: projectId ?? 'demo',
          title: LOCAL_DRAFT_TITLE,
          content_markdown: seedMarkdown || buildLocalTemplate(),
          content_json: null,
          status: 'in_progress',
        });
        toast.error('문서 초안을 불러오지 못해 임시 편집 모드로 전환했습니다.');
      } finally {
        setIsLoading(false);
      }
    }

    void load();
  }, [fetchLatestDiagnosis, isLocalMode, projectId, seedMarkdown]);

  const flushSave = useCallback(async () => {
    const content = pendingContentRef.current ?? editorRef.current?.getJSON();
    const markdown = editorRef.current?.getMarkdown() || draft?.content_markdown || '';

    if (!content || !projectId || !draft || draft.id === 'local') {
      return;
    }
    if (isSaving) {
      return;
    }

    setIsSaving(true);
    try {
      const updated = await api.patch<Draft>(`/api/v1/projects/${projectId}/drafts/${draft.id}`, {
        content_json: JSON.stringify(content),
        content_markdown: markdown,
        status: 'in_progress',
      });
      setDraft(updated);
      setLastSaved(new Date());
      pendingContentRef.current = null;
    } catch (err) {
      console.error('Auto-save failed:', err);
      toast.error('자동 저장에 실패했습니다. 잠시 후 다시 저장해 주세요.');
    } finally {
      setIsSaving(false);
    }
  }, [draft, isSaving, projectId]);

  const handleEditorUpdate = useCallback(
    (json: JSONContent) => {
      pendingContentRef.current = json;
      if (saveTimerRef.current) window.clearTimeout(saveTimerRef.current);

      if (draft?.id === 'local') {
        setLastSaved(new Date());
        return;
      }

      saveTimerRef.current = window.setTimeout(() => {
        void flushSave();
      }, 2000);
    },
    [draft?.id, flushSave],
  );

  const handleManualSave = useCallback(async () => {
    if (saveTimerRef.current) window.clearTimeout(saveTimerRef.current);

    const json = editorRef.current?.getJSON();
    if (json) pendingContentRef.current = json;

    if (draft?.id === 'local') {
      setLastSaved(new Date());
      toast.success('임시 편집 상태를 현재 브라우저 세션에 반영했습니다.');
      return;
    }

    await flushSave();
    toast.success('문서를 저장했습니다.');
  }, [draft?.id, flushSave]);

  const handleRegenerateFromDiagnosis = useCallback(async () => {
    if (!projectId || isLocalMode) return;
    setIsRegenerating(true);
    try {
      const run = await fetchLatestDiagnosis();
      const markdown = buildReportMarkdownFromDiagnosis(run?.result_payload, {
        targetMajor: run?.result_payload?.diagnosis_summary?.target_context || null,
      });
      editorRef.current?.setContent(markdown);
      const json = editorRef.current?.getJSON();
      pendingContentRef.current = json || null;

      if (draft && draft.id !== 'local') {
        const updated = await api.patch<Draft>(`/api/v1/projects/${projectId}/drafts/${draft.id}`, {
          title: draft.title || PROJECT_DRAFT_TITLE,
          content_markdown: markdown,
          content_json: json ? JSON.stringify(json) : null,
          status: 'in_progress',
        });
        setDraft(updated);
      }
      setLastSaved(new Date());
      setEditorVersion((value) => value + 1);
      toast.success('진단 결과 기반 초안을 다시 구성했습니다.');
    } catch (error) {
      console.error('Regenerate editor draft failed:', error);
      toast.error('진단 기반 초안 생성에 실패했습니다.');
    } finally {
      setIsRegenerating(false);
    }
  }, [draft, fetchLatestDiagnosis, isLocalMode, projectId]);

  const handleAskAssistant = useCallback(async () => {
    const message = assistantPrompt.trim();
    if (!message) {
      toast.error('AI에게 요청할 내용을 입력해 주세요.');
      return;
    }

    assistantAbortRef.current?.abort();
    const controller = new AbortController();
    assistantAbortRef.current = controller;

    setIsAssistantRunning(true);
    setAssistantError(null);
    setAssistantResponse('');

    try {
      const baseUrl = getResolvedApiBaseUrl();
      const response = await fetchWithAuth(
        `${baseUrl}/api/v1/drafts/chat/stream`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            project_id: isLocalMode ? null : projectId,
            message,
            draft_snapshot_markdown: editorRef.current?.getMarkdown() || draft?.content_markdown || '',
          }),
          signal: controller.signal,
        },
      );

      if (!response.response.ok) {
        if (response.response.status === 401) {
          throw new Error('로그인 세션이 필요합니다. 다시 로그인한 뒤 이용해 주세요.');
        }
        throw new Error(`AI 제안 요청 실패 (${response.response.status})`);
      }

      const reader = response.response.body?.getReader();
      if (!reader) {
        throw new Error('AI 응답 스트림을 읽을 수 없습니다.');
      }

      const decoder = new TextDecoder('utf-8');
      let buffer = '';

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split(/\r?\n/);
        buffer = lines.pop() || '';

        for (const line of lines) {
          if (!line.startsWith('data:')) continue;
          const raw = line.slice(5).trim();
          if (!raw) continue;
          try {
            const event = JSON.parse(raw) as { token?: string; status?: string; meta?: { limited_mode?: boolean; limited_reason?: string | null } };
            if (event.token) {
              setAssistantResponse((current) => `${current}${event.token}`);
            }
            if (event.meta?.limited_mode) {
              setAssistantError('LLM 응답이 제한되어 보수적 fallback 안내가 사용되었습니다.');
            }
          } catch {
            // Ignore malformed SSE keep-alive fragments.
          }
        }
      }
    } catch (error) {
      if ((error as Error).name !== 'AbortError') {
        const messageText = error instanceof Error ? error.message : 'AI 제안 요청에 실패했습니다.';
        setAssistantError(messageText);
        toast.error(messageText);
      }
    } finally {
      setIsAssistantRunning(false);
    }
  }, [assistantPrompt, draft?.content_markdown, isLocalMode, projectId]);

  const handleAppendAssistantResponse = useCallback(async () => {
    const suggestion = assistantResponse.trim();
    if (!suggestion) return;

    const currentMarkdown = editorRef.current?.getMarkdown() || draft?.content_markdown || '';
    const nextMarkdown = `${currentMarkdown.trim()}\n\n## AI 보완 제안\n${suggestion}`.trim();
    editorRef.current?.setContent(nextMarkdown);
    const json = editorRef.current?.getJSON();
    if (json) pendingContentRef.current = json;

    if (draft?.id === 'local') {
      setLastSaved(new Date());
      toast.success('AI 제안을 문서에 추가했습니다.');
      return;
    }

    await flushSave();
    toast.success('AI 제안을 문서에 추가하고 저장했습니다.');
  }, [assistantResponse, draft?.content_markdown, draft?.id, flushSave]);

  useEffect(
    () => () => {
      if (saveTimerRef.current) window.clearTimeout(saveTimerRef.current);
      assistantAbortRef.current?.abort();
    },
    [],
  );

  const initialContent = useMemo(
    () => getInitialContent(draft, seedMarkdown),
    [draft, seedMarkdown],
  );

  const insights = useMemo(
    () => buildInsights(latestDiagnosis?.result_payload ?? null),
    [latestDiagnosis?.result_payload],
  );

  const editorStatus = isSaving
    ? { tone: 'active' as const, label: '저장 중' }
    : lastSaved
      ? { tone: 'success' as const, label: `${lastSaved.toLocaleTimeString('ko-KR')} 저장됨` }
      : isLocalMode
        ? { tone: 'warning' as const, label: '임시 편집' }
        : { tone: 'neutral' as const, label: '자동 저장 켜짐' };

  if (isLoading) {
    return (
      <div className="flex h-[80vh] w-full items-center justify-center">
        <div className="flex flex-col items-center gap-4">
          <div className="relative">
            <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-violet-50">
              <FileText size={28} className="text-violet-600" />
            </div>
            <Loader2 size={20} className="absolute -bottom-1 -right-1 animate-spin text-violet-600" />
          </div>
          <p className="text-sm font-medium text-slate-500">진단 근거를 바탕으로 문서 편집기를 준비하고 있습니다.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex h-full min-h-[100dvh] flex-col overflow-hidden bg-[#FAFAFA]">
      <header className="sticky top-0 z-30 flex min-h-16 w-full shrink-0 items-center justify-between border-b border-slate-200 bg-white/95 px-3 backdrop-blur sm:px-5">
        <div className="flex min-w-0 items-center gap-2 sm:gap-3">
          <button
            onClick={() => navigate(-1)}
            className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl border border-slate-200 text-slate-500 transition hover:bg-slate-50 hover:text-slate-700"
            aria-label="이전 화면으로 이동"
          >
            <ChevronLeft size={18} />
          </button>

          <div className="hidden h-7 w-px bg-slate-200 sm:block" />

          <div className="min-w-0">
            <div className="flex items-center gap-2">
              <BookOpen size={17} className="shrink-0 text-violet-600" />
              <h1 className="truncate text-sm font-extrabold text-slate-950 sm:text-base">
                {draft?.title || '문서 편집기'}
              </h1>
            </div>
            <div className="mt-1 flex flex-wrap items-center gap-2">
              <StatusBadge status={editorStatus.tone}>
                {isSaving ? <Loader2 size={10} className="animate-spin" /> : null}
                {!isSaving && lastSaved ? <Check size={10} /> : null}
                {editorStatus.label}
              </StatusBadge>
              {latestDiagnosis?.result_payload ? <StatusBadge status="active">진단 데이터 연결됨</StatusBadge> : null}
            </div>
          </div>
        </div>

        <div className="flex shrink-0 items-center gap-1.5 sm:gap-2">
          {!isLocalMode ? (
            <SecondaryButton
              size="sm"
              onClick={() => void handleRegenerateFromDiagnosis()}
              disabled={isRegenerating}
              className="px-2.5 sm:px-3.5"
            >
              {isRegenerating ? <Loader2 size={14} className="animate-spin" /> : <RefreshCw size={14} />}
              <span className="hidden md:inline">진단 기반 재구성</span>
            </SecondaryButton>
          ) : null}
          <SecondaryButton size="sm" onClick={() => setIsExportOpen(true)} className="px-2.5 sm:px-3.5">
            <Download size={14} />
            <span className="hidden sm:inline">내보내기</span>
          </SecondaryButton>
          <PrimaryButton size="sm" onClick={() => void handleManualSave()} disabled={isSaving} className="px-2.5 sm:px-3.5">
            <Save size={14} />
            <span className="hidden sm:inline">저장</span>
          </PrimaryButton>
        </div>
      </header>

      <main className="grid min-h-0 flex-1 grid-cols-1 overflow-hidden xl:grid-cols-[minmax(0,1fr)_360px]">
        <section className="min-h-0 overflow-hidden p-3 sm:p-5">
          <TiptapEditor
            key={`${draft?.id || 'draft'}-${editorVersion}`}
            ref={editorRef}
            initialContent={initialContent}
            onJsonUpdate={handleEditorUpdate}
          />
        </section>

        <aside className="hidden min-h-0 overflow-y-auto border-l border-slate-200 bg-white px-5 py-5 xl:block">
          <div className="mb-5">
            <div className="mb-2 flex items-center gap-2 text-xs font-black uppercase tracking-[0.16em] text-violet-600">
              <Sparkles size={14} />
              Diagnosis Context
            </div>
            <h2 className="text-xl font-black leading-tight text-slate-950">{insights.headline}</h2>
            <p className="mt-3 text-sm font-medium leading-6 text-slate-600">{insights.focus}</p>
          </div>

          <div className="grid gap-3">
            <div className="rounded-2xl border border-violet-100 bg-violet-50 p-4">
              <div className="mb-2 flex items-center justify-between">
                <span className="inline-flex items-center gap-2 text-sm font-black text-violet-900">
                  <Target size={16} />
                  핵심 강점
                </span>
                <StatusBadge status="success">{insights.strengths.length || 0}개</StatusBadge>
              </div>
              <ul className="space-y-2 text-sm font-medium leading-5 text-slate-700">
                {(insights.strengths.length ? insights.strengths : ['진단 결과의 강점 항목을 불러오면 자동으로 채워집니다.']).map((item) => (
                  <li key={item}>- {clipText(item, 110)}</li>
                ))}
              </ul>
            </div>

            <div className="rounded-2xl border border-amber-100 bg-amber-50 p-4">
              <div className="mb-2 flex items-center justify-between">
                <span className="inline-flex items-center gap-2 text-sm font-black text-amber-900">
                  <AlertTriangle size={16} />
                  보완 리스크
                </span>
                <StatusBadge status="warning">{insights.risks.length || 0}개</StatusBadge>
              </div>
              <ul className="space-y-2 text-sm font-medium leading-5 text-slate-700">
                {(insights.risks.length ? insights.risks : ['리스크가 없더라도 탐구 질문, 결과 수치, 한계 분석은 반드시 점검하세요.']).map((item) => (
                  <li key={item}>- {clipText(item, 110)}</li>
                ))}
              </ul>
            </div>

            <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
              <div className="mb-2 flex items-center justify-between">
                <span className="inline-flex items-center gap-2 text-sm font-black text-slate-900">
                  <ClipboardList size={16} />
                  다음 작업
                </span>
                <StatusBadge status="active">{insights.evidenceCount}개 근거</StatusBadge>
              </div>
              <ul className="space-y-2 text-sm font-medium leading-5 text-slate-700">
                {(insights.actions.length ? insights.actions : ['초안의 3번 근거 항목을 먼저 실제 문장으로 보강하세요.']).map((item) => (
                  <li key={item}>- {clipText(item, 110)}</li>
                ))}
              </ul>
            </div>

            <div className="rounded-2xl border border-violet-200 bg-white p-4 shadow-sm">
              <div className="mb-3 flex items-center justify-between">
                <span className="inline-flex items-center gap-2 text-sm font-black text-slate-950">
                  <Sparkles size={16} className="text-violet-600" />
                  AI 문단 제안
                </span>
                <StatusBadge status={isAssistantRunning ? 'active' : 'neutral'}>
                  {isAssistantRunning ? '작성 중' : '대기'}
                </StatusBadge>
              </div>
              <textarea
                value={assistantPrompt}
                onChange={(event) => setAssistantPrompt(event.target.value)}
                className="min-h-24 w-full resize-none rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-sm font-medium leading-5 text-slate-800 outline-none transition focus:border-violet-300 focus:bg-white focus:ring-4 focus:ring-violet-100"
                placeholder="예: 탐구 동기 문단을 학생부 근거 중심으로 써줘."
              />
              <div className="mt-3 flex gap-2">
                <PrimaryButton
                  size="sm"
                  onClick={() => void handleAskAssistant()}
                  disabled={isAssistantRunning}
                  className="flex-1"
                >
                  {isAssistantRunning ? <Loader2 size={14} className="animate-spin" /> : <Send size={14} />}
                  제안 받기
                </PrimaryButton>
                <SecondaryButton
                  size="sm"
                  onClick={() => void handleAppendAssistantResponse()}
                  disabled={!assistantResponse.trim() || isAssistantRunning}
                  className="px-3"
                >
                  <PlusCircle size={14} />
                </SecondaryButton>
              </div>
              {assistantError ? (
                <p className="mt-3 rounded-xl bg-amber-50 px-3 py-2 text-xs font-bold leading-5 text-amber-700">
                  {assistantError}
                </p>
              ) : null}
              {assistantResponse ? (
                <div className="mt-3 max-h-64 overflow-y-auto rounded-xl border border-slate-200 bg-slate-50 p-3 text-sm font-medium leading-6 text-slate-700">
                  {assistantResponse}
                </div>
              ) : (
                <p className="mt-3 text-xs font-semibold leading-5 text-slate-500">
                  현재 초안과 진단 근거를 함께 보내므로, 일반론보다 문서에 바로 붙일 수 있는 제안을 받을 수 있습니다.
                </p>
              )}
            </div>
          </div>
        </aside>
      </main>

      <ExportModal
        isOpen={isExportOpen}
        onClose={() => setIsExportOpen(false)}
        documentTitle={draft?.title || LOCAL_DRAFT_TITLE}
        getJSON={() => editorRef.current?.getJSON() || { type: 'doc', content: [] }}
        getHTML={() => editorRef.current?.getHTML() || ''}
      />
    </div>
  );
}
