import React, { useState, useEffect, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { motion, AnimatePresence } from 'motion/react';
import { 
  Mic, 
  Send, 
  ChevronRight, 
  Award, 
  Target, 
  UserCheck, 
  BookOpen, 
  AlertCircle, 
  Loader2, 
  CheckCircle2,
  ArrowLeft
} from 'lucide-react';
import { 
  SectionCard, 
  SurfaceCard, 
  StatusBadge, 
  PrimaryButton, 
  SecondaryButton,
  TextArea
} from '../components/primitives';
import { api } from '../lib/api';
import toast from 'react-hot-toast';

interface InterviewQuestion {
  id: string;
  question: string;
  rationale: string;
}

interface InterviewEvaluation {
  score: number;
  axes_scores: Record<string, number>;
  feedback: string;
  coaching_advice: string;
}

export const Interview: React.FC = () => {
  const { projectId } = useParams<{ projectId: string }>();
  const navigate = useNavigate();
  
  const [questions, setQuestions] = useState<InterviewQuestion[]>([]);
  const [currentIndex, setCurrentIndex] = useState(0);
  const [loading, setLoading] = useState(true);
  const [answering, setAnswering] = useState(false);
  const [answer, setAnswer] = useState('');
  const [evaluation, setEvaluation] = useState<InterviewEvaluation | null>(null);
  const [finished, setFinished] = useState(false);

  const fetchQuestions = useCallback(async () => {
    if (!projectId) return;
    try {
      setLoading(true);
      const data = await api.post<InterviewQuestion[]>('/api/v1/interview/generate-questions', { project_id: projectId });
      setQuestions(data);
    } catch (err) {
      toast.error('면접 질문을 생성하는 데 실패했습니다.');
      console.error(err);
    } finally {
      setLoading(false);
    }
  }, [projectId]);

  useEffect(() => {
    if (projectId) {
      fetchQuestions();
    }
  }, [projectId, fetchQuestions]);

  const submitAnswer = async () => {
    if (!answer.trim()) {
      toast.error('답변을 입력해주세요.');
      return;
    }
    
    try {
      setAnswering(true);
      const data = await api.post<InterviewEvaluation>('/api/v1/interview/evaluate-answer', {
        question: questions[currentIndex].question,
        answer: answer
      });
      setEvaluation(data);
    } catch (err) {
      toast.error('답변 분석에 실패했습니다.');
      console.error(err);
    } finally {
      setAnswering(false);
    }
  };

  const nextQuestion = () => {
    if (currentIndex < questions.length - 1) {
      setCurrentIndex(prev => prev + 1);
      setAnswer('');
      setEvaluation(null);
    } else {
      setFinished(true);
    }
  };

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-slate-50">
        <div className="flex flex-col items-center gap-4">
          <Loader2 className="h-10 w-10 animate-spin text-[#004aad]" />
          <p className="text-sm font-bold text-slate-500">생기부 기반 면접 질문을 추출하고 있습니다...</p>
        </div>
      </div>
    );
  }

  if (finished) {
    return (
      <div className="mx-auto max-w-2xl px-4 py-12">
        <motion.div initial={{ opacity: 0, scale: 0.95 }} animate={{ opacity: 1, scale: 1 }} className="text-center">
          <div className="mb-6 flex justify-center">
            <div className="flex h-20 w-20 items-center justify-center rounded-full bg-emerald-100 text-emerald-600">
              <CheckCircle2 size={40} />
            </div>
          </div>
          <h1 className="text-3xl font-black text-slate-900">모의 면접 완료!</h1>
          <p className="mt-4 text-lg font-medium text-slate-600">
            총 {questions.length}개의 질문에 대한 답변 연습을 마쳤습니다.
            <br />꾸준한 연습이 합격의 지름길입니다.
          </p>
          <div className="mt-10 flex justify-center gap-3">
            <SecondaryButton onClick={() => navigate(`/app/workshop/${projectId}`)}>워크숍으로 돌아가기</SecondaryButton>
            <PrimaryButton onClick={() => window.location.reload()}>한 번 더 연습하기</PrimaryButton>
          </div>
        </motion.div>
      </div>
    );
  }

  const currentQuestion = questions[currentIndex];

  return (
    <div className="mx-auto max-w-4xl px-4 py-8 sm:py-12">
      <div className="mb-8 flex items-center justify-between">
        <div className="flex items-center gap-4">
          <button 
            onClick={() => navigate(-1)}
            className="flex h-10 w-10 items-center justify-center rounded-full bg-white text-slate-400 shadow-sm ring-1 ring-slate-200 transition-colors hover:text-slate-600"
          >
            <ArrowLeft size={20} />
          </button>
          <div>
            <h1 className="text-2xl font-black text-slate-900">AI 실전 모의 면접</h1>
            <p className="text-sm font-bold text-slate-400">Step {currentIndex + 1} of {questions.length}</p>
          </div>
        </div>
        <StatusBadge status="active">Beta</StatusBadge>
      </div>

      <div className="grid gap-8 lg:grid-cols-12">
        <div className="lg:col-span-12">
          <SectionCard
            eyebrow={`Question ${currentIndex + 1}`}
            title="Interview Simulator"
            description="인공지능 면접관의 질문에 답변해 보세요."
            className="border-none bg-white shadow-2xl ring-1 ring-slate-200/50"
          >
            <div className="mb-8 rounded-[2rem] bg-slate-900 p-8 text-white shadow-xl lg:p-10">
              <div className="mb-6 flex items-center gap-2 text-[#004aad]">
                <Mic size={20} className="animate-pulse" />
                <span className="text-xs font-black uppercase tracking-widest text-[#004aad]">AI Interviewer</span>
              </div>
              <h2 className="text-xl font-black leading-relaxed sm:text-2xl">
                "{currentQuestion?.question}"
              </h2>
              <p className="mt-6 text-sm font-bold text-slate-400 italic">
                Tip: {currentQuestion?.rationale}
              </p>
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
                  <div className="relative">
                    <TextArea
                      value={answer}
                      onChange={(e) => setAnswer(e.target.value)}
                      placeholder="답변을 입력해 주세요. (가급적 구체적으로 작성할수록 정확한 피드백이 가능합니다)"
                      disabled={answering}
                      className="min-h-[200px] bg-slate-50/50 p-6 text-lg font-medium leading-relaxed ring-slate-200 focus:bg-white"
                    />
                  </div>
                  <div className="flex justify-end">
                    <PrimaryButton 
                      onClick={submitAnswer} 
                      disabled={!answer.trim() || answering}
                      className="px-8 py-4"
                    >
                      {answering ? (
                        <>
                          <Loader2 size={18} className="mr-2 animate-spin" />
                          답변 분석 중...
                        </>
                      ) : (
                        <>
                          답변 제출하기 <Send size={18} className="ml-2" />
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
                  <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
                    {Object.entries(evaluation.axes_scores).map(([axis, score]) => (
                      <SurfaceCard key={axis} className="border-none bg-white p-5 shadow-sm ring-1 ring-slate-200/50">
                        <div className="mb-2 flex items-center gap-2">
                          {axis === '구체성' && <Target size={14} className="text-blue-500" />}
                          {axis === '진정성' && <UserCheck size={14} className="text-emerald-500" />}
                          {axis === '학생부 근거 활용' && <BookOpen size={14} className="text-amber-500" />}
                          {axis === '전공 연결성' && <Award size={14} className="text-rose-500" />}
                          <span className="text-[10px] font-black uppercase tracking-widest text-slate-400">{axis}</span>
                        </div>
                        <p className="text-2xl font-black text-slate-900">{score}<span className="text-xs text-slate-300 ml-1">pts</span></p>
                      </SurfaceCard>
                    ))}
                  </div>

                  <SurfaceCard className="border-none bg-[#004aad]/5 p-8 ring-1 ring-[#004aad]/10">
                    <div className="mb-6 flex items-center gap-3">
                      <div className="flex h-10 w-10 items-center justify-center rounded-2xl bg-[#004aad] text-white shadow-lg shadow-[#004aad]/20">
                        <Award size={20} />
                      </div>
                      <div>
                        <h4 className="text-lg font-black text-slate-900">면접관 피드백</h4>
                        <p className="text-xs font-black uppercase tracking-widest text-[#004aad]/60">Expert Evaluation</p>
                      </div>
                    </div>
                    
                    <div className="space-y-6">
                      <div>
                        <p className="mb-2 text-xs font-black uppercase tracking-widest text-slate-400">종합 평가</p>
                        <p className="text-lg font-bold leading-relaxed text-slate-700">{evaluation.feedback}</p>
                      </div>
                      
                      <div className="rounded-2xl bg-white p-6 shadow-sm ring-1 ring-[#004aad]/10">
                        <p className="mb-3 flex items-center gap-2 text-sm font-black text-[#004aad]">
                          <AlertCircle size={16} />
                          합격을 위한 고득점 포인트
                        </p>
                        <p className="text-base font-bold leading-relaxed text-slate-600 italic">
                          "{evaluation.coaching_advice}"
                        </p>
                      </div>
                    </div>
                  </SurfaceCard>

                  <div className="flex justify-center">
                    <PrimaryButton onClick={nextQuestion} className="px-10 py-4 shadow-xl shadow-[#004aad]/20">
                      다음 질문으로 넘어가기 <ChevronRight size={18} className="ml-2" />
                    </PrimaryButton>
                  </div>
                </motion.div>
              )}
            </AnimatePresence>
          </SectionCard>
        </div>
      </div>
    </div>
  );
};
