import React, { useEffect, useMemo, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import {
  ArrowRight,
  ClipboardCheck,
  Download,
  FileText,
  Loader2,
  MessageSquareQuote,
  Trash2,
} from 'lucide-react';

import { DiagnosisReportPanel } from '../components/DiagnosisReportPanel';
import { EmptyState, PrimaryButton, SecondaryButton, StatusBadge, SurfaceCard } from '../components/primitives';
import { useAuth } from '../contexts/AuthContext';
import { api } from '../lib/api';
import { DIAGNOSIS_STORAGE_KEY, mergeDiagnosisPayload, type DiagnosisRunResponse, type StoredDiagnosis } from '../lib/diagnosis';

type CachedDiagnosis = StoredDiagnosis & {
  diagnosisRunId?: string | null;
  reportStatus?: string | null;
  reportArtifactId?: string | null;
  reportErrorMessage?: string | null;
};

function readCachedDiagnosis(): CachedDiagnosis | null {
  if (typeof window === 'undefined') return null;
  try {
    const raw = window.localStorage.getItem(DIAGNOSIS_STORAGE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as CachedDiagnosis;
    return parsed && typeof parsed === 'object' ? parsed : null;
  } catch {
    return null;
  }
}

function normalizeStatus(value: string | null | undefined): string {
  return (value || '').trim().toUpperCase();
}

function statusLabel(value: string | null | undefined): string {
  const status = normalizeStatus(value);
  if (status === 'READY') return '다운로드 가능';
  if (status === 'FAILED') return '생성 실패';
  if (['AUTO_STARTING', 'QUEUED', 'RUNNING', 'RETRYING', 'SUCCEEDED'].includes(status)) return '생성 중';
  return '진단 완료';
}

function statusTone(value: string | null | undefined): 'success' | 'warning' | 'danger' | 'active' | 'neutral' {
  const status = normalizeStatus(value);
  if (status === 'READY') return 'success';
  if (status === 'FAILED') return 'danger';
  if (['AUTO_STARTING', 'QUEUED', 'RUNNING', 'RETRYING', 'SUCCEEDED'].includes(status)) return 'warning';
  return value ? 'active' : 'neutral';
}

export function DiagnosisReports() {
  const navigate = useNavigate();
  const { user, isGuestSession } = useAuth();
  const cached = useMemo(readCachedDiagnosis, []);
  const [run, setRun] = useState<DiagnosisRunResponse | null>(null);
  const [isLoading, setIsLoading] = useState(Boolean(cached?.projectId));
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function loadLatestRun(projectId: string) {
      setIsLoading(true);
      setErrorMessage(null);
      try {
        const latest = await api.get<DiagnosisRunResponse>(`/api/v1/diagnosis/project/${projectId}/latest`);
        if (!cancelled) setRun(latest);
      } catch (error: any) {
        if (!cancelled) {
          if (error?.response?.status !== 404) {
            setErrorMessage('최신 진단서를 불러오지 못했습니다. 잠시 후 다시 확인해 주세요.');
          }
          setRun(null);
        }
      } finally {
        if (!cancelled) setIsLoading(false);
      }
    }

    if (cached?.projectId) {
      void loadLatestRun(cached.projectId);
    } else {
      setIsLoading(false);
    }

    return () => {
      cancelled = true;
    };
  }, [cached?.projectId]);

  const payload = run ? mergeDiagnosisPayload(run) : cached?.diagnosis ?? null;
  const reportStatus = run?.report_status ?? run?.report_async_job_status ?? cached?.reportStatus ?? null;
  const projectId = run?.project_id ?? cached?.projectId ?? null;
  const diagnosisRunId = run?.id ?? cached?.diagnosisRunId ?? null;
  const savedLabel = cached?.savedAt ? new Date(cached.savedAt).toLocaleString('ko-KR') : null;
  const userLabel = user?.displayName || (isGuestSession ? '게스트' : '사용자');

  if (isLoading) {
    return (
      <div className="flex min-h-[50vh] items-center justify-center">
        <div className="flex items-center gap-3 text-sm font-bold text-slate-500">
          <Loader2 size={18} className="animate-spin text-blue-600" />
          진단서 상태를 확인하는 중입니다.
        </div>
      </div>
    );
  }

  if (!payload && !diagnosisRunId) {
    return (
      <div className="mx-auto max-w-5xl space-y-8 py-8">
        <div className="space-y-3">
          <p className="text-sm font-black uppercase tracking-widest text-blue-600">Diagnosis Report</p>
          <h1 className="text-3xl font-black tracking-tight text-slate-950">진단서</h1>
          <p className="max-w-2xl text-sm font-semibold leading-6 text-slate-500">
            생기부 PDF 진단이 끝나면 이곳에서 프리미엄 진단서를 생성하고 다운로드할 수 있습니다.
          </p>
        </div>

        <EmptyState
          icon={<FileText size={24} />}
          title="아직 확인할 진단서가 없습니다."
          description="먼저 AI 진단에서 생기부 PDF를 업로드하면 진단 결과와 다운로드 가능한 진단서가 이 메뉴에 정리됩니다."
          actionLabel="AI 진단 시작하기"
          onAction={() => navigate('/app/diagnosis')}
          className="bg-white"
        />
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-6xl space-y-8 py-8">
      <div className="flex flex-col justify-between gap-5 lg:flex-row lg:items-end">
        <div className="space-y-3">
          <p className="text-sm font-black uppercase tracking-widest text-blue-600">Diagnosis Report</p>
          <h1 className="text-3xl font-black tracking-tight text-slate-950">{userLabel}님의 진단서</h1>
          <p className="max-w-2xl text-sm font-semibold leading-6 text-slate-500">
            AI 진단 결과와 PDF 진단서를 이 화면에서 확인합니다. 탐구 보고서 초안과 저장 문서는 탐구 보관함에서 따로 관리됩니다.
          </p>
        </div>
        <StatusBadge status={statusTone(reportStatus)}>{statusLabel(reportStatus)}</StatusBadge>
      </div>

      {errorMessage ? (
        <div className="rounded-2xl border border-amber-200 bg-amber-50 px-5 py-4 text-sm font-bold text-amber-900">
          {errorMessage}
        </div>
      ) : null}

      <div className="grid gap-4 lg:grid-cols-3">
        <SurfaceCard className="p-6">
          <div className="mb-4 flex h-11 w-11 items-center justify-center rounded-2xl bg-blue-50 text-blue-600">
            <ClipboardCheck size={22} />
          </div>
          <p className="text-xs font-black uppercase tracking-widest text-slate-400">AI 진단 결과</p>
          <h2 className="mt-2 line-clamp-2 text-lg font-black text-slate-950">
            {payload?.headline || '진단 결과 요약'}
          </h2>
          <p className="mt-3 text-sm font-semibold leading-6 text-slate-500">
            {savedLabel ? `최근 저장: ${savedLabel}` : '최근 진단 결과를 기준으로 표시합니다.'}
          </p>
        </SurfaceCard>

        <SurfaceCard className="p-6">
          <div className="mb-4 flex h-11 w-11 items-center justify-center rounded-2xl bg-indigo-50 text-indigo-600">
            <Download size={22} />
          </div>
          <p className="text-xs font-black uppercase tracking-widest text-slate-400">PDF 진단서</p>
          <h2 className="mt-2 text-lg font-black text-slate-950">{statusLabel(reportStatus)}</h2>
          <p className="mt-3 text-sm font-semibold leading-6 text-slate-500">
            아래 패널에서 생성 상태를 확인하고 준비된 PDF를 바로 다운로드할 수 있습니다.
          </p>
        </SurfaceCard>

        <SurfaceCard className="p-6">
          <div className="mb-4 flex h-11 w-11 items-center justify-center rounded-2xl bg-slate-100 text-slate-700">
            <MessageSquareQuote size={22} />
          </div>
          <p className="text-xs font-black uppercase tracking-widest text-slate-400">다음 단계</p>
          <h2 className="mt-2 text-lg font-black text-slate-950">면접 준비로 연결</h2>
          <p className="mt-3 text-sm font-semibold leading-6 text-slate-500">
            진단 결과를 바탕으로 예상 질문을 생성하고 답변 연습까지 이어갈 수 있습니다.
          </p>
        </SurfaceCard>
      </div>

      {diagnosisRunId ? (
        <DiagnosisReportPanel
          diagnosisRunId={diagnosisRunId}
          reportStatus={run?.report_status ?? cached?.reportStatus}
          reportAsyncJobStatus={run?.report_async_job_status}
          reportArtifactId={run?.report_artifact_id ?? cached?.reportArtifactId}
          reportErrorMessage={run?.report_error_message ?? cached?.reportErrorMessage}
        />
      ) : (
        <EmptyState
          icon={<FileText size={24} />}
          title="진단 결과는 있지만 다운로드 실행 정보가 없습니다."
          description="AI 진단 화면에서 최신 진단을 다시 열면 진단서 생성과 다운로드 상태가 연결됩니다."
          actionLabel="AI 진단으로 이동"
          onAction={() => navigate('/app/diagnosis')}
          className="bg-white"
        />
      )}

      <div className="flex flex-wrap gap-3">
        <SecondaryButton onClick={() => navigate('/app/diagnosis')}>AI 진단 다시 보기</SecondaryButton>
        {projectId ? (
          <PrimaryButton onClick={() => navigate(`/app/interview/${projectId}`)}>
            면접 준비 시작 <ArrowRight size={16} />
          </PrimaryButton>
        ) : null}
        <Link to="/app/archive" className="inline-flex items-center rounded-2xl px-4 py-2 text-sm font-black text-slate-500 hover:bg-slate-100">
          탐구 보관함 보기
        </Link>
        <button
          onClick={() => {
            if (confirm('현재 진단 결과를 삭제하고 처음으로 돌아가시겠습니까?')) {
              localStorage.removeItem(DIAGNOSIS_STORAGE_KEY);
              navigate('/app/diagnosis');
              toast.success('진단 결과가 삭제되었습니다.');
            }
          }}
          className="inline-flex items-center gap-2 rounded-2xl px-4 py-2 text-sm font-black text-rose-500 hover:bg-rose-50 transition-colors"
        >
          <Trash2 size={16} />
          결과 삭제
        </button>
      </div>
    </div>
  );
}
