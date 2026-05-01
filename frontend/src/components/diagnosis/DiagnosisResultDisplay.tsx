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
      {/* 1. Cinematic Hero Header */}
      <section className="relative overflow-hidden rounded-[48px] bg-[#111] p-12 sm:p-20 shadow-2xl ring-1 ring-white/5">
        <div className="absolute top-0 right-0 w-[600px] h-[600px] bg-[#3182f6]/20 blur-[150px] -mr-64 -mt-64 animate-pulse" />
        <div className="absolute bottom-0 left-0 w-[400px] h-[400px] bg-violet-500/10 blur-[120px] -ml-48 -mb-48" />
        
        <div className="relative z-10 flex flex-col md:flex-row md:items-center justify-between gap-12">
          <div className="flex-1 space-y-8">
            <div className="flex flex-wrap items-center gap-3">
              <span className="px-4 py-1.5 bg-blue-500/10 text-blue-400 border border-blue-500/20 rounded-full text-[12px] font-black uppercase tracking-[0.2em]">PREMIUM ADMISSIONS CONSULTING</span>
              {completionState && (
                <span className="px-4 py-1.5 bg-white/5 text-slate-300 border border-white/10 rounded-full text-[12px] font-black tracking-tight">
                  {completionState}
                </span>
              )}
            </div>

            {/* Student Identity Bar */}
            <div className="inline-flex flex-wrap gap-x-8 gap-y-4 px-6 py-3 bg-white/5 border border-white/10 rounded-3xl backdrop-blur-md">
              <div className="flex flex-col">
                <span className="text-[10px] font-black text-slate-500 uppercase tracking-widest mb-0.5">Grade / Track</span>
                <span className="text-sm font-black text-white">{diagnosisResult.grade || '전체'} · {diagnosisResult.track || '미지정'}</span>
              </div>
              <div className="w-px h-8 bg-white/10 hidden sm:block mt-1" />
              <div className="flex flex-col">
                <span className="text-[10px] font-black text-slate-500 uppercase tracking-widest mb-0.5">Target Major</span>
                <span className="text-sm font-black text-blue-400">{diagnosisResult.target_major || '미설정'}</span>
              </div>
            </div>
            <h1 className="text-5xl sm:text-7xl font-black text-white leading-[1.1] tracking-tight">
              {sanitizeKoreanText(diagnosisResult.headline, '학생부 정밀 진단')}
            </h1>
            <p className="text-xl text-slate-400 font-medium leading-relaxed max-w-2xl border-l-4 border-blue-500/30 pl-6">
              {sanitizeKoreanText(diagnosisResult.overview)}
            </p>
          </div>
          
          <div className="flex flex-col items-center justify-center bg-gradient-to-br from-[#3182f6] to-[#1b64da] rounded-[48px] p-12 text-white min-w-[280px] shadow-[0_20px_50px_rgba(49,130,246,0.3)] group hover:scale-105 transition-transform duration-500">
            <span className="text-[14px] font-black opacity-80 mb-3 tracking-[0.2em] uppercase">종합 역량 지수</span>
            <span className="text-8xl font-black tracking-tighter tabular-nums">{totalScore !== null ? Math.round(totalScore) : '--'}</span>
            <div className="mt-8 px-6 py-2.5 bg-white/20 backdrop-blur-xl rounded-2xl text-[14px] font-black border border-white/20">
               {normalizeScoreLabel(scoreLabelsRaw?.['총점'])}
            </div>
          </div>
        </div>
      </section>

      {/* 2. Consultant's Strategic Brief */}
      <div className="grid gap-8 md:grid-cols-2 lg:grid-cols-4">
        <div className="bg-emerald-500/5 border border-emerald-500/10 p-8 rounded-[32px] space-y-4 shadow-[0_10px_30px_rgba(16,185,129,0.05)]">
          <div className="flex items-center gap-3 text-emerald-400">
            <CheckCircle2 size={20} />
            <span className="text-xs font-black uppercase tracking-widest">Strengths</span>
          </div>
          <p className="text-white font-black text-lg leading-tight">핵심 강점</p>
          <div className="space-y-2">
            {strengths.slice(0, 2).map((s, i) => (
              <p key={i} className="text-slate-400 text-sm font-medium leading-relaxed">• {s}</p>
            ))}
          </div>
        </div>

        <div className="bg-rose-500/5 border border-rose-500/10 p-8 rounded-[32px] space-y-4 shadow-[0_10px_30px_rgba(244,63,94,0.05)]">
          <div className="flex items-center gap-3 text-rose-400">
            <AlertTriangle size={20} />
            <span className="text-xs font-black uppercase tracking-widest">Risks</span>
          </div>
          <p className="text-white font-black text-lg leading-tight">주요 리스크</p>
          <div className="space-y-2">
            {risks.slice(0, 2).map((r, i) => (
              <p key={i} className="text-slate-400 text-sm font-medium leading-relaxed">• {r}</p>
            ))}
          </div>
        </div>

        <div className="bg-amber-500/5 border border-amber-500/10 p-8 rounded-[32px] space-y-4 shadow-[0_10px_30px_rgba(245,158,11,0.05)]">
          <div className="flex items-center gap-3 text-amber-400">
            <Target size={20} />
            <span className="text-xs font-black uppercase tracking-widest">Next Strategy</span>
          </div>
          <p className="text-white font-black text-lg leading-tight">보완 방향</p>
          <div className="space-y-2">
            {improvements.slice(0, 2).map((imp, i) => (
              <p key={i} className="text-slate-400 text-sm font-medium leading-relaxed">• {imp}</p>
            ))}
          </div>
        </div>

        <div className="bg-blue-500/5 border border-blue-500/10 p-8 rounded-[32px] space-y-4 shadow-[0_10px_30px_rgba(59,130,246,0.05)]">
          <div className="flex items-center gap-3 text-blue-400">
            <Mic size={20} />
            <span className="text-xs font-black uppercase tracking-widest">Interview</span>
          </div>
          <p className="text-white font-black text-lg leading-tight">면접 활용성</p>
          <p className="text-slate-400 text-sm font-medium leading-relaxed line-clamp-3">
            {interviewUtility || '학생부 기록 기반 면접 문항 도출이 용이합니다.'}
          </p>
        </div>
      </div>

      {/* 3. Core Competency Analysis Grid */}
      <div className="grid gap-8 lg:grid-cols-3">
        <div className="lg:col-span-2 space-y-8">
          <div className="grid gap-8 sm:grid-cols-2">
             <SurfaceCard className="p-10 space-y-6 border border-white/5 bg-[#191f28]/60 backdrop-blur-md">
                <div className="flex items-center gap-4">
                  <div className="h-12 w-12 bg-blue-500/10 rounded-2xl flex items-center justify-center text-blue-400 shadow-[0_0_20px_rgba(59,130,246,0.2)]">
                    <BookOpen size={24} />
                  </div>
                  <h3 className="text-xl font-black text-white">학업 역량</h3>
                </div>
                <p className="text-slate-300 text-[15px] leading-relaxed font-medium">
                  {academicCompetency}
                </p>
             </SurfaceCard>

             <SurfaceCard className="p-10 space-y-6 border border-white/5 bg-[#191f28]/60 backdrop-blur-md">
                <div className="flex items-center gap-4">
                  <div className="h-12 w-12 bg-violet-500/10 rounded-2xl flex items-center justify-center text-violet-400 shadow-[0_0_20px_rgba(139,92,246,0.2)]">
                    <Lightbulb size={24} />
                  </div>
                  <h3 className="text-xl font-black text-white">탐구 역량</h3>
                </div>
                <p className="text-slate-300 text-[15px] leading-relaxed font-medium">
                  {inquiryCompetency}
                </p>
             </SurfaceCard>
          </div>

          <SurfaceCard className="p-10 border border-white/5 bg-[#191f28]/60 backdrop-blur-md relative overflow-hidden">
            <div className="absolute top-0 right-0 p-8 opacity-5">
              <Compass size={120} className="text-white" />
            </div>
            <div className="flex items-center gap-4 mb-8">
               <div className="h-12 w-12 bg-emerald-500/10 rounded-2xl flex items-center justify-center text-emerald-400">
                 <Link2 size={24} />
               </div>
               <h3 className="text-xl font-black text-white">활동 일관성 및 전공 적합성</h3>
            </div>
            <div className="grid gap-8 md:grid-cols-2">
               <div className="space-y-4">
                  <div className="flex items-center gap-2">
                    <div className="h-1 w-4 bg-emerald-500 rounded-full" />
                    <p className="text-xs font-black text-emerald-500 uppercase tracking-widest">Suitability</p>
                  </div>
                  <p className="text-slate-300 text-[15px] leading-relaxed font-medium">{majorSuitability}</p>
               </div>
               <div className="space-y-4">
                  <div className="flex items-center gap-2">
                    <div className="h-1 w-4 bg-blue-500 rounded-full" />
                    <p className="text-xs font-black text-blue-500 uppercase tracking-widest">Consistency</p>
                  </div>
                  <p className="text-slate-300 text-[15px] leading-relaxed font-medium">{activityConsistency}</p>
               </div>
            </div>
          </SurfaceCard>

          {/* Key Subject Comments (핵심 세특) */}
          <SurfaceCard className="p-10 border border-white/5 bg-[#191f28]/60 backdrop-blur-md">
            <div className="flex items-center justify-between mb-8">
              <div className="flex items-center gap-4">
                <div className="h-12 w-12 bg-amber-500/10 rounded-2xl flex items-center justify-center text-amber-400">
                  <Target size={24} />
                </div>
                <h3 className="text-xl font-black text-white">핵심 세부능력 및 특기사항</h3>
              </div>
              <span className="text-xs font-black text-slate-500 tracking-tighter uppercase">Subject Evidence</span>
            </div>
            <div className="grid gap-4">
               {keySubjectComments.map((comment, i) => (
                 <div key={i} className="flex gap-5 p-6 rounded-[32px] bg-white/[0.03] border border-white/5 items-start group hover:bg-white/5 transition-all duration-300">
                   <div className="h-10 w-10 shrink-0 rounded-2xl bg-amber-500/20 text-amber-400 flex items-center justify-center text-xs font-black shadow-lg group-hover:scale-110 transition-transform">
                    {i+1}
                   </div>
                   <div className="space-y-2">
                     <p className="text-slate-300 text-[15px] font-bold leading-relaxed">{comment}</p>
                     <div className="flex items-center gap-2 text-[10px] font-black text-slate-500 group-hover:text-amber-400 transition-colors">
                       <Link2 size={12} /> REPRESENTATIVE EVIDENCE
                     </div>
                   </div>
                 </div>
               ))}
            </div>
          </SurfaceCard>
        </div>

        <div className="space-y-8">
           <SurfaceCard className="p-10 border border-white/5 bg-[#191f28]/60 backdrop-blur-md">
              <h3 className="text-lg font-black text-white mb-8 flex items-center gap-3">
                <Gauge size={20} className="text-blue-400" />
                역량 분석 대시보드
              </h3>
              <div className="space-y-8">
                {categoryScores.map(({ name, score }) => (
                  <div key={name} className="space-y-3">
                    <div className="flex justify-between items-end">
                       <span className="text-sm font-black text-slate-400">{name}</span>
                       <span className="text-xl font-black text-white tabular-nums">{Math.round(score)}<span className="text-[10px] text-slate-500 ml-1">/100</span></span>
                    </div>
                    <div className="h-2.5 w-full bg-white/5 rounded-full overflow-hidden">
                      <motion.div 
                        initial={{ width: 0 }}
                        animate={{ width: `${score}%` }}
                        transition={{ duration: 2, ease: [0.22, 1, 0.36, 1] }}
                        className="h-full bg-gradient-to-r from-blue-500 to-violet-500 rounded-full shadow-[0_0_10px_rgba(59,130,246,0.3)]"
                      />
                    </div>
                  </div>
                ))}
              </div>
           </SurfaceCard>

           <SurfaceCard className="p-10 border border-white/5 bg-[#191f28]/60 backdrop-blur-md">
              <Timeline grade={profile.grade} />
           </SurfaceCard>
        </div>
      </div>

      {/* 4. Strategic Analysis Modules */}
      <div className="grid gap-8 md:grid-cols-2">
        <div className="bg-[#191f28]/40 p-12 rounded-[56px] border border-blue-500/10 shadow-2xl relative overflow-hidden group">
          <div className="absolute top-0 right-0 w-32 h-32 bg-blue-500/5 blur-3xl group-hover:bg-blue-500/10 transition-colors" />
          <div className="flex items-center gap-4 mb-10">
            <div className="h-14 w-14 bg-blue-500/10 rounded-3xl flex items-center justify-center text-blue-400 shadow-xl">
              <ShieldCheck size={32} strokeWidth={2.5} />
            </div>
            <div>
              <h3 className="text-2xl font-black text-white">면접 방어력 분석</h3>
              <p className="text-xs font-bold text-blue-400 uppercase tracking-widest mt-1">Interview Defensibility</p>
            </div>
          </div>
          <p className="text-slate-300 text-lg leading-relaxed font-medium mb-10">
            {interviewDefensibility}
          </p>
          <div className="p-8 rounded-[32px] bg-blue-500/5 border border-blue-500/10 group-hover:bg-blue-500/10 transition-colors">
             <div className="flex items-center gap-3 mb-4">
                <Mic size={18} className="text-blue-400" />
                <span className="text-[10px] font-black text-blue-400 uppercase tracking-[0.2em]">Practice Guide</span>
             </div>
             <p className="text-[15px] font-bold text-white leading-relaxed">
               {interviewUtility || '학생부 기록 기반의 정교한 예상 질문을 통해 실전 감각을 극대화할 수 있습니다.'}
             </p>
          </div>
        </div>

        <div className="bg-[#191f28]/40 p-12 rounded-[56px] border border-violet-500/10 shadow-2xl relative overflow-hidden group">
          <div className="absolute top-0 right-0 w-32 h-32 bg-violet-500/5 blur-3xl group-hover:bg-violet-500/10 transition-colors" />
          <div className="flex items-center gap-4 mb-10">
            <div className="h-14 w-14 bg-violet-500/10 rounded-3xl flex items-center justify-center text-violet-400 shadow-xl">
              <TrendingUp size={32} strokeWidth={2.5} />
            </div>
            <div>
              <h3 className="text-2xl font-black text-white">후속 탐구 가능성</h3>
              <p className="text-xs font-bold text-violet-400 uppercase tracking-widest mt-1">Growth Expansion</p>
            </div>
          </div>
          <p className="text-slate-300 text-lg leading-relaxed font-medium mb-10">
            {followupInquiry}
          </p>
          <div className="space-y-4">
            <p className="text-[10px] font-black text-slate-500 uppercase tracking-[0.2em] mb-4">Strategic Next Actions</p>
            {nextActions.slice(0, 3).map((action, i) => (
              <div key={i} className="flex gap-4 items-center p-4 rounded-2xl bg-white/[0.02] border border-white/5 hover:bg-white/[0.05] transition-colors">
                <span className="h-2 w-2 shrink-0 rounded-full bg-violet-500 shadow-[0_0_8px_rgba(139,92,246,0.6)]" />
                <span className="text-[15px] text-slate-300 font-bold">{action}</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* 5. AI Recommended Tracks */}
      {majorDirections.length > 0 && (
        <section className="bg-gradient-to-br from-[#111] to-[#191f28] rounded-[64px] p-12 sm:p-20 text-white relative overflow-hidden border border-white/5 shadow-3xl">
          <div className="absolute top-0 right-0 w-[600px] h-[600px] bg-blue-500/10 blur-[150px] -mr-64 -mt-64" />
          <div className="relative z-10">
            <div className="mb-20 flex flex-col gap-4">
               <div className="h-1 w-20 bg-blue-500 rounded-full" />
               <span className="text-blue-400 font-black tracking-[0.4em] text-[10px] uppercase">Future Pathway Architecture</span>
               <h3 className="text-5xl font-black tracking-tight leading-tight">AI 설계 최적 커리어 트랙</h3>
            </div>
            <div className="grid gap-8 md:grid-cols-3">
              {majorDirections.map((dir, i) => (
                <div key={i} className="group relative bg-white/[0.02] border border-white/5 p-12 rounded-[48px] hover:bg-white/[0.05] hover:border-white/20 transition-all duration-700 overflow-hidden">
                  <div className="absolute top-0 right-0 p-8 opacity-[0.03] group-hover:opacity-10 transition-opacity">
                    <span className="text-9xl font-black italic">0{i+1}</span>
                  </div>
                  <div className="relative z-10">
                    <div className="h-12 w-12 bg-white/5 rounded-2xl flex items-center justify-center mb-10 group-hover:bg-blue-500/10 group-hover:text-blue-400 transition-colors">
                      <Compass size={24} />
                    </div>
                    <p className="text-2xl font-black mb-6 group-hover:text-blue-400 transition-colors leading-tight">{dir.label}</p>
                    <p className="text-[16px] text-slate-400 font-medium leading-relaxed mb-10">{dir.summary}</p>
                    <div className="flex items-center gap-3 text-xs font-black text-slate-500 group-hover:text-white transition-all">
                       EXPLORE DETAILS <ArrowRight size={16} className="group-hover:translate-x-1 transition-transform" />
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </section>
      )}

      {/* 6. Strategic Footer Call to Action */}
      <section className="bg-white rounded-[64px] p-12 sm:p-24 shadow-[0_50px_100px_rgba(0,0,0,0.15)] relative overflow-hidden group">
        <div className="absolute top-0 right-0 w-[500px] h-[500px] bg-blue-50 blur-[120px] -mr-48 -mt-48 group-hover:bg-blue-100/50 transition-colors duration-1000" />
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-16 relative z-10">
          <div className="space-y-8 flex-1">
            <div className="inline-flex items-center gap-4 px-6 py-2.5 bg-blue-50 rounded-2xl text-blue-600 font-black text-[11px] uppercase tracking-[0.2em] shadow-sm">
              <Zap size={16} fill="currentColor" />
              Strategic Next Step
            </div>
            <h3 className="text-5xl font-black text-[#191f28] leading-[1.2] tracking-tight">진단 리포트를 기반으로<br /><span className="text-blue-600">독보적인 학생부</span>를 완성하세요</h3>
            <p className="text-slate-500 font-bold text-xl leading-relaxed max-w-xl">워크숍에서 AI 컨설턴트와 함께 세특의 논리를 강화하고 탐구의 깊이를 더할 수 있습니다.</p>
          </div>
          
          <button 
            onClick={() => navigate(`/app/workshop/${projectId}`)}
            className="group relative bg-[#191f28] text-white px-16 h-24 rounded-[32px] font-black text-2xl shadow-[0_20px_50px_rgba(25,31,40,0.3)] hover:-translate-y-2 transition-all active:scale-95 flex items-center gap-6 overflow-hidden shrink-0"
          >
             <span className="relative z-10">워크숍 시작하기</span>
             <ArrowRight size={28} strokeWidth={3} className="relative z-10 group-hover:translate-x-3 transition-transform" />
             <div className="absolute inset-0 bg-gradient-to-r from-[#3182f6] to-[#1b64da] opacity-0 group-hover:opacity-100 transition-opacity duration-700" />
          </button>
        </div>
      </section>

      {/* 7. Relational Keyword Visualization */}
      {diagnosisResult.relational_graph && (
        <div className="bg-white/5 rounded-[64px] p-16 border border-white/5 shadow-2xl">
           <div className="flex items-center justify-between mb-16">
             <div className="flex items-center gap-5">
               <div className="h-14 w-14 bg-blue-500/10 rounded-3xl flex items-center justify-center text-blue-400">
                 <Target size={32} strokeWidth={2.5} />
               </div>
               <div>
                 <h3 className="text-3xl font-black text-white">역량 키워드 네트워크</h3>
                 <p className="text-xs font-bold text-slate-500 uppercase tracking-widest mt-1">Competency Semantic Map</p>
               </div>
             </div>
             <span className="px-6 py-2 bg-white/5 border border-white/10 rounded-2xl text-[10px] font-black text-slate-400 uppercase tracking-widest">AI Semantic Analysis</span>
           </div>
           <div className="rounded-[40px] bg-black/40 p-10 ring-1 ring-white/5 h-[600px] shadow-inner relative overflow-hidden">
             <div className="absolute inset-0 bg-gradient-to-b from-blue-500/5 to-transparent pointer-events-none" />
             <DiagnosisRelationalGraph graph={diagnosisResult.relational_graph} />
           </div>
        </div>
      )}
    </motion.div>
  );
};
