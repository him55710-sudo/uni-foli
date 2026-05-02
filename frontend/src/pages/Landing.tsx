import React from 'react';
import { Link } from 'react-router-dom';
import { motion } from 'motion/react';
import {
  ArrowRight,
  BookOpenCheck,
  Check,
  ClipboardCheck,
  FileSearch,
  MessageSquareText,
  ShieldCheck,
} from 'lucide-react';
import { useAuth } from '../contexts/AuthContext';

const workflowSteps = [
  {
    title: '생기부 업로드',
    copy: 'PDF를 올리면 학생명, 학교, 세특·진로·동아리 기록을 먼저 구조화합니다.',
  },
  {
    title: '근거 기반 진단',
    copy: '전공 연결 근거, 탐구 깊이, 기록 공백, 설명 가능성을 문장 단위로 확인합니다.',
  },
  {
    title: '보완 탐구 추천',
    copy: '부족한 근거를 채울 수 있는 세특·탐구 주제를 학생 수준에 맞게 제안합니다.',
  },
  {
    title: '보고서·면접 실행',
    copy: '선택한 주제를 워크숍에서 보고서 초안, 면접 질문, 후속 탐구로 이어갑니다.',
  },
];

const pricingPlans = [
  {
    name: 'Free',
    price: '0원',
    description: '처음 방향을 확인하는 체험 진단',
    outputs: ['샘플 진단 흐름', '생기부 요약', '대표 강점 2개', '기본 탐구 아이디어'],
    cta: '무료로 시작',
    href: '/auth',
  },
  {
    name: 'Pro',
    price: '23,900원',
    description: '생기부를 실제 보완 계획으로 바꾸는 리포트',
    outputs: ['7쪽 진단 리포트', '핵심 세특 분석', '전공 연결망', '추천 탐구 주제 8개', '보완 액션 플랜'],
    cta: 'Pro로 진단',
    href: '/auth',
    featured: true,
  },
  {
    name: 'Ultra',
    price: '49,900원',
    description: '진단 이후 보고서와 면접까지 이어가는 실행 패키지',
    outputs: ['Pro 전체 포함', '면접 질문 20개', '보고서 개요·초안', '학년별 후속 탐구 설계', '워크숍 저장·재작업'],
    cta: 'Ultra로 실행',
    href: '/auth',
  },
];

