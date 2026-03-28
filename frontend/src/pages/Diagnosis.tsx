import React, { useCallback, useEffect, useState } from 'react';
import { motion, AnimatePresence } from 'motion/react';
import { 
  Target, 
  FileUp, 
  Sparkles, 
  CheckCircle2, 
  AlertTriangle, 
  ArrowRight, 
  Loader2, 
  Target as TargetIcon,
  Plus,
  Trash2,
  ChevronRight,
  ChevronDown,
  ChevronUp
} from 'lucide-react';
import { useDropzone } from 'react-dropzone';
import toast from 'react-hot-toast';
import { useNavigate } from 'react-router-dom';
import { AsyncJobStatusCard } from '../components/AsyncJobStatusCard';
import { useAuthStore } from '../store/authStore';
import { useOnboardingStore } from '../store/onboardingStore';
import { api } from '../lib/api';
import { DiagnosisEvidencePanel } from '../components/DiagnosisEvidencePanel';
import {
  type AsyncJobRead,
  type DiagnosisRunResponse,
  type DiagnosisResultPayload,
  DIAGNOSIS_STORAGE_KEY,
  formatRiskLevel,
  getDiagnosisFailureMessage,
  isDiagnosisComplete,
  isDiagnosisFailed,
  mergeDiagnosisPayload,
} from '../lib/diagnosis';
import { searchUniversities, searchMajors } from '../lib/educationCatalog';
import { CatalogAutocompleteInput } from '../components/CatalogAutocompleteInput';

type DiagnosisStep = 'GOALS' | 'UPLOAD' | 'ANALYSING' | 'RESULT' | 'FAILED';

