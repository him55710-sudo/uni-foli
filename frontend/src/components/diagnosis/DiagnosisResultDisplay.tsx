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
      initial={{ opacity: 0, y: 30 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -30 }}
      transition={{ duration: 0.6, ease: [0.22, 1, 0.36, 1] }}
      className="mx-auto max-w-5xl space-y-12 pb-20"
    >
      {/* 1. Header Overview Card */}
      <section className="relative overflow-hidden rounded-[32px] bg-white p-8 sm:p-14 shadow-sm ring-1 ring-slate-200/50">
        <div className="flex flex-col md:flex-row md:items-start justify-between gap-10">
          <div className="flex-1 space-y-6">
            <div className="flex items-center gap-2">
              <span className="px-3 py-1 bg-blue-50 text-[#3182f6] rounded-full text-[11px] font-black uppercase tracking-widest">AI 진단 리포트</span>
              {completionState && <span className="px-3 py-1 bg-[#f2f4f6] text-[#6b7684] rounded-full text-[11px] font-black">{completionState}</span>}
            </div>
            <h1 className="text-4xl sm:text-5xl font-black text-[#191f28] leading-[1.2] tracking-tight">
              {sanitizeKoreanText(diagnosisResult.headline, '진단 결과')}
            </h1>
            <p className="text-xl text-[#4e5968] font-medium leading-relaxed max-w-3xl">
              {sanitizeKoreanText(diagnosisResult.overview)}
            </p>
          </div>
          
          <div className="flex flex-col items-center justify-center bg-[#3182f6] rounded-[40px] p-10 text-white min-w-[240px] shadow-2xl shadow-blue-200/50">
            <span className="text-[13px] font-black opacity-90 mb-2 tracking-widest uppercase">종합 역량 지수</span>
            <span className="text-7xl font-black tracking-tight">{totalScore !== null ? Math.round(totalScore) : '--'}</span>
            <div className="mt-6 px-5 py-2 bg-white/20 backdrop-blur-md rounded-full text-[13px] font-black">
               {normalizeScoreLabel(scoreLabelsRaw?.['총점'])}
            </div>
          </div>
        </div>
      </section>

      {/* 2. Key Metrics Grid */}
      <div className="grid gap-6 grid-cols-2 lg:grid-cols-4">
        {categoryScores.map(({ name, score }) => (
          <div key={name} className="bg-white p-8 rounded-[32px] shadow-sm ring-1 ring-slate-200/50 group hover:ring-[#3182f6]/30 transition-all duration-300">
            <p className="text-[13px] font-black text-[#8b95a1] uppercase mb-4 tracking-wider">{sanitizeKoreanText(name, '항목')}</p>
            <div className="flex items-end gap-1 mb-4">
              <span className="text-4xl font-black text-[#191f28]">{Math.round(score)}</span>
              <span className="text-sm font-black text-[#b0b8c1] mb-1.5">/ 100</span>
            </div>
            <div className="h-2 w-full bg-[#f2f4f6] rounded-full overflow-hidden">
              <motion.div 
                initial={{ width: 0 }}
                animate={{ width: `${score}%` }}
                transition={{ duration: 1.2, delay: 0.3, ease: [0.22, 1, 0.36, 1] }}
                className="h-full bg-[#3182f6] rounded-full"
              />
            </div>
          </div>
        ))}
      </div>

      {/* 3. Strengths & Challenges */}
      <div className="grid gap-8 md:grid-cols-2">
        <div className="bg-white p-10 rounded-[40px] shadow-sm ring-1 ring-slate-200/50">
          <div className="flex items-center gap-4 mb-10">
            <div className="h-12 w-12 bg-[#e8f3ff] rounded-2xl flex items-center justify-center">
              <CheckCircle2 size={28} className="text-[#3182f6]" strokeWidth={2.5} />
            </div>
            <h3 className="text-2xl font-black text-[#191f28]">핵심 역량 강점</h3>
          </div>
          <ul className="space-y-6">
            {strengths.map((item, i) => (
              <li key={i} className="flex gap-4 text-[#4e5968] font-bold text-[17px] leading-relaxed">
                <span className="mt-2.5 h-2 w-2 shrink-0 rounded-full bg-[#3182f6]" />
                {item}
              </li>
            ))}
          </ul>
        </div>
        <div className="bg-white p-10 rounded-[40px] shadow-sm ring-1 ring-slate-200/50">
          <div className="flex items-center gap-4 mb-10">
            <div className="h-12 w-12 bg-[#fff0f1] rounded-2xl flex items-center justify-center">
              <AlertTriangle size={28} className="text-[#f04452]" strokeWidth={2.5} />
            </div>
            <h3 className="text-2xl font-black text-[#191f28]">보완 과제</h3>
          </div>
          <ul className="space-y-6">
            {gaps.map((item, i) => (
              <li key={i} className="flex gap-4 text-[#4e5968] font-bold text-[17px] leading-relaxed">
                <span className="mt-2.5 h-2 w-2 shrink-0 rounded-full bg-[#f04452]" />
                {item}
              </li>
            ))}
          </ul>
        </div>
      </div>

      {/* 4. AI Recommendations */}
      {majorDirections.length > 0 && (
        <section className="bg-[#191f28] rounded-[48px] p-12 sm:p-20 text-white relative overflow-hidden">
          <div className="absolute top-0 right-0 w-[500px] h-[500px] bg-[#3182f6]/20 blur-[120px] -mr-64 -mt-64" />
          <div className="relative z-10">
            <div className="mb-14 flex flex-col gap-2">
               <span className="text-[#3182f6] font-black tracking-widest text-xs uppercase">Future Path</span>
               <h3 className="text-3xl font-black">AI 추천 전공 트랙</h3>
            </div>
            <div className="grid gap-8 md:grid-cols-3">
              {majorDirections.map((dir, i) => (
                <div key={i} className="group bg-white/5 border border-white/10 p-8 rounded-[32px] hover:bg-white/10 hover:border-white/20 transition-all duration-300">
                  <span className="text-[11px] font-black text-[#3182f6] mb-3 block uppercase tracking-widest">Track 0{i+1}</span>
                  <p className="text-xl font-black mb-4 group-hover:text-white transition-colors">{dir.label}</p>
                  <p className="text-[15px] text-[#8b95a1] font-medium leading-relaxed">{dir.summary}</p>
                </div>
              ))}
            </div>
          </div>
        </section>
      )}

      {/* 5. Strategic Actions */}
      <section className="bg-white rounded-[48px] p-12 sm:p-20 shadow-sm ring-1 ring-slate-200/50">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-10 mb-14">
          <div className="flex items-center gap-6">
            <div className="h-16 w-16 bg-[#3182f6] rounded-[24px] flex items-center justify-center shadow-xl shadow-blue-200">
              <Zap size={32} className="text-white" fill="white" />
            </div>
            <div>
              <h3 className="text-3xl font-black text-[#191f28]">전략적 실행 가이드</h3>
              <p className="text-[#3182f6] font-black text-sm mt-1">합격 확률을 높이는 즉시 실행 리스트</p>
            </div>
          </div>
          
          <button 
            onClick={() => navigate(`/app/workshop/${projectId}`)}
            className="bg-[#3182f6] text-white px-10 h-16 rounded-[20px] font-black text-lg shadow-2xl shadow-blue-200/50 hover:bg-[#1b64da] hover:-translate-y-1 transition-all active:scale-95 flex items-center gap-3"
          >
             워크숍에서 작성하기
             <Compass size={22} strokeWidth={3} />
          </button>
        </div>

        <div className="grid gap-6 md:grid-cols-2">
          {nextActions.map((action, i) => (
            <div key={i} className="bg-[#f9fafb] p-8 rounded-[32px] flex items-start gap-5 group hover:bg-[#f2f4f6] transition-colors duration-200">
              <span className="h-10 w-10 rounded-2xl bg-white text-[#3182f6] flex items-center justify-center font-black text-sm shrink-0 shadow-sm ring-1 ring-slate-200/50">{i+1}</span>
              <p className="text-[#333d4b] font-bold text-[17px] leading-relaxed">{action}</p>
            </div>
          ))}
        </div>
      </section>

      {/* 6. Visualization */}
      {diagnosisResult.relational_graph && (
        <div className="bg-white rounded-[40px] p-10 shadow-sm ring-1 ring-slate-200/50">
           <h3 className="text-2xl font-black text-[#191f28] mb-10 flex items-center gap-4">
             <Target size={28} className="text-[#3182f6]" strokeWidth={2.5} />
             역량 키워드 구조
           </h3>
           <div className="rounded-[24px] bg-[#f9fafb] p-6 ring-1 ring-slate-200/50">
             <DiagnosisRelationalGraph graph={diagnosisResult.relational_graph} />
           </div>
        </div>
      )}
    </motion.div>
  );
};
