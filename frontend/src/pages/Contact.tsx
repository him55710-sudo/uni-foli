import React, { useEffect, useRef, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { Building2, Bug, Headset, Mail, Phone, Send, Sparkles } from 'lucide-react';
import toast from 'react-hot-toast';
import { submitInquiry, type InquiryErrors, type InquiryPayload, validateInquiry } from '../lib/inquiries';

type ContactTab = 'one_to_one' | 'partnership' | 'bug_report';

const tabConfigs: Record<
  ContactTab,
  {
    label: string;
    title: string;
    description: string;
    icon: typeof Headset;
    query: string;
  }
> = {
  one_to_one: {
    label: '1:1 문의',
    title: '계정, 사용 흐름, 기록 업로드 관련 문의',
    description: '학생과 보호자가 바로 사용할 수 있는 문의 채널입니다.',
    icon: Headset,
    query: 'support',
  },
  partnership: {
    label: '협업/도입 문의',
    title: '학교·학원 단위 협업과 도입 가능성 문의',
    description: '운영 방식, 적용 범위, 협업 흐름을 확인하고 싶은 기관을 위한 채널입니다.',
    icon: Building2,
    query: 'partnership',
  },
  bug_report: {
    label: '버그/기능 제안',
    title: '문제 제보와 개선 제안을 분리해 받습니다.',
    description: '발생 위치와 상황을 남겨주시면 원인 파악에 도움이 됩니다.',
    icon: Bug,
    query: 'bug',
  },
};

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
  return tabConfigs[tab].query;
}

