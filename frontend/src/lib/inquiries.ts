import { api } from './api';

export type InquiryType = 'one_to_one' | 'partnership' | 'bug_report';
export type InquiryMetadataValue = string | number | boolean | null;
export type InquiryCategory =
  | 'product_usage'
  | 'account_login'
  | 'record_upload'
  | 'partnership_request'
  | 'bug'
  | 'feature_request'
  | 'other';
export type InstitutionType = 'school' | 'academy' | 'other';

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
  created_at: string;
  message: string;
}

export type InquiryErrors = Partial<Record<keyof InquiryPayload, string>>;

const emailPattern = /^[^@\s]+@[^@\s]+\.[^@\s]+$/;

function isBlank(value?: string) {
  return !value || !value.trim();
}

export function validateInquiry(payload: InquiryPayload): InquiryErrors {
  const errors: InquiryErrors = {};

  if (isBlank(payload.name)) {
    errors.name = payload.inquiry_type === 'bug_report' ? '이름 또는 닉네임을 입력해 주세요.' : '이름을 입력해 주세요.';
  }
  if (isBlank(payload.email) || !emailPattern.test(payload.email.trim())) {
    errors.email = '올바른 이메일 주소를 입력해 주세요.';
  }
  if (isBlank(payload.message) || payload.message.trim().length < 10) {
    errors.message = '내용은 10자 이상 입력해 주세요.';
  }

  if (payload.inquiry_type === 'one_to_one') {
    if (isBlank(payload.subject)) {
      errors.subject = '문의 제목을 입력해 주세요.';
    }
    if (!payload.inquiry_category || !['product_usage', 'account_login', 'record_upload', 'other'].includes(payload.inquiry_category)) {
      errors.inquiry_category = '문의 유형을 선택해 주세요.';
    }
  }

  if (payload.inquiry_type === 'partnership') {
    if (isBlank(payload.institution_name)) {
      errors.institution_name = '기관명을 입력해 주세요.';
    }
    if (isBlank(payload.phone)) {
      errors.phone = '연락처를 입력해 주세요.';
    }
    if (!payload.institution_type) {
      errors.institution_type = '기관 유형을 선택해 주세요.';
    }
  }

  if (payload.inquiry_type === 'bug_report') {
    if (!payload.inquiry_category || !['bug', 'feature_request'].includes(payload.inquiry_category)) {
      errors.inquiry_category = '버그 또는 기능 제안을 선택해 주세요.';
    }
    if (isBlank(payload.context_location)) {
      errors.context_location = '발생 위치를 입력해 주세요.';
    }
  }

  return errors;
}

export async function submitInquiry(payload: InquiryPayload) {
  const normalized: InquiryPayload = {
    ...payload,
    name: payload.name?.trim(),
    email: payload.email.trim(),
    phone: payload.phone?.trim(),
    subject: payload.subject?.trim(),
    message: payload.message.trim(),
    institution_name: payload.institution_name?.trim(),
    source_path: payload.source_path?.trim(),
    context_location: payload.context_location?.trim(),
    metadata: payload.metadata,
  };

  return api.post<InquiryResponse>('/api/v1/inquiries', normalized);
}
