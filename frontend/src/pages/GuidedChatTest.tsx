import React, { useEffect, useMemo, useState } from 'react';
import { Loader2, Sparkles } from 'lucide-react';
import { useParams } from 'react-router-dom';
import toast from 'react-hot-toast';

import { api } from '../lib/api';
import {
  applyTopicSelectionToUiState,
  createInitialGuidedChatUiState,
  limitTopicSuggestions,
  type GuidedChatUiState,
  type GuidedTopicSelectionResponse,
  type GuidedTopicSuggestionResponse,
} from '../lib/guidedChat';
import {
  PageHeader,
  PrimaryButton,
  SectionCard,
  SecondaryButton,
  StatusBadge,
  SurfaceCard,
  WorkflowNotice,
} from '../components/primitives';

const FIXED_GREETING = '안녕하세요. 어떤 주제의 보고서를 써볼까요?';

interface GuidedChatStartResponse {
  greeting: string;
  project_id: string | null;
  evidence_gap_note: string | null;
}

export function GuidedChatTest() {
  const { projectId } = useParams<{ projectId?: string }>();
  const [resolvedProjectId, setResolvedProjectId] = useState<string | null>(projectId || null);
  const [greeting, setGreeting] = useState(FIXED_GREETING);
  const [evidenceGapNote, setEvidenceGapNote] = useState<string | null>(null);
  const [subject, setSubject] = useState('');
  const [suggestionsPayload, setSuggestionsPayload] = useState<GuidedTopicSuggestionResponse | null>(null);
  const [uiState, setUiState] = useState<GuidedChatUiState>(() =>
    createInitialGuidedChatUiState('# 선택한 주제가 여기에 초안으로 채워집니다.'),
  );
  const [isStarting, setIsStarting] = useState(false);
  const [isGeneratingSuggestions, setIsGeneratingSuggestions] = useState(false);
  const [isSelectingTopic, setIsSelectingTopic] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    const run = async () => {
      setIsStarting(true);
      try {
        const startResponse = await api.post<GuidedChatStartResponse>('/api/v1/guided-chat/start', {
          project_id: projectId ?? null,
        });
        if (cancelled) return;
        setGreeting(startResponse.greeting || FIXED_GREETING);
        setEvidenceGapNote(startResponse.evidence_gap_note);
        setResolvedProjectId(startResponse.project_id ?? projectId ?? null);
      } catch (error) {
        console.error(error);
        if (!cancelled) {
          setGreeting(FIXED_GREETING);
          setEvidenceGapNote('초기 맥락을 불러오지 못해 제한 모드로 시작합니다.');
        }
      } finally {
        if (!cancelled) {
          setIsStarting(false);
        }
      }
    };
    void run();
    return () => {
      cancelled = true;
    };
  }, [projectId]);

  const suggestions = useMemo(() => suggestionsPayload?.suggestions ?? [], [suggestionsPayload?.suggestions]);

  const handleGenerateSuggestions = async () => {
    const normalized = (subject || '').trim();
    if (!normalized) {
      toast.error('과목 또는 넓은 주제를 입력해 주세요.');
      return;
    }
    setIsGeneratingSuggestions(true);
    setSuggestionsPayload(null);
    try {
      const response = await api.post<GuidedTopicSuggestionResponse>('/api/v1/guided-chat/topic-suggestions', {
        project_id: resolvedProjectId,
        subject: normalized,
      });
      const normalizedResponse = limitTopicSuggestions(response);
      setSuggestionsPayload(normalizedResponse);
      if (normalizedResponse.evidence_gap_note) {
        setEvidenceGapNote(normalizedResponse.evidence_gap_note);
      }
    } catch (error) {
      console.error(error);
      toast.error('주제 제안을 생성하지 못했습니다. 잠시 후 다시 시도해 주세요.');
    } finally {
      setIsGeneratingSuggestions(false);
    }
  };

  const handleSelectTopic = async (selectedTopicId: string) => {
    if (!suggestionsPayload) return;
    setIsSelectingTopic(selectedTopicId);
    try {
      const response = await api.post<GuidedTopicSelectionResponse>('/api/v1/guided-chat/topic-selection', {
        project_id: resolvedProjectId,
        selected_topic_id: selectedTopicId,
        subject: suggestionsPayload.subject,
        suggestions: suggestionsPayload.suggestions,
      });
      setUiState(previous => applyTopicSelectionToUiState(previous, response));
    } catch (error) {
      console.error(error);
      toast.error('선택 주제 초안을 불러오지 못했습니다.');
    } finally {
      setIsSelectingTopic(null);
    }
  };

  return (
    <div className="mx-auto max-w-7xl space-y-6 py-4">
      <PageHeader
        eyebrow="Guided Chat Test"
        title="주제 가이드 테스트"
        description="자유 채팅이 아니라, 근거 기반 300개 이상 주제 제안 후 구조를 먼저 잡는 테스트 흐름입니다."
        evidence={
          <div className="flex flex-wrap items-center gap-2">
            <StatusBadge status="active">고정 인사말</StatusBadge>
            <StatusBadge status="neutral">{resolvedProjectId ? '프로젝트 연동' : '제한 모드'}</StatusBadge>
            <StatusBadge status="success">300개 이상 주제</StatusBadge>
          </div>
        }
      />

      <div className="grid gap-6 lg:grid-cols-[1fr_1fr]">
        <SectionCard
          title="주제 제안"
          description="넓은 과목을 입력하면 학생 맥락 기반으로 300개 이상 주제를 제안합니다."
          eyebrow="LEFT PANEL"
          bodyClassName="space-y-4"
        >
          <SurfaceCard tone="muted" padding="sm" className="space-y-2">
            <p className="text-sm font-bold text-slate-900">{isStarting ? '초기화 중입니다...' : greeting}</p>
            {evidenceGapNote ? (
              <p className="text-sm font-medium leading-6 text-slate-600">{evidenceGapNote}</p>
            ) : (
              <p className="text-sm font-medium leading-6 text-slate-600">
                확인된 근거를 우선 사용하고, 부족한 정보는 부족하다고 명시해서 제안드립니다.
              </p>
            )}
          </SurfaceCard>

          <div className="flex flex-col gap-2 sm:flex-row">
            <input
              value={subject}
              onChange={event => setSubject(event.target.value)}
              onKeyDown={event => {
                if (event.key === 'Enter') {
                  event.preventDefault();
                  void handleGenerateSuggestions();
                }
              }}
              placeholder="예: 수학, 화학, 사회문화"
              className="h-12 w-full rounded-2xl border border-slate-300 bg-white px-4 text-sm font-semibold text-slate-700 outline-none transition focus-visible:ring-2 focus-visible:ring-blue-300"
            />
            <PrimaryButton onClick={() => void handleGenerateSuggestions()} disabled={isGeneratingSuggestions || isStarting}>
              {isGeneratingSuggestions ? <Loader2 size={16} className="animate-spin" /> : <Sparkles size={16} />}
              300개 주제 제안
            </PrimaryButton>
          </div>

          {suggestions.length ? (
            <div className="max-h-[560px] space-y-3 overflow-y-auto pr-1">
              {suggestions.map((item, index) => (
                <SurfaceCard key={item.id} padding="sm" className="space-y-3">
                  <div className="flex items-center justify-between gap-2">
                    <StatusBadge status="active">주제 {index + 1}</StatusBadge>
                    <SecondaryButton
                      size="sm"
                      onClick={() => void handleSelectTopic(item.id)}
                      disabled={Boolean(isSelectingTopic)}
                    >
                      {isSelectingTopic === item.id ? <Loader2 size={14} className="animate-spin" /> : null}
                      이 주제로 시작
                    </SecondaryButton>
                  </div>
                  <h3 className="text-base font-black text-slate-900">{item.title}</h3>
                  <p className="text-sm font-medium leading-6 text-slate-700">{item.why_fit_student}</p>
                  <p className="text-sm font-medium leading-6 text-slate-600">기록 연결: {item.link_to_record_flow}</p>
                  {item.link_to_target_major_or_university ? (
                    <p className="text-sm font-medium leading-6 text-slate-600">목표 연결: {item.link_to_target_major_or_university}</p>
                  ) : null}
                  <p className="text-sm font-medium leading-6 text-slate-600">새로움: {item.novelty_point}</p>
                  {item.caution_note ? (
                    <WorkflowNotice tone="warning" title="주의" description={item.caution_note} />
                  ) : null}
                </SurfaceCard>
              ))}
            </div>
          ) : (
            <SurfaceCard tone="muted" padding="sm">
              <p className="text-sm font-medium leading-6 text-slate-600">
                과목을 입력해 주시면 근거 기반 300개 이상 주제를 보여드립니다.
              </p>
            </SurfaceCard>
          )}
        </SectionCard>

        <SectionCard
          title="우측 초안 패널"
          description="주제를 선택하면 페이지 범위, 개요, 스타터 초안이 채워집니다."
          eyebrow="RIGHT PANEL"
          bodyClassName="space-y-4"
        >
          <SurfaceCard tone="muted" padding="sm">
            <div className="flex flex-wrap items-center gap-2">
              <StatusBadge status={uiState.selectedTopicId ? 'success' : 'neutral'}>
                {uiState.selectedTopicId ? '주제 선택 완료' : '주제 선택 대기'}
              </StatusBadge>
              {uiState.selectedTitle ? <StatusBadge status="active">{uiState.selectedTitle}</StatusBadge> : null}
            </div>
            {uiState.guidanceMessage ? (
              <p className="mt-3 text-sm font-medium leading-6 text-slate-700">{uiState.guidanceMessage}</p>
            ) : null}
          </SurfaceCard>

          <div className="grid gap-3 md:grid-cols-2">
            <SurfaceCard padding="sm" className="space-y-2">
              <p className="text-xs font-black uppercase tracking-[0.14em] text-slate-400">권장 페이지 범위</p>
              {uiState.pageRanges.length ? (
                <ul className="space-y-2">
                  {uiState.pageRanges.map(item => (
                    <li key={item.label} className="rounded-xl border border-slate-200 bg-white p-2.5">
                      <p className="text-sm font-bold text-slate-800">
                        {item.label}: {item.min_pages}~{item.max_pages}p
                      </p>
                      <p className="mt-1 text-xs font-medium leading-5 text-slate-600">{item.why_this_length}</p>
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="text-sm font-medium text-slate-500">주제를 선택하면 표시됩니다.</p>
              )}
            </SurfaceCard>

            <SurfaceCard padding="sm" className="space-y-2">
              <p className="text-xs font-black uppercase tracking-[0.14em] text-slate-400">권장 구조</p>
              {uiState.outline.length ? (
                <ul className="space-y-2">
                  {uiState.outline.map(section => (
                    <li key={section.title} className="rounded-xl border border-slate-200 bg-white p-2.5">
                      <p className="text-sm font-bold text-slate-800">{section.title}</p>
                      <p className="mt-1 text-xs font-medium leading-5 text-slate-600">{section.purpose}</p>
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="text-sm font-medium text-slate-500">주제를 선택하면 표시됩니다.</p>
              )}
            </SurfaceCard>
          </div>

          <SurfaceCard
            padding="sm"
            className="min-h-[24rem] overflow-auto bg-slate-950 text-slate-100"
            data-testid="guided-chat-draft-panel"
          >
            <pre className="whitespace-pre-wrap break-words font-mono text-xs leading-6">{uiState.draftMarkdown}</pre>
          </SurfaceCard>
        </SectionCard>
      </div>
    </div>
  );
}
