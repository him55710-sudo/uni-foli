import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useDropzone } from 'react-dropzone';
import {
  AlertTriangle,
  ArrowRight,
  CheckCircle2,
  Clock3,
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

type DocumentStatus =
  | 'uploaded'
  | 'masking'
  | 'parsing'
  | 'retrying'
  | 'parsed'
  | 'partial'
  | 'failed';

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

function formatBytes(value: number | null): string {
  if (!value) return '0 B';
  if (value < 1024) return `${value} B`;
  if (value < 1024 * 1024) return `${(value / 1024).toFixed(1)} KB`;
  return `${(value / (1024 * 1024)).toFixed(1)} MB`;
}

function formatStatusLabel(status: DocumentStatus): string {
  switch (status) {
    case 'uploaded':
      return 'Uploaded';
    case 'masking':
      return 'Masking';
    case 'parsing':
      return 'Parsing';
    case 'retrying':
      return 'Retrying';
    case 'parsed':
      return 'Parsed';
    case 'partial':
      return 'Partial';
    case 'failed':
      return 'Failed';
    default:
      return status;
  }
}

function getStatusTone(status: DocumentStatus): string {
  switch (status) {
    case 'parsed':
      return 'border-emerald-200 bg-emerald-50 text-emerald-700';
    case 'partial':
      return 'border-amber-200 bg-amber-50 text-amber-700';
    case 'failed':
      return 'border-red-200 bg-red-50 text-red-700';
    default:
      return 'border-blue-200 bg-blue-50 text-blue-700';
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

function StepRow({
  title,
  description,
  state,
}: {
  title: string;
  description: string;
  state: 'done' | 'active' | 'pending' | 'error';
}) {
  const tone =
    state === 'done'
      ? 'border-emerald-200 bg-emerald-50 text-emerald-700'
      : state === 'active'
        ? 'border-blue-200 bg-blue-50 text-blue-700'
        : state === 'error'
          ? 'border-red-200 bg-red-50 text-red-700'
          : 'border-slate-200 bg-slate-50 text-slate-500';

  const icon =
    state === 'done' ? (
      <CheckCircle2 size={18} />
    ) : state === 'error' ? (
      <AlertTriangle size={18} />
    ) : state === 'active' ? (
      <RefreshCw size={18} className="animate-spin" />
    ) : (
      <Clock3 size={18} />
    );

  return (
    <div className={`flex items-start gap-3 rounded-2xl border p-4 ${tone}`}>
      <div className="mt-0.5">{icon}</div>
      <div>
        <p className="text-sm font-extrabold">{title}</p>
        <p className="mt-1 text-xs font-medium">{description}</p>
      </div>
    </div>
  );
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
  const previewText = useMemo(() => {
    if (!document?.content_text) return '';
    return document.content_text.slice(0, 800);
  }, [document?.content_text]);

  useEffect(() => {
    if (!document || !IN_PROGRESS_STATUSES.has(document.status)) {
      return undefined;
    }

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
      toast.success('Upload, masking, and parsing completed.');
    } else if (document.status === 'partial') {
      toast('Parsing completed with warnings. Review the status panel before continuing.', { icon: '!' });
    } else if (document.status === 'failed') {
      toast.error(document.last_error || 'Parsing failed. Review the error details and retry.');
    }
    lastTerminalStatus.current = document.status;
  }, [document]);

  const startParse = useCallback(async (documentId: string) => {
    setIsStartingParse(true);
    try {
      const started = await api.post<DocumentStatusResponse>(`/api/v1/documents/${documentId}/parse`);
      setDocument(started);
    } catch (error) {
      console.error('Failed to start parsing:', error);
      toast.error('Could not start masking and parsing.');
    } finally {
      setIsStartingParse(false);
    }
  }, []);

  const onDrop = useCallback(
    async (acceptedFiles: File[]) => {
      const file = acceptedFiles[0];
      if (!file || isBusy) return;

      setIsUploading(true);
      const loadingId = toast.loading('Uploading PDF and creating a tracked document...');

      try {
        const formData = new FormData();
        formData.append('file', file);
        if (targetMajor.trim()) {
          formData.append('target_major', targetMajor.trim());
          formData.append('title', `${targetMajor.trim()} intake`);
        }

        const created = await api.post<DocumentStatusResponse>('/api/v1/documents/upload', formData, {
          headers: { 'Content-Type': 'multipart/form-data' },
        });
        setDocument(created);
        toast.success('Upload saved. Masking and parsing will start next.', { id: loadingId });
        await startParse(created.id);
      } catch (error) {
        console.error('Upload flow failed:', error);
        toast.error('Upload failed. Please retry with a valid PDF.', { id: loadingId });
      } finally {
        setIsUploading(false);
      }
    },
    [isBusy, startParse, targetMajor],
  );

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: { 'application/pdf': ['.pdf'] },
    multiple: false,
    disabled: isBusy,
  });

  const canContinue = Boolean(document && SUCCESS_STATUSES.has(document.status));
  const maskingSummary = document?.parse_metadata?.masking;
  const pageFailures = document?.parse_metadata?.page_failures ?? [];
  const warnings = document?.parse_metadata?.warnings ?? [];

  return (
    <div className="mx-auto max-w-7xl space-y-8">
      <div className="flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <h1 className="text-3xl font-extrabold text-slate-800">
            {user?.displayName || (isGuestSession ? 'Guest' : 'Student')} document intake
          </h1>
          <p className="mt-2 max-w-3xl text-sm font-medium text-slate-500">
            Upload a real school-record PDF, pass it through masking before storage, and track each processing step.
          </p>
        </div>
        <div className="rounded-2xl border border-slate-200 bg-white px-4 py-3 shadow-sm">
          <label className="block text-xs font-extrabold uppercase tracking-[0.18em] text-slate-400">
            Target Major
          </label>
          <input
            value={targetMajor}
            onChange={(event) => setTargetMajor(event.target.value)}
            placeholder="Optional context for the intake project"
            className="mt-2 w-full min-w-[280px] bg-transparent text-sm font-semibold text-slate-700 outline-none placeholder:text-slate-400"
          />
        </div>
      </div>

      <div className="grid grid-cols-1 gap-8 xl:grid-cols-[1.05fr_0.95fr]">
        <section className="space-y-6">
          <div
            {...getRootProps()}
            className={`cursor-pointer rounded-3xl border-2 border-dashed p-8 text-left transition-all clay-card ${
              isDragActive
                ? 'border-blue-400 bg-blue-50'
                : 'border-blue-200 bg-white hover:border-blue-400 hover:bg-slate-50'
            } ${isBusy ? 'cursor-not-allowed opacity-75' : ''}`}
          >
            <input {...getInputProps()} />
            <div className="flex flex-col gap-6 lg:flex-row lg:items-center lg:justify-between">
              <div className="flex items-start gap-4">
                <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-gradient-to-br from-blue-500 to-cyan-500 text-white shadow-lg shadow-blue-500/20">
                  <FileUp size={30} />
                </div>
                <div>
                  <h2 className="text-2xl font-extrabold text-slate-800">Upload school-record PDF</h2>
                  <p className="mt-2 max-w-xl text-sm font-medium leading-6 text-slate-500">
                    The backend will create a tracked document resource first, then apply masking before it stores parsed text and chunks.
                  </p>
                </div>
              </div>
              <div className="rounded-2xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm font-bold text-emerald-700">
                {isBusy ? 'Processing in progress' : 'Single PDF, up to 50 MB'}
              </div>
            </div>
          </div>

          <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
            <StepRow
              title="1. Upload saved"
              description="The file is written to backend storage and assigned a document id."
              state={getStepState(document, 'upload')}
            />
            <StepRow
              title="2. PII masking"
              description="Regex fallback always runs. Presidio augments when available."
              state={getStepState(document, 'masking')}
            />
            <StepRow
              title="3. PDF parsing"
              description="Text, tables, chunks, and parse metadata are persisted with status."
              state={getStepState(document, 'parsing')}
            />
          </div>

          <div className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm">
            <div className="flex flex-wrap items-center gap-3">
              <span className={`rounded-full border px-3 py-1 text-xs font-extrabold uppercase tracking-[0.16em] ${getStatusTone(document?.status ?? 'uploaded')}`}>
                {document ? formatStatusLabel(document.status) : 'Waiting'}
              </span>
              {document ? (
                <span className="rounded-full border border-slate-200 bg-slate-50 px-3 py-1 text-xs font-bold text-slate-600">
                  Attempts: {document.parse_attempts}
                </span>
              ) : null}
              {document?.masking_status ? (
                <span className="rounded-full border border-slate-200 bg-slate-50 px-3 py-1 text-xs font-bold text-slate-600">
                  Masking: {document.masking_status}
                </span>
              ) : null}
            </div>

            <div className="mt-5 grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
              <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
                <p className="text-xs font-extrabold uppercase tracking-[0.16em] text-slate-400">File</p>
                <p className="mt-2 text-sm font-bold text-slate-700">{document?.original_filename || 'No file yet'}</p>
              </div>
              <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
                <p className="text-xs font-extrabold uppercase tracking-[0.16em] text-slate-400">Size</p>
                <p className="mt-2 text-sm font-bold text-slate-700">{formatBytes(document?.file_size_bytes ?? null)}</p>
              </div>
              <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
                <p className="text-xs font-extrabold uppercase tracking-[0.16em] text-slate-400">Pages</p>
                <p className="mt-2 text-sm font-bold text-slate-700">{document?.page_count ?? 0}</p>
              </div>
              <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
                <p className="text-xs font-extrabold uppercase tracking-[0.16em] text-slate-400">Chunks</p>
                <p className="mt-2 text-sm font-bold text-slate-700">{document?.parse_metadata?.chunk_count ?? 0}</p>
              </div>
            </div>

            {document ? (
              <div className="mt-5 flex flex-wrap gap-3">
                <button
                  type="button"
                  onClick={() => startParse(document.id)}
                  disabled={!document.can_retry || isBusy}
                  className="inline-flex items-center gap-2 rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm font-extrabold text-slate-700 transition-colors hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-50"
                >
                  <TimerReset size={16} />
                  Retry parsing
                </button>
                <button
                  type="button"
                  onClick={() => navigate(`/workshop/${document.project_id}?major=${encodeURIComponent(targetMajor.trim())}`)}
                  disabled={!canContinue}
                  className="inline-flex items-center gap-2 rounded-2xl bg-slate-900 px-4 py-3 text-sm font-extrabold text-white transition-colors hover:bg-slate-800 disabled:cursor-not-allowed disabled:bg-slate-300"
                >
                  Continue to workshop
                  <ArrowRight size={16} />
                </button>
              </div>
            ) : null}
          </div>
        </section>

        <section className="space-y-6">
          <div className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm">
            <div className="flex items-center gap-3">
              <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-slate-900 text-white">
                <ShieldCheck size={22} />
              </div>
              <div>
                <h2 className="text-lg font-extrabold text-slate-800">Masking summary</h2>
                <p className="text-sm font-medium text-slate-500">Stored and indexed text must pass a masking path first.</p>
              </div>
            </div>

            <div className="mt-5 grid grid-cols-1 gap-4 sm:grid-cols-3">
              <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
                <p className="text-xs font-extrabold uppercase tracking-[0.16em] text-slate-400">Method</p>
                <p className="mt-2 text-sm font-bold text-slate-700">
                  {maskingSummary?.methods?.join(', ') || 'Pending'}
                </p>
              </div>
              <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
                <p className="text-xs font-extrabold uppercase tracking-[0.16em] text-slate-400">Replacements</p>
                <p className="mt-2 text-sm font-bold text-slate-700">{maskingSummary?.replacement_count ?? 0}</p>
              </div>
              <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
                <p className="text-xs font-extrabold uppercase tracking-[0.16em] text-slate-400">Tables kept</p>
                <p className="mt-2 text-sm font-bold text-slate-700">{document?.parse_metadata?.table_count ?? 0}</p>
              </div>
            </div>

            <div className="mt-5 rounded-2xl border border-slate-200 bg-slate-50 p-4">
              <p className="text-xs font-extrabold uppercase tracking-[0.16em] text-slate-400">Regex hit summary</p>
              <div className="mt-3 flex flex-wrap gap-2">
                {Object.entries(maskingSummary?.pattern_hits ?? {}).length ? (
                  Object.entries(maskingSummary?.pattern_hits ?? {}).map(([key, value]) => (
                    <span
                      key={key}
                      className="rounded-full border border-slate-200 bg-white px-3 py-1 text-xs font-bold text-slate-700"
                    >
                      {key}: {value}
                    </span>
                  ))
                ) : (
                  <span className="text-sm font-medium text-slate-500">No regex replacements recorded yet.</span>
                )}
              </div>
            </div>
          </div>

          <div className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm">
            <div className="flex items-center gap-3">
              <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-blue-50 text-blue-600">
                <FileText size={22} />
              </div>
              <div>
                <h2 className="text-lg font-extrabold text-slate-800">Parsed preview</h2>
                <p className="text-sm font-medium text-slate-500">This preview is already masked before it is shown here.</p>
              </div>
            </div>

            <div className="mt-5 rounded-2xl border border-slate-200 bg-slate-950 p-4 text-sm leading-6 text-slate-100">
              <pre className="whitespace-pre-wrap break-words font-mono">
                {previewText || 'No parsed text available yet.'}
              </pre>
            </div>
          </div>

          {(warnings.length || pageFailures.length || document?.last_error) ? (
            <div className="rounded-3xl border border-amber-200 bg-amber-50 p-6 shadow-sm">
              <div className="flex items-center gap-3">
                <AlertTriangle size={20} className="text-amber-600" />
                <h2 className="text-lg font-extrabold text-amber-900">Warnings and recovery details</h2>
              </div>
              <div className="mt-4 space-y-3 text-sm font-medium text-amber-900">
                {document?.last_error ? <p>{document.last_error}</p> : null}
                {warnings.map((warning) => (
                  <p key={warning}>{warning}</p>
                ))}
                {pageFailures.map((failure, index) => (
                  <p key={`${failure.page_number ?? 'na'}-${index}`}>
                    Page {failure.page_number ?? '?'}: {failure.message || 'Unknown parsing issue'}
                  </p>
                ))}
              </div>
            </div>
          ) : null}
        </section>
      </div>
    </div>
  );
}
