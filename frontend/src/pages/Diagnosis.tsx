import React, { useCallback, useEffect, useRef, useState } from 'react';
import { AnimatePresence, motion } from 'motion/react';
import { AlertTriangle, ArrowRight, CheckCircle2, FileUp, Loader2, Plus, Trash2 } from 'lucide-react';
import { useDropzone } from 'react-dropzone';
import toast from 'react-hot-toast';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { AsyncJobStatusCard } from '../components/AsyncJobStatusCard';
import { UniversityLogo } from '../components/UniversityLogo';
import { ProcessTimingDashboard, type TimingPhaseStatus } from '../components/ProcessTimingDashboard';
import { useAuthStore } from '../store/authStore';
import { useOnboardingStore } from '../store/onboardingStore';
import { api, shouldUseSynchronousApiJobs } from '../lib/api';
import { getApiErrorMessage } from '../lib/apiError';
import { DiagnosisEvidencePanel } from '../components/DiagnosisEvidencePanel';
import { DiagnosisGuidedChoicePanel } from '../components/DiagnosisGuidedChoicePanel';
import { DiagnosisReportPanel } from '../components/DiagnosisReportPanel';
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
const MAX_UPLOAD_BYTES = 50 * 1024 * 1024;
const PARSE_POLL_INTERVAL_MS = 1500;
const PARSE_TIMEOUT_MS = 3 * 60 * 1000;

type DocumentLifecycleStatus = 'uploaded' | 'masking' | 'parsing' | 'retrying' | 'parsed' | 'partial' | 'failed';
type TimingPhaseKey = 'upload' | 'parse' | 'diagnosis';

interface DiagnosisDocumentStatus {
  id: string;
  status: DocumentLifecycleStatus;
  content_text: string;
  page_count?: number;
  latest_async_job_id?: string | null;
  latest_async_job_status?: string | null;
  parse_metadata?: {
    chunk_count?: number;
    pdf_analysis?: {
      summary?: string;
    };
  };
  latest_async_job_error?: string | null;
  last_error?: string | null;
}

interface TimingPhaseState {
  status: TimingPhaseStatus;
  startedAt: number | null;
  finishedAt: number | null;
  note?: string;
}

type TimingPhaseMap = Record<TimingPhaseKey, TimingPhaseState>;

const PARSE_SUCCESS_STATUSES = new Set<DocumentLifecycleStatus>(['parsed', 'partial']);
const PARSE_TERMINAL_STATUSES = new Set<DocumentLifecycleStatus>(['parsed', 'partial', 'failed']);

function createInitialTimingPhases(): TimingPhaseMap {
  return {
    upload: { status: 'idle', startedAt: null, finishedAt: null, note: '파일 전송' },
    parse: { status: 'idle', startedAt: null, finishedAt: null, note: '파싱/마스킹' },
    diagnosis: { status: 'idle', startedAt: null, finishedAt: null, note: 'AI 진단' },
  };
}

function hasDocumentContent(document: DiagnosisDocumentStatus): boolean {
  if (document.content_text?.trim().length > 0) return true;
  if (document.parse_metadata?.pdf_analysis?.summary?.trim()) return true;
  return false;
}

function getParseFailureMessage(document: DiagnosisDocumentStatus): string {
  if (document.latest_async_job_error) return document.latest_async_job_error;
  if (document.last_error) return document.last_error;
  return 'PDF 분석에 실패했습니다. 다른 파일로 다시 시도해 주세요.';
}

async function waitForDocumentParseResult(
  documentId: string,
  onPoll?: (document: DiagnosisDocumentStatus) => void,
): Promise<DiagnosisDocumentStatus> {
  const startedAt = Date.now();

  while (Date.now() - startedAt < PARSE_TIMEOUT_MS) {
    const document = await api.get<DiagnosisDocumentStatus>(`/api/v1/documents/${documentId}`);
    onPoll?.(document);
    if (PARSE_TERMINAL_STATUSES.has(document.status)) return document;
    await new Promise(resolve => window.setTimeout(resolve, PARSE_POLL_INTERVAL_MS));
  }

  throw new Error('문서 분석 시간이 예상보다 오래 걸리고 있어요. 잠시 뒤 다시 시도해 주세요.');
}

