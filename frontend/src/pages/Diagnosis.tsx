import React, { useCallback, useEffect, useState } from 'react';
import { AnimatePresence, motion } from 'motion/react';
import { AlertTriangle, ArrowRight, CheckCircle2, FileUp, Loader2, Plus, Target, Trash2 } from 'lucide-react';
import { useDropzone } from 'react-dropzone';
import toast from 'react-hot-toast';
import { useNavigate } from 'react-router-dom';
import { AsyncJobStatusCard } from '../components/AsyncJobStatusCard';
import { UniversityLogo } from '../components/UniversityLogo';
import { useAuthStore } from '../store/authStore';
import { useOnboardingStore } from '../store/onboardingStore';
import { api, shouldUseSynchronousApiJobs } from '../lib/api';
import { DiagnosisEvidencePanel } from '../components/DiagnosisEvidencePanel';
import { DiagnosisGuidedChoicePanel } from '../components/DiagnosisGuidedChoicePanel';
import { ClaimGroundingPanel } from '../components/ClaimGroundingPanel';
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
import {
  EmptyState,
  PageHeader,
  PrimaryButton,
  SecondaryButton,
  SectionCard,
  StatusBadge,
  StepIndicator,
  SurfaceCard,
  WorkflowNotice,
} from '../components/primitives';

type DiagnosisStep = 'GOALS' | 'UPLOAD' | 'ANALYSING' | 'RESULT' | 'FAILED';

