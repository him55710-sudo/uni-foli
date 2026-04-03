import {
  isInquiryCategoryAllowedForType,
  type InquiryPayload,
  type InquiryResponse,
} from '@shared-contracts';
import { api } from './api';

export {
  BUG_REPORT_INQUIRY_CATEGORY_VALUES,
  INQUIRY_ALLOWED_CATEGORIES_BY_TYPE,
  INQUIRY_CATEGORY_VALUES,
  INQUIRY_TYPE_VALUES,
  INSTITUTION_TYPE_VALUES,
  ONE_TO_ONE_INQUIRY_CATEGORY_VALUES,
  PARTNERSHIP_INQUIRY_CATEGORY_VALUES,
  isInquiryCategoryAllowedForType,
} from '@shared-contracts';
export type {
  BugReportInquiryCategory,
  InquiryCategory,
  InquiryMetadataValue,
  InquiryPayload,
  InquiryResponse,
  InquiryType,
  InstitutionType,
  OneToOneInquiryCategory,
  PartnershipInquiryCategory,
} from '@shared-contracts';

export type InquiryErrors = Partial<Record<keyof InquiryPayload, string>>;

const emailPattern = /^[^@\s]+@[^@\s]+\.[^@\s]+$/;

function isBlank(value?: string) {
  return !value || !value.trim();
}

export function validateInquiry(payload: InquiryPayload): InquiryErrors {
  const errors: InquiryErrors = {};

  if (isBlank(payload.name)) {
    errors.name = '이름을 입력해 주세요.';
  }
  if (isBlank(payload.email) || !emailPattern.test(payload.email.trim())) {
    errors.email = '올바른 이메일 주소를 입력해 주세요.';
  }
  if (isBlank(payload.message) || payload.message.trim().length < 10) {
    errors.message = '문의 내용은 10자 이상 입력해 주세요.';
  }

  if (payload.inquiry_type === 'one_to_one') {
    if (isBlank(payload.subject)) {
      errors.subject = '문의 제목을 입력해 주세요.';
    }
    if (!isInquiryCategoryAllowedForType('one_to_one', payload.inquiry_category)) {
      errors.inquiry_category = '문의 유형을 다시 선택해 주세요.';
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
    if (payload.inquiry_category && !isInquiryCategoryAllowedForType('partnership', payload.inquiry_category)) {
      errors.inquiry_category = '기관 문의 유형이 올바르지 않아요.';
    }
  }

  if (payload.inquiry_type === 'bug_report') {
    if (!isInquiryCategoryAllowedForType('bug_report', payload.inquiry_category)) {
      errors.inquiry_category = '오류 제보 유형을 선택해 주세요.';
    }
    if (isBlank(payload.context_location)) {
      errors.context_location = '문제가 발생한 위치를 입력해 주세요.';
    }
  }

  return errors;
}

export async function submitInquiry(payload: InquiryPayload) {
  const normalized: InquiryPayload = {
    ...payload,
    name: payload.name?.trim(),
    email: payload.email.trim().toLowerCase(),
    phone: payload.phone?.trim(),
    subject: payload.subject?.trim(),
    message: payload.message.trim(),
    inquiry_category: payload.inquiry_type === 'partnership' ? 'partnership_request' : payload.inquiry_category,
    institution_name: payload.institution_name?.trim(),
    source_path: payload.source_path?.trim(),
    context_location: payload.context_location?.trim(),
    metadata: payload.metadata,
  };

  return api.post<InquiryResponse>('/api/v1/inquiries', normalized);
}