export function Contact() {
  const [searchParams, setSearchParams] = useSearchParams();
  const initialTab = resolveTab(searchParams.get('type'));
  const [activeTab, setActiveTab] = useState<ContactTab>(initialTab);
  const [oneToOne, setOneToOne] = useState(oneToOneInitial);
  const [partnership, setPartnership] = useState(partnershipInitial);
  const [bugReport, setBugReport] = useState(bugInitial);
  const [errors, setErrors] = useState<Record<ContactTab, InquiryErrors>>({
    one_to_one: {},
    partnership: {},
    bug_report: {},
  });
  const [submittingTab, setSubmittingTab] = useState<ContactTab | null>(null);
  const tabRefs = useRef<Record<ContactTab, HTMLButtonElement | null>>({
    one_to_one: null,
    partnership: null,
    bug_report: null,
  });

  useEffect(() => {
    setActiveTab(resolveTab(searchParams.get('type')));
  }, [searchParams]);

  const setTab = (tab: ContactTab) => {
    setActiveTab(tab);
    setSearchParams({ type: getQueryValue(tab) });
  };

  const moveTab = (direction: 1 | -1) => {
    const tabs: ContactTab[] = ['one_to_one', 'partnership', 'bug_report'];
    const currentIndex = tabs.indexOf(activeTab);
    const nextIndex = (currentIndex + direction + tabs.length) % tabs.length;
    const nextTab = tabs[nextIndex];
    setTab(nextTab);
    tabRefs.current[nextTab]?.focus();
  };

  const handleTabKeyDown = (event: React.KeyboardEvent<HTMLButtonElement>) => {
    if (event.key === 'ArrowRight') {
      event.preventDefault();
      moveTab(1);
    }
    if (event.key === 'ArrowLeft') {
      event.preventDefault();
      moveTab(-1);
    }
  };

  const handleSubmit = async (tab: ContactTab, payload: InquiryPayload) => {
    const validation = validateInquiry(payload);
    setErrors(prev => ({ ...prev, [tab]: validation }));
    if (Object.keys(validation).length > 0) {
      toast.error('필수 항목을 확인해 주세요.');
      return;
    }

    setSubmittingTab(tab);
    const loadingId = toast.loading('문의 내용을 접수하고 있습니다...');

    try {
      await submitInquiry(payload);
      toast.success('문의가 접수되었습니다. 남겨주신 연락처로 확인 후 안내드리겠습니다.', { id: loadingId });
      setErrors(prev => ({ ...prev, [tab]: {} }));
      if (tab === 'one_to_one') setOneToOne(oneToOneInitial);
      if (tab === 'partnership') setPartnership(partnershipInitial);
      if (tab === 'bug_report') setBugReport(bugInitial);
    } catch (error) {
      console.error('Inquiry submit failed:', error);
      toast.error('문의 접수에 실패했습니다. 잠시 후 다시 시도해 주세요.', { id: loadingId });
    } finally {
      setSubmittingTab(null);
    }
  };

  const activeConfig = tabConfigs[activeTab];
  const ActiveIcon = activeConfig.icon;

  return (
    <main className="mx-auto max-w-7xl px-4 py-16 sm:px-6 lg:px-8">
      <section className="grid gap-8 lg:grid-cols-[0.88fr_1.12fr]">
        <div className="rounded-[40px] border border-slate-200 bg-white p-8 shadow-sm sm:p-10">
          <p className="text-sm font-black uppercase tracking-[0.22em] text-blue-600">Support Hub</p>
          <h1 className="mt-3 text-4xl font-black tracking-tight text-slate-900 sm:text-5xl">
            문의와 협업 제안을
            <br />
            한 곳에서 받습니다.
          </h1>
          <p className="mt-5 text-base font-medium leading-8 text-slate-600">
            Uni Folia의 사용 문의, 학교·학원 협업, 버그 및 기능 제안을 구분해 접수할 수 있습니다. 유형에 맞는 항목을 남겨주시면
            확인 흐름이 더 선명해집니다.
          </p>

          <div className="mt-8 space-y-4">
            <div className="rounded-[28px] border border-slate-200 bg-slate-50 p-5">
              <div className="flex items-center gap-3">
                <Mail size={18} className="text-blue-600" />
                <span className="text-sm font-black text-slate-900">이메일 문의</span>
              </div>
              <a href="mailto:mongben@naver.com" className="mt-3 block text-base font-bold text-slate-700 underline decoration-slate-200">
                mongben@naver.com
              </a>
            </div>
            <div className="rounded-[28px] border border-slate-200 bg-slate-50 p-5">
              <div className="flex items-center gap-3">
                <Phone size={18} className="text-blue-600" />
                <span className="text-sm font-black text-slate-900">협업 연락처</span>
              </div>
              <a href="tel:01076142633" className="mt-3 block text-base font-bold text-slate-700 underline decoration-slate-200">
                010-7614-2633
              </a>
            </div>
            <div className="rounded-[28px] border border-blue-100 bg-blue-50 p-5">
              <div className="flex items-center gap-3">
                <Sparkles size={18} className="text-blue-600" />
                <span className="text-sm font-black text-slate-900">안내</span>
              </div>
              <p className="mt-3 text-sm font-medium leading-7 text-slate-600">
                문의 내용은 제품 운영과 지원에 필요한 범위에서만 검토합니다. 결제 시스템과 기관 도입 패키지는 현재 준비 중이므로,
                공개되지 않은 항목은 문의를 통해 정직하게 안내드립니다.
              </p>
            </div>
          </div>
        </div>

        <div className="rounded-[40px] border border-slate-200 bg-white p-6 shadow-sm sm:p-8">
          <div className="rounded-[32px] border border-slate-200 bg-slate-50 p-2">
            <div role="tablist" aria-label="문의 유형 선택" className="grid gap-2 md:grid-cols-3">
              {(Object.entries(tabConfigs) as Array<[ContactTab, (typeof tabConfigs)[ContactTab]]>).map(([tab, config]) => {
                const Icon = config.icon;
                const selected = activeTab === tab;
                return (
                  <button
                    key={tab}
                    ref={element => {
                      tabRefs.current[tab] = element;
                    }}
                    id={`${tab}-tab`}
                    type="button"
                    role="tab"
                    aria-selected={selected}
                    aria-controls={`${tab}-panel`}
                    tabIndex={selected ? 0 : -1}
                    onKeyDown={handleTabKeyDown}
                    onClick={() => setTab(tab)}
                    className={`rounded-[24px] px-4 py-4 text-left transition-colors ${
                      selected ? 'bg-white shadow-sm' : 'text-slate-500 hover:bg-white/70'
                    }`}
                  >
                    <div className="flex items-center gap-2">
                      <Icon size={18} className={selected ? 'text-blue-600' : 'text-slate-400'} />
                      <span className="text-sm font-black text-slate-900">{config.label}</span>
                    </div>
                    <p className="mt-2 text-xs font-medium leading-5 text-slate-500">{config.description}</p>
                  </button>
                );
              })}
            </div>
          </div>

          <div className="mt-6 rounded-[32px] border border-slate-200 bg-white p-6">
            <div className="mb-6 flex items-start gap-3">
              <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-blue-50 text-blue-600">
                <ActiveIcon size={22} />
              </div>
              <div>
                <h2 className="text-2xl font-black tracking-tight text-slate-900">{activeConfig.title}</h2>
                <p className="mt-2 text-sm font-medium leading-7 text-slate-600">{activeConfig.description}</p>
              </div>
            </div>

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
          </div>
        </div>
      </section>

      <section className="mt-12 rounded-[36px] border border-slate-200 bg-white p-8 shadow-sm">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h2 className="text-2xl font-black tracking-tight text-slate-900">로그인 전에도 서비스 방향을 먼저 확인할 수 있습니다.</h2>
            <p className="mt-2 text-sm font-medium leading-7 text-slate-600">
              처음 방문한 사용자라면 공개 홈과 FAQ에서 제품 원칙과 워크플로를 먼저 확인해 보세요.
            </p>
          </div>
          <div className="flex flex-wrap gap-3">
            <Link to="/" className="rounded-full border border-slate-200 bg-slate-50 px-5 py-3 text-sm font-black text-slate-700">
              홈으로 돌아가기
            </Link>
            <Link to="/faq" className="rounded-full bg-slate-900 px-5 py-3 text-sm font-black text-white">
              FAQ 보기
            </Link>
          </div>
        </div>
      </section>
    </main>
  );
}

