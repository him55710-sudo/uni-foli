import React, { useEffect, useMemo, useState } from 'react';
import { motion } from 'motion/react';
import {
  Activity,
  AlertTriangle,
  BarChart3,
  ClipboardList,
  Database,
  ExternalLink,
  FileText,
  MessageSquare,
  RefreshCcw,
  Search,
  ShieldCheck,
  Users,
} from 'lucide-react';
import toast from 'react-hot-toast';
import { useAuth } from '../contexts/AuthContext';
import { api } from '../lib/api';
import { PageHeader, StatusBadge, SurfaceCard, type StatusBadgeProps } from '../components/primitives';
import { cn } from '../lib/cn';

type StatusTone = NonNullable<StatusBadgeProps['status']>;

interface BreakdownItem {
  status: string;
  count: number;
}

interface AdminStats {
  generated_at: string;
  summary: Record<string, number>;
  growth: Record<string, Record<string, number>>;
  quality: Record<string, number>;
  usage: Record<string, number>;
  breakdowns: Record<string, BreakdownItem[]>;
}

interface AdminProject {
  id: string;
  title: string;
  target_university?: string | null;
  target_major?: string | null;
  status?: string | null;
  created_at: string;
  updated_at?: string | null;
  counts?: Record<string, number>;
  owner?: {
    id?: string | null;
    email?: string | null;
    name?: string | null;
    grade?: string | null;
    target_major?: string | null;
  };
}

interface AdminUpload {
  id: string;
  filename: string;
  content_type?: string | null;
  file_size_bytes?: number | null;
  page_count?: number | null;
  created_at: string;
  ingested_at?: string | null;
  status?: string | null;
  ingest_error?: string | null;
}

interface AdminDocument {
  id: string;
  upload_asset_id?: string | null;
  parser_name?: string | null;
  status?: string | null;
  masking_status?: string | null;
  parse_attempts?: number | null;
  page_count?: number | null;
  word_count?: number | null;
  last_error?: string | null;
  latest_async_job_status?: string | null;
  latest_async_job_error?: string | null;
  updated_at?: string | null;
}

interface AdminDiagnosisRun {
  id: string;
  status?: string | null;
  status_message?: string | null;
  error_message?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
}

interface AdminReport {
  id: string;
  mode?: string | null;
  format?: string | null;
  version?: number | null;
  created_at: string;
  updated_at?: string | null;
  status?: string | null;
  error_message?: string | null;
}

interface AdminAssets {
  uploads: AdminUpload[];
  documents: AdminDocument[];
  diagnosis_runs: AdminDiagnosisRun[];
  reports: AdminReport[];
}

interface AdminLog {
  occurred_at?: string | null;
  category: string;
  severity: string;
  title: string;
  message?: string | null;
  metadata?: Record<string, unknown>;
}

function formatNumber(value: number | null | undefined) {
  return new Intl.NumberFormat('ko-KR').format(Number(value ?? 0));
}

function formatBytes(value: number | null | undefined) {
  const bytes = Number(value ?? 0);
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  if (bytes < 1024 * 1024 * 1024) return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
  return `${(bytes / 1024 / 1024 / 1024).toFixed(1)} GB`;
}

function formatDate(value?: string | null) {
  if (!value) return '-';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '-';
  return date.toLocaleString('ko-KR', { dateStyle: 'short', timeStyle: 'short' });
}

function toneFromStatus(value?: string | null): StatusTone {
  const status = String(value || '').toLowerCase();
  if (['ready', 'completed', 'complete', 'success', 'succeeded', 'stored', 'parsed', 'active', 'done'].includes(status)) {
    return 'success';
  }
  if (['failed', 'failure', 'error', 'dead_lettered', 'blocked'].includes(status)) {
    return 'danger';
  }
  if (['pending', 'running', 'retrying', 'partial', 'uploaded', 'queued', 'open'].includes(status)) {
    return 'warning';
  }
  return 'neutral';
}

