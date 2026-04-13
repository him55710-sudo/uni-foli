import React, { useState, useRef, useEffect, useCallback, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import { motion, AnimatePresence } from 'motion/react';
import { useDropzone } from 'react-dropzone';
import { 
  Sparkles, 
  ArrowRight, 
} from 'lucide-react';

import toast from 'react-hot-toast';

import { useAuthStore } from '../store/authStore';
import { useOnboardingStore } from '../store/onboardingStore';
import { api, shouldUseSynchronousApiJobs } from '../lib/api';
import { getApiErrorMessage } from '../lib/apiError';
import { ProcessTimingDashboard, TimingPhaseStatus } from '../components/ProcessTimingDashboard';

import { 
  AsyncJobRead, 
  DiagnosisRunResponse, 
  DiagnosisResultPayload 
} from '../types/api';
import { buildRankedGoals } from '../lib/rankedGoals';
import { 
  mergeDiagnosisPayload,
  isDiagnosisComplete,
  isDiagnosisFailed,
  getDiagnosisFailureMessage,
  DIAGNOSIS_STORAGE_KEY
} from '../lib/diagnosis';

import {
  PrimaryButton,
  SecondaryButton,
  StepIndicator,
  WorkflowNotice,
} from '../components/primitives';
import { AsyncJobStatusCard } from '../components/AsyncJobStatusCard';
import { useAsyncJob } from '../hooks/useAsyncJob';
import { TERMINAL_STATUSES, SUCCESS_STATUSES, DocumentStatus } from '../types/domain';

import { DiagnosisProfile } from '../components/diagnosis/DiagnosisProfile';
import { DiagnosisGoals } from '../components/diagnosis/DiagnosisGoals';
import { DiagnosisUpload } from '../components/diagnosis/DiagnosisUpload';
import { DiagnosisResultDisplay } from '../components/diagnosis/DiagnosisResultDisplay';

type DiagnosisStep = 'PROFILE' | 'GOALS' | 'UPLOAD' | 'ANALYSING' | 'RESULT' | 'FAILED';
const MAX_UPLOAD_BYTES = 50 * 1024 * 1024;

interface DiagnosisDocumentStatus {
  id: string;
  project_id: string;
  status: DocumentStatus;
  content_text: string;
  page_count?: number;
  latest_async_job_id?: string | null;
  latest_async_job_status?: string | null;
  latest_async_job_error?: string | null;
  last_error?: string | null;
  parse_metadata?: {
    stages?: Record<string, { status: 'pending' | 'processing' | 'success' | 'failed'; error?: string }>;
    fallback_used?: boolean;
    pipeline_version?: string;
    [key: string]: any;
  };
}

type TimingPhaseKey = 'upload' | 'parse' | 'diagnosis';
interface TimingPhaseState {
  status: TimingPhaseStatus;
  startedAt: number | null;
  finishedAt: number | null;
  note?: string;
}
type TimingPhaseMap = Record<TimingPhaseKey, TimingPhaseState>;

const PARSE_SUCCESS_STATUSES = SUCCESS_STATUSES;
const PARSE_TERMINAL_STATUSES = TERMINAL_STATUSES;

function createInitialTimingPhases(): TimingPhaseMap {
  return {
    upload: { status: 'idle', startedAt: null, finishedAt: null, note: '데이터 전송 준비 중' },
    parse: { status: 'idle', startedAt: null, finishedAt: null, note: '학생부 정보 추출 준비 중' },
    diagnosis: { status: 'idle', startedAt: null, finishedAt: null, note: '인공지능 맞춤 진단 준비 중' },
  };
}

export function Diagnosis() {
  const navigate = useNavigate();
  const { user } = useAuthStore();
  
  const { 
    diagnosisStep, 
    setDiagnosisStep,
    goalList,
    activeProjectId: projectId,
    activeDocumentId,
    activeDiagnosisRunId: diagnosisRunId,
    setActiveProjectId: setProjectId,
    setActiveDocumentId,
    setActiveDiagnosisRunId: setDiagnosisRunId,
    resetOnboarding,
    syncWithUser
  } = useOnboardingStore();

  const step = diagnosisStep as DiagnosisStep;
  const setStep = setDiagnosisStep;

  const diagnosisProcessKickoffRef = useRef<Set<string>>(new Set());
  const parseProcessKickoffRef = useRef<Set<string>>(new Set());

  const [isUploading, setIsUploading] = useState(false);
  const [diagnosisResult, setDiagnosisResult] = useState<DiagnosisResultPayload | null>(null);
  const [diagnosisRun, setDiagnosisRun] = useState<DiagnosisRunResponse | null>(null);
  const [diagnosisJob, setDiagnosisJob] = useState<AsyncJobRead | null>(null);
  const [diagnosisError, setDiagnosisError] = useState<string | null>(null);
  const [isRetryingDiagnosis, setIsRetryingDiagnosis] = useState(false);
  const [flowError, setFlowError] = useState<string | null>(null);

  // Sync state on mount
  useEffect(() => {
    if (user) void syncWithUser(user);
  }, [syncWithUser, user]);
  const [timingPhases, setTimingPhases] = useState<TimingPhaseMap>(createInitialTimingPhases());
  
  const useSynchronousApiJobs = shouldUseSynchronousApiJobs();

  const setTimingPhase = useCallback(
    (phase: TimingPhaseKey, updater: Partial<TimingPhaseState> | ((prev: TimingPhaseState) => TimingPhaseState)) => {
      setTimingPhases((prev) => {
        const current = prev[phase];
        const next = typeof updater === 'function' ? updater(current) : { ...current, ...updater };
        return { ...prev, [phase]: next };
      });
    },
    [],
  );

  const beginTimingPhase = useCallback((phase: TimingPhaseKey, note?: string) => {
    const now = Date.now();
    setTimingPhase(phase, {
      status: 'running',
      startedAt: now,
      finishedAt: null,
      note,
    });
  }, [setTimingPhase]);

  const finishTimingPhase = useCallback((phase: TimingPhaseKey, status: Exclude<TimingPhaseStatus, 'idle'>, note?: string) => {
    const now = Date.now();
    setTimingPhase(phase, (prev) => ({
      ...prev,
      status,
      startedAt: prev.startedAt ?? now,
      finishedAt: now,
      note: note ?? prev.note,
    }));
  }, [setTimingPhase]);

  const failRunningTimingPhases = useCallback((note?: string) => {
    const now = Date.now();
    setTimingPhases((prev) => {
      const next = { ...prev };
      (Object.keys(next) as TimingPhaseKey[]).forEach((phase) => {
        if (next[phase].status !== 'running') return;
        next[phase] = {
          ...next[phase],
          status: 'failed',
          finishedAt: now,
          note: note ?? next[phase].note,
        };
      });
      return next;
    });
  }, []);

  const resetTimingPhases = useCallback(() => {
    setTimingPhases(createInitialTimingPhases());
  }, []);

  const triggerInlineDiagnosisProcessing = useCallback(
    (jobId: string) => {
      if (!jobId) return;
      const kickoffCache = diagnosisProcessKickoffRef.current;
      if (kickoffCache.has(jobId)) return;
      kickoffCache.add(jobId);

      void api.post<AsyncJobRead>(`/api/v1/jobs/${jobId}/process`)
        .then((processed) => {
          setDiagnosisJob((previous) => (previous && previous.id !== processed.id ? previous : processed));
        })
        .catch(() => {
          kickoffCache.delete(jobId);
        });
    },
    [],
  );

  const triggerInlineParseProcessing = useCallback(
    (document: DiagnosisDocumentStatus | null | undefined) => {
      if (!document) return;
      const jobId = document.latest_async_job_id;
      const jobStatus = (document.latest_async_job_status || '').toLowerCase();
      if (!jobId || (jobStatus !== 'queued' && jobStatus !== 'retrying')) return;

      const kickoffCache = parseProcessKickoffRef.current;
      if (kickoffCache.has(jobId)) return;
      kickoffCache.add(jobId);

      void api.post<AsyncJobRead>(`/api/v1/jobs/${jobId}/process`)
        .catch(() => {
          kickoffCache.delete(jobId);
        });
    },
    [],
  );

  const hasDocumentContent = (doc: DiagnosisDocumentStatus) => Boolean(doc.content_text?.trim());

  const completeDiagnosis = useCallback(
    (run: DiagnosisRunResponse) => {
      const payload = mergeDiagnosisPayload(run);
      if (!payload) return false;
      if (run.async_job_id) {
        diagnosisProcessKickoffRef.current.delete(run.async_job_id);
      }

      finishTimingPhase('diagnosis', 'done', '진단 생성 완료');
      setProjectId(run.project_id);
      setDiagnosisRun(run);
      setDiagnosisResult(payload);
      setDiagnosisError(null);
      setFlowError(null);
      setStep('RESULT');
      setDiagnosisRunId(null);
      setIsUploading(false);

      if (goalList.length > 0) {
        localStorage.setItem(
          DIAGNOSIS_STORAGE_KEY,
          JSON.stringify({
            major: goalList[0].major,
            projectId: run.project_id,
            savedAt: new Date().toISOString(),
            diagnosis: payload,
          }),
        );
      }

      return true;
    },
    [finishTimingPhase, goalList, setProjectId, setDiagnosisRunId, setStep],
  );

  const startDiagnosisForProject = useCallback(
    async (activeProjectId: string): Promise<boolean> => {
      const diagnosisUrl = useSynchronousApiJobs ? '/api/v1/diagnosis/run?wait_for_completion=true' : '/api/v1/diagnosis/run';
      const others = goalList.slice(1).map(goal => `${goal.university} (${goal.major})`);
      const run = await api.post<DiagnosisRunResponse>(diagnosisUrl, { 
        project_id: activeProjectId,
        interest_universities: others 
      });
      setProjectId(activeProjectId);
      setDiagnosisRun(run);
      setDiagnosisJob(null);

      if (isDiagnosisComplete(run)) {
        return completeDiagnosis(run);
      }

      if (isDiagnosisFailed(run, null)) {
        const runFailure = getDiagnosisFailureMessage(run, null);
        finishTimingPhase('diagnosis', 'failed', runFailure);
        setDiagnosisError(runFailure);
        setFlowError(runFailure);
        setStep('FAILED');
        setDiagnosisRunId(null);
        setIsUploading(false);
        return false;
      }

      setDiagnosisRunId(run.id);
      if (run.async_job_id) {
        triggerInlineDiagnosisProcessing(run.async_job_id);
      }
      return true;
    },
    [completeDiagnosis, finishTimingPhase, goalList, setProjectId, setDiagnosisRunId, setStep, triggerInlineDiagnosisProcessing, useSynchronousApiJobs],
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
        const completed = completeDiagnosis(run);
        if (!completed) {
          const failureMessage = '진단 결과를 불러오지 못했어요. 다시 시도해 주세요.';
          finishTimingPhase('diagnosis', 'failed', failureMessage);
          setDiagnosisError(failureMessage);
          setFlowError(failureMessage);
          setStep('FAILED');
          setDiagnosisRunId(null);
          setIsUploading(false);
        }
        return true;
      }

      if (isDiagnosisFailed(run, job)) {
        const failureMessage = getDiagnosisFailureMessage(run, job);
        finishTimingPhase('diagnosis', 'failed', failureMessage);
        setDiagnosisError(failureMessage);
        setFlowError(failureMessage);
        setStep('FAILED');
        setDiagnosisRunId(null);
        setIsUploading(false);
        return true;
      }

      return false;
    },
    [completeDiagnosis, finishTimingPhase, setDiagnosisRunId, setStep],
  );

  // Poll Document
  const { data: polledDoc } = useAsyncJob<DiagnosisDocumentStatus>({
    url: activeDocumentId ? `/api/v1/documents/${activeDocumentId}` : null,
    isTerminal: (doc) => PARSE_TERMINAL_STATUSES.has(doc.status),
    enabled: step === 'ANALYSING' && !!activeDocumentId,
    onSuccess: (doc) => {
      triggerInlineParseProcessing(doc);
    },
  });

  useEffect(() => {
    if (!polledDoc || step !== 'ANALYSING') return;
    triggerInlineParseProcessing(polledDoc);

    // Update granular phase notes from metadata stages
    const stages = polledDoc.parse_metadata?.stages;
    if (stages) {
      if (stages.quality?.status === 'success') setTimingPhase('parse', { note: '데이터 정밀 검수 완료' });
      else if (stages.normalize?.status === 'success') setTimingPhase('parse', { note: '학생부 포맷 정규화 완료' });
      else if (stages.segment?.status === 'success') setTimingPhase('parse', { note: '항목별 단락 구분 완료' });
      else if (stages.classify?.status === 'success') setTimingPhase('parse', { note: '문서 카테고리 분류 완료' });
      else if (stages.extract?.status === 'success') setTimingPhase('parse', { note: '기본 텍스트 추출 완료' });
      else if (stages.start?.status === 'success') setTimingPhase('parse', { note: '학생부 분석을 시작합니다' });

      // Check for partial failure warning
      const failedStage = Object.entries(stages).find(([_, s]) => s.status === 'failed');
      if (failedStage) {
        // We don't fail immediately here if extract (Stage 1) is success, 
        // because document_service already decided whether it's a terminal failure or a warning.
      }
    }

    if (PARSE_TERMINAL_STATUSES.has(polledDoc.status)) {
      if (polledDoc.latest_async_job_id) {
        parseProcessKickoffRef.current.delete(polledDoc.latest_async_job_id);
      }

      const isActuallySuccess = PARSE_SUCCESS_STATUSES.has(polledDoc.status);
      const extractionSucceeded = stages?.extract?.status === 'success' || hasDocumentContent(polledDoc);

      if (!isActuallySuccess && !extractionSucceeded) {
        const parseError = polledDoc.latest_async_job_error || polledDoc.last_error || '문서 분석에 실패했습니다.';
        finishTimingPhase('parse', 'failed', parseError);
        setDiagnosisError(parseError);
        setFlowError(parseError);
        setStep('FAILED');
        setIsUploading(false);
      } else if (!extractionSucceeded) {
        const emptyError = '진단 가능한 텍스트를 찾지 못했습니다.';
        finishTimingPhase('parse', 'failed', emptyError);
        setDiagnosisError(emptyError);
        setFlowError(emptyError);
        setStep('FAILED');
        setIsUploading(false);
      } else {
        // success or partial success with usable text
        const hasPartialFailure = stages && Object.values(stages).some(s => s.status === 'failed');
        const successNote = hasPartialFailure 
          ? '분석 완료 (일부 고급 기능 생략)' 
          : (polledDoc.page_count ? `분석 완료 (${polledDoc.page_count}쪽)` : '분석 완료');
          
        finishTimingPhase('parse', 'done', successNote);
        beginTimingPhase('diagnosis', '인공지능 진단 생성 중');
        startDiagnosisForProject(polledDoc.project_id);
      }
    }
  }, [polledDoc, step, finishTimingPhase, beginTimingPhase, startDiagnosisForProject, setStep, setTimingPhase]);

  // Poll Diagnosis Run
  const { data: polledRun } = useAsyncJob<DiagnosisRunResponse>({
    url: diagnosisRunId ? `/api/v1/diagnosis/${diagnosisRunId}` : null,
    isTerminal: (run) => isDiagnosisComplete(run) || isDiagnosisFailed(run, null),
    enabled: step === 'ANALYSING' && !!diagnosisRunId,
  });

  useEffect(() => {
    if (!polledRun || step !== 'ANALYSING') return;
    void syncDiagnosisRun(polledRun.id);
  }, [polledRun, step, syncDiagnosisRun]);

  // Poll Report
  const { data: polledReportRun } = useAsyncJob<DiagnosisRunResponse>({
    url: step === 'RESULT' && diagnosisRun?.id ? `/api/v1/diagnosis/${diagnosisRun.id}` : null,
    isTerminal: (run) => {
      const status = (run.report_status || run.report_async_job_status || '').toUpperCase();
      return status === 'READY' || status === 'FAILED';
    },
    enabled: step === 'RESULT' && !!diagnosisRun?.id && (diagnosisRun.report_status !== 'READY'),
    intervalMs: 3000,
  });

  useEffect(() => {
    if (polledReportRun) setDiagnosisRun(polledReportRun);
  }, [polledReportRun]);

  const onDrop = useCallback(
    async (acceptedFiles: File[]) => {
      const file = acceptedFiles[0];
      if (!file) return;
      if (file.size > MAX_UPLOAD_BYTES) {
        toast.error('파일 용량이 50MB를 초과하여 업로드할 수 없습니다.');
        return;
      }

      setDiagnosisResult(null);
      setDiagnosisRun(null);
      setDiagnosisJob(null);
      setDiagnosisRunId(null);
      setDiagnosisError(null);
      setFlowError(null);
      resetTimingPhases();
      setIsUploading(true);
      const loadingId = toast.loading('생활기록부 파일 업로드와 진단 준비를 진행 중입니다...');

      try {
        beginTimingPhase('upload', '파일 업로드 진행 중');
        const formData = new FormData();
        formData.append('file', file);
        const mainGoal = goalList[0];
        if (mainGoal) {
          formData.append('target_university', mainGoal.university);
          formData.append('target_major', mainGoal.major);
          formData.append('title', `${mainGoal.university} ${mainGoal.major} 진단`);
        }

        const uploadRes = await api.post<{ project_id: string; id: string }>('/api/v1/documents/upload', formData);
        setProjectId(uploadRes.project_id);
        finishTimingPhase('upload', 'done', `업로드 완료 (${(file.size / (1024 * 1024)).toFixed(1)}MB)`);

        beginTimingPhase('parse', '기록 내용을 꼼꼼히 읽고 있어요');
        setStep('ANALYSING');
        
        const parseUrl = useSynchronousApiJobs
          ? `/api/v1/documents/${uploadRes.id}/parse?wait_for_completion=true`
          : `/api/v1/documents/${uploadRes.id}/parse`;
        
        const parseStarted = await api.post<DiagnosisDocumentStatus>(parseUrl);
        setActiveDocumentId(uploadRes.id);
        triggerInlineParseProcessing(parseStarted);

        toast.success('진단 실행이 시작되었습니다.', { id: loadingId });
      } catch (error: any) {
        const failureMessage = getApiErrorMessage(error, '진단 실행에 실패했습니다. 잠시 후 다시 시도해 주세요.');
        failRunningTimingPhases(failureMessage);
        setDiagnosisError(failureMessage);
        setFlowError(failureMessage);
        setStep('FAILED');
        toast.error(failureMessage, { id: loadingId });
        setIsUploading(false);
      }
    },
    [beginTimingPhase, failRunningTimingPhases, finishTimingPhase, goalList, resetTimingPhases, setActiveDocumentId, setProjectId, setStep, triggerInlineParseProcessing, useSynchronousApiJobs],
  );

  const { getRootProps, getInputProps, isDragActive, open } = useDropzone({
    onDrop,
    accept: { 'application/pdf': ['.pdf'] },
    multiple: false,
    disabled: isUploading,
    noClick: true,
  });

  const retryDiagnosis = useCallback(async () => {
    if (!diagnosisRun?.async_job_id || isRetryingDiagnosis) return;
    setIsRetryingDiagnosis(true);
    try {
      beginTimingPhase('diagnosis', '진단 재시도 진행 중');
      const retried = await api.post<AsyncJobRead>(`/api/v1/jobs/${diagnosisRun.async_job_id}/retry`);
      setDiagnosisJob(retried);
      setDiagnosisError(null);
      setFlowError(null);
      setStep('ANALYSING');

      if (useSynchronousApiJobs) {
        await api.post<AsyncJobRead>(`/api/v1/jobs/${retried.id}/process`);
        await syncDiagnosisRun(diagnosisRun.id);
        setDiagnosisRunId(null);
        toast.success('재시도를 즉시 처리했습니다.');
      } else {
        setDiagnosisRunId(diagnosisRun.id);
        triggerInlineDiagnosisProcessing(retried.id);
        toast.success('재시도를 요청했습니다.');
      }
    } catch (error) {
      finishTimingPhase('diagnosis', 'failed', '진단 재시도 요청 실패');
      toast.error('재시도 요청에 실패했습니다.');
    } finally {
      setIsRetryingDiagnosis(false);
    }
  }, [beginTimingPhase, diagnosisRun, finishTimingPhase, isRetryingDiagnosis, setDiagnosisRunId, setStep, syncDiagnosisRun, triggerInlineDiagnosisProcessing, useSynchronousApiJobs]);

  const stepItems = [
    { id: 'profile', label: '프로필 설정', description: '기본 정보 입력', state: step === 'PROFILE' ? 'active' : ['GOALS', 'UPLOAD', 'ANALYSING', 'RESULT', 'FAILED'].includes(step) ? 'done' : 'pending' },
    { id: 'goals', label: '목표 설정', description: '지원 목표 확정', state: step === 'GOALS' ? 'active' : ['UPLOAD', 'ANALYSING', 'RESULT', 'FAILED'].includes(step) ? 'done' : 'pending' },
    { id: 'upload', label: '기록 업로드', description: '학생부 파일 제출', state: step === 'UPLOAD' ? 'active' : ['ANALYSING', 'RESULT', 'FAILED'].includes(step) ? 'done' : 'pending' },
    { id: 'analysis', label: '진단 실행', description: '근거 기반 분석', state: step === 'ANALYSING' ? 'active' : step === 'RESULT' ? 'done' : step === 'FAILED' ? 'error' : 'pending' },
    { id: 'result', label: '결과 검토', description: '워크숍 진입', state: step === 'RESULT' ? 'active' : 'pending' },
  ] as any;

  const onStepClick = (stepId: string) => {
    const mapping: Record<string, DiagnosisStep> = {
      profile: 'PROFILE',
      goals: 'GOALS',
      upload: 'UPLOAD',
      analysis: 'ANALYSING',
      result: 'RESULT',
    };
    const nextStep = mapping[stepId];
    if (nextStep) setStep(nextStep);
  };

  const headerTitle = useMemo(() => {
    switch (step) {
      case 'PROFILE': return '학생 프로필 설정';
      case 'GOALS': return '목표 대학교 진단';
      case 'UPLOAD': return '생활기록부 업로드';
      case 'ANALYSING': return '인공지능 정밀 분석 중';
      case 'RESULT': return '인공지능 진단 결과';
      case 'FAILED': return '진단 분석 실패';
      default: return '진단 서비스';
    }
  }, [step]);

  const headerDescription = useMemo(() => {
    switch (step) {
      case 'PROFILE': return '보다 정확한 진단을 위해 학년과 계열을 설정해 주세요.';
      case 'GOALS': return '희망하는 대학교와 학과를 선택해 주세요. 목표에 맞춘 정밀 진단을 시작합니다.';
      case 'UPLOAD': return '분석을 위해 본인의 생활기록부 파일을 업로드해 주세요.';
      case 'ANALYSING': return '기록된 내용을 바탕으로 대학별 합격 가능성과 강점을 분석하고 있습니다.';
      case 'RESULT': return '분석이 완료되었습니다. 결과 리포트와 추천 워크숍 내용을 확인하세요.';
      case 'FAILED': return '분석 과정에서 문제가 발생했습니다. 내용을 확인하고 다시 시도해 주세요.';
      default: return '사용자 맞춤형 대학 입시 진단 서비스입니다.';
    }
  }, [step]);

  return (
    <div className="mx-auto max-w-6xl space-y-8 py-8 animate-in fade-in duration-700">
      <div className="relative overflow-hidden rounded-[2.5rem] bg-gradient-to-br from-[#004aad] to-[#0070f3] p-8 md:p-12 shadow-2xl shadow-blue-500/20">
        <div className="relative z-10 space-y-4">
          <div className="inline-flex items-center gap-2 rounded-full bg-white/10 px-4 py-1.5 backdrop-blur-md ring-1 ring-white/20">
            <Sparkles size={14} className="text-cyan-300" />
            <span className="text-sm font-bold tracking-tight text-cyan-50">프리미엄 인공지능 분석</span>
          </div>
          <h1 className="text-4xl font-black tracking-tight text-white md:text-5xl lg:leading-[1.15]">{headerTitle}</h1>
          <p className="max-w-2xl text-lg font-medium leading-relaxed text-blue-100/80">{headerDescription}</p>
        </div>
      </div>

      <div className="px-4">
        <StepIndicator items={stepItems} onStepClick={onStepClick} />
      </div>

      {(step === 'ANALYSING' || (step === 'UPLOAD' && isUploading)) && (
        <ProcessTimingDashboard
          phases={Object.entries(timingPhases).map(([key, p]) => ({ 
            id: key, 
            label: p.note || '', 
            status: p.status, 
            startedAt: p.startedAt, 
            finishedAt: p.finishedAt 
          }))}
          title="실시간 진단 현황"
          description="데이터 마스킹과 정밀 분석이 실시간으로 진행 중입니다"
          preferStageMode
          stageMessage={diagnosisRun?.status_message || diagnosisJob?.progress_message || null}
        />
      )}

      <AnimatePresence mode="wait">
        {step === 'PROFILE' && <DiagnosisProfile />}

        {step === 'GOALS' && <DiagnosisGoals />}

        {step === 'UPLOAD' && (
          <DiagnosisUpload
            getRootProps={getRootProps}
            getInputProps={getInputProps}
            isDragActive={isDragActive}
            isUploading={isUploading}
            handleOpenFileDialog={() => open()}
            handleDropzoneKeyDown={() => open()}
            setStep={setStep}
            flowError={flowError}
          />
        )}

        {step === 'ANALYSING' && (
          <motion.div key="analysing" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} className="space-y-6">
            <WorkflowNotice tone="loading" title="분석 진행 중" description="잠시만 기다려 주세요..." />
            <AsyncJobStatusCard
              job={diagnosisJob}
              runStatus={diagnosisRun?.status}
              runStatusMessage={diagnosisRun?.status_message || null}
              errorMessage={diagnosisRun?.error_message}
            />
          </motion.div>
        )}

        {step === 'FAILED' && (
          <motion.div key="failed" initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} className="space-y-6">
            <WorkflowNotice tone="danger" title="진단 실패" description={flowError || diagnosisError || '오류가 발생했습니다.'} />
            <div className="flex justify-center gap-2">
              <SecondaryButton onClick={() => setStep('UPLOAD')}>업로드로 돌아가기</SecondaryButton>
              <PrimaryButton onClick={retryDiagnosis} disabled={isRetryingDiagnosis}>재시도</PrimaryButton>
            </div>
          </motion.div>
        )}

        {step === 'RESULT' && diagnosisResult && (
          <motion.div key="result-view" initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} className="space-y-8">
            <DiagnosisResultDisplay diagnosisResult={diagnosisResult} diagnosisRun={diagnosisRun} />
            <div className="flex justify-center gap-2">
              <SecondaryButton onClick={() => { resetOnboarding(); void syncWithUser(user); }}>진단 새로 시작</SecondaryButton>
              <PrimaryButton onClick={() => navigate(`/app/workshop/${projectId}`)}>워크숍 시작하기 <ArrowRight size={16} /></PrimaryButton>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