export function Diagnosis() {
  const navigate = useNavigate();
  const { user } = useAuthStore();
  const { goals, setGoals, submitGoals } = useOnboardingStore();

  const [step, setStep] = useState<DiagnosisStep>('GOALS');
  const [goalList, setGoalList] = useState<Array<{ id: string; university: string; major: string }>>([]);
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
  const useSynchronousApiJobs = shouldUseSynchronousApiJobs();

  useEffect(() => {
    if (!user) return;

    const initial: Array<{ id: string; university: string; major: string }> = [];
    if (user.target_university && user.target_major) {
      initial.push({ id: 'main', university: user.target_university, major: user.target_major });
    }
    user.interest_universities?.forEach((interest, idx) => {
      const match = interest.match(/^(.+)\s\((.+)\)$/);
      if (match) initial.push({ id: `interest-${idx}`, university: match[1], major: match[2] });
      else initial.push({ id: `interest-${idx}`, university: interest, major: '' });
    });
    setGoalList(initial.slice(0, 6));
  }, [user]);

  const handleAddGoal = () => {
    if (!currentUniv || !currentMajor || goalList.length >= 6) return;
    setGoalList(prev => [...prev, { id: crypto.randomUUID(), university: currentUniv, major: currentMajor }]);
    setCurrentUniv('');
    setCurrentMajor('');
    setUnivInput('');
  };

  const removeGoal = (id: string) => setGoalList(prev => prev.filter(goal => goal.id !== id));

  const saveGoals = async () => {
    if (!goalList.length) {
      toast.error('최소 1개의 목표를 설정해 주세요.');
      return;
    }

    const main = goalList[0];
    const others = goalList.slice(1).map(goal => `${goal.university} (${goal.major})`);
    const payload = {
      target_university: main.university,
      target_major: main.major,
      interest_universities: others,
      admission_type: goals.admission_type || '학생부종합',
    };

    setGoals(payload);

    const success = await submitGoals(payload);
    if (success) {
      setIsEditingGoals(false);
      toast.success('목표가 저장되었습니다.');
    }
  };

  const completeDiagnosis = useCallback(
    (run: DiagnosisRunResponse) => {
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
    },
    [currentMajor, goalList],
  );

  const syncDiagnosisRun = useCallback(
    async (runId: string) => {
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
    },
    [completeDiagnosis],
  );

  useEffect(() => {
    if (!diagnosisRunId) return undefined;

    let cancelled = false;
    let timeoutId: number | undefined;

    const poll = async () => {
      try {
        const terminal = await syncDiagnosisRun(diagnosisRunId);
        if (!cancelled && !terminal) timeoutId = window.setTimeout(poll, 2000);
      } catch (error) {
        console.error('Polling failed', error);
        if (!cancelled) {
          setDiagnosisError('진단 상태를 갱신하지 못했습니다.');
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

      if (useSynchronousApiJobs) {
        await api.post<AsyncJobRead>(`/api/v1/jobs/${retried.id}/process`);
        await syncDiagnosisRun(diagnosisRun.id);
        setDiagnosisRunId(null);
        toast.success('재시도를 즉시 처리했습니다.');
      } else {
        setDiagnosisRunId(diagnosisRun.id);
        toast.success('재시도를 요청했습니다.');
      }
    } catch (error) {
      console.error('Diagnosis retry failed:', error);
      toast.error('재시도 요청에 실패했습니다.');
    } finally {
      setIsRetryingDiagnosis(false);
    }
  }, [diagnosisRun, isRetryingDiagnosis, syncDiagnosisRun, useSynchronousApiJobs]);

  const onDrop = useCallback(
    async (acceptedFiles: File[]) => {
      const file = acceptedFiles[0];
      if (!file) return;

      setIsUploading(true);
      const loadingId = toast.loading('PDF 업로드와 진단 준비를 진행 중입니다...');

      try {
        const formData = new FormData();
        formData.append('file', file);
        const mainGoal = goalList[0];
        if (mainGoal) {
          formData.append('target_major', mainGoal.major);
          formData.append('title', `${mainGoal.university} ${mainGoal.major} 진단`);
        }

        const uploadRes = await api.post<{ project_id: string; id: string }>('/api/v1/documents/upload', formData, {
          headers: { 'Content-Type': 'multipart/form-data' },
        });
        setProjectId(uploadRes.project_id);

        const parseUrl = useSynchronousApiJobs
          ? `/api/v1/documents/${uploadRes.id}/parse?wait_for_completion=true`
          : `/api/v1/documents/${uploadRes.id}/parse`;
        await api.post(parseUrl);

        setStep('ANALYSING');

        const diagnosisUrl = useSynchronousApiJobs ? '/api/v1/diagnosis/run?wait_for_completion=true' : '/api/v1/diagnosis/run';
        const run = await api.post<DiagnosisRunResponse>(diagnosisUrl, { project_id: uploadRes.project_id });
        setDiagnosisRun(run);
        setDiagnosisJob(null);
        setDiagnosisResult(null);
        setDiagnosisError(null);

        if (isDiagnosisComplete(run)) {
          completeDiagnosis(run);
        } else if (isDiagnosisFailed(run, null)) {
          setDiagnosisError(getDiagnosisFailureMessage(run, null));
          setStep('FAILED');
          setDiagnosisRunId(null);
          setIsUploading(false);
        } else {
          setDiagnosisRunId(run.id);
        }

        toast.success('진단 실행을 시작했습니다.', { id: loadingId });
      } catch (error: any) {
        console.error('Diagnosis flow failed:', error);
        const detail = error.response?.data?.detail || '진단 실행에 실패했습니다. 파일 형식이나 용량(50MB)을 확인해 주세요.';
        toast.error(detail, { id: loadingId });
        setIsUploading(false);
      }
    },
    [completeDiagnosis, goalList, useSynchronousApiJobs],
  );

  const { getRootProps, getInputProps, isDragActive, open } = useDropzone({
    onDrop,
    accept: { 'application/pdf': ['.pdf'] },
    multiple: false,
    disabled: isUploading,
    noClick: true,
    noKeyboard: true,
    useFsAccessApi: false,
  });

  const handleOpenFileDialog = useCallback(() => {
    if (isUploading) return;
    open();
  }, [isUploading, open]);

  const handleDropzoneKeyDown = useCallback((event: React.KeyboardEvent<HTMLDivElement>) => {
    if (isUploading) return;
    if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault();
      open();
    }
  }, [isUploading, open]);

  const evidenceCitations = diagnosisResult?.citations ?? diagnosisRun?.citations ?? [];
  const reviewRequired = diagnosisResult?.review_required ?? diagnosisRun?.review_required ?? false;
  const responseTraceId = diagnosisResult?.response_trace_id ?? diagnosisRun?.response_trace_id ?? null;
  const univPreviewName = (currentUniv || univInput).trim();

  const stepItems: Array<{ id: string; label: string; description: string; state: 'done' | 'active' | 'pending' | 'error' }> = [
    {
      id: 'goals',
      label: '목표 설정',
      description: '지원 목표 확정',
      state: step === 'GOALS' ? 'active' : ['UPLOAD', 'ANALYSING', 'RESULT', 'FAILED'].includes(step) ? 'done' : 'pending',
    },
    {
      id: 'upload',
      label: '기록 업로드',
      description: '학생부 PDF 제출',
      state: step === 'UPLOAD' ? 'active' : ['ANALYSING', 'RESULT', 'FAILED'].includes(step) ? 'done' : 'pending',
    },
    {
      id: 'analysis',
      label: '진단 실행',
      description: '근거 기반 분석',
      state: step === 'ANALYSING' ? 'active' : step === 'RESULT' ? 'done' : step === 'FAILED' ? 'error' : 'pending',
    },
    {
      id: 'result',
      label: '결과 검토',
      description: '워크숍 진입 판단',
      state: step === 'RESULT' ? 'active' : step === 'FAILED' ? 'error' : 'pending',
    },
  ];

  const headerTitle =
    step === 'GOALS' ? '진단 목표를 확인해 주세요' :
    step === 'UPLOAD' ? '학생부 PDF를 업로드해 주세요' :
    step === 'ANALYSING' ? '진단을 실행하고 있습니다' :
    step === 'RESULT' ? '진단 결과를 검토해 주세요' :
    '진단 실행 중 확인이 필요합니다';

  const headerDescription =
    step === 'GOALS' ? '목표가 분명할수록 진단 결과와 퀘스트 추천의 정확도가 높아집니다.' :
    step === 'UPLOAD' ? 'PDF 1개를 업로드하면 파싱, 마스킹, 진단이 순차적으로 진행됩니다.' :
    step === 'ANALYSING' ? '근거 매핑과 위험 신호 분석을 진행 중입니다.' :
    step === 'RESULT' ? '강점, 보완점, 액션 플랜을 확인한 뒤 워크숍으로 이동하세요.' :
    '실패 원인과 작업 상태를 확인하고 안전하게 재시도해 주세요.';

  return (
    <div className="mx-auto max-w-6xl space-y-6 py-4">
      <PageHeader eyebrow="진단" title={headerTitle} description={headerDescription} />
      <StepIndicator items={stepItems} />

      <AnimatePresence mode="wait">
        {step === 'GOALS' ? (
          <motion.div key="goals" initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -10 }} className="space-y-6">
            <SectionCard
              title="지원 목표 목록"
              description="첫 번째 목표가 진단 기준점으로 사용됩니다."
              actions={
                !isEditingGoals ? (
                  <SecondaryButton data-testid="diagnosis-edit-goals" onClick={() => setIsEditingGoals(true)}>
                    수정하기
                  </SecondaryButton>
                ) : null
              }
            >
              {isEditingGoals ? (
                <div className="grid gap-6 lg:grid-cols-2">
                  <SurfaceCard tone="muted" className="space-y-4">
                    <div className="relative">
                      <label className="mb-1 block text-xs font-bold uppercase tracking-[0.14em] text-slate-400">대학 검색</label>
                      <input
                        data-testid="diagnosis-university-search"
                        type="text"
                        value={univInput}
                        onChange={event => setUnivInput(event.target.value)}
                        placeholder="대학명을 입력하세요"
                        className="h-11 w-full rounded-xl border border-slate-300 bg-white px-3.5 pr-12 text-sm font-semibold text-slate-700 outline-none focus-visible:ring-2 focus-visible:ring-blue-300"
                      />
                      {univPreviewName.length >= 2 ? (
                        <UniversityLogo
                          universityName={univPreviewName}
                          className="pointer-events-none absolute right-2 top-[31px] h-7 w-7 rounded-md bg-white object-contain p-0.5 shadow-sm"
                          fallbackClassName="border border-slate-200"
                        />
                      ) : null}
                      {univInput ? (
                        <div className="absolute left-0 right-0 top-full z-10 mt-1 max-h-44 overflow-auto rounded-xl border border-slate-200 bg-white shadow-md">
                          {searchUniversities(univInput, { excludeNames: goalList.map(goal => goal.university) }).map((suggestion, index) => (
                            <button
                              key={suggestion.label}
                              type="button"
                              data-testid={`diagnosis-university-option-${index}`}
                              onClick={() => {
                                setCurrentUniv(suggestion.label);
                                setUnivInput('');
                              }}
                              className="block w-full border-b border-slate-100 px-3 py-2 text-left text-sm font-semibold text-slate-700 last:border-b-0 hover:bg-slate-50"
                            >
                              {suggestion.label}
                            </button>
                          ))}
                        </div>
                      ) : null}
                    </div>

                    {currentUniv ? (
                      <div className="space-y-3 rounded-xl border border-blue-100 bg-blue-50 p-3">
                        <div className="flex items-center justify-between gap-2">
                          <div className="flex min-w-0 items-center gap-2">
                            <UniversityLogo
                              universityName={currentUniv}
                              className="h-7 w-7 rounded-md bg-white object-contain p-0.5 shadow-sm"
                              fallbackClassName="border border-blue-100"
                            />
                            <StatusBadge status="active" className="truncate">{currentUniv}</StatusBadge>
                          </div>
                          <button type="button" onClick={() => setCurrentUniv('')} className="text-slate-400 hover:text-slate-700">
                            <Trash2 size={15} />
                          </button>
                        </div>
                        <CatalogAutocompleteInput
                          label="학과"
                          value={currentMajor}
                          onChange={setCurrentMajor}
                          placeholder="학과를 입력하세요"
                          suggestions={searchMajors(currentMajor, currentUniv, 20)}
                          onSelect={item => setCurrentMajor(item.label)}
                          inputTestId="diagnosis-major-search"
                          suggestionTestIdPrefix="diagnosis-major-option"
                        />
                        <PrimaryButton
                          data-testid="diagnosis-add-goal"
                          onClick={handleAddGoal}
                          disabled={!currentUniv || currentMajor.length < 2 || goalList.length >= 6}
                          fullWidth
                        >
                          <Plus size={16} />
                          목표 추가
                        </PrimaryButton>
                      </div>
                    ) : null}
                  </SurfaceCard>

                  <div className="space-y-2">
                    {goalList.map((goal, index) => (
                      <SurfaceCard key={goal.id} padding="sm" className="flex items-center justify-between gap-3">
                        <div className="flex min-w-0 items-center gap-2">
                          <UniversityLogo
                            universityName={goal.university}
                            className="h-8 w-8 rounded-md bg-white object-contain p-0.5 shadow-sm"
                            fallbackClassName="border border-slate-200"
                          />
                          <div className="min-w-0">
                            <p className="truncate text-sm font-bold text-slate-800">{goal.university}</p>
                            <p className="truncate text-xs font-medium text-slate-500">{goal.major}</p>
                          </div>
                        </div>
                        <div className="flex items-center gap-2">
                          {index === 0 ? <StatusBadge status="active">주 목표</StatusBadge> : null}
                          <button type="button" onClick={() => removeGoal(goal.id)} className="text-slate-400 hover:text-red-600">
                            <Trash2 size={15} />
                          </button>
                        </div>
                      </SurfaceCard>
                    ))}
                  </div>
                </div>
              ) : goalList.length ? (
                <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                  {goalList.map((goal, index) => (
                    <SurfaceCard key={goal.id} tone="muted" padding="sm">
                      <div className="mb-2">
                        <StatusBadge status={index === 0 ? 'active' : 'neutral'}>{index === 0 ? '주 목표' : `목표 ${index + 1}`}</StatusBadge>
                      </div>
                      <div className="flex min-w-0 items-center gap-2">
                        <UniversityLogo
                          universityName={goal.university}
                          className="h-8 w-8 rounded-md bg-white object-contain p-0.5 shadow-sm"
                          fallbackClassName="border border-slate-200"
                        />
                        <div className="min-w-0">
                          <p className="truncate text-sm font-bold text-slate-800">{goal.university}</p>
                          <p className="truncate text-xs font-medium text-slate-500">{goal.major}</p>
                        </div>
                      </div>
                    </SurfaceCard>
                  ))}
                </div>
              ) : (
                <EmptyState title="설정된 목표가 없습니다" description="진단을 시작하려면 최소 1개의 목표를 설정해 주세요." />
              )}
            </SectionCard>

            {isEditingGoals ? (
              <div className="flex flex-wrap items-center justify-end gap-2">
                <SecondaryButton onClick={() => setIsEditingGoals(false)}>취소</SecondaryButton>
                <PrimaryButton data-testid="diagnosis-save-goals" onClick={saveGoals}>
                  목표 저장
                </PrimaryButton>
              </div>
            ) : (
              <div className="flex justify-center">
                <PrimaryButton data-testid="diagnosis-goals-continue" onClick={() => setStep('UPLOAD')} disabled={!goalList.length} size="lg">
                  업로드 단계로 이동
                  <ArrowRight size={18} />
                </PrimaryButton>
              </div>
            )}
          </motion.div>
        ) : null}

        {step === 'UPLOAD' ? (
          <motion.div key="upload" initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -10 }}>
            <SectionCard title="PDF 업로드" description="파일 1개(최대 50MB)를 업로드하면 파싱과 진단이 자동 실행됩니다.">
              <div
                {...getRootProps({
                  onClick: handleOpenFileDialog,
                  onKeyDown: handleDropzoneKeyDown,
                })}
                className={`cursor-pointer rounded-2xl border-2 border-dashed p-10 text-center transition-colors ${
                  isDragActive ? 'border-blue-400 bg-blue-50' : 'border-slate-300 bg-slate-50 hover:border-blue-300 hover:bg-white'
                } ${isUploading ? 'pointer-events-none opacity-60' : ''}`}
              >
                <input data-testid="diagnosis-upload-input" {...getInputProps()} />
                <div className="mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-2xl bg-white text-blue-700 shadow-sm">
                  {isUploading ? <Loader2 size={26} className="animate-spin" /> : <FileUp size={26} />}
                </div>
                <p className="text-lg font-bold tracking-tight text-slate-900">학생부 PDF를 드래그하거나 클릭해 업로드하세요</p>
                <p className="mt-2 text-sm font-medium text-slate-500">파싱, 마스킹, 진단이 순차적으로 진행됩니다.</p>
                <div className="mt-4">
                  <button
                    type="button"
                    onClick={(event) => {
                      event.preventDefault();
                      event.stopPropagation();
                      handleOpenFileDialog();
                    }}
                    disabled={isUploading}
                    className="inline-flex items-center gap-2 rounded-xl border border-blue-200 bg-white px-4 py-2 text-sm font-bold text-blue-700 shadow-sm transition-colors hover:bg-blue-50 disabled:cursor-not-allowed disabled:opacity-60"
                  >
                    <FileUp size={15} />
                    파일 선택
                  </button>
                </div>
              </div>
            </SectionCard>
          </motion.div>
        ) : null}

        {step === 'ANALYSING' ? (
          <motion.div key="analysing" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} className="space-y-6">
            <WorkflowNotice
              tone="loading"
              title="진단 분석을 진행 중입니다"
              description="페이지를 유지하면 작업 상태가 자동으로 갱신됩니다."
            />
            <AsyncJobStatusCard job={diagnosisJob} runStatus={diagnosisRun?.status} errorMessage={diagnosisRun?.error_message} />
          </motion.div>
        ) : null}

        {step === 'FAILED' ? (
          <motion.div key="failed" initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -10 }} className="space-y-6">
            <WorkflowNotice tone="danger" title="진단 실행에 실패했습니다" description={diagnosisError || '작업 상태를 확인한 뒤 재시도해 주세요.'} />

            <AsyncJobStatusCard
              job={diagnosisJob}
              runStatus={diagnosisRun?.status}
              errorMessage={diagnosisError}
              onRetry={diagnosisJob?.status === 'failed' ? retryDiagnosis : null}
              isRetrying={isRetryingDiagnosis}
            />

            <div className="flex flex-wrap items-center justify-center gap-2">
              <SecondaryButton onClick={() => setStep('UPLOAD')}>업로드로 돌아가기</SecondaryButton>
              {diagnosisJob?.status === 'failed' ? (
                <PrimaryButton onClick={retryDiagnosis} disabled={isRetryingDiagnosis}>
                  {isRetryingDiagnosis ? '재시도 중...' : '진단 재시도'}
                </PrimaryButton>
              ) : null}
            </div>
          </motion.div>
        ) : null}

        {step === 'RESULT' && diagnosisResult ? (
          <motion.div key="result" initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }} className="space-y-6">
            <SectionCard
              title={diagnosisResult.headline}
              description="진단 근거를 확인한 뒤 워크숍으로 이동해 주세요."
              eyebrow="진단 결과"
              data-testid="diagnosis-result-panel"
              actions={
                <StatusBadge status={diagnosisResult.risk_level === 'safe' ? 'success' : diagnosisResult.risk_level === 'warning' ? 'warning' : 'danger'}>
                  {formatRiskLevel(diagnosisResult.risk_level)}
                </StatusBadge>
              }
            >
              <div className="grid gap-4 md:grid-cols-2">
                <SurfaceCard tone="muted" padding="sm">
                  <p className="mb-2 text-xs font-bold uppercase tracking-[0.14em] text-slate-400">강점</p>
                  <ul className="space-y-1.5">
                    {diagnosisResult.strengths.map((item, index) => (
                      <li key={index} className="flex gap-2 text-sm font-medium leading-6 text-slate-700">
                        <CheckCircle2 size={14} className="mt-1 text-emerald-600" />
                        {item}
                      </li>
                    ))}
                  </ul>
                </SurfaceCard>

                <SurfaceCard tone="muted" padding="sm">
                  <p className="mb-2 text-xs font-bold uppercase tracking-[0.14em] text-slate-400">보완 포인트</p>
                  <ul className="space-y-1.5">
                    {(diagnosisResult.detailed_gaps?.length
                      ? diagnosisResult.detailed_gaps.map(gap => `${gap.title}: ${gap.description}`)
                      : diagnosisResult.gaps
                    ).map((item, index) => (
                      <li key={index} className="flex gap-2 text-sm font-medium leading-6 text-slate-700">
                        <AlertTriangle size={14} className="mt-1 text-amber-600" />
                        {item}
                      </li>
                    ))}
                  </ul>
                </SurfaceCard>
              </div>

              {diagnosisResult.action_plan?.length ? (
                <div className="space-y-2">
                  <p className="text-xs font-bold uppercase tracking-[0.14em] text-slate-400">권장 액션 플랜</p>
                  <div className="grid gap-3 md:grid-cols-2">
                    {diagnosisResult.action_plan.map((quest, index) => (
                      <SurfaceCard key={`${quest.title}-${index}`} padding="sm">
                        <div className="mb-2 flex items-center justify-between gap-2">
                          <p className="text-sm font-bold text-slate-800">{quest.title}</p>
                          <StatusBadge status={quest.priority === 'high' ? 'danger' : quest.priority === 'medium' ? 'warning' : 'neutral'}>
                            {quest.priority}
                          </StatusBadge>
                        </div>
                        <p className="text-sm font-medium leading-6 text-slate-600">{quest.description}</p>
                      </SurfaceCard>
                    ))}
                  </div>
                </div>
              ) : null}

              <WorkflowNotice tone="info" title="추천 집중 영역" description={diagnosisResult.recommended_focus} />
            </SectionCard>

            {diagnosisRun?.id && projectId ? (
              <DiagnosisGuidedChoicePanel
                diagnosisRunId={diagnosisRun.id}
                projectId={projectId}
                diagnosis={diagnosisResult}
                useSynchronousApiJobs={useSynchronousApiJobs}
              />
            ) : null}

            <div className="grid gap-6 xl:grid-cols-2">
              {diagnosisResult.claims?.length ? <ClaimGroundingPanel claims={diagnosisResult.claims} /> : null}
              <DiagnosisEvidencePanel
                citations={evidenceCitations}
                reviewRequired={reviewRequired}
                policyFlags={diagnosisRun?.policy_flags ?? []}
                responseTraceId={responseTraceId}
              />
            </div>

            <div className="flex flex-wrap items-center justify-center gap-2">
              <SecondaryButton
                onClick={() => {
                  setStep('GOALS');
                  setDiagnosisResult(null);
                  setDiagnosisRun(null);
                  setDiagnosisJob(null);
                  setDiagnosisRunId(null);
                  setDiagnosisError(null);
                  setIsUploading(false);
                }}
              >
                목표 다시 설정
              </SecondaryButton>
              <PrimaryButton onClick={() => navigate(`/app/workshop/${projectId}`)}>
                워크숍 시작
                <ArrowRight size={16} />
              </PrimaryButton>
            </div>
          </motion.div>
        ) : null}
      </AnimatePresence>
    </div>
  );
}