function toneFromSeverity(value?: string | null): StatusTone {
  const severity = String(value || '').toLowerCase();
  if (severity === 'danger' || severity === 'error' || severity === 'high') return 'danger';
  if (severity === 'warning' || severity === 'medium') return 'warning';
  if (severity === 'success') return 'success';
  return 'active';
}

function compactMetadata(metadata?: Record<string, unknown>) {
  if (!metadata) return '';
  const entries = Object.entries(metadata)
    .filter(([, value]) => value !== undefined && value !== null && value !== '')
    .slice(0, 4);
  return entries.map(([key, value]) => `${key}: ${String(value)}`).join(' · ');
}

function MetricCard({
  label,
  value,
  helper,
  icon: Icon,
  tone = 'blue',
}: {
  label: string;
  value: string;
  helper?: string;
  icon: React.ElementType;
  tone?: 'blue' | 'emerald' | 'amber' | 'rose' | 'slate';
}) {
  const toneClass = {
    blue: 'bg-blue-50 text-blue-700',
    emerald: 'bg-emerald-50 text-emerald-700',
    amber: 'bg-amber-50 text-amber-700',
    rose: 'bg-rose-50 text-rose-700',
    slate: 'bg-slate-100 text-slate-700',
  }[tone];

  return (
    <SurfaceCard className="p-5">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="text-xs font-black uppercase tracking-[0.16em] text-slate-400">{label}</p>
          <p className="mt-2 text-2xl font-black tracking-tight text-slate-950">{value}</p>
          {helper ? <p className="mt-1 text-xs font-semibold text-slate-500">{helper}</p> : null}
        </div>
        <span className={cn('inline-flex h-10 w-10 shrink-0 items-center justify-center rounded-2xl', toneClass)}>
          <Icon size={18} />
        </span>
      </div>
    </SurfaceCard>
  );
}

function LogList({ logs, emptyText }: { logs: AdminLog[]; emptyText: string }) {
  if (!logs.length) {
    return <p className="rounded-2xl border border-dashed border-slate-200 bg-slate-50 px-4 py-6 text-center text-sm font-semibold text-slate-500">{emptyText}</p>;
  }

  return (
    <div className="divide-y divide-slate-100">
      {logs.map((log, index) => {
        const metadata = compactMetadata(log.metadata);
        return (
          <div key={`${log.category}-${log.occurred_at}-${index}`} className="py-4 first:pt-0 last:pb-0">
            <div className="flex flex-wrap items-center gap-2">
              <StatusBadge status={toneFromSeverity(log.severity)} className="text-[11px]">
                {log.category}
              </StatusBadge>
              <span className="text-xs font-bold text-slate-400">{formatDate(log.occurred_at)}</span>
            </div>
            <p className="mt-2 text-sm font-black text-slate-900">{log.title}</p>
            {log.message ? <p className="mt-1 break-words text-sm font-medium leading-6 text-slate-600">{log.message}</p> : null}
            {metadata ? <p className="mt-1 break-all text-[11px] font-semibold text-slate-400">{metadata}</p> : null}
          </div>
        );
      })}
    </div>
  );
}

