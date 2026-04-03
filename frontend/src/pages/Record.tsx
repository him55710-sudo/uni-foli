import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useDropzone } from 'react-dropzone';
import {
  AlertTriangle,
  ArrowRight,
  CheckCircle2,
  Clock3,
  FileSearch,
  FileText,
  FileUp,
  RefreshCw,
  ShieldCheck,
  TimerReset,
} from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import toast from 'react-hot-toast';
import { useAuth } from '../contexts/AuthContext';
import { api } from '../lib/api';
import { searchMajors } from '../lib/educationCatalog';
import { CatalogAutocompleteInput } from '../components/CatalogAutocompleteInput';
import {
  PageHeader,
  PrimaryButton,
  SecondaryButton,
  SectionCard,
  StatusBadge,
  StepIndicator,
  SurfaceCard,
  WorkflowNotice,
} from '../components/primitives';

type DocumentStatus = 'uploaded' | 'masking' | 'parsing' | 'retrying' | 'parsed' | 'partial' | 'failed';
type MaskingStatus = 'pending' | 'masking' | 'masked' | 'failed';

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
  page_count: number;
  word_count: number;
  parse_started_at: string | null;
  parse_completed_at: string | null;
  created_at: string;
  updated_at: string;
  content_text: string;
  content_markdown: string;
  parse_metadata: {
    chunk_count?: number;
    table_count?: number;
    warnings?: string[];
    masking?: {
      methods?: string[];
      replacement_count?: number;
      pattern_hits?: Record<string, number>;
    };
    page_failures?: Array<{ page_number?: number; message?: string }>;
  };
}

const IN_PROGRESS_STATUSES = new Set<DocumentStatus>(['masking', 'parsing', 'retrying']);
const SUCCESS_STATUSES = new Set<DocumentStatus>(['parsed', 'partial']);

const FRIENDLY_UPLOAD_STEPS = [
  {
    id: '01',
    title: 'PDF 준비',
    description: '학생부 파일을 PDF로 저장해 주세요.',
    tip: '파일명은 학년/이름 없이 간단하게 적으면 좋아요.',
    icon: FileText,
    accentClassName: 'bg-blue-100 text-blue-700',
  },
  {
    id: '02',
    title: '파일 올리기',
    description: '아래 상자에 끌어놓거나 버튼으로 선택해 주세요.',
    tip: '최대 50MB까지 올릴 수 있어요.',
    icon: FileUp,
    accentClassName: 'bg-indigo-100 text-indigo-700',
  },
  {
    id: '03',
    title: '자동 분석 시작',
    description: '개인정보 보호 처리와 내용 분석이 자동으로 진행돼요.',
    tip: '완료되면 바로 작성 화면으로 이동할 수 있어요.',
    icon: CheckCircle2,
    accentClassName: 'bg-emerald-100 text-emerald-700',
  },
] as const;

const UPLOAD_READY_CHECKLIST = [
  '파일 확장자가 .pdf인지 확인하기',
  '용량이 50MB 이하인지 확인하기',
  '학생부 전체 페이지가 모두 포함됐는지 확인하기',
] as const;

const COMMON_UPLOAD_ISSUES = [
  {
    title: '파일 선택창에 PDF가 보이지 않아요',
    description: '다운로드 폴더를 확인하고 파일 형식이 PDF인지 먼저 확인해 주세요.',
  },
  {
    title: '업로드가 중간에 멈춰요',
    description: '인터넷 연결을 확인한 뒤 다시 시도 버튼을 눌러 주세요.',
  },
] as const;

function formatBytes(value: number | null): string {
  if (!value) return '0 B';
  if (value < 1024) return `${value} B`;
  if (value < 1024 * 1024) return `${(value / 1024).toFixed(1)} KB`;
  return `${(value / (1024 * 1024)).toFixed(1)} MB`;
}

