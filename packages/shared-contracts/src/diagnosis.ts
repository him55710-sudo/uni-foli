export const DIAGNOSIS_RISK_LEVEL_VALUES = ['safe', 'warning', 'danger'] as const;
export const DIAGNOSIS_GAP_DIFFICULTY_VALUES = ['low', 'medium', 'high'] as const;
export const DIAGNOSIS_QUEST_PRIORITY_VALUES = ['low', 'medium', 'high'] as const;
export const DIAGNOSIS_GAP_AXIS_VALUES = [
  'conceptual_depth',
  'inquiry_continuity',
  'evidence_density',
  'process_explanation',
  'subject_major_alignment',
] as const;
export const DIAGNOSIS_AXIS_SEVERITY_VALUES = ['strong', 'watch', 'weak'] as const;
export const DIAGNOSIS_DIRECTION_COMPLEXITY_VALUES = ['lighter', 'balanced', 'deeper'] as const;
export const DIAGNOSIS_EXPORT_FORMAT_VALUES = ['pdf', 'pptx', 'hwpx'] as const;
export const DIAGNOSIS_ADMISSION_AXIS_VALUES = [
  'major_alignment',
  'inquiry_continuity',
  'evidence_density',
  'process_explanation',
  'authenticity_risk',
] as const;

export type DiagnosisRiskLevel = (typeof DIAGNOSIS_RISK_LEVEL_VALUES)[number];
export type DiagnosisGapDifficulty = (typeof DIAGNOSIS_GAP_DIFFICULTY_VALUES)[number];
export type DiagnosisQuestPriority = (typeof DIAGNOSIS_QUEST_PRIORITY_VALUES)[number];
export type DiagnosisGapAxisKey = (typeof DIAGNOSIS_GAP_AXIS_VALUES)[number];
export type DiagnosisAxisSeverity = (typeof DIAGNOSIS_AXIS_SEVERITY_VALUES)[number];
export type DiagnosisDirectionComplexity = (typeof DIAGNOSIS_DIRECTION_COMPLEXITY_VALUES)[number];
export type DiagnosisExportFormat = (typeof DIAGNOSIS_EXPORT_FORMAT_VALUES)[number];
export type DiagnosisAdmissionAxisKey = (typeof DIAGNOSIS_ADMISSION_AXIS_VALUES)[number];
export type DiagnosisAxisPrioritySeverity = 'low' | 'medium' | 'high';

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
  difficulty: DiagnosisGapDifficulty;
}

export interface DiagnosisQuest {
  title: string;
  description: string;
  priority: DiagnosisQuestPriority;
}

export type ClaimSupportStatus = 'supported' | 'weak' | 'unsupported' | 'mixed';
export type ClaimProvenanceType = 'student_record' | 'external_research' | 'ai_interpretation';

export interface ClaimGrounding {
  id: string;
  claim_text: string;
  support_status: ClaimSupportStatus;
  confidence: number;
  source_excerpts: Array<{
    text: string;
    source_label: string;
    page_number?: number | null;
    chunk_id?: string | null;
  }>;
  provenance_type: ClaimProvenanceType;
  unsupported_reason?: string | null;
}

export interface DiagnosisSummary {
  overview: string;
  target_context: string;
  reasoning: string;
  authenticity_note: string;
}

export interface DiagnosisGapAxis {
  key: DiagnosisGapAxisKey;
  label: string;
  score: number;
  severity: DiagnosisAxisSeverity;
  rationale: string;
  evidence_hint?: string | null;
}

export interface DocumentQualitySummary {
  source_mode: string;
  parse_reliability_score: number;
  parse_reliability_band: string;
  needs_review: boolean;
  needs_review_documents: number;
  total_records: number;
  total_word_count: number;
  narrative_density: number;
  evidence_density: number;
  summary: string;
}

export interface SectionAnalysisItem {
  key: string;
  label: string;
  present: boolean;
  record_count: number;
  note: string;
}

export interface AdmissionAxisResult {
  key: DiagnosisAdmissionAxisKey;
  label: string;
  score: number;
  band: string;
  severity: DiagnosisAxisPrioritySeverity;
  rationale: string;
  evidence_hints: string[];
}

