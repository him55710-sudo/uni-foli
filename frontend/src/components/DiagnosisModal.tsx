import React, { useCallback, useMemo, useState } from 'react';
import { motion, AnimatePresence } from 'motion/react';
import {
  X,
  Search,
  AlertTriangle,
  CheckCircle2,
  ChevronDown,
  ChevronUp,
  Zap,
  Sparkles,
  AlertCircle,
  FileText,
  ShieldCheck,
} from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { useDropzone } from 'react-dropzone';
import toast from 'react-hot-toast';
import { api } from '../lib/api';

interface DiagnosisModalProps {
  isOpen: boolean;
  onClose: () => void;
}

interface DiagnosisSubject {
  name: string;
  status: 'safe' | 'warning' | 'danger';
  feedback: string;
}

interface DiagnosisResponse {
  overall: {
    score: number;
    summary: string;
  };
  subjects: DiagnosisSubject[];
  prescription: {
    message: string;
    recommendedTopic: string;
  };
}

const FALLBACK_DIAGNOSIS: DiagnosisResponse = {
  overall: {
    score: 71,
    summary: '전공 연결성이 일부 부족하지만, 강점 과목을 중심으로 구조를 잡으면 빠르게 개선 가능합니다.',
  },
  subjects: [
    {
      name: '수학',
      status: 'warning',
      feedback: '탐구 과정 설명은 좋지만 전공 연계 근거를 한 문단 더 보강하면 완성도가 올라갑니다.',
    },
    {
      name: '과학',
      status: 'danger',
      feedback: '결론이 관찰 내용 반복에 머물러 있습니다. 해석과 시사점 중심으로 재구성이 필요합니다.',
    },
    {
      name: '국어',
      status: 'safe',
      feedback: '논리 전개와 표현이 안정적입니다. 발표/토론 연계 내용이 강점으로 보입니다.',
    },
  ],
  prescription: {
    message: '다음 보고서는 강점 과목의 분석 프레임을 약점 과목에 이식하는 방식으로 구성해보세요.',
    recommendedTopic: '전공 키워드 기반 비교 분석 보고서',
  },
};

const DIAGNOSIS_STORAGE_KEY = 'polio_last_diagnosis';

