export const DIAGNOSIS_RISK_LEVEL_VALUES = ['safe', 'warning', 'danger'] as const;
export const DIAGNOSIS_GAP_DIFFICULTY_VALUES = ['low', 'medium', 'high'] as const;
export const DIAGNOSIS_QUEST_PRIORITY_VALUES = ['low', 'medium', 'high'] as const;
export const DIAGNOSIS_GAP_AXIS_VALUES = [
  'universal_rigor',
  'universal_specificity',
  'relational_narrative',
  'relational_continuity',
  'cluster_depth',
  'cluster_suitability',
] as const;
export const DIAGNOSIS_AXIS_SEVERITY_VALUES = ['strong', 'watch', 'weak'] as const;
export const DIAGNOSIS_DIRECTION_COMPLEXITY_VALUES = ['lighter', 'balanced', 'deeper'] as const;
export const DIAGNOSIS_EXPORT_FORMAT_VALUES = ['pdf', 'pptx', 'hwpx'] as const;
export const DIAGNOSIS_REPORT_MODE_VALUES = ['basic', 'premium', 'consultant', 'compact', 'premium_10p'] as const;
export const DIAGNOSIS_ADMISSION_AXIS_VALUES = [
  'universal_rigor',
  'universal_specificity',
  'relational_narrative',
  'relational_continuity',
  'cluster_depth',
  'cluster_suitability',
  'authenticity_risk',
] as const;

export type DiagnosisRiskLevel = (typeof DIAGNOSIS_RISK_LEVEL_VALUES)[number];
export type DiagnosisGapDifficulty = (typeof DIAGNOSIS_GAP_DIFFICULTY_VALUES)[number];
export type DiagnosisQuestPriority = (typeof DIAGNOSIS_QUEST_PRIORITY_VALUES)[number];
export type DiagnosisGapAxisKey = (typeof DIAGNOSIS_GAP_AXIS_VALUES)[number];
export type DiagnosisAxisSeverity = (typeof DIAGNOSIS_AXIS_SEVERITY_VALUES)[number];
export type DiagnosisDirectionComplexity = (typeof DIAGNOSIS_DIRECTION_COMPLEXITY_VALUES)[number];
export type DiagnosisExportFormat = (typeof DIAGNOSIS_EXPORT_FORMAT_VALUES)[number];
export type DiagnosisReportMode = (typeof DIAGNOSIS_REPORT_MODE_VALUES)[number];
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

export interface ContinuityLink {
  subject_chain: string[];
  description: string;
  strength: 'weak' | 'moderate' | 'strong';
}

export interface ThemeCluster {
  theme: string;
  evidence: string[];
  depth_level: 'exploratory' | 'applied' | 'integrated';
  cross_subject: boolean;
}

export interface OutlierActivity {
  activity: string;
  reason: string;
}

export interface RelationalGraph {
  continuity_links: ContinuityLink[];
  theme_clusters: ThemeCluster[];
  outlier_activities: OutlierActivity[];
  major_alignment_score: number;
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
  requested_llm_provider?: string | null;
  requested_llm_model?: string | null;
  actual_llm_provider?: string | null;
  actual_llm_model?: string | null;
  llm_profile_used?: string | null;
  fallback_used?: boolean | null;
  fallback_reason?: string | null;
  processing_duration_ms?: number | null;
  diagnosis_result_json?: Record<string, unknown> | null;
  diagnosis_report_markdown?: string | null;
  diagnosis_summary_json?: Record<string, unknown> | null;
  chatbot_context_json?: Record<string, unknown> | null;
  relational_graph?: RelationalGraph | null;
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
  status_message?: string | null;
  result_payload: DiagnosisResultPayload | null;
  error_message: string | null;
  review_required: boolean;
  policy_flags: DiagnosisPolicyFlag[];
  citations: DiagnosisCitation[];
  response_trace_id: string | null;
  async_job_id: string | null;
  async_job_status: string | null;
  report_status?: string | null;
  report_async_job_id?: string | null;
  report_async_job_status?: string | null;
  report_artifact_id?: string | null;
  report_error_message?: string | null;
}

export interface ConsultantDiagnosisEvidenceItem {
  source_label: string;
  page_number?: number | null;
  excerpt: string;
  relevance_score: number;
  support_status: 'verified' | 'probable' | 'needs_verification';
}

export interface ConsultantDiagnosisScoreBlock {
  key: string;
  label: string;
  score: number;
  band: string;
  interpretation: string;
  uncertainty_note?: string | null;
}

export interface ConsultantDiagnosisScoreGroup {
  group: 'student_evaluation' | 'system_quality';
  title: string;
  blocks: ConsultantDiagnosisScoreBlock[];
  gating_status?: 'ok' | 'reanalysis_required' | 'blocked' | null;
  note?: string | null;
}

export interface ConsultantDiagnosisRoadmapItem {
  horizon: '1_month' | '3_months' | '6_months';
  title: string;
  actions: string[];
  success_signals: string[];
  caution_notes: string[];
}

export interface ConsultantSubjectMetricScores {
  academic_concept_density: number;
  inquiry_process: number;
  student_agency: number;
  major_connection: number;
  expansion_potential: number;
  differentiation: number;
  interview_defense: number;
}