const AdminDashboard: React.FC = () => {
  const { isAdmin } = useAuth();
  const [stats, setStats] = useState<AdminStats | null>(null);
  const [projects, setProjects] = useState<AdminProject[]>([]);
  const [recentLogs, setRecentLogs] = useState<AdminLog[]>([]);
  const [projectLogs, setProjectLogs] = useState<AdminLog[]>([]);
  const [assets, setAssets] = useState<AdminAssets | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadingAssets, setLoadingAssets] = useState(false);
  const [selectedProjectId, setSelectedProjectId] = useState<string | null>(null);
  const [searchTerm, setSearchTerm] = useState('');

  const fetchDashboard = async () => {
    try {
      setLoading(true);
      const [statsData, projectData, logsData] = await Promise.all([
        api.admin.getStats(),
        api.admin.listProjects(),
        api.admin.getRecentLogs(),
      ]);
      setStats(statsData);
      setProjects(projectData);
      setRecentLogs(logsData.logs || []);
      if (!selectedProjectId && projectData.length > 0) {
        setSelectedProjectId(projectData[0].id);
      }
    } catch (error) {
      console.error('Failed to fetch admin dashboard:', error);
      toast.error('관리자 데이터를 불러오지 못했습니다.');
    } finally {
      setLoading(false);
    }
  };

  const fetchProjectDetail = async (projectId: string) => {
    try {
      setLoadingAssets(true);
      const [assetsData, logsData] = await Promise.all([
        api.admin.getProjectAssets(projectId),
        api.admin.getProjectLogs(projectId),
      ]);
      setAssets({
        uploads: assetsData.uploads || [],
        documents: assetsData.documents || [],
        diagnosis_runs: assetsData.diagnosis_runs || [],
        reports: assetsData.reports || [],
      });
      setProjectLogs(logsData.logs || []);
    } catch (error) {
      console.error('Failed to fetch project detail:', error);
      toast.error('프로젝트 상세 정보와 로그를 불러오지 못했습니다.');
    } finally {
      setLoadingAssets(false);
    }
  };

  useEffect(() => {
    if (isAdmin) {
      void fetchDashboard();
    }
  }, [isAdmin]);

  useEffect(() => {
    if (selectedProjectId) {
      void fetchProjectDetail(selectedProjectId);
    }
  }, [selectedProjectId]);

  const openPdf = async (url: string) => {
    try {
      toast.loading('파일을 불러오는 중입니다...', { id: 'admin-file-open' });
      const response = await api.download(url);
      const blobUrl = URL.createObjectURL(response.blob);
      window.open(blobUrl, '_blank', 'noopener,noreferrer');
      toast.success('파일을 열었습니다.', { id: 'admin-file-open' });
    } catch (error) {
      console.error('Failed to open admin file:', error);
      toast.error('파일을 불러오지 못했습니다.', { id: 'admin-file-open' });
    }
  };

  const filteredProjects = useMemo(() => {
    const term = searchTerm.trim().toLowerCase();
    if (!term) return projects;
    return projects.filter(project => {
      const haystack = [
        project.title,
        project.target_university,
        project.target_major,
        project.owner?.email,
        project.owner?.name,
        project.owner?.grade,
      ]
        .filter(Boolean)
        .join(' ')
        .toLowerCase();
      return haystack.includes(term);
    });
  }, [projects, searchTerm]);

  const selectedProject = projects.find(project => project.id === selectedProjectId) || null;
  const summary = stats?.summary || {};
  const quality = stats?.quality || {};
  const usage = stats?.usage || {};
  const last24h = stats?.growth?.last_24h || {};

  const metricCards = [
    {
      label: '전체 사용자',
      value: formatNumber(summary.total_users),
      helper: `24시간 신규 ${formatNumber(last24h.users)}`,
      icon: Users,
      tone: 'blue' as const,
    },
    {
      label: '전체 프로젝트',
      value: formatNumber(summary.total_projects),
      helper: `24시간 신규 ${formatNumber(last24h.projects)}`,
      icon: Database,
      tone: 'slate' as const,
    },
    {
      label: '진단 실행',
      value: formatNumber(summary.total_diagnosis_runs),
      helper: `24시간 ${formatNumber(last24h.diagnosis_runs)}`,
      icon: Activity,
      tone: 'emerald' as const,
    },
    {
      label: '업로드',
      value: formatNumber(summary.total_uploads),
      helper: `${formatBytes(usage.total_upload_bytes)} · ${formatNumber(usage.total_upload_pages)}쪽`,
      icon: FileText,
      tone: 'blue' as const,
    },
    {
      label: '실패 신호',
      value: formatNumber(quality.total_failure_signals),
      helper: `진단 ${formatNumber(quality.diagnosis_failures)} · 파싱 ${formatNumber(quality.document_failures)}`,
      icon: AlertTriangle,
      tone: Number(quality.total_failure_signals || 0) > 0 ? 'rose' as const : 'slate' as const,
    },
    {
      label: '검토 대기',
      value: formatNumber(quality.open_review_tasks),
      helper: `정책 플래그 ${formatNumber(quality.open_policy_flags)}`,
      icon: ClipboardList,
      tone: Number(quality.open_review_tasks || 0) > 0 ? 'amber' as const : 'slate' as const,
    },
  ];

  if (!isAdmin) {
    return null;
  }

  return (
    <div className="mx-auto flex w-full max-w-7xl flex-col gap-6 pb-12">
      <PageHeader
        eyebrow="Admin"
        title="관리자 대시보드"
        description="관리자 검증이 완료된 계정에서만 운영 지표, 프로젝트 자산, 파싱·진단 로그를 확인할 수 있습니다."
        actions={
          <button
            type="button"
            onClick={fetchDashboard}
            className="inline-flex h-11 items-center gap-2 rounded-2xl bg-slate-950 px-4 text-sm font-black text-white transition-colors hover:bg-slate-800"
          >
            <RefreshCcw size={16} className={loading ? 'animate-spin' : ''} />
            새로고침
          </button>
        }
        evidence={
          <div className="flex flex-wrap items-center gap-3 text-sm font-bold text-slate-500">
            <span className="inline-flex items-center gap-2 text-emerald-700">
              <ShieldCheck size={16} />
              서버 권한 검증 완료
            </span>
            <span>최근 갱신: {formatDate(stats?.generated_at)}</span>
          </div>
        }
      />

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-6">
        {metricCards.map(card => (
          <MetricCard key={card.label} {...card} />
        ))}
      </div>

      <div className="grid grid-cols-1 gap-6 xl:grid-cols-[minmax(360px,0.9fr)_minmax(0,1.35fr)]">
        <SurfaceCard className="flex min-h-[640px] flex-col p-5">
          <div className="flex flex-col gap-4 border-b border-slate-100 pb-4">
            <div className="flex items-center justify-between gap-3">
              <div>
                <h2 className="text-lg font-black text-slate-950">프로젝트</h2>
                <p className="mt-1 text-sm font-semibold text-slate-500">{formatNumber(filteredProjects.length)}개 표시</p>
              </div>
              <StatusBadge status="active">{formatNumber(projects.length)} total</StatusBadge>
            </div>
            <div className="relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" size={18} />
              <input
                type="text"
                placeholder="프로젝트, 학생, 이메일, 목표 전공 검색"
                className="h-11 w-full rounded-2xl border border-slate-200 bg-slate-50 pl-10 pr-4 text-sm font-semibold text-slate-800 outline-none transition focus:border-blue-400 focus:bg-white focus:ring-4 focus:ring-blue-100"
                value={searchTerm}
                onChange={(event) => setSearchTerm(event.target.value)}
              />
            </div>
          </div>

          <div className="mt-4 flex-1 overflow-y-auto pr-1">
            {loading ? (
              <div className="space-y-3">
                {Array.from({ length: 6 }).map((_, index) => (
                  <div key={index} className="h-24 animate-pulse rounded-2xl bg-slate-100" />
                ))}
              </div>
            ) : filteredProjects.length > 0 ? (
              <div className="space-y-2">
                {filteredProjects.map(project => {
                  const selected = project.id === selectedProjectId;
                  return (
                    <motion.button
                      key={project.id}
                      type="button"
                      layout
                      onClick={() => setSelectedProjectId(project.id)}
                      className={cn(
                        'w-full rounded-2xl border p-4 text-left transition',
                        selected ? 'border-blue-300 bg-blue-50/70 shadow-sm' : 'border-slate-100 bg-white hover:border-slate-200 hover:bg-slate-50',
                      )}
                    >
                      <div className="flex items-start justify-between gap-3">
                        <div className="min-w-0">
                          <p className="truncate text-sm font-black text-slate-950">{project.title || '제목 없음'}</p>
                          <p className="mt-1 truncate text-xs font-semibold text-slate-500">
                            {project.owner?.name || '사용자'} · {project.owner?.email || '이메일 없음'}
                          </p>
                        </div>
                        <StatusBadge status={toneFromStatus(project.status)} className="text-[11px]">
                          {project.status || 'unknown'}
                        </StatusBadge>
                      </div>
                      <div className="mt-3 grid grid-cols-4 gap-2 text-center">
                        <span className="rounded-xl bg-slate-50 px-2 py-2 text-[11px] font-black text-slate-600">업로드 {project.counts?.uploads ?? 0}</span>
                        <span className="rounded-xl bg-slate-50 px-2 py-2 text-[11px] font-black text-slate-600">진단 {project.counts?.diagnosis_runs ?? 0}</span>
                        <span className="rounded-xl bg-slate-50 px-2 py-2 text-[11px] font-black text-slate-600">보고서 {project.counts?.reports ?? 0}</span>
                        <span className="rounded-xl bg-slate-50 px-2 py-2 text-[11px] font-black text-slate-600">로그 {project.counts?.async_jobs ?? 0}</span>
                      </div>
                      <p className="mt-3 truncate text-xs font-semibold text-slate-400">
                        {project.target_university || '목표 대학 미설정'} / {project.target_major || '목표 전공 미설정'}
                      </p>
                    </motion.button>
                  );
                })}
              </div>
            ) : (
              <div className="flex h-full min-h-[300px] flex-col items-center justify-center rounded-2xl border border-dashed border-slate-200 bg-slate-50 text-center">
                <Database className="mb-3 text-slate-300" size={34} />
                <p className="text-sm font-bold text-slate-500">검색 결과가 없습니다.</p>
              </div>
            )}
          </div>
        </SurfaceCard>

        <div className="flex flex-col gap-6">
          <SurfaceCard className="p-5">
            {selectedProject ? (
              <div className="space-y-5">
                <div className="flex flex-col gap-3 border-b border-slate-100 pb-5 sm:flex-row sm:items-start sm:justify-between">
                  <div className="min-w-0">
                    <h2 className="break-keep text-xl font-black text-slate-950">{selectedProject.title}</h2>
                    <p className="mt-1 break-all text-xs font-semibold text-slate-400">Project ID: {selectedProject.id}</p>
                  </div>
                  <StatusBadge status={toneFromStatus(selectedProject.status)}>{selectedProject.status || 'unknown'}</StatusBadge>
                </div>

                <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
                  <div className="rounded-2xl bg-slate-50 p-4">
                    <p className="text-xs font-black uppercase tracking-[0.15em] text-slate-400">학생</p>
                    <p className="mt-2 truncate text-sm font-black text-slate-900">{selectedProject.owner?.name || '사용자'}</p>
                    <p className="mt-1 truncate text-xs font-semibold text-slate-500">{selectedProject.owner?.email || '-'}</p>
                  </div>
                  <div className="rounded-2xl bg-slate-50 p-4">
                    <p className="text-xs font-black uppercase tracking-[0.15em] text-slate-400">목표</p>
                    <p className="mt-2 truncate text-sm font-black text-slate-900">{selectedProject.target_university || '-'}</p>
                    <p className="mt-1 truncate text-xs font-semibold text-slate-500">{selectedProject.target_major || '-'}</p>
                  </div>
                  <div className="rounded-2xl bg-slate-50 p-4">
                    <p className="text-xs font-black uppercase tracking-[0.15em] text-slate-400">갱신</p>
                    <p className="mt-2 text-sm font-black text-slate-900">{formatDate(selectedProject.updated_at || selectedProject.created_at)}</p>
                    <p className="mt-1 text-xs font-semibold text-slate-500">생성 {formatDate(selectedProject.created_at)}</p>
                  </div>
                </div>

                <div className="grid grid-cols-1 gap-5 lg:grid-cols-2">
                  <AssetSection
                    title="업로드 원본"
                    icon={FileText}
                    loading={loadingAssets}
                    emptyText="업로드된 파일이 없습니다."
                  >
                    {assets?.uploads.map(upload => (
                      <AssetRow
                        key={upload.id}
                        title={upload.filename}
                        detail={`${formatDate(upload.created_at)} · ${formatBytes(upload.file_size_bytes)} · ${upload.page_count ?? 0}쪽`}
                        status={upload.status}
                        error={upload.ingest_error}
                        onOpen={() => openPdf(api.admin.getRawUploadUrl(upload.id))}
                      />
                    ))}
                  </AssetSection>

                  <AssetSection
                    title="파싱 문서"
                    icon={BarChart3}
                    loading={loadingAssets}
                    emptyText="파싱된 문서가 없습니다."
                  >
                    {assets?.documents.map(document => (
                      <AssetRow
                        key={document.id}
                        title={document.parser_name || 'parser'}
                        detail={`${document.word_count ?? 0}단어 · ${document.page_count ?? 0}쪽 · 시도 ${document.parse_attempts ?? 0}회`}
                        status={document.status}
                        error={document.last_error || document.latest_async_job_error}
                      />
                    ))}
                  </AssetSection>

                  <AssetSection
                    title="진단 실행"
                    icon={Activity}
                    loading={loadingAssets}
                    emptyText="진단 실행 기록이 없습니다."
                  >
                    {assets?.diagnosis_runs.map(run => (
                      <AssetRow
                        key={run.id}
                        title={run.id}
                        detail={run.status_message || formatDate(run.updated_at || run.created_at)}
                        status={run.status}
                        error={run.error_message}
                      />
                    ))}
                  </AssetSection>

                  <AssetSection
                    title="진단 보고서"
                    icon={ShieldCheck}
                    loading={loadingAssets}
                    emptyText="생성된 보고서가 없습니다."
                  >
                    {assets?.reports.map(report => (
                      <AssetRow
                        key={report.id}
                        title={`${report.mode || 'report'} · v${report.version || 1}`}
                        detail={`${report.format || 'pdf'} · ${formatDate(report.created_at)}`}
                        status={report.status}
                        error={report.error_message}
                        onOpen={() => openPdf(api.admin.getDiagnosisReportUrl(report.id))}
                      />
                    ))}
                  </AssetSection>
                </div>
              </div>
            ) : (
              <div className="flex min-h-[420px] flex-col items-center justify-center rounded-3xl border border-dashed border-slate-200 bg-slate-50 p-10 text-center">
                <Users className="mb-4 text-slate-300" size={42} />
                <h2 className="text-lg font-black text-slate-950">프로젝트를 선택하세요</h2>
                <p className="mt-2 max-w-sm text-sm font-semibold leading-6 text-slate-500">왼쪽 목록에서 프로젝트를 선택하면 제출 파일, 파싱 결과, 진단 보고서와 로그가 함께 표시됩니다.</p>
              </div>
            )}
          </SurfaceCard>

          <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
            <SurfaceCard className="p-5">
              <div className="mb-5 flex items-center justify-between gap-3">
                <div>
                  <h2 className="text-lg font-black text-slate-950">프로젝트 로그</h2>
                  <p className="mt-1 text-sm font-semibold text-slate-500">선택한 프로젝트의 처리 타임라인</p>
                </div>
                <MessageSquare className="text-slate-300" size={22} />
              </div>
              {loadingAssets ? (
                <div className="h-56 animate-pulse rounded-2xl bg-slate-100" />
              ) : (
                <LogList logs={projectLogs} emptyText="선택한 프로젝트에 기록된 로그가 없습니다." />
              )}
            </SurfaceCard>

            <SurfaceCard className="p-5">
              <div className="mb-5 flex items-center justify-between gap-3">
                <div>
                  <h2 className="text-lg font-black text-slate-950">최근 전역 오류</h2>
                  <p className="mt-1 text-sm font-semibold text-slate-500">비동기 작업, 진단, 파싱 실패 신호</p>
                </div>
                <AlertTriangle className="text-slate-300" size={22} />
              </div>
              <LogList logs={recentLogs} emptyText="최근 오류 로그가 없습니다." />
            </SurfaceCard>
          </div>

          <SurfaceCard className="p-5">
            <div className="mb-4 flex items-center justify-between gap-3">
              <div>
                <h2 className="text-lg font-black text-slate-950">상태 분포</h2>
                <p className="mt-1 text-sm font-semibold text-slate-500">진단, 파싱, 렌더링, 문의, 검토 상태를 빠르게 확인합니다.</p>
              </div>
              <StatusBadge status="active">live</StatusBadge>
            </div>
            <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-4">
              {Object.entries(stats?.breakdowns || {}).map(([key, items]) => (
                <div key={key} className="rounded-2xl bg-slate-50 p-4">
                  <p className="mb-3 text-xs font-black uppercase tracking-[0.14em] text-slate-400">{key.replaceAll('_', ' ')}</p>
                  <div className="flex flex-wrap gap-2">
                    {items.length ? items.map(item => (
                      <StatusBadge key={`${key}-${item.status}`} status={toneFromStatus(item.status)} className="text-[11px]">
                        {item.status} {formatNumber(item.count)}
                      </StatusBadge>
                    )) : <span className="text-xs font-semibold text-slate-400">데이터 없음</span>}
                  </div>
                </div>
              ))}
            </div>
          </SurfaceCard>
        </div>
      </div>
    </div>
  );
};

