import React from 'react';
import { AlertTriangle, CheckCircle2, Clock3, Loader2, RefreshCw, RotateCcw } from 'lucide-react';
import { type AsyncJobRead, formatAsyncJobStatus, formatDateTime } from '../lib/diagnosis';
import {
  isDiagnosisLongRunning,
  resolveDiagnosisJobMessage,
  resolveDiagnosisJobProgressPercent,
  resolveDiagnosisJobStageLabel,
  resolveDiagnosisJobVisualStatus,
  type DiagnosisJobVisualStatus,
} from '../lib/diagnosisProgress';
import { PrimaryButton, SectionCard, StatusBadge, WorkflowNotice } from './primitives';

interface AsyncJobStatusCardProps {
  job: AsyncJobRead | null;
  runStatus: string | null | undefined;
  runStatusMessage?: string | null;
  errorMessage?: string | null;
  onRetry?: (() => void) | null;
  isRetrying?: boolean;
}

function statusVariant(status: DiagnosisJobVisualStatus): 'neutral' | 'active' | 'success' | 'warning' | 'danger' {
  if (status === 'succeeded') return 'success';
  if (status === 'failed') return 'danger';
  if (status === 'retrying' || status === 'stale') return 'warning';
  if (status === 'running') return 'active';
  return 'neutral';
}

function statusIcon(status: DiagnosisJobVisualStatus) {
  if (status === 'succeeded') return <CheckCircle2 size={16} />;
  if (status === 'failed') return <AlertTriangle size={16} />;
  if (status === 'retrying') return <RefreshCw size={16} />;
  if (status === 'stale') return <AlertTriangle size={16} />;
  if (status === 'running') return <Loader2 size={16} className="animate-spin" />;
  return <Clock3 size={16} />;
}

function statusLabel(status: DiagnosisJobVisualStatus): string {
  if (status === 'stale') return '지연 복구 중';
  return formatAsyncJobStatus(status);
}

function fallbackProgressWidth(status: DiagnosisJobVisualStatus): number {
  if (status === 'queued') return 10;
  if (status === 'running') return 35;
  if (status === 'retrying') return 28;
  if (status === 'stale') return 22;
  if (status === 'failed') return 100;
  if (status === 'succeeded') return 100;
  return 8;
}

export function AsyncJobStatusCard({
  job,
  runStatus,
  runStatusMessage,
  errorMessage,
  onRetry,
  isRetrying = false,
}: AsyncJobStatusCardProps) {
  const status = resolveDiagnosisJobVisualStatus(job, runStatus);
  const failure = job?.failure_reason || errorMessage || null;
  const stage = resolveDiagnosisJobStageLabel(job, runStatusMessage, status);
  const message = resolveDiagnosisJobMessage(job, runStatusMessage, status);
  const progressPct = resolveDiagnosisJobProgressPercent(job, status);
  const isLongRunning = isDiagnosisLongRunning(job, status);
  const history = (job?.progress_history || [])
    .filter((item) => item && (item.stage || item.message))
    .slice(-4);
  const progressWidth = progressPct ?? fallbackProgressWidth(status);

  return (
    <SectionCard
      title="진단 작업 상태"
      description="현재 단계와 최근 상태를 기반으로 진행 상황을 안내합니다."
      eyebrow="진행 상태"
      data-testid="diagnosis-job-status"
      actions={(
        <StatusBadge status={statusVariant(status)}>
          <span className="inline-flex items-center gap-1">
            {statusIcon(status)}
            {statusLabel(status)}
          </span>
        </StatusBadge>
      )}
    >
      <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
        <div className="mb-3 flex items-start justify-between gap-3">
          <div>
            <p className="text-xs font-bold uppercase tracking-[0.14em] text-slate-400">현재 단계</p>
            <p className="mt-1 text-sm font-bold text-slate-800">{stage}</p>
            <p className="mt-1 text-xs font-medium text-slate-500">{message}</p>
          </div>
          <div className="text-right">
            {progressPct !== null ? (
              <p className="text-lg font-bold text-slate-900">{progressPct}%</p>
            ) : (
              <p className="text-xs font-semibold text-slate-500">단계 기반 진행 추적</p>
            )}
            {formatDateTime(job?.updated_at || job?.completed_at) ? (
              <p className="text-[11px] font-medium text-slate-400">{formatDateTime(job?.updated_at || job?.completed_at)}</p>
            ) : null}
          </div>
        </div>
        <div className="h-2 overflow-hidden rounded-full bg-slate-200">
          <div
            className={
              status === 'failed'
                ? 'h-full rounded-full bg-red-500'
                : progressPct === null && (status === 'running' || status === 'retrying' || status === 'stale')
                  ? 'h-full rounded-full bg-[#004aad] animate-pulse'
                  : 'h-full rounded-full bg-[#004aad] transition-[width] duration-500'
            }
            style={{ width: `${progressWidth}%` }}
          />
        </div>
      </div>

      {isLongRunning ? (
        <WorkflowNotice
          tone="warning"
          title="예상보다 오래 걸리고 있습니다."
          description="자동 복구와 재시도를 계속 진행 중입니다. 완료 또는 실패 상태가 확정되면 즉시 반영됩니다."
        />
      ) : null}

      {history.length ? (
        <div className="space-y-2">
          <p className="text-xs font-bold uppercase tracking-[0.14em] text-slate-400">최근 기록</p>
          <div className="space-y-1.5">
            {history.map((item, index) => (
              <div key={`${item.stage || 'stage'}-${index}`} className="flex items-start gap-2 text-xs">
                <span className="mt-1 h-1.5 w-1.5 rounded-full bg-slate-400" />
                <p className="font-semibold text-slate-600">
                  <span className="mr-2 font-bold text-slate-700">{item.stage || '단계'}</span>
                  {item.message || ''}
                </p>
              </div>
            ))}
          </div>
        </div>
      ) : null}

      {failure ? <WorkflowNotice tone="danger" title="확인 필요" description={failure} /> : null}

      {status === 'failed' && onRetry ? (
        <PrimaryButton type="button" data-testid="diagnosis-job-retry" onClick={onRetry} disabled={isRetrying} fullWidth className="mt-2">
          {isRetrying ? <RefreshCw size={16} className="animate-spin" /> : <RotateCcw size={16} />}
          {isRetrying ? '다시 시도 중...' : '실패 단계 다시 시도'}
        </PrimaryButton>
      ) : null}
    </SectionCard>
  );
}