function FieldShell({
  id,
  label,
  required = false,
  children,
  error,
}: {
  id: string;
  label: string;
  required?: boolean;
  children: React.ReactNode;
  error?: string;
}) {
  return (
    <div className="space-y-2">
      <label htmlFor={id} className="block text-sm font-black text-slate-700">
        {label}
        {required ? <span className="ml-1 text-blue-600">*</span> : null}
      </label>
      {children}
      {error ? <p className="text-xs font-bold text-red-600">{error}</p> : null}
    </div>
  );
}

function inputClass(error?: string) {
  return `w-full rounded-2xl border bg-slate-50 px-4 py-3.5 text-sm font-medium text-slate-700 outline-none transition-colors placeholder:text-slate-400 ${
    error ? 'border-red-200 focus:border-red-400' : 'border-slate-200 focus:border-blue-500'
  }`;
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
      id="one_to_one-panel"
      role="tabpanel"
      aria-labelledby="one_to_one-tab"
      className="grid gap-5"
      onSubmit={event => {
        event.preventDefault();
        onSubmit();
      }}
    >
      <div className="grid gap-5 md:grid-cols-2">
        <FieldShell id="support-name" label="이름" required error={errors.name}>
          <input
            id="support-name"
            value={payload.name ?? ''}
            onChange={event => onChange({ ...payload, name: event.target.value })}
            className={inputClass(errors.name)}
            autoComplete="name"
            aria-invalid={Boolean(errors.name)}
          />
        </FieldShell>
        <FieldShell id="support-email" label="이메일" required error={errors.email}>
          <input
            id="support-email"
            type="email"
            value={payload.email}
            onChange={event => onChange({ ...payload, email: event.target.value })}
            className={inputClass(errors.email)}
            autoComplete="email"
            aria-invalid={Boolean(errors.email)}
          />
        </FieldShell>
      </div>

      <FieldShell id="support-type" label="문의 유형" required error={errors.inquiry_category}>
        <select
          id="support-type"
          value={payload.inquiry_category ?? 'product_usage'}
          onChange={event => onChange({ ...payload, inquiry_category: event.target.value as InquiryPayload['inquiry_category'] })}
          className={inputClass(errors.inquiry_category)}
          aria-invalid={Boolean(errors.inquiry_category)}
        >
          <option value="product_usage">서비스 사용 방법</option>
          <option value="account_login">계정/로그인</option>
          <option value="record_upload">기록 업로드</option>
          <option value="other">기타</option>
        </select>
      </FieldShell>

      <FieldShell id="support-subject" label="제목" required error={errors.subject}>
        <input
          id="support-subject"
          value={payload.subject ?? ''}
          onChange={event => onChange({ ...payload, subject: event.target.value })}
          className={inputClass(errors.subject)}
          aria-invalid={Boolean(errors.subject)}
        />
      </FieldShell>

      <FieldShell id="support-message" label="내용" required error={errors.message}>
        <textarea
          id="support-message"
          rows={6}
          value={payload.message}
          onChange={event => onChange({ ...payload, message: event.target.value })}
          className={inputClass(errors.message)}
          aria-invalid={Boolean(errors.message)}
        />
      </FieldShell>

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
      id="partnership-panel"
      role="tabpanel"
      aria-labelledby="partnership-tab"
      className="grid gap-5"
      onSubmit={event => {
        event.preventDefault();
        onSubmit();
      }}
    >
      <div className="grid gap-5 md:grid-cols-2">
        <FieldShell id="partner-org" label="기관명" required error={errors.institution_name}>
          <input
            id="partner-org"
            value={payload.institution_name ?? ''}
            onChange={event => onChange({ ...payload, institution_name: event.target.value })}
            className={inputClass(errors.institution_name)}
            aria-invalid={Boolean(errors.institution_name)}
          />
        </FieldShell>
        <FieldShell id="partner-name" label="담당자명" required error={errors.name}>
          <input
            id="partner-name"
            value={payload.name ?? ''}
            onChange={event => onChange({ ...payload, name: event.target.value })}
            className={inputClass(errors.name)}
            aria-invalid={Boolean(errors.name)}
          />
        </FieldShell>
        <FieldShell id="partner-phone" label="연락처" required error={errors.phone}>
          <input
            id="partner-phone"
            value={payload.phone ?? ''}
            onChange={event => onChange({ ...payload, phone: event.target.value })}
            className={inputClass(errors.phone)}
            autoComplete="tel"
            aria-invalid={Boolean(errors.phone)}
          />
        </FieldShell>
        <FieldShell id="partner-email" label="이메일" required error={errors.email}>
          <input
            id="partner-email"
            type="email"
            value={payload.email}
            onChange={event => onChange({ ...payload, email: event.target.value })}
            className={inputClass(errors.email)}
            autoComplete="email"
            aria-invalid={Boolean(errors.email)}
          />
        </FieldShell>
      </div>

      <FieldShell id="partner-type" label="기관 유형" required error={errors.institution_type}>
        <select
          id="partner-type"
          value={payload.institution_type ?? 'school'}
          onChange={event => onChange({ ...payload, institution_type: event.target.value as InquiryPayload['institution_type'] })}
          className={inputClass(errors.institution_type)}
          aria-invalid={Boolean(errors.institution_type)}
        >
          <option value="school">학교</option>
          <option value="academy">학원</option>
          <option value="other">기타</option>
        </select>
      </FieldShell>

      <FieldShell id="partner-message" label="문의 내용" required error={errors.message}>
        <textarea
          id="partner-message"
          rows={6}
          value={payload.message}
          onChange={event => onChange({ ...payload, message: event.target.value })}
          className={inputClass(errors.message)}
          aria-invalid={Boolean(errors.message)}
        />
      </FieldShell>

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
      id="bug_report-panel"
      role="tabpanel"
      aria-labelledby="bug_report-tab"
      className="grid gap-5"
      onSubmit={event => {
        event.preventDefault();
        onSubmit();
      }}
    >
      <div className="grid gap-5 md:grid-cols-2">
        <FieldShell id="bug-name" label="이름 또는 닉네임" required error={errors.name}>
          <input
            id="bug-name"
            value={payload.name ?? ''}
            onChange={event => onChange({ ...payload, name: event.target.value })}
            className={inputClass(errors.name)}
            aria-invalid={Boolean(errors.name)}
          />
        </FieldShell>
        <FieldShell id="bug-email" label="이메일" required error={errors.email}>
          <input
            id="bug-email"
            type="email"
            value={payload.email}
            onChange={event => onChange({ ...payload, email: event.target.value })}
            className={inputClass(errors.email)}
            aria-invalid={Boolean(errors.email)}
          />
        </FieldShell>
      </div>

      <div className="grid gap-5 md:grid-cols-2">
        <FieldShell id="bug-type" label="유형" required error={errors.inquiry_category}>
          <select
            id="bug-type"
            value={payload.inquiry_category ?? 'bug'}
            onChange={event => onChange({ ...payload, inquiry_category: event.target.value as InquiryPayload['inquiry_category'] })}
            className={inputClass(errors.inquiry_category)}
            aria-invalid={Boolean(errors.inquiry_category)}
          >
            <option value="bug">버그</option>
            <option value="feature_request">기능 제안</option>
          </select>
        </FieldShell>
        <FieldShell id="bug-location" label="발생 위치" required error={errors.context_location}>
          <input
            id="bug-location"
            value={payload.context_location ?? ''}
            onChange={event => onChange({ ...payload, context_location: event.target.value })}
            className={inputClass(errors.context_location)}
            placeholder="예: 작업실 메시지 전송, 기록 업로드 화면"
            aria-invalid={Boolean(errors.context_location)}
          />
        </FieldShell>
      </div>

      <FieldShell id="bug-message" label="상세 내용" required error={errors.message}>
        <textarea
          id="bug-message"
          rows={6}
          value={payload.message}
          onChange={event => onChange({ ...payload, message: event.target.value })}
          className={inputClass(errors.message)}
          aria-invalid={Boolean(errors.message)}
        />
      </FieldShell>

      <SubmitRow pending={pending} />
    </form>
  );
}

function SubmitRow({ pending }: { pending: boolean }) {
  return (
    <div className="flex flex-col gap-3 border-t border-slate-100 pt-6 sm:flex-row sm:items-center sm:justify-between">
      <p className="text-sm font-medium text-slate-500">
        접수 후 확인 가능한 연락처로 안내드립니다. 급한 협업 문의는 공개 연락처도 함께 이용해 주세요.
      </p>
      <button
        type="submit"
        disabled={pending}
        className="inline-flex items-center justify-center gap-2 rounded-full bg-slate-900 px-6 py-4 text-sm font-black text-white shadow-lg shadow-slate-900/10 disabled:cursor-not-allowed disabled:opacity-60"
      >
        {pending ? '전송 중...' : '문의 보내기'}
        <Send size={16} />
      </button>
    </div>
  );
}