export function Diagnosis() {
  const navigate = useNavigate();
  const { user } = useAuthStore();
  const { goals, setGoals, submitGoals } = useOnboardingStore();
  
  const [step, setStep] = useState<DiagnosisStep>('GOALS');
  const [goalList, setGoalList] = useState<{id: string, university: string, major: string}[]>([]);
  const [isEditingGoals, setIsEditingGoals] = useState(false);
  const [univInput, setUnivInput] = useState('');
  const [currentUniv, setCurrentUniv] = useState('');
  const [currentMajor, setCurrentMajor] = useState('');
  
  const [projectId, setProjectId] = useState<string | null>(null);
  const [isUploading, setIsUploading] = useState(false);
  const [diagnosisResult, setDiagnosisResult] = useState<DiagnosisResultPayload | null>(null);
  const [diagnosisRunId, setDiagnosisRunId] = useState<string | null>(null);
  const [diagnosisRun, setDiagnosisRun] = useState<DiagnosisRunResponse | null>(null);
  const [diagnosisJob, setDiagnosisJob] = useState<AsyncJobRead | null>(null);
  const [diagnosisError, setDiagnosisError] = useState<string | null>(null);
  const [isRetryingDiagnosis, setIsRetryingDiagnosis] = useState(false);

  // Initialize goalList from user profile
  useEffect(() => {
    if (!user) return;
    const initialList: { id: string; university: string; major: string }[] = [];
    if (user.target_university && user.target_major) {
      initialList.push({ id: 'main', university: user.target_university, major: user.target_major });
    }
    user.interest_universities?.forEach((i, idx) => {
      const match = i.match(/^(.+)\s\((.+)\)$/);
      if (match) initialList.push({ id: `int-${idx}`, university: match[1], major: match[2] });
      else initialList.push({ id: `int-${idx}`, university: i, major: '' });
    });
    setGoalList(initialList.slice(0, 6));
  }, [user]);

  // Goal Management Logic
  const handleAddGoal = () => {
    if (!currentUniv || !currentMajor || goalList.length >= 6) return;
    setGoalList(prev => [...prev, { id: crypto.randomUUID(), university: currentUniv, major: currentMajor }]);
    setCurrentUniv('');
    setCurrentMajor('');
    setUnivInput('');
  };

  const removeGoal = (id: string) => setGoalList(prev => prev.filter(g => g.id !== id));
  
  const saveGoals = async () => {
    if (goalList.length === 0) {
      toast.error('목표 대학을 하나 이상 설정해주세요.');
      return;
    }
    const main = goalList[0];
    const others = goalList.slice(1).map(g => `${g.university} (${g.major})`);
    
    setGoals({
      target_university: main.university,
      target_major: main.major,
      interest_universities: others,
      admission_type: goals.admission_type || '학생부종합'
    });
    
    const success = await submitGoals();
    if (success) {
      setIsEditingGoals(false);
      toast.success('목표 대학이 업데이트되었습니다.');
    }
  };

  const completeDiagnosis = useCallback((run: DiagnosisRunResponse) => {
    const payload = mergeDiagnosisPayload(run);
    if (!payload) return false;

    setDiagnosisRun(run);
    setDiagnosisResult(payload);
    setDiagnosisError(null);
    setStep('RESULT');
    setDiagnosisRunId(null);
    setIsUploading(false);

    const primaryMajor = goalList[0]?.major || currentMajor || '';
    localStorage.setItem(
      DIAGNOSIS_STORAGE_KEY,
      JSON.stringify({
        major: primaryMajor,
        projectId: run.project_id,
        savedAt: new Date().toISOString(),
        diagnosis: {
          headline: payload.headline,
          strengths: payload.strengths,
          gaps: payload.gaps,
          risk_level: payload.risk_level,
          recommended_focus: payload.recommended_focus,
        },
      }),
    );
    return true;
  }, [currentMajor, goalList]);

  const syncDiagnosisRun = useCallback(async (runId: string) => {
    const run = await api.get<DiagnosisRunResponse>(`/api/v1/diagnosis/${runId}`);
    setDiagnosisRun(run);

    let job: AsyncJobRead | null = null;
    if (run.async_job_id) {
      try {
        job = await api.get<AsyncJobRead>(`/api/v1/jobs/${run.async_job_id}`);
      } catch {
        job = null;
      }
    }
    setDiagnosisJob(job);

    if (isDiagnosisComplete(run)) {
      completeDiagnosis(run);
      return true;
    }

    if (isDiagnosisFailed(run, job)) {
      setDiagnosisError(getDiagnosisFailureMessage(run, job));
      setStep('FAILED');
      setDiagnosisRunId(null);
      setIsUploading(false);
      return true;
    }

    return false;
  }, [completeDiagnosis]);

  useEffect(() => {
    if (!diagnosisRunId) return undefined;

    let cancelled = false;
    let timeoutId: number | undefined;

    const poll = async () => {
      try {
        const isTerminal = await syncDiagnosisRun(diagnosisRunId);
        if (!cancelled && !isTerminal) {
          timeoutId = window.setTimeout(poll, 2000);
        }
      } catch (error) {
        console.error('Polling failed', error);
        if (!cancelled) {
          setDiagnosisError('The diagnosis status could not be refreshed. Please try again.');
          setStep('FAILED');
          setDiagnosisRunId(null);
          setIsUploading(false);
        }
      }
    };

    void poll();

    return () => {
      cancelled = true;
      if (timeoutId) window.clearTimeout(timeoutId);
    };
  }, [diagnosisRunId, syncDiagnosisRun]);

  const retryDiagnosis = useCallback(async () => {
    if (!diagnosisRun?.async_job_id || isRetryingDiagnosis) return;

    setIsRetryingDiagnosis(true);
    try {
      const retried = await api.post<AsyncJobRead>(`/api/v1/jobs/${diagnosisRun.async_job_id}/retry`);
      setDiagnosisJob(retried);
      setDiagnosisError(null);
      setStep('ANALYSING');
      setDiagnosisRunId(diagnosisRun.id);
      toast.success('Diagnosis retry queued. We will keep polling for updates.');
    } catch (error) {
      console.error('Diagnosis retry failed:', error);
      toast.error('The diagnosis retry could not be started.');
    } finally {
      setIsRetryingDiagnosis(false);
    }
  }, [diagnosisRun, isRetryingDiagnosis]);

  // PDF Upload Logic
  const onDrop = useCallback(async (acceptedFiles: File[]) => {
    const file = acceptedFiles[0];
    if (!file) return;

    setIsUploading(true);
    const loadingId = toast.loading('생기부 PDF를 분석 준비 중...');

    try {
      const formData = new FormData();
      formData.append('file', file);
      const mainGoal = goalList[0];
      if (mainGoal) {
        formData.append('target_major', mainGoal.major);
        formData.append('title', `${mainGoal.university} ${mainGoal.major} 진단`);
      }

      // 1. Upload
      const uploadRes = await api.post<any>('/api/v1/documents/upload', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });
      const pid = uploadRes.project_id;
      const docId = uploadRes.id;
      setProjectId(pid);

      // 2. Parse (Wait for it)
      await api.post(`/api/v1/documents/${docId}/parse`);
      
      // We'll move to ANALYSING step and start polling or wait a bit
      setStep('ANALYSING');
      
      // 3. Trigger Diagnosis
      const diagRes = await api.post<DiagnosisRunResponse>('/api/v1/diagnosis/run', { project_id: pid });
      setDiagnosisRun(diagRes);
      setDiagnosisJob(null);
      setDiagnosisResult(null);
      setDiagnosisError(null);
      setDiagnosisRunId(diagRes.id);
      toast.success('생기부 업로드 및 파싱 완료. AI 진단을 시작합니다.', { id: loadingId });
    } catch (error) {
      console.error('Diagnosis flow failed:', error);
      toast.error('오류가 발생했습니다. 다시 시도해주세요.', { id: loadingId });
      setIsUploading(false);
    }
  }, [goalList]);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: { 'application/pdf': ['.pdf'] },
    multiple: false,
    disabled: isUploading,
  });

  const evidenceCitations = diagnosisResult?.citations ?? diagnosisRun?.citations ?? [];
  const reviewRequired = diagnosisResult?.review_required ?? diagnosisRun?.review_required ?? false;
  const responseTraceId = diagnosisResult?.response_trace_id ?? diagnosisRun?.response_trace_id ?? null;

  return (
    <div className="mx-auto max-w-4xl py-10 px-4">
      {/* Header */}
      <div className="mb-12 text-center">
        <h1 className="text-4xl font-black text-slate-900 mb-4">
          {step === 'GOALS' && '나의 목표 대학 확인'}
          {step === 'UPLOAD' && '생기부 PDF 업로드'}
          {step === 'ANALYSING' && 'AI 심층 진단 중'}
          {step === 'RESULT' && 'Uni Folia AI 진단지'}
          {step === 'FAILED' && '진단 상태 확인'}
        </h1>
        <p className="text-slate-500 font-bold text-lg">
          {step === 'GOALS' && '진단의 기준이 되는 목표 대학과 학과를 확인해주세요.'}
          {step === 'UPLOAD' && '분석할 학생부 PDF 파일을 선택해주세요.'}
          {step === 'ANALYSING' && '생기부의 내용과 목표 대학의 인재상을 매칭하고 있습니다...'}
          {step === 'RESULT' && '나의 생기부 경쟁력과 향후 탐구 방향을 확인하세요.'}
          {step === 'FAILED' && '실패 이유를 확인하고 같은 진단 작업을 안전하게 다시 시도할 수 있습니다.'}
        </p>
      </div>

      {/* Main Content Area */}
      <AnimatePresence mode="wait">
        {step === 'GOALS' && (
          <motion.div
            key="goals"
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            exit={{ opacity: 0, scale: 0.95 }}
            className="space-y-8"
          >
            <div className="bg-white rounded-[40px] border border-slate-100 p-8 shadow-xl shadow-slate-200/50">
              <div className="flex items-center justify-between mb-8">
                <div className="flex items-center gap-3">
                  <div className="h-12 w-12 bg-blue-50 text-blue-600 flex items-center justify-center rounded-2xl">
                    <TargetIcon size={24} />
                  </div>
                  <div>
                    <h2 className="text-xl font-black text-slate-800">목표 대학 리스트</h2>
                    <p className="text-sm font-medium text-slate-400">가장 상단에 위치한 대학이 1지망(기준)이 됩니다.</p>
                  </div>
                </div>
                {!isEditingGoals && (
                  <button 
                    data-testid="diagnosis-edit-goals"
                    onClick={() => setIsEditingGoals(true)}
                    className="text-sm font-black text-blue-600 hover:text-blue-700 bg-blue-50 px-4 py-2 rounded-xl transition-colors"
                  >
                    수정하기
                  </button>
                )}
              </div>

              {isEditingGoals ? (
                <div className="space-y-6">
                  {/* Goal Editor */}
                  <div className="grid md:grid-cols-2 gap-6">
                    <div className="space-y-4">
                      <div className="p-6 bg-slate-50 border border-slate-100 rounded-[32px] space-y-4">
                         <div className="relative">
                           <label className="text-xs font-black text-slate-400 mb-2 block uppercase">대학 검색</label>
                           <input 
                              data-testid="diagnosis-university-search"
                               type="text" 
                               value={univInput} 
                               onChange={e => setUnivInput(e.target.value)} 
                               placeholder="대학명 입력..." 
                               className="w-full p-4 bg-white border-2 border-slate-100 rounded-xl font-bold outline-none focus:border-blue-500" 
                            />
                            {univInput && (
                               <div className="absolute top-full left-0 right-0 z-10 mt-1 max-h-40 overflow-auto bg-white border border-slate-100 rounded-xl shadow-xl">
                                 {searchUniversities(univInput, { excludeNames: goalList.map(g => g.university) }).map((s, index) => (
                                   <button data-testid={`diagnosis-university-option-${index}`} key={s.label} onClick={() => { setCurrentUniv(s.label); setUnivInput(''); }} className="w-full text-left p-3 hover:bg-slate-50 text-sm font-bold border-b border-slate-50 last:border-0">{s.label}</button>
                                 ))}
                               </div>
                            )}
                         </div>

                         {currentUniv && (
                           <div className="space-y-4 pt-2">
                              <div className="p-3 bg-blue-50 rounded-xl border border-blue-100 flex items-center justify-between">
                                 <span className="text-sm font-black text-blue-600">{currentUniv}</span>
                                 <button onClick={() => setCurrentUniv('')} className="text-slate-400"><Trash2 size={16}/></button>
                              </div>
                              <CatalogAutocompleteInput 
                                label="전공 선택" 
                               value={currentMajor} 
                               onChange={setCurrentMajor} 
                               placeholder="전공명 입력..." 
                               suggestions={searchMajors(currentMajor, currentUniv, 20)} 
                               onSelect={s => setCurrentMajor(s.label)} 
                               inputTestId="diagnosis-major-search"
                               suggestionTestIdPrefix="diagnosis-major-option"
                              />
                              <button data-testid="diagnosis-add-goal" onClick={handleAddGoal} disabled={!currentUniv || currentMajor.length < 2 || goalList.length >= 6} className="w-full py-3 bg-slate-900 text-white rounded-xl font-black text-sm flex items-center justify-center gap-2">
                                 <Plus size={16} /> 대학 추가하기
                              </button>
                           </div>
                         )}
                      </div>
                    </div>

                    <div className="space-y-3">
                      {goalList.map((g, idx) => (
                        <div key={g.id} className="flex items-center gap-4 p-4 bg-white border border-slate-100 rounded-2xl shadow-sm">
                          <span className="text-blue-500 font-black italic">#{idx+1}</span>
                          <div className="flex-1">
                            <p className="text-sm font-black text-slate-800">{g.university}</p>
                            <p className="text-[11px] font-bold text-slate-500">{g.major}</p>
                          </div>
                          <button onClick={() => removeGoal(g.id)} className="text-slate-300 hover:text-red-500 transition-colors">
                            <Trash2 size={18} />
                          </button>
                        </div>
                      ))}
                    </div>
                  </div>
                  <div className="flex gap-4 pt-6">
                    <button onClick={() => { setIsEditingGoals(false); window.location.reload(); }} className="flex-1 py-4 bg-slate-100 text-slate-500 rounded-2xl font-black">취소</button>
                    <button data-testid="diagnosis-save-goals" onClick={saveGoals} className="flex-1 py-4 bg-blue-600 text-white rounded-2xl font-black shadow-lg shadow-blue-500/20">저장 완료</button>
                  </div>
                </div>
              ) : (
                <div className="grid sm:grid-cols-2 md:grid-cols-3 gap-4">
                  {goalList.map((g, idx) => (
                    <div key={g.id} className={`p-6 rounded-[24px] border transition-all ${idx === 0 ? 'bg-blue-600 border-blue-500 text-white shadow-xl shadow-blue-500/20' : 'bg-slate-50 border-slate-100 text-slate-700'}`}>
                      <span className={`text-[10px] font-black uppercase tracking-widest ${idx === 0 ? 'text-blue-100' : 'text-slate-400'}`}>
                        {idx === 0 ? 'Main Goal' : `Pick #${idx + 1}`}
                      </span>
                      <p className="text-lg font-black mt-1 leading-tight">{g.university}</p>
                      <p className={`text-xs font-bold mt-1 ${idx === 0 ? 'text-blue-200' : 'text-slate-400'}`}>{g.major}</p>
                    </div>
                  ))}
                  {goalList.length === 0 && (
                    <div className="col-span-full py-12 text-center border-2 border-dashed rounded-[32px] text-slate-300 font-bold">
                      설정된 목표 대학이 없습니다.
                    </div>
                  )}
                </div>
              )}
            </div>

            {!isEditingGoals && (
              <div className="flex justify-center">
                <button 
                  data-testid="diagnosis-goals-continue"
                  onClick={() => setStep('UPLOAD')}
                  disabled={goalList.length === 0}
                  className="px-12 py-5 bg-slate-900 text-white rounded-[24px] font-black text-xl flex items-center gap-3 hover:bg-black transition-all shadow-2xl disabled:opacity-50"
                >
                  확인 완료, 생기부 넣기 <ArrowRight />
                </button>
              </div>
            )}
          </motion.div>
        )}

        {step === 'UPLOAD' && (
          <motion.div
            key="upload"
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -20 }}
            className="space-y-8"
          >
            <div 
              {...getRootProps()} 
              className={`cursor-pointer rounded-[48px] border-4 border-dashed p-16 text-center transition-all ${
                isDragActive 
                ? 'border-blue-400 bg-blue-50' 
                : 'border-slate-200 bg-white hover:border-blue-200 hover:bg-slate-50'
              } ${isUploading ? 'opacity-50 pointer-events-none' : ''}`}
            >
              <input data-testid="diagnosis-upload-input" {...getInputProps()} />
              <div className="flex flex-col items-center gap-6">
                <div className="h-24 w-24 bg-gradient-to-br from-blue-500 to-indigo-600 text-white flex items-center justify-center rounded-[32px] shadow-2xl shadow-blue-500/30">
                  {isUploading ? <Loader2 size={40} className="animate-spin" /> : <FileUp size={40} />}
                </div>
                <div>
                  <h2 className="text-2xl font-black text-slate-800">생활기록부 PDF 업로드</h2>
                  <p className="mt-2 text-slate-500 font-bold max-w-sm">
                    업로드된 파일은 AI 분석 후 진단서를 작성하는데 사용되며, 개인정보는 안전하게 마스킹 처리됩니다.
                  </p>
                </div>
                <div className="px-6 py-2.5 bg-slate-100 rounded-full text-xs font-black text-slate-400 uppercase tracking-widest">
                  PDF Format • Max 50MB
                </div>
              </div>
            </div>
          </motion.div>
        )}

        {step === 'ANALYSING' && (
          <motion.div
            key="analysing"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            className="space-y-8 py-12"
          >
            <div className="flex flex-col items-center justify-center space-y-10">
              <div className="relative">
                <div className="h-40 w-40 rounded-full border-8 border-slate-100 border-t-blue-500 animate-spin" />
                <div className="absolute inset-0 flex items-center justify-center">
                  <Sparkles size={48} className="text-blue-500 animate-pulse" />
                </div>
              </div>

              <div className="space-y-4 text-center">
                <h2 className="text-3xl font-black text-slate-800">기록 분석 중...</h2>
                <div className="flex flex-col gap-2">
                  <div className="flex items-center gap-3 text-emerald-500 font-bold justify-center">
                     <CheckCircle2 size={18} /> <span>생기부 텍스트 파싱 완료</span>
                  </div>
                  <div className="flex items-center gap-3 text-blue-500 font-bold justify-center">
                     <Loader2 size={18} className="animate-spin" /> <span>목표 대학 인재상 매칭 모델 탐색 중</span>
                  </div>
                  <div className="flex items-center gap-3 text-slate-300 font-bold justify-center">
                     <div className="w-4 h-4 rounded-full border-2 border-slate-200" /> <span>심층 학업 역량 및 탐구 지수 산출</span>
                  </div>
                </div>
              </div>
            </div>

            <AsyncJobStatusCard
              job={diagnosisJob}
              runStatus={diagnosisRun?.status}
              errorMessage={diagnosisRun?.error_message}
            />
          </motion.div>
        )}

        {step === 'FAILED' && (
          <motion.div
            key="failed"
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            className="space-y-8"
          >
            <div className="rounded-[40px] border border-red-200 bg-white p-8 shadow-xl shadow-red-100/40">
              <div className="flex items-start gap-4">
                <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-red-50 text-red-600">
                  <AlertTriangle size={28} />
                </div>
                <div className="space-y-3">
                  <h2 className="text-2xl font-extrabold text-slate-800">The diagnosis needs attention.</h2>
                  <p className="text-sm font-medium leading-6 text-slate-600">
                    {diagnosisError || 'The diagnosis could not be completed. Check the job details below and retry if it is safe to do so.'}
                  </p>
                </div>
              </div>
            </div>

            <AsyncJobStatusCard
              job={diagnosisJob}
              runStatus={diagnosisRun?.status}
              errorMessage={diagnosisError}
              onRetry={diagnosisJob?.status === 'failed' ? retryDiagnosis : null}
              isRetrying={isRetryingDiagnosis}
            />

            <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-center">
              <button
                type="button"
                onClick={() => setStep('UPLOAD')}
                className="w-full rounded-[24px] border-2 border-slate-100 bg-white px-8 py-4 text-base font-black text-slate-600 transition-colors hover:bg-slate-50 sm:w-auto"
              >
                Back to upload
              </button>
              {diagnosisJob?.status === 'failed' ? (
                <button
                  type="button"
                  onClick={retryDiagnosis}
                  disabled={isRetryingDiagnosis}
                  className="w-full rounded-[24px] bg-slate-900 px-8 py-4 text-base font-black text-white transition-colors hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-60 sm:w-auto"
                >
                  {isRetryingDiagnosis ? 'Retrying...' : 'Retry diagnosis'}
                </button>
              ) : null}
            </div>
          </motion.div>
        )}

        {step === 'RESULT' && diagnosisResult && (
          <motion.div
            key="result"
            initial={{ opacity: 0, y: 30 }}
            animate={{ opacity: 1, y: 0 }}
            data-testid="diagnosis-result-panel"
            className="space-y-8"
          >
            <div className="bg-white rounded-[50px] border border-slate-100 p-10 md:p-14 shadow-2xl relative overflow-hidden">
              <div className="absolute top-0 right-0 p-8">
                <div className={`px-5 py-2 rounded-full text-xs font-black uppercase tracking-widest shadow-sm ${
                  diagnosisResult.risk_level === 'safe' ? 'bg-emerald-50 text-emerald-600' :
                  diagnosisResult.risk_level === 'warning' ? 'bg-amber-50 text-amber-600' : 'bg-red-50 text-red-600'
                }`}>
                  {formatRiskLevel(diagnosisResult.risk_level)}
                </div>
              </div>

              <div className="space-y-12">
                {/* Headline */}
                <div className="max-w-2xl">
                  <h3 className="text-[12px] font-black text-blue-500 uppercase tracking-[0.2em] mb-3">AI 심층 진단 요약</h3>
                  <p className="text-3xl md:text-4xl font-black text-slate-900 leading-tight">
                    {diagnosisResult.headline}
                  </p>
                </div>
 
                {/* Grid */}
                <div className="grid md:grid-cols-2 gap-12">
                  <div className="space-y-6">
                    <div className="flex items-center gap-2">
                      <div className="h-6 w-6 bg-emerald-100 text-emerald-600 rounded-lg flex items-center justify-center"><CheckCircle2 size={14}/></div>
                      <h4 className="text-sm font-black text-slate-800 uppercase tracking-widest">현재의 강점 (Strengths)</h4>
                    </div>
                    <ul className="space-y-4">
                      {diagnosisResult.strengths.map((s, i) => (
                        <li key={i} className="flex gap-3 text-slate-600 font-bold leading-relaxed">
                          <span className="text-emerald-500 shrink-0">•</span> {s}
                        </li>
                      ))}
                    </ul>
                  </div>
 
                  <div className="space-y-6">
                    <div className="flex items-center gap-2">
                      <div className="h-6 w-6 bg-red-100 text-red-600 rounded-lg flex items-center justify-center"><AlertTriangle size={14}/></div>
                      <h4 className="text-sm font-black text-slate-800 uppercase tracking-widest">보완 필요 사항 (Evidence Gaps)</h4>
                    </div>
                    <ul className="space-y-4">
                      {diagnosisResult.detailed_gaps?.length ? (
                        diagnosisResult.detailed_gaps.map((g, i) => (
                          <li key={i} className="bg-slate-50 border border-slate-100 rounded-xl p-4 space-y-1">
                            <p className="text-sm font-black text-slate-800 flex items-center gap-2">
                              <span className="text-red-500">•</span> {g.title}
                            </p>
                            <p className="text-xs font-bold text-slate-500 leading-relaxed pl-5">
                              {g.description}
                            </p>
                          </li>
                        ))
                      ) : (
                        diagnosisResult.gaps.map((g, i) => (
                          <li key={i} className="flex gap-3 text-slate-600 font-bold leading-relaxed">
                            <span className="text-red-500 shrink-0">•</span> {g}
                          </li>
                        ))
                      )}
                    </ul>
                  </div>
                </div>

                {/* Action Plan (Quests) */}
                {diagnosisResult.action_plan && diagnosisResult.action_plan.length > 0 && (
                  <div className="pt-8 border-t border-slate-100">
                    <div className="flex items-center gap-3 mb-6">
                       <TargetIcon className="text-blue-600" size={20} />
                       <h4 className="text-sm font-black text-slate-800 uppercase tracking-widest">AI 추천 퀘스트 (Action Plan)</h4>
                    </div>
                    <div className="grid sm:grid-cols-2 gap-4">
                      {diagnosisResult.action_plan.map((quest, i) => (
                        <div key={i} className="p-6 bg-white border-2 border-slate-50 rounded-[32px] hover:border-blue-100 transition-all group">
                          <div className="flex items-start justify-between mb-4">
                            <span className={`px-3 py-1 rounded-full text-[10px] font-black uppercase tracking-widest ${
                              quest.priority === 'high' ? 'bg-red-50 text-red-600' :
                              quest.priority === 'medium' ? 'bg-blue-50 text-blue-600' : 'bg-slate-50 text-slate-400'
                            }`}>
                              {quest.priority} priority
                            </span>
                            <div className="h-8 w-8 bg-slate-50 text-slate-400 rounded-lg flex items-center justify-center group-hover:bg-blue-600 group-hover:text-white transition-colors">
                              <Plus size={16} />
                            </div>
                          </div>
                          <h5 className="font-black text-slate-800 mb-2 leading-tight">{quest.title}</h5>
                          <p className="text-sm font-bold text-slate-500 leading-relaxed">{quest.description}</p>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
 
                {/* Recommendation */}
                <div className="p-8 bg-blue-50 rounded-[32px] border border-blue-100">
                  <div className="flex items-center gap-3 mb-4">
                    <Sparkles className="text-blue-500" />
                    <h4 className="text-lg font-black text-blue-900">AI 추천 다음 탐구 방향</h4>
                  </div>
                  <p className="text-blue-800 font-bold leading-relaxed text-lg">
                    {diagnosisResult.recommended_focus}
                  </p>
                </div>
              </div>
            </div>

            <DiagnosisEvidencePanel
              citations={evidenceCitations}
              reviewRequired={reviewRequired}
              policyFlags={diagnosisRun?.policy_flags ?? []}
              responseTraceId={responseTraceId}
            />

            <div className="flex flex-col sm:flex-row gap-4 items-center justify-center">
              <button 
                 onClick={() => {
                   setStep('GOALS');
                   setDiagnosisResult(null);
                   setDiagnosisRun(null);
                   setDiagnosisJob(null);
                   setDiagnosisRunId(null);
                   setDiagnosisError(null);
                   setIsUploading(false);
                 }}
                 className="w-full sm:w-auto px-8 py-5 bg-white border-2 border-slate-100 text-slate-600 rounded-[24px] font-black hover:bg-slate-50"
              >
                 목표 다시 수정하기
              </button>
              <button 
                onClick={() => navigate(`/workshop/${projectId}`)}
                className="w-full sm:w-auto px-12 py-5 bg-slate-900 text-white rounded-[24px] font-black text-xl flex items-center gap-3 hover:bg-black transition-all shadow-2xl"
              >
                이 진단을 토대로 탐구 시작하기 <ArrowRight />
              </button>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
