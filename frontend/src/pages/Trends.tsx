import React, { useEffect, useMemo, useState } from 'react';
import { motion } from 'motion/react';
import { ArrowRight, Compass, Lightbulb, Link2, Sparkles, Target } from 'lucide-react';
import { useLocation, useNavigate } from 'react-router-dom';
import toast from 'react-hot-toast';
import { DIAGNOSIS_STORAGE_KEY } from '../lib/diagnosis';
import { extractDiagnosisMajorDirectionCandidates } from '../lib/chatbotMode';
import {
  MAJOR_TREND_PLAYBOOK,
  buildMajorChipLabels,
  buildWorkshopPrompt,
  resolveTrendMajorKey,
  type MajorTrendTopic,
  type TrendLens,
} from '../lib/trendCopilot';

interface TrendLocationState {
  major?: string;
  projectId?: string;
}

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

  const majorChips = useMemo(
    () =>
      buildMajorChipLabels({
        explicitMajor,
        inferredMajors: inferredMajorTop3,
      }),
    [explicitMajor, inferredMajorTop3],
  );

  const [selectedMajor, setSelectedMajor] = useState<string>(majorChips[0] || '컴공');
  const [activeLens, setActiveLens] = useState<TrendLens>('flow');
  const [showRecordConnection, setShowRecordConnection] = useState(false);

  useEffect(() => {
    if (!majorChips.length) return;
    if (!majorChips.includes(selectedMajor)) {
      setSelectedMajor(majorChips[0]);
    }
  }, [majorChips, selectedMajor]);

  const majorKey = resolveTrendMajorKey(selectedMajor);
  const trendTopics = MAJOR_TREND_PLAYBOOK[majorKey];

  const diagnosisSummary = asRecord(storedDiagnosisPayload?.diagnosis_summary_json) ?? null;
  const diagnosisContext = asRecord(storedDiagnosisPayload?.chatbot_context_json) ?? null;
  const storedProjectId = asText(storedDiagnosis?.projectId);
  const projectId = routeState?.projectId?.trim() || storedProjectId || null;
  const workshopPath = resolveWorkshopPath(projectId);

  const sourceLabel = explicitMajor
    ? '직접 선택한 목표 전공 기준'
    : inferredMajorTop3.length > 0
      ? '진단 기반 추정 전공 Top 3 기준'
      : '기본 전공 트렌드 기준';

  const handleStartWorkshop = (topic?: MajorTrendTopic) => {
    const prompt = topic ? buildWorkshopPrompt(topic, selectedMajor) : undefined;
    navigate(workshopPath, {
      state: {
        major: selectedMajor,
        chatbotMode: 'trend',
        fromTrend: true,
        trendTopicId: topic?.id ?? null,
        trendPrompt: prompt ?? null,
        projectId: projectId ?? undefined,
      },
    });
    toast.success(topic ? '선택한 주제로 워크숍을 열었습니다.' : '트렌드 모드로 워크숍을 열었습니다.');
  };

  const recordLinkHint = [
    summaryLine(diagnosisSummary?.headline, '최근 진단 헤드라인이 아직 없습니다.'),
    summaryLine(diagnosisSummary?.recommended_focus, '추천 초점이 없어 기본 실행 루틴을 안내합니다.'),
    summaryLine(
      diagnosisContext?.major_alignment_hints && Array.isArray(diagnosisContext.major_alignment_hints)
        ? diagnosisContext.major_alignment_hints[0]
        : null,
      '진단 기반 전공 적합성 힌트를 추가로 불러오지 못했습니다.',
    ),
  ];

  return (
    <div className="mx-auto max-w-6xl space-y-6 px-3 py-4 sm:px-5 sm:py-7">
      <motion.section initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} className="space-y-4">
        <div className="rounded-3xl border border-[#d9e5ff] bg-[linear-gradient(145deg,#f4f8ff_0%,#ffffff_72%)] p-5 sm:p-7">
          <div className="mb-3 inline-flex items-center gap-2 rounded-full border border-[#c9dafc] bg-white px-3 py-1 text-xs font-extrabold text-[#004aad]">
            <Compass size={14} />
            전공별 탐구주제 트렌드 코파일럿
          </div>
          <h1 className="text-2xl font-black text-slate-900 sm:text-3xl">
            {selectedMajor} 기준 탐구주제 방향을 빠르게 고르고 실행으로 넘기기
          </h1>
          <p className="mt-2 text-sm font-semibold text-slate-600 sm:text-base">
            {sourceLabel} · 짧은 칩으로 주제 흐름을 탐색하고 바로 워크숍 설계로 연결합니다.
          </p>
          <div className="mt-4 flex flex-wrap gap-2">
            {majorChips.map((chip) => (
              <button
                key={chip}
                type="button"
                onClick={() => {
                  setSelectedMajor(chip);
                  setShowRecordConnection(false);
                }}
                className={`rounded-full px-3 py-1.5 text-sm font-extrabold transition ${
                  chip === selectedMajor
                    ? 'bg-[#004aad] text-white shadow-[0_8px_18px_rgba(0,74,173,0.25)]'
                    : 'border border-slate-200 bg-white text-slate-600 hover:border-[#004aad]/40 hover:text-[#004aad]'
                }`}
              >
                {chip}
              </button>
            ))}
            <button
              type="button"
              onClick={() => setShowRecordConnection((prev) => !prev)}
              className={`rounded-full px-3 py-1.5 text-sm font-extrabold transition ${
                showRecordConnection
                  ? 'bg-emerald-600 text-white shadow-[0_8px_18px_rgba(5,150,105,0.25)]'
                  : 'border border-emerald-200 bg-white text-emerald-700 hover:bg-emerald-50'
              }`}
            >
              내 학생부와 연결하기
            </button>
          </div>
        </div>
      </motion.section>

      <motion.section
        initial={{ opacity: 0, y: 14 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.05 }}
        className="space-y-4"
      >
        <div className="flex flex-wrap items-center gap-2">
          {[
            { key: 'flow', label: '핵심 흐름', icon: Sparkles },
            { key: 'question', label: '탐구 질문', icon: Target },
            { key: 'activity', label: '활동 연결', icon: Lightbulb },
          ].map((lens) => (
            <button
              key={lens.key}
              type="button"
              onClick={() => setActiveLens(lens.key as TrendLens)}
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
          <button
            type="button"
            onClick={() => handleStartWorkshop()}
            className="inline-flex items-center gap-2 rounded-full border border-[#c8dafd] bg-[#eff5ff] px-3 py-1.5 text-sm font-bold text-[#004aad] transition hover:bg-[#dfeaff]"
          >
            워크숍으로 가져가기
            <ArrowRight size={14} />
          </button>
        </div>

        <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
          {trendTopics.map((topic) => (
            <article
              key={topic.id}
              className="flex h-full flex-col rounded-2xl border border-slate-200 bg-white p-4 shadow-[0_8px_20px_rgba(15,23,42,0.06)]"
            >
              <p className="mb-2 text-xs font-extrabold uppercase tracking-wide text-[#004aad]">{selectedMajor} 탐구 트렌드</p>
              <h3 className="text-lg font-black text-slate-900">{topic.title}</h3>
              <p className="mt-3 text-sm font-medium leading-6 text-slate-600">
                {activeLens === 'flow' ? topic.flow : activeLens === 'question' ? topic.question : topic.activity}
              </p>
              <div className="mt-auto pt-4">
                <button
                  type="button"
                  onClick={() => handleStartWorkshop(topic)}
                  className="inline-flex items-center gap-2 rounded-xl bg-[#004aad] px-3 py-2 text-sm font-extrabold text-white transition hover:brightness-110"
                >
                  이 주제로 설계하기
                  <ArrowRight size={14} />
                </button>
              </div>
            </article>
          ))}
        </div>
      </motion.section>

      {showRecordConnection && (
        <motion.section
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          className="rounded-2xl border border-emerald-200 bg-emerald-50/60 p-4 sm:p-5"
        >
          <h2 className="mb-2 flex items-center gap-2 text-lg font-black text-emerald-900">
            <Link2 size={18} />
            내 학생부와 연결하기
          </h2>
          <ul className="space-y-2 text-sm font-semibold text-emerald-900/90">
            <li>진단 요약: {recordLinkHint[0]}</li>
            <li>현재 초점: {recordLinkHint[1]}</li>
            <li>전공 연계 힌트: {recordLinkHint[2]}</li>
          </ul>

          <div className="mt-4 flex flex-wrap gap-2">
            <button
              type="button"
              onClick={() => handleStartWorkshop(trendTopics[0])}
              className="rounded-full bg-emerald-600 px-3 py-1.5 text-sm font-extrabold text-white transition hover:bg-emerald-700"
            >
              주제 계획 시작
            </button>
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

