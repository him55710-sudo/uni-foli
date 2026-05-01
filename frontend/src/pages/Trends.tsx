import React, { useEffect, useMemo, useState } from 'react';
import { AnimatePresence, motion } from 'motion/react';
import {
  ArrowRight,
  BookOpen,
  Check,
  Compass,
  Lightbulb,
  Link2,
  Search,
  Sparkles,
  Target,
  X,
} from 'lucide-react';
import { useLocation, useNavigate } from 'react-router-dom';
import toast from 'react-hot-toast';

import { DIAGNOSIS_STORAGE_KEY } from '../lib/diagnosis';
import { searchMajors } from '../lib/educationCatalog';
import { extractDiagnosisMajorDirectionCandidates } from '../lib/chatbotMode';
import {
  MAJOR_TREND_PLAYBOOK,
  buildMajorChipLabels,
  buildWorkshopPrompt,
  resolveTrendMajorKey,
  type MajorTrendTopic,
  type TrendLens,
  type TrendMajorKey,
} from '../lib/trendCopilot';

interface TrendLocationState {
  major?: string;
  projectId?: string;
}

type TopicWithMajor = MajorTrendTopic & { major?: string };

const neutralPalette = {
  panel: 'from-slate-800 via-slate-700 to-blue-700',
  button: 'bg-slate-900 hover:bg-slate-800',
  tag: 'text-slate-700 bg-slate-50 border-slate-200',
  accent: 'text-blue-700',
  soft: 'bg-blue-50 text-blue-700 border-blue-100',
};

const majorPalette: Record<TrendMajorKey, typeof neutralPalette> = {
  건축: {
    panel: 'from-amber-500/90 via-orange-500/85 to-rose-500/75',
    button: 'bg-amber-600 hover:bg-amber-700',
    tag: 'text-amber-700 bg-amber-50 border-amber-200',
    accent: 'text-amber-700',
    soft: 'bg-amber-50 text-amber-800 border-amber-100',
  },
  컴공: {
    panel: 'from-cyan-500/90 via-sky-500/85 to-indigo-500/75',
    button: 'bg-sky-600 hover:bg-sky-700',
    tag: 'text-sky-700 bg-sky-50 border-sky-200',
    accent: 'text-sky-700',
    soft: 'bg-sky-50 text-sky-800 border-sky-100',
  },
  바이오: {
    panel: 'from-emerald-500/90 via-teal-500/85 to-cyan-500/75',
    button: 'bg-emerald-600 hover:bg-emerald-700',
    tag: 'text-emerald-700 bg-emerald-50 border-emerald-200',
    accent: 'text-emerald-700',
    soft: 'bg-emerald-50 text-emerald-800 border-emerald-100',
  },
  경영: {
    panel: 'from-fuchsia-500/90 via-rose-500/85 to-orange-500/75',
    button: 'bg-rose-600 hover:bg-rose-700',
    tag: 'text-rose-700 bg-rose-50 border-rose-200',
    accent: 'text-rose-700',
    soft: 'bg-rose-50 text-rose-800 border-rose-100',
  },
  사회과학: {
    panel: 'from-violet-500/90 via-purple-500/85 to-indigo-500/75',
    button: 'bg-violet-600 hover:bg-violet-700',
    tag: 'text-violet-700 bg-violet-50 border-violet-200',
    accent: 'text-violet-700',
    soft: 'bg-violet-50 text-violet-800 border-violet-100',
  },
  디자인: {
    panel: 'from-pink-500/90 via-fuchsia-500/85 to-violet-500/75',
    button: 'bg-pink-600 hover:bg-pink-700',
    tag: 'text-pink-700 bg-pink-50 border-pink-200',
    accent: 'text-pink-700',
    soft: 'bg-pink-50 text-pink-800 border-pink-100',
  },
  국어: {
    panel: 'from-teal-500/90 via-emerald-500/85 to-cyan-500/75',
    button: 'bg-teal-600 hover:bg-teal-700',
    tag: 'text-teal-700 bg-teal-50 border-teal-200',
    accent: 'text-teal-700',
    soft: 'bg-teal-50 text-teal-800 border-teal-100',
  },
  수학: {
    panel: 'from-blue-500/90 via-indigo-500/85 to-violet-500/75',
    button: 'bg-blue-600 hover:bg-blue-700',
    tag: 'text-blue-700 bg-blue-50 border-blue-200',
    accent: 'text-blue-700',
    soft: 'bg-blue-50 text-blue-800 border-blue-100',
  },
  영어: {
    panel: 'from-orange-500/90 via-red-500/85 to-rose-500/75',
    button: 'bg-orange-600 hover:bg-orange-700',
    tag: 'text-orange-700 bg-orange-50 border-orange-200',
    accent: 'text-orange-700',
    soft: 'bg-orange-50 text-orange-800 border-orange-100',
  },
  과학탐구: {
    panel: 'from-lime-500/90 via-green-500/85 to-emerald-500/75',
    button: 'bg-lime-600 hover:bg-lime-700',
    tag: 'text-lime-700 bg-lime-50 border-lime-200',
    accent: 'text-lime-700',
    soft: 'bg-lime-50 text-lime-800 border-lime-100',
  },
  사회탐구: {
    panel: 'from-purple-500/90 via-fuchsia-500/85 to-pink-500/75',
    button: 'bg-purple-600 hover:bg-purple-700',
    tag: 'text-purple-700 bg-purple-50 border-purple-200',
    accent: 'text-purple-700',
    soft: 'bg-purple-50 text-purple-800 border-purple-100',
  },
};