function formatStatusLabel(status: DocumentStatus): string {
  switch (status) {
    case 'uploaded':
      return '업로드 완료';
    case 'masking':
      return '개인정보 보호 처리 중';
    case 'parsing':
      return '내용 분석 중';
    case 'retrying':
      return '다시 시도 중';
    case 'parsed':
      return '분석 완료';
    case 'partial':
      return '부분 완료';
    case 'failed':
      return '실패';
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
  const { user, isGuestSession } = useAuth();

  const [targetMajor, setTargetMajor] = useState('');
  const [document, setDocument] = useState<DocumentStatusResponse | null>(null);
  const [isUploading, setIsUploading] = useState(false);
  const [isStartingParse, setIsStartingParse] = useState(false);
  const lastTerminalStatus = useRef<DocumentStatus | null>(null);

  const isBusy = isUploading || isStartingParse;
  const previewText = useMemo(() => (document?.content_text ? document.content_text.slice(0, 900) : ''), [document?.content_text]);

  const majorSuggestions = useMemo(
    () => (targetMajor.trim().length >= 1 ? searchMajors(targetMajor, null, 10) : []),
    [targetMajor],
  );

  useEffect(() => {
    if (!document || !IN_PROGRESS_STATUSES.has(document.status)) return undefined;

    const intervalId = window.setInterval(async () => {
      try {
        const fresh = await api.get<DocumentStatusResponse>(`/api/v1/documents/${document.id}`);
        setDocument(fresh);
      } catch (error) {
        console.error('Failed to poll document status:', error);
      }
    }, 1500);

    return () => window.clearInterval(intervalId);
  }, [document]);

  useEffect(() => {
    if (!document) return;
    if (IN_PROGRESS_STATUSES.has(document.status)) {
      lastTerminalStatus.current = null;
      return;
    }
    if (lastTerminalStatus.current === document.status) return;

    if (document.status === 'parsed') {
      toast.success('업로드와 분석이 모두 완료됐어요.');
    } else if (document.status === 'partial') {
      toast('일부 경고가 있지만 분석은 완료됐어요. 내용을 확인해 주세요.', { icon: '!' });
    } else if (document.status === 'failed') {
      toast.error(document.last_error || '분석에 실패했어요. 파일 상태를 확인한 뒤 다시 시도해 주세요.');
    }

    lastTerminalStatus.current = document.status;
  }, [document]);

  const startParse = useCallback(async (documentId: string) => {
    setIsStartingParse(true);
    try {
      const started = await api.post<DocumentStatusResponse>(`/api/v1/documents/${documentId}/parse`);
      setDocument(started);
    } catch (error: any) {
      console.error('Failed to start parsing:', error);
      const detail = error.response?.data?.detail || '분석 시작에 실패했어요.';
      toast.error(detail);
    } finally {
      setIsStartingParse(false);
    }
  }, []);

  const onDrop = useCallback(
    async (acceptedFiles: File[]) => {
      const file = acceptedFiles[0];
      if (!file || isBusy) return;

      if (isGuestSession && !user) {
        toast.error('현재 게스트 체험 상태에서는 업로드가 제한돼요. 로그인 후 다시 시도해 주세요.');
        navigate('/auth');
        return;
      }

      setIsUploading(true);
      const loadingId = toast.loading('PDF를 업로드하고 문서를 준비하는 중이에요...');

      try {
        const formData = new FormData();
        formData.append('file', file);
        if (targetMajor.trim()) {
          formData.append('target_major', targetMajor.trim());
          formData.append('title', `${targetMajor.trim()} 준비`);
        }

        const created = await api.post<DocumentStatusResponse>('/api/v1/documents/upload', formData, {
          headers: { 'Content-Type': 'multipart/form-data' },
        });
        setDocument(created);
        toast.success('업로드 완료! 분석을 시작할게요.', { id: loadingId });
        await startParse(created.id);
      } catch (error: any) {
        console.error('Upload flow failed:', error);
        const detail = error.response?.data?.detail || '업로드에 실패했어요. 파일 형식(PDF)과 용량(50MB 이하)을 확인해 주세요.';
        toast.error(detail, { id: loadingId });
      } finally {
        setIsUploading(false);
      }
    },
    [isBusy, isGuestSession, navigate, startParse, targetMajor, user],
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
  const pageFailures = document?.parse_metadata?.page_failures ?? [];
  const warnings = document?.parse_metadata?.warnings ?? [];
  const stepItems = [
    { id: 'upload', label: '업로드', description: '파일 등록', state: getStepState(document, 'upload') },
    { id: 'masking', label: '개인정보 보호', description: '이름/연락처 숨김 처리', state: getStepState(document, 'masking') },
    { id: 'parsing', label: '내용 분석', description: '텍스트 구조 분석', state: getStepState(document, 'parsing') },
    {
      id: 'done',
      label: '작성 화면 이동',
      description: '다음 단계 진입 가능',
      state: canContinue ? 'done' : document?.status === 'failed' ? 'error' : 'pending' as 'done' | 'active' | 'pending' | 'error',
    },
  ] as Array<{ id: string; label: string; description: string; state: 'done' | 'active' | 'pending' | 'error' }>;

  return (
    <div className="mx-auto max-w-7xl space-y-6 py-4">
      <PageHeader
        eyebrow="기록 업로드"
        title="학생부 PDF를 안전하게 처리해요"
        description="문서를 올리면 개인정보 보호 처리와 내용 분석이 자동으로 진행돼요. 완료되면 바로 작성 화면으로 이동할 수 있어요."
        evidence={
          <div className="flex flex-wrap items-center gap-2">
            <StatusBadge status={document?.status === 'failed' ? 'danger' : document && SUCCESS_STATUSES.has(document.status) ? 'success' : 'active'}>
              {document ? formatStatusLabel(document.status) : '업로드 대기'}
            </StatusBadge>
            {document ? <StatusBadge status="neutral">시도 {document.parse_attempts}회</StatusBadge> : null}
          </div>
        }
      />

      <section className="rounded-[30px] border border-blue-100 bg-gradient-to-br from-blue-50 via-white to-indigo-50 p-5 shadow-sm sm:p-7">
        <div className="grid gap-6 xl:grid-cols-[1.15fr_0.85fr]">
          <div>
            <div className="flex flex-wrap items-center gap-2">
              <span className="rounded-full bg-blue-600 px-3 py-1 text-[11px] font-black uppercase tracking-[0.14em] text-white">
                Upload Guide
              </span>
              <StatusBadge status="neutral">
                <Clock3 size={14} />
                평균 1~2분
              </StatusBadge>
            </div>
            <h2 className="mt-4 text-2xl font-extrabold tracking-tight text-slate-900 sm:text-3xl break-keep">
              처음이어도 쉽게 업로드할 수 있어요.
            </h2>
            <p className="mt-2 text-sm font-medium leading-6 text-slate-600 sm:text-base sm:leading-7 break-keep">
              아래 3단계만 따라오면 업로드부터 작성 화면 이동까지 한 번에 진행돼요.
            </p>

            <div className="mt-5 grid gap-3 sm:grid-cols-3">
              {FRIENDLY_UPLOAD_STEPS.map(step => {
                const Icon = step.icon;
                return (
                  <article key={step.id} className="rounded-2xl border border-white/70 bg-white/95 p-4 shadow-sm">
                    <div className="flex items-center justify-between gap-2">
                      <span className="text-xs font-black tracking-[0.14em] text-slate-400">{step.id}</span>
                      <div className={`flex h-9 w-9 items-center justify-center rounded-xl ${step.accentClassName}`}>
                        <Icon size={17} />
                      </div>
                    </div>
                    <h3 className="mt-3 text-sm font-black text-slate-900 break-keep">{step.title}</h3>
                    <p className="mt-1 text-sm font-medium leading-6 text-slate-600 break-keep">{step.description}</p>
                    <p className="mt-2 text-xs font-semibold leading-5 text-slate-500 break-keep">{step.tip}</p>
                  </article>
                );
              })}
            </div>
          </div>

          <div className="space-y-4">
            <SurfaceCard tone="muted" className="border border-emerald-100 bg-emerald-50/70" padding="sm">
              <p className="text-xs font-black uppercase tracking-[0.14em] text-emerald-700">업로드 전 체크리스트</p>
              <ul className="mt-3 space-y-2">
                {UPLOAD_READY_CHECKLIST.map(item => (
                  <li key={item} className="flex items-start gap-2 text-sm font-semibold leading-6 text-emerald-900 break-keep">
                    <CheckCircle2 size={15} className="mt-1 shrink-0 text-emerald-600" />
                    <span>{item}</span>
                  </li>
                ))}
              </ul>
            </SurfaceCard>

            <SurfaceCard tone="muted" className="border border-amber-200 bg-amber-50/80" padding="sm">
              <div className="flex items-center justify-between gap-2">
                <div className="flex items-center gap-2">
                  <AlertTriangle size={15} className="text-amber-700" />
                  <p className="text-xs font-black uppercase tracking-[0.14em] text-amber-700">자주 생기는 상황</p>
                </div>
                <span className="inline-flex items-center gap-1 rounded-full border border-amber-300 bg-white px-2.5 py-1 text-[11px] font-black text-amber-700">
                  <RefreshCw size={12} />
                  다시 시도 가능
                </span>
              </div>
              <div className="mt-3 space-y-3">
                {COMMON_UPLOAD_ISSUES.map(issue => (
                  <div key={issue.title} className="rounded-xl border border-amber-200/70 bg-white/80 p-3">
                    <p className="text-sm font-black text-slate-900 break-keep">{issue.title}</p>
                    <p className="mt-1 text-sm font-medium leading-6 text-slate-600 break-keep">{issue.description}</p>
                  </div>
                ))}
              </div>
            </SurfaceCard>
          </div>
        </div>
      </section>

      <StepIndicator items={stepItems} />

      <div className="grid grid-cols-1 gap-6 xl:grid-cols-[1.05fr_0.95fr]">
        <SectionCard title="문서 업로드" description="PDF 1개(최대 50MB) 업로드를 지원해요." eyebrow="입력">
          <CatalogAutocompleteInput
            label="목표 학과 (선택)"
            value={targetMajor}
            onChange={setTargetMajor}
            onSelect={suggestion => setTargetMajor(suggestion.label)}
            placeholder="예: 경영학과, 컴퓨터공학과"
            suggestions={majorSuggestions}
            helperText="학과를 입력하면 아래에 관련 학과 목록이 자동으로 뜹니다."
            emptyText="일치하는 학과가 아직 없어요. 다른 키워드로 검색해 보세요."
            suggestionTestIdPrefix="record-major-suggestion"
            inputTestId="record-target-major"
          />

          <div
            {...getRootProps({
              onClick: handleOpenFileDialog,
              onKeyDown: handleDropzoneKeyDown,
            })}
            className={`cursor-pointer rounded-2xl border-2 border-dashed p-8 text-left transition-all ${
              isDragActive ? 'border-blue-400 bg-blue-50' : 'border-slate-300 bg-slate-50 hover:border-blue-300 hover:bg-white'
            } ${isBusy ? 'cursor-not-allowed opacity-70' : ''}`}
          >
            <input {...getInputProps({ 'aria-label': '학생부 PDF 업로드' })} />
            <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
              <div className="flex items-start gap-4">
                <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-blue-100 text-blue-700">
                  <FileUp size={26} />
                </div>
                <div className="min-w-0">
                  <h2 className="text-lg font-bold text-slate-900 break-keep">PDF 올리기</h2>
                  <p className="mt-1 text-sm font-medium leading-6 text-slate-600 break-keep">여기에 파일을 끌어놓거나 버튼으로 선택해 주세요.</p>
                  <p className="mt-2 text-xs font-semibold leading-5 text-slate-500 break-keep">
                    팁. 업로드 후에는 개인정보 보호 처리와 내용 분석이 자동으로 시작됩니다.
                  </p>
                  <div className="mt-3">
                    <button
                      type="button"
                      onClick={(event) => {
                        event.preventDefault();
                        event.stopPropagation();
                        handleOpenFileDialog();
                      }}
                      disabled={isBusy}
                      className="inline-flex items-center gap-2 rounded-xl border border-blue-200 bg-white px-3 py-2 text-sm font-bold text-blue-700 shadow-sm transition-colors hover:bg-blue-50 disabled:cursor-not-allowed disabled:opacity-60"
                    >
                      <FileText size={15} />
                      파일 선택
                    </button>
                  </div>
                </div>
              </div>
              <StatusBadge status={isBusy ? 'active' : 'neutral'}>{isBusy ? '처리 중' : 'PDF 파일'}</StatusBadge>
            </div>
          </div>

          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-4">
            <SurfaceCard tone="muted" padding="sm">
              <p className="text-xs font-bold uppercase tracking-[0.14em] text-slate-400">파일명</p>
              <p className="mt-2 text-sm font-bold text-slate-700 break-all">{document?.original_filename || '-'}</p>
            </SurfaceCard>
            <SurfaceCard tone="muted" padding="sm">
              <p className="text-xs font-bold uppercase tracking-[0.14em] text-slate-400">용량</p>
              <p className="mt-2 text-sm font-bold text-slate-700">{formatBytes(document?.file_size_bytes ?? null)}</p>
            </SurfaceCard>
            <SurfaceCard tone="muted" padding="sm">
              <p className="text-xs font-bold uppercase tracking-[0.14em] text-slate-400">페이지</p>
              <p className="mt-2 text-sm font-bold text-slate-700">{document?.page_count ?? 0}p</p>
            </SurfaceCard>
            <SurfaceCard tone="muted" padding="sm">
              <p className="text-xs font-bold uppercase tracking-[0.14em] text-slate-400">분석 조각</p>
              <p className="mt-2 text-sm font-bold text-slate-700">{document?.parse_metadata?.chunk_count ?? 0}개</p>
            </SurfaceCard>
          </div>

          <div className="flex flex-wrap gap-2">
            <SecondaryButton onClick={() => document && startParse(document.id)} disabled={!document?.can_retry || isBusy}>
              <TimerReset size={16} />
              분석 다시 시도
            </SecondaryButton>
            <SecondaryButton onClick={() => navigate('/app/diagnosis')} disabled={!canContinue}>
              진단 결과 보기
              <FileSearch size={16} />
            </SecondaryButton>
            <PrimaryButton
              onClick={() => navigate(`/app/workshop/${document?.project_id}?major=${encodeURIComponent(targetMajor.trim())}`)}
              disabled={!canContinue}
            >
              작성 화면으로 이동
              <ArrowRight size={16} />
            </PrimaryButton>
          </div>
        </SectionCard>

        <div className="space-y-6">
          <SectionCard title="개인정보 보호 요약" description="개인정보 숨김 처리 결과를 확인해요." eyebrow="보안">
            <div className="flex items-start gap-3 rounded-2xl border border-blue-200 bg-blue-50 p-4">
              <ShieldCheck size={18} className="mt-0.5 text-blue-700" />
              <p className="text-sm font-medium leading-6 text-blue-900 break-keep">
                문서 내용은 분석 전에 개인정보 보호 규칙이 먼저 적용돼요. 아래에서 처리 방식과 개수 정보를 확인할 수 있어요.
              </p>
            </div>
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
              <SurfaceCard tone="muted" padding="sm">
                <p className="text-xs font-bold uppercase tracking-[0.14em] text-slate-400">처리 방식</p>
                <p className="mt-2 text-sm font-bold text-slate-700 break-keep">{maskingSummary?.methods?.join(', ') || '대기 중'}</p>
              </SurfaceCard>
              <SurfaceCard tone="muted" padding="sm">
                <p className="text-xs font-bold uppercase tracking-[0.14em] text-slate-400">치환 개수</p>
                <p className="mt-2 text-sm font-bold text-slate-700">{maskingSummary?.replacement_count ?? 0}건</p>
              </SurfaceCard>
              <SurfaceCard tone="muted" padding="sm">
                <p className="text-xs font-bold uppercase tracking-[0.14em] text-slate-400">표 보존</p>
                <p className="mt-2 text-sm font-bold text-slate-700">{document?.parse_metadata?.table_count ?? 0}개</p>
              </SurfaceCard>
            </div>
          </SectionCard>

          <SectionCard title="문서 내용 미리보기" description="숨김 처리 후 텍스트 일부를 확인해요." eyebrow="미리보기">
            <SurfaceCard padding="sm" className="bg-slate-950 text-slate-100">
              <pre className="whitespace-pre-wrap break-words font-mono text-xs leading-6">
                {previewText || '아직 표시할 분석 텍스트가 없어요.'}
              </pre>
            </SurfaceCard>
          </SectionCard>

          {warnings.length || pageFailures.length || document?.last_error ? (
            <SectionCard title="경고와 오류" description="확인이 필요한 항목이 있으면 여기에서 알려드려요." eyebrow="확인 필요">
              {document?.last_error ? <WorkflowNotice tone="danger" title="오류 메시지" description={document.last_error} /> : null}
              {warnings.map(warning => (
                <WorkflowNotice key={warning} tone="warning" title="분석 경고" description={warning} />
              ))}
              {pageFailures.map((failure, index) => (
                <WorkflowNotice
                  key={`${failure.page_number ?? 'na'}-${index}`}
                  tone="warning"
                  title={`${failure.page_number ?? '?'} 페이지 경고`}
                  description={failure.message || '상세 내용을 확인해 주세요.'}
                />
              ))}
            </SectionCard>
          ) : (
            <WorkflowNotice
              tone="success"
              title="현재 경고/오류가 없어요."
              description="분석이 끝나면 바로 작성 화면에서 다음 단계를 이어갈 수 있어요."
            />
          )}
        </div>
      </div>
    </div>
  );
}

