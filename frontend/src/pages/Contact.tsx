import React, { useEffect, useMemo, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { Building2, Bug, Headset, Mail, Phone, Send } from 'lucide-react';
import toast from 'react-hot-toast';
import type { BugReportInquiryCategory, InstitutionType, OneToOneInquiryCategory } from '@shared-contracts';
import {
  getInquirySubmissionFeedback,
  submitInquiry,
  type InquiryErrors,
  type InquiryPayload,
  validateInquiry,
} from '../lib/inquiries';
import {
  Input,
  PageHeader,
  PrimaryButton,
  SectionCard,
  Select,
  StatusBadge,
  SurfaceCard,
  Tabs,
  TextArea,
  WorkflowNotice,
} from '../components/primitives';

type ContactTab = 'one_to_one' | 'partnership' | 'bug_report';

const tabMeta: Record<ContactTab, { label: string; query: string; icon: typeof Headset; title: string; description: string }> = {
  one_to_one: {
    label: '1:1 문의',
    query: 'support',
    icon: Headset,
    title: '사용 문의',
    description: '계정, 업로드, 진단, 문서 작성 중 궁금한 점을 남겨 주세요.',
  },
  partnership: {
    label: '기관 문의',
    query: 'partnership',
    icon: Building2,
    title: '학교/학원 문의',
    description: '학교·학원 단위 도입이나 운영 관련 문의를 남겨 주세요.',
  },
  bug_report: {
    label: '오류 제보',
    query: 'bug',
    icon: Bug,
    title: '오류/개선 제보',
    description: '문제가 발생한 위치와 상황을 알려 주시면 빠르게 확인해 드려요.',
  },
};

const oneToOneCategoryOptions: Array<{ value: OneToOneInquiryCategory; label: string }> = [
  { value: 'product_usage', label: '서비스 사용 방법' },
  { value: 'account_login', label: '계정/로그인' },
  { value: 'record_upload', label: '기록 업로드' },
  { value: 'other', label: '기타' },
];

const institutionTypeOptions: Array<{ value: InstitutionType; label: string }> = [
  { value: 'school', label: '학교' },
  { value: 'academy', label: '학원' },
  { value: 'other', label: '기타 기관' },
];

const bugCategoryOptions: Array<{ value: BugReportInquiryCategory; label: string }> = [
  { value: 'bug', label: '오류' },
  { value: 'feature_request', label: '기능 제안' },
];

const oneToOneInitial: InquiryPayload = {
  inquiry_type: 'one_to_one',
  name: '',
  email: '',
  subject: '',
  inquiry_category: 'product_usage',
  message: '',
  source_path: '/contact',
  metadata: {
    entry_point: 'contact_hub',
    tab: 'one_to_one',
  },
};

const partnershipInitial: InquiryPayload = {
  inquiry_type: 'partnership',
  inquiry_category: 'partnership_request',
  institution_name: '',
  name: '',
  phone: '',
  email: '',
  institution_type: 'school',
  message: '',
  source_path: '/contact?type=partnership',
  metadata: {
    entry_point: 'contact_hub',
    tab: 'partnership',
  },
};

const bugInitial: InquiryPayload = {
  inquiry_type: 'bug_report',
  name: '',
  email: '',
  inquiry_category: 'bug',
  context_location: '',
  message: '',
  source_path: '/contact?type=bug',
  metadata: {
    entry_point: 'contact_hub',
    tab: 'bug_report',
  },
};

function resolveTab(rawType: string | null): ContactTab {
  if (rawType === 'partnership') return 'partnership';
  if (rawType === 'bug' || rawType === 'feedback') return 'bug_report';
  return 'one_to_one';
}

function getQueryValue(tab: ContactTab) {
  return tabMeta[tab].query;
}

export function Contact() {
  const [searchParams, setSearchParams] = useSearchParams();
  const [activeTab, setActiveTab] = useState<ContactTab>(resolveTab(searchParams.get('type')));
  const [oneToOne, setOneToOne] = useState(oneToOneInitial);
  const [partnership, setPartnership] = useState(partnershipInitial);
  const [bugReport, setBugReport] = useState(bugInitial);
  const [errors, setErrors] = useState<Record<ContactTab, InquiryErrors>>({
    one_to_one: {},
    partnership: {},
    bug_report: {},
  });
  const [submittingTab, setSubmittingTab] = useState<ContactTab | null>(null);

  useEffect(() => {
    setActiveTab(resolveTab(searchParams.get('type')));
  }, [searchParams]);

  const setTab = (tab: ContactTab) => {
    setActiveTab(tab);
    setSearchParams({ type: getQueryValue(tab) });
  };

  const tabs = useMemo(
    () => [
      { value: 'one_to_one', label: '1:1 문의' },
      { value: 'partnership', label: '기관 문의' },
      { value: 'bug_report', label: '오류 제보' },
    ] as const,
    [],
  );

  const handleSubmit = async (tab: ContactTab, payload: InquiryPayload) => {
    const validation = validateInquiry(payload);
    setErrors(prev => ({ ...prev, [tab]: validation }));
    if (Object.keys(validation).length > 0) {
      toast.error('필수 입력 항목을 확인해 주세요.');
      return;
    }

    setSubmittingTab(tab);
    const loadingId = toast.loading('문의 내용을 전송하는 중이에요...');
    try {
      const response = await submitInquiry(payload);
      const feedback = getInquirySubmissionFeedback(response);
      if (feedback.kind === 'success') {
        toast.success(feedback.message, { id: loadingId });
      } else {
        toast(feedback.message, { id: loadingId, duration: 7000 });
      }
      setErrors(prev => ({ ...prev, [tab]: {} }));
      if (tab === 'one_to_one') setOneToOne(oneToOneInitial);
      if (tab === 'partnership') setPartnership(partnershipInitial);
      if (tab === 'bug_report') setBugReport(bugInitial);
    } catch (error) {
      console.error('Inquiry submit failed:', error);
      toast.error('문의 접수에 실패했어요. 잠시 후 다시 시도해 주세요.', { id: loadingId });
    } finally {
      setSubmittingTab(null);
    }
  };

  const activeInfo = tabMeta[activeTab];
  const ActiveIcon = activeInfo.icon;

  return (
    <main className="mx-auto max-w-7xl space-y-6 py-10">
      <PageHeader
        eyebrow="문의"
        title="문의 허브"
        description="문의 유형에 맞는 폼으로 빠르게 접수할 수 있어요."
        evidence={
          <div className="flex flex-wrap items-center gap-2">
            <StatusBadge status="active">문의 허브 운영 중</StatusBadge>
            <StatusBadge status="neutral">이메일: mongben@naver.com</StatusBadge>
          </div>
        }
      />

      <div className="grid gap-6 lg:grid-cols-[0.9fr_1.1fr]">
        <SectionCard 
          title="연락 채널" 
          description="급하지 않은 문의는 폼 접수를 권장해요." 
          eyebrow="연락처"
          bodyClassName="space-y-4"
        >
          <SurfaceCard tone="muted" padding="sm">
            <p className="inline-flex items-center gap-2 text-sm font-bold text-slate-800">
              <Mail size={16} className="text-blue-700" />
              이메일
            </p>
            <a href="mailto:mongben@naver.com" className="mt-2 block text-sm font-semibold text-slate-700 underline decoration-slate-200">
              mongben@naver.com
            </a>
          </SurfaceCard>

          <SurfaceCard tone="muted" padding="sm">
            <p className="inline-flex items-center gap-2 text-sm font-bold text-slate-800">
              <Phone size={16} className="text-blue-700" />
              전화
            </p>
            <a href="tel:01076142633" className="mt-2 block text-sm font-semibold text-slate-700 underline decoration-slate-200">
              010-7614-2633
            </a>
          </SurfaceCard>

          <WorkflowNotice
            tone="info"
            title="응답 안내"
            description="문의 종류에 따라 확인 시간이 다를 수 있어요. 기관 문의는 학교/학원 정보를 함께 적어 주세요."
          />

          <div className="flex flex-wrap gap-2">
            <Link to="/" className="inline-flex items-center gap-2 rounded-2xl border border-slate-300 bg-white px-4 py-2 text-sm font-bold text-slate-700">
              공개 페이지
            </Link>
            <Link to="/faq" className="inline-flex items-center gap-2 rounded-2xl border border-slate-300 bg-white px-4 py-2 text-sm font-bold text-slate-700">
              FAQ
            </Link>
          </div>
        </SectionCard>

        <SectionCard
          title={activeInfo.title}
          description={activeInfo.description}
          eyebrow="문의 작성"
          actions={
            <span className="inline-flex h-9 w-9 items-center justify-center rounded-xl border border-blue-200 bg-blue-50 text-blue-700">
              <ActiveIcon size={16} />
            </span>
          }
        >
          <Tabs value={activeTab} onChange={value => setTab(value as ContactTab)} items={tabs as any} ariaLabel="문의 유형 선택" className="w-full" />

          {activeTab === 'one_to_one' ? (
            <OneToOneForm
              payload={oneToOne}
              errors={errors.one_to_one}
              pending={submittingTab === 'one_to_one'}
              onChange={setOneToOne}
              onSubmit={() => handleSubmit('one_to_one', oneToOne)}
            />
          ) : null}

          {activeTab === 'partnership' ? (
            <PartnershipForm
              payload={partnership}
              errors={errors.partnership}
              pending={submittingTab === 'partnership'}
              onChange={setPartnership}
              onSubmit={() => handleSubmit('partnership', partnership)}
            />
          ) : null}

          {activeTab === 'bug_report' ? (
            <BugReportForm
              payload={bugReport}
              errors={errors.bug_report}
              pending={submittingTab === 'bug_report'}
              onChange={setBugReport}
              onSubmit={() => handleSubmit('bug_report', bugReport)}
            />
          ) : null}
        </SectionCard>
      </div>
    </main>
  );
}

function OneToOneForm({
  payload,
  errors,
  pending,
  onChange,
  onSubmit,
}: {
  payload: InquiryPayload;
  errors: InquiryErrors;
  pending: boolean;
  onChange: (value: InquiryPayload) => void;
  onSubmit: () => void;
}) {
  return (
    <form
      className="grid gap-4"
      onSubmit={event => {
        event.preventDefault();
        onSubmit();
      }}
    >
      <div className="grid gap-4 md:grid-cols-2">
        <Input id="contact-name" label="이름" value={payload.name ?? ''} onChange={event => onChange({ ...payload, name: event.target.value })} error={errors.name} />
        <Input
          id="contact-email"
          type="email"
          label="이메일"
          value={payload.email}
          onChange={event => onChange({ ...payload, email: event.target.value })}
          error={errors.email}
        />
      </div>

      <Select
        id="contact-category"
        label="문의 유형"
        value={payload.inquiry_category ?? 'product_usage'}
        onChange={event => onChange({ ...payload, inquiry_category: event.target.value as OneToOneInquiryCategory })}
        options={oneToOneCategoryOptions}
        error={errors.inquiry_category}
      />

      <Input
        id="contact-subject"
        label="제목"
        value={payload.subject ?? ''}
        onChange={event => onChange({ ...payload, subject: event.target.value })}
        error={errors.subject}
      />

      <TextArea
        id="contact-message"
        rows={6}
        label="문의 내용"
        value={payload.message}
        onChange={event => onChange({ ...payload, message: event.target.value })}
        error={errors.message}
      />

      <SubmitRow pending={pending} />
    </form>
  );
}

function PartnershipForm({
  payload,
  errors,
  pending,
  onChange,
  onSubmit,
}: {
  payload: InquiryPayload;
  errors: InquiryErrors;
  pending: boolean;
  onChange: (value: InquiryPayload) => void;
  onSubmit: () => void;
}) {
  return (
    <form
      className="grid gap-4"
      onSubmit={event => {
        event.preventDefault();
        onSubmit();
      }}
    >
      <div className="grid gap-4 md:grid-cols-2">
        <Input id="partner-org" label="기관명" value={payload.institution_name ?? ''} onChange={event => onChange({ ...payload, institution_name: event.target.value })} error={errors.institution_name} />
        <Input id="partner-name" label="담당자명" value={payload.name ?? ''} onChange={event => onChange({ ...payload, name: event.target.value })} error={errors.name} />
      </div>

      <div className="grid gap-4 md:grid-cols-2">
        <Input id="partner-phone" label="연락처" value={payload.phone ?? ''} onChange={event => onChange({ ...payload, phone: event.target.value })} error={errors.phone} />
        <Input id="partner-email" type="email" label="이메일" value={payload.email} onChange={event => onChange({ ...payload, email: event.target.value })} error={errors.email} />
      </div>

      <Select
        id="partner-type"
        label="기관 유형"
        value={payload.institution_type ?? 'school'}
        onChange={event => onChange({ ...payload, institution_type: event.target.value as InstitutionType })}
        options={institutionTypeOptions}
        error={errors.institution_type}
      />

      <TextArea
        id="partner-message"
        rows={6}
        label="문의 내용"
        value={payload.message}
        onChange={event => onChange({ ...payload, message: event.target.value })}
        error={errors.message}
      />

      <SubmitRow pending={pending} />
    </form>
  );
}

function BugReportForm({
  payload,
  errors,
  pending,
  onChange,
  onSubmit,
}: {
  payload: InquiryPayload;
  errors: InquiryErrors;
  pending: boolean;
  onChange: (value: InquiryPayload) => void;
  onSubmit: () => void;
}) {
  return (
    <form
      className="grid gap-4"
      onSubmit={event => {
        event.preventDefault();
        onSubmit();
      }}
    >
      <div className="grid gap-4 md:grid-cols-2">
        <Input id="bug-name" label="이름 또는 닉네임" value={payload.name ?? ''} onChange={event => onChange({ ...payload, name: event.target.value })} error={errors.name} />
        <Input id="bug-email" type="email" label="이메일" value={payload.email} onChange={event => onChange({ ...payload, email: event.target.value })} error={errors.email} />
      </div>

      <div className="grid gap-4 md:grid-cols-2">
        <Select
          id="bug-category"
          label="유형"
          value={payload.inquiry_category ?? 'bug'}
          onChange={event => onChange({ ...payload, inquiry_category: event.target.value as BugReportInquiryCategory })}
          options={bugCategoryOptions}
          error={errors.inquiry_category}
        />
        <Input
          id="bug-location"
          label="발생 위치"
          value={payload.context_location ?? ''}
          onChange={event => onChange({ ...payload, context_location: event.target.value })}
          error={errors.context_location}
          placeholder="예: 기록 업로드 화면"
        />
      </div>

      <TextArea
        id="bug-message"
        rows={6}
        label="상세 내용"
        value={payload.message}
        onChange={event => onChange({ ...payload, message: event.target.value })}
        error={errors.message}
      />

      <SubmitRow pending={pending} />
    </form>
  );
}

function SubmitRow({ pending }: { pending: boolean }) {
  return (
    <div className="flex flex-col gap-3 border-t border-slate-200 pt-4 sm:flex-row sm:items-center sm:justify-between">
      <p className="text-sm font-medium text-slate-500 break-keep">접수 후 확인 가능한 연락처로 답변드립니다.</p>
      <PrimaryButton type="submit" disabled={pending}>
        {pending ? '전송 중...' : '문의 보내기'}
        <Send size={16} />
      </PrimaryButton>
    </div>
  );
}
