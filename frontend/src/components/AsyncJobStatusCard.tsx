import React from 'react';
import {
  AlertTriangle,
  CheckCircle2,
  Clock3,
  Loader2,
  RefreshCw,
  RotateCcw,
} from 'lucide-react';
import { type AsyncJobRead, formatAsyncJobStatus, formatDateTime } from '../lib/diagnosis';

interface AsyncJobStatusCardProps {
  job: AsyncJobRead | null;
  runStatus: string | null | undefined;
  errorMessage?: string | null;
  onRetry?: (() => void) | null;
  isRetrying?: boolean;
}

function statusTone(status: string | null | undefined): string {
  switch (status) {
    case 'succeeded':
      return 'border-emerald-200 bg-emerald-50 text-emerald-700';
    case 'failed':
      return 'border-red-200 bg-red-50 text-red-700';
    case 'retrying':
      return 'border-amber-200 bg-amber-50 text-amber-700';
    case 'running':
      return 'border-blue-200 bg-blue-50 text-blue-700';
    default:
      return 'border-slate-200 bg-slate-50 text-slate-600';
  }
}

function statusIcon(status: string | null | undefined) {
  switch (status) {
    case 'succeeded':
      return <CheckCircle2 size={18} />;
    case 'failed':
      return <AlertTriangle size={18} />;
    case 'retrying':
      return <RefreshCw size={18} className="animate-spin" />;
    case 'running':
      return <Loader2 size={18} className="animate-spin" />;
    default:
      return <Clock3 size={18} />;
  }
}

export function AsyncJobStatusCard({
  job,
  runStatus,
  errorMessage,
  onRetry,
  isRetrying = false,
}: AsyncJobStatusCardProps) {
  const status = job?.status ?? (runStatus ? runStatus.toLowerCase() : 'queued');
  const nextAttempt = formatDateTime(job?.next_attempt_at);
  const startedAt = formatDateTime(job?.started_at);
  const completedAt = formatDateTime(job?.completed_at);
  const failure = job?.failure_reason || errorMessage || null;

  return (
    <div
      data-testid="diagnosis-job-status"
      className={`rounded-3xl border p-5 shadow-sm ${statusTone(status)}`}
    >
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="flex items-start gap-3">
          <div className="mt-0.5">{statusIcon(status)}</div>
          <div>
            <p className="text-xs font-black uppercase tracking-[0.18em] opacity-70">Diagnosis job</p>
            <p className="mt-1 text-lg font-extrabold">{formatAsyncJobStatus(status)}</p>
            <p className="mt-2 text-sm font-medium opacity-80">
              Run status: <span className="font-extrabold">{runStatus || 'PENDING'}</span>
            </p>
          </div>
        </div>

        <div className="rounded-2xl border border-current/15 bg-white/60 px-4 py-3 text-sm font-bold text-slate-700">
          Retries {job?.retry_count ?? 0} / {job?.max_retries ?? 0}
        </div>
      </div>

      <div className="mt-4 grid gap-3 sm:grid-cols-2">
        <div className="rounded-2xl border border-white/60 bg-white/70 p-4 text-sm font-medium text-slate-700">
          <p className="text-xs font-black uppercase tracking-[0.16em] text-slate-400">Started</p>
          <p className="mt-2">{startedAt || 'Not started yet'}</p>
        </div>
        <div className="rounded-2xl border border-white/60 bg-white/70 p-4 text-sm font-medium text-slate-700">
          <p className="text-xs font-black uppercase tracking-[0.16em] text-slate-400">Completed</p>
          <p className="mt-2">{completedAt || 'Still in progress'}</p>
        </div>
      </div>

      {nextAttempt ? (
        <p className="mt-4 text-sm font-medium text-slate-700">
          Next retry window: <span className="font-extrabold">{nextAttempt}</span>
        </p>
      ) : null}

      {failure ? (
        <div className="mt-4 rounded-2xl border border-red-200 bg-white/80 p-4 text-sm font-medium text-slate-700">
          <p className="text-xs font-black uppercase tracking-[0.16em] text-red-500">Failure reason</p>
          <p className="mt-2">{failure}</p>
        </div>
      ) : null}

      {status === 'failed' && onRetry ? (
        <button
          type="button"
          data-testid="diagnosis-job-retry"
          onClick={onRetry}
          disabled={isRetrying}
          className="mt-4 inline-flex items-center gap-2 rounded-2xl bg-slate-900 px-4 py-3 text-sm font-extrabold text-white transition-colors hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-60"
        >
          {isRetrying ? <RefreshCw size={16} className="animate-spin" /> : <RotateCcw size={16} />}
          Retry diagnosis
        </button>
      ) : null}
    </div>
  );
}