export function Landing() {
  const { isAuthenticated } = useAuth();
  const startHref = isAuthenticated ? '/app/diagnosis' : '/auth';

  return (
    <div className="bg-[#f8fafc] text-slate-950">
      <section className="border-b border-slate-200 bg-white">
        <div className="mx-auto grid min-h-[calc(88vh-72px)] max-w-7xl items-center gap-12 px-5 py-16 lg:grid-cols-[0.92fr_1.08fr] lg:px-8">
          <motion.div
            initial={{ opacity: 0, y: 18 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.45 }}
            className="max-w-3xl"
          >
            <div className="mb-6 inline-flex items-center gap-2 rounded-full border border-slate-200 bg-slate-50 px-4 py-2 text-xs font-black text-slate-700">
              <ShieldCheck size={15} className="text-emerald-600" />
              합격 가능성이 아니라 기록의 근거와 보완 방향을 진단합니다
            </div>
            <h1 className="text-4xl font-black leading-[1.08] tracking-tight sm:text-6xl">
              생기부를 읽고,
              <span className="block text-indigo-600">보완할 탐구까지 이어줍니다</span>
            </h1>
            <p className="mt-6 max-w-2xl text-lg font-semibold leading-8 text-slate-600">
              Uni Foli는 업로드한 학생 기록을 기준으로 전공 연결성, 세특 흐름, 탐구 깊이, 면접 리스크를 분석하고
              다음 보고서와 후속 세특 준비로 연결하는 AI 입시 진단 플랫폼입니다.
            </p>
            <div className="mt-8 flex flex-wrap gap-3">
              <Link
                to={startHref}
                className="inline-flex items-center gap-2 rounded-2xl bg-indigo-600 px-6 py-4 text-base font-black text-white shadow-lg shadow-indigo-100 transition hover:bg-indigo-700"
              >
                생기부 진단 시작
                <ArrowRight size={18} />
              </Link>
              <Link
                to="/help/student-record-pdf"
                className="inline-flex items-center gap-2 rounded-2xl border border-slate-200 bg-white px-6 py-4 text-base font-black text-slate-700 transition hover:bg-slate-50"
              >
                PDF 준비 방법
              </Link>
            </div>
          </motion.div>

          <motion.div
            initial={{ opacity: 0, y: 20, scale: 0.98 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            transition={{ duration: 0.55, delay: 0.1 }}
          >
            <EvidenceReportPreview />
          </motion.div>
        </div>
      </section>

      <WorkflowSection />

      <section className="border-y border-slate-200 bg-white">
        <div className="mx-auto grid max-w-7xl gap-10 px-5 py-16 lg:grid-cols-[0.9fr_1.1fr] lg:px-8">
          <div>
            <p className="text-sm font-black uppercase tracking-[0.18em] text-indigo-600">Evidence first</p>
            <h2 className="mt-3 text-3xl font-black tracking-tight sm:text-4xl">
              점수보다 먼저 보여줘야 할 것은 판단 근거입니다
            </h2>
            <p className="mt-5 text-base font-semibold leading-8 text-slate-600">
              모든 판단은 학생부 문장, 근거 강도, 부족한 근거, 다음 행동으로 이어집니다.
              점수는 합격 가능성이 아니라 기록의 완성도와 설명 가능성을 보는 참고 지표로만 사용합니다.
            </p>
          </div>
          <div className="space-y-3 rounded-[28px] border border-slate-200 bg-slate-50 p-5">
            <EvidenceRow label="판단" value="전공 연결 근거는 충분하지만 탐구 심화 근거가 부족합니다." />
            <EvidenceRow label="근거" value="2학년 물리 세특, 진로활동, 건축 관련 탐구 기록" />
            <EvidenceRow label="신뢰도" value="중간: 수학적 모델링 기록은 추가 확인이 필요합니다." />
            <EvidenceRow label="다음 행동" value="구조역학 또는 환경공학 연결 탐구 1개를 보고서로 보완" />
          </div>
        </div>
      </section>

      <section id="pricing" className="mx-auto max-w-7xl px-5 py-20 lg:px-8">
        <div className="mx-auto max-w-3xl text-center">
          <p className="text-sm font-black uppercase tracking-[0.18em] text-indigo-600">Pricing by outputs</p>
          <h2 className="mt-3 text-3xl font-black tracking-tight sm:text-4xl">결제하면 받는 결과물이 보여야 합니다</h2>
          <p className="mt-4 text-base font-semibold leading-7 text-slate-600">
            기능 이름보다 진단서, 세특 분석, 탐구 주제, 면접 질문, 보고서 초안 같은 산출물을 기준으로 나눴습니다.
          </p>
        </div>
        <PricingSection />
      </section>
    </div>
  );
}

function EvidenceReportPreview() {
  return (
    <div className="mx-auto max-w-[620px] rounded-[32px] border border-slate-200 bg-white p-5 shadow-[0_30px_80px_-36px_rgba(15,23,42,0.35)]">
      <div className="rounded-[24px] bg-slate-950 p-5 text-white">
        <div className="flex items-start justify-between gap-4">
          <div>
            <p className="text-xs font-black uppercase tracking-[0.18em] text-indigo-200">Diagnosis report</p>
            <h2 className="mt-2 text-2xl font-black">진단 → 보완 → 실행</h2>
          </div>
          <FileSearch className="text-indigo-200" size={28} />
        </div>
        <div className="mt-6 grid gap-3">
          {[
            ['전공 연결성', '근거 충분', 'bg-emerald-400'],
            ['탐구 심화', '보완 필요', 'bg-amber-300'],
            ['면접 설명력', '질문 대비', 'bg-sky-300'],
          ].map(([label, value, color]) => (
            <div key={label} className="rounded-2xl bg-white/8 p-4">
              <div className="flex items-center justify-between text-sm font-black">
                <span>{label}</span>
                <span>{value}</span>
              </div>
              <div className="mt-3 h-2 rounded-full bg-white/12">
                <div className={cn('h-2 rounded-full', color)} style={{ width: label === '탐구 심화' ? '54%' : '78%' }} />
              </div>
            </div>
          ))}
        </div>
      </div>
      <div className="mt-5 space-y-3">
        <PreviewLine icon={ClipboardCheck} title="핵심 약점" copy="수학적 모델링 근거가 부족해 탐구 깊이 설명이 약합니다." />
        <PreviewLine icon={BookOpenCheck} title="보완 주제" copy="하중 분산을 함수 모델로 해석하는 구조역학 탐구" />
        <PreviewLine icon={MessageSquareText} title="실행" copy="워크숍에서 보고서 초안과 면접 질문으로 이어 작업" />
      </div>
    </div>
  );
}

function WorkflowSection() {
  return (
    <section className="mx-auto max-w-7xl px-5 py-16 lg:px-8">
      <div className="mb-8 flex flex-col justify-between gap-4 lg:flex-row lg:items-end">
        <div>
          <p className="text-sm font-black uppercase tracking-[0.18em] text-indigo-600">Core workflow</p>
          <h2 className="mt-3 text-3xl font-black tracking-tight sm:text-4xl">하나의 흐름만 강하게 밀어갑니다</h2>
        </div>
        <p className="max-w-xl text-sm font-semibold leading-6 text-slate-600">
          목표 학과가 있으면 그 기준으로, 아직 없으면 생기부를 먼저 읽어 어울리는 전공군과 탐구 방향을 찾습니다.
        </p>
      </div>
      <div className="grid gap-4 md:grid-cols-4">
        {workflowSteps.map((step, index) => (
          <div key={step.title} className="rounded-[24px] border border-slate-200 bg-white p-5">
            <div className="flex h-9 w-9 items-center justify-center rounded-2xl bg-indigo-50 text-sm font-black text-indigo-700">
              {index + 1}
            </div>
            <h3 className="mt-5 text-lg font-black text-slate-950">{step.title}</h3>
            <p className="mt-3 text-sm font-semibold leading-6 text-slate-600">{step.copy}</p>
          </div>
        ))}
      </div>
    </section>
  );
}

function EvidenceRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-2xl border border-slate-200 bg-white p-4">
      <p className="text-xs font-black text-slate-400">{label}</p>
      <p className="mt-1 text-sm font-bold leading-6 text-slate-800">{value}</p>
    </div>
  );
}

