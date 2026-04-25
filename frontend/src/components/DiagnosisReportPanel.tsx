import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { Download, FileText, Loader2, RefreshCw } from 'lucide-react';
import toast from 'react-hot-toast';

import { api } from '../lib/api';
import type { ConsultantDiagnosisArtifactResponse, DiagnosisReportMode } from '../lib/diagnosis';
import {
  PrimaryButton,
  SecondaryButton,
  SectionCard,
  StatusBadge,
  SurfaceCard,
  WorkflowNotice,
} from './primitives';

interface DiagnosisReportPanelProps {
  diagnosisRunId: string;
  reportStatus?: string | null;
  reportAsyncJobStatus?: string | null;
  reportArtifactId?: string | null;
  reportErrorMessage?: string | null;
}

const FIXED_REPORT_MODE: DiagnosisReportMode = 'premium';
const REPORT_IN_PROGRESS_STATUS = new Set(['AUTO_STARTING', 'QUEUED', 'RUNNING', 'RETRYING', 'SUCCEEDED']);
const REPORT_SYNC_MAX_RETRIES = 24;
const REPORT_POLL_INTERVAL_MS = 2500;

function parseFilename(contentDisposition: string | undefined, fallback: string): string {
  if (!contentDisposition) return fallback;

  const utf8Match = contentDisposition.match(/filename\*=UTF-8''([^;]+)/i);
  if (utf8Match?.[1]) {
    try {
      return decodeURIComponent(utf8Match[1]);
    } catch {
      return fallback;
    }
  }

  const simpleMatch = contentDisposition.match(/filename="?([^";]+)"?/i);
  if (!simpleMatch?.[1]) return fallback;
  return simpleMatch[1];
}

function normalizeStatus(value: string | null | undefined): string | null {
  const normalized = (value || '').trim();
  if (!normalized) return null;
  return normalized.toUpperCase();
}

function resolveBadgeStatus(status: string | null): 'success' | 'warning' | 'danger' | 'neutral' {
  if (status === 'READY') return 'success';
  if (status === 'FAILED') return 'danger';
  if (status && REPORT_IN_PROGRESS_STATUS.has(status)) return 'warning';
  return 'neutral';
}

function resolveBadgeLabel(status: string | null): string {
  if (status === 'READY') return '준비 완료';
  if (status === 'FAILED') return '생성 실패';
  if (status && REPORT_IN_PROGRESS_STATUS.has(status)) return '생성 중';
  return '대기 중';
}

function formatDateTimeLabel(value: string | null | undefined): string | null {
  if (!value) return null;
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return null;
  return parsed.toLocaleString('ko-KR', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  });
}

function buildStatusSummary(status: string | null, retries: number): string {
  if (status === 'READY') return '진단 보고서가 준비되었습니다. 바로 내려받을 수 있습니다.';
  if (status === 'FAILED') return '보고서 생성 중 문제가 발생했습니다. 다시 생성 버튼으로 복구해 주세요.';
  if (status && REPORT_IN_PROGRESS_STATUS.has(status)) {
    if (retries > 0) return `보고서를 준비하는 중입니다. 동기화 재시도 ${retries}회 진행 중입니다.`;
    return '진단 결과를 바탕으로 보고서를 생성하고 있습니다.';
  }
  return '아직 보고서가 생성되지 않았습니다.';
}

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => window.setTimeout(resolve, ms));
}

async function extractApiErrorMessage(error: unknown, fallback: string): Promise<string> {
  const anyError = error as any;
  const detail = anyError?.response?.data?.detail;
  if (typeof detail === 'string' && detail.trim()) return detail.trim();

  const blob = anyError?.response?.data;
  if (blob instanceof Blob) {
    try {
      const text = await blob.text();
      const parsed = JSON.parse(text);
      if (typeof parsed?.detail === 'string' && parsed.detail.trim()) {
        return parsed.detail.trim();
      }
      if (typeof parsed?.message === 'string' && parsed.message.trim()) {
        return parsed.message.trim();
      }
    } catch {
      // Keep fallback.
    }
  }
  return fallback;
}

function startBlobDownload(blob: Blob, fileName: string) {
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement('a');
  anchor.href = url;
  anchor.download = fileName;
  document.body.appendChild(anchor);
  anchor.click();
  document.body.removeChild(anchor);
  URL.revokeObjectURL(url);
}

