import React, { useCallback, useState } from 'react';
import { motion, AnimatePresence } from 'motion/react';
import {
  X,
  Search,
  AlertTriangle,
  CheckCircle2,
  Zap,
  Sparkles,
  AlertCircle,
  FileText,
  ShieldCheck,
  TrendingDown,
  TrendingUp,
  Target,
} from 'lucide-react';
import { useDropzone } from 'react-dropzone';
import toast from 'react-hot-toast';
import { api } from '../lib/api';
import {
  DIAGNOSIS_STORAGE_KEY,
  type DiagnosisResultPayload,
  type DiagnosisRunResponse,
  type StoredDiagnosis,
} from '../lib/diagnosis';

interface DiagnosisModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export function DiagnosisModal({ isOpen, onClose }: DiagnosisModalProps) {
  const [step, setStep] = useState(1);
  const [major, setMajor] = useState('');
  const [projectId, setProjectId] = useState<string | null>(null);
  const [diagnosis, setDiagnosis] = useState<DiagnosisResultPayload | null>(null);
  const [isBusy, setIsBusy] = useState(false);
  const [errorMessage, setErrorMessage] = useState('');
  const [uploadedFileName, setUploadedFileName] = useState<string | null>(null);
  const resetState = () => {
    setStep(1);
    setMajor('');
    setProjectId(null);
    setDiagnosis(null);
    setUploadedFileName(null);
    setErrorMessage('');
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

  const pollDiagnosisStatus = async (runId: string, minStartMs: number) => {
    try {
      const res = await api.get<DiagnosisRunResponse>(`/api/v1/diagnosis/${runId}`);
      if (res.status === 'COMPLETED' && res.result_payload) {
        setDiagnosis(res.result_payload);
        
        // Save to cache for roadmap usage
        const storedDiagnosis: StoredDiagnosis = {
          major: major.trim(),
          projectId: projectId ?? undefined,
          diagnosis: res.result_payload,
          savedAt: new Date().toISOString(),
        };
        localStorage.setItem(
          DIAGNOSIS_STORAGE_KEY,
          JSON.stringify(storedDiagnosis),
        );
        
        const elapsed = Date.now() - minStartMs;
        const delay = Math.max(0, 2000 - elapsed);
        setTimeout(() => { setIsBusy(false); setStep(4); }, delay);
      } else if (res.status === 'FAILED') {
        setIsBusy(false);
        setErrorMessage(res.error_message || '진단 중 알 수 없는 오류가 발생했습니다.');
        setStep(5); // Error step
      } else {
        setTimeout(() => pollDiagnosisStatus(runId, minStartMs), 2000);
      }
    } catch (error) {
      setIsBusy(false);
      setErrorMessage('서버와 상태를 확인하는 과정에서 통신 오류가 발생했습니다.');
      setStep(5);
    }
  };

  const runDiagnosis = async (activeProjectId: string) => {
    setStep(3);
    setIsBusy(true);
    const startAt = Date.now();
    try {
      const run = await api.post<DiagnosisRunResponse>(`/api/v1/diagnosis/run`, { project_id: activeProjectId });
      pollDiagnosisStatus(run.id, startAt);
    } catch (error) {
      console.error('Diagnosis trigger error:', error);
      setIsBusy(false);
      setErrorMessage('진단 프로세스를 시작할 수 없습니다. 문서를 먼저 업로드했는지 확인해주세요.');
      setStep(5);
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
        // Note: Using the project-specific upload endpoint to bind to project 
        await api.post(`/api/v1/projects/${projectId}/uploads`, formData, {
          headers: { 'Content-Type': 'multipart/form-data' },
        });
        toast.success('업로드 완료! AI 진단을 시작합니다.', { id: toastId });
        await runDiagnosis(projectId);
      } catch (error) {
        console.error('Upload error:', error);
        toast.error('PDF 업로드에 실패했습니다. 파일 형식을 확인해주세요.', { id: toastId });
        setIsBusy(false);
      }
    },
    [projectId, isBusy],
  );

  const { getRootProps, getInputProps, isDragActive, open } = useDropzone({
    onDrop,
    accept: { 'application/pdf': ['.pdf'] },
    maxFiles: 1,
    multiple: false,
    disabled: isBusy || !projectId,
    noClick: true,
    noKeyboard: true,
    useFsAccessApi: false,
  });

