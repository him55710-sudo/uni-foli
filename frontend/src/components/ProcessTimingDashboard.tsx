import React, { useEffect, useMemo, useState } from 'react';
import { Clock3 } from 'lucide-react';
import { cn } from '../lib/cn';
import { SectionCard, StatusBadge, SurfaceCard, WorkflowNotice } from './primitives';

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
  preferStageMode?: boolean;
  stageMessage?: string | null;
  longRunningHintAfterSeconds?: number;
}

const DEFAULT_EXPECTED_SECONDS = 60;
const RUNNING_PROGRESS_CAP = 0.78;

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
  if (phase.status === 'failed') return 1;
  if (phase.status === 'idle') return 0;

  const expectedMs = toExpectedMs(phase);
  if (!phase.startedAt) return 0.05;

  const endAt = phase.finishedAt ?? nowMs;
  const elapsedMs = Math.max(0, endAt - phase.startedAt);
  const ratio = elapsedMs / expectedMs;

  // Running phase intentionally avoids "almost done" illusion when backend completion isn't confirmed yet.
  return Math.min(Math.max(0.08, ratio), RUNNING_PROGRESS_CAP);
}

function elapsedMsForPhase(phase: TimingPhase, nowMs: number): number {
  if (!phase.startedAt) return 0;
  const endAt = phase.finishedAt ?? nowMs;
  return Math.max(0, endAt - phase.startedAt);
}

export function ProcessTimingDashboard({
  phases,
  title = '예상 진행 타임라인',
  description = '예상 소요시간 대비 작업 진행 단계를 안내합니다.',
  className,
  preferStageMode = false,
  stageMessage,
  longRunningHintAfterSeconds = 120,
}: ProcessTimingDashboardProps) {
  const [tick, setTick] = useState(() => Date.now());

  const hasRunningPhase = phases.some((phase) => phase.status === 'running');

  useEffect(() => {
    if (!hasRunningPhase) return undefined;
    const intervalId = window.setInterval(() => setTick(Date.now()), 1000);
    return () => window.clearInterval(intervalId);
  }, [hasRunningPhase]);

  const runningPhase = useMemo(
    () => phases.find((phase) => phase.status === 'running') ?? null,
    [phases],
  );

  const runningElapsedMs = runningPhase ? elapsedMsForPhase(runningPhase, tick) : 0;
  const longRunningThresholdMs = Math.max(30, longRunningHintAfterSeconds) * 1000;
  const isLongRunning = Boolean(runningPhase) && runningElapsedMs >= longRunningThresholdMs;

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
      actions={(
        <div className="flex flex-wrap items-center gap-2">
          <StatusBadge status={hasRunningPhase ? 'active' : 'neutral'}>
            <Clock3 size={14} />
            {preferStageMode && hasRunningPhase
              ? `단계 진행 중${runningPhase ? `: ${runningPhase.label}` : ''}`
              : `진행률 ${overallPercent}%`}
          </StatusBadge>
          <StatusBadge status="neutral">예상 잔여 시간 {formatDuration(remainingMs)}</StatusBadge>
        </div>
      )}
    >
      {isLongRunning ? (
        <WorkflowNotice
          tone="warning"
          title="예상보다 오래 걸리는 중입니다."
          description="백엔드 상태를 계속 확인하고 있으며, 지연 시 자동 복구/재시도 상태가 우선 반영됩니다."
          className="mb-3"
        />
      ) : null}

      {preferStageMode && stageMessage ? (
        <WorkflowNotice tone="loading" title="현재 단계 설명" description={stageMessage} className="mb-3" />
      ) : null}

      <div className="grid gap-3 md:grid-cols-3">
        {phases.map((phase) => {
          const progress = phaseProgressMap.get(phase.id) ?? 0;
          const phasePercent = Math.round(progress * 100);
          const phaseExpectedMs = toExpectedMs(phase);
          const phaseElapsedMs = elapsedMsForPhase(phase, tick);

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
                          : 'bg-[#004aad]',
                    )}
                    style={{ width: `${phasePercent}%` }}
                  />
                </div>
                <div className="flex items-center justify-between text-xs font-semibold text-slate-500">
                  <span>
                    {preferStageMode && phase.status === 'running'
                      ? `진행 중 (${formatDuration(phaseElapsedMs)})`
                      : `진행률 ${phasePercent}%`}
                  </span>
                  <span>예상 {formatDuration(phaseExpectedMs)}</span>
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