export function DiagnosisReportPanel({
  diagnosisRunId,
  reportStatus,
  reportAsyncJobStatus,
  reportArtifactId,
  reportErrorMessage,
}: DiagnosisReportPanelProps) {
  const [isLoading, setIsLoading] = useState(false);
  const [isGenerating, setIsGenerating] = useState(false);
  const [isDownloading, setIsDownloading] = useState(false);
  const [artifact, setArtifact] = useState<ConsultantDiagnosisArtifactResponse | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [reportSyncRetries, setReportSyncRetries] = useState(0);

  const payload = artifact?.payload ?? null;
  const normalizedRunStatus = normalizeStatus(reportStatus) ?? normalizeStatus(reportAsyncJobStatus);
  const normalizedArtifactStatus = normalizeStatus(artifact?.status ?? null);
  const effectiveStatus = normalizedArtifactStatus ?? normalizedRunStatus;

  const shouldPollReport = useMemo(() => {
    if (reportSyncRetries >= REPORT_SYNC_MAX_RETRIES) return false;
    if (artifact?.status === 'READY') return false;
    if (normalizedRunStatus === 'READY' && !artifact) return true;
    return Boolean(normalizedRunStatus && REPORT_IN_PROGRESS_STATUS.has(normalizedRunStatus));
  }, [artifact, normalizedRunStatus, reportSyncRetries]);

  const canDownloadReport = Boolean(
    (artifact && artifact.status === 'READY') ||
    (normalizedRunStatus === 'READY' && reportArtifactId),
  );

  const fetchArtifact = useCallback(
    async (artifactId?: string | null) => {
      const params: Record<string, string | number> = {
        report_mode: FIXED_REPORT_MODE,
        _ts: Date.now(),
      };
      if (artifactId) params.artifact_id = artifactId;
      return api.get<ConsultantDiagnosisArtifactResponse>(
        `/api/v1/diagnosis/${diagnosisRunId}/report`,
        { params },
      );
    },
    [diagnosisRunId],
  );

  const loadExistingArtifact = useCallback(async () => {
    setIsLoading(true);
    setErrorMessage(null);
    try {
      const artifactId = normalizedRunStatus === 'READY' ? reportArtifactId : undefined;
      const existing = await fetchArtifact(artifactId);
      setArtifact(existing);
      setReportSyncRetries(0);
      if (existing.status === 'FAILED') {
        setErrorMessage(existing.error_message || '보고서 생성에 실패했습니다. 다시 시도해 주세요.');
      }
    } catch (error: any) {
      if (error?.response?.status === 404) {
        setArtifact(null);
        if (normalizedRunStatus === 'READY') {
          setReportSyncRetries((prev) => prev + 1);
          setErrorMessage('보고서 동기화가 지연되고 있습니다. 잠시 후 자동으로 다시 시도합니다.');
        }
      } else {
        setErrorMessage(
          reportErrorMessage ||
          '보고서 정보를 불러오는 중 오류가 발생했습니다. 잠시 후 다시 시도해 주세요.',
        );
      }
    } finally {
      setIsLoading(false);
    }
  }, [fetchArtifact, normalizedRunStatus, reportArtifactId, reportErrorMessage]);

  useEffect(() => {
    void loadExistingArtifact();
  }, [loadExistingArtifact]);

  useEffect(() => {
    if (!shouldPollReport) return undefined;
    const timer = window.setInterval(() => {
      void loadExistingArtifact();
    }, REPORT_POLL_INTERVAL_MS);
    return () => window.clearInterval(timer);
  }, [loadExistingArtifact, shouldPollReport]);

  const generateReport = useCallback(async (forceRegenerate: boolean) => {
    setIsGenerating(true);
    setErrorMessage(null);
    try {
      const created = await api.post<ConsultantDiagnosisArtifactResponse>(
        `/api/v1/diagnosis/${diagnosisRunId}/report`,
        {
          report_mode: FIXED_REPORT_MODE,
          include_appendix: true,
          include_citations: true,
          force_regenerate: forceRegenerate,
        },
      );
      setArtifact(created);
      if (created.status === 'FAILED') {
        const detail = created.error_message || '보고서 생성에 실패했습니다.';
        setErrorMessage(detail);
        toast.error(detail);
        return;
      }
      toast.success('진단 보고서 생성을 시작했습니다.');
    } catch (error) {
      const message = await extractApiErrorMessage(error, '보고서 생성 중 오류가 발생했습니다.');
      setErrorMessage(message);
      toast.error(message);
    } finally {
      setIsGenerating(false);
    }
  }, [diagnosisRunId]);

  const waitForReadyArtifact = useCallback(async (artifactId?: string | null) => {
    for (let attempt = 0; attempt < 8; attempt += 1) {
      const latest = await fetchArtifact(artifactId);
      setArtifact(latest);
      if (latest.status === 'READY') return latest;
      if (latest.status === 'FAILED') {
        throw new Error(latest.error_message || '보고서 생성에 실패했습니다.');
      }
      await sleep(1200);
    }
    return null;
  }, [fetchArtifact]);

  const requestPdf = useCallback(
    async (artifactId?: string | null, forceRegenerate = false) =>
      api.download(`/api/v1/diagnosis/${diagnosisRunId}/report.pdf`, {
        params: {
          artifact_id: artifactId ?? undefined,
          report_mode: FIXED_REPORT_MODE,
          include_appendix: true,
          include_citations: true,
          force_regenerate: forceRegenerate,
        },
      }),
    [diagnosisRunId],
  );

  const downloadReport = useCallback(async () => {
    setIsDownloading(true);
    setErrorMessage(null);
    const initialArtifactId = artifact?.id ?? reportArtifactId ?? null;

    try {
      const direct = await requestPdf(initialArtifactId, false);
      const fileName = parseFilename(direct.contentDisposition, '진단보고서.pdf');
      startBlobDownload(direct.blob, fileName);
      toast.success('진단서 파일 다운로드를 시작합니다.');
      return;
    } catch {
      // 아래 재생성 복구 로직으로 이동
    }

    try {
      const regenerated = await api.post<ConsultantDiagnosisArtifactResponse>(
        `/api/v1/diagnosis/${diagnosisRunId}/report`,
        {
          report_mode: FIXED_REPORT_MODE,
          include_appendix: true,
          include_citations: true,
          force_regenerate: true,
        },
      );
      setArtifact(regenerated);

      const readyArtifact =
        regenerated.status === 'READY'
          ? regenerated
          : await waitForReadyArtifact(regenerated.id);

      if (!readyArtifact || readyArtifact.status !== 'READY') {
        throw new Error('보고서 준비가 완료되지 않았습니다. 잠시 후 다시 시도해 주세요.');
      }

      const recovered = await requestPdf(readyArtifact.id, true);
      const fileName = parseFilename(recovered.contentDisposition, '진단보고서.pdf');
      startBlobDownload(recovered.blob, fileName);
      toast.success('진단서 파일 다운로드를 시작합니다.');
    } catch (error) {
      const message = await extractApiErrorMessage(error, '진단서 파일 다운로드에 실패했습니다.');
      setErrorMessage(message);
      toast.error(message);
    } finally {
      setIsDownloading(false);
    }
  }, [artifact?.id, diagnosisRunId, reportArtifactId, requestPdf, waitForReadyArtifact]);

  const statusSummary = buildStatusSummary(effectiveStatus, reportSyncRetries);
  const reportStateMessage = reportErrorMessage || errorMessage;
  const lastUpdatedLabel = formatDateTimeLabel(artifact?.updated_at || payload?.generated_at || null);

  return (
    <SectionCard
      title="진단 보고서"
      eyebrow="고정 템플릿"
      description="내부 표준 템플릿으로 자동 생성됩니다."
      actions={<StatusBadge status={resolveBadgeStatus(effectiveStatus)}>{resolveBadgeLabel(effectiveStatus)}</StatusBadge>}
    >
      <div className="space-y-4">
        {reportStateMessage && (artifact?.status === 'FAILED' || normalizedRunStatus === 'FAILED') ? (
          <WorkflowNotice tone="danger" title="보고서 상태" description={reportStateMessage} />
        ) : null}

        <SurfaceCard tone="muted" padding="sm" className="space-y-3">
          <p className="text-sm font-semibold text-slate-700">{statusSummary}</p>
          {lastUpdatedLabel ? (
            <p className="text-xs font-semibold text-slate-500">최근 갱신: {lastUpdatedLabel}</p>
          ) : null}
          {payload ? (
            <div className="grid gap-2 sm:grid-cols-3">
              <p className="rounded-xl bg-white px-3 py-2 text-xs font-semibold text-slate-600">섹션 {payload.sections.length}개</p>
              <p className="rounded-xl bg-white px-3 py-2 text-xs font-semibold text-slate-600">근거 {payload.citations.length}건</p>
              <p className="rounded-xl bg-white px-3 py-2 text-xs font-semibold text-slate-600">로드맵 {payload.roadmap.length}단계</p>
            </div>
          ) : null}
          <div className="flex flex-wrap gap-2">
            {canDownloadReport ? (
              <PrimaryButton onClick={downloadReport} disabled={isDownloading}>
                {isDownloading ? <Loader2 size={14} className="animate-spin" /> : <Download size={14} />}
                진단서 내려받기
              </PrimaryButton>
            ) : (
              <PrimaryButton onClick={() => generateReport(false)} disabled={isGenerating || isLoading}>
                {isGenerating ? <Loader2 size={14} className="animate-spin" /> : <FileText size={14} />}
                보고서 생성
              </PrimaryButton>
            )}
            <SecondaryButton onClick={() => generateReport(true)} disabled={isGenerating || isLoading || isDownloading}>
              <RefreshCw size={14} />
              다시 생성
            </SecondaryButton>
          </div>
        </SurfaceCard>

        {isLoading ? (
          <div className="flex items-center gap-2 text-sm font-medium text-slate-500">
            <Loader2 size={16} className="animate-spin" />
            보고서 정보를 불러오는 중입니다...
          </div>
        ) : null}
      </div>
    </SectionCard>
  );
}
