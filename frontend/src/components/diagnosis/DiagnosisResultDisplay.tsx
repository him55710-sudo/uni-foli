import React from 'react';
import { motion } from 'motion/react';
import { useNavigate } from 'react-router-dom';
import { CheckCircle2, AlertTriangle, Zap, Clock, Download, AlertCircle, Gauge, Compass, Target, Mic } from 'lucide-react';
import { SectionCard, SurfaceCard, StatusBadge, PrimaryButton } from '../primitives';
import { formatRiskLevel } from '../../lib/diagnosis';
import { DiagnosisRunResponse } from '../../types/api';
import { DiagnosisRelationalGraph } from './DiagnosisRelationalGraph';


interface DiagnosisResultDisplayProps {
  diagnosisResult: any;
  diagnosisRun?: DiagnosisRunResponse | null;
  projectId?: string;
}

const NEEDS_SUPPORT_PATTERN = /\bneeds?\s+support\b/gi;

function asRecord(value: unknown): Record<string, unknown> | null {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return null;
  return value as Record<string, unknown>;
}

function asNumber(value: unknown): number | null {
  if (typeof value === 'number' && Number.isFinite(value)) return value;
  if (typeof value === 'string' && value.trim()) {
    const parsed = Number(value);
    if (Number.isFinite(parsed)) return parsed;
  }
  return null;
}

function sanitizeKoreanText(value: unknown, fallback = '내용을 정리 중입니다.'): string {
  const source = String(value ?? '').trim();
  if (!source) return fallback;
  const replaced = source.replace(NEEDS_SUPPORT_PATTERN, '보완 필요');
  const cleaned = replaced.replace(/\s{2,}/g, ' ').trim();
  return cleaned || fallback;
}

function sanitizeList(values: unknown, fallback: string): string[] {
  if (!Array.isArray(values)) return [fallback];
  const normalized = values
    .map((item) => sanitizeKoreanText(item, ''))
    .filter(Boolean);
  return normalized.length ? normalized : [fallback];
}

function normalizeScoreLabel(value: unknown): string {
  const text = String(value ?? '').trim();
  if (!text) return '진단 참고';
  return text;
}

function scoreBadgeStatus(label: string): 'success' | 'active' | 'warning' | 'danger' | 'neutral' {
  if (label.includes('매우 우수')) return 'success';
  if (label.includes('우수')) return 'active';
  if (label.includes('보통')) return 'neutral';
  if (label.includes('집중 보완')) return 'danger';
  return 'warning';
}

function completionStateLabel(value: unknown): string | null {
  const key = String(value ?? '').trim().toLowerCase();
  if (!key) return null;
  if (key === 'finalized') return '기록 마감 단계';
  if (key === 'ongoing') return '개선 가능 단계';
  return '상태 확인 중';
}

