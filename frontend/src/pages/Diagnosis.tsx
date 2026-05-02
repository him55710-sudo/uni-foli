import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { motion, AnimatePresence } from 'motion/react';
import { useDropzone } from 'react-dropzone';
import { ArrowRight } from 'lucide-react';
import toast from 'react-hot-toast';

import { useAuthStore } from '../store/authStore';
import { useOnboardingStore } from '../store/onboardingStore';
import { api, shouldUseSynchronousApiJobs } from '../lib/api';
import { type ApiErrorInfo, getApiErrorInfo, getApiErrorMessage } from '../lib/apiError';
import { ProcessTimingDashboard, type TimingPhaseStatus } from '../components/ProcessTimingDashboard';
import type { AsyncJobRead, DiagnosisResultPayload, DiagnosisRunResponse } from '../types/api';
import {
  DIAGNOSIS_STORAGE_KEY,
  getDiagnosisFailureMessage,
  isDiagnosisComplete,
  isDiagnosisFailed,
  mergeDiagnosisPayload,
} from '../lib/diagnosis';
import {
  isDiagnosisProjectNotFound,
  resolveDiagnosisHydrationDecision,
  resolvePreferredDiagnosisProjectId,
  selectLatestDiagnosisProjectDocument,
  shouldApplyDiagnosisResource,
  type DiagnosisProjectDocumentSummary,
} from '../lib/diagnosisProjectContext';
import {
  PageHeader,
  PrimaryButton,
  SecondaryButton,
  StatusBadge,
  StepIndicator,
  WorkflowNotice,
} from '../components/primitives';
import { AsyncJobStatusCard } from '../components/AsyncJobStatusCard';
import { useAsyncJob } from '../hooks/useAsyncJob';
import { TERMINAL_STATUSES, SUCCESS_STATUSES, type DocumentStatus } from '../types/domain';
import { DiagnosisProfile } from '../components/diagnosis/DiagnosisProfile';
import { DiagnosisUpload } from '../components/diagnosis/DiagnosisUpload';
import { DiagnosisResultDisplay } from '../components/diagnosis/DiagnosisResultDisplay';
import { DiagnosisReportPanel } from '../components/DiagnosisReportPanel';

const DiagnosisGoals = React.lazy(() =>
  import('../components/diagnosis/DiagnosisGoals').then((module) => ({ default: module.DiagnosisGoals })),
);

type DiagnosisStep = 'PROFILE' | 'GOALS' | 'UPLOAD' | 'ANALYSING' | 'RESULT' | 'FAILED';
type TimingPhaseKey = 'upload' | 'parse' | 'diagnosis';

const MAX_UPLOAD_BYTES = 50 * 1024 * 1024;
const INVALID_PROJECT_MESSAGE = '기존 프로젝트 연결이 유효하지 않아 다시 업로드가 필요합니다.';

interface DiagnosisDocumentStatus extends DiagnosisProjectDocumentSummary {
  content_text: string;
  page_count?: number;
  parse_metadata?: {
    stages?: Record<string, { status: 'pending' | 'processing' | 'success' | 'failed'; error?: string }>;
    fallback_used?: boolean;
    pipeline_version?: string;
    [key: string]: any;
  };
}

interface TimingPhaseState {
  status: TimingPhaseStatus;
  startedAt: number | null;
  finishedAt: number | null;
  note?: string;
}

type TimingPhaseMap = Record<TimingPhaseKey, TimingPhaseState>;

interface FlowDebugState {
  code?: string | null;
  detail?: string | null;
  status?: number | null;
}

function createInitialTimingPhases(): TimingPhaseMap {
  return {
    upload: { status: 'idle', startedAt: null, finishedAt: null, note: '업로드 준비 중' },
    parse: { status: 'idle', startedAt: null, finishedAt: null, note: '문서 분석 준비 중' },
    diagnosis: { status: 'idle', startedAt: null, finishedAt: null, note: '진단 준비 중' },
  };
}

function toFlowDebugState(failure: ApiErrorInfo): FlowDebugState {
  return {
    code: failure.debugCode,
    detail: failure.debugDetail,
    status: failure.status,
  };
}

