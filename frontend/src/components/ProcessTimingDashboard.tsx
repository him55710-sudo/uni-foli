import React, { useEffect, useMemo, useState } from 'react';
import { Clock3 } from 'lucide-react';
import { cn } from '../lib/cn';
import { SectionCard, StatusBadge, SurfaceCard } from './primitives';

export type TimingPhaseStatus = 'idle' | 'running' | 'done' | 'failed';

export interface TimingPhase {
  id: string;
  label: string;
  status: TimingPhaseStatus;
  startedAt: number | null;
  finishedAt: number | null;
  note?: string;
}

interface ProcessTimingDashboardProps {
  phases: TimingPhase[];
  title?: string;
  description?: string;
  className?: string;
}

function formatDuration(ms: number | null): string {
  if (ms == null || ms < 0) return '-';
  const seconds = Math.round(ms / 1000);
  const mins = Math.floor(seconds / 60);
  const remain = seconds % 60;
  if (mins === 0) return `${seconds}초`;
  return `${mins}분 ${remain}초`;
}

function phaseStatusLabel(status: TimingPhaseStatus): string {
  if (status === 'running') return '진행 중';
  if (status === 'done') return '완료';
  if (status === 'failed') return '실패';
  return '대기';
}

function phaseStatusTone(status: TimingPhaseStatus): 'neutral' | 'active' | 'success' | 'danger' {
  if (status === 'running') return 'active';
  if (status === 'done') return 'success';
  if (status === 'failed') return 'danger';
  return 'neutral';
}

export function ProcessTimingDashboard({
  phases,
  title = '처리 시간 대시보드',
  description = '업로드부터 진단까지 각 단계 소요 시간을 확인할 수 있어요.',
  className,
}: ProcessTimingDashboardProps) {
  const [tick, setTick] = useState(() => Date.now());

  const hasRunningPhase = phases.some(phase => phase.status === 'running');

  useEffect(() => {
    if (!hasRunningPhase) return undefined;
    const intervalId = window.setInterval(() => setTick(Date.now()), 1000);
    return () => window.clearInterval(intervalId);
  }, [hasRunningPhase]);

  const totalDuration = useMemo(() => {
    const starts = phases.map(phase => phase.startedAt).filter((value): value is number => typeof value === 'number');
    if (!starts.length) return null;
    const startAt = Math.min(...starts);
    const endCandidates = phases
      .map(phase => phase.finishedAt)
      .filter((value): value is number => typeof value === 'number');
    const endAt = hasRunningPhase ? tick : (endCandidates.length ? Math.max(...endCandidates) : tick);
    return endAt - startAt;
  }, [hasRunningPhase, phases, tick]);

  return (
    <SectionCard
      title={title}
      description={description}
      eyebrow="소요 시간"
      className={cn('border-blue-100 bg-blue-50/50', className)}
      data-testid="process-timing-dashboard"
      actions={
        <StatusBadge status={hasRunningPhase ? 'active' : 'neutral'}>
          <Clock3 size={14} />
          총 {formatDuration(totalDuration)}
        </StatusBadge>
      }
    >
      <div className="grid gap-3 md:grid-cols-3">
        {phases.map((phase) => {
          const endAt = phase.finishedAt ?? (phase.status === 'running' ? tick : null);
          const duration = phase.startedAt != null && endAt != null ? endAt - phase.startedAt : null;

          return (
            <SurfaceCard key={phase.id} tone="muted" padding="sm" className="space-y-2 border border-white/70 bg-white/95">
              <div className="flex items-center justify-between gap-2">
                <p className="text-sm font-black text-slate-800">{phase.label}</p>
                <StatusBadge status={phaseStatusTone(phase.status)}>{phaseStatusLabel(phase.status)}</StatusBadge>
              </div>
              <p className="text-lg font-black text-slate-900">{formatDuration(duration)}</p>
              {phase.note ? <p className="text-sm font-medium leading-6 text-slate-500">{phase.note}</p> : null}
            </SurfaceCard>
          );
        })}
      </div>
    </SectionCard>
  );
}