export const DiagnosisResultDisplay: React.FC<DiagnosisResultDisplayProps> = ({ diagnosisResult, diagnosisRun, projectId }) => {
  const navigate = useNavigate();
  const summaryJson = asRecord(diagnosisResult?.diagnosis_summary_json);
  const totalScore = summaryJson ? asNumber(summaryJson.total_score) : null;
  const categoryScoresRaw = summaryJson ? asRecord(summaryJson.category_scores) : null;
  const scoreLabelsRaw = summaryJson ? asRecord(summaryJson.score_labels) : null;
  const scoreExplanationsRaw = summaryJson ? asRecord(summaryJson.score_explanations) : null;
  const majorDirectionsRaw = summaryJson?.major_direction_candidates_top3;
  const completionState = completionStateLabel(
    summaryJson?.completion_state || diagnosisResult?.record_completion_state
  );
  const stageMode = String(summaryJson?.stage_aware_recommendation_mode ?? '').trim();
  const stageModeNote = String(summaryJson?.stage_aware_recommendation_note ?? '').trim();

  const categoryScores = categoryScoresRaw
    ? Object.entries(categoryScoresRaw)
        .map(([name, value]) => ({ name, score: asNumber(value) }))
        .filter((item): item is { name: string; score: number } => Number.isFinite(item.score))
    : [];

  const majorDirections = Array.isArray(majorDirectionsRaw)
    ? majorDirectionsRaw
        .map((item) => {
          const record = asRecord(item);
          return {
            label: sanitizeKoreanText(record?.label, ''),
            summary: sanitizeKoreanText(record?.summary, ''),
          };
        })
        .filter((item) => item.label)
        .slice(0, 3)
    : [];

  const strengths = sanitizeList(diagnosisResult.strengths, '강점 항목을 정리 중입니다.');
  const gaps = sanitizeList(
    diagnosisResult.detailed_gaps?.length
      ? diagnosisResult.detailed_gaps.map((gap: any) => `${gap.title}: ${gap.description}`)
      : diagnosisResult.gaps,
    '보완 항목을 정리 중입니다.',
  );
  const nextActions = sanitizeList(diagnosisResult.next_actions, '다음 실행 과제를 정리 중입니다.');

  const reportStatus = (diagnosisRun?.report_status || diagnosisRun?.report_async_job_status || '').toUpperCase();

  return (
    <motion.div
      key="result"
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0 }}
      className="space-y-8"
    >
      {/* 1. Header Area: Hybrid Overview & Total Score */}
      <div className="grid gap-6 lg:grid-cols-12">
        <div className="lg:col-span-8">
          <SectionCard
            title={sanitizeKoreanText(diagnosisResult.headline, '진단 결과')}
            description="인공지능이 분석한 나의 입시 경쟁력 요약 리포트입니다."
            eyebrow="인공지능 정밀 진단"
            className="h-full border-none bg-white shadow-xl ring-1 ring-slate-200/50"
            actions={
              <div className="flex flex-wrap items-center gap-2">
                <div
                  className={`flex items-center gap-2 rounded-full px-4 py-1.5 text-xs font-black shadow-lg ${
                    diagnosisResult.risk_level === 'safe'
                      ? 'bg-emerald-500 text-white shadow-emerald-500/20'
                      : diagnosisResult.risk_level === 'warning'
                        ? 'bg-amber-500 text-white shadow-amber-500/20'
                        : 'bg-rose-500 text-white shadow-rose-500/20'
                  }`}
                >
                  {formatRiskLevel(diagnosisResult.risk_level)}
                </div>
                {completionState && (
                  <StatusBadge status="neutral">
                    {completionState}
                  </StatusBadge>
                )}
                {summaryJson?.completion_state === 'finalized' && projectId && (
                  <PrimaryButton
                    size="sm"
                    className="h-8 rounded-full bg-[#004aad] text-[10px] font-black shadow-lg shadow-[#004aad]/20"
                    onClick={() => navigate(`/app/interview/${projectId}`)}
                  >
                    <Mic size={12} className="mr-1" />
                    AI 실전 면접 연습
                  </PrimaryButton>
                )}
              </div>
            }
          >
            {diagnosisResult.overview && (
              <div className="rounded-2xl bg-slate-50/80 p-6">
                <p className="text-base font-bold leading-relaxed text-slate-700">
                  <span className="mb-2 block text-[10px] font-black uppercase tracking-widest text-slate-400">
                    종합 분석 의견
                  </span>
                  {sanitizeKoreanText(diagnosisResult.overview)}
                </p>
              </div>
            )}
          </SectionCard>
        </div>

        <div className="lg:col-span-4">
          <SurfaceCard className="flex h-full flex-col items-center justify-center border-none bg-[linear-gradient(135deg,#004aad_0%,#00214d_100%)] p-8 text-white shadow-2xl">
            <div className="mb-2 flex items-center gap-2 opacity-60">
              <Gauge size={16} />
              <span className="text-[10px] font-black uppercase tracking-widest">Total Diagnostic Score</span>
            </div>
            {totalScore !== null ? (
              <div className="flex flex-col items-center">
                <span className="text-7xl font-black tracking-tighter leading-none">{Math.round(totalScore)}</span>
                <div className="mt-6">
                  <StatusBadge status={scoreBadgeStatus(normalizeScoreLabel(scoreLabelsRaw?.['총점']))}>
                    {normalizeScoreLabel(scoreLabelsRaw?.['총점'])}
                  </StatusBadge>
                </div>
              </div>
            ) : (
              <div className="flex flex-col items-center opacity-30">
                <Clock size={48} />
                <p className="mt-4 text-xs font-bold uppercase tracking-widest">Calculation Pending</p>
              </div>
            )}
          </SurfaceCard>
        </div>
      </div>

      {/* 2. Category Intelligence Cards */}
      {categoryScores.length > 0 && (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {categoryScores.map(({ name, score }) => (
            <SurfaceCard key={name} className="group border-none bg-white p-5 shadow-sm ring-1 ring-slate-200/70 hover:shadow-md hover:ring-[#004aad]/20 transition-all">
              <div className="flex items-start justify-between mb-3">
                <span className="text-[10px] font-black text-slate-400 uppercase tracking-widest">{sanitizeKoreanText(name, '항목')}</span>
                <StatusBadge status={scoreBadgeStatus(normalizeScoreLabel(scoreLabelsRaw?.[name]))}>
                  {normalizeScoreLabel(scoreLabelsRaw?.[name])}
                </StatusBadge>
              </div>
              <div className="flex items-end gap-1">
                <span className="text-3xl font-black text-slate-900 group-hover:text-[#004aad] transition-colors">{Math.round(score)}</span>
                <span className="mb-1 text-xs font-bold text-slate-400 italic">/ 100</span>
              </div>
              {scoreExplanationsRaw?.[name] && (
                <p className="mt-3 text-xs font-semibold leading-relaxed text-slate-500 border-t border-slate-50 pt-3">
                  {sanitizeKoreanText(scoreExplanationsRaw[name], '')}
                </p>
              )}
            </SurfaceCard>
          ))}
        </div>
      )}

      {/* 3. Major Discovery Top 3 */}
      {majorDirections.length > 0 && (
        <div className="relative overflow-hidden rounded-[2.5rem] bg-[#0f172a] p-8 text-white shadow-2xl sm:p-12">
          {/* Decorative Elements */}
          <div className="absolute top-0 right-0 w-64 h-64 bg-[#004aad] rounded-full blur-[120px] opacity-20 -mr-32 -mt-32" />
          
          <div className="relative z-10">
            <div className="mb-10 flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
              <div>
                <div className="mb-2 flex items-center gap-2 text-cyan-400">
                  <Compass size={18} />
                  <span className="text-[10px] font-black uppercase tracking-[0.2em]">Career Intelligence</span>
                </div>
                <h3 className="text-2xl font-black text-white sm:text-3xl">AI 권장 전공 트랙 <span className="text-cyan-400">Top 3</span></h3>
              </div>
              <p className="max-w-xs text-sm font-bold leading-relaxed text-slate-400 sm:text-right">현재 생기부의 탐구 흐름을 분석하여 합격 확률이 가장 높은 전공 계열을 제안합니다.</p>
            </div>

            <div className="grid gap-4 md:grid-cols-3">
              {majorDirections.map((direction, index) => (
                <SurfaceCard key={`${direction.label}-${index}`} className="group relative overflow-hidden border-none bg-white/5 p-6 ring-1 ring-white/10 hover:bg-white/10 transition-all duration-300">
                  <div className="absolute right-0 top-0 p-4 opacity-10 group-hover:opacity-20 transition-opacity">
                    <Target size={48} />
                  </div>
                  <div className="relative z-10">
                    <div className="mb-4 inline-flex h-8 w-8 items-center justify-center rounded-lg bg-cyan-500/10 text-xs font-black text-cyan-400 ring-1 ring-cyan-500/20">
                      0{index + 1}
                    </div>
                    <p className="mb-2 text-lg font-black text-white group-hover:text-cyan-300 transition-colors">{direction.label}</p>
                    {direction.summary && (
                      <p className="text-sm font-medium leading-relaxed text-slate-400 group-hover:text-slate-200 transition-colors">
                        {direction.summary}
                      </p>
                    )}
                  </div>
                </SurfaceCard>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* 4. Narrative Sections: Strengths & Challenges */}
      <div className="grid gap-6 md:grid-cols-2">
        <SurfaceCard className="border-none bg-emerald-50/30 p-8 shadow-sm ring-1 ring-emerald-100/50">
          <div className="mb-6 flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-2xl bg-emerald-500 text-white shadow-lg shadow-emerald-500/20">
              <CheckCircle2 size={24} />
            </div>
            <div>
              <p className="text-[10px] font-black uppercase tracking-widest text-emerald-600/60">Success Markers</p>
              <h4 className="text-xl font-black text-slate-800">합격을 지탱하는 핵심 강점</h4>
            </div>
          </div>
          <ul className="space-y-4">
            {strengths.map((item: string, index: number) => (
              <li key={index} className="flex gap-4 text-base font-bold leading-relaxed text-slate-700">
                <span className="mt-2.5 h-1.5 w-1.5 shrink-0 rounded-full bg-emerald-400" />
                {item}
              </li>
            ))}
          </ul>
        </SurfaceCard>

        <SurfaceCard className="border-none bg-rose-50/30 p-8 shadow-sm ring-1 ring-rose-100/50">
          <div className="mb-6 flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-2xl bg-rose-500 text-white shadow-lg shadow-rose-500/20">
              <AlertTriangle size={24} />
            </div>
            <div>
              <p className="text-[10px] font-black uppercase tracking-widest text-rose-600/60">Risk Management</p>
              <h4 className="text-xl font-black text-slate-800">우선 보완이 필요한 지점</h4>
            </div>
          </div>
          <ul className="space-y-4">
            {gaps.map((item: string, index: number) => (
              <li key={index} className="flex gap-4 text-base font-bold leading-relaxed text-slate-700">
                <span className="mt-2.5 h-1.5 w-1.5 shrink-0 rounded-full bg-rose-400" />
                {item}
              </li>
            ))}
          </ul>
        </SurfaceCard>
      </div>

      {/* 5. Visualization */}
      {diagnosisResult.relational_graph && (
        <div className="py-2">
          <DiagnosisRelationalGraph graph={diagnosisResult.relational_graph} />
        </div>
      )}

      {/* 6. Strategic Action Plan */}
      {(diagnosisResult.next_actions?.length > 0 || diagnosisResult.recommended_focus) && (
        <div className="relative overflow-hidden rounded-[3rem] bg-slate-900 p-8 text-white shadow-2xl sm:p-12">
          <div className="absolute bottom-0 left-0 w-64 h-64 bg-[#004aad] rounded-full blur-[100px] opacity-10 -ml-32 -mb-32" />
          
          <div className="relative z-10">
            <div className="mb-12 flex items-center gap-4">
              <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-[#004aad] text-white shadow-lg shadow-[#004aad]/40">
                <Zap size={24} fill="currentColor" />
              </div>
              <div>
                <div className="flex items-center gap-2 mb-1">
                  <span className="text-[10px] font-black uppercase tracking-[0.2em] text-[#004aad]">Strategic Roadmap</span>
                  {stageModeNote && (
                    <span className="rounded-full bg-white/10 px-2 py-0.5 text-[10px] font-bold text-slate-300 ring-1 ring-white/10 uppercase italic">
                       {stageModeNote} mode
                    </span>
                  )}
                </div>
                <h4 className="text-2xl font-black">합격을 위한 최적화 실행 과제</h4>
              </div>
            </div>

            <div className="grid gap-10 lg:grid-cols-12">
              <div className="lg:col-span-8">
                <ul className="space-y-6">
                  {nextActions.map((item: string, index: number) => (
                    <motion.li
                      key={index}
                      initial={{ opacity: 0, x: -10 }}
                      animate={{ opacity: 1, x: 0 }}
                      transition={{ delay: 0.1 + index * 0.1 }}
                      className="flex items-start gap-5 rounded-[1.5rem] bg-white/5 p-6 ring-1 ring-white/10 hover:bg-white/10 transition-colors"
                    >
                      <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-cyan-500/20 text-xs font-black text-cyan-400 ring-1 ring-cyan-500/20">
                        {index + 1}
                      </span>
                      <p className="text-base font-bold leading-relaxed text-slate-300">{item}</p>
                    </motion.li>
                  ))}
                </ul>
              </div>
              
              {(diagnosisResult.recommended_focus || stageModeNote) && (
                <div className="lg:col-span-4">
                  <div className="h-full rounded-[2rem] bg-[linear-gradient(135deg,rgba(0,74,173,0.2)_0%,rgba(0,74,173,0.05)_100%)] p-8 ring-1 ring-[#004aad]/30">
                    <h5 className="mb-6 flex items-center gap-2 text-sm font-black text-[#004aad] uppercase tracking-widest">
                      <Target size={16} />
                      Priority Focus
                    </h5>
                    <p className="text-2xl font-black italic leading-tight text-white">
                      {sanitizeKoreanText(diagnosisResult.recommended_focus || stageModeNote)}
                    </p>
                    <p className="mt-6 text-sm font-medium leading-relaxed text-slate-400">
                      현재 데이터상에서 가장 빠른 변화를 만들어낼 수 있는 핵심 성공 경로입니다.
                    </p>
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </motion.div>
  );
};