export interface TopicCandidate {
  id: string;
  title: string;
  summary: string;
  why_it_fits: string;
  evidence_hooks: string[];
}

export interface PageCountOption {
  id: string;
  label: string;
  page_count: number;
  rationale: string;
}

export interface FormatRecommendation {
  format: DiagnosisExportFormat;
  label: string;
  rationale: string;
  recommended: boolean;
  caution?: string | null;
}

export interface TemplatePreviewMetadata {
  accent_color: string;
  surface_tone: string;
  cover_title: string;
  preview_sections: string[];
  thumbnail_hint: string;
}

export interface TemplateCandidate {
  id: string;
  label: string;
  description: string;
  supported_formats: DiagnosisExportFormat[];
  category: string;
  section_schema: string[];
  density: string;
  visual_priority: string;
  supports_provenance_appendix: boolean;
  recommended_for: string[];
  preview: TemplatePreviewMetadata;
  why_it_fits?: string | null;
  recommended?: boolean;
}

export interface RecommendedDirection {
  id: string;
  label: string;
  summary: string;
  why_now: string;
  complexity: DiagnosisDirectionComplexity;
  related_axes: DiagnosisGapAxisKey[];
  topic_candidates: TopicCandidate[];
  page_count_options: PageCountOption[];
  format_recommendations: FormatRecommendation[];
  template_candidates: TemplateCandidate[];
}

export interface RecommendedDefaultAction {
  direction_id: string;
  topic_id: string;
  page_count: number;
  export_format: DiagnosisExportFormat;
  template_id: string;
  rationale: string;
}

export interface GuidedOutlineSection {
  id: string;
  title: string;
  purpose: string;
  evidence_plan: string[];
  authenticity_guardrail: string;
}

export interface GuidedDraftOutline {
  title: string;
  summary: string;
  outline_markdown: string;
  sections: GuidedOutlineSection[];
  export_format: DiagnosisExportFormat;
  template_id: string;
  template_label: string;
  page_count: number;
  include_provenance_appendix: boolean;
  hide_internal_provenance_on_final_export: boolean;
  draft_id?: string | null;
  draft_title?: string | null;
}

export interface DiagnosisGuidedPlanRequest {
  direction_id: string;
  topic_id: string;
  page_count: number;
  export_format: DiagnosisExportFormat;
  template_id: string;
  include_provenance_appendix?: boolean;
  hide_internal_provenance_on_final_export?: boolean;
  open_text_note?: string | null;
}

export interface DiagnosisGuidedPlanResponse {
  diagnosis_run_id: string;
  project_id: string;
  direction: RecommendedDirection;
  topic: TopicCandidate;
  outline: GuidedDraftOutline;
}

export interface DiagnosisResultPayload {
  headline: string;
  overview?: string | null;
  strengths: string[];
  gaps: string[];
  detailed_gaps?: DiagnosisGap[];
  recommended_focus: string;
  action_plan?: DiagnosisQuest[];
  risk_level: DiagnosisRiskLevel;
  document_quality?: DocumentQualitySummary | null;
  section_analysis?: SectionAnalysisItem[];
  admission_axes?: AdmissionAxisResult[];
  risks?: string[];
  next_actions?: string[];
  recommended_topics?: string[];
  diagnosis_summary?: DiagnosisSummary | null;
  gap_axes?: DiagnosisGapAxis[];
  recommended_directions?: RecommendedDirection[];
  recommended_default_action?: RecommendedDefaultAction | null;
  citations?: DiagnosisCitation[];
  claims?: ClaimGrounding[];
  policy_codes?: string[];
  review_required?: boolean;
  response_trace_id?: string | null;
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

export interface DiagnosisRunRequest {
  project_id: string;
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
  progress_stage?: string | null;
  progress_message?: string | null;
  progress_history?: Array<{ stage: string; message: string; completed_at: string }>;
  next_attempt_at: string;
  started_at: string | null;
  completed_at: string | null;
  dead_lettered_at: string | null;
  created_at: string;
  updated_at: string;
}