function AssetSection({
  title,
  icon: Icon,
  loading,
  emptyText,
  children,
}: {
  title: string;
  icon: React.ElementType;
  loading: boolean;
  emptyText: string;
  children?: React.ReactNode;
}) {
  const childArray = React.Children.toArray(children).filter(Boolean);
  return (
    <div className="rounded-3xl border border-slate-100 bg-white p-4">
      <div className="mb-3 flex items-center gap-2">
        <Icon size={16} className="text-blue-600" />
        <h3 className="text-sm font-black text-slate-950">{title}</h3>
      </div>
      {loading ? (
        <div className="h-24 animate-pulse rounded-2xl bg-slate-100" />
      ) : childArray.length ? (
        <div className="space-y-2">{childArray}</div>
      ) : (
        <p className="rounded-2xl bg-slate-50 px-4 py-6 text-center text-xs font-bold text-slate-400">{emptyText}</p>
      )}
    </div>
  );
}

function AssetRow({
  title,
  detail,
  status,
  error,
  onOpen,
}: {
  title: string;
  detail?: string | null;
  status?: string | null;
  error?: string | null;
  onOpen?: () => void;
}) {
  return (
    <div className="rounded-2xl border border-slate-100 bg-slate-50/70 p-3">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="truncate text-sm font-black text-slate-900">{title}</p>
          {detail ? <p className="mt-1 break-words text-xs font-semibold text-slate-500">{detail}</p> : null}
        </div>
        <div className="flex shrink-0 items-center gap-2">
          <StatusBadge status={toneFromStatus(status)} className="text-[11px]">
            {status || 'unknown'}
          </StatusBadge>
          {onOpen ? (
            <button
              type="button"
              onClick={onOpen}
              className="inline-flex h-8 w-8 items-center justify-center rounded-xl bg-white text-slate-500 shadow-sm transition hover:text-blue-600"
              title="파일 열기"
            >
              <ExternalLink size={15} />
            </button>
          ) : null}
        </div>
      </div>
      {error ? <p className="mt-2 break-words rounded-xl bg-rose-50 px-3 py-2 text-xs font-bold leading-5 text-rose-700">{error}</p> : null}
    </div>
  );
}

export default AdminDashboard;
