import React from 'react';
import { motion } from 'motion/react';
import { useNavigate } from 'react-router-dom';
import { 
  CheckCircle2, 
  AlertTriangle, 
  Zap, 
  Clock, 
  Download, 
  AlertCircle, 
  Gauge, 
  Compass, 
  Target, 
  Mic, 
  ShieldCheck, 
  TrendingUp, 
  BookOpen, 
  Lightbulb, 
  Link2,
  ChevronRight,
  ArrowRight
} from 'lucide-react';
import { SectionCard, SurfaceCard, StatusBadge, PrimaryButton } from '../primitives';
import { formatRiskLevel } from '../../lib/diagnosis';
import { DiagnosisRunResponse } from '../../types/api';
import { DiagnosisRelationalGraph } from './DiagnosisRelationalGraph';
import { Timeline } from './Timeline';
import { useOnboardingStore } from '../../store/onboardingStore';


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

function completionStateLabel(value: unknown): string | null {
  const key = String(value ?? '').trim().toLowerCase();
  if (!key) return null;
  if (key === 'finalized') return '기록 마감 단계';
  if (key === 'ongoing') return '개선 가능 단계';
  return '상태 확인 중';
}

export const DiagnosisResultDisplay: React.FC<DiagnosisResultDisplayProps> = ({ diagnosisResult, diagnosisRun, projectId }) => {
  const navigate = useNavigate();
  const { profile } = useOnboardingStore();
  const summaryJson = asRecord(diagnosisResult?.diagnosis_summary_json);
  
  const totalScore = summaryJson ? asNumber(summaryJson.total_score) : null;
  const categoryScoresRaw = summaryJson ? asRecord(summaryJson.category_scores) : null;
  const scoreLabelsRaw = summaryJson ? asRecord(summaryJson.score_labels) : null;
  const majorDirectionsRaw = summaryJson?.major_direction_candidates_top3;
  
  const completionState = completionStateLabel(
    summaryJson?.completion_state || diagnosisResult?.record_completion_state
  );

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
  
  // Analysis sections
  const academicCompetency = sanitizeKoreanText(summaryJson?.academic_competency || diagnosisResult.academic_competency, '학업 역량 분석 결과를 생성 중입니다.');
  const majorSuitability = sanitizeKoreanText(summaryJson?.major_suitability || diagnosisResult.major_suitability, '전공 적합성 분석 결과를 생성 중입니다.');
  const inquiryCompetency = sanitizeKoreanText(summaryJson?.inquiry_competency || diagnosisResult.inquiry_competency, '탐구 역량 분석 결과를 생성 중입니다.');
  const activityConsistency = sanitizeKoreanText(summaryJson?.activity_consistency || diagnosisResult.activity_consistency, '활동 일관성 분석 결과를 생성 중입니다.');
  const keySubjectComments = sanitizeList(summaryJson?.key_subject_comments || diagnosisResult.key_subject_comments, '핵심 세특 항목을 분석 중입니다.');
  const interviewDefensibility = sanitizeKoreanText(summaryJson?.interview_defensibility || diagnosisResult.interview_defensibility, '면접 방어력 분석 결과를 생성 중입니다.');
  const followupInquiry = sanitizeKoreanText(summaryJson?.followup_inquiry || diagnosisResult.followup_inquiry, '후속 탐구 가능성 제안을 생성 중입니다.');

  // Strategic modules (Consultant Persona)
  const risks = sanitizeList(summaryJson?.risks || [], '현재 특별한 리스크가 발견되지 않았습니다.');
  const improvements = sanitizeList(summaryJson?.improvement_directions || gaps, '보완 방향을 도출 중입니다.');
  const interviewUtility = sanitizeKoreanText(summaryJson?.interview_utility || '', '면접 활용 포인트를 분석 중입니다.');

  return (
    <motion.div
      key="result"
      initial={{ opacity: 0, y: 30 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -30 }}
      transition={{ duration: 0.8, ease: [0.22, 1, 0.36, 1] }}
      className="mx-auto max-w-6xl space-y-16 pb-24"
    >
      {/* 1. Refined Hero Header */}
      <section className="relative overflow-hidden rounded-[32px] bg-white border border-slate-200 p-8 sm:p-12 shadow-sm">
        <div className="relative z-10 flex flex-col md:flex-row md:items-start justify-between gap-10">
          <div className="flex-1 space-y-6">
            <div className="flex flex-wrap items-center gap-3">
              <span className="px-3 py-1 bg-blue-50 text-blue-600 border border-blue-100 rounded-lg text-[11px] font-bold uppercase tracking-wider">상세 분석 리포트</span>
              {completionState && (
                <span className="px-3 py-1 bg-slate-50 text-slate-500 border border-slate-100 rounded-lg text-[11px] font-bold tracking-tight">
                  {completionState}
                </span>
              )}
            </div>

            <h1 className="text-2xl sm:text-3xl font-bold text-slate-900 leading-snug tracking-tight max-w-3xl">
              {sanitizeKoreanText(diagnosisResult.headline, '학생부 정밀 진단')}
            </h1>
            <p className="text-base text-slate-600 font-medium leading-relaxed max-w-2xl">
              {sanitizeKoreanText(diagnosisResult.overview)}
            </p>
          </div>
          
          <div className="flex flex-col items-center justify-center bg-slate-900 rounded-3xl p-8 text-white min-w-[200px] shadow-lg">
            <span className="text-[12px] font-bold opacity-60 mb-2 tracking-wider uppercase">종합 역량 지수</span>
            <span className="text-6xl font-bold tracking-tighter tabular-nums">{totalScore !== null ? Math.round(totalScore) : '--'}</span>
            <div className="mt-4 px-4 py-1.5 bg-white/10 rounded-xl text-[12px] font-bold border border-white/10">
               {normalizeScoreLabel(scoreLabelsRaw?.['총점'])}
            </div>
          </div>
        </div>
      </section>

      {/* 2. Simplified Strategic Brief */}
      <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-4">
        {[
          { label: '핵심 강점', items: strengths.slice(0, 2), color: 'text-emerald-600', bg: 'bg-emerald-50', icon: CheckCircle2 },
          { label: '주요 리스크', items: risks.slice(0, 2), color: 'text-rose-600', bg: 'bg-rose-50', icon: AlertTriangle },
          { label: '보완 방향', items: improvements.slice(0, 2), color: 'text-amber-600', bg: 'bg-amber-50', icon: Target },
          { label: '면접 활용성', content: interviewUtility || '학생부 기록 기반 면접 문항 도출이 용이합니다.', color: 'text-blue-600', bg: 'bg-blue-50', icon: Mic }
        ].map((box, idx) => (
          <div key={idx} className={`${box.bg} p-6 rounded-2xl border border-black/5 space-y-3`}>
            <div className={`flex items-center gap-2 ${box.color}`}>
              <box.icon size={16} />
              <span className="text-xs font-bold uppercase tracking-wider">{box.label}</span>
            </div>
            {box.items ? (
              <div className="space-y-1">
                {box.items.map((item, i) => (
                  <p key={i} className="text-slate-700 text-[13px] font-medium leading-relaxed">• {item}</p>
                ))}
              </div>
            ) : (
              <p className="text-slate-700 text-[13px] font-medium leading-relaxed line-clamp-3">
                {box.content}
              </p>
            )}
          </div>
        ))}
      </div>

      {/* 3. Core Competency Analysis Grid */}
      <div className="grid gap-8 lg:grid-cols-3">
        <div className="lg:col-span-2 space-y-8">
          <div className="grid gap-6 sm:grid-cols-2">
             <SurfaceCard className="p-8 space-y-4 border border-slate-200 bg-white shadow-sm">
                <div className="flex items-center gap-3">
                  <div className="h-10 w-10 bg-blue-50 rounded-xl flex items-center justify-center text-blue-600">
                    <BookOpen size={20} />
                  </div>
                  <h3 className="text-lg font-bold text-slate-900">학업 역량</h3>
                </div>
                <p className="text-slate-600 text-sm leading-relaxed font-medium">
                  {academicCompetency}
                </p>
             </SurfaceCard>

             <SurfaceCard className="p-8 space-y-4 border border-slate-200 bg-white shadow-sm">
                <div className="flex items-center gap-3">
                  <div className="h-10 w-10 bg-violet-50 rounded-xl flex items-center justify-center text-violet-600">
                    <Lightbulb size={20} />
                  </div>
                  <h3 className="text-lg font-bold text-slate-900">탐구 역량</h3>
                </div>
                <p className="text-slate-600 text-sm leading-relaxed font-medium">
                  {inquiryCompetency}
                </p>
             </SurfaceCard>
          </div>

          <SurfaceCard className="p-8 border border-slate-200 bg-white shadow-sm">
            <div className="flex items-center gap-3 mb-6">
               <div className="h-10 w-10 bg-emerald-50 rounded-xl flex items-center justify-center text-emerald-600">
                 <Link2 size={20} />
               </div>
               <h3 className="text-lg font-bold text-slate-900">활동 일관성 및 전공 적합성</h3>
            </div>
            <div className="grid gap-6 md:grid-cols-2">
               <div className="space-y-3">
                  <p className="text-[11px] font-bold text-emerald-600 uppercase tracking-wider">Suitability</p>
                  <p className="text-slate-600 text-sm leading-relaxed font-medium">{majorSuitability}</p>
               </div>
               <div className="space-y-3">
                  <p className="text-[11px] font-bold text-blue-600 uppercase tracking-wider">Consistency</p>
                  <p className="text-slate-600 text-sm leading-relaxed font-medium">{activityConsistency}</p>
               </div>
            </div>
          </SurfaceCard>

          {/* Key Subject Comments */}
          <SurfaceCard className="p-8 border border-slate-200 bg-white shadow-sm">
            <div className="flex items-center justify-between mb-6">
              <div className="flex items-center gap-3">
                <div className="h-10 w-10 bg-amber-50 rounded-xl flex items-center justify-center text-amber-600">
                  <Target size={20} />
                </div>
                <h3 className="text-lg font-bold text-slate-900">핵심 세부능력 및 특기사항</h3>
              </div>
            </div>
            <div className="space-y-3">
               {keySubjectComments.map((comment, i) => (
                 <div key={i} className="flex gap-4 p-5 rounded-2xl bg-slate-50 border border-slate-100 items-start">
                   <div className="h-8 w-8 shrink-0 rounded-lg bg-amber-100 text-amber-700 flex items-center justify-center text-xs font-bold">
                    {i+1}
                   </div>
                   <p className="text-slate-700 text-sm font-medium leading-relaxed">{comment}</p>
                 </div>
               ))}
            </div>
          </SurfaceCard>
        </div>

        <div className="space-y-8">
           <SurfaceCard className="p-8 border border-slate-200 bg-white shadow-sm">
              <h3 className="text-base font-bold text-slate-900 mb-6 flex items-center gap-2">
                <Gauge size={18} className="text-blue-600" />
                역량 분석 대시보드
              </h3>
              <div className="space-y-6">
                {categoryScores.map(({ name, score }) => (
                  <div key={name} className="space-y-2">
                    <div className="flex justify-between items-end">
                       <span className="text-xs font-bold text-slate-500">{name}</span>
                       <span className="text-sm font-bold text-slate-900 tabular-nums">{Math.round(score)}<span className="text-[10px] text-slate-400 ml-1">/100</span></span>
                    </div>
                    <div className="h-2 w-full bg-slate-100 rounded-full overflow-hidden">
                      <motion.div 
                        initial={{ width: 0 }}
                        animate={{ width: `${score}%` }}
                        transition={{ duration: 1.5, ease: "easeOut" }}
                        className="h-full bg-blue-600 rounded-full"
                      />
                    </div>
                  </div>
                ))}
              </div>
           </SurfaceCard>

           <SurfaceCard className="p-8 border border-slate-200 bg-white shadow-sm">
              <Timeline grade={profile.grade} />
           </SurfaceCard>
        </div>
      </div>

      {/* 4. Strategic Analysis Modules */}
      <div className="grid gap-8 md:grid-cols-2">
        <div className="bg-blue-50/50 p-10 rounded-[32px] border border-blue-100 shadow-sm space-y-6">
          <div className="flex items-center gap-3">
            <div className="h-12 w-12 bg-blue-100 rounded-2xl flex items-center justify-center text-blue-600">
              <ShieldCheck size={24} />
            </div>
            <h3 className="text-xl font-bold text-slate-900">면접 방어력 분석</h3>
          </div>
          <p className="text-slate-600 text-base leading-relaxed font-medium">
            {interviewDefensibility}
          </p>
        </div>

        <div className="bg-violet-50/50 p-10 rounded-[32px] border border-violet-100 shadow-sm space-y-6">
          <div className="flex items-center gap-3">
            <div className="h-12 w-12 bg-violet-100 rounded-2xl flex items-center justify-center text-violet-600">
              <TrendingUp size={24} />
            </div>
            <h3 className="text-xl font-bold text-slate-900">후속 탐구 가능성</h3>
          </div>
          <p className="text-slate-600 text-base leading-relaxed font-medium">
            {followupInquiry}
          </p>
        </div>
      </div>

      {/* 5. Simplified Pathway (Compact) */}
      {majorDirections.length > 0 && (
        <section className="bg-slate-50 rounded-[32px] p-10 border border-slate-100">
          <div className="mb-10">
             <h3 className="text-2xl font-bold tracking-tight text-slate-900">AI 추천 커리어 트랙</h3>
             <p className="text-sm font-medium text-slate-500 mt-1">학생부 기록을 바탕으로 도출된 최적의 진로 방향성입니다.</p>
          </div>
          <div className="grid gap-6 md:grid-cols-3">
            {majorDirections.map((dir, i) => (
              <div key={i} className="bg-white border border-slate-200 p-8 rounded-2xl shadow-sm hover:border-blue-300 transition-colors group">
                <div className="h-10 w-10 bg-blue-50 rounded-xl flex items-center justify-center text-blue-600 mb-4 group-hover:bg-blue-600 group-hover:text-white transition-all">
                  <Compass size={20} />
                </div>
                <p className="text-lg font-bold mb-3 text-slate-900">{dir.label}</p>
                <p className="text-sm text-slate-600 font-medium leading-relaxed line-clamp-4">{dir.summary}</p>
              </div>
            ))}
          </div>
        </section>
      )}

      {/* 6. Refined Call to Action */}
      <section className="bg-white rounded-[40px] p-12 border-2 border-blue-50 shadow-xl shadow-blue-900/5 flex flex-col md:flex-row items-center justify-between gap-10 relative overflow-hidden">
        <div className="absolute top-0 right-0 w-64 h-64 bg-blue-50 rounded-full blur-3xl -mr-32 -mt-32 opacity-50" />
        <div className="relative z-10 space-y-3 text-center md:text-left">
          <h3 className="text-3xl font-bold text-slate-900 tracking-tight">워크숍에서 이 기록을 완성해보세요</h3>
          <p className="text-slate-600 font-medium text-lg">AI 컨설턴트가 세특의 논리를 강화하고 탐구의 깊이를 더해드립니다.</p>
        </div>
        <button 
          onClick={() => navigate(`/app/workshop/${projectId}`)}
          className="relative z-10 bg-blue-600 text-white px-10 py-5 rounded-[20px] font-bold text-lg hover:bg-blue-700 transition-all hover:scale-105 shadow-lg shadow-blue-600/20 flex items-center gap-3 shrink-0"
        >
           워크숍 시작하기
           <ArrowRight size={20} />
        </button>
      </section>

      {/* 7. Relational Keyword Visualization */}
      {diagnosisResult.relational_graph && (
        <section className="space-y-8">
           <div className="flex items-center justify-between">
             <div className="flex items-center gap-4">
               <div className="h-12 w-12 bg-blue-50 rounded-2xl flex items-center justify-center text-blue-600 border border-blue-100">
                 <Target size={24} />
               </div>
               <div>
                 <h3 className="text-2xl font-bold text-slate-900">역량 키워드 및 관계성 분석</h3>
                 <p className="text-sm font-medium text-slate-500">학생부 내 활동들 간의 유기적인 연결 고리를 분석합니다.</p>
               </div>
             </div>
             <span className="hidden sm:inline-block px-4 py-1.5 bg-slate-50 border border-slate-200 rounded-xl text-[11px] font-bold text-slate-400 uppercase tracking-wider">AI Semantic Mapping</span>
           </div>
           
           <div className="rounded-[32px] bg-white border border-slate-200 p-10 shadow-sm relative overflow-hidden">
             <div className="absolute inset-0 bg-slate-50/30 pointer-events-none" />
             <div className="relative z-10">
               <DiagnosisRelationalGraph graph={diagnosisResult.relational_graph} />
             </div>
           </div>
        </section>
      )}
    </motion.div>
  );
};
