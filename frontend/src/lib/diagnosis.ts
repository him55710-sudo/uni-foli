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
    'The diagnosis could not be completed. Review the status details and try again.'
  );
}

export function formatAsyncJobStatus(status: string | null | undefined): string {
  if (!status) return 'Waiting';
  return status
    .split('_')
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(' ');
}

export function formatRiskLevel(level: DiagnosisRiskLevel): string {
  if (level === 'danger') return 'Needs evidence';
  if (level === 'warning') return 'Needs support';
  return 'Grounded enough';
}

export function formatDateTime(value: string | null | undefined): string | null {
  if (!value) return null;
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return null;
  return parsed.toLocaleString();
}
