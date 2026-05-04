import React from 'react';
import { motion } from 'motion/react';
import { useNavigate } from 'react-router-dom';
import { 
  CheckCircle2, 
  AlertTriangle, 
  Target, 
  Mic, 
  BookOpen, 
  Lightbulb, 
  Link2,
  Gauge, 
  Compass, 
  ShieldCheck, 
  TrendingUp, 
  ArrowRight,
  BarChart3,
  Award,
  FileText
} from 'lucide-react';
import { Timeline } from './Timeline';
import { DiagnosisRelationalGraph } from './DiagnosisRelationalGraph';
import { useOnboardingStore } from '../../store/onboardingStore';
import { DiagnosisRunResponse } from '../../types/api';
import { DiagnosisReportPanel } from '../DiagnosisReportPanel';

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
  const scoringPolicyRaw = summaryJson ? asRecord(summaryJson.scoring_policy) : null;
  const majorDirectionsRaw = summaryJson?.major_direction_candidates_top3;
  const scoreCap = scoringPolicyRaw ? asNumber(scoringPolicyRaw.evidence_quality_score_cap) : null;
  const scoreValidity = String(scoringPolicyRaw?.score_validity ?? '').trim();
  const scoreQualityNotes = Array.isArray(scoringPolicyRaw?.quality_gate_notes)
    ? scoringPolicyRaw.quality_gate_notes.map((item) => sanitizeKoreanText(item, '')).filter(Boolean)
    : [];
  const shouldShowScoreGate = Boolean(
    scoreValidity && scoreValidity !== 'verified_student_record' || (scoreCap !== null && scoreCap < 100)
  );
  
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
  
  const academicCompetency = sanitizeKoreanText(summaryJson?.academic_competency || diagnosisResult.academic_competency, '학업 역량 분석 결과를 생성 중입니다.');
  const majorSuitability = sanitizeKoreanText(summaryJson?.major_suitability || diagnosisResult.major_suitability, '전공 적합성 분석 결과를 생성 중입니다.');
  const inquiryCompetency = sanitizeKoreanText(summaryJson?.inquiry_competency || diagnosisResult.inquiry_competency, '탐구 역량 분석 결과를 생성 중입니다.');
  const activityConsistency = sanitizeKoreanText(summaryJson?.activity_consistency || diagnosisResult.activity_consistency, '활동 일관성 분석 결과를 생성 중입니다.');
  const keySubjectComments = sanitizeList(summaryJson?.key_subject_comments || diagnosisResult.key_subject_comments, '핵심 세특 항목을 분석 중입니다.');
  const interviewDefensibility = sanitizeKoreanText(summaryJson?.interview_defensibility || diagnosisResult.interview_defensibility, '면접 방어력 분석 결과를 생성 중입니다.');
  const followupInquiry = sanitizeKoreanText(summaryJson?.followup_inquiry || diagnosisResult.followup_inquiry, '후속 탐구 가능성 제안을 생성 중입니다.');

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
      className="mx-auto max-w-5xl space-y-12 pb-24"
    >
      {/* 1. Header Section */}
      <section className="relative text-center space-y-4 pb-8 border-b-2 border-slate-900">
        <div className="flex justify-center items-center gap-3 mb-2">
          <span className="px-3 py-1 bg-blue-100 text-blue-800 font-bold uppercase tracking-widest text-xs rounded-full">
            Uni Foli 정밀 진단 리포트
          </span>
          {completionState && (
            <span className="px-3 py-1 bg-slate-100 text-slate-800 font-bold uppercase tracking-widest text-xs rounded-full">
              {completionState}
            </span>
          )}
        </div>
        <h1 className="text-3xl md:text-4xl font-extrabold text-slate-900 tracking-tight">
          {sanitizeKoreanText(diagnosisResult.headline, '학생부 정밀 진단 결과')}
        </h1>
        <p className="text-lg text-slate-700 font-medium max-w-3xl mx-auto">
          {sanitizeKoreanText(diagnosisResult.overview)}
        </p>

        {diagnosisRun && diagnosisRun.id && (
          <div className="pt-4 flex justify-center">
            <div className="max-w-md w-full">
              <DiagnosisReportPanel
                diagnosisRunId={diagnosisRun.id}
                reportStatus={diagnosisRun.report_status}
                reportAsyncJobStatus={diagnosisRun.report_async_job_status}
                reportArtifactId={diagnosisRun.report_artifact_id}
                reportErrorMessage={diagnosisRun.report_error_message}
                variant="minimal"
              />
            </div>
          </div>
        )}
      </section>

      {/* 2. Executive Summary (요약과 하이라이트) */}
      <section className="bg-slate-50 border border-slate-200 p-8 md:p-10 rounded-2xl shadow-sm">
        <h2 className="text-2xl font-bold text-slate-900 mb-8 flex items-center gap-3">
          <BarChart3 className="text-blue-600" size={28} />
          Executive Summary
        </h2>
        
        <div className="grid md:grid-cols-3 gap-8">
          {/* Score & Major */}
          <div className="space-y-6 md:col-span-1">
            <div className="bg-white p-6 rounded-xl border border-slate-200 shadow-sm flex flex-col items-center justify-center text-center h-full">
              <span className="text-sm font-bold text-slate-600 mb-2 uppercase tracking-widest">종합 평가 점수</span>
              <div className="text-6xl font-extrabold text-blue-700 tracking-tighter tabular-nums mb-2">
                {totalScore !== null ? Math.round(totalScore) : '--'}
              </div>
              <span className="px-4 py-1.5 bg-blue-50 text-blue-800 rounded-lg text-sm font-bold">
                {normalizeScoreLabel(scoreLabelsRaw?.['총점'])}
              </span>
              {shouldShowScoreGate && (
                <div className="mt-4 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-left text-xs font-bold leading-relaxed text-amber-900">
                  <div className="flex items-start gap-2">
                    <AlertTriangle size={14} className="mt-0.5 shrink-0" />
                    <p>
                      {scoreQualityNotes[0] || '원본 학생부 구조와 근거 수를 기준으로 점수 상한을 적용했습니다.'}
                      {scoreCap !== null && scoreCap < 100 ? ` (상한 ${Math.round(scoreCap)}점)` : ''}
                    </p>
                  </div>
                </div>
              )}
            </div>
          </div>
          
          {/* Key Strengths & Weaknesses */}
          <div className="md:col-span-2 grid grid-cols-1 sm:grid-cols-2 gap-6">
            <div className="bg-white p-6 rounded-xl border-t-4 border-t-emerald-500 border-x border-b border-slate-200 shadow-sm">
              <div className="flex items-center gap-2 text-emerald-700 mb-4">
                <CheckCircle2 size={20} />
                <h3 className="font-bold text-lg">주요 강점 (Strengths)</h3>
              </div>
              <ul className="space-y-3">
                {strengths.slice(0, 3).map((item, i) => (
                  <li key={i} className="text-slate-800 text-sm font-medium flex items-start gap-2 leading-relaxed">
                    <span className="text-emerald-500 mt-1">•</span>
                    {item}
                  </li>
                ))}
              </ul>
            </div>
            
            <div className="bg-white p-6 rounded-xl border-t-4 border-t-rose-500 border-x border-b border-slate-200 shadow-sm">
              <div className="flex items-center gap-2 text-rose-700 mb-4">
                <AlertTriangle size={20} />
                <h3 className="font-bold text-lg">보완 필요 (Risks)</h3>
              </div>
              <ul className="space-y-3">
                {risks.slice(0, 3).map((item, i) => (
                  <li key={i} className="text-slate-800 text-sm font-medium flex items-start gap-2 leading-relaxed">
                    <span className="text-rose-500 mt-1">•</span>
                    {item}
                  </li>
                ))}
              </ul>
            </div>
          </div>
        </div>

        {/* AI Recommended Majors */}
        {majorDirections.length > 0 && (
          <div className="mt-8 pt-8 border-t border-slate-200">
            <h3 className="text-lg font-bold text-slate-900 mb-4 flex items-center gap-2">
              <Compass className="text-blue-600" size={20} />
              추천 전공 적합성
            </h3>
            <div className="grid sm:grid-cols-3 gap-4">
              {majorDirections.map((dir, i) => (
                <div key={i} className="bg-white border border-slate-200 p-4 rounded-xl">
                  <p className="font-bold text-slate-900 mb-1">{dir.label}</p>
                  <p className="text-sm text-slate-700 font-medium line-clamp-2 leading-relaxed">{dir.summary}</p>
                </div>
              ))}
            </div>
          </div>
        )}
      </section>

      {/* 3. Detailed Competency Analysis (표/리스트 형태 강조) */}
      <section className="space-y-8">
        <h2 className="text-2xl font-bold text-slate-900 flex items-center gap-3 border-b-2 border-slate-100 pb-4">
          <Award className="text-blue-600" size={28} />
          핵심 역량 상세 분석
        </h2>

        <div className="grid lg:grid-cols-3 gap-8">
          {/* Dashboard Scores */}
          <div className="lg:col-span-1">
            <div className="bg-slate-900 text-white p-8 rounded-2xl shadow-md sticky top-6">
              <h3 className="text-lg font-bold mb-6 flex items-center gap-2">
                <Gauge size={20} className="text-blue-400" />
                역량 지표
              </h3>
              <div className="space-y-6">
                {categoryScores.map(({ name, score }) => (
                  <div key={name} className="space-y-2">
                    <div className="flex justify-between items-end">
                       <span className="text-sm font-bold text-slate-300">{name}</span>
                       <span className="text-lg font-bold tabular-nums">{Math.round(score)}<span className="text-xs text-slate-500 ml-1">/100</span></span>
                    </div>
                    <div className="h-2.5 w-full bg-slate-800 rounded-full overflow-hidden">
                      <motion.div 
                        initial={{ width: 0 }}
                        animate={{ width: `${score}%` }}
                        transition={{ duration: 1.5, ease: "easeOut" }}
                        className="h-full bg-blue-500 rounded-full"
                      />
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>

          {/* Text Analysis Grid */}
          <div className="lg:col-span-2 space-y-6">
            <div className="grid sm:grid-cols-2 gap-6">
              <div className="bg-white border border-slate-200 p-6 rounded-xl shadow-sm">
                <h4 className="text-lg font-bold text-slate-900 mb-3 flex items-center gap-2">
                  <BookOpen size={18} className="text-blue-600" /> 학업 역량
                </h4>
                <p className="text-slate-800 text-sm leading-relaxed font-medium">{academicCompetency}</p>
              </div>
              <div className="bg-white border border-slate-200 p-6 rounded-xl shadow-sm">
                <h4 className="text-lg font-bold text-slate-900 mb-3 flex items-center gap-2">
                  <Lightbulb size={18} className="text-violet-600" /> 탐구 역량
                </h4>
                <p className="text-slate-800 text-sm leading-relaxed font-medium">{inquiryCompetency}</p>
              </div>
            </div>
            
            <div className="bg-white border border-slate-200 p-6 rounded-xl shadow-sm">
              <h4 className="text-lg font-bold text-slate-900 mb-3 flex items-center gap-2">
                <Link2 size={18} className="text-emerald-600" /> 활동 일관성 및 전공 적합성
              </h4>
              <div className="grid sm:grid-cols-2 gap-6 mt-4">
                <div>
                  <h5 className="text-sm font-bold text-slate-500 mb-2">전공 적합성</h5>
                  <p className="text-slate-800 text-sm leading-relaxed font-medium">{majorSuitability}</p>
                </div>
                <div>
                  <h5 className="text-sm font-bold text-slate-500 mb-2">활동 일관성</h5>
                  <p className="text-slate-800 text-sm leading-relaxed font-medium">{activityConsistency}</p>
                </div>
              </div>
            </div>

            {/* Key Subject Comments - Styled like a table/list */}
            <div className="bg-white border border-slate-200 rounded-xl shadow-sm overflow-hidden">
              <div className="bg-slate-50 px-6 py-4 border-b border-slate-200">
                <h4 className="text-lg font-bold text-slate-900 flex items-center gap-2">
                  <FileText size={18} className="text-amber-600" /> 핵심 세부능력 및 특기사항
                </h4>
              </div>
              <div className="divide-y divide-slate-100">
                {keySubjectComments.map((comment, i) => (
                  <div key={i} className="flex gap-4 p-6 hover:bg-slate-50 transition-colors">
                    <div className="h-8 w-8 shrink-0 rounded-full bg-amber-100 text-amber-700 flex items-center justify-center text-sm font-bold">
                      {i+1}
                    </div>
                    <p className="text-slate-800 text-sm font-medium leading-relaxed pt-1">{comment}</p>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* 4. Strategic Actions & Interviews */}
      <section className="grid md:grid-cols-2 gap-6">
        <div className="bg-blue-50 border border-blue-200 p-8 rounded-2xl shadow-sm">
          <h3 className="text-xl font-bold text-slate-900 mb-4 flex items-center gap-2">
            <ShieldCheck size={24} className="text-blue-600" />
            면접 방어력 분석
          </h3>
          <p className="text-slate-800 text-base leading-relaxed font-medium mb-6">
            {interviewDefensibility}
          </p>
          <div className="bg-white bg-opacity-60 p-4 rounded-xl border border-blue-100">
            <h4 className="text-sm font-bold text-blue-800 mb-2 flex items-center gap-2">
              <Mic size={16} /> 면접 활용성
            </h4>
            <p className="text-slate-800 text-sm leading-relaxed font-medium">{interviewUtility}</p>
          </div>
        </div>

        <div className="bg-violet-50 border border-violet-200 p-8 rounded-2xl shadow-sm">
          <h3 className="text-xl font-bold text-slate-900 mb-4 flex items-center gap-2">
            <TrendingUp size={24} className="text-violet-600" />
            후속 탐구 및 보완 방향
          </h3>
          <p className="text-slate-800 text-base leading-relaxed font-medium mb-6">
            {followupInquiry}
          </p>
          <div className="bg-white bg-opacity-60 p-4 rounded-xl border border-violet-100">
             <h4 className="text-sm font-bold text-violet-800 mb-2 flex items-center gap-2">
              <Target size={16} /> 권장 개선 방향
            </h4>
            <ul className="space-y-2">
              {improvements.slice(0, 3).map((item, i) => (
                <li key={i} className="text-slate-800 text-sm font-medium flex items-start gap-2 leading-relaxed">
                  <span className="text-violet-500 mt-1">•</span>
                  {item}
                </li>
              ))}
            </ul>
          </div>
        </div>
      </section>

      {/* 5. Timeline */}
      <section className="bg-white border border-slate-200 p-8 md:p-10 rounded-2xl shadow-sm">
        <h3 className="text-2xl font-bold text-slate-900 mb-8 border-b-2 border-slate-100 pb-4">학기별 진로·학업 타임라인</h3>
        <Timeline grade={profile.grade} />
      </section>

      {/* 6. Relational Keyword Visualization */}
      {diagnosisResult.relational_graph && (
        <section className="bg-white border border-slate-200 p-8 md:p-10 rounded-2xl shadow-sm">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-8 border-b-2 border-slate-100 pb-4">
            <div>
              <h3 className="text-2xl font-bold text-slate-900 flex items-center gap-3">
                <Target size={28} className="text-blue-600" />
                역량 키워드 관계 분석
              </h3>
              <p className="text-base font-medium text-slate-600 mt-2">학생부 활동 간의 연결성과 흐름을 시각화합니다.</p>
            </div>
            <span className="px-4 py-2 bg-slate-100 text-slate-600 font-bold uppercase text-xs rounded-lg tracking-widest self-start sm:self-auto">
              AI Semantic Mapping
            </span>
          </div>
          
          <div className="relative rounded-xl overflow-hidden border border-slate-100 bg-slate-50">
            <DiagnosisRelationalGraph graph={diagnosisResult.relational_graph} />
          </div>
        </section>
      )}


      {/* 8. CTA */}
      <section className="bg-slate-900 text-white rounded-2xl p-10 md:p-12 shadow-xl flex flex-col md:flex-row items-center justify-between gap-8 relative overflow-hidden">
        <div className="absolute top-0 right-0 w-96 h-96 bg-blue-600 rounded-full blur-[100px] -mr-32 -mt-32 opacity-30 pointer-events-none" />
        <div className="relative z-10 space-y-4 text-center md:text-left">
          <h3 className="text-3xl font-bold tracking-tight">기록을 한 단계 더 업그레이드하세요</h3>
          <p className="text-slate-300 font-medium text-lg max-w-xl">
            워크숍에서 AI 컨설턴트와 함께 세특의 논리를 강화하고 탐구의 깊이를 더해보세요. 지금 바로 시작할 수 있습니다.
          </p>
        </div>
        <button 
          onClick={() => navigate(`/app/workshop/${projectId}`)}
          className="relative z-10 bg-blue-500 text-white px-8 py-4 rounded-xl font-bold text-lg hover:bg-blue-400 transition-all shadow-lg flex items-center gap-3 shrink-0"
        >
           워크숍으로 이동
           <ArrowRight size={20} />
        </button>
      </section>
    </motion.div>
  );
};
