import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useDropzone } from 'react-dropzone';
import {
  ArrowRight,
  FileSearch,
  FileText,
  FileUp,
  TimerReset,
} from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import toast from 'react-hot-toast';
import { useAuth } from '../contexts/AuthContext';
import { ProcessTimingDashboard, type TimingPhaseStatus } from '../components/ProcessTimingDashboard';
import { api, shouldUseSynchronousApiJobs } from '../lib/api';
import { getApiErrorMessage } from '../lib/apiError';
import { searchMajors } from '../lib/educationCatalog';
import { buildRankedGoals } from '../lib/rankedGoals';
import { CatalogAutocompleteInput } from '../components/CatalogAutocompleteInput';
import { useAuthStore } from '../store/authStore';
import {
  PageHeader,
  PrimaryButton,
  SecondaryButton,
  SectionCard,
  StatusBadge,
  StepIndicator,
  WorkflowNotice,
} from '../components/primitives';
import { 
  DocumentStatus, 
  IN_PROGRESS_STATUSES, 
  SUCCESS_STATUSES,
  TERMINAL_STATUSES
} from '../types/domain';
import { useAsyncJob } from '../hooks/useAsyncJob';

type MaskingStatus = 'pending' | 'masking' | 'masked' | 'failed';
const MAX_UPLOAD_BYTES = 50 * 1024 * 1024;
type RecordTimingPhaseKey = 'upload' | 'parse';

interface RecordTimingPhaseState {
  status: TimingPhaseStatus;
  startedAt: number | null;
  finishedAt: number | null;
  note?: string;
}

type RecordTimingPhaseMap = Record<RecordTimingPhaseKey, RecordTimingPhaseState>;

interface DocumentStatusResponse {
  id: string;
  project_id: string;
  upload_asset_id: string;
  original_filename: string | null;
  content_type: string | null;
  file_size_bytes: number | null;
  sha256: string | null;
  stored_path: string | null;
  upload_status: string | null;
  parser_name: string;
  source_extension: string;
  status: DocumentStatus;
  masking_status: MaskingStatus;
  parse_attempts: number;
  last_error: string | null;
  can_retry: boolean;
  latest_async_job_id: string | null;
  latest_async_job_status: string | null;
  latest_async_job_error: string | null;
  page_count: number;
  word_count: number;
  parse_started_at: string | null;
  parse_completed_at: string | null;
  created_at: string;
  updated_at: string;
  content_text: string;
  content_markdown: string;
  parse_metadata: {
    source_storage_provider?: string;
    source_storage_key?: string;
    chunk_count?: number;
    table_count?: number;
    warnings?: string[];
    masking?: {
      methods?: string[];
      replacement_count?: number;
      pattern_hits?: Record<string, number>;
    };
    page_failures?: Array<{ page_number?: number; message?: string }>;
    pdf_analysis?: {
      provider?: string;
      model?: string;
      engine?: string;
      generated_at?: string;
      failure_reason?: string;
      attempted_provider?: string;
      attempted_model?: string;
      recovered_from_text_fallback?: boolean;
      requested_pdf_analysis_provider?: string;
      requested_pdf_analysis_model?: string;
      actual_pdf_analysis_provider?: string;
      actual_pdf_analysis_model?: string;
      pdf_analysis_engine?: string;
      fallback_used?: boolean;
      fallback_reason?: string;
      processing_duration_ms?: number;
      summary?: string;
      key_points?: string[];
      evidence_gaps?: string[];
      page_insights?: Array<{ page_number?: number; summary?: string }>;
    };
  };
}

const UPLOAD_READY_CHECKLIST = [
  '파일 확장자가 .pdf인지 확인하기',
  '용량이 50MB 이하인지 확인하기',
  '학생부 전체 페이지가 모두 포함됐는지 확인하기',
] as const;

function createInitialTimingPhases(): RecordTimingPhaseMap {
  return {
    upload: { status: 'idle', startedAt: null, finishedAt: null, note: '파일 업로드 준비 중' },
    parse: { status: 'idle', startedAt: null, finishedAt: null, note: '문서 내용을 확인할 준비 중' },
  };
}

function formatBytes(value: number | null): string {
  if (!value) return '0 B';
  if (value < 1024) return `${value} B`;
  if (value < 1024 * 1024) return `${(value / 1024).toFixed(1)} KB`;
  return `${(value / (1024 * 1024)).toFixed(1)} MB`;
}

