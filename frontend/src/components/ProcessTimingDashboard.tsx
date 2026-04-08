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
  expectedSeconds?: number;
  note?: string;
}

interface ProcessTimingDashboardProps {
  phases: TimingPhase[];
  title?: string;
  description?: string;
  className?: string;
}

const DEFAULT_EXPECTED_SECONDS = 60;

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

function toExpectedMs(phase: TimingPhase): number {
  const expectedSeconds = Number.isFinite(phase.expectedSeconds) ? Number(phase.expectedSeconds) : DEFAULT_EXPECTED_SECONDS;
  return Math.max(5, expectedSeconds) * 1000;
}

function formatDuration(ms: number): string {
  if (ms <= 0) return '0초';
  const seconds = Math.round(ms / 1000);
  const mins = Math.floor(seconds / 60);
  const remain = seconds % 60;
  if (mins === 0) return `${seconds}초`;
  return `${mins}분 ${remain}초`;
}

function computePhaseProgress(phase: TimingPhase, nowMs: number): number {
  if (phase.status === 'done') return 1;
  if (phase.status === 'idle') return 0;

  const expectedMs = toExpectedMs(phase);
  if (!phase.startedAt) return phase.status === 'running' ? 0.05 : 0;

  const endAt = phase.finishedAt ?? (phase.status === 'running' ? nowMs : null);
  if (!endAt) return 0;

  const elapsedMs = Math.max(0, endAt - phase.startedAt);
  const ratio = Math.min(elapsedMs / expectedMs, 1);

  if (phase.status === 'running') {
    return Math.min(ratio, 0.98);
  }
  return ratio;
}

export function ProcessTimingDashboard({
  phases,
  title = '예상 진행 타임테이블',
  description = '예상 소요시간 대비 작업 완료 비율을 보여드려요.',
  className,
}: ProcessTimingDashboardProps) {
  const [tick, setTick] = useState(() => Date.now());

  const hasRunningPhase = phases.some((phase) => phase.status === 'running');

  useEffect(() => {
    if (!hasRunningPhase) return undefined;
    const intervalId = window.setInterval(() => setTick(Date.now()), 1000);
    return () => window.clearInterval(intervalId);
  }, [hasRunningPhase]);

  const phaseProgressMap = useMemo(() => {
    const map = new Map<string, number>();
    phases.forEach((phase) => map.set(phase.id, computePhaseProgress(phase, tick)));
    return map;
  }, [phases, tick]);

  const overallProgress = useMemo(() => {
    const totalExpectedMs = phases.reduce((sum, phase) => sum + toExpectedMs(phase), 0);
    if (totalExpectedMs <= 0) return 0;
    const weightedProgressMs = phases.reduce((sum, phase) => {
      const progress = phaseProgressMap.get(phase.id) ?? 0;
      return sum + toExpectedMs(phase) * progress;
    }, 0);
    return Math.max(0, Math.min(weightedProgressMs / totalExpectedMs, 1));
  }, [phaseProgressMap, phases]);

  const remainingMs = useMemo(() => {
    const totalExpectedMs = phases.reduce((sum, phase) => sum + toExpectedMs(phase), 0);
    return Math.max(0, totalExpectedMs * (1 - overallProgress));
  }, [overallProgress, phases]);

  const overallPercent = Math.round(overallProgress * 100);

  return (
    <SectionCard
      title={title}
      description={description}
      eyebrow="예상 진행률"
      className={cn('border-blue-100 bg-blue-50/50', className)}
      data-testid="process-timing-dashboard"
      actions={
        <div className="flex flex-wrap items-center gap-2">
          <StatusBadge status={hasRunningPhase ? 'active' : 'neutral'}>
            <Clock3 size={14} />
            진행률 {overallPercent}%
          </StatusBadge>
          <StatusBadge status="neutral">예상 남은 시간 {formatDuration(remainingMs)}</StatusBadge>
        </div>
      }
    >
      <div className="grid gap-3 md:grid-cols-3">
        {phases.map((phase) => {
          const progress = phaseProgressMap.get(phase.id) ?? 0;
          const phasePercent = Math.round(progress * 100);

          return (
            <SurfaceCard key={phase.id} tone="muted" padding="sm" className="space-y-3 border border-white/70 bg-white/95">
              <div className="flex items-center justify-between gap-2">
                <p className="text-sm font-black text-slate-800">{phase.label}</p>
                <StatusBadge status={phaseStatusTone(phase.status)}>{phaseStatusLabel(phase.status)}</StatusBadge>
              </div>

              <div className="space-y-1.5">
                <div className="h-2.5 overflow-hidden rounded-full bg-slate-200">
                  <div
                    className={cn(
                      'h-full rounded-full transition-[width] duration-500',
                      phase.status === 'failed'
                        ? 'bg-red-400'
                        : phase.status === 'done'
                          ? 'bg-emerald-500'
                          : 'bg-blue-500',
                    )}
                    style={{ width: `${phasePercent}%` }}
                  />
                </div>
                <div className="flex items-center justify-between text-xs font-semibold text-slate-500">
                  <span>진행률 {phasePercent}%</span>
                  <span>예상 {formatDuration(toExpectedMs(phase))}</span>
                </div>
              </div>

              {phase.note ? <p className="text-sm font-medium leading-6 text-slate-500">{phase.note}</p> : null}
            </SurfaceCard>
          );
        })}
      </div>
    </SectionCard>
  );
}
