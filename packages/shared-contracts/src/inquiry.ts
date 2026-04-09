export const INQUIRY_TYPE_VALUES = ['one_to_one', 'partnership', 'bug_report'] as const;
export const INSTITUTION_TYPE_VALUES = ['school', 'academy', 'other'] as const;
export const ONE_TO_ONE_INQUIRY_CATEGORY_VALUES = [
  'product_usage',
  'account_login',
  'record_upload',
  'other',
] as const;
export const PARTNERSHIP_INQUIRY_CATEGORY_VALUES = ['partnership_request'] as const;
export const BUG_REPORT_INQUIRY_CATEGORY_VALUES = ['bug', 'feature_request'] as const;
export const INQUIRY_CATEGORY_VALUES = [
  ...ONE_TO_ONE_INQUIRY_CATEGORY_VALUES,
  ...PARTNERSHIP_INQUIRY_CATEGORY_VALUES,
  ...BUG_REPORT_INQUIRY_CATEGORY_VALUES,
] as const;

export type InquiryType = (typeof INQUIRY_TYPE_VALUES)[number];
export type InstitutionType = (typeof INSTITUTION_TYPE_VALUES)[number];
export type OneToOneInquiryCategory = (typeof ONE_TO_ONE_INQUIRY_CATEGORY_VALUES)[number];
export type PartnershipInquiryCategory = (typeof PARTNERSHIP_INQUIRY_CATEGORY_VALUES)[number];
export type BugReportInquiryCategory = (typeof BUG_REPORT_INQUIRY_CATEGORY_VALUES)[number];
export type InquiryCategory = (typeof INQUIRY_CATEGORY_VALUES)[number];
export type InquiryMetadataValue = string | number | boolean | null;

export interface InquiryPayload {
  inquiry_type: InquiryType;
  name?: string;
  email: string;
  phone?: string;
  subject?: string;
  message: string;
  inquiry_category?: InquiryCategory;
  institution_name?: string;
  institution_type?: InstitutionType;
  source_path?: string;
  context_location?: string;
  metadata?: Record<string, InquiryMetadataValue>;
}

export interface InquiryResponse {
  id: string;
  inquiry_type: InquiryType;
  status: string;
  delivery_status?: string | null;
  delivery_reason?: string | null;
  delivery_async_job_id?: string | null;
  delivery_retry_needed?: boolean | null;
  created_at: string;
  message: string;
}

export const INQUIRY_ALLOWED_CATEGORIES_BY_TYPE = {
  one_to_one: ONE_TO_ONE_INQUIRY_CATEGORY_VALUES,
  partnership: PARTNERSHIP_INQUIRY_CATEGORY_VALUES,
  bug_report: BUG_REPORT_INQUIRY_CATEGORY_VALUES,
} as const;

export function isInquiryCategoryAllowedForType(
  inquiryType: InquiryType,
  category: InquiryCategory | null | undefined,
): boolean {
  if (!category) {
    return false;
  }
  return INQUIRY_ALLOWED_CATEGORIES_BY_TYPE[inquiryType].includes(
    category as never,
  );
}
