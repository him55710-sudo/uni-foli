import React from 'react';
import { Link } from 'react-router-dom';
import { motion } from 'motion/react';
import {
  ArrowRight,
  BarChart3,
  Check,
  ClipboardCheck,
  Compass,
  FileSearch,
  Layers3,
  PieChart,
  Rocket,
  ShieldCheck,
  Sparkles,
  Target,
  TrendingUp,
} from 'lucide-react';
import { useAuth } from '../contexts/AuthContext';

const quickMajors = ['건축공학', '컴퓨터공학', '바이오', '경영', '사회과학', '디자인'];

const quickFeatures = [
  {
    title: 'PDF 진단',
    subtitle: '생기부 업로드 후 전공 적합성, 탐구 흐름, 리스크를 자동 분석합니다.',
    icon: FileSearch,
    href: '/app/diagnosis',
  },
  {
    title: '전공 탐색',
    subtitle: '내 기록과 맞는 학과 흐름을 비교하고 다음 탐구 방향을 찾습니다.',
    icon: Compass,
    href: '/app/trends',
  },
  {
    title: '보고서 작성',
    subtitle: '분석 결과를 바탕으로 유의미한 탐구 보고서 초안을 만듭니다.',
    icon: Layers3,
    href: '/app/workshop',
  },
  {
    title: '전략 정리',
    subtitle: '면접 질문, 30일 액션 플랜, 보완 체크리스트까지 이어집니다.',
    icon: Target,
    href: '/app/workshop',
  },
];

const dashboardBars = [
  { label: '전공 적합성', mine: 88, major: 76, total: 69 },
  { label: '탐구 심화도', mine: 82, major: 71, total: 64 },
  { label: '학업 엄밀성', mine: 79, major: 70, total: 63 },
  { label: '서사 일관성', mine: 86, major: 73, total: 66 },
];

const proofCards = [
  { title: '핵심 강점', value: '5개', copy: '학년별 반복 근거와 전공 연결성을 묶어 정리' },
  { title: '리스크', value: '3개', copy: '면접에서 공격받을 수 있는 빈틈을 우선순위화' },
  { title: '액션 플랜', value: '30일', copy: '보고서, 면접, 후속 탐구를 실행 단위로 변환' },
];