function asRecord(value: unknown): Record<string, unknown> | null {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return null;
  return value as Record<string, unknown>;
}

function asText(value: unknown): string | null {
  if (typeof value !== 'string') return null;
  const normalized = value.trim();
  return normalized || null;
}

function readDiagnosisStorageSnapshot(): Record<string, unknown> | null {
  if (typeof window === 'undefined') return null;
  try {
    const raw = localStorage.getItem(DIAGNOSIS_STORAGE_KEY);
    if (!raw) return null;
    return asRecord(JSON.parse(raw));
  } catch (error) {
    console.error('Failed to parse diagnosis storage for trend copilot:', error);
    return null;
  }
}

function resolveWorkshopPath(projectId: string | null): string {
  if (!projectId) return '/app/workshop';
  return `/app/workshop/${encodeURIComponent(projectId)}`;
}

function summaryLine(value: unknown, fallback: string): string {
  const text = asText(value);
  return text || fallback;
}

function compactLine(value: string, max = 58): string {
  if (value.length <= max) return value;
  return `${value.slice(0, max).trim()}...`;
}

function buildCustomMajorTopics(majorLabel: string): MajorTrendTopic[] {
  return [
    {
      id: `custom-${majorLabel}-local`,
      title: `${majorLabel}와 지역 문제 해결`,
      flow: '전공 지식을 학교나 지역사회 문제에 적용하는 탐구 흐름',
      question: `${majorLabel} 관점에서 우리 주변의 불편이나 비효율을 어떻게 정의하고 개선할 수 있을까?`,
      activity: '문제 상황을 관찰하고 원인-근거-개선안을 1페이지 탐구 설계로 정리',
    },
    {
      id: `custom-${majorLabel}-data`,
      title: `${majorLabel} 데이터 탐구`,
      flow: '공개 자료와 간단한 분석을 결합해 주장을 검증하는 흐름',
      question: `${majorLabel}와 관련된 현상을 데이터로 설명하려면 어떤 지표가 필요할까?`,
      activity: '공개 통계나 문헌 3개를 비교해 변수와 평가 기준을 설계',
    },
    {
      id: `custom-${majorLabel}-ethics`,
      title: `${majorLabel}의 사회적 쟁점`,
      flow: '전공 기술이나 제도가 실제 사회에 미치는 영향을 함께 보는 흐름',
      question: `${majorLabel} 분야의 변화가 사용자, 지역, 환경에 주는 영향은 무엇일까?`,
      activity: '찬반 근거를 표로 정리하고 실천 가능한 개선 원칙을 제안',
    },
  ];
}

