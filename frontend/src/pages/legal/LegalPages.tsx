import React from 'react';
import { motion } from 'motion/react';
import { CheckCircle2, Info, Scale, ShieldCheck, Mail, Phone, MapPin, Building, FileText, Ban, Trash2 } from 'lucide-react';

interface LegalSectionProps {
  title: string;
  icon: React.ReactNode;
  children: React.ReactNode;
}

function LegalSection({ title, icon, children }: LegalSectionProps) {
  return (
    <section className="mb-12">
      <div className="mb-6 flex items-center gap-3">
        <div className="flex h-10 w-10 items-center justify-center rounded-2xl border border-blue-100 bg-blue-50 text-blue-600 shadow-sm">
          {icon}
        </div>
        <h2 className="text-xl font-black tracking-tight text-slate-800">{title}</h2>
      </div>
      <div className="space-y-4 pl-[52px] text-[15px] font-medium leading-8 text-slate-600">{children}</div>
    </section>
  );
}

function LegalShell({
  eyebrow,
  title,
  description,
  children,
}: {
  eyebrow: string;
  title: string;
  description: string;
  children: React.ReactNode;
}) {
  return (
    <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} className="mx-auto max-w-4xl px-4 py-16 sm:px-6">
      <div className="mb-16 text-center">
        <div className="mb-4 inline-flex items-center gap-2 rounded-full bg-slate-100 px-4 py-1.5 text-xs font-black uppercase tracking-widest text-slate-500">
          {eyebrow}
        </div>
        <h1 className="mb-6 text-4xl font-black tracking-tight text-slate-900 md:text-5xl">{title}</h1>
        <p className="text-lg font-medium leading-8 text-slate-500">{description}</p>
      </div>

      <div className="rounded-[2.5rem] border border-slate-100 bg-white p-10 shadow-xl shadow-slate-200/50 md:p-16">
        {children}
        
        {/* Company Info Footer block */}
        <div className="mt-20 border-t border-slate-100 pt-10 text-center text-sm font-medium text-slate-400">
          최종 업데이트: 2026년 4월 8일
        </div>
        <div className="mt-6 rounded-2xl bg-slate-50 p-6 text-sm text-slate-500">
          <h3 className="mb-4 font-bold text-slate-700">사업자 정보</h3>
          <div className="grid gap-3 sm:grid-cols-2">
            <div className="flex items-center gap-2">
              <Building size={16} className="text-slate-400" />
              <span>상호명: Uni Foli</span>
            </div>
            <div className="flex items-center gap-2">
              <UserIcon size={16} className="text-slate-400" />
              <span>대표자: 임현수</span>
            </div>
            <div className="flex items-center gap-2">
              <MapPin size={16} className="text-slate-400" />
              <span>주소: 서울특별시 용산구 서빙고로 17 (한강로3가) 센트레빌아스테리움용산오피스텔 7층 704호</span>
            </div>
            <div className="flex items-center gap-2">
              <Mail size={16} className="text-slate-400" />
              <span>이메일: mongben@naver.com</span>
            </div>
            <div className="flex items-center gap-2">
              <Phone size={16} className="text-slate-400" />
              <span>전화번호: 010-3882-7742</span>
            </div>
            <div className="flex items-center gap-2">
              <FileText size={16} className="text-slate-400" />
              <span>사업자등록번호: 254-13-02553</span>
            </div>
            <div className="flex items-center gap-2 sm:col-span-2">
              <FileText size={16} className="text-slate-400" />
              <span>통신판매업 신고번호: 신고 준비 중</span>
            </div>
          </div>
        </div>
      </div>
    </motion.div>
  );
}

// Temporary User Icon component definition for above
function UserIcon(props: any) {
  return (
    <svg
      {...props}
      xmlns="http://www.w3.org/2000/svg"
      width="24"
      height="24"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d="M19 21v-2a4 4 0 0 0-4-4H9a4 4 0 0 0-4 4v2" />
      <circle cx="12" cy="7" r="4" />
    </svg>
  );
}