function ProvenanceName(type: string) {
  switch (type) {
    case 'student_record': return '학생부 기록';
    case 'external_research': return '외부 문헌 및 기준';
    case 'ai_interpretation': return 'AI 심층 분석';
    default: return type;
  }
}

function formatStatusLabel(status: DocumentStatus): string {
  switch (status) {
    case 'uploaded':
      return '업로드 완료';
    case 'masking':
      return '보안 처리 중';
    case 'parsing':
      return '분석 중';
    case 'retrying':
      return '재시도 중';
    case 'parsed':
      return '분석 완료';
    case 'partial':
      return '분석 완료(일부 경고)';
    case 'failed':
      return '오류 발생';
    default:
      return status;
  }
}

function getStepState(
  document: DocumentStatusResponse | null,
  step: 'upload' | 'masking' | 'parsing',
): 'done' | 'active' | 'pending' | 'error' {
  if (!document) return 'pending';
  if (step === 'upload') return 'done';
  if (step === 'masking') {
    if (document.masking_status === 'failed') return 'error';
    if (document.masking_status === 'masked') return 'done';
    if (document.masking_status === 'masking' || IN_PROGRESS_STATUSES.has(document.status)) return 'active';
    return 'pending';
  }
  if (document.status === 'failed') return 'error';
  if (document.status === 'parsed' || document.status === 'partial') return 'done';
  if (IN_PROGRESS_STATUSES.has(document.status)) return 'active';
  return 'pending';
}