  const handleOpenFileDialog = useCallback(() => {
    if (isBusy || !projectId) return;
    open();
  }, [isBusy, projectId, open]);

  const handleDropzoneKeyDown = useCallback((event: React.KeyboardEvent<HTMLDivElement>) => {
    if (isBusy || !projectId) return;
    if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault();
      open();
    }
  }, [isBusy, projectId, open]);

  const handleStartWorkshop = () => {
    window.location.hash = 'action-blueprint';
    handleClose();
  };

  if (!isOpen) return null;

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
                <div className="mb-6 flex h-16 w-16 items-center justify-center rounded-2xl bg-gradient-to-br from-blue-500 to-indigo-600 shadow-xl shadow-blue-500/20">
                  <Target size={30} className="text-white" />
                </div>
                <h3 className="mb-3 break-keep text-3xl font-extrabold leading-tight text-slate-800">
                  목표 전공을 알려주세요.
                </h3>
                <p className="mb-8 text-lg font-medium text-slate-500">
                  전공을 기준으로 현재 기록과의 '실제 거리'와 '우선 보완점'을 계산해 드립니다.
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
                <h3 className="mb-2 text-2xl font-extrabold text-slate-800">학교생활기록부 PDF 업로드</h3>
                <p className="mb-6 font-medium text-slate-500">
                  목표 전공과 비교할 기준점을 마련합니다.
                </p>

                <div
                  {...getRootProps({
                    onClick: handleOpenFileDialog,
                    onKeyDown: handleDropzoneKeyDown,
                  })}
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
                  <button
                    type="button"
                    onClick={(event) => {
                      event.preventDefault();
                      event.stopPropagation();
                      handleOpenFileDialog();
                    }}
                    disabled={isBusy || !projectId}
                    className="mb-6 inline-flex items-center gap-2 rounded-xl border border-blue-200 bg-white px-4 py-2 text-sm font-bold text-blue-700 shadow-sm transition-colors hover:bg-blue-50 disabled:cursor-not-allowed disabled:opacity-60"
                  >
                    <FileText size={15} />
                    파일 선택
                  </button>

                  <div className="mt-auto flex items-center gap-1.5 rounded-full bg-white/60 px-4 py-2.5 text-center text-xs font-bold text-slate-500">
                    <ShieldCheck size={16} className="shrink-0 text-emerald-500" />
                    업로드 파일은 진단 처리 용도로만 보관 및 암호화됩니다.
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
                  AI가 객관적 관점에서 간극(Gap)을 찾고 있습니다.
                </h3>
                <p className="font-bold text-blue-500">
                  과장된 합격 예측이 아닌, 명확한 다음 액션 플랜을 도출합니다. (최대 1분 소요될 수 있습니다)
                </p>
              </motion.div>
            ) : null}

            {step === 5 ? (
              <motion.div
                key="step5"
                initial={{ opacity: 0, scale: 0.9 }}
                animate={{ opacity: 1, scale: 1 }}
                exit={{ opacity: 0, scale: 1.1 }}
                className="flex h-full flex-col items-center justify-center p-6 text-center"
              >
                <div className="mb-6 flex h-24 w-24 items-center justify-center rounded-full bg-red-100">
                  <AlertCircle size={40} className="text-red-500" />
                </div>
                <h3 className="mb-3 text-2xl font-extrabold text-slate-800">진단 중 오류가 발생했습니다.</h3>
                <p className="mb-8 font-medium text-slate-500">{errorMessage}</p>
                <button
                  onClick={() => projectId ? runDiagnosis(projectId) : setStep(1)}
                  className="rounded-2xl bg-slate-900 px-8 py-4 text-base font-extrabold text-white transition-colors hover:bg-slate-800"
                >
                  {projectId ? '다시 시도하기' : '처음부터 다시 시도'}
                </button>
              </motion.div>
            ) : null}

            {step === 4 && diagnosis ? (
              <motion.div
                key="step4"
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                className="flex h-full flex-col bg-slate-50"
              >
                <div className="hide-scrollbar flex-1 space-y-8 overflow-y-auto p-6 pb-32 sm:p-8">
                  <div className="relative overflow-hidden bg-white p-8 text-center clay-card">
                    <div className="absolute left-0 top-0 h-2 w-full bg-gradient-to-r from-blue-400 to-indigo-500" />
                    
                    <div className="mb-4 inline-flex items-center gap-2 rounded-full border border-slate-200 bg-slate-50 px-4 py-1.5">
                      <Zap size={16} className="text-blue-500" />
                      <span className="text-sm font-extrabold text-slate-600">
                        {major} 목표 대비 학생부 진단
                      </span>
                    </div>

                    <h2 className="text-2xl font-black leading-snug tracking-tight text-slate-800 break-keep sm:text-3xl">
                      "{diagnosis.headline}"
                    </h2>

                    <div className="mt-6 inline-flex flex-wrap items-center justify-center gap-2 rounded-2xl border border-slate-200 bg-slate-50 p-2 sm:gap-4 sm:rounded-full">
                      <div className="flex items-center gap-2 px-3 py-1">
                         <span className="text-xs font-bold text-slate-500">리스크 레벨</span>
                         <span className={`rounded-full px-3 py-1 text-sm font-black ${
                           diagnosis.risk_level === 'danger' ? 'bg-red-100 text-red-700' :
                           diagnosis.risk_level === 'warning' ? 'bg-amber-100 text-amber-700' :
                           'bg-emerald-100 text-emerald-700'
                         }`}>
                           {diagnosis.risk_level === 'danger' ? '위험 수준' :
                            diagnosis.risk_level === 'warning' ? '보완 필수' : '상대적 안정'}
                         </span>
                      </div>
                    </div>
                  </div>

                  <div className="grid grid-cols-1 gap-6 md:grid-cols-2">
                    <div className="flex flex-col rounded-3xl border border-emerald-100 bg-emerald-50/50 p-6 sm:p-8">
                      <div className="mb-4 flex items-center gap-3">
                        <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-emerald-100 text-emerald-600">
                          <TrendingUp size={20} />
                        </div>
                        <h3 className="text-xl font-extrabold text-emerald-900">현재의 확실한 강점</h3>
                      </div>
                      <ul className="flex-1 space-y-3">
                        {diagnosis.strengths.map((str, i) => (
                           <li key={i} className="flex items-start gap-3 rounded-2xl border border-white bg-white/80 p-4 text-sm font-bold leading-relaxed text-emerald-800 shadow-sm backdrop-blur-sm">
                             <CheckCircle2 size={18} className="mt-0.5 shrink-0 text-emerald-500" />
                             <span>{str}</span>
                           </li>
                        ))}
                      </ul>
                    </div>

                    <div className="flex flex-col rounded-3xl border border-red-100 bg-red-50/50 p-6 sm:p-8">
                      <div className="mb-4 flex items-center gap-3">
                        <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-red-100 text-red-600">
                          <TrendingDown size={20} />
                        </div>
                        <h3 className="text-xl font-extrabold text-red-900">치명적인 약점 (Gap)</h3>
                      </div>
                      <ul className="flex-1 space-y-3">
                        {diagnosis.gaps.map((gap, i) => (
                           <li key={i} className="flex items-start gap-3 rounded-2xl border border-white bg-white/80 p-4 text-sm font-bold leading-relaxed text-red-800 shadow-sm backdrop-blur-sm">
                             <AlertTriangle size={18} className="mt-0.5 shrink-0 text-red-500" />
                             <span>{gap}</span>
                           </li>
                        ))}
                      </ul>
                    </div>
                  </div>
                </div>

                <div className="absolute bottom-0 left-0 w-full border-t border-slate-200 bg-white/90 p-6 shadow-[0_-10px_30px_rgba(0,0,0,0.05)] backdrop-blur-md sm:px-8">
                  <div className="mb-4 flex items-start gap-3">
                    <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-blue-500 font-extrabold text-white shadow-md">
                      F
                    </div>
                    <div className="flex-1 rounded-2xl rounded-tl-sm border border-blue-100 bg-blue-50 p-4">
                      <p className="text-sm font-extrabold leading-snug text-blue-900 sm:text-base">
                        <span className="mb-1 block text-xs font-black uppercase tracking-wider text-blue-500">Next Action Goal</span>
                        {diagnosis.recommended_focus}
                      </p>
                    </div>
                  </div>
                  <button
                    onClick={handleStartWorkshop}
                    className="group flex w-full items-center justify-center gap-2 py-4 text-lg font-extrabold clay-btn-primary"
                  >
                    <Zap size={20} className="fill-yellow-300 text-yellow-300 transition-transform group-hover:scale-110" />
                    다음 학기 보완을 위한 워크숍 시작
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
