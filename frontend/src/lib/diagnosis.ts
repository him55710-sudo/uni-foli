export const DIAGNOSIS_STORAGE_KEY = 'uni_foli_last_diagnosis';

import type {
  AsyncJobRead,
  DiagnosisResultPayload,
  DiagnosisRiskLevel,
  DiagnosisRunResponse,
  StoredDiagnosis,
} from '@shared-contracts';

export type {
  AsyncJobRead,
  ConsultantDiagnosisArtifactResponse,
  ConsultantDiagnosisReport,
  ConsultantDiagnosisRoadmapItem,
  ConsultantDiagnosisSection,
  DiagnosisReportCreateRequest,
  DiagnosisReportMode,
  DiagnosisCitation,
  DiagnosisExportFormat,
  DiagnosisGuidedPlanRequest,
  DiagnosisGuidedPlanResponse,
  DiagnosisGap,
  DiagnosisGapAxis,
  DiagnosisSummary,
  DiagnosisPolicyFlag,
  DiagnosisQuest,
  DiagnosisResultPayload,
  DiagnosisRiskLevel,
  DiagnosisRunRequest,
  DiagnosisRunResponse,
  FormatRecommendation,
  GuidedDraftOutline,
  PageCountOption,
  RecommendedDirection,
  RecommendedDefaultAction,
  StoredDiagnosis,
  TemplateCandidate,
  TopicCandidate,
} from '@shared-contracts';

export function mergeDiagnosisPayload(run: DiagnosisRunResponse): DiagnosisResultPayload | null {
  if (!run.result_payload) return null;
  return {
    ...run.result_payload,
    citations: run.result_payload.citations?.length ? run.result_payload.citations : run.citations,
    review_required: run.result_payload.review_required ?? run.review_required,
    response_trace_id: run.result_payload.response_trace_id ?? run.response_trace_id,
  };
}

export function isDiagnosisComplete(run: DiagnosisRunResponse | null): boolean {
  if (!run) return false;
  return Boolean(run.result_payload) || run.status === 'COMPLETED' || run.status === 'SUCCESS';
}

export function isDiagnosisFailed(run: DiagnosisRunResponse | null, job: AsyncJobRead | null): boolean {
  if (run?.status === 'FAILED') return true;
  return job?.status === 'failed';
}

export function getDiagnosisFailureMessage(
  run: DiagnosisRunResponse | null,
  job: AsyncJobRead | null,
): string {
  return (
    run?.error_message ||
    job?.failure_reason ||
    '진단을 완료하지 못했습니다. 분석 과정에서 문제가 발생했으니 다시 시도해 주세요.'
  );
}

export type DiagnosisDeliveryState =
  | 'idle'
  | 'diagnosing'
  | 'diagnosis_ready'
  | 'report_generating'
  | 'report_ready'
  | 'failed';

export interface DiagnosisDeliveryResolution {
  state: DiagnosisDeliveryState;
  diagnosisFailed: boolean;
  reportFailed: boolean;
  diagnosisStatus: string | null;
  reportStatus: string | null;
  message: string | null;
}

function normalizeStatus(status: string | null | undefined): string | null {
  const normalized = (status || '').trim();
  return normalized ? normalized.toUpperCase() : null;
}

export function resolveDiagnosisDeliveryState(
  run: DiagnosisRunResponse | null,
  job: AsyncJobRead | null,
): DiagnosisDeliveryResolution {
  const diagnosisStatus = normalizeStatus(run?.status);
  const reportStatus =
    normalizeStatus(run?.report_status) ?? normalizeStatus(run?.report_async_job_status);
  const diagnosisFailed = isDiagnosisFailed(run, job);
  const reportFailed = reportStatus === 'FAILED';

  if (!run) {
    return {
      state: 'idle',
      diagnosisFailed: false,
      reportFailed: false,
      diagnosisStatus: null,
      reportStatus: null,
      message: null,
    };
  }

  if (diagnosisFailed) {
    return {
      state: 'failed',
      diagnosisFailed: true,
      reportFailed: false,
      diagnosisStatus,
      reportStatus,
      message: getDiagnosisFailureMessage(run, job),
    };
  }

  if (!isDiagnosisComplete(run)) {
    return {
      state: 'diagnosing',
      diagnosisFailed: false,
      reportFailed: false,
      diagnosisStatus,
      reportStatus,
      message: null,
    };
  }

  if (reportStatus === 'READY') {
    return {
      state: 'report_ready',
      diagnosisFailed: false,
      reportFailed: false,
      diagnosisStatus,
      reportStatus,
      message: null,
    };
  }

  if (reportFailed) {
    return {
      state: 'failed',
      diagnosisFailed: false,
      reportFailed: true,
      diagnosisStatus,
      reportStatus,
      message: run.report_error_message || '진단서 생성에 실패했습니다. 생성을 다시 요청해 주세요.',
    };
  }

  if (reportStatus && reportStatus !== 'NOT_REQUESTED') {
    return {
      state: 'report_generating',
      diagnosisFailed: false,
      reportFailed: false,
      diagnosisStatus,
      reportStatus,
      message: null,
    };
  }

  return {
    state: 'diagnosis_ready',
    diagnosisFailed: false,
    reportFailed: false,
    diagnosisStatus,
    reportStatus,
    message: null,
  };
}

export function formatAsyncJobStatus(status: string | null | undefined): string {
  const normalized = (status || '').trim().toLowerCase();
  if (!normalized) return '대기 중';
  if (normalized === 'queued' || normalized === 'pending') return '대기 중';
  if (normalized === 'running') return '진단 진행 중';
  if (normalized === 'retrying') return '다시 시도 중';
  if (normalized === 'stale') return '지연 복구 중';
  if (normalized === 'succeeded' || normalized === 'completed' || normalized === 'success') return '완료됨';
  if (normalized === 'failed') return '실패';

  return '상태 확인 중';
}

export function formatRiskLevel(level: DiagnosisRiskLevel): string {
  if (level === 'danger') return '근거 보완 필요';
  if (level === 'warning') return '일부 지원 필요';
  return '근거 충분함';
}

export function formatDateTime(value: string | null | undefined): string | null {
  if (!value) return null;
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return null;
  return parsed.toLocaleString();
}