export function Record() {
  const navigate = useNavigate();
  const { user: authUser, isGuestSession } = useAuth();
  const { user: profileUser } = useAuthStore();

  const [targetMajor, setTargetMajor] = useState('');
  
  const goalList = useMemo(() => buildRankedGoals(profileUser, 6), [profileUser]);

  useEffect(() => {
    const preferredMajor = profileUser?.target_major?.trim() || goalList[0]?.major || '';
    if (preferredMajor && !targetMajor) {
      setTargetMajor(preferredMajor);
    }
  }, [goalList, profileUser?.target_major, targetMajor]);
  const [document, setDocument] = useState<DocumentStatusResponse | null>(null);
  const [isUploading, setIsUploading] = useState(false);
  const [isStartingParse, setIsStartingParse] = useState(false);
  const [timingPhases, setTimingPhases] = useState<RecordTimingPhaseMap>(() => createInitialTimingPhases());
  const lastTerminalStatus = useRef<DocumentStatus | null>(null);
  const useSynchronousApiJobs = shouldUseSynchronousApiJobs();

  const setTimingPhase = useCallback(
    (phase: RecordTimingPhaseKey, updater: Partial<RecordTimingPhaseState> | ((prev: RecordTimingPhaseState) => RecordTimingPhaseState)) => {
      setTimingPhases((prev) => {
        const current = prev[phase];
        const next = typeof updater === 'function' ? updater(current) : { ...current, ...updater };
        return { ...prev, [phase]: next };
      });
    },
    [],
  );

  const beginTimingPhase = useCallback((phase: RecordTimingPhaseKey, note?: string) => {
    const now = Date.now();
    setTimingPhase(phase, {
      status: 'running',
      startedAt: now,
      finishedAt: null,
      note,
    });
  }, [setTimingPhase]);

  const finishTimingPhase = useCallback((phase: RecordTimingPhaseKey, status: Exclude<TimingPhaseStatus, 'idle'>, note?: string) => {
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
      (Object.keys(next) as RecordTimingPhaseKey[]).forEach((phase) => {
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

  const isBusy = isUploading || isStartingParse;

  const majorSuggestions = useMemo(
    () => ((targetMajor || '').trim().length >= 1 ? searchMajors(targetMajor, null, 10) : []),
    [targetMajor],
  );

  useAsyncJob<DocumentStatusResponse>({
    url: document && IN_PROGRESS_STATUSES.has(document.status) ? `/api/v1/documents/${document.id}` : null,
    isTerminal: (data) => TERMINAL_STATUSES.has(data.status),
    onSuccess: (fresh) => {
      setDocument(fresh);
    },
    onError: (error) => {
      console.error('Failed to poll document status:', error);
    },
  });

  useEffect(() => {
    if (!document) return;
    if (IN_PROGRESS_STATUSES.has(document.status)) {
      lastTerminalStatus.current = null;
      return;
    }
    if (lastTerminalStatus.current === document.status) return;

    if (document.status === 'parsed') {
      const parseNote = document.page_count ? `분석 완료 (${document.page_count}페이지)` : '분석 완료';
      finishTimingPhase('parse', 'done', parseNote);
      toast.success('업로드와 분석이 모두 완료됐어요.');
    } else if (document.status === 'partial') {
      const partialNote = document.page_count ? `분석 일부 완료 (${document.page_count}페이지)` : '분석 일부 완료';
      finishTimingPhase('parse', 'done', partialNote);
      toast('일부 경고가 있지만 분석은 완료됐어요. 내용을 확인해 주세요.', { icon: '!' });
    } else if (document.status === 'failed') {
      const failureMessage =
        document.latest_async_job_error || document.last_error || '문서 분석에 실패했어요. 파일 상태를 확인한 뒤 다시 시도해 주세요.';
      finishTimingPhase('parse', 'failed', failureMessage);
      toast.error(
        failureMessage,
      );
    }

    lastTerminalStatus.current = document.status;
  }, [document, finishTimingPhase]);

  const startParse = useCallback(async (documentId: string, source: 'initial' | 'retry' = 'retry') => {
    beginTimingPhase('parse', source === 'initial' ? '문서 내용을 꼼꼼하게 읽어보는 중' : '문서를 다시 확인하는 중');
    setIsStartingParse(true);
    try {
      const parseUrl = useSynchronousApiJobs
        ? `/api/v1/documents/${documentId}/parse?wait_for_completion=true`
        : `/api/v1/documents/${documentId}/parse`;
      const started = await api.post<DocumentStatusResponse>(parseUrl);
      setDocument(started);

      if (started.status === 'failed') {
        const failureMessage = started.latest_async_job_error || started.last_error || '분석 시작에 실패했어요.';
        finishTimingPhase('parse', 'failed', failureMessage);
      } else if (SUCCESS_STATUSES.has(started.status)) {
        const parseNote = started.page_count ? `분석 완료 (${started.page_count}페이지)` : '분석 완료';
        finishTimingPhase('parse', 'done', parseNote);
      }
    } catch (error: any) {
      console.error('Failed to start parsing:', error);
      const detail = error.response?.data?.detail || '분석 시작에 실패했어요.';
      finishTimingPhase('parse', 'failed', detail);
      toast.error(detail);
    } finally {
      setIsStartingParse(false);
    }
  }, [beginTimingPhase, finishTimingPhase, useSynchronousApiJobs]);

  const onDrop = useCallback(
    async (acceptedFiles: File[]) => {
      const file = acceptedFiles[0];
      if (!file || isBusy) return;
      if (file.size > MAX_UPLOAD_BYTES) {
        toast.error('파일 용량이 50MB를 초과해 업로드할 수 없습니다.');
        return;
      }

      if (isGuestSession && !authUser) {
        toast.error('현재 게스트 체험 상태에서는 업로드가 제한돼요. 로그인 후 다시 시도해 주세요.');
        navigate('/auth');
        return;
      }

      setIsUploading(true);
      resetTimingPhases();
      beginTimingPhase('upload', '파일 업로드 진행 중');
      const loadingId = toast.loading('PDF를 업로드하고 문서를 준비하는 중이에요...');

      try {
        const formData = new FormData();
        formData.append('file', file);
        if (targetMajor) {
          formData.append('target_major', targetMajor);
          const matchedGoal =
            goalList.find((g) => g.major === targetMajor)
            || goalList[0]
            || (profileUser?.target_university
              ? { university: profileUser.target_university, major: profileUser.target_major || '' }
              : null);
          if (matchedGoal) {
            formData.append('target_university', matchedGoal.university);
            formData.append('title', `${matchedGoal.university} ${targetMajor} 기록 분석`);
          } else {
            formData.append('title', `${targetMajor} 기록 분석`);
          }
        }

        const created = await api.post<DocumentStatusResponse>('/api/v1/documents/upload', formData);
        setDocument(created);
        finishTimingPhase('upload', 'done', `업로드 완료 (${formatBytes(created.file_size_bytes)})`);
        toast.success('업로드 완료! 분석을 시작할게요.', { id: loadingId });
        await startParse(created.id, 'initial');
      } catch (error: any) {
        console.error('Upload flow failed:', error);
        const failureMessage = getApiErrorMessage(error, '업로드에 실패했습니다. 잠시 후 다시 시도해 주세요.');
        failRunningTimingPhases(failureMessage);
        toast.error(failureMessage, { id: loadingId });
      } finally {
        setIsUploading(false);
      }
    },
    [
      beginTimingPhase,
      failRunningTimingPhases,
      finishTimingPhase,
      isBusy,
      isGuestSession,
      navigate,
      resetTimingPhases,
      startParse,
      targetMajor,
      goalList,
      profileUser?.target_major,
      profileUser?.target_university,
      authUser,
    ],
  );

  const { getRootProps, getInputProps, isDragActive, open } = useDropzone({
    onDrop,
    accept: { 'application/pdf': ['.pdf'] },
    multiple: false,
    disabled: isBusy,
    noClick: true,
    noKeyboard: true,
    useFsAccessApi: false,
  });

  const handleOpenFileDialog = useCallback(() => {
    if (isBusy) return;
    open();
  }, [isBusy, open]);

  const handleDropzoneKeyDown = useCallback((event: React.KeyboardEvent<HTMLDivElement>) => {
    if (isBusy) return;
    if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault();
      open();
    }
  }, [isBusy, open]);

  const canContinue = Boolean(document && SUCCESS_STATUSES.has(document.status));
  const maskingSummary = document?.parse_metadata?.masking;
  const stepItems = [
    { id: 'upload', label: '업로드', description: '파일 등록', state: getStepState(document, 'upload') },
    { id: 'masking', label: '보안 처리', description: '개인정보 보호', state: getStepState(document, 'masking') },
    { id: 'parsing', label: '문서 읽기', description: '내용 추출', state: getStepState(document, 'parsing') },
    {
      id: 'done',
      label: '다음 단계',
      description: '진단/워크숍 이동',
      state: canContinue ? 'done' : document?.status === 'failed' ? 'error' : 'pending' as 'done' | 'active' | 'pending' | 'error',
    },
  ] as Array<{ id: string; label: string; description: string; state: 'done' | 'active' | 'pending' | 'error' }>;
  const timingPhaseItems = [
    { id: 'upload', label: '업로드', expectedSeconds: 20, ...timingPhases.upload },
    { id: 'parse', label: '문서 읽기', expectedSeconds: 90, ...timingPhases.parse },
  ];
  const shouldShowTimingDashboard = timingPhaseItems.some((phase) => phase.startedAt !== null);
  const diagnosisPath = document?.project_id
    ? `/app/diagnosis?project_id=${encodeURIComponent(document.project_id)}`
    : '/app/diagnosis';

  return (
    <div className="mx-auto max-w-6xl animate-in fade-in slide-in-from-bottom-4 space-y-6 py-6 duration-700">
      <PageHeader
        eyebrow="Record"
        title="학생부 PDF 업로드"
        description="파일 1개 업로드 후 바로 분석이 시작됩니다."
        className="border-slate-200 bg-white"
        actions={(
          <button
            type="button"
            onClick={() => navigate('/app/help/student-record-pdf')}
            className="inline-flex h-11 items-center gap-2 rounded-2xl border border-[#e5e8eb] bg-white px-5 text-[14px] font-bold text-[#4e5968] transition hover:bg-[#f2f4f6]"
          >
            업로드 도움말
            <ArrowRight size={16} strokeWidth={2.5} />
          </button>
        )}
        evidence={(
          <div className="flex flex-wrap items-center gap-2">
            <StatusBadge status={document?.status === 'failed' ? 'danger' : document && SUCCESS_STATUSES.has(document.status) ? 'success' : 'active'}>
              {document ? formatStatusLabel(document.status) : '업로드 대기'}
            </StatusBadge>
            <StatusBadge status="neutral">PDF Only</StatusBadge>
            {document ? (
              <StatusBadge status="neutral">
                분석 시도 {document.parse_attempts}회
              </StatusBadge>
            ) : null}
          </div>
        )}
      />

      <StepIndicator items={stepItems} />

      <div className="grid gap-6 xl:grid-cols-[1.25fr_0.75fr]">
        <SectionCard
          title="문서 업로드"
          description="드래그하거나 파일을 선택하세요."
          eyebrow="Upload"
          className="border-slate-200 bg-white shadow-sm"
        >
          <div className="space-y-6">
            <CatalogAutocompleteInput
              label="목표 학과"
              value={targetMajor}
              onChange={setTargetMajor}
              onSelect={suggestion => setTargetMajor(suggestion.label)}
              placeholder="예: 경영학과, 인공지능공학과"
              suggestions={majorSuggestions}
              helperText={goalList.length > 0 ? `현재 목표: ${goalList[0].university} ${goalList[0].major}` : '학과 입력 시 선별 분석이 적용됩니다.'}
              emptyText="일치 학과가 없어도 그대로 진행할 수 있습니다."
              inputClassName="bg-white border-slate-200 focus:bg-white"
            />

            <div className="flex flex-wrap gap-2">
              {UPLOAD_READY_CHECKLIST.map((item, idx) => (
                <span
                  key={idx}
                  className="rounded-full border border-blue-100 bg-blue-50 px-4 py-1.5 text-[12px] font-black text-[#3182f6]"
                >
                  {item}
                </span>
              ))}
            </div>

            <div
              {...getRootProps({
                onClick: handleOpenFileDialog,
                onKeyDown: handleDropzoneKeyDown,
              })}
              className={`group relative overflow-hidden rounded-[1.8rem] border-2 border-dashed p-8 transition-all md:p-10 ${
                isDragActive
                  ? 'scale-[0.99] border-cyan-500 bg-cyan-50/70'
                  : 'border-slate-200 bg-slate-50/70 hover:border-fuchsia-300 hover:bg-white'
              } ${isBusy ? 'cursor-not-allowed opacity-70' : 'cursor-pointer'}`}
            >
              <input {...getInputProps({ 'aria-label': '학생부 PDF 업로드' })} />

              <div className="flex flex-col items-center text-center">
                <div className={`mb-6 flex h-16 w-16 items-center justify-center rounded-[1.4rem] transition-all ${
                  isBusy
                    ? 'bg-slate-100 text-slate-400'
                    : 'bg-blue-50 text-[#3182f6] shadow-[0_14px_28px_-18px_rgba(49,130,246,0.3)] group-hover:-translate-y-0.5'
                }`}>
                  <FileUp size={28} strokeWidth={2.5} />
                </div>

                <h2 className="text-xl font-black text-slate-900 sm:text-2xl">PDF 업로드</h2>
                <p className="mt-2 text-sm font-semibold text-slate-500">드래그 또는 파일 선택</p>

                <button
                  type="button"
                  onClick={(event) => {
                    event.preventDefault();
                    event.stopPropagation();
                    handleOpenFileDialog();
                  }}
                  disabled={isBusy}
                  className="mt-6 inline-flex h-11 items-center gap-2 rounded-2xl bg-[#333d4b] px-6 text-[14px] font-black text-white transition hover:bg-[#191f28] disabled:opacity-50"
                >
                  파일 선택
                  <ArrowRight size={16} strokeWidth={2.5} />
                </button>
              </div>

              {isBusy ? <div className="absolute inset-0 bg-white/20 backdrop-blur-[1px]" /> : null}
            </div>

            {document ? (
              <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
                {[
                  { label: '파일명', value: document.original_filename || '-', full: true },
                  { label: '용량', value: formatBytes(document.file_size_bytes ?? null) },
                  { label: '페이지', value: `${document.page_count ?? 0}p` },
                  { label: '추출 항목', value: `${document.parse_metadata?.chunk_count ?? 0}개` },
                ].map((stat, idx) => (
                  <div
                    key={idx}
                    className={`rounded-xl border border-slate-200 bg-white px-3 py-3 ${stat.full ? 'col-span-2' : ''}`}
                  >
                    <p className="text-[10px] font-black uppercase tracking-[0.18em] text-slate-400">{stat.label}</p>
                    <p className="mt-1 truncate text-sm font-bold text-slate-700">{stat.value}</p>
                  </div>
                ))}
              </div>
            ) : null}

            <div className="flex flex-wrap items-center gap-3">
              <PrimaryButton
                size="lg"
                className="px-6 h-12 rounded-2xl shadow-lg shadow-blue-100 bg-[#3182f6] hover:bg-[#1b64da]"
                onClick={() => navigate(diagnosisPath)}
                disabled={!canContinue}
              >
                기록 진단 시작
                <ArrowRight size={18} strokeWidth={2.5} />
              </PrimaryButton>

              <SecondaryButton
                size="lg"
                variant="secondary"
                onClick={() => navigate(`/app/workshop/${document?.project_id}?major=${encodeURIComponent((targetMajor || '').trim())}`)}
                disabled={!canContinue}
              >
                워크숍 이동
              </SecondaryButton>

              {document?.status === 'failed' ? (
                <button
                  type="button"
                  onClick={() => startParse(document.id, 'retry')}
                  disabled={isBusy}
                  className="inline-flex items-center gap-2 rounded-xl border border-rose-200 bg-rose-50 px-3 py-2 text-sm font-bold text-rose-700 transition hover:bg-rose-100 disabled:opacity-50"
                >
                  <TimerReset size={14} />
                  다시 시도
                </button>
              ) : null}
            </div>
          </div>
        </SectionCard>

        <div className="space-y-6">
          {shouldShowTimingDashboard ? (
            <ProcessTimingDashboard
              phases={timingPhaseItems}
              title="실시간 분석 상태"
              description="업로드/문서 읽기 진행 중"
            />
          ) : (
            <SectionCard
              title="업로드 후 다음 작업"
              description="분석 완료 후 바로 이동"
              eyebrow="Next"
              className="border-white/70 bg-white/84 shadow-[0_24px_46px_-34px_rgba(15,23,42,0.55)]"
            >
              <div className="space-y-3">
                <button
                  type="button"
                  onClick={() => navigate(diagnosisPath)}
                  className="flex w-full items-center justify-between rounded-xl border border-slate-200 bg-white px-3 py-3 text-left text-sm font-bold text-slate-700 transition hover:border-violet-200 hover:bg-violet-50/40"
                >
                  <span className="inline-flex items-center gap-2">
                    <FileSearch size={15} className="text-violet-600" />
                    목표 대학 진단
                  </span>
                  <ArrowRight size={14} />
                </button>
                <button
                  type="button"
                  onClick={() => navigate(`/app/workshop/${document?.project_id || ''}`)}
                  className="flex w-full items-center justify-between rounded-xl border border-slate-200 bg-white px-3 py-3 text-left text-sm font-bold text-slate-700 transition hover:border-cyan-200 hover:bg-cyan-50/40"
                >
                  <span className="inline-flex items-center gap-2">
                    <FileText size={15} className="text-cyan-600" />
                    세특 워크숍
                  </span>
                  <ArrowRight size={14} />
                </button>
              </div>
            </SectionCard>
          )}

          <SectionCard
            title="보안 상태"
            description="개인정보 보호 요약"
            eyebrow="Security"
            className="border-white/70 bg-white/84 shadow-[0_24px_46px_-34px_rgba(15,23,42,0.55)]"
          >
            <div className="grid grid-cols-2 gap-3">
              <div className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-3">
                <p className="text-[10px] font-black uppercase tracking-[0.18em] text-slate-400">보안 처리</p>
                <p className="mt-1 text-lg font-black text-slate-800">{maskingSummary?.replacement_count ?? 0}</p>
              </div>
              <div className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-3">
                <p className="text-[10px] font-black uppercase tracking-[0.18em] text-slate-400">인식 객체</p>
                <p className="mt-1 text-lg font-black text-slate-800">{document?.parse_metadata?.table_count ?? 0}</p>
              </div>
            </div>
          </SectionCard>

          {document?.parse_metadata?.warnings?.length ? (
            <SectionCard
              title="검토 알림"
              description="확인 권장 항목"
              eyebrow="Warning"
              className="border-amber-200 bg-amber-50/70 shadow-[0_20px_36px_-28px_rgba(245,158,11,0.45)]"
            >
              <div className="space-y-2">
                {document.parse_metadata.warnings.map((warning, idx) => (
                  <WorkflowNotice key={idx} tone="warning" title={warning} />
                ))}
              </div>
            </SectionCard>
          ) : document && SUCCESS_STATUSES.has(document.status) ? (
            <WorkflowNotice
              tone="success"
              title="분석 완료"
              description="진단 또는 워크숍으로 바로 이동할 수 있습니다."
              className="shadow-[0_18px_34px_-24px_rgba(16,185,129,0.5)]"
            />
          ) : null}
        </div>
      </div>
    </div>
  );
}
