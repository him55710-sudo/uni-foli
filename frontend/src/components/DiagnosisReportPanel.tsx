import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { Download, FileText, Loader2, RefreshCw } from 'lucide-react';
import toast from 'react-hot-toast';

import { api } from '../lib/api';
import type {
  ConsultantDiagnosisArtifactResponse,
  DiagnosisReportMode,
} from '../lib/diagnosis';
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
}

const MODE_OPTIONS: Array<{
  value: DiagnosisReportMode;
  label: string;
  description: string;
}> = [
  {
    value: 'premium_10p',
    label: 'Premium 10p',
    description: '표지/축분석/섹션진단/로드맵/부록이 포함된 약 10페이지 전문 진단서',
  },
  {
    value: 'compact',
    label: 'Compact',
    description: '핵심 요약 중심의 간결 진단서',
  },
];

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

export function DiagnosisReportPanel({ diagnosisRunId }: DiagnosisReportPanelProps) {
  const [mode, setMode] = useState<DiagnosisReportMode>('premium_10p');
  const [includeAppendix, setIncludeAppendix] = useState(true);
  const [includeCitations, setIncludeCitations] = useState(true);
  const [isLoading, setIsLoading] = useState(false);
  const [isGenerating, setIsGenerating] = useState(false);
  const [isDownloading, setIsDownloading] = useState(false);
  const [artifact, setArtifact] = useState<ConsultantDiagnosisArtifactResponse | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const selectedMode = useMemo(() => MODE_OPTIONS.find((item) => item.value === mode) ?? MODE_OPTIONS[0], [mode]);

  const loadExistingArtifact = useCallback(async () => {
    setIsLoading(true);
    setErrorMessage(null);
    try {
      const existing = await api.get<ConsultantDiagnosisArtifactResponse>(
        `/api/v1/diagnosis/${diagnosisRunId}/report`,
        { params: { report_mode: mode } },
      );
      setArtifact(existing);
      setIncludeAppendix(existing.include_appendix);
      setIncludeCitations(existing.include_citations);
      if (existing.status === 'FAILED') {
        setErrorMessage(existing.error_message || '진단서 생성에 실패했습니다. 재생성해 주세요.');
      }
    } catch (error: any) {
      if (error?.response?.status === 404) {
        setArtifact(null);
        setErrorMessage(null);
      } else {
        setErrorMessage('기존 진단서를 불러오지 못했습니다.');
      }
    } finally {
      setIsLoading(false);
    }
  }, [diagnosisRunId, mode]);

  useEffect(() => {
    void loadExistingArtifact();
  }, [loadExistingArtifact]);

  const generateReport = useCallback(
    async (forceRegenerate: boolean) => {
      setIsGenerating(true);
      setErrorMessage(null);
      try {
        const created = await api.post<ConsultantDiagnosisArtifactResponse>(
          `/api/v1/diagnosis/${diagnosisRunId}/report`,
          {
            report_mode: mode,
            include_appendix: includeAppendix,
            include_citations: includeCitations,
            force_regenerate: forceRegenerate,
          },
        );
        setArtifact(created);
        if (created.status === 'FAILED') {
          setErrorMessage(created.error_message || '진단서 생성에 실패했습니다.');
          toast.error('진단서 생성 실패');
          return;
        }
        toast.success('전문 진단서가 생성되었습니다.');
      } catch (error: any) {
        const detail = error?.response?.data?.detail;
        const message =
          typeof detail === 'string' && detail.trim()
            ? detail
            : '진단서 생성 중 오류가 발생했습니다.';
        setErrorMessage(message);
        toast.error(message);
      } finally {
        setIsGenerating(false);
      }
    },
    [diagnosisRunId, includeAppendix, includeCitations, mode],
  );

  const downloadReport = useCallback(async () => {
    setIsDownloading(true);
    try {
      const response = await api.download(`/api/v1/diagnosis/${diagnosisRunId}/report.pdf`, {
        params: {
          artifact_id: artifact?.id ?? undefined,
          report_mode: mode,
          include_appendix: includeAppendix,
          include_citations: includeCitations,
          force_regenerate: false,
        },
      });
      const filename = parseFilename(
        response.contentDisposition,
        `consultant-diagnosis-${diagnosisRunId}.pdf`,
      );

      const url = URL.createObjectURL(response.blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = filename;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      URL.revokeObjectURL(url);
      toast.success('PDF 다운로드를 시작합니다.');
    } catch {
      toast.error('PDF 다운로드에 실패했습니다.');
    } finally {
      setIsDownloading(false);
    }
  }, [artifact?.id, diagnosisRunId, includeAppendix, includeCitations, mode]);

  return (
    <SectionCard
      title="전문 진단서"
      eyebrow="Consultant Report"
      description="진단 결과를 근거 중심의 컨설턴트 형식으로 재구성해 PDF로 제공합니다."
      actions={
        <div className="flex items-center gap-2">
          <StatusBadge status={artifact?.status === 'READY' ? 'success' : artifact?.status === 'FAILED' ? 'danger' : 'neutral'}>
            {artifact?.status === 'READY' ? '준비됨' : artifact?.status === 'FAILED' ? '실패' : '미생성'}
          </StatusBadge>
        </div>
      }
    >
      <div className="space-y-4">
        <div className="grid gap-2 sm:grid-cols-2">
          {MODE_OPTIONS.map((option) => (
            <button
              type="button"
              key={option.value}
              onClick={() => setMode(option.value)}
              className={`rounded-xl border px-3 py-3 text-left transition-colors ${
                mode === option.value
                  ? 'border-blue-400 bg-blue-50'
                  : 'border-slate-200 bg-white hover:border-slate-300'
              }`}
            >
              <p className="text-sm font-bold text-slate-800">{option.label}</p>
              <p className="mt-1 text-xs font-medium leading-5 text-slate-600">{option.description}</p>
            </button>
          ))}
        </div>

        <div className="flex flex-wrap items-center gap-4 text-sm font-medium text-slate-700">
          <label className="inline-flex items-center gap-2">
            <input
              type="checkbox"
              checked={includeAppendix}
              onChange={(event) => setIncludeAppendix(event.target.checked)}
              className="h-4 w-4 rounded border-slate-300 text-blue-600"
            />
            부록 포함
          </label>
          <label className="inline-flex items-center gap-2">
            <input
              type="checkbox"
              checked={includeCitations}
              onChange={(event) => setIncludeCitations(event.target.checked)}
              className="h-4 w-4 rounded border-slate-300 text-blue-600"
            />
            인용/근거 라인 포함
          </label>
        </div>

        {errorMessage ? (
          <WorkflowNotice tone="danger" title="진단서 상태" description={errorMessage} />
        ) : (
          <WorkflowNotice
            tone="info"
            title={`선택 모드: ${selectedMode.label}`}
            description={selectedMode.description}
          />
        )}

        <div className="flex flex-wrap items-center gap-2">
          <PrimaryButton onClick={() => generateReport(false)} disabled={isGenerating || isLoading}>
            {isGenerating ? <Loader2 size={14} className="animate-spin" /> : <FileText size={14} />}
            전문 진단서 생성
          </PrimaryButton>
          <SecondaryButton onClick={() => generateReport(true)} disabled={isGenerating || isLoading}>
            <RefreshCw size={14} />
            재생성
          </SecondaryButton>
          <SecondaryButton onClick={downloadReport} disabled={!artifact || artifact.status !== 'READY' || isDownloading}>
            {isDownloading ? <Loader2 size={14} className="animate-spin" /> : <Download size={14} />}
            PDF 다운로드
          </SecondaryButton>
        </div>

        {isLoading ? (
          <div className="flex items-center gap-2 text-sm font-medium text-slate-500">
            <Loader2 size={16} className="animate-spin" />
            기존 진단서 확인 중...
          </div>
        ) : null}

        {artifact?.payload ? (
          <SurfaceCard tone="muted" padding="sm" className="space-y-3">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <p className="text-sm font-bold text-slate-800">{artifact.payload.title}</p>
              <StatusBadge status="neutral">v{artifact.version}</StatusBadge>
            </div>
            <p className="text-sm font-medium leading-6 text-slate-600">{artifact.payload.subtitle}</p>
            <div className="grid gap-2 md:grid-cols-2">
              {artifact.payload.sections.slice(0, 6).map((section) => (
                <div key={section.id} className="rounded-lg border border-slate-200 bg-white p-3">
                  <p className="text-sm font-bold text-slate-800">{section.title}</p>
                  <p className="mt-1 line-clamp-3 text-xs font-medium leading-5 text-slate-600">
                    {section.body_markdown}
                  </p>
                </div>
              ))}
            </div>
          </SurfaceCard>
        ) : null}
      </div>
    </SectionCard>
  );
}