function PreviewLine({
  icon: Icon,
  title,
  copy,
}: {
  icon: React.ComponentType<{ size?: number; className?: string }>;
  title: string;
  copy: string;
}) {
  return (
    <div className="flex gap-3 rounded-2xl border border-slate-200 bg-slate-50 p-4">
      <Icon size={19} className="mt-0.5 text-indigo-600" />
      <div>
        <p className="text-sm font-black text-slate-950">{title}</p>
        <p className="mt-1 text-sm font-semibold leading-5 text-slate-600">{copy}</p>
      </div>
    </div>
  );
}

function PricingSection() {
  const { isAuthenticated } = useAuth();

  return (
    <div className="mt-10 grid gap-5 lg:grid-cols-3">
      {pricingPlans.map((plan) => (
        <motion.div
          key={plan.name}
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.35 }}
          className={cn(
            'flex flex-col rounded-[28px] border bg-white p-6',
            plan.featured ? 'border-indigo-500 shadow-xl shadow-indigo-100' : 'border-slate-200',
          )}
        >
          {plan.featured && (
            <span className="mb-4 inline-flex w-fit rounded-full bg-indigo-600 px-3 py-1 text-xs font-black text-white">
              가장 명확한 진단
            </span>
          )}
          <h3 className="text-2xl font-black text-slate-950">{plan.name}</h3>
          <p className="mt-2 text-sm font-semibold leading-6 text-slate-600">{plan.description}</p>
          <p className="mt-7 text-4xl font-black tracking-tight text-slate-950">{plan.price}</p>
          <ul className="mt-7 flex-1 space-y-3">
            {plan.outputs.map((output) => (
              <li key={output} className="flex gap-3 text-sm font-bold leading-6 text-slate-700">
                <Check size={17} className="mt-1 shrink-0 text-emerald-600" />
                {output}
              </li>
            ))}
          </ul>
          <Link
            to={isAuthenticated ? '/app/diagnosis' : plan.href}
            className={cn(
              'mt-8 inline-flex items-center justify-center gap-2 rounded-2xl px-5 py-3 text-sm font-black transition',
              plan.featured ? 'bg-indigo-600 text-white hover:bg-indigo-700' : 'bg-slate-100 text-slate-800 hover:bg-slate-200',
            )}
          >
            {plan.cta}
            <ArrowRight size={16} />
          </Link>
        </motion.div>
      ))}
    </div>
  );
}

const cn = (...classes: Array<string | false | null | undefined>) => classes.filter(Boolean).join(' ');
