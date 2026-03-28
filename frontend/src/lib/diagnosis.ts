export const DIAGNOSIS_STORAGE_KEY = 'folia_last_diagnosis';

export type DiagnosisRiskLevel = 'safe' | 'warning' | 'danger';

export interface DiagnosisCitation {
  id?: string | null;
  document_id?: string | null;
  document_chunk_id?: string | null;
  provenance_type?: string;
  source_label: string;
  page_number?: number | null;
  excerpt: string;
  relevance_score: number;
}

export interface DiagnosisPolicyFlag {
  id: string;
  code: string;
  severity: string;
  detail: string;
  matched_text: string;
  match_count: number;
  status: string;
  created_at?: string | null;
}

export interface DiagnosisGap {
  title: string;
  description: string;
  difficulty: 'low' | 'medium' | 'high';
}

export interface DiagnosisQuest {
  title: string;
  description: string;
  priority: 'low' | 'medium' | 'high';
}

export interface DiagnosisResultPayload {
  headline: string;
  strengths: string[];
  gaps: string[];
  detailed_gaps?: DiagnosisGap[];
  recommended_focus: string;
  action_plan?: DiagnosisQuest[];
  risk_level: DiagnosisRiskLevel;
  citations?: DiagnosisCitation[];
  policy_codes?: string[];
  review_required?: boolean;
  response_trace_id?: string | null;
}

export interface DiagnosisRunResponse {
  id: string;
  project_id: string;
  status: string;
  result_payload: DiagnosisResultPayload | null;
  error_message: string | null;
  review_required: boolean;
  policy_flags: DiagnosisPolicyFlag[];
  citations: DiagnosisCitation[];
  response_trace_id: string | null;
  async_job_id: string | null;
  async_job_status: string | null;
}

export interface AsyncJobRead {
  id: string;
  project_id: string | null;
  job_type: string;
  resource_type: string;
  resource_id: string;
  status: string;
  retry_count: number;
  max_retries: number;
  failure_reason: string | null;
  failure_history: Array<Record<string, unknown>>;
  next_attempt_at: string;
  started_at: string | null;
  completed_at: string | null;
  dead_lettered_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface StoredDiagnosis {
  major: string;
  projectId?: string;
  savedAt: string;
  diagnosis: Pick<
    DiagnosisResultPayload,
    'headline' | 'strengths' | 'gaps' | 'risk_level' | 'recommended_focus'
  >;
}

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