export function TermsOfService() {
  return (
    <LegalShell
      eyebrow="Service Policy"
      title="이용약관"
      description="Uni Foli는 학생 기록과 탐구 준비를 돕는 도구이며, 안전하고 책임 있는 사용을 전제로 운영됩니다."
    >
      <LegalSection title="서비스의 범위" icon={<Scale size={20} />}>
        <p>
          Uni Foli는 학생의 생기부와 실제 활동 기록을 정리하고, AI 진단과 탐구 플랜, 작업실 drafting 흐름을 지원하는 서비스입니다.
        </p>
        <div className="flex items-start gap-4 rounded-2xl border border-amber-100 bg-amber-50/60 p-6">
          <Info className="mt-1 shrink-0 text-amber-500" size={20} />
          <p className="text-sm font-bold leading-7 text-amber-700">
            Uni Foli는 특정 대학의 합격이나 입시 결과를 보장하지 않습니다. 최종 판단과 제출 책임은 사용자와 교육 기관에 있습니다.
          </p>
        </div>
      </LegalSection>

      <LegalSection title="사용자 데이터와 권리" icon={<ShieldCheck size={20} />}>
        <p>학생이 직접 입력하거나 업로드한 기록의 권리와 책임은 기본적으로 사용자에게 있습니다.</p>
        <ul className="space-y-3">
          {[
            '원본 기록과 업로드 자료의 정확성은 사용자가 확인해야 합니다.',
            'AI 제안 내용은 검토 보조를 위한 것이며, 최종 기록 문장으로 자동 확정되지 않습니다.',
            '사용자 동의 없이 학생 기록을 외부에 공개하거나 판매하지 않습니다.',
          ].map(item => (
            <li key={item} className="flex items-start gap-3">
              <CheckCircle2 size={16} className="mt-1 shrink-0 text-blue-500" />
              <span>{item}</span>
            </li>
          ))}
        </ul>
      </LegalSection>

      <LegalSection title="금지되는 사용 방식" icon={<Ban size={20} />}>
        <ul className="space-y-2">
          <li>실제로 하지 않은 활동을 허위로 생성하거나 기록에 포함하려는 시도</li>
          <li>타인의 개인정보 또는 기록을 무단으로 입력·업로드하는 행위</li>
          <li>서비스 운영을 방해하거나 보안 우회를 시도하는 행위</li>
        </ul>
      </LegalSection>
    </LegalShell>
  );
}

export function PrivacyPolicy() {
  return (
    <LegalShell
      eyebrow="Transparency & Safety"
      title="개인정보처리방침"
      description="Uni Foli는 학생 기록과 개인정보를 다루는 만큼, 수집 범위와 처리 목적을 가능한 한 분명하게 안내합니다."
    >
      <LegalSection title="수집하는 정보" icon={<ShieldCheck size={20} />}>
        <p>서비스 운영과 계정 연결, 기록 분석에 필요한 최소 범위의 정보를 다룹니다.</p>
        <ul className="space-y-4">
          <li>
            <span className="mb-1 block font-black text-slate-700">계정 정보</span>
            이메일, 이름, 로그인 식별자
          </li>
          <li>
            <span className="mb-1 block font-black text-slate-700">학생 설정 정보</span>
            학년, 목표 대학/전공, 관심 진로, 입시 준비 흐름에 필요한 입력값
          </li>
          <li>
            <span className="mb-1 block font-black text-slate-700">업로드 및 작업 정보</span>
            생기부 PDF, 파싱 상태, 작업실 drafting 결과, 문의 허브를 통한 문의 내용
          </li>
        </ul>
      </LegalSection>

      <LegalSection title="처리 목적과 보호 원칙" icon={<Info size={20} />}>
        <div className="mb-6 rounded-2xl border border-slate-100 bg-slate-50 p-6">
          <h3 className="mb-2 font-black text-slate-800">중요: 기록은 근거 기반 워크플로를 위해서만 사용합니다.</h3>
          <p className="text-sm font-bold leading-7 text-slate-600">
            기록과 개인정보는 업로드, 분석, 안전 검토, 결과물 작성 지원 같은 제품 흐름을 위해 필요한 범위에서만 처리합니다.
            부족한 기록을 억지로 생성하거나 외부 공개용 데이터로 전환하는 방향은 지향하지 않습니다.
          </p>
        </div>
        <ul className="space-y-3">
          <li className="flex items-start gap-3">
            <CheckCircle2 size={16} className="mt-1 shrink-0 text-blue-500" />
            <span>전송 구간 보호와 접근 통제를 우선합니다.</span>
          </li>
          <li className="flex items-start gap-3">
            <CheckCircle2 size={16} className="mt-1 shrink-0 text-blue-500" />
            <span>기록은 가능한 한 마스킹과 상태 관리 흐름을 거쳐 처리합니다.</span>
          </li>
        </ul>
      </LegalSection>

      <LegalSection title="보관과 삭제" icon={<Trash2 size={20} />}>
        <p>
          계정 삭제 요청, 서비스 종료, 또는 보관 목적이 끝난 경우에는 관련 법령과 운영 정책에 따라 필요한 범위만 남기고 나머지 정보는 정리합니다.
        </p>
      </LegalSection>
    </LegalShell>
  );
}