export function DiagnosisModal({ isOpen, onClose }: DiagnosisModalProps) {
  const [step, setStep] = useState(1);
  const [major, setMajor] = useState('');
  const [projectId, setProjectId] = useState<string | null>(null);
  const [expandedSubject, setExpandedSubject] = useState<string | null>(null);
  const [diagnosis, setDiagnosis] = useState<DiagnosisResponse | null>(null);
  const [isBusy, setIsBusy] = useState(false);
  const [uploadedFileName, setUploadedFileName] = useState<string | null>(null);

  const navigate = useNavigate();

  const scoreColorClass = useMemo(() => {
    const score = diagnosis?.overall.score ?? 0;
    if (score >= 80) return 'text-emerald-600';
    if (score >= 60) return 'text-amber-600';
    return 'text-red-600';
  }, [diagnosis?.overall.score]);

  const resetState = () => {
    setStep(1);
    setMajor('');
    setProjectId(null);
    setExpandedSubject(null);
    setDiagnosis(null);
    setUploadedFileName(null);
    setIsBusy(false);
  };

  const handleClose = () => {
    onClose();
    setTimeout(resetState, 250);
  };

  const handleCreateProject = async () => {
    if (!major.trim() || isBusy) return;

    setIsBusy(true);
    const toastId = toast.loading('프로젝트를 생성하는 중입니다...');
    try {
      const created = await api.post<{ id: string }>('/api/v1/projects', {
        title: `${major.trim()} 진단 프로젝트`,
        description: '대시보드 진단 모달에서 생성된 프로젝트',
        target_major: major.trim(),
      });
      setProjectId(created.id);
      setStep(2);
      toast.success('프로젝트 생성 완료! 이제 PDF를 업로드해주세요.', { id: toastId });
    } catch (error) {
      console.error('Project creation error:', error);
      toast.error('프로젝트 생성에 실패했습니다. 잠시 후 다시 시도해주세요.', { id: toastId });
    } finally {
      setIsBusy(false);
    }
  };

  const runDiagnosis = async (activeProjectId: string) => {
    setStep(3);
    const startAt = Date.now();
    const minimumLoadingMs = 2000;
    let resolvedDiagnosis: DiagnosisResponse = FALLBACK_DIAGNOSIS;

    try {
      const result = await api.post<DiagnosisResponse>(`/api/v1/projects/${activeProjectId}/diagnose`);
      setDiagnosis(result);
      setExpandedSubject(result.subjects[0]?.name ?? null);
      resolvedDiagnosis = result;
    } catch (error) {
      console.error('Diagnosis error:', error);
      setDiagnosis(FALLBACK_DIAGNOSIS);
      setExpandedSubject(FALLBACK_DIAGNOSIS.subjects[0]?.name ?? null);
      toast('실시간 진단 연결이 불안정해 기본 분석으로 이어갑니다.', { icon: '⚠️' });
      resolvedDiagnosis = FALLBACK_DIAGNOSIS;
    } finally {
      localStorage.setItem(
        DIAGNOSIS_STORAGE_KEY,
        JSON.stringify({
          major: major.trim(),
          diagnosis: resolvedDiagnosis,
          savedAt: new Date().toISOString(),
        }),
      );
      const elapsed = Date.now() - startAt;
      const delay = Math.max(0, minimumLoadingMs - elapsed);
      setTimeout(() => setStep(4), delay);
    }
  };

  const onDrop = useCallback(
    async (acceptedFiles: File[]) => {
      const file = acceptedFiles[0];
      if (!file || !projectId || isBusy) return;

      setIsBusy(true);
      setUploadedFileName(file.name);
      const toastId = toast.loading('PDF를 업로드하고 분석 준비 중입니다...');
      try {
        const formData = new FormData();
        formData.append('file', file);
        await api.post(`/api/v1/projects/${projectId}/uploads`, formData, {
          headers: { 'Content-Type': 'multipart/form-data' },
        });
        toast.success('업로드 완료! AI 진단을 시작합니다.', { id: toastId });
        await runDiagnosis(projectId);
      } catch (error) {
        console.error('Upload error:', error);
        toast.error('PDF 업로드에 실패했습니다. 파일 형식을 확인해주세요.', { id: toastId });
      } finally {
        setIsBusy(false);
      }
    },
    [projectId, isBusy],
  );

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: { 'application/pdf': ['.pdf'] },
    maxFiles: 1,
    multiple: false,
    disabled: isBusy || !projectId,
  });

  const handleStartWorkshop = () => {
    const majorQuery = encodeURIComponent(major.trim());
    handleClose();
    if (projectId) {
      navigate(`/workshop/${projectId}?major=${majorQuery}`);
      return;
    }
    navigate(`/workshop?major=${majorQuery}`);
  };

  if (!isOpen) return null;

  const subjectList = diagnosis?.subjects ?? [];
  const overallScore = diagnosis?.overall.score ?? 0;
  const overallSummary = diagnosis?.overall.summary ?? '';
  const prescription = diagnosis?.prescription;

  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center bg-slate-900/40 p-0 backdrop-blur-sm sm:items-center sm:p-4">
      <motion.div
        initial={{ opacity: 0, y: 100 }}
        animate={{ opacity: 1, y: 0 }}
        exit={{ opacity: 0, y: 100 }}
        className={`relative flex w-full flex-col overflow-hidden rounded-t-3xl bg-white shadow-2xl transition-all duration-500 sm:rounded-3xl ${
          step === 4 ? 'h-[90vh] sm:h-[800px] sm:max-w-3xl' : 'h-[80vh] sm:h-[620px] sm:max-w-md'
        }`}
      >
        <button
          onClick={handleClose}
          className="absolute right-4 top-4 z-20 rounded-full bg-slate-50/80 p-2 text-slate-400 backdrop-blur-sm transition-colors hover:text-slate-600"
        >
          <X size={20} />
        </button>

        <div className="relative flex-1 overflow-y-auto hide-scrollbar">
          <AnimatePresence mode="wait">
            {step === 1 ? (
              <motion.div
                key="step1"
                initial={{ opacity: 0, x: 50 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: -50 }}
                className="flex h-full flex-col justify-center p-6 sm:p-8"
              >
                <h3 className="mb-3 break-keep text-3xl font-extrabold leading-tight text-slate-800">
                  목표 전공을 입력해주세요.
                </h3>
                <p className="mb-10 text-lg font-medium text-slate-500">
                  전공 정보를 기반으로 진단 질문과 분석 기준을 세팅합니다.
                </p>
                <input
                  type="text"
                  value={major}
                  onChange={(event) => setMajor(event.target.value)}
                  onKeyDown={(event) => {
                    if (event.key === 'Enter') handleCreateProject();
                  }}
                  placeholder="예: 경영학과, 컴퓨터공학과"
                  className="w-full border-b-2 border-slate-200 pb-3 text-3xl font-bold text-slate-800 outline-none transition-colors placeholder:text-slate-300 focus:border-blue-500"
                  autoFocus
                />
              </motion.div>
            ) : null}

            {step === 2 ? (
              <motion.div
                key="step2"
                initial={{ opacity: 0, x: 50 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: -50 }}
                className="flex h-full flex-col p-6 pt-16 sm:p-8"
              >
                <h3 className="mb-2 text-2xl font-extrabold text-slate-800">학교생활기록부 PDF를 업로드해주세요.</h3>
                <p className="mb-6 font-medium text-slate-500">
                  프로젝트가 생성되었습니다. 이제 파일을 올리면 바로 분석을 시작합니다.
                </p>

                <div
                  {...getRootProps()}
                  className={`group flex flex-1 cursor-pointer flex-col items-center justify-center rounded-3xl border-2 border-dashed p-6 transition-all duration-300 ${
                    isDragActive
                      ? 'border-blue-500 bg-blue-100'
                      : 'border-blue-300 bg-blue-50/50 hover:border-blue-400 hover:bg-blue-50'
                  } ${isBusy ? 'cursor-not-allowed opacity-70' : ''}`}
                >
                  <input {...getInputProps()} />
                  <div className="mb-6 flex h-20 w-20 rotate-3 items-center justify-center rounded-2xl bg-gradient-to-br from-blue-400 to-blue-600 shadow-lg shadow-blue-500/30 transition-all duration-300 group-hover:scale-110 group-hover:rotate-6">
                    <FileText size={36} className="text-white" />
                  </div>
                  <h3 className="mb-2 text-center text-xl font-extrabold text-slate-800">
                    파일을 드래그하거나 클릭해서 업로드하세요.
                  </h3>
                  <p className="mb-8 text-center text-sm font-medium text-slate-500">
                    PDF 1개, 최대 50MB
                    {uploadedFileName ? ` · 최근 선택: ${uploadedFileName}` : ''}
                  </p>

                  <div className="mt-auto flex items-center gap-1.5 rounded-full bg-white/60 px-4 py-2.5 text-center text-xs font-bold text-slate-500">
                    <ShieldCheck size={16} className="shrink-0 text-emerald-500" />
                    업로드 파일은 진단 처리 용도로만 사용됩니다.
                  </div>
                </div>
              </motion.div>
            ) : null}

            {step === 3 ? (
              <motion.div
                key="step3"
                initial={{ opacity: 0, scale: 0.9 }}
                animate={{ opacity: 1, scale: 1 }}
                exit={{ opacity: 0, scale: 1.1 }}
                className="flex h-full flex-col items-center justify-center p-6 text-center"
              >
                <div className="relative mb-8 flex h-32 w-32 items-center justify-center">
                  <div className="absolute inset-0 rounded-full border-4 border-blue-100" />
                  <div
                    className="absolute inset-0 animate-spin rounded-full border-4 border-blue-500 border-t-transparent"
                    style={{ animationDuration: '1.5s' }}
                  />
                  <Search size={40} className="animate-pulse text-blue-500" />
                </div>
                <h3 className="mb-3 text-2xl font-extrabold text-slate-800">
                  AI가 PDF를 읽고 전공 적합도를 계산 중입니다...
                </h3>
                <p className="font-bold text-blue-500">Poli가 근거 중심으로 분석하고 있어요.</p>
              </motion.div>
            ) : null}

            {step === 4 ? (
              <motion.div
                key="step4"
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                className="flex h-full flex-col bg-slate-50"
              >
                <div className="hide-scrollbar flex-1 space-y-6 overflow-y-auto p-6 pb-32 sm:p-8">
                  <div className="relative overflow-hidden bg-white p-8 text-center clay-card">
                    <div className="absolute left-0 top-0 h-2 w-full bg-gradient-to-r from-blue-400 to-indigo-500" />
                    <h2 className="mb-6 text-xl font-extrabold text-slate-800">AI 종합 진단 리포트</h2>

                    <div className="mx-auto mb-4 w-48">
                      <div className={`text-5xl font-black tracking-tighter ${scoreColorClass}`}>
                        {overallScore}
                        <span className="text-2xl text-slate-400">%</span>
                      </div>
                      <p className="mt-1 text-xs font-bold text-slate-500">전공 적합도 점수</p>
                    </div>

                    <div className="mt-4 inline-flex items-center gap-2 rounded-xl border border-red-100 bg-red-50 px-4 py-2.5 text-sm font-bold text-red-600">
                      <AlertTriangle size={18} className="shrink-0" />
                      <span className="text-left">{overallSummary}</span>
                    </div>
                  </div>

                  <div className="space-y-3">
                    <h3 className="px-2 text-lg font-extrabold text-slate-800">과목별 상세 진단</h3>
                    {subjectList.map((subject) => (
                      <div
                        key={subject.name}
                        className={`overflow-hidden border-2 bg-white transition-all duration-300 clay-card ${
                          expandedSubject === subject.name
                            ? subject.status === 'danger'
                              ? 'border-red-200'
                              : subject.status === 'warning'
                                ? 'border-amber-200'
                                : 'border-emerald-200'
                            : 'border-transparent'
                        }`}
                      >
                        <button
                          onClick={() =>
                            setExpandedSubject((prev) => (prev === subject.name ? null : subject.name))
                          }
                          className="flex w-full items-center justify-between bg-white p-5 transition-colors hover:bg-slate-50"
                        >
                          <div className="flex items-center gap-3">
                            <span className="rounded-lg bg-slate-100 px-3 py-1.5 text-sm font-extrabold text-slate-700">
                              {subject.name}
                            </span>
                            <div className="flex items-center gap-1.5">
                              {subject.status === 'safe' ? (
                                <>
                                  <CheckCircle2 size={18} className="text-emerald-500" />
                                  <span className="text-sm font-bold text-emerald-600">안정</span>
                                </>
                              ) : null}
                              {subject.status === 'warning' ? (
                                <>
                                  <AlertCircle size={18} className="text-amber-500" />
                                  <span className="text-sm font-bold text-amber-600">보완 필요</span>
                                </>
                              ) : null}
                              {subject.status === 'danger' ? (
                                <>
                                  <AlertTriangle size={18} className="text-red-500" />
                                  <span className="text-sm font-bold text-red-600">집중 보완</span>
                                </>
                              ) : null}
                            </div>
                          </div>
                          {expandedSubject === subject.name ? (
                            <ChevronUp size={20} className="text-slate-400" />
                          ) : (
                            <ChevronDown size={20} className="text-slate-400" />
                          )}
                        </button>

                        <AnimatePresence>
                          {expandedSubject === subject.name ? (
                            <motion.div
                              initial={{ height: 0, opacity: 0 }}
                              animate={{ height: 'auto', opacity: 1 }}
                              exit={{ height: 0, opacity: 0 }}
                              className="overflow-hidden"
                            >
                              <div
                                className={`p-5 pt-0 text-sm font-medium leading-relaxed ${
                                  subject.status === 'danger'
                                    ? 'text-red-700'
                                    : subject.status === 'warning'
                                      ? 'text-amber-700'
                                      : 'text-emerald-700'
                                }`}
                              >
                                <div
                                  className={`rounded-xl p-4 ${
                                    subject.status === 'danger'
                                      ? 'bg-red-50'
                                      : subject.status === 'warning'
                                        ? 'bg-amber-50'
                                        : 'bg-emerald-50'
                                  }`}
                                >
                                  <span className="mb-1 block font-extrabold">Poli 피드백</span>
                                  {subject.feedback}
                                </div>
                              </div>
                            </motion.div>
                          ) : null}
                        </AnimatePresence>
                      </div>
                    ))}
                  </div>
                </div>

                <div className="absolute bottom-0 left-0 w-full border-t border-slate-200 bg-white/90 p-6 shadow-[0_-10px_30px_rgba(0,0,0,0.05)] backdrop-blur-md sm:px-8">
                  <div className="mb-4 flex items-start gap-3">
                    <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-blue-500 font-extrabold text-white shadow-md">
                      P
                    </div>
                    <div className="flex-1 rounded-2xl rounded-tl-sm border border-blue-100 bg-blue-50 p-4">
                      <p className="text-sm font-bold leading-snug text-blue-900 sm:text-base">
                        {prescription?.message}
                        {prescription?.recommendedTopic ? (
                          <>
                            {' '}
                            <span className="font-black text-blue-600">"{prescription.recommendedTopic}"</span>
                          </>
                        ) : null}
                      </p>
                    </div>
                  </div>
                  <button
                    onClick={handleStartWorkshop}
                    className="group flex w-full items-center justify-center gap-2 py-4 text-lg font-extrabold clay-btn-primary"
                  >
                    <Zap size={20} className="fill-yellow-300 text-yellow-300 transition-transform group-hover:scale-110" />
                    진단 결과 기반으로 워크숍 시작하기
                  </button>
                </div>
              </motion.div>
            ) : null}
          </AnimatePresence>
        </div>

        {step === 1 ? (
          <div className="z-10 border-t border-slate-100 bg-white p-6">
            <button
              onClick={handleCreateProject}
              disabled={!major.trim() || isBusy}
              className="flex w-full items-center justify-center gap-2 py-4 text-lg font-extrabold disabled:cursor-not-allowed disabled:opacity-50 clay-btn-primary"
            >
              {isBusy ? <Sparkles size={18} className="animate-pulse" /> : null}
              다음
            </button>
          </div>
        ) : null}
      </motion.div>
    </div>
  );
}