export function Trends() {
  const navigate = useNavigate();
  const location = useLocation();
  const routeState = (location.state as TrendLocationState | null) ?? null;

  const explicitMajorFromQuery = useMemo(() => {
    const major = new URLSearchParams(location.search).get('major');
    return major?.trim() || null;
  }, [location.search]);
  const explicitMajor = routeState?.major?.trim() || explicitMajorFromQuery;

  const storedDiagnosis = useMemo(readDiagnosisStorageSnapshot, []);
  const storedDiagnosisPayload = asRecord(storedDiagnosis?.diagnosis) ?? null;
  const inferredMajorTop3 = useMemo(
    () => extractDiagnosisMajorDirectionCandidates(storedDiagnosisPayload, 3),
    [storedDiagnosisPayload],
  );
  const diagnosisMajorSuggestions = useMemo(
    () =>
      buildMajorChipLabels({
        explicitMajor,
        inferredMajors: inferredMajorTop3,
        limit: 3,
      }),
    [explicitMajor, inferredMajorTop3],
  );

  const initialMajor = explicitMajor || inferredMajorTop3[0] || '';
  const [selectedMajor, setSelectedMajor] = useState(initialMajor);
  const [majorQuery, setMajorQuery] = useState(initialMajor);
  const [activeLens, setActiveLens] = useState<TrendLens>('flow');
  const [showRecordConnection, setShowRecordConnection] = useState(false);
  const [searchKeyword, setSearchKeyword] = useState('');
  const [subjectKeyword, setSubjectKeyword] = useState('');

  useEffect(() => {
    if (selectedMajor || !initialMajor) return;
    setSelectedMajor(initialMajor);
    setMajorQuery(initialMajor);
  }, [initialMajor, selectedMajor]);

  const majorSuggestions = useMemo(() => {
    const query = majorQuery.trim();
    if (!query) return [];
    return searchMajors(query, null, 8);
  }, [majorQuery]);

  const majorKey = resolveTrendMajorKey(selectedMajor);
  const palette = majorKey ? majorPalette[majorKey] : neutralPalette;

  const allTopics = useMemo<TopicWithMajor[]>(() => {
    const result: TopicWithMajor[] = [];
    Object.entries(MAJOR_TREND_PLAYBOOK).forEach(([major, topics]) => {
      topics.forEach(topic => result.push({ ...topic, major }));
    });
    return result;
  }, []);

  const selectedMajorTopics = useMemo<MajorTrendTopic[]>(() => {
    if (!selectedMajor.trim()) return [];
    if (majorKey) return MAJOR_TREND_PLAYBOOK[majorKey] || [];
    return buildCustomMajorTopics(selectedMajor.trim());
  }, [majorKey, selectedMajor]);

  const displayedTopics = useMemo<TopicWithMajor[]>(() => {
    const keyword = searchKeyword.trim().toLowerCase();
    if (keyword) {
      return allTopics.filter(topic =>
        topic.title.toLowerCase().includes(keyword) ||
        topic.flow.toLowerCase().includes(keyword) ||
        topic.question.toLowerCase().includes(keyword) ||
        topic.activity.toLowerCase().includes(keyword) ||
        (topic.major || '').toLowerCase().includes(keyword),
      );
    }
    return selectedMajorTopics.map(topic => ({ ...topic, major: selectedMajor }));
  }, [allTopics, searchKeyword, selectedMajor, selectedMajorTopics]);

  const diagnosisSummary = asRecord(storedDiagnosisPayload?.diagnosis_summary_json) ?? null;
  const diagnosisContext = asRecord(storedDiagnosisPayload?.chatbot_context_json) ?? null;
  const storedProjectId = asText(storedDiagnosis?.projectId);
  const projectId = routeState?.projectId?.trim() || storedProjectId || null;
  const workshopPath = resolveWorkshopPath(projectId);

  const sourceLabel = selectedMajor
    ? diagnosisMajorSuggestions.includes(selectedMajor)
      ? '진단 기반 학과'
      : '직접 선택한 학과'
    : '학과 선택 전';

  const recordLinkHint = [
    summaryLine(diagnosisSummary?.headline, '진단 헤드라인 없음'),
    summaryLine(diagnosisSummary?.recommended_focus, '추천 초점 없음'),
    summaryLine(
      diagnosisContext?.major_alignment_hints && Array.isArray(diagnosisContext.major_alignment_hints)
        ? diagnosisContext.major_alignment_hints[0]
        : null,
      '전공 연계 힌트 없음',
    ),
  ];

  const lensItems: Array<{ key: TrendLens; label: string; icon: React.ComponentType<{ size?: number }> }> = [
    { key: 'flow', label: '흐름', icon: Sparkles },
    { key: 'question', label: '질문', icon: Target },
    { key: 'activity', label: '활동', icon: Lightbulb },
  ];

  const applyMajor = (major: string) => {
    const normalized = major.trim();
    if (!normalized) {
      toast.error('학과명을 입력해 주세요.');
      return;
    }
    setSelectedMajor(normalized);
    setMajorQuery(normalized);
    setSearchKeyword('');
    setShowRecordConnection(false);
    toast.success(`${normalized} 기준으로 탐구주제를 맞췄습니다.`);
  };

  const clearMajor = () => {
    setSelectedMajor('');
    setMajorQuery('');
    setSearchKeyword('');
    setShowRecordConnection(false);
  };

  const runSubjectSearch = () => {
    const keyword = subjectKeyword.trim();
    if (!keyword) {
      toast.error('과목명이나 키워드를 입력해 주세요.');
      return;
    }
    setSearchKeyword(keyword);
    toast.success(`'${keyword}' 관련 탐구주제를 검색합니다.`);
  };

  const handleStartWorkshop = (topic?: MajorTrendTopic) => {
    const majorLabel = selectedMajor || majorQuery.trim();
    if (!majorLabel) {
      toast.error('먼저 학과를 선택해 주세요.');
      return;
    }

    const prompt = topic ? buildWorkshopPrompt(topic, majorLabel) : undefined;
    navigate(workshopPath, {
      state: {
        major: majorLabel,
        chatbotMode: 'trend',
        fromTrend: true,
        trendTopicId: topic?.id ?? null,
        trendPrompt: prompt ?? null,
        projectId: projectId ?? undefined,
      },
    });
    toast.success(topic ? '선택 주제로 워크숍을 열었습니다.' : '트렌드 모드로 워크숍을 열었습니다.');
  };

  const hasMajorQuery = Boolean(majorQuery.trim());
  const canApplyTypedMajor = hasMajorQuery && majorQuery.trim() !== selectedMajor;
  const titleText = selectedMajor ? `${selectedMajor} 맞춤 탐구주제` : '학과를 검색해 탐구주제를 맞춰보세요';
  const resultLabel = searchKeyword.trim()
    ? `'${searchKeyword.trim()}' 검색 결과`
    : selectedMajor
      ? `${selectedMajor} 추천 주제`
      : '학과 선택 필요';

  return (
    <div className="mx-auto max-w-6xl space-y-6 px-3 py-4 sm:px-5 sm:py-7">
      <motion.section
        initial={{ opacity: 0, y: 14 }}
        animate={{ opacity: 1, y: 0 }}
        className="relative overflow-hidden rounded-[2rem] border border-slate-200 bg-white p-5 shadow-[0_26px_52px_-36px_rgba(15,23,42,0.55)] sm:p-7"
      >
        <div className="grid gap-7 lg:grid-cols-[0.95fr_1.05fr] lg:items-start">
          <div className="space-y-5">
            <div className="inline-flex items-center gap-2 rounded-full border border-slate-200 bg-white px-3 py-1 text-xs font-black text-slate-700">
              <Compass size={14} />
              Major Trend Copilot
            </div>

            <div className="space-y-3">
              <h1 className="text-2xl font-black leading-tight text-slate-950 sm:text-4xl">
                {titleText}
              </h1>
              <p className="max-w-xl text-sm font-semibold leading-6 text-slate-500">
                고정 전공 칩 대신 실제 지원 학과를 검색하고, 선택한 학과에 맞춰 탐구주제와 실행 활동을 정리합니다.
              </p>
            </div>

            <div className="flex flex-wrap items-center gap-2">
              <span className={`rounded-full border px-3 py-1 text-xs font-black ${palette.soft}`}>
                {sourceLabel}
              </span>
              {selectedMajor ? (
                <button
                  type="button"
                  onClick={clearMajor}
                  className="inline-flex items-center gap-1 rounded-full border border-slate-200 bg-white px-3 py-1 text-xs font-black text-slate-500 transition hover:border-slate-300 hover:bg-slate-50"
                >
                  <X size={13} />
                  학과 초기화
                </button>
              ) : null}
            </div>

            {diagnosisMajorSuggestions.length > 0 ? (
              <div className="space-y-2">
                <p className="text-xs font-black uppercase tracking-widest text-slate-400">AI 진단에서 찾은 학과</p>
                <div className="flex flex-wrap gap-2">
                  {diagnosisMajorSuggestions.map((major) => (
                    <button
                      key={major}
                      type="button"
                      onClick={() => applyMajor(major)}
                      className={`rounded-full border px-3 py-1.5 text-sm font-extrabold transition ${
                        selectedMajor === major
                          ? 'border-blue-600 bg-blue-600 text-white shadow-md shadow-blue-200'
                          : 'border-slate-200 bg-white text-slate-700 hover:border-blue-200 hover:bg-blue-50 hover:text-blue-700'
                      }`}
                    >
                      {major}
                    </button>
                  ))}
                </div>
              </div>
            ) : null}

            <div className="flex flex-wrap gap-2">
              {lensItems.map((lens) => (
                <button
                  key={lens.key}
                  type="button"
                  onClick={() => setActiveLens(lens.key)}
                  className={`inline-flex items-center gap-2 rounded-full px-3 py-1.5 text-sm font-bold transition ${
                    activeLens === lens.key
                      ? 'bg-slate-900 text-white'
                      : 'border border-slate-200 bg-white text-slate-600 hover:border-slate-400'
                  }`}
                >
                  <lens.icon size={14} />
                  {lens.label}
                </button>
              ))}
            </div>
          </div>

          <div className="space-y-4">
            <div className="rounded-[1.6rem] border border-slate-200 bg-slate-50/80 p-4 sm:p-5">
              <label htmlFor="major-search" className="text-sm font-black text-slate-900">
                학과 검색
              </label>
              <div className="mt-3 flex flex-col gap-2 sm:flex-row">
                <div className="relative flex-1">
                  <Search className="pointer-events-none absolute left-4 top-1/2 -translate-y-1/2 text-slate-400" size={18} />
                  <input
                    id="major-search"
                    type="text"
                    value={majorQuery}
                    onChange={(event) => setMajorQuery(event.target.value)}
                    onKeyDown={(event) => {
                      if (event.key === 'Enter') applyMajor(majorQuery);
                    }}
                    placeholder="예: 컴퓨터공학과, 생명과학과, 경영학과"
                    className="h-12 w-full rounded-2xl border border-slate-300 bg-white py-3 pl-11 pr-4 text-sm font-bold text-slate-800 outline-none transition placeholder:text-slate-400 focus:border-blue-500 focus:ring-4 focus:ring-blue-100"
                  />
                </div>
                <button
                  type="button"
                  onClick={() => applyMajor(majorQuery)}
                  className="inline-flex h-12 items-center justify-center gap-2 rounded-2xl bg-blue-600 px-5 text-sm font-black text-white transition hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-50"
                  disabled={!hasMajorQuery}
                >
                  <Check size={16} />
                  적용
                </button>
              </div>

              <AnimatePresence initial={false}>
                {majorSuggestions.length > 0 ? (
                  <motion.div
                    initial={{ opacity: 0, y: -4 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0, y: -4 }}
                    className="mt-3 grid gap-2 sm:grid-cols-2"
                  >
                    {majorSuggestions.map((suggestion) => (
                      <button
                        key={suggestion.id}
                        type="button"
                        onClick={() => applyMajor(suggestion.label)}
                        className="min-h-11 rounded-2xl border border-slate-200 bg-white px-3 py-2 text-left text-sm font-bold text-slate-700 transition hover:border-blue-200 hover:bg-blue-50 hover:text-blue-700"
                      >
                        {suggestion.label}
                      </button>
                    ))}
                  </motion.div>
                ) : canApplyTypedMajor ? (
                  <motion.div
                    initial={{ opacity: 0, y: -4 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0, y: -4 }}
                    className="mt-3 rounded-2xl border border-slate-200 bg-white px-4 py-3"
                  >
                    <p className="text-sm font-semibold text-slate-500">
                      목록에 없어도 입력한 학과명으로 맞춤 주제를 만들 수 있습니다.
                    </p>
                    <button
                      type="button"
                      onClick={() => applyMajor(majorQuery)}
                      className="mt-2 text-sm font-black text-blue-700 hover:text-blue-800"
                    >
                      "{majorQuery.trim()}"로 적용
                    </button>
                  </motion.div>
                ) : null}
              </AnimatePresence>
            </div>

            <div className="grid gap-3 sm:grid-cols-2">
              <div className="rounded-[1.4rem] border border-slate-200 bg-white p-4">
                <div className="flex items-center gap-2">
                  <Search size={18} className="text-slate-400" />
                  <h2 className="text-sm font-black text-slate-900">키워드 검색</h2>
                </div>
                <input
                  type="text"
                  placeholder="예: 인공지능, 기후변화"
                  value={searchKeyword}
                  onChange={(event) => setSearchKeyword(event.target.value)}
                  className="mt-3 h-11 w-full rounded-xl border border-slate-300 px-3 text-sm font-bold outline-none focus:border-blue-500 focus:ring-4 focus:ring-blue-100"
                />
              </div>

              <div className="rounded-[1.4rem] border border-slate-200 bg-white p-4">
                <div className="flex items-center gap-2">
                  <BookOpen size={18} className="text-slate-400" />
                  <h2 className="text-sm font-black text-slate-900">교과목 검색</h2>
                </div>
                <div className="mt-3 flex gap-2">
                  <input
                    type="text"
                    placeholder="예: 생명과학, 확률과 통계"
                    value={subjectKeyword}
                    onChange={(event) => setSubjectKeyword(event.target.value)}
                    onKeyDown={(event) => {
                      if (event.key === 'Enter') runSubjectSearch();
                    }}
                    className="h-11 min-w-0 flex-1 rounded-xl border border-slate-300 px-3 text-sm font-bold outline-none focus:border-blue-500 focus:ring-4 focus:ring-blue-100"
                  />
                  <button
                    type="button"
                    onClick={runSubjectSearch}
                    className="h-11 rounded-xl bg-slate-900 px-3 text-sm font-black text-white transition hover:bg-slate-700"
                  >
                    검색
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>
      </motion.section>

      <motion.section
        initial={{ opacity: 0, y: 14 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.05 }}
        className="space-y-4"
      >
        <div className="flex flex-col justify-between gap-3 sm:flex-row sm:items-center">
          <div>
            <p className="text-xs font-black uppercase tracking-widest text-slate-400">Topics</p>
            <h2 className="mt-1 text-xl font-black text-slate-950">{resultLabel}</h2>
          </div>
          <div className="flex flex-wrap gap-2">
            {searchKeyword.trim() ? (
              <button
                type="button"
                onClick={() => setSearchKeyword('')}
                className="inline-flex items-center gap-2 rounded-full border border-slate-200 bg-white px-3 py-1.5 text-sm font-bold text-slate-600 transition hover:bg-slate-50"
              >
                <X size={14} />
                검색 해제
              </button>
            ) : null}
            <button
              type="button"
              onClick={() => handleStartWorkshop()}
              className="inline-flex items-center gap-2 rounded-full border border-slate-200 bg-white px-3 py-1.5 text-sm font-bold text-slate-700 transition hover:border-slate-300 hover:bg-slate-50"
            >
              워크숍으로 가져가기
              <ArrowRight size={14} />
            </button>
            <button
              type="button"
              onClick={() => setShowRecordConnection((prev) => !prev)}
              className={`inline-flex items-center gap-2 rounded-full border px-3 py-1.5 text-sm font-bold transition ${
                showRecordConnection
                  ? 'border-emerald-500 bg-emerald-600 text-white'
                  : 'border-emerald-200 bg-white text-emerald-700 hover:bg-emerald-50'
              }`}
            >
              <Link2 size={14} />
              학생부 연결
            </button>
          </div>
        </div>

        {!selectedMajor && !searchKeyword.trim() ? (
          <div className="rounded-[1.6rem] border border-dashed border-slate-300 bg-white px-6 py-10 text-center">
            <div className="mx-auto mb-3 flex h-12 w-12 items-center justify-center rounded-2xl bg-blue-50 text-blue-600">
              <Search size={22} />
            </div>
            <h3 className="text-lg font-black text-slate-950">학과를 먼저 검색해 주세요.</h3>
            <p className="mx-auto mt-2 max-w-xl text-sm font-semibold leading-6 text-slate-500">
              선택한 학과명으로 주제 방향을 맞추고, 목록에 없는 학과도 직접 입력해 사용할 수 있습니다.
            </p>
          </div>
        ) : displayedTopics.length === 0 ? (
          <div className="rounded-[1.6rem] border border-dashed border-slate-300 bg-white px-6 py-10 text-center">
            <div className="mx-auto mb-3 flex h-12 w-12 items-center justify-center rounded-2xl bg-slate-100 text-slate-500">
              <Target size={22} />
            </div>
            <h3 className="text-lg font-black text-slate-950">검색 결과가 없습니다.</h3>
            <p className="mx-auto mt-2 max-w-xl text-sm font-semibold leading-6 text-slate-500">
              더 넓은 키워드로 검색하거나 학과명을 적용해 맞춤 주제를 확인해 주세요.
            </p>
          </div>
        ) : (
          <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
            {displayedTopics.map((topic, index) => {
              const topicLine = activeLens === 'flow'
                ? topic.flow
                : activeLens === 'question'
                  ? topic.question
                  : topic.activity;
              const topicMajorLabel = searchKeyword.trim()
                ? topic.major ? `${topic.major} 계열` : '검색 결과'
                : selectedMajor;
              const topicKey = resolveTrendMajorKey(topic.major || selectedMajor);
              const topicPalette = topicKey ? majorPalette[topicKey] : palette;

              return (
                <motion.article
                  key={topic.id}
                  initial={{ opacity: 0, y: 20 }}
                  whileInView={{ opacity: 1, y: 0 }}
                  viewport={{ once: true, amount: 0.25 }}
                  transition={{ duration: 0.35, delay: index * 0.04 }}
                  className="flex h-full min-h-[320px] flex-col overflow-hidden rounded-[1.6rem] border border-slate-200 bg-white shadow-[0_22px_40px_-30px_rgba(15,23,42,0.55)]"
                >
                  <div className={`relative h-24 bg-gradient-to-br ${topicPalette.panel}`}>
                    <div className="absolute left-4 top-4 max-w-[75%] rounded-full bg-white/20 px-3 py-1 text-xs font-black text-white">
                      <span className="line-clamp-1">{topicMajorLabel}</span>
                    </div>
                    <div className="absolute bottom-4 right-4 text-xs font-black text-white/85">
                      {String(index + 1).padStart(2, '0')}
                    </div>
                  </div>

                  <div className="flex flex-1 flex-col p-5">
                    <h3 className="text-lg font-black leading-snug text-slate-950">{topic.title}</h3>
                    <p className="mt-3 min-h-[72px] text-sm font-semibold leading-6 text-slate-600">
                      {compactLine(topicLine)}
                    </p>

                    <div className="mt-4 flex flex-wrap gap-2">
                      <span className={`rounded-full border px-2.5 py-1 text-[11px] font-black ${topicPalette.tag}`}>
                        {activeLens === 'flow' ? '흐름' : activeLens === 'question' ? '질문' : '활동'}
                      </span>
                      <span className="rounded-full border border-slate-200 bg-white px-2.5 py-1 text-[11px] font-black text-slate-600">
                        실행 연결
                      </span>
                    </div>

                    <div className="mt-auto pt-5">
                      <button
                        type="button"
                        onClick={() => handleStartWorkshop(topic)}
                        className={`inline-flex min-h-11 items-center gap-2 rounded-xl px-3 py-2 text-sm font-extrabold text-white transition ${topicPalette.button}`}
                      >
                        이 주제로 설계하기
                        <ArrowRight size={14} />
                      </button>
                    </div>
                  </div>
                </motion.article>
              );
            })}
          </div>
        )}
      </motion.section>

      {showRecordConnection && (
        <motion.section
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          className="rounded-[1.6rem] border border-emerald-200 bg-emerald-50/70 p-4 sm:p-5"
        >
          <h2 className="mb-3 flex items-center gap-2 text-lg font-black text-emerald-900">
            <Link2 size={18} />
            학생부 연결 포인트
          </h2>

          <div className="grid gap-3 sm:grid-cols-3">
            {recordLinkHint.map((item, index) => (
              <div key={index} className="rounded-2xl border border-emerald-200 bg-white px-3 py-3 text-sm font-semibold text-emerald-900">
                {compactLine(item, 52)}
              </div>
            ))}
          </div>

          <div className="mt-4 flex flex-wrap gap-2">
            {displayedTopics[0] ? (
              <button
                type="button"
                onClick={() => handleStartWorkshop(displayedTopics[0])}
                className="rounded-full bg-emerald-600 px-3 py-1.5 text-sm font-extrabold text-white transition hover:bg-emerald-700"
              >
                주제 계획 시작
              </button>
            ) : null}
            <button
              type="button"
              onClick={() =>
                navigate('/app/diagnosis', {
                  state: { projectId: projectId ?? undefined },
                })
              }
              className="rounded-full border border-emerald-300 bg-white px-3 py-1.5 text-sm font-extrabold text-emerald-800 transition hover:bg-emerald-100"
            >
              진단 결과 다시 보기
            </button>
          </div>
        </motion.section>
      )}
    </div>
  );
}