export function Diagnosis() {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
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
    clearActiveProjectContext,
    resetOnboarding,
    syncWithUser,
  } = useOnboardingStore();

  const step = diagnosisStep as DiagnosisStep;
  const setStep = setDiagnosisStep;
  const useSynchronousApiJobs = shouldUseSynchronousApiJobs();

  const diagnosisProcessKickoffRef = useRef<Set<string>>(new Set());
  const parseProcessKickoffRef = useRef<Set<string>>(new Set());
  const hydratedProjectKeyRef = useRef<string | null>(null);
  const diagnosisAutoStartKeyRef = useRef<string | null>(null);

  const [isUploading, setIsUploading] = useState(false);
  const [diagnosisResult, setDiagnosisResult] = useState<DiagnosisResultPayload | null>(null);
  const [diagnosisRun, setDiagnosisRun] = useState<DiagnosisRunResponse | null>(null);
  const [diagnosisJob, setDiagnosisJob] = useState<AsyncJobRead | null>(null);
  const [diagnosisError, setDiagnosisError] = useState<string | null>(null);
  const [isRetryingDiagnosis, setIsRetryingDiagnosis] = useState(false);
  const [flowError, setFlowError] = useState<string | null>(null);
  const [flowDebug, setFlowDebug] = useState<FlowDebugState | null>(null);
  const [timingPhases, setTimingPhases] = useState<TimingPhaseMap>(createInitialTimingPhases());

  const queryProjectId = useMemo(() => {
    const value = searchParams.get('project_id');
    if (typeof value !== 'string') return null;
    const normalized = value.trim();
    return normalized || null;
  }, [searchParams]);

  const preferredProjectId = useMemo(
    () => resolvePreferredDiagnosisProjectId(queryProjectId, projectId),
    [projectId, queryProjectId],
  );

  const preferredProjectKey = useMemo(() => {
    if (!preferredProjectId) return null;
    const userKey = [user?.id, user?.firebase_uid].filter(Boolean).join(':') || 'anonymous';
    return `${userKey}:${preferredProjectId}`;
  }, [preferredProjectId, user?.firebase_uid, user?.id]);

  const shouldHydratePreferredProject = useMemo(
    () => Boolean(
      preferredProjectId &&
      (queryProjectId || (!activeDocumentId && !diagnosisRunId && !diagnosisRun && !diagnosisResult)),
    ),
    [activeDocumentId, diagnosisResult, diagnosisRun, diagnosisRunId, preferredProjectId, queryProjectId],
  );

  useEffect(() => {
    if (user) void syncWithUser(user);
  }, [syncWithUser, user]);

  useEffect(() => {
    if (!preferredProjectKey) {
      hydratedProjectKeyRef.current = null;
    }
  }, [preferredProjectKey]);

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

  const clearProjectQueryParam = useCallback(() => {
    if (!queryProjectId) return;
    const nextSearchParams = new URLSearchParams(searchParams);
    nextSearchParams.delete('project_id');
    setSearchParams(nextSearchParams, { replace: true });
  }, [queryProjectId, searchParams, setSearchParams]);

  const recoverFromInvalidProject = useCallback((message = INVALID_PROJECT_MESSAGE) => {
    clearActiveProjectContext();
    setDiagnosisResult(null);
    setDiagnosisRun(null);
    setDiagnosisJob(null);
    setDiagnosisError(null);
    setFlowError(message);
    setFlowDebug(null);
    setIsRetryingDiagnosis(false);
    setIsUploading(false);
    resetTimingPhases();
    setStep('UPLOAD');
    diagnosisAutoStartKeyRef.current = null;
    clearProjectQueryParam();
    toast.error(message);
  }, [clearActiveProjectContext, clearProjectQueryParam, resetTimingPhases, setStep]);

  const applyFailureState = useCallback((params: {
    message: string;
    debug?: FlowDebugState | null;
    phase?: TimingPhaseKey | null;
    clearRunId?: boolean;
  }) => {
    if (params.phase) {
      finishTimingPhase(params.phase, 'failed', params.message);
    }
    setDiagnosisError(params.message);
    setFlowError(params.message);
    setFlowDebug(params.debug ?? null);
    setStep('FAILED');
    if (params.clearRunId ?? true) {
      setDiagnosisRunId(null);
    }
    setIsUploading(false);
  }, [finishTimingPhase, setDiagnosisRunId, setStep]);

  const triggerInlineDiagnosisProcessing = useCallback((jobId: string) => {
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
  }, []);

  const triggerInlineParseProcessing = useCallback(
    (document: Pick<DiagnosisProjectDocumentSummary, 'latest_async_job_id' | 'latest_async_job_status'> | null | undefined) => {
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

  const hasDocumentContent = useCallback((document: DiagnosisDocumentStatus) => Boolean(document.content_text?.trim()), []);

  const completeDiagnosis = useCallback((run: DiagnosisRunResponse) => {
    const payload = mergeDiagnosisPayload(run);
    if (!payload) return false;

    if (run.async_job_id) {
      diagnosisProcessKickoffRef.current.delete(run.async_job_id);
    }

    finishTimingPhase('diagnosis', 'done', '진단 생성 완료');
    setProjectId(run.project_id);
    setDiagnosisRun(run);
    setDiagnosisJob(null);
    setDiagnosisResult(payload);
    setDiagnosisError(null);
    setFlowError(null);
    setFlowDebug(null);
    setStep('RESULT');
    setDiagnosisRunId(null);
    setIsUploading(false);

    const primaryGoal = goalList[0];
    if (primaryGoal?.university && primaryGoal?.major) {
      localStorage.setItem(
        DIAGNOSIS_STORAGE_KEY,
        JSON.stringify({
          major: primaryGoal.major,
          targetUniversity: primaryGoal.university,
          targetMajor: primaryGoal.major,
          target_university: primaryGoal.university,
          target_major: primaryGoal.major,
          projectId: run.project_id,
          diagnosisRunId: run.id,
          reportStatus: run.report_status ?? run.report_async_job_status ?? null,
          reportArtifactId: run.report_artifact_id ?? null,
          reportErrorMessage: run.report_error_message ?? null,
          savedAt: new Date().toISOString(),
          diagnosis: payload,
        }),
      );
    }

    return true;
  }, [finishTimingPhase, goalList, setDiagnosisRunId, setProjectId, setStep]);

  const startDiagnosisForProject = useCallback(async (activeProjectId: string): Promise<boolean> => {
    try {
      const diagnosisUrl = useSynchronousApiJobs
        ? '/api/v1/diagnosis/run?wait_for_completion=true'
        : '/api/v1/diagnosis/run';
      const others = goalList.slice(1).map((goal) => `${goal.university} (${goal.major})`);
      const run = await api.post<DiagnosisRunResponse>(diagnosisUrl, {
        project_id: activeProjectId,
        interest_universities: others,
      });

      setProjectId(activeProjectId);
      setDiagnosisRun(run);
      setDiagnosisJob(null);

      if (isDiagnosisComplete(run)) {
        return completeDiagnosis(run);
      }

      if (isDiagnosisFailed(run, null)) {
        applyFailureState({
          message: getDiagnosisFailureMessage(run, null),
          phase: 'diagnosis',
        });
        return false;
      }

      setDiagnosisRunId(run.id);
      if (run.async_job_id) {
        triggerInlineDiagnosisProcessing(run.async_job_id);
      }
      return true;
    } catch (error) {
      const failure = getApiErrorInfo(error, '진단 실행에 실패했습니다. 잠시 후 다시 시도해 주세요.');
      if (isDiagnosisProjectNotFound(failure)) {
        recoverFromInvalidProject();
        return false;
      }
      applyFailureState({
        message: failure.userMessage,
        debug: toFlowDebugState(failure),
        phase: 'diagnosis',
      });
      return false;
    }
  }, [
    applyFailureState,
    completeDiagnosis,
    goalList,
    recoverFromInvalidProject,
    setDiagnosisRunId,
    setProjectId,
    triggerInlineDiagnosisProcessing,
    useSynchronousApiJobs,
  ]);

  const syncDiagnosisRun = useCallback(async (runId: string) => {
    try {
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
          applyFailureState({
            message: '진단 결과를 불러오지 못했습니다. 다시 시도해 주세요.',
            phase: 'diagnosis',
            debug: null,
          });
        }
        return true;
      }

      if (isDiagnosisFailed(run, job)) {
        applyFailureState({
          message: getDiagnosisFailureMessage(run, job),
          phase: 'diagnosis',
          debug: null,
        });
        return true;
      }

      return false;
    } catch (error) {
      const failure = getApiErrorInfo(error, '진단 상태를 확인하는 중 문제가 발생했습니다. 잠시 후 다시 시도해 주세요.');
      if (isDiagnosisProjectNotFound(failure)) {
        recoverFromInvalidProject();
        return true;
      }
      applyFailureState({
        message: failure.userMessage,
        debug: toFlowDebugState(failure),
        phase: 'diagnosis',
      });
      return true;
    }
  }, [applyFailureState, completeDiagnosis, recoverFromInvalidProject]);

  useEffect(() => {
    if (!preferredProjectId || !preferredProjectKey || !shouldHydratePreferredProject) return;
    if (hydratedProjectKeyRef.current === preferredProjectKey) return;

    hydratedProjectKeyRef.current = preferredProjectKey;
    let cancelled = false;

    const hydrateProjectContext = async () => {
      try {
        await api.get<{ id: string }>(`/api/v1/projects/${preferredProjectId}`);
        const documents = await api.get<DiagnosisProjectDocumentSummary[]>(`/api/v1/projects/${preferredProjectId}/documents`);

        let latestRun: DiagnosisRunResponse | null = null;
        try {
          latestRun = await api.get<DiagnosisRunResponse>(`/api/v1/diagnosis/project/${preferredProjectId}/latest`);
        } catch (latestRunError) {
          const latestRunFailure = getApiErrorInfo(latestRunError, '');
          if (latestRunFailure.status !== 404) {
            throw latestRunError;
          }
        }

        if (cancelled) return;

        const latestDocument = selectLatestDiagnosisProjectDocument(documents);
        const decision = resolveDiagnosisHydrationDecision({
          latestRun,
          latestDocument,
        });

        setProjectId(preferredProjectId);
        setActiveDocumentId(decision.activeDocumentId);
        setDiagnosisRunId(decision.activeDiagnosisRunId);
        setDiagnosisError(decision.flowError);
        setFlowError(decision.flowError);
        setFlowDebug(null);
        setIsUploading(false);

        if (decision.mode === 'run_completed' && latestRun) {
          completeDiagnosis(latestRun);
          return;
        }

        if (decision.mode === 'run_failed' && latestRun) {
          setDiagnosisRun(latestRun);
          setDiagnosisJob(null);
          setDiagnosisResult(null);
          setStep('FAILED');
          return;
        }

        if (decision.mode === 'run_in_progress' && latestRun) {
          setDiagnosisRun(latestRun);
          setDiagnosisJob(null);
          setDiagnosisResult(null);
          setStep('ANALYSING');
          if (latestRun.async_job_id) {
            triggerInlineDiagnosisProcessing(latestRun.async_job_id);
          }
          void syncDiagnosisRun(latestRun.id);
          return;
        }

        if (decision.mode === 'document_failed') {
          setDiagnosisRun(null);
          setDiagnosisJob(null);
          setDiagnosisResult(null);
          setStep('FAILED');
          return;
        }

        if (decision.mode === 'document_in_progress' && latestDocument) {
          setDiagnosisRun(null);
          setDiagnosisJob(null);
          setDiagnosisResult(null);
          setStep('ANALYSING');
          triggerInlineParseProcessing(latestDocument);
          return;
        }

        if (decision.mode === 'start_diagnosis' && latestDocument) {
          const autoStartKey = `${preferredProjectId}:${latestDocument.id}`;
          if (diagnosisAutoStartKeyRef.current === autoStartKey) return;

          diagnosisAutoStartKeyRef.current = autoStartKey;
          setDiagnosisRun(null);
          setDiagnosisJob(null);
          setDiagnosisResult(null);
          setStep('ANALYSING');
          beginTimingPhase('diagnosis', '기존 문서를 기준으로 진단을 다시 시작하고 있습니다.');
          await startDiagnosisForProject(preferredProjectId);
          return;
        }

        setDiagnosisRun(null);
        setDiagnosisJob(null);
        setDiagnosisResult(null);
        setStep(decision.step);
      } catch (error) {
        if (cancelled) return;

        const failure = getApiErrorInfo(error, '프로젝트 정보를 불러오는 중 문제가 발생했습니다. 잠시 후 다시 시도해 주세요.');
        if (isDiagnosisProjectNotFound(failure)) {
          recoverFromInvalidProject();
          return;
        }

        setDiagnosisResult(null);
        setDiagnosisRun(null);
        setDiagnosisJob(null);
        setDiagnosisError(failure.userMessage);
        setFlowError(failure.userMessage);
        setFlowDebug(toFlowDebugState(failure));
        setStep('FAILED');
        setDiagnosisRunId(null);
        setIsUploading(false);
      }
    };

    void hydrateProjectContext();

    return () => {
      cancelled = true;
    };
  }, [
    beginTimingPhase,
    completeDiagnosis,
    preferredProjectId,
    preferredProjectKey,
    recoverFromInvalidProject,
    setActiveDocumentId,
    setDiagnosisRunId,
    setProjectId,
    setStep,
    shouldHydratePreferredProject,
    startDiagnosisForProject,
    syncDiagnosisRun,
    triggerInlineDiagnosisProcessing,
    triggerInlineParseProcessing,
  ]);

  const { data: polledDoc } = useAsyncJob<DiagnosisDocumentStatus>({
    url: activeDocumentId ? `/api/v1/documents/${activeDocumentId}` : null,
    isTerminal: (document) => TERMINAL_STATUSES.has(document.status),
    enabled: step === 'ANALYSING' && Boolean(activeDocumentId),
    onSuccess: (document) => {
      triggerInlineParseProcessing(document);
    },
  });

  useEffect(() => {
    if (!polledDoc || step !== 'ANALYSING') return;
    if (!shouldApplyDiagnosisResource(polledDoc.id, activeDocumentId)) return;

    triggerInlineParseProcessing(polledDoc);

    const stages = polledDoc.parse_metadata?.stages;
    if (stages) {
      if (stages.quality?.status === 'success') setTimingPhase('parse', { note: '품질 검사 완료' });
      else if (stages.normalize?.status === 'success') setTimingPhase('parse', { note: '문서 정규화 완료' });
      else if (stages.segment?.status === 'success') setTimingPhase('parse', { note: '항목 분리 완료' });
      else if (stages.classify?.status === 'success') setTimingPhase('parse', { note: '문서 분류 완료' });
      else if (stages.extract?.status === 'success') setTimingPhase('parse', { note: '텍스트 추출 완료' });
      else if (stages.start?.status === 'success') setTimingPhase('parse', { note: '문서 분석을 시작했습니다.' });
    }

    if (!TERMINAL_STATUSES.has(polledDoc.status)) return;

    if (polledDoc.latest_async_job_id) {
      parseProcessKickoffRef.current.delete(polledDoc.latest_async_job_id);
    }

    const extractionSucceeded = stages?.extract?.status === 'success' || hasDocumentContent(polledDoc);
    const hasSuccessfulStatus = SUCCESS_STATUSES.has(polledDoc.status);

    if (!hasSuccessfulStatus && !extractionSucceeded) {
      applyFailureState({
        message: polledDoc.latest_async_job_error || polledDoc.last_error || '문서 분석에 실패했습니다.',
        phase: 'parse',
        debug: null,
      });
      return;
    }

    if (!extractionSucceeded) {
      applyFailureState({
        message: '진단에 사용할 수 있는 텍스트를 찾지 못했습니다.',
        phase: 'parse',
        debug: null,
      });
      return;
    }

    const hasPartialFailure = Boolean(stages && Object.values(stages).some((stage) => stage.status === 'failed'));
    const successNote = hasPartialFailure
      ? '분석 완료 (일부 고급 단계는 생략됨)'
      : (polledDoc.page_count ? `분석 완료 (${polledDoc.page_count}페이지)` : '분석 완료');

    finishTimingPhase('parse', 'done', successNote);
    beginTimingPhase('diagnosis', '진단을 생성하고 있습니다.');
    void startDiagnosisForProject(polledDoc.project_id);
  }, [
    activeDocumentId,
    applyFailureState,
    beginTimingPhase,
    finishTimingPhase,
    hasDocumentContent,
    polledDoc,
    setTimingPhase,
    startDiagnosisForProject,
    step,
    triggerInlineParseProcessing,
  ]);

  const { data: polledRun } = useAsyncJob<DiagnosisRunResponse>({
    url: diagnosisRunId ? `/api/v1/diagnosis/${diagnosisRunId}` : null,
    isTerminal: (run) => isDiagnosisComplete(run) || isDiagnosisFailed(run, null),
    enabled: step === 'ANALYSING' && Boolean(diagnosisRunId),
  });

  useEffect(() => {
    if (!polledRun || step !== 'ANALYSING') return;
    if (!shouldApplyDiagnosisResource(polledRun.id, diagnosisRunId)) return;
    
    // Task 3: Sync timingPhases with Job phase
    if (diagnosisJob) {
      const jobPhase = (diagnosisJob as any).phase;
      const jobMsg = diagnosisJob.progress_message;
      
      if (jobPhase === 'diagnosis') {
        setTimingPhases(prev => ({
          ...prev,
          parse: { ...prev.parse, status: 'done', finishedAt: prev.parse.finishedAt || Date.now() },
          diagnosis: { ...prev.diagnosis, status: 'running', note: jobMsg || prev.diagnosis.note }
        }));
      } else if (jobPhase === 'report') {
        setTimingPhases(prev => ({
          ...prev,
          parse: { ...prev.parse, status: 'done' },
          diagnosis: { ...prev.diagnosis, status: 'done', finishedAt: prev.diagnosis.finishedAt || Date.now() }
        }));
      }
    }

    void syncDiagnosisRun(polledRun.id);
  }, [diagnosisRunId, polledRun, step, syncDiagnosisRun, diagnosisJob]);

  const { data: polledReportRun } = useAsyncJob<DiagnosisRunResponse>({
    url: step === 'RESULT' && diagnosisRun?.id ? `/api/v1/diagnosis/${diagnosisRun.id}` : null,
    isTerminal: (run) => {
      const status = (run.report_status || run.report_async_job_status || '').toUpperCase();
      return status === 'READY' || status === 'FAILED';
    },
    enabled: step === 'RESULT' && Boolean(diagnosisRun?.id) && diagnosisRun.report_status !== 'READY',
    intervalMs: 3000,
  });

  useEffect(() => {
    if (!polledReportRun || !shouldApplyDiagnosisResource(polledReportRun.id, diagnosisRun?.id)) return;
    setDiagnosisRun(polledReportRun);
  }, [diagnosisRun?.id, polledReportRun]);

  const onDrop = useCallback(async (acceptedFiles: File[]) => {
    const file = acceptedFiles[0];
    if (!file) return;

    if (file.size > MAX_UPLOAD_BYTES) {
      toast.error('파일 용량이 50MB를 초과했습니다.');
      return;
    }

    clearProjectQueryParam();
    clearActiveProjectContext();
    hydratedProjectKeyRef.current = null;
    diagnosisAutoStartKeyRef.current = null;
    setDiagnosisResult(null);
    setDiagnosisRun(null);
    setDiagnosisJob(null);
    setDiagnosisRunId(null);
    setDiagnosisError(null);
    setFlowError(null);
    setFlowDebug(null);
    resetTimingPhases();
    setIsUploading(true);

    const loadingId = toast.loading('학생부 파일을 업로드하고 있습니다...');

    try {
      beginTimingPhase('upload', '서버 상태를 확인하고 있습니다.');
      try {
        await api.getBackendReadiness();
      } catch (readinessError) {
        const failure = getApiErrorInfo(readinessError, '백엔드 서버 준비 상태 확인에 실패했습니다.');
        throw failure; // getApiErrorInfo returns an object, but we need to pass it to the catch block below
      }

      const formData = new FormData();
      setTimingPhase('upload', (prev) => ({
        ...prev,
        note: 'PDF 업로드 중',
      }));
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

      beginTimingPhase('parse', '문서를 분석하고 있습니다.');
      setStep('ANALYSING');

      const parseUrl = useSynchronousApiJobs
        ? `/api/v1/documents/${uploadRes.id}/parse?wait_for_completion=true`
        : `/api/v1/documents/${uploadRes.id}/parse`;

      const parseStarted = await api.post<DiagnosisDocumentStatus>(parseUrl);
      setActiveDocumentId(uploadRes.id);
      triggerInlineParseProcessing(parseStarted);

      toast.success('진단을 시작했습니다.', { id: loadingId });
    } catch (error: any) {
      // If error is already an ApiErrorInfo (from our readiness try-catch), use it. 
      // Otherwise, resolve it normally.
      const failure = error.userMessage && error.debugCode !== undefined
        ? (error as ApiErrorInfo)
        : getApiErrorInfo(error, '진단 실행에 실패했습니다. 잠시 후 다시 시도해 주세요.');
      
      const failureMessage = failure.userMessage;
      
      failRunningTimingPhases(failureMessage);
      setDiagnosisError(failureMessage);
      setFlowError(failureMessage);
      setFlowDebug(toFlowDebugState(failure));
      setStep('FAILED');
      toast.error(failureMessage, { id: loadingId });
      setIsUploading(false);
    }
  }, [
    beginTimingPhase,
    clearActiveProjectContext,
    clearProjectQueryParam,
    failRunningTimingPhases,
    finishTimingPhase,
    goalList,
    resetTimingPhases,
    setActiveDocumentId,
    setDiagnosisRunId,
    setProjectId,
    setStep,
    setTimingPhase,
    triggerInlineParseProcessing,
    useSynchronousApiJobs,
  ]);

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
      beginTimingPhase('diagnosis', '진단을 다시 요청하고 있습니다.');
      const retried = await api.post<AsyncJobRead>(`/api/v1/jobs/${diagnosisRun.async_job_id}/retry`);
      setDiagnosisJob(retried);
      setDiagnosisError(null);
      setFlowError(null);
      setFlowDebug(null);
      setStep('ANALYSING');

      if (useSynchronousApiJobs) {
        await api.post<AsyncJobRead>(`/api/v1/jobs/${retried.id}/process`);
        await syncDiagnosisRun(diagnosisRun.id);
        setDiagnosisRunId(null);
        toast.success('재시도를 즉시 처리했습니다.');
      } else {
        setDiagnosisRunId(diagnosisRun.id);
        triggerInlineDiagnosisProcessing(retried.id);
        toast.success('재시도 요청을 보냈습니다.');
      }
    } catch (error) {
      const failure = getApiErrorInfo(error, '진단 재시도 요청에 실패했습니다.');
      if (isDiagnosisProjectNotFound(failure)) {
        recoverFromInvalidProject();
        return;
      }
      setDiagnosisError(failure.userMessage);
      setFlowError(failure.userMessage);
      setFlowDebug(toFlowDebugState(failure));
      finishTimingPhase('diagnosis', 'failed', '진단 재시도 요청 실패');
      toast.error('재시도 요청에 실패했습니다.');
    } finally {
      setIsRetryingDiagnosis(false);
    }
  }, [
    beginTimingPhase,
    diagnosisRun,
    finishTimingPhase,
    isRetryingDiagnosis,
    recoverFromInvalidProject,
    setDiagnosisRunId,
    setStep,
    syncDiagnosisRun,
    triggerInlineDiagnosisProcessing,
    useSynchronousApiJobs,
  ]);

  const stepItems = [
    { id: 'profile', label: '프로필', state: step === 'PROFILE' ? 'active' : ['GOALS', 'UPLOAD', 'ANALYSING', 'RESULT', 'FAILED'].includes(step) ? 'done' : 'pending' },
    { id: 'goals', label: '목표', state: step === 'GOALS' ? 'active' : ['UPLOAD', 'ANALYSING', 'RESULT', 'FAILED'].includes(step) ? 'done' : 'pending' },
    { id: 'upload', label: '업로드', state: step === 'UPLOAD' ? 'active' : ['ANALYSING', 'RESULT', 'FAILED'].includes(step) ? 'done' : 'pending' },
    { id: 'analysis', label: '분석', state: step === 'ANALYSING' ? 'active' : step === 'RESULT' ? 'done' : step === 'FAILED' ? 'error' : 'pending' },
    { id: 'result', label: '결과', state: step === 'RESULT' ? 'active' : 'pending' },
  ] as const;

  const onStepClick = useCallback((stepId: string) => {
    const mapping: Record<string, DiagnosisStep> = {
      profile: 'PROFILE',
      goals: 'GOALS',
      upload: 'UPLOAD',
      analysis: 'ANALYSING',
      result: 'RESULT',
    };
    const nextStep = mapping[stepId];
    if (nextStep) setStep(nextStep);
  }, [setStep]);

  const headerTitle = useMemo(() => {
    switch (step) {
      case 'PROFILE': return '진단 프로필 설정';
      case 'GOALS': return '목표 확인';
      case 'UPLOAD': return '생활기록부 업로드';
      case 'ANALYSING': return '진단 진행 중';
      case 'RESULT': return '진단 결과';
      case 'FAILED': return '진단 실패';
      default: return '학생부 진단';
    }
  }, [step]);

  const headerDescription = useMemo(() => {
    switch (step) {
      case 'PROFILE': return '학년/계열 확인';
      case 'GOALS': return '목표 전공 점검';
      case 'UPLOAD': return 'PDF 1개 업로드';
      case 'ANALYSING': return '문서 분석 중';
      case 'RESULT': return '결과 확인 후 실행';
      case 'FAILED': return '오류 확인 후 재시도';
      default: return '진단 시작';
    }
  }, [step]);

  return (
    <div className="mx-auto max-w-6xl space-y-8 py-8 animate-in fade-in duration-700">
      <PageHeader
        eyebrow="Diagnosis"
        title={headerTitle}
        description={headerDescription}
        className="border-slate-200 bg-[linear-gradient(180deg,rgba(255,255,255,0.95)_0%,rgba(243,247,255,0.92)_100%)]"
        evidence={(
          <div className="flex flex-wrap items-center gap-2">
            <StatusBadge status={step === 'FAILED' ? 'danger' : step === 'RESULT' ? 'success' : 'active'}>
              현재 단계: {step === 'ANALYSING' ? '분석' : step === 'FAILED' ? '오류' : step === 'RESULT' ? '완료' : '입력'}
            </StatusBadge>
            <StatusBadge status="neutral">목표 {goalList.length}개</StatusBadge>
            {projectId ? <StatusBadge status="neutral">프로젝트 연결됨</StatusBadge> : null}
          </div>
        )}
      />

      <div className="px-4">
        <StepIndicator items={stepItems as any} onStepClick={onStepClick} />
      </div>

      {(step === 'ANALYSING' || (step === 'UPLOAD' && isUploading)) && (
        <ProcessTimingDashboard
          phases={Object.entries(timingPhases).map(([key, phase]) => ({
            id: key,
            label: phase.note || '',
            status: phase.status,
            startedAt: phase.startedAt,
            finishedAt: phase.finishedAt,
          }))}
          title="실시간 진단 현황"
          description="업로드 · 파싱 · 진단 상태"
          preferStageMode
          stageMessage={diagnosisRun?.status_message || diagnosisJob?.progress_message || null}
        />
      )}

      <AnimatePresence mode="wait">
        {step === 'PROFILE' && <DiagnosisProfile key="profile" />}

        {step === 'GOALS' && (
          <React.Suspense
            fallback={(
              <div className="rounded-3xl border border-slate-200 bg-white p-8 text-center text-sm font-bold text-slate-500 shadow-sm">
                목표 대학과 학과 선택 화면을 준비하는 중입니다.
              </div>
            )}
          >
            <DiagnosisGoals key="goals" />
          </React.Suspense>
        )}

        {step === 'UPLOAD' && (
          <DiagnosisUpload
            key="upload"
            getRootProps={getRootProps}
            getInputProps={getInputProps}
            isDragActive={isDragActive}
            isUploading={isUploading}
            handleOpenFileDialog={() => open()}
            handleDropzoneKeyDown={() => open()}
            setStep={setStep}
            flowError={flowError}
            targetMajor={goalList[0]?.major ?? null}
          />
        )}

        {step === 'ANALYSING' && (
          <motion.div key="analysing" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} className="space-y-6">
            <WorkflowNotice tone="loading" title="분석 진행 중" description="잠시만 기다려 주세요." />
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
            {flowDebug && (flowDebug.code || flowDebug.detail || flowDebug.status != null) && (
              <div className="rounded-2xl border border-rose-200 bg-rose-50/80 p-4 text-sm text-rose-950">
                <p className="font-semibold">디버그 정보</p>
                {flowDebug.code && <p className="mt-2 font-mono">code: {flowDebug.code}</p>}
                {flowDebug.status != null && <p className="font-mono">status: {flowDebug.status}</p>}
                {flowDebug.detail && <p className="mt-2 whitespace-pre-wrap break-words font-mono text-xs">{flowDebug.detail}</p>}
              </div>
            )}
            <div className="flex justify-center gap-2">
              <SecondaryButton onClick={() => setStep('UPLOAD')}>업로드로 돌아가기</SecondaryButton>
              <PrimaryButton onClick={retryDiagnosis} disabled={isRetryingDiagnosis}>재시도</PrimaryButton>
            </div>
          </motion.div>
        )}

        {step === 'RESULT' && diagnosisResult && (
          <motion.div key="result-view" initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} className="space-y-8">
            <DiagnosisResultDisplay 
              diagnosisResult={diagnosisResult} 
              diagnosisRun={diagnosisRun} 
              projectId={projectId} 
            />
            {diagnosisRun?.id ? (
              <DiagnosisReportPanel
                diagnosisRunId={diagnosisRun.id}
                reportStatus={diagnosisRun.report_status}
                reportAsyncJobStatus={diagnosisRun.report_async_job_status}
                reportArtifactId={diagnosisRun.report_artifact_id}
                reportErrorMessage={diagnosisRun.report_error_message}
              />
            ) : null}
            <div className="flex justify-center gap-2">
              <SecondaryButton
                onClick={() => {
                  resetOnboarding();
                  if (user) void syncWithUser(user);
                }}
              >
                진단 새로 시작
              </SecondaryButton>
              <PrimaryButton
                onClick={() =>
                  navigate(`/app/workshop/${projectId}`, {
                    state: {
                      major: goalList[0]?.major,
                      chatbotMode: 'diagnosis',
                      fromDiagnosis: true,
                      diagnosisRunId: diagnosisRun?.id ?? null,
                    },
                  })
                }
              >
                워크숍 시작하기 <ArrowRight size={16} />
              </PrimaryButton>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
