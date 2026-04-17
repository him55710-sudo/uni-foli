/**
 * 전역적으로 사용되는 도메인 모델 및 상태 타입 정의
 */

/**
 * 학생부 문서의 처리 상태
 */
export type DocumentStatus = 'uploaded' | 'masking' | 'parsing' | 'retrying' | 'parsed' | 'partial' | 'failed';

/**
 * 마스킹(개인정보 보호) 처리 상태
 */
export type MaskingStatus = 'pending' | 'masking' | 'masked' | 'failed';

/**
 * 비동기 작업 진행 중으로 간주되는 상태 세트
 */
export const IN_PROGRESS_STATUSES: Set<DocumentStatus> = new Set(['masking', 'parsing', 'retrying']);

/**
 * 비동기 작업이 터미널(종료) 상태로 간주되는 상태 세트
 */
export const TERMINAL_STATUSES: Set<DocumentStatus> = new Set(['parsed', 'partial', 'failed']);

/**
 * 분석 성공으로 간주되는 상태 세트
 */
export const SUCCESS_STATUSES: Set<DocumentStatus> = new Set(['parsed', 'partial']);

/**
 * 공통 문서 정보 인터페이스 (API 응답 기준)
 */
export interface DocumentBase {
  id: string;
  project_id: string;
  status: DocumentStatus;
  masking_status: MaskingStatus;
  original_filename: string | null;
  file_size_bytes: number | null;
  page_count: number;
  word_count: number;
  latest_async_job_id: string | null;
  latest_async_job_status: string | null;
  latest_async_job_error: string | null;
  last_error: string | null;
  created_at: string;
  updated_at: string;
}

/**
 * 진단 작업(Diagnosis Run)의 상태
 */
export type DiagnosisStatus = 'QUEUED' | 'RUNNING' | 'COMPLETED' | 'FAILED' | 'PENDING' | 'SUCCESS';

/**
 * 진단 보고서 생성 상태
 */
export type ReportStatus = 'NOT_REQUESTED' | 'GENERATING' | 'READY' | 'FAILED';

/**
 * 진단 결과 요약 데이터 (Zustand Store나 캐시에서 공통으로 사용)
 */
export interface DiagnosisSummary {
  headline: string;
  strengths: string[];
  gaps: string[];
  risk_level: 'safe' | 'warning' | 'danger';
  recommended_focus: string;
  total_score?: number;
  category_scores?: Record<string, number>;
  score_labels?: Record<string, string>;
  score_explanations?: Record<string, string>;
  major_direction_candidates_top3?: Array<{
    label: string;
    summary: string;
  }>;
  record_completion_state?: 'ongoing' | 'finalized' | 'unknown';
  stage_aware_recommendation_mode?: string;
  stage_aware_recommendation_note?: string;
}

/**
 * 입시 지표 대시보드 데이터 전용 인터페이스
 */
export interface AdmissionsDashboardData {
  total_score: number | null;
  category_scores: Array<{ name: string; score: number }>;
  score_labels: Record<string, string>;
  major_directions: Array<{ label: string; summary: string }>;
  completion_state?: string | null;
  recommendation_mode?: string | null;
  recommendation_note?: string | null;
}
