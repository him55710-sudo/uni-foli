import type { AsyncJobRead } from './diagnosis';

export type DiagnosisJobVisualStatus =
  | 'queued'
  | 'running'
  | 'retrying'
  | 'stale'
  | 'failed'
  | 'succeeded'
  | 'unknown';

const DEFAULT_STALE_AFTER_MS = 90_000;
const DEFAULT_LONG_RUNNING_AFTER_MS = 120_000;

function normalizeStatus(raw: string | null | undefined): string {
  return String(raw || '').trim().toLowerCase();
}

function parseTime(value: string | null | undefined): number | null {
  if (!value) return null;
  const parsed = new Date(value).getTime();
  if (!Number.isFinite(parsed)) return null;
  return parsed;
}

function latestUpdateMs(job: AsyncJobRead | null, nowMs: number): number | null {
  if (!job) return null;
  const candidates = [
    parseTime(job.updated_at),
    parseTime(job.started_at),
    parseTime(job.created_at),
  ].filter((item): item is number => item !== null);
  if (!candidates.length) return null;
  return Math.min(nowMs, Math.max(...candidates));
}

function looksStaleSignal(job: AsyncJobRead | null): boolean {
  const stage = normalizeStatus(job?.progress_stage);
  const message = normalizeStatus(job?.progress_message);
  const reason = normalizeStatus(job?.failure_reason);
  return (
    stage.includes('stale') ||
    message.includes('stale') ||
    message.includes('recover') ||
    reason.includes('stale')
  );
}

export function resolveDiagnosisJobVisualStatus(
  job: AsyncJobRead | null,
  runStatus: string | null | undefined,
  options?: { nowMs?: number; staleAfterMs?: number },
): DiagnosisJobVisualStatus {
  const jobStatus = normalizeStatus(job?.status);
  const fallbackStatus = normalizeStatus(runStatus);
  const status = jobStatus || fallbackStatus;

  if (status === 'succeeded' || status === 'completed' || status === 'success') return 'succeeded';
  if (status === 'failed') return 'failed';
  if (status === 'queued' || status === 'pending') return 'queued';

  if (status === 'retrying') {
    if (looksStaleSignal(job)) return 'stale';
    return 'retrying';
  }

  if (status === 'running') {
    if (looksStaleSignal(job)) return 'stale';
    const nowMs = options?.nowMs ?? Date.now();
    const staleAfterMs = Math.max(15_000, options?.staleAfterMs ?? DEFAULT_STALE_AFTER_MS);
    const updateMs = latestUpdateMs(job, nowMs);
    if (updateMs !== null && nowMs - updateMs >= staleAfterMs) return 'stale';
    return 'running';
  }

  return 'unknown';
}

function toTitleCaseFromSnake(raw: string): string {
  const normalized = String(raw || '').trim();
  if (!normalized) return '';
  return normalized
    .split(/[_\-\s]+/)
    .map((word) => (word ? `${word[0].toUpperCase()}${word.slice(1)}` : ''))
    .join(' ')
    .trim();
}

export function resolveDiagnosisJobStageLabel(
  job: AsyncJobRead | null,
  runStatusMessage: string | null | undefined,
  visualStatus: DiagnosisJobVisualStatus,
): string {
  const stageFromJob = toTitleCaseFromSnake(String(job?.progress_stage || ''));
  if (stageFromJob) return stageFromJob;

  const fromRun = String(runStatusMessage || '').trim();
  if (fromRun) return fromRun;

  if (visualStatus === 'queued') return '작업 대기';
  if (visualStatus === 'running') return '진행 중';
  if (visualStatus === 'retrying') return '재시도 진행';
  if (visualStatus === 'stale') return '지연 감지 및 복구 중';
  if (visualStatus === 'failed') return '실패';
  if (visualStatus === 'succeeded') return '완료';
  return '상태 확인 중';
}

export function resolveDiagnosisJobMessage(
  job: AsyncJobRead | null,
  runStatusMessage: string | null | undefined,
  visualStatus: DiagnosisJobVisualStatus,
): string {
  const runMessage = String(runStatusMessage || '').trim();
  if (runMessage) return runMessage;

  const jobMessage = String(job?.progress_message || '').trim();
  if (jobMessage) return jobMessage;

  if (visualStatus === 'queued') return '작업 순서를 대기하고 있습니다.';
  if (visualStatus === 'running') return '단계별 진단 처리를 진행하고 있습니다.';
  if (visualStatus === 'retrying') return '일시적 오류를 복구하기 위해 자동 재시도 중입니다.';
  if (visualStatus === 'stale') return '예상보다 오래 걸려 자동 복구를 시도하고 있습니다.';
  if (visualStatus === 'failed') return '작업이 실패했습니다. 오류 내용을 확인해 주세요.';
  if (visualStatus === 'succeeded') return '진단 처리가 완료되었습니다.';
  return '작업 상태를 확인하고 있습니다.';
}

export function resolveDiagnosisJobProgressPercent(
  job: AsyncJobRead | null,
  visualStatus: DiagnosisJobVisualStatus,
): number | null {
  const raw = (job as AsyncJobRead & { progress_percent?: number | null } | null)?.progress_percent;
  if (typeof raw === 'number' && Number.isFinite(raw)) {
    return Math.max(0, Math.min(100, Math.round(raw)));
  }
  if (visualStatus === 'succeeded') return 100;
  return null;
}

export function isDiagnosisLongRunning(
  job: AsyncJobRead | null,
  visualStatus: DiagnosisJobVisualStatus,
  options?: { nowMs?: number; longRunningAfterMs?: number },
): boolean {
  if (visualStatus !== 'running' && visualStatus !== 'retrying' && visualStatus !== 'stale') return false;
  const nowMs = options?.nowMs ?? Date.now();
  const startedAtMs =
    parseTime(job?.started_at) ??
    parseTime(job?.created_at) ??
    latestUpdateMs(job, nowMs);
  if (startedAtMs === null) return false;
  const threshold = Math.max(30_000, options?.longRunningAfterMs ?? DEFAULT_LONG_RUNNING_AFTER_MS);
  return nowMs - startedAtMs >= threshold;
}
