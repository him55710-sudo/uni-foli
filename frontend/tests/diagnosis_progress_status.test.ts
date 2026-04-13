import assert from 'node:assert/strict';
import test from 'node:test';

import type { AsyncJobRead } from '../src/lib/diagnosis';
import {
  isDiagnosisLongRunning,
  resolveDiagnosisJobMessage,
  resolveDiagnosisJobProgressPercent,
  resolveDiagnosisJobStageLabel,
  resolveDiagnosisJobVisualStatus,
} from '../src/lib/diagnosisProgress';

function buildJob(overrides: Partial<AsyncJobRead>): AsyncJobRead {
  return {
    id: 'job-1',
    project_id: 'project-1',
    job_type: 'diagnosis',
    resource_type: 'diagnosis_run',
    resource_id: 'run-1',
    status: 'queued',
    retry_count: 0,
    max_retries: 2,
    failure_reason: null,
    failure_history: [],
    progress_stage: null,
    progress_message: null,
    progress_percent: null,
    progress_history: [],
    next_attempt_at: '2026-04-13T01:00:00.000Z',
    started_at: null,
    completed_at: null,
    dead_lettered_at: null,
    created_at: '2026-04-13T00:59:00.000Z',
    updated_at: '2026-04-13T00:59:00.000Z',
    ...overrides,
  };
}

test('queued state is rendered as queue-waiting stage', () => {
  const job = buildJob({ status: 'queued' });
  const status = resolveDiagnosisJobVisualStatus(job, 'PENDING');
  assert.equal(status, 'queued');
  assert.equal(resolveDiagnosisJobStageLabel(job, null, status), '작업 대기');
  assert.equal(resolveDiagnosisJobMessage(job, null, status), '작업 순서를 대기하고 있습니다.');
});

test('running state prefers backend status_message over fallback copy', () => {
  const job = buildJob({
    status: 'running',
    started_at: '2026-04-13T01:00:00.000Z',
    updated_at: '2026-04-13T01:00:10.000Z',
  });
  const status = resolveDiagnosisJobVisualStatus(job, 'RUNNING', { nowMs: Date.parse('2026-04-13T01:00:15.000Z') });
  assert.equal(status, 'running');
  assert.equal(
    resolveDiagnosisJobMessage(job, '학생부 핵심 지표를 추출하고 있습니다...', status),
    '학생부 핵심 지표를 추출하고 있습니다...',
  );
});

test('retrying stale state is rendered as stale/recovering', () => {
  const job = buildJob({
    status: 'retrying',
    failure_reason: 'Job execution became stale and was returned to the retry queue.',
    progress_stage: 'stale_recovering',
  });
  const status = resolveDiagnosisJobVisualStatus(job, 'RUNNING');
  assert.equal(status, 'stale');
  assert.equal(resolveDiagnosisJobStageLabel(job, null, status), 'Stale Recovering');
});

test('failed state remains failed and does not expose fake progress', () => {
  const job = buildJob({
    status: 'failed',
    failure_reason: 'provider error',
  });
  const status = resolveDiagnosisJobVisualStatus(job, 'FAILED');
  assert.equal(status, 'failed');
  assert.equal(resolveDiagnosisJobProgressPercent(job, status), null);
});

test('completed state resolves to succeeded with 100 percent', () => {
  const job = buildJob({
    status: 'succeeded',
    progress_percent: 100,
    completed_at: '2026-04-13T01:02:00.000Z',
  });
  const status = resolveDiagnosisJobVisualStatus(job, 'COMPLETED');
  assert.equal(status, 'succeeded');
  assert.equal(resolveDiagnosisJobProgressPercent(job, status), 100);
});

test('long-running running state is flagged for warning copy', () => {
  const job = buildJob({
    status: 'running',
    created_at: '2026-04-13T01:00:00.000Z',
    started_at: '2026-04-13T01:00:00.000Z',
    updated_at: '2026-04-13T01:00:05.000Z',
  });
  const status = resolveDiagnosisJobVisualStatus(job, 'RUNNING', {
    nowMs: Date.parse('2026-04-13T01:03:30.000Z'),
  });
  assert.equal(status, 'stale');
  assert.equal(
    isDiagnosisLongRunning(job, status, { nowMs: Date.parse('2026-04-13T01:03:30.000Z') }),
    true,
  );
});