export function Diagnosis() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const { user } = useAuthStore();
  const { goals, setGoals, submitGoals } = useOnboardingStore();
  const preselectedProjectId = searchParams.get('project_id')?.trim() || null;
  const autoLoadedProjectRef = useRef<string | null>(null);
  const diagnosisProcessKickoffRef = useRef<Set<string>>(new Set());
  const parseProcessKickoffRef = useRef<Set<string>>(new Set());

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
  const [flowError, setFlowError] = useState<string | null>(null);
  const [showAdvancedDetails, setShowAdvancedDetails] = useState(false);
  const [timingPhases, setTimingPhases] = useState<TimingPhaseMap>(() => createInitialTimingPhases());
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
          // Allow a later retry kick if processing endpoint is temporarily unavailable.
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
          // Allow retrying a process kick if this call temporarily fails.
          kickoffCache.delete(jobId);
        });
    },
    [],
  );

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
      if (run.async_job_id) {
        diagnosisProcessKickoffRef.current.delete(run.async_job_id);
      }

      finishTimingPhase('diagnosis', 'done', '진단 생성 완료');
      setProjectId(run.project_id);
      setDiagnosisRun(run);
      setDiagnosisResult(payload);
      setDiagnosisError(null);
      setFlowError(null);
      setShowAdvancedDetails(false);
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
    [currentMajor, finishTimingPhase, goalList],
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
      if (!job && run.async_job_id) {
        triggerInlineDiagnosisProcessing(run.async_job_id);
      }
      if (job?.status === 'succeeded' || job?.status === 'failed') {
        diagnosisProcessKickoffRef.current.delete(job.id);
      }
      if (job?.status === 'queued' || job?.status === 'retrying') {
        diagnosisProcessKickoffRef.current.delete(job.id);
        triggerInlineDiagnosisProcessing(job.id);
      }

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
    [completeDiagnosis, finishTimingPhase, triggerInlineDiagnosisProcessing],
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
          const failureMessage = '진단 상태를 갱신하지 못했습니다.';
          finishTimingPhase('diagnosis', 'failed', failureMessage);
          setDiagnosisError(failureMessage);
          setFlowError(failureMessage);
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
  }, [diagnosisRunId, finishTimingPhase, syncDiagnosisRun]);

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
      console.error('Diagnosis retry failed:', error);
      finishTimingPhase('diagnosis', 'failed', '진단 재시도 요청 실패');
      toast.error('재시도 요청에 실패했습니다.');
    } finally {
      setIsRetryingDiagnosis(false);
    }
  }, [beginTimingPhase, diagnosisRun, finishTimingPhase, isRetryingDiagnosis, syncDiagnosisRun, triggerInlineDiagnosisProcessing, useSynchronousApiJobs]);

  const startDiagnosisForProject = useCallback(
    async (activeProjectId: string): Promise<boolean> => {
      const diagnosisUrl = useSynchronousApiJobs ? '/api/v1/diagnosis/run?wait_for_completion=true' : '/api/v1/diagnosis/run';
      const run = await api.post<DiagnosisRunResponse>(diagnosisUrl, { project_id: activeProjectId });
      setProjectId(activeProjectId);
      setDiagnosisRun(run);
      setDiagnosisJob(null);

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
          return false;
        }
        return true;
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
    [completeDiagnosis, finishTimingPhase, triggerInlineDiagnosisProcessing, useSynchronousApiJobs],
  );

  useEffect(() => {
    if (!preselectedProjectId) return;
    if (autoLoadedProjectRef.current === preselectedProjectId) return;
    autoLoadedProjectRef.current = preselectedProjectId;

    let cancelled = false;

    const hydrateFromRecordUpload = async () => {
      const loadingId = toast.loading('업로드한 기록으로 진단 결과를 확인하고 있어요...');
      const now = Date.now();

      setProjectId(preselectedProjectId);
      setShowAdvancedDetails(false);
      setDiagnosisResult(null);
      setDiagnosisRun(null);
      setDiagnosisJob(null);
      setDiagnosisRunId(null);
      setDiagnosisError(null);
      setFlowError(null);
      setStep('ANALYSING');
      setIsUploading(true);
      setTimingPhases({
        upload: { status: 'done', startedAt: now, finishedAt: now, note: '기록 업로드 완료' },
        parse: { status: 'done', startedAt: now, finishedAt: now, note: '문서 파싱 완료' },
        diagnosis: { status: 'running', startedAt: now, finishedAt: null, note: '진단 진행 중' },
      });

      try {
        let latestRun: DiagnosisRunResponse | null = null;
        try {
          latestRun = await api.get<DiagnosisRunResponse>(`/api/v1/diagnosis/project/${preselectedProjectId}/latest`);
        } catch (latestError: any) {
          if (latestError?.response?.status !== 404) throw latestError;
        }

        if (cancelled) return;

        if (latestRun && !isDiagnosisFailed(latestRun, null)) {
          setDiagnosisRun(latestRun);

          if (isDiagnosisComplete(latestRun)) {
            const loaded = completeDiagnosis(latestRun);
            if (loaded) {
              toast.success('기존 진단 결과를 바로 불러왔어요.', { id: loadingId });
              return;
            }
          } else {
            setDiagnosisRunId(latestRun.id);
            if (latestRun.async_job_id) {
              triggerInlineDiagnosisProcessing(latestRun.async_job_id);
            }
            toast.success('진행 중이던 진단 작업을 이어서 보여드릴게요.', { id: loadingId });
            return;
          }
        }

        const started = await startDiagnosisForProject(preselectedProjectId);
        if (!cancelled && started) {
          toast.success('업로드한 기록으로 진단을 시작했어요.', { id: loadingId });
        }
      } catch (error: any) {
        if (cancelled) return;
        const failureMessage = getApiErrorMessage(error, '저장된 업로드 기록으로 진단을 시작하지 못했어요.');
        failRunningTimingPhases(failureMessage);
        setDiagnosisError(failureMessage);
        setFlowError(failureMessage);
        setStep('FAILED');
        setIsUploading(false);
        toast.error(failureMessage, { id: loadingId });
      }
    };

    void hydrateFromRecordUpload();

    return () => {
      cancelled = true;
    };
  }, [completeDiagnosis, failRunningTimingPhases, preselectedProjectId, startDiagnosisForProject, triggerInlineDiagnosisProcessing]);

  const onDrop = useCallback(
    async (acceptedFiles: File[]) => {
      const file = acceptedFiles[0];
      if (!file) return;
      if (file.size > MAX_UPLOAD_BYTES) {
        toast.error('파일 용량이 50MB를 초과해 업로드할 수 없습니다.');
        return;
      }

      setShowAdvancedDetails(false);
      setDiagnosisResult(null);
      setDiagnosisRun(null);
      setDiagnosisJob(null);
      setDiagnosisRunId(null);
      setDiagnosisError(null);
      setFlowError(null);
      resetTimingPhases();
      setIsUploading(true);
      const loadingId = toast.loading('PDF 업로드와 진단 준비를 진행 중입니다...');

      try {
        beginTimingPhase('upload', '파일 업로드 진행 중');
        const formData = new FormData();
        formData.append('file', file);
        const mainGoal = goalList[0];
        if (mainGoal) {
          formData.append('target_major', mainGoal.major);
          formData.append('title', `${mainGoal.university} ${mainGoal.major} 진단`);
        }

        const uploadRes = await api.post<{ project_id: string; id: string }>('/api/v1/documents/upload', formData);
        setProjectId(uploadRes.project_id);
        finishTimingPhase('upload', 'done', `업로드 완료 (${(file.size / (1024 * 1024)).toFixed(1)}MB)`);

        beginTimingPhase('parse', '문서 파싱/마스킹 진행 중');
        setStep('ANALYSING');
        const parseUrl = useSynchronousApiJobs
          ? `/api/v1/documents/${uploadRes.id}/parse?wait_for_completion=true`
          : `/api/v1/documents/${uploadRes.id}/parse`;
        const parseStarted = await api.post<DiagnosisDocumentStatus>(parseUrl);
        triggerInlineParseProcessing(parseStarted);
        const parsedDocument = PARSE_TERMINAL_STATUSES.has(parseStarted.status)
          ? parseStarted
          : await waitForDocumentParseResult(uploadRes.id, triggerInlineParseProcessing);
        if (parsedDocument.latest_async_job_id && PARSE_TERMINAL_STATUSES.has(parsedDocument.status)) {
          parseProcessKickoffRef.current.delete(parsedDocument.latest_async_job_id);
        }

        if (!PARSE_SUCCESS_STATUSES.has(parsedDocument.status)) {
          const parseError = getParseFailureMessage(parsedDocument);
          finishTimingPhase('parse', 'failed', parseError);
          setDiagnosisError(parseError);
          setFlowError(parseError);
          setStep('FAILED');
          setIsUploading(false);
          toast.error(parseError, { id: loadingId });
          return;
        }

        if (!hasDocumentContent(parsedDocument)) {
          const emptyContentError = 'PDF에서 진단 가능한 텍스트를 찾지 못했습니다. OCR 품질이 더 좋은 파일로 다시 시도해 주세요.';
          finishTimingPhase('parse', 'failed', emptyContentError);
          setDiagnosisError(emptyContentError);
          setFlowError(emptyContentError);
          setStep('FAILED');
          setIsUploading(false);
          toast.error(emptyContentError, { id: loadingId });
          return;
        }

        const parseNote = parsedDocument.page_count ? `파싱 완료 (${parsedDocument.page_count}페이지)` : '파싱 완료';
        finishTimingPhase('parse', 'done', parseNote);
        beginTimingPhase('diagnosis', '진단 생성 진행 중');

        await startDiagnosisForProject(uploadRes.project_id);

        toast.success('진단 실행을 시작했습니다.', { id: loadingId });
      } catch (error: any) {
        console.error('Diagnosis flow failed:', error);
        const failureMessage = getApiErrorMessage(error, '진단 실행에 실패했습니다. 잠시 후 다시 시도해 주세요.');
        failRunningTimingPhases(failureMessage);
        setDiagnosisError(failureMessage);
        setFlowError(failureMessage);
        setStep('FAILED');
        toast.error(failureMessage, { id: loadingId });
        setIsUploading(false);
      }
    },
    [
      beginTimingPhase,
      failRunningTimingPhases,
      finishTimingPhase,
      goalList,
      resetTimingPhases,
      startDiagnosisForProject,
      triggerInlineParseProcessing,
      useSynchronousApiJobs,
    ],
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

  const timingPhaseItems = [
    { id: 'upload', label: '업로드', expectedSeconds: 20, ...timingPhases.upload },
    { id: 'parse', label: '파싱', expectedSeconds: 90, ...timingPhases.parse },
    { id: 'diagnosis', label: '진단', expectedSeconds: 120, ...timingPhases.diagnosis },
  ];
  const shouldShowTimingDashboard = timingPhaseItems.some((phase) => phase.startedAt !== null);

  return (
    <div className="mx-auto max-w-6xl space-y-6 py-4">
      <PageHeader eyebrow="진단" title={headerTitle} description={headerDescription} />
      <StepIndicator items={stepItems} />
      {shouldShowTimingDashboard ? (
        <ProcessTimingDashboard
          phases={timingPhaseItems}
          title="진단 진행 타임테이블"
          description="예상 소요시간 대비 현재 진단 진행률을 보여드려요."
        />
      ) : null}

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
            <SectionCard title="PDF 업로드" description="파일 1개(최대 50MB)를 올리면 업로드 → 파싱 → 진단이 자동으로 이어집니다.">
              <div className="grid gap-2 rounded-2xl border border-slate-200 bg-slate-50 p-4 sm:grid-cols-3">
                <p className="text-sm font-semibold text-slate-700">1. PDF 선택</p>
                <p className="text-sm font-semibold text-slate-700">2. 자동 파싱 확인</p>
                <p className="text-sm font-semibold text-slate-700">3. 진단 결과 확인</p>
              </div>
              <div
                {...getRootProps({
                  onClick: handleOpenFileDialog,
                  onKeyDown: handleDropzoneKeyDown,
                })}
                className={`cursor-pointer rounded-2xl border-2 border-dashed p-6 text-center transition-colors sm:p-10 ${
                  isDragActive ? 'border-blue-400 bg-blue-50' : 'border-slate-300 bg-slate-50 hover:border-blue-300 hover:bg-white'
                } ${isUploading ? 'pointer-events-none opacity-60' : ''}`}
              >
                <input data-testid="diagnosis-upload-input" {...getInputProps()} />
                <div className="mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-2xl bg-white text-blue-700 shadow-sm">
                  {isUploading ? <Loader2 size={26} className="animate-spin" /> : <FileUp size={26} />}
                </div>
                <p className="text-xl font-black tracking-tight text-slate-900">학생부 PDF를 드래그하거나 클릭해 업로드하세요</p>
                <p className="mt-2 text-base font-medium text-slate-600">업로드 후에는 페이지를 유지하면 자동으로 상태가 갱신됩니다.</p>
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
              {flowError ? <WorkflowNotice tone="danger" title="업로드/진단 오류" description={flowError} /> : null}
            </SectionCard>
          </motion.div>
        ) : null}

        {step === 'ANALYSING' ? (
          <motion.div key="analysing" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} className="space-y-6">
            <WorkflowNotice
              tone="loading"
              title="문서 분석과 진단 생성을 진행 중입니다"
              description="파싱이 끝나면 자동으로 진단 생성 단계로 넘어가며, 페이지를 유지하면 상태가 자동 갱신됩니다."
            />
            <AsyncJobStatusCard job={diagnosisJob} runStatus={diagnosisRun?.status} errorMessage={diagnosisRun?.error_message} />
          </motion.div>
        ) : null}

        {step === 'FAILED' ? (
          <motion.div key="failed" initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -10 }} className="space-y-6">
            <WorkflowNotice tone="danger" title="진단 실행에 실패했습니다" description={flowError || diagnosisError || '작업 상태를 확인한 뒤 재시도해 주세요.'} />

            <AsyncJobStatusCard
              job={diagnosisJob}
              runStatus={diagnosisRun?.status}
              errorMessage={diagnosisError}
              onRetry={diagnosisJob?.status === 'failed' ? retryDiagnosis : null}
              isRetrying={isRetryingDiagnosis}
            />

            <div className="flex flex-wrap items-center justify-center gap-2">
              <SecondaryButton
                onClick={() => {
                  setStep('UPLOAD');
                  setFlowError(null);
                  setDiagnosisError(null);
                }}
              >
                업로드로 돌아가기
              </SecondaryButton>
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
                <div className="flex flex-wrap items-center gap-2">
                  <StatusBadge status={diagnosisResult.risk_level === 'safe' ? 'success' : diagnosisResult.risk_level === 'warning' ? 'warning' : 'danger'}>
                    {formatRiskLevel(diagnosisResult.risk_level)}
                  </StatusBadge>
                  <SecondaryButton onClick={() => setShowAdvancedDetails((prev) => !prev)}>
                    {showAdvancedDetails ? '상세 데이터 접기' : '상세 데이터 보기'}
                  </SecondaryButton>
                </div>
              }
            >
              {diagnosisResult.overview ? (
                <WorkflowNotice tone="info" title="개요" description={diagnosisResult.overview} />
              ) : null}

              <div className="grid gap-4 md:grid-cols-2">
                <SurfaceCard tone="muted" padding="sm">
                  <p className="mb-2 text-xs font-bold uppercase tracking-[0.14em] text-slate-400">강점</p>
                  <ul className="space-y-1.5">
                    {diagnosisResult.strengths.map((item, index) => (
                      <li key={index} className="flex gap-2 text-base font-medium leading-7 text-slate-700">
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
                      <li key={index} className="flex gap-2 text-base font-medium leading-7 text-slate-700">
                        <AlertTriangle size={14} className="mt-1 text-amber-600" />
                        {item}
                      </li>
                    ))}
                  </ul>
                </SurfaceCard>
              </div>

              {showAdvancedDetails ? (
                <>
                  {diagnosisResult.document_quality ? (
                    <SurfaceCard tone="muted" padding="sm" className="space-y-3">
                      <div className="flex flex-wrap items-center justify-between gap-2">
                        <p className="text-xs font-bold uppercase tracking-[0.14em] text-slate-400">문서 품질</p>
                        <StatusBadge status={diagnosisResult.document_quality.needs_review ? 'warning' : 'success'}>
                          {diagnosisResult.document_quality.parse_reliability_band} ({diagnosisResult.document_quality.parse_reliability_score}점)
                        </StatusBadge>
                      </div>
                      <p className="text-base font-medium leading-7 text-slate-700">{diagnosisResult.document_quality.summary}</p>
                      <div className="grid gap-2 sm:grid-cols-3">
                        <div className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm font-semibold text-slate-700">
                          source: {diagnosisResult.document_quality.source_mode}
                        </div>
                        <div className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm font-semibold text-slate-700">
                          records: {diagnosisResult.document_quality.total_records}
                        </div>
                        <div className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm font-semibold text-slate-700">
                          words: {diagnosisResult.document_quality.total_word_count}
                        </div>
                      </div>
                    </SurfaceCard>
                  ) : null}

                  {diagnosisResult.section_analysis?.length ? (
                    <div className="space-y-2">
                      <p className="text-xs font-bold uppercase tracking-[0.14em] text-slate-400">섹션 분석</p>
                      <div className="grid gap-2 md:grid-cols-2">
                        {diagnosisResult.section_analysis.map((item) => (
                          <SurfaceCard key={item.key} tone="muted" padding="sm" className="space-y-1.5">
                            <div className="flex items-center justify-between gap-2">
                              <p className="text-sm font-bold text-slate-800">{item.label}</p>
                              <StatusBadge status={item.present ? 'success' : 'warning'}>
                                {item.present ? `records ${item.record_count}` : 'missing'}
                              </StatusBadge>
                            </div>
                            <p className="text-base font-medium leading-7 text-slate-600">{item.note}</p>
                          </SurfaceCard>
                        ))}
                      </div>
                    </div>
                  ) : null}

                  {diagnosisResult.admission_axes?.length ? (
                    <div className="space-y-2">
                      <p className="text-xs font-bold uppercase tracking-[0.14em] text-slate-400">핵심 평가축</p>
                      <div className="grid gap-3 md:grid-cols-2">
                        {diagnosisResult.admission_axes.map((axis) => (
                          <SurfaceCard key={axis.key} padding="sm">
                            <div className="mb-2 flex items-center justify-between gap-2">
                              <p className="text-sm font-bold text-slate-800">{axis.label}</p>
                              <div className="flex items-center gap-1.5">
                                <StatusBadge status={axis.severity === 'low' ? 'success' : axis.severity === 'medium' ? 'warning' : 'danger'}>
                                  {axis.band}
                                </StatusBadge>
                                <StatusBadge status="neutral">{axis.score}점</StatusBadge>
                              </div>
                            </div>
                            <p className="text-base font-medium leading-7 text-slate-600">{axis.rationale}</p>
                            {axis.evidence_hints?.length ? (
                              <ul className="mt-2 space-y-1">
                                {axis.evidence_hints.slice(0, 2).map((hint) => (
                                  <li key={hint} className="text-sm font-semibold text-slate-500">
                                    · {hint}
                                  </li>
                                ))}
                              </ul>
                            ) : null}
                          </SurfaceCard>
                        ))}
                      </div>
                    </div>
                  ) : null}
                </>
              ) : (
                <WorkflowNotice
                  tone="info"
                  title="상세 데이터는 숨겨져 있어요"
                  description="문서 품질, 섹션 분석, 평가축은 상단의 상세 데이터 보기 버튼을 누르면 확인할 수 있습니다."
                />
              )}

              {diagnosisResult.risks?.length ? (
                <SurfaceCard tone="muted" padding="sm" className="border border-amber-200 bg-amber-50/70">
                  <p className="mb-2 text-xs font-bold uppercase tracking-[0.14em] text-amber-700">리스크</p>
                  <ul className="space-y-1.5">
                    {diagnosisResult.risks.map((risk) => (
                      <li key={risk} className="text-sm font-medium leading-6 text-amber-900">
                        · {risk}
                      </li>
                    ))}
                  </ul>
                </SurfaceCard>
              ) : null}

              {diagnosisResult.next_actions?.length ? (
                <SurfaceCard tone="muted" padding="sm">
                  <p className="mb-2 text-xs font-bold uppercase tracking-[0.14em] text-slate-400">다음 액션</p>
                  <ul className="space-y-1.5">
                    {diagnosisResult.next_actions.map((action) => (
                      <li key={action} className="text-base font-medium leading-7 text-slate-700">
                        · {action}
                      </li>
                    ))}
                  </ul>
                </SurfaceCard>
              ) : null}

              {diagnosisResult.recommended_topics?.length ? (
                <SurfaceCard tone="muted" padding="sm">
                  <p className="mb-2 text-xs font-bold uppercase tracking-[0.14em] text-slate-400">추천 주제</p>
                  <div className="flex flex-wrap gap-2">
                    {diagnosisResult.recommended_topics.map((topic) => (
                      <StatusBadge key={topic} status="neutral">
                        {topic}
                      </StatusBadge>
                    ))}
                  </div>
                </SurfaceCard>
              ) : null}

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
                        <p className="text-base font-medium leading-7 text-slate-600">{quest.description}</p>
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

            {diagnosisRun?.id ? (
              <DiagnosisReportPanel diagnosisRunId={diagnosisRun.id} />
            ) : null}

            {showAdvancedDetails ? (
              <div className="grid gap-6 xl:grid-cols-2">
                {diagnosisResult.claims?.length ? <ClaimGroundingPanel claims={diagnosisResult.claims} /> : null}
                <DiagnosisEvidencePanel
                  citations={evidenceCitations}
                  reviewRequired={reviewRequired}
                  policyFlags={diagnosisRun?.policy_flags ?? []}
                  responseTraceId={responseTraceId}
                />
              </div>
            ) : null}

            <div className="flex flex-wrap items-center justify-center gap-2">
              <SecondaryButton
                onClick={() => {
                  setStep('GOALS');
                  setDiagnosisResult(null);
                  setDiagnosisRun(null);
                  setDiagnosisJob(null);
                  setDiagnosisRunId(null);
                  setDiagnosisError(null);
                  setFlowError(null);
                  resetTimingPhases();
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