export interface ConsultantSubjectSpecialtyAnalysis {
  subject: string;
  core_record_summary: string;
  strengths: string[];
  weaknesses: string[];
  score: number;
  metric_scores: ConsultantSubjectMetricScores;
  level: '매우 강함' | '강함' | '보통' | '약함' | '위험';
  admissions_meaning: string;
  major_connection: string;
  sentence_to_improve: string;
  recommended_follow_up: string;
  interview_question: string;
  evidence_refs: string[];
}

export interface ConsultantRecordNetworkNode {
  id: string;
  label: string;
  category: string;
  evidence_summary: string;
  weight: number;
}

export interface ConsultantRecordNetworkEdge {
  source: string;
  target: string;
  label: string;
  strength: 'Strong' | 'Moderate' | 'Weak' | 'Artificial';
  rationale: string;
}

export interface ConsultantRecordNetwork {
  central_theme: string;
  evaluation: Record<string, string>;
  nodes: ConsultantRecordNetworkNode[];
  edges: ConsultantRecordNetworkEdge[];
  matrix: Array<Record<string, unknown>>;
}

export interface ConsultantResearchTopicRecommendation {
  title: string;
  classification: '강력 추천' | '확장 가능 주제';
  connected_evidence: string;
  inquiry_question: string;
  subject_concepts: string[];
  method: string;
  expected_output: string;
  record_sentence: string;
  interview_use: string;
  difficulty: '상' | '중' | '하';
  priority: number;
}

export interface ConsultantInterviewQuestionFrame {
  category: '전공 적합성' | '탐구 과정 검증' | '약점 방어';
  question: string;
  intent: string;
  answer_frame: string;
  connected_evidence: string;
  good_direction: string;
  avoid: string;
}

export interface ConsultantBeforeAfterRewrite {
  original_summary: string;
  problem: string;
  improved_sentence: string;
  why_better: string;
  exaggeration_risk: string;
}

export interface ConsultantGradeStoryAnalysis {
  grade_label: string;
  stage_role: string;
  core_activities: string[];
  visible_competencies: string[];
  weak_connections: string[];
  next_flow: string;
  section_linkage: string;
  guidance_tone: string;
}

export interface ConsultantReportQualityGate {
  key: string;
  label: string;
  passed: boolean;
  message: string;
}

export interface ConsultantDiagnosisSection {
  id: string;
  title: string;
  subtitle?: string | null;
  body_markdown: string;
  evidence_items: ConsultantDiagnosisEvidenceItem[];
  unsupported_claims: string[];
  additional_verification_needed: string[];
}

export interface ConsultantDiagnosisReport {
  diagnosis_run_id: string;
  project_id: string;
  report_mode: DiagnosisReportMode;
  template_id: string;
  title: string;
  subtitle: string;
  student_target_context: string;
  generated_at: string;
  report_mode_label?: string | null;
  expected_page_range?: string | null;
  actual_page_count?: number | null;
  score_blocks: ConsultantDiagnosisScoreBlock[];
  score_groups: ConsultantDiagnosisScoreGroup[];
  sections: ConsultantDiagnosisSection[];
  roadmap: ConsultantDiagnosisRoadmapItem[];
  subject_specialty_analyses?: ConsultantSubjectSpecialtyAnalysis[];
  record_network?: ConsultantRecordNetwork | null;
  research_topics?: ConsultantResearchTopicRecommendation[];
  interview_questions?: ConsultantInterviewQuestionFrame[];
  before_after_examples?: ConsultantBeforeAfterRewrite[];
  grade_story_analyses?: ConsultantGradeStoryAnalysis[];
  quality_gates?: ConsultantReportQualityGate[];
  citations: ConsultantDiagnosisEvidenceItem[];
  uncertainty_notes: string[];
  final_consultant_memo: string;
  appendix_notes: string[];
  render_hints: Record<string, unknown>;
}

export interface DiagnosisReportCreateRequest {
  report_mode?: DiagnosisReportMode;
  template_id?: string | null;
  include_appendix?: boolean;
  include_citations?: boolean;
  force_regenerate?: boolean;
}

export interface ConsultantDiagnosisArtifactResponse {
  id: string;
  diagnosis_run_id: string;
  project_id: string;
  report_mode: DiagnosisReportMode;
  template_id: string;
  export_format: 'pdf';
  include_appendix: boolean;
  include_citations: boolean;
  status: 'READY' | 'FAILED';
  version: number;
  storage_provider?: string | null;
  storage_key?: string | null;
  generated_file_path?: string | null;
  download_url?: string | null;
  execution_metadata?: Record<string, unknown> | null;
  error_message?: string | null;
  payload?: ConsultantDiagnosisReport | null;
  created_at: string;
  updated_at: string;
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
  progress_percent?: number | null;
  progress_history?: Array<{ stage: string; message: string; completed_at: string }>;
  next_attempt_at: string;
  started_at: string | null;
  completed_at: string | null;
  dead_lettered_at: string | null;
  created_at: string;
  updated_at: string;
}
