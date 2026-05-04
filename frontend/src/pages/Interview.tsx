import React, { useCallback, useMemo, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { AnimatePresence, motion } from 'motion/react';
import {
  AlertCircle,
  ArrowLeft,
  Award,
  BookOpen,
  CheckCircle2,
  ChevronRight,
  ClipboardList,
  FileText,
  Loader2,
  Mic,
  PlayCircle,
  RefreshCw,
  Send,
  Sparkles,
  Target,
  UserCheck,
} from 'lucide-react';
import toast from 'react-hot-toast';

import {
  EmptyState,
  PrimaryButton,
  SecondaryButton,
  SectionCard,
  StatusBadge,
  SurfaceCard,
  TextArea,
} from '../components/primitives';
import { api } from '../lib/api';
import { DIAGNOSIS_STORAGE_KEY, type StoredDiagnosis } from '../lib/diagnosis';
import { useOnboardingStore } from '../store/onboardingStore';

interface InterviewQuestion {
  id: string;
  category?: string;
  strategy?: string;
  question: string;
  rationale: string;
  answer_frame?: string;
  avoid?: string;
  expected_evidence_ids?: string[];
}

interface InterviewEvaluation {
  score: number;
  grade?: 'S' | 'A' | 'B' | 'C';
  grade_label?: string;
  axes_scores: Record<string, number>;
  feedback: string;
  coaching_advice: string;
  follow_up_questions?: string[];
}

type CachedDiagnosis = StoredDiagnosis & {
  diagnosisRunId?: string | null;
};

const AXIS_LABELS: Record<string, string> = {
  구체성: '구체성',
  진정성: '진정성',
  '학생부 근거 활용': '생기부 근거',
  '전공 연결성': '전공 연결',
  '논리적 인과관계': '논리 인과',
};
const AXIS_ICONS = [Target, UserCheck, BookOpen, Award, ClipboardList];
const GRADE_STYLES: Record<string, string> = {
  S: 'bg-violet-100 text-violet-700 ring-violet-200',
  A: 'bg-blue-100 text-blue-700 ring-blue-200',
  B: 'bg-emerald-100 text-emerald-700 ring-emerald-200',
  C: 'bg-amber-100 text-amber-800 ring-amber-200',
};

function readStoredDiagnosis(): CachedDiagnosis | null {
  if (typeof window === 'undefined') return null;
  try {
    const raw = window.localStorage.getItem(DIAGNOSIS_STORAGE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as CachedDiagnosis;
    return parsed && typeof parsed === 'object' ? parsed : null;
  } catch {
    return null;
  }
}

function resolveApiMessage(error: any): string {
  if (error?.response?.status === 404) {
    return '먼저 AI 진단을 완료한 뒤 면접 질문을 생성할 수 있습니다.';
  }
  const detail = error?.response?.data?.detail;
  if (typeof detail === 'string' && detail.trim()) return detail.trim();
  return '면접 질문을 생성하지 못했습니다. 잠시 후 다시 시도해 주세요.';
}

export const Interview: React.FC = () => {
  const { projectId } = useParams<{ projectId: string }>();
  const navigate = useNavigate();
  const storedDiagnosis = useMemo(readStoredDiagnosis, []);
  const storeProjectId = useOnboardingStore((state) => state.activeProjectId);
  const candidateProjectIds = useMemo(
    () => Array.from(new Set([projectId, storeProjectId, storedDiagnosis?.projectId].filter(Boolean) as string[])),
    [projectId, storeProjectId, storedDiagnosis?.projectId],
  );
  const activeProjectId = candidateProjectIds[0] ?? null;
  const activeStoredDiagnosis =
    storedDiagnosis?.projectId && storedDiagnosis.projectId === activeProjectId ? storedDiagnosis : null;

  const [questions, setQuestions] = useState<InterviewQuestion[]>([]);
  const [currentIndex, setCurrentIndex] = useState(0);
  const [hasRequestedQuestions, setHasRequestedQuestions] = useState(false);
  const [loading, setLoading] = useState(false);
  const [answering, setAnswering] = useState(false);
  const [answer, setAnswer] = useState('');
  const [evaluation, setEvaluation] = useState<InterviewEvaluation | null>(null);
  const [finished, setFinished] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const currentQuestion = questions[currentIndex] ?? null;
  const targetLabel = [
    activeStoredDiagnosis?.targetUniversity ?? activeStoredDiagnosis?.target_university,
    activeStoredDiagnosis?.targetMajor ?? activeStoredDiagnosis?.target_major ?? activeStoredDiagnosis?.major,
  ]
    .filter(Boolean)
    .join(' · ');

  const generateQuestions = useCallback(async () => {
    if (!activeProjectId) {
      navigate('/app/diagnosis');
      return;
    }

    setHasRequestedQuestions(true);
    setLoading(true);
    setErrorMessage(null);
    setEvaluation(null);
    setAnswer('');
    setFinished(false);
    setCurrentIndex(0);

    try {
      let data: InterviewQuestion[] | null = null;
      let lastError: any = null;

      for (const candidateProjectId of candidateProjectIds) {
        try {
          data = await api.post<InterviewQuestion[]>('/api/v1/interview/generate-questions', {
            project_id: candidateProjectId,
          });
          break;
        } catch (candidateError: any) {
          lastError = candidateError;
          if (candidateError?.response?.status !== 404) break;
        }
      }

      if (!data) {
        throw lastError;
      }

      if (!data.length) {
        setQuestions([]);
        setErrorMessage('생성된 질문이 없습니다. AI 진단을 다시 확인해 주세요.');
        toast.error('생성된 질문이 없습니다.');
        return;
      }
      setQuestions(data);
      toast.success('면접 질문이 준비되었습니다.');
    } catch (error: any) {
      const message = resolveApiMessage(error);
      setQuestions([]);
      setErrorMessage(message);
      toast.error(message);
    } finally {
      setLoading(false);
    }
  }, [activeProjectId, candidateProjectIds, navigate]);

  const submitAnswer = async () => {
    if (!currentQuestion) return;
    if (!answer.trim()) {
      toast.error('답변을 입력해 주세요.');
      return;
    }

    try {
      setAnswering(true);
      const data = await api.post<InterviewEvaluation>('/api/v1/interview/evaluate-answer', {
        question: currentQuestion.question,
        answer,
        context: activeStoredDiagnosis?.diagnosis?.headline ?? '',
      });
      setEvaluation(data);
    } catch (error) {
      toast.error('답변 분석에 실패했습니다.');
      console.error(error);
    } finally {
      setAnswering(false);
    }
  };

  const nextQuestion = () => {
    if (currentIndex < questions.length - 1) {
      setCurrentIndex(prev => prev + 1);
      setAnswer('');
      setEvaluation(null);
      return;
    }
    setFinished(true);
  };

  const restartPractice = () => {
    setQuestions([]);
    setCurrentIndex(0);
    setHasRequestedQuestions(false);
    setAnswer('');
    setEvaluation(null);
    setFinished(false);
    setErrorMessage(null);
  };

  if (finished) {
    return (
      <div className="mx-auto max-w-2xl px-4 py-12">
        <motion.div initial={{ opacity: 0, scale: 0.96 }} animate={{ opacity: 1, scale: 1 }} className="text-center">
          <div className="mb-6 flex justify-center">
            <div className="flex h-20 w-20 items-center justify-center rounded-full bg-emerald-100 text-emerald-600">
              <CheckCircle2 size={40} />
            </div>
          </div>
          <h1 className="text-3xl font-black text-slate-900">모의 면접 완료</h1>
          <p className="mt-4 text-base font-semibold leading-7 text-slate-600">
            총 {questions.length}개의 질문에 답변했습니다. 부족했던 답변은 탐구 근거와 전공 연결을 보강하면 더 좋아집니다.
          </p>
          <div className="mt-10 flex flex-wrap justify-center gap-3">
            {activeProjectId ? (
              <SecondaryButton onClick={() => navigate(`/app/workshop/${activeProjectId}`)}>문서 작성으로 이동</SecondaryButton>
            ) : null}
            <PrimaryButton onClick={restartPractice}>
              새 질문으로 연습하기 <RefreshCw size={16} />
            </PrimaryButton>
          </div>
        </motion.div>
      </div>
    );
  }

  const renderPreparation = () => (
    <div className="space-y-6">
      {!activeProjectId ? (
        <EmptyState
          icon={<FileText size={24} />}
          title="AI 진단 결과가 필요합니다."
          description="면접 질문은 생기부 PDF 진단 결과를 기준으로 생성됩니다."
          actionLabel="AI 진단 시작하기"
          onAction={() => navigate('/app/diagnosis')}
          className="bg-white"
        />
      ) : (
        <>
          <div className="grid gap-4 lg:grid-cols-3">
            <SurfaceCard className="p-6">
              <div className="mb-4 flex h-11 w-11 items-center justify-center rounded-2xl bg-blue-50 text-blue-600">
                <Sparkles size={22} />
              </div>
              <p className="text-xs font-black uppercase tracking-widest text-slate-400">질문 생성</p>
              <h2 className="mt-2 text-lg font-black text-slate-950">생기부 기반 예상 질문</h2>
              <p className="mt-3 text-sm font-semibold leading-6 text-slate-500">
                AI 진단에서 잡힌 강점, 보완점, 전공 연결 지점을 질문으로 바꿉니다.
              </p>
            </SurfaceCard>

            <SurfaceCard className="p-6">
              <div className="mb-4 flex h-11 w-11 items-center justify-center rounded-2xl bg-emerald-50 text-emerald-600">
                <ClipboardList size={22} />
              </div>
              <p className="text-xs font-black uppercase tracking-widest text-slate-400">답변 구조</p>
              <h2 className="mt-2 text-lg font-black text-slate-950">근거 중심 답변 연습</h2>
              <p className="mt-3 text-sm font-semibold leading-6 text-slate-500">
                활동 맥락, 배운 점, 다음 탐구로 이어지는 흐름을 점검합니다.
              </p>
            </SurfaceCard>

            <SurfaceCard className="p-6">
              <div className="mb-4 flex h-11 w-11 items-center justify-center rounded-2xl bg-amber-50 text-amber-600">
                <Award size={22} />
              </div>
              <p className="text-xs font-black uppercase tracking-widest text-slate-400">피드백</p>
              <h2 className="mt-2 text-lg font-black text-slate-950">구체성·진정성 평가</h2>
              <p className="mt-3 text-sm font-semibold leading-6 text-slate-500">
                답변 제출 후 면접관 관점의 피드백과 보완 포인트를 확인합니다.
              </p>
            </SurfaceCard>
          </div>

          <SurfaceCard className="border-blue-100 bg-blue-50/60 p-6">
            <div className="flex flex-col gap-5 lg:flex-row lg:items-center lg:justify-between">
              <div>
                <p className="text-xs font-black uppercase tracking-widest text-blue-600">Ready</p>
                <h2 className="mt-2 text-xl font-black text-slate-950">
                  {targetLabel || '최근 AI 진단'} 기준으로 면접 질문을 준비합니다.
                </h2>
                <p className="mt-2 text-sm font-semibold leading-6 text-slate-600">
                  버튼을 누르면 최신 진단 결과에서 예상 질문을 생성합니다.
                </p>
              </div>
              <div className="flex flex-wrap gap-2">
                <SecondaryButton onClick={() => navigate('/app/diagnosis/history')}>진단서 보기</SecondaryButton>
                <PrimaryButton onClick={generateQuestions} disabled={loading} size="lg">
                  {loading ? <Loader2 size={18} className="animate-spin" /> : <PlayCircle size={18} />}
                  질문 생성하기
                </PrimaryButton>
              </div>
            </div>
          </SurfaceCard>
        </>
      )}

      {loading ? (
        <SurfaceCard className="flex items-center gap-3 border-slate-200 p-5">
          <Loader2 size={18} className="animate-spin text-blue-600" />
          <p className="text-sm font-bold text-slate-600">생기부 진단 내용을 바탕으로 질문을 준비하고 있습니다.</p>
        </SurfaceCard>
      ) : null}

      {errorMessage ? (
        <div className="rounded-2xl border border-amber-200 bg-amber-50 px-5 py-4 text-sm font-bold text-amber-900">
          {errorMessage}
        </div>
      ) : null}

      {hasRequestedQuestions && !loading && !questions.length && activeProjectId ? (
        <div className="flex justify-center">
          <PrimaryButton onClick={generateQuestions}>
            다시 생성하기 <RefreshCw size={16} />
          </PrimaryButton>
        </div>
      ) : null}
    </div>
  );

  return (
    <div className="mx-auto max-w-5xl px-4 py-8 sm:py-12">
      <div className="mb-8 flex flex-col justify-between gap-4 sm:flex-row sm:items-start">
        <div className="flex items-start gap-4">
          <button
            type="button"
            onClick={() => navigate(-1)}
            aria-label="이전 화면"
            className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-white text-slate-400 shadow-sm ring-1 ring-slate-200 transition-colors hover:text-slate-600"
          >
            <ArrowLeft size={20} />
          </button>
          <div>
            <p className="text-sm font-black uppercase tracking-widest text-blue-600">Interview</p>
            <h1 className="mt-2 text-3xl font-black tracking-tight text-slate-950">면접 준비</h1>
            <p className="mt-2 max-w-2xl text-sm font-semibold leading-6 text-slate-500">
              생기부 진단 결과에서 예상 질문을 만들고 답변을 바로 점검합니다.
            </p>
          </div>
        </div>
        <StatusBadge status={questions.length ? 'active' : activeProjectId ? 'neutral' : 'warning'}>
          {questions.length ? `${currentIndex + 1}/${questions.length}` : activeProjectId ? '생성 대기' : '진단 필요'}
        </StatusBadge>
      </div>

      {!questions.length || !currentQuestion ? (
        renderPreparation()
      ) : (
        <div className="grid gap-8">
          <SectionCard
            eyebrow={`Question ${currentIndex + 1}`}
            title="AI 모의 면접"
            description="면접관 질문에 답변하고 구체성, 진정성, 생기부 근거, 전공 연결을 점검합니다."
            className="border-none bg-white shadow-xl ring-1 ring-slate-200/60"
          >
            <div className="mb-8 rounded-[2rem] bg-slate-950 p-8 text-white shadow-xl lg:p-10">
              <div className="mb-6 flex items-center gap-2 text-blue-300">
                <Mic size={20} className="animate-pulse" />
                <span className="text-xs font-black uppercase tracking-widest text-blue-300">AI Interviewer</span>
              </div>
              <div className="mb-4 flex flex-wrap gap-2">
                {currentQuestion.category ? (
                  <span className="rounded-full bg-white/10 px-3 py-1 text-xs font-black text-blue-100 ring-1 ring-white/10">
                    {currentQuestion.category}
                  </span>
                ) : null}
                {currentQuestion.strategy ? (
                  <span className="rounded-full bg-amber-300/15 px-3 py-1 text-xs font-black text-amber-100 ring-1 ring-amber-200/20">
                    {currentQuestion.strategy}
                  </span>
                ) : null}
              </div>
              <h2 className="text-xl font-black leading-relaxed sm:text-2xl">
                {currentQuestion.question}
              </h2>
              <p className="mt-6 text-sm font-bold leading-6 text-slate-400">
                질문 의도: {currentQuestion.rationale}
              </p>
              {(currentQuestion.answer_frame || currentQuestion.avoid || currentQuestion.expected_evidence_ids?.length) ? (
                <div className="mt-6 grid gap-4 text-sm font-bold leading-6 text-slate-300 lg:grid-cols-2">
                  {currentQuestion.answer_frame ? (
                    <div className="rounded-2xl bg-white/5 p-4 ring-1 ring-white/10">
                      <p className="text-xs font-black uppercase tracking-widest text-blue-200">Answer Frame</p>
                      <p className="mt-2">{currentQuestion.answer_frame}</p>
                    </div>
                  ) : null}
                  {currentQuestion.avoid ? (
                    <div className="rounded-2xl bg-white/5 p-4 ring-1 ring-white/10">
                      <p className="text-xs font-black uppercase tracking-widest text-amber-200">Avoid</p>
                      <p className="mt-2">{currentQuestion.avoid}</p>
                    </div>
                  ) : null}
                  {currentQuestion.expected_evidence_ids?.length ? (
                    <div className="rounded-2xl bg-white/5 p-4 ring-1 ring-white/10 lg:col-span-2">
                      <p className="text-xs font-black uppercase tracking-widest text-emerald-200">Evidence</p>
                      <p className="mt-2">{currentQuestion.expected_evidence_ids.join(' · ')}</p>
                    </div>
                  ) : null}
                </div>
              ) : null}
            </div>

            <AnimatePresence mode="wait">
              {!evaluation ? (
                <motion.div
                  key="answer-input"
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -10 }}
                  className="space-y-4"
                >
                  <TextArea
                    value={answer}
                    onChange={(event) => setAnswer(event.target.value)}
                    placeholder="답변을 입력해 주세요. 활동 근거와 느낀 점을 함께 적으면 더 정밀하게 피드백합니다."
                    disabled={answering}
                    className="min-h-[200px] bg-slate-50/50 p-6 text-base font-medium leading-relaxed ring-slate-200 focus:bg-white sm:text-lg"
                  />
                  <div className="flex justify-end">
                    <PrimaryButton onClick={submitAnswer} disabled={!answer.trim() || answering} className="px-8">
                      {answering ? (
                        <>
                          <Loader2 size={18} className="animate-spin" />
                          답변 분석 중
                        </>
                      ) : (
                        <>
                          답변 제출하기 <Send size={18} />
                        </>
                      )}
                    </PrimaryButton>
                  </div>
                </motion.div>
              ) : (
                <motion.div
                  key="evaluation-result"
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  className="space-y-8"
                >
                  <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
                    {Object.entries(evaluation.axes_scores).map(([axis, score], index) => {
                      const Icon = AXIS_ICONS[index] ?? Target;
                      return (
                        <SurfaceCard key={axis} className="border-none bg-white p-5 shadow-sm ring-1 ring-slate-200/60">
                          <div className="mb-2 flex items-center gap-2">
                            <Icon size={14} className="text-blue-500" />
                            <span className="text-[10px] font-black uppercase tracking-widest text-slate-400">
                              {AXIS_LABELS[axis] ?? axis}
                            </span>
                          </div>
                          <p className="text-2xl font-black text-slate-900">
                            {score}<span className="ml-1 text-xs text-slate-300">pts</span>
                          </p>
                        </SurfaceCard>
                      );
                    })}
                  </div>

                  <SurfaceCard className="border-none bg-blue-50/70 p-8 ring-1 ring-blue-100">
                    <div className="mb-6 flex items-center gap-3">
                      <div className="flex h-10 w-10 items-center justify-center rounded-2xl bg-blue-600 text-white shadow-lg shadow-blue-200">
                        <Award size={20} />
                      </div>
                      <div className="min-w-0 flex-1">
                        <h4 className="text-lg font-black text-slate-900">면접관 피드백</h4>
                        <p className="text-xs font-black uppercase tracking-widest text-blue-500/70">Expert Evaluation</p>
                      </div>
                      {evaluation.grade ? (
                        <div className={`rounded-2xl px-4 py-3 text-center ring-1 ${GRADE_STYLES[evaluation.grade] ?? GRADE_STYLES.C}`}>
                          <p className="text-2xl font-black leading-none">{evaluation.grade}</p>
                          <p className="mt-1 text-[10px] font-black uppercase tracking-widest">Grade</p>
                        </div>
                      ) : null}
                    </div>

                    <div className="space-y-6">
                      {evaluation.grade_label ? (
                        <p className="rounded-2xl bg-white px-5 py-4 text-sm font-black leading-6 text-slate-700 ring-1 ring-blue-100">
                          {evaluation.grade_label}
                        </p>
                      ) : null}

                      <div>
                        <p className="mb-2 text-xs font-black uppercase tracking-widest text-slate-400">종합 평가</p>
                        <p className="text-lg font-bold leading-relaxed text-slate-700">{evaluation.feedback}</p>
                      </div>

                      <div className="rounded-2xl bg-white p-6 shadow-sm ring-1 ring-blue-100">
                        <p className="mb-3 flex items-center gap-2 text-sm font-black text-blue-700">
                          <AlertCircle size={16} />
                          보완 포인트
                        </p>
                        <p className="text-base font-bold leading-relaxed text-slate-600">
                          {evaluation.coaching_advice}
                        </p>
                      </div>

                      {evaluation.follow_up_questions?.length ? (
                        <div>
                          <p className="mb-3 text-xs font-black uppercase tracking-widest text-slate-400">
                            꼬리 질문
                          </p>
                          <div className="space-y-2">
                            {evaluation.follow_up_questions.map((item, index) => (
                              <p
                                key={`${item}-${index}`}
                                className="rounded-2xl bg-white px-5 py-4 text-sm font-bold leading-6 text-slate-700 ring-1 ring-blue-100"
                              >
                                {item}
                              </p>
                            ))}
                          </div>
                        </div>
                      ) : null}
                    </div>
                  </SurfaceCard>

                  <div className="flex justify-center">
                    <PrimaryButton onClick={nextQuestion} className="px-10">
                      {currentIndex < questions.length - 1 ? '다음 질문으로 이동' : '연습 마무리'}
                      <ChevronRight size={18} />
                    </PrimaryButton>
                  </div>
                </motion.div>
              )}
            </AnimatePresence>
          </SectionCard>
        </div>
      )}
    </div>
  );
};