export function RefundPolicy() {
  return (
    <LegalShell
      eyebrow="Billing Policy"
      title="환불 정책"
      description="서비스 결제 및 환불에 대한 명확한 기준을 안내합니다."
    >
      <LegalSection title="결제 및 환불 기준" icon={<Scale size={20} />}>
        <ul className="space-y-3">
          <li className="flex items-start gap-3">
            <CheckCircle2 size={16} className="mt-1 shrink-0 text-blue-500" />
            <span>서비스 이용 내역이 없는 경우, 결제일로부터 7일 이내에 전액 환불이 가능합니다.</span>
          </li>
          <li className="flex items-start gap-3">
            <CheckCircle2 size={16} className="mt-1 shrink-0 text-blue-500" />
            <span>AI 진단, 분석 등 핵심 서비스 이용 후에는 원칙적으로 환불이 불가능합니다. 단, 시스템 오류로 인한 미제공 시에는 전액 환불됩니다.</span>
          </li>
        </ul>
      </LegalSection>
    </LegalShell>
  );
}

export function CookiesPolicy() {
  return (
    <LegalShell
      eyebrow="Data Collection Policy"
      title="쿠키 및 자동수집정보 안내"
      description="웹사이트 이용 경험 향상을 위해 쿠키 및 자동 수집되는 정보에 대해 안내합니다."
    >
      <LegalSection title="수집되는 정보 및 목적" icon={<Info size={20} />}>
        <p>인증 상태 유지, 보안 설정, 사용자 이용 통계 분석(오류 확인 등)을 위해 쿠키와 접속 IP 등의 정보가 수집될 수 있습니다. 브라우저 설정을 통해 쿠키 저장을 거부할 수 있으나, 이 경우 자동 로그인 등 일부 기능 사용에 제한이 있을 수 있습니다.</p>
      </LegalSection>
    </LegalShell>
  );
}

export function MarketingPolicy() {
  return (
    <LegalShell
      eyebrow="Communication Policy"
      title="마케팅 정보 수신 안내"
      description="새로운 기능, 입시 정보 및 이벤트 등의 혜택 정보를 전달해 드립니다."
    >
      <LegalSection title="안내 사항" icon={<Mail size={20} />}>
        <p>마케팅 정보 수신에 동의하시면 이메일 등의 수단으로 유용한 정보를 받아보실 수 있습니다. 언제든 '설정' 페이지에서 수신 거부로 변경하실 수 있습니다.</p>
      </LegalSection>
    </LegalShell>
  );
}

export function YouthPolicy() {
  return (
    <LegalShell
      eyebrow="Youth Protection"
      title="청소년 보호 및 법정대리인 안내"
      description="만 14세 미만 사용자의 서비스 이용에 대한 보호 원칙을 안내합니다."
    >
      <LegalSection title="법정대리인 동의" icon={<ShieldCheck size={20} />}>
        <p>만 14세 미만의 아동이 서비스를 이용하고 개인정보를 제공할 경우, 반드시 법정대리인(부모님 등)의 동의가 필요합니다. 법정대리인은 언제든지 아동의 개인정보 조회, 수정, 삭제를 요청할 수 있습니다.</p>
      </LegalSection>
    </LegalShell>
  );
}

export function DataDeletionPolicy() {
  return (
    <LegalShell
      eyebrow="Data Control"
      title="개인정보 삭제 요청 안내"
      description="사용자 권리 보장을 위한 개인정보 삭제 절차를 안내합니다."
    >
      <LegalSection title="삭제 절차" icon={<Trash2 size={20} />}>
        <p>마이페이지 '설정' 메뉴 내의 [개인정보 삭제 요청] 기능을 통해 계정 및 연관 데이터를 삭제할 수 있습니다. 요청 즉시 처리 절차가 진행되며, 법률상 보관 의무가 있는 정보 외에는 지체 없이 영구 삭제됩니다.</p>
      </LegalSection>
    </LegalShell>
  );
}