export function Landing() {
  const { isAuthenticated } = useAuth();
  const startHref = isAuthenticated ? '/app/diagnosis' : '/auth';

  const scrollToTop = () => {
    window.scrollTo({ top: 0, left: 0, behavior: 'auto' });
  };

  return (
    <div className="bg-[#FAFAFA] text-[#111827] selection:bg-violet-100">
      <section className="relative overflow-hidden border-b border-[#E5E7EB] bg-white">
        <div className="absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-[#7C3AED] to-transparent" />
        <div className="mx-auto grid min-h-[calc(86vh-72px)] max-w-7xl items-center gap-12 px-4 py-12 sm:px-6 lg:grid-cols-[1.02fr_0.98fr] lg:px-8 lg:py-14">
          <motion.div
            initial={{ opacity: 0, y: 18 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5, ease: 'easeOut' }}
            className="space-y-8"
          >
            <div className="inline-flex items-center gap-2 rounded-full border border-[#DDD6FE] bg-[#F5F3FF] px-4 py-2 text-xs font-black text-[#5B21B6] shadow-sm">
              <Sparkles size={14} />
              최고의 온라인 입시컨설팅 | 업계 최저가 보장
            </div>

            <div className="space-y-5">
              <h1 className="max-w-3xl text-4xl font-black leading-[1.08] tracking-tight sm:text-6xl lg:text-7xl">
                최고의 온라인
                <span className="block text-[#7C3AED]">입시 컨설팅.</span>
              </h1>
              <p className="max-w-2xl text-base font-semibold leading-8 text-[#4B5563] sm:text-xl">
                오프라인 컨설팅의 1/10 가격으로 만나는 프리미엄 리포트.
                과목별 세특, 창체, 진로활동을 데이터로 분석하여 전공 적합성을 한눈에 보여줍니다.
              </p>
            </div>

            <div className="flex flex-wrap gap-3">
              <Link
                to={startHref}
                onClick={scrollToTop}
                className="group inline-flex items-center gap-2 rounded-2xl bg-[#7C3AED] px-7 py-4 text-base font-black text-white shadow-xl shadow-violet-200 transition hover:bg-[#5B21B6] active:scale-[0.98] sm:text-lg"
              >
                <Rocket size={20} />
                생기부 PDF 진단하기
                <ArrowRight size={18} className="transition-transform group-hover:translate-x-1" />
              </Link>
              <Link
                to="/app/trends"
                onClick={scrollToTop}
                className="inline-flex items-center gap-2 rounded-2xl border border-[#E5E7EB] bg-white px-7 py-4 text-base font-black text-[#374151] shadow-sm transition hover:border-[#C4B5FD] hover:bg-[#F5F3FF] sm:text-lg"
              >
                샘플 대시보드 보기
              </Link>
            </div>

            <div className="flex flex-wrap gap-2 pt-2">
              <p className="w-full text-xs font-black text-[#6B7280]">인기 전공 분석</p>
              {quickMajors.map((major) => (
                <span
                  key={major}
                  className="rounded-full border border-[#EDE9FE] bg-[#F5F3FF] px-3 py-1 text-xs font-black text-[#5B21B6]"
                >
                  #{major}
                </span>
              ))}
            </div>
          </motion.div>

          <motion.div
            initial={{ opacity: 0, scale: 0.96, y: 22 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            transition={{ duration: 0.65, delay: 0.12, ease: [0.16, 1, 0.3, 1] }}
          >
            <DashboardMockup />
          </motion.div>
        </div>
      </section>

      <section className="mx-auto max-w-7xl px-4 py-14 sm:px-6 lg:px-8">
        <div className="grid gap-5 md:grid-cols-2 xl:grid-cols-4">
          {quickFeatures.map((item, index) => (
            <motion.div
              key={item.title}
              initial={{ opacity: 0, y: 18 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ duration: 0.36, delay: index * 0.05 }}
            >
              <Link
                to={item.href}
                onClick={scrollToTop}
                className="group block h-full rounded-2xl border border-[#E5E7EB] bg-white p-6 shadow-sm transition hover:-translate-y-1 hover:border-[#C4B5FD] hover:shadow-xl hover:shadow-violet-100"
              >
                <div className="mb-6 inline-flex rounded-2xl bg-[#F5F3FF] p-3 text-[#7C3AED] ring-1 ring-[#EDE9FE]">
                  <item.icon size={23} />
                </div>
                <h3 className="text-lg font-black text-[#111827]">{item.title}</h3>
                <p className="mt-2 text-sm font-semibold leading-6 text-[#6B7280]">{item.subtitle}</p>
                <div className="mt-6 inline-flex items-center gap-1.5 text-sm font-black text-[#7C3AED]">
                  바로가기
                  <ArrowRight size={14} className="transition-transform group-hover:translate-x-1" />
                </div>
              </Link>
            </motion.div>
          ))}
        </div>
      </section>

      <section className="border-y border-[#E5E7EB] bg-white">
        <div className="mx-auto grid max-w-7xl gap-8 px-4 py-16 sm:px-6 lg:grid-cols-[0.9fr_1.1fr] lg:px-8">
          <div className="space-y-4">
            <div className="inline-flex rounded-full bg-[#EDE9FE] px-3 py-1 text-xs font-black text-[#5B21B6]">
              프리미엄 리포트 구조
            </div>
            <h2 className="text-3xl font-black tracking-tight text-[#111827] sm:text-4xl">
              AI가 쓴 긴 문장이 아니라,
              <span className="block text-[#7C3AED]">분석 JSON을 템플릿에 배치합니다.</span>
            </h2>
            <p className="text-base font-semibold leading-8 text-[#6B7280]">
              내부 근거 코드나 텍스트 그래프를 노출하지 않고, 고정된 카드와 차트에
              학생별 데이터를 자동 배치해 학부모가 바로 이해할 수 있게 만듭니다.
            </p>
          </div>
          <div className="grid gap-4 sm:grid-cols-3">
            {proofCards.map((card) => (
              <div key={card.title} className="rounded-2xl border border-[#E5E7EB] bg-[#FAFAFA] p-5">
                <p className="text-sm font-black text-[#6B7280]">{card.title}</p>
                <p className="mt-3 text-3xl font-black text-[#7C3AED]">{card.value}</p>
                <p className="mt-3 text-sm font-semibold leading-6 text-[#4B5563]">{card.copy}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section id="pricing" className="mx-auto max-w-7xl px-4 py-20 sm:px-6 lg:px-8">
        <PricingSection />
      </section>
    </div>
  );
}

function DashboardMockup() {
  return (
    <div className="mx-auto w-full max-w-[560px] rounded-[28px] border border-[#E5E7EB] bg-white p-4 shadow-[0_28px_70px_-28px_rgba(17,24,39,0.35)] sm:p-5">
      <div className="rounded-[22px] border border-[#EDE9FE] bg-[#F5F3FF] p-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <p className="text-xs font-black text-[#7C3AED]">PREMIUM DIAGNOSIS</p>
            <h2 className="mt-1 text-xl font-black text-[#111827]">AI 생기부 진단 대시보드</h2>
          </div>
          <span className="rounded-full bg-white px-3 py-1.5 text-xs font-black text-[#5B21B6] shadow-sm">
            상위 7.8%
          </span>
        </div>
      </div>

      <div className="mt-4 grid gap-4 lg:grid-cols-[0.9fr_1.1fr]">
        <div className="rounded-3xl border border-[#E5E7EB] bg-white p-5">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-xs font-black text-[#6B7280]">종합 점수</p>
              <p className="mt-1 text-3xl font-black text-[#111827]">347</p>
              <p className="text-xs font-black text-[#9CA3AF]">/ 400점</p>
            </div>
            <PieChart className="text-[#7C3AED]" size={24} />
          </div>
          <div className="relative mx-auto mt-5 flex h-36 w-36 items-center justify-center">
            <svg className="h-36 w-36 -rotate-90" viewBox="0 0 144 144">
              <circle cx="72" cy="72" r="58" fill="none" stroke="#EDE9FE" strokeWidth="14" />
              <motion.circle
                cx="72"
                cy="72"
                r="58"
                fill="none"
                stroke="#7C3AED"
                strokeWidth="14"
                strokeLinecap="round"
                strokeDasharray="364.4"
                initial={{ strokeDashoffset: 364.4 }}
                whileInView={{ strokeDashoffset: 48.3 }}
                viewport={{ once: true }}
                transition={{ duration: 1, delay: 0.2 }}
              />
            </svg>
            <div className="absolute text-center">
              <p className="text-2xl font-black text-[#111827]">86.8%</p>
              <p className="text-[11px] font-black text-[#6B7280]">전공 적합</p>
            </div>
          </div>
        </div>

        <div className="rounded-3xl border border-[#E5E7EB] bg-white p-5">
          <div className="mb-5 flex items-center justify-between">
            <div>
              <p className="text-xs font-black text-[#6B7280]">비교 분석</p>
              <h3 className="text-base font-black text-[#111827]">내 점수 vs 평균</h3>
            </div>
            <BarChart3 className="text-[#7C3AED]" size={22} />
          </div>

          <div className="space-y-4">
            {dashboardBars.map((item) => (
              <div key={item.label} className="space-y-2">
                <div className="flex items-center justify-between text-[11px] font-black">
                  <span className="text-[#374151]">{item.label}</span>
                  <span className="text-[#7C3AED]">{item.mine}점</span>
                </div>
                <CompareBars mine={item.mine} major={item.major} total={item.total} />
              </div>
            ))}
          </div>

          <div className="mt-5 grid grid-cols-3 gap-2 text-[10px] font-black text-[#6B7280]">
            <Legend color="bg-[#7C3AED]" label="내 점수" />
            <Legend color="bg-[#2563EB]" label="동일 전공" />
            <Legend color="bg-[#D1D5DB]" label="전체 평균" />
          </div>
        </div>
      </div>

      <div className="mt-4 grid gap-3 sm:grid-cols-3">
        <MiniMetric icon={TrendingUp} label="강점" value="전공 연결성" tone="purple" />
        <MiniMetric icon={ShieldCheck} label="리스크" value="근거 분산" tone="red" />
        <MiniMetric icon={ClipboardCheck} label="다음 액션" value="대표 탐구 3개" tone="blue" />
      </div>
    </div>
  );
}

function CompareBars({ mine, major, total }: { mine: number; major: number; total: number }) {
  const rows = [
    { value: mine, color: 'bg-[#7C3AED]' },
    { value: major, color: 'bg-[#2563EB]' },
    { value: total, color: 'bg-[#D1D5DB]' },
  ];

  return (
    <div className="space-y-1">
      {rows.map((row, index) => (
        <div key={index} className="h-2 overflow-hidden rounded-full bg-[#F3F4F6]">
          <motion.div
            initial={{ width: 0 }}
            whileInView={{ width: `${row.value}%` }}
            viewport={{ once: true }}
            transition={{ duration: 0.8, delay: index * 0.05 }}
            className={`h-full rounded-full ${row.color}`}
          />
        </div>
      ))}
    </div>
  );
}

function Legend({ color, label }: { color: string; label: string }) {
  return (
    <div className="flex items-center gap-1.5">
      <span className={`h-2 w-2 rounded-full ${color}`} />
      <span>{label}</span>
    </div>
  );
}

function MiniMetric({
  icon: Icon,
  label,
  value,
  tone,
}: {
  icon: React.ComponentType<{ size?: number; className?: string }>;
  label: string;
  value: string;
  tone: 'purple' | 'red' | 'blue';
}) {
  const toneClass = {
    purple: 'bg-[#F5F3FF] text-[#7C3AED] border-[#EDE9FE]',
    red: 'bg-red-50 text-[#EF4444] border-red-100',
    blue: 'bg-blue-50 text-[#2563EB] border-blue-100',
  }[tone];

  return (
    <div className={`rounded-2xl border p-4 ${toneClass}`}>
      <Icon size={18} />
      <p className="mt-3 text-[11px] font-black opacity-70">{label}</p>
      <p className="mt-1 text-sm font-black">{value}</p>
    </div>
  );
}

function PricingSection() {
  const [billingCycle, setBillingCycle] = React.useState<'monthly' | 'semester'>('semester');

  const plans = [
    {
      name: 'Free',
      description: 'AI 분석 흐름을 가볍게 체험',
      price: { monthly: 0, semester: 0 },
      features: ['샘플 리포트 열람', '생기부 간단 분석 1회', '기본 탐구 아이디어 추천', '문서 편집기 체험'],
      buttonText: '체험하기',
      highlight: false,
      dark: false,
    },
    {
      name: 'Pro',
      description: '본격적인 입시 전략 설계',
      price: { monthly: 5900, semester: 23900 },
      features: ['프리미엄 진단서 3회 제공', '워터마크 없는 PDF 다운로드', '과목별 세특 분석 카드', '추천 탐구 주제와 액션 플랜'],
      buttonText: 'Pro 시작하기',
      highlight: true,
      dark: false,
      popular: true,
      originalPrice: { semester: 35400 },
    },
    {
      name: 'Ultra',
      description: '면접과 보고서까지 연결',
      price: { monthly: 12900, semester: 49900 },
      features: ['프리미엄 진단 리포트 월간 업데이트', 'AI 모의 면접 질문 생성', '보고서 초안 자동 구성', '전공별 30일 로드맵'],
      buttonText: 'Ultra 시작하기',
      highlight: false,
      dark: true,
      originalPrice: { semester: 77400 },
    },
  ];

  return (
    <div className="space-y-10">
      <div className="mx-auto max-w-3xl text-center">
        <h2 className="text-3xl font-black tracking-tight text-[#111827] sm:text-4xl">
          업계 최저가로 누리는 <span className="text-[#7C3AED]">고퀄리티 컨설팅</span>
        </h2>
        <p className="mt-3 text-base font-semibold leading-7 text-[#6B7280]">
          오프라인 컨설팅의 거품을 걷어냈습니다. 
          PDF 진단부터 보고서, 면접 준비까지 가장 합리적인 가격으로 시작하세요.
        </p>
        <div className="mt-7 inline-flex rounded-2xl border border-[#E5E7EB] bg-white p-1 shadow-sm">
          <button
            onClick={() => setBillingCycle('monthly')}
            className={cn(
              'rounded-xl px-6 py-2 text-sm font-black transition',
              billingCycle === 'monthly' ? 'bg-[#F5F3FF] text-[#7C3AED]' : 'text-[#6B7280] hover:text-[#111827]',
            )}
          >
            월간 결제
          </button>
          <button
            onClick={() => setBillingCycle('semester')}
            className={cn(
              'rounded-xl px-6 py-2 text-sm font-black transition',
              billingCycle === 'semester' ? 'bg-[#F5F3FF] text-[#7C3AED]' : 'text-[#6B7280] hover:text-[#111827]',
            )}
          >
            학기 결제
          </button>
        </div>
      </div>

      <div className="grid gap-6 lg:grid-cols-3">
        {plans.map((plan, index) => (
          <motion.div
            key={plan.name}
            initial={{ opacity: 0, y: 24 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ duration: 0.4, delay: index * 0.06 }}
            className={cn(
              'relative flex flex-col rounded-3xl p-7 transition hover:-translate-y-1',
              plan.dark
                ? 'bg-[#111827] text-white shadow-2xl shadow-violet-200'
                : 'border border-[#E5E7EB] bg-white shadow-sm hover:shadow-xl hover:shadow-violet-100',
              plan.highlight && 'ring-2 ring-[#7C3AED] ring-offset-4',
            )}
          >
            {plan.popular && (
              <div className="absolute left-1/2 top-0 -translate-x-1/2 -translate-y-1/2">
                <span className="rounded-full bg-[#7C3AED] px-5 py-2 text-[10px] font-black tracking-widest text-white shadow-lg">
                  RECOMMENDED
                </span>
              </div>
            )}

            <div>
              <h3 className={cn('text-2xl font-black', plan.dark ? 'text-white' : 'text-[#111827]')}>{plan.name}</h3>
              <p className={cn('mt-2 text-sm font-semibold leading-6', plan.dark ? 'text-slate-300' : 'text-[#6B7280]')}>
                {plan.description}
              </p>
            </div>

            <div className="my-9">
              <div className="h-5">
                {billingCycle === 'semester' && plan.originalPrice && (
                  <span className="text-sm font-bold text-[#9CA3AF] line-through">
                    {plan.originalPrice.semester.toLocaleString()}원
                  </span>
                )}
              </div>
              <div className="flex items-baseline gap-1">
                <span className="text-4xl font-black tracking-tight">{plan.price[billingCycle].toLocaleString()}원</span>
                <span className={cn('text-sm font-black', plan.dark ? 'text-slate-400' : 'text-[#9CA3AF]')}>
                  /{billingCycle === 'monthly' ? '월' : '학기'}
                </span>
              </div>
            </div>

            <ul className="mb-9 flex-1 space-y-4">
              {plan.features.map((feature) => (
                <li key={feature} className="flex items-start gap-3">
                  <span
                    className={cn(
                      'mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full',
                      plan.dark ? 'bg-[#7C3AED]/20 text-[#C4B5FD]' : 'bg-[#F5F3FF] text-[#7C3AED]',
                    )}
                  >
                    <Check size={12} strokeWidth={4} />
                  </span>
                  <span className={cn('text-sm font-semibold leading-6', plan.dark ? 'text-slate-200' : 'text-[#374151]')}>
                    {feature}
                  </span>
                </li>
              ))}
            </ul>

            <button
              className={cn(
                'w-full rounded-2xl py-4 text-base font-black transition active:scale-[0.98]',
                plan.dark
                  ? 'bg-[#7C3AED] text-white hover:bg-[#8B5CF6]'
                  : plan.highlight
                    ? 'bg-[#7C3AED] text-white hover:bg-[#5B21B6]'
                    : 'bg-[#F5F3FF] text-[#5B21B6] hover:bg-[#EDE9FE]',
              )}
            >
              {plan.buttonText}
            </button>
          </motion.div>
        ))}
      </div>
    </div>
  );
}

const cn = (...classes: Array<string | false | undefined>) => classes.filter(Boolean).join(' ');
