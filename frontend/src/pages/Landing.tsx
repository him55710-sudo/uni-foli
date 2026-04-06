import React from 'react';
import { Link } from 'react-router-dom';
import { motion } from 'motion/react';
import {
  ArrowRight,
  BookOpen,
  CheckCircle2,
  Compass,
  FileSearch,
  PenTool,
  Rocket,
  ShieldCheck,
  Sparkles,
  Target,
  Zap,
} from 'lucide-react';
import { FaqAccordion } from '../components/FaqAccordion';
import { faqPreviewItems } from '../content/faq';
import { useAuth } from '../contexts/AuthContext';
import { buttonClassName } from '../components/ui';
import { cn } from '../lib/cn';

const workflowItems = [
  {
    title: '1. 목표 세팅',
    description: '대학과 전공 목표를 먼저 고정해 AI 진단 기준을 명확히 맞춥니다.',
    icon: Target,
  },
  {
    title: '2. 학생부 업로드',
    description: 'PDF를 올리면 핵심 근거를 추출하고 과장 가능 문장을 먼저 걸러냅니다.',
    icon: FileSearch,
  },
  {
    title: '3. 진단 결과 확인',
    description: '강점·보완점·다음 액션을 근거와 함께 바로 확인할 수 있습니다.',
    icon: Compass,
  },
  {
    title: '4. 문서 초안 작성',
    description: '진단 결과를 문서 흐름으로 연결해 실제 제출 가능한 초안으로 이어집니다.',
    icon: PenTool,
  },
];

const trustPoints = [
  '근거 없는 문장은 자동으로 경고해요.',
  '합격 보장 표현 대신 다음 행동을 제시해요.',
  '학생 기록 범위를 넘어선 과장 작성을 막아요.',
];

const pricingPlans = [
  {
    name: 'Free',
    badge: '기본',
    monthlyPrice: '₩0',
    originalPrice: null,
    description: '서비스를 처음 경험해 보는 학생을 위한 시작 플랜',
    highlights: ['진단 체험', '게스트 미리보기', '문의 채널 이용'],
    cta: '무료로 시작',
    href: '/auth',
    featured: false,
  },
  {
    name: 'Plus',
    badge: '추천',
    monthlyPrice: '₩5,900',
    originalPrice: '정가 예정 ₩9,900',
    description: '준비 루틴을 꾸준히 이어가고 싶은 학생용 플랜',
    highlights: ['심화 진단', '진행 기록 관리', '우선 문의 지원'],
    cta: 'Plus 시작',
    href: '/auth?plan=plus',
    featured: true,
  },
  {
    name: 'Pro',
    badge: '고급',
    monthlyPrice: '₩9,900',
    originalPrice: '정가 예정 ₩15,900',
    description: '장기 준비와 정교한 관리가 필요한 학생용 플랜',
    highlights: ['고급 분석 흐름', '확장 문서 워크플로우', '전용 안내 채널'],
    cta: 'Pro 시작',
    href: '/auth?plan=pro',
    featured: false,
  },
];

export function Landing() {
  const { isAuthenticated } = useAuth();
  const startHref = isAuthenticated ? '/app' : '/auth';

  const scrollToTop = () => {
    window.scrollTo({ top: 0, left: 0, behavior: 'auto' });
  };

  return (
    <div className="bg-slate-950 text-slate-100">
      <section className="relative overflow-hidden border-b border-slate-800">
        <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_18%_22%,rgba(37,99,235,0.4),transparent_40%),radial-gradient(circle_at_82%_18%,rgba(14,165,233,0.3),transparent_36%),linear-gradient(180deg,#020617_0%,#0f172a_52%,#020617_100%)]" />
        <div className="pointer-events-none absolute -left-28 top-24 h-72 w-72 rounded-full border border-blue-400/20" />
        <div className="pointer-events-none absolute -right-24 bottom-10 h-64 w-64 rounded-full border border-cyan-300/20" />

        <div className="relative mx-auto max-w-7xl px-4 pb-14 pt-14 sm:px-6 sm:pb-16 lg:px-8 lg:pt-20">
          <motion.div
            initial={{ opacity: 0, y: 24 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.45 }}
            className="grid gap-10 lg:grid-cols-[1.1fr_0.9fr]"
          >
            <div>
              <p className="inline-flex items-center gap-2 rounded-full border border-blue-300/40 bg-blue-400/10 px-4 py-2 text-xs font-black uppercase tracking-[0.16em] text-blue-200">
                <Sparkles size={14} />
                Evidence First Workflow
              </p>
              <h1 className="mt-6 max-w-3xl text-4xl font-black leading-tight tracking-tight text-white sm:text-5xl lg:text-6xl">
                막막한 입시 준비를
                <span className="block bg-gradient-to-r from-blue-300 via-cyan-300 to-sky-400 bg-clip-text text-transparent">근거 중심 실행 플랜</span>
                으로 바꿔줍니다
              </h1>
              <p className="mt-6 max-w-2xl text-base font-medium leading-8 text-slate-300 sm:text-lg">
                목표 설정부터 학생부 분석, 진단 결과, 문서 초안까지. 한 화면에서 바로 이어지는 흐름으로
                불안한 준비 과정을 실행 가능한 단계로 정리합니다.
              </p>

              <div className="mt-8 flex flex-wrap gap-3">
                <Link
                  to={startHref}
                  onClick={scrollToTop}
                  className={cn(buttonClassName({ variant: 'primary', size: 'lg' }), 'rounded-2xl px-8 shadow-xl shadow-blue-900/40')}
                >
                  <Rocket size={18} />
                  지금 시작하기
                </Link>
                <Link
                  to="/contact"
                  onClick={scrollToTop}
                  className={cn(
                    buttonClassName({ variant: 'ghost', size: 'lg' }),
                    'rounded-2xl border border-white/20 px-8 text-white hover:bg-white/10',
                  )}
                >
                  문의하기
                </Link>
              </div>

              <div className="mt-8 grid max-w-3xl gap-3 sm:grid-cols-3">
                {[
                  { label: '진단 흐름', value: '4 STEP', icon: Zap },
                  { label: '파일 업로드', value: 'PDF 지원', icon: FileSearch },
                  { label: '결과 연결', value: '문서 초안', icon: BookOpen },
                ].map(item => (
                  <div key={item.label} className="rounded-2xl border border-slate-700/80 bg-slate-900/70 p-4 backdrop-blur">
                    <p className="inline-flex items-center gap-2 text-xs font-black uppercase tracking-[0.14em] text-slate-400">
                      <item.icon size={14} />
                      {item.label}
                    </p>
                    <p className="mt-2 text-xl font-black text-white">{item.value}</p>
                  </div>
                ))}
              </div>
            </div>

            <div className="rounded-3xl border border-slate-700 bg-slate-900/80 p-6 shadow-[0_24px_80px_rgba(2,6,23,0.55)] backdrop-blur sm:p-7">
              <p className="text-xs font-black uppercase tracking-[0.16em] text-cyan-300">실행 프리뷰</p>
              <h2 className="mt-3 text-2xl font-black tracking-tight text-white">오늘 해야 할 일만 선명하게</h2>
              <p className="mt-2 text-sm font-medium leading-7 text-slate-300">
                합격을 보장하는 과장 대신, 현재 기록에서 가능한 다음 액션을 우선순위로 제안합니다.
              </p>

              <div className="mt-6 space-y-3">
                {[
                  '학생부에서 근거 추출 완료',
                  '강점/보완점 진단 결과 생성',
                  '다음 행동 3개 자동 제안',
                  '초안 작성 워크플로우 연결',
                ].map((line, idx) => (
                  <div key={line} className="flex items-center gap-3 rounded-2xl border border-slate-700 bg-slate-950/70 px-4 py-3">
                    <span className="inline-flex h-6 w-6 items-center justify-center rounded-full bg-blue-500 text-xs font-black text-white">
                      {idx + 1}
                    </span>
                    <span className="text-sm font-semibold text-slate-200">{line}</span>
                  </div>
                ))}
              </div>

              <div className="mt-6 rounded-2xl border border-emerald-400/30 bg-emerald-500/10 p-4">
                <p className="inline-flex items-center gap-2 text-sm font-black text-emerald-200">
                  <ShieldCheck size={16} />
                  안전 가이드
                </p>
                <p className="mt-2 text-sm font-medium leading-6 text-emerald-100">
                  근거가 약한 영역은 "추정"으로 분리하고, 다음에 보완할 기록 포인트를 함께 안내합니다.
                </p>
              </div>
            </div>
          </motion.div>
        </div>
      </section>

      <section className="mx-auto max-w-7xl px-4 py-12 sm:px-6 sm:py-16 lg:px-8">
        <div className="grid gap-4 lg:grid-cols-4">
          {workflowItems.map(item => (
            <article key={item.title} className="rounded-2xl border border-slate-800 bg-slate-900/70 p-5 shadow-lg shadow-slate-950/30 sm:p-6">
              <p className="inline-flex items-center gap-2 text-sm font-black text-blue-300">
                <item.icon size={15} />
                {item.title}
              </p>
              <p className="mt-3 text-sm font-medium leading-6 text-slate-300 break-keep">{item.description}</p>
            </article>
          ))}
        </div>
      </section>

      <section className="border-y border-slate-800 bg-slate-900/70">
        <div className="mx-auto grid max-w-7xl gap-10 px-4 py-12 sm:px-6 sm:py-14 lg:grid-cols-2 lg:px-8">
          <div>
            <p className="text-xs font-black uppercase tracking-[0.16em] text-slate-400">핵심 가치</p>
            <h2 className="mt-3 text-3xl font-black tracking-tight text-white">안전하게, 그러나 빠르게</h2>
            <p className="mt-4 text-sm font-medium leading-7 text-slate-300 sm:text-base">
              Uni Folia는 그럴듯한 문장을 만드는 도구가 아니라, 실제 기록 기반으로 다음 행동을 좁혀주는 실행 도구입니다.
            </p>
            <div className="mt-6 space-y-3">
              {trustPoints.map(point => (
                <div key={point} className="flex items-start gap-3 rounded-2xl border border-slate-700 bg-slate-950/70 p-4">
                  <CheckCircle2 size={16} className="mt-1 text-emerald-400" />
                  <p className="text-sm font-semibold leading-6 text-slate-200 break-keep">{point}</p>
                </div>
              ))}
            </div>
          </div>

          <div className="rounded-3xl border border-blue-400/30 bg-gradient-to-br from-blue-500/15 via-slate-900 to-cyan-500/10 p-6 sm:p-8">
            <p className="text-xs font-black uppercase tracking-[0.16em] text-blue-200">Outcome</p>
            <h3 className="mt-3 text-2xl font-black tracking-tight text-white">진단에서 작성까지 끊기지 않는 흐름</h3>
            <ul className="mt-5 space-y-3">
              {[
                '근거-문장 매핑으로 결과 신뢰도 확보',
                '부족한 포인트를 즉시 보완 액션으로 전환',
                '워크숍/에디터로 바로 이어지는 작성 동선',
              ].map(item => (
                <li key={item} className="rounded-2xl border border-blue-300/20 bg-slate-950/60 px-4 py-3 text-sm font-semibold text-slate-100">
                  {item}
                </li>
              ))}
            </ul>
          </div>
        </div>
      </section>

      <section className="mx-auto max-w-7xl px-4 py-12 sm:px-6 sm:py-16 lg:px-8">
        <div className="rounded-[32px] border border-amber-300/30 bg-gradient-to-br from-amber-500/15 via-slate-900 to-orange-500/10 p-6 sm:p-8">
          <div className="flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
            <div>
              <p className="inline-flex items-center gap-2 text-xs font-black uppercase tracking-[0.16em] text-amber-200">
                <Sparkles size={14} />
                출시 기념 요금
              </p>
              <h2 className="mt-2 text-2xl font-black tracking-tight text-white sm:text-3xl">요금제 안내</h2>
              <p className="mt-2 text-sm font-medium text-slate-300 break-keep">정식 오픈 전 가격으로 먼저 시작할 수 있어요.</p>
            </div>
            <p className="text-xs font-bold text-amber-100">월 결제 기준 · VAT 포함</p>
          </div>

          <div className="mt-6 grid gap-4 lg:grid-cols-3">
            {pricingPlans.map(plan => (
              <article
                key={plan.name}
                className={cn(
                  'rounded-2xl border bg-slate-950/70 p-5 shadow-lg shadow-slate-950/40 sm:p-6',
                  plan.featured ? 'border-blue-300/60' : 'border-slate-700',
                )}
              >
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <p className="text-xs font-black uppercase tracking-[0.16em] text-slate-400">{plan.name}</p>
                    <p className="mt-2 text-3xl font-black tracking-tight text-white">{plan.monthlyPrice}</p>
                    {plan.originalPrice ? (
                      <p className="mt-1 text-xs font-bold text-rose-300 line-through">{plan.originalPrice}</p>
                    ) : (
                      <p className="mt-1 text-xs font-bold text-emerald-300">항상 무료</p>
                    )}
                  </div>
                  <span
                    className={cn(
                      'rounded-full px-3 py-1 text-xs font-black',
                      plan.featured ? 'bg-blue-500 text-white' : 'border border-slate-600 bg-slate-800 text-slate-200',
                    )}
                  >
                    {plan.badge}
                  </span>
                </div>

                <p className="mt-4 text-sm font-medium leading-6 text-slate-300 break-keep">{plan.description}</p>
                <ul className="mt-4 space-y-2">
                  {plan.highlights.map(highlight => (
                    <li key={highlight} className="flex items-start gap-2 text-sm font-semibold text-slate-200">
                      <CheckCircle2 size={15} className="mt-0.5 text-cyan-300" />
                      <span className="break-keep">{highlight}</span>
                    </li>
                  ))}
                </ul>

                <Link
                  to={plan.href}
                  onClick={scrollToTop}
                  className={cn(
                    buttonClassName({
                      variant: plan.featured ? 'primary' : 'secondary',
                      size: 'md',
                      fullWidth: true,
                    }),
                    'mt-6',
                  )}
                >
                  {plan.cta}
                  <ArrowRight size={16} />
                </Link>
              </article>
            ))}
          </div>
        </div>
      </section>

      <section className="mx-auto max-w-7xl px-4 py-12 sm:px-6 sm:py-16 lg:px-8">
        <div className="flex items-end justify-between gap-4">
          <div>
            <p className="text-xs font-black uppercase tracking-[0.16em] text-slate-400">FAQ</p>
            <h2 className="mt-2 text-2xl font-black tracking-tight text-white">자주 묻는 질문</h2>
          </div>
          <Link
            to="/faq"
            onClick={scrollToTop}
            className="inline-flex items-center gap-2 rounded-2xl border border-slate-700 bg-slate-900 px-4 py-2 text-sm font-bold text-slate-100"
          >
            전체 보기
            <ArrowRight size={14} />
          </Link>
        </div>
        <div className="mt-6">
          <FaqAccordion items={faqPreviewItems} initialOpenId={faqPreviewItems[0]?.id} compact />
        </div>
      </section>

      <section className="border-t border-slate-800 bg-slate-950">
        <div className="mx-auto max-w-7xl px-4 py-12 sm:px-6 sm:py-14 lg:px-8">
          <div className="rounded-2xl border border-slate-700 bg-gradient-to-r from-slate-900 via-slate-900 to-blue-950 p-6 text-center sm:p-8 lg:p-12">
            <p className="mx-auto text-xs font-black uppercase tracking-[0.16em] text-blue-300">Start Now</p>
            <h2 className="mx-auto mt-3 text-2xl font-black tracking-tight text-white sm:text-3xl break-keep">
              오늘의 준비를 실행 가능한 계획으로 바꿔보세요
            </h2>
            <p className="mx-auto mt-4 max-w-2xl text-sm font-medium leading-7 text-slate-300 break-keep">
              기록 업로드부터 진단, 문서 초안 연결까지 바로 시작할 수 있습니다.
            </p>
            <div className="mt-8 flex flex-wrap justify-center gap-4">
              <Link
                to={startHref}
                onClick={scrollToTop}
                className={cn(buttonClassName({ variant: 'primary', size: 'lg' }), 'rounded-2xl px-8 shadow-xl shadow-blue-900/50 sm:px-10')}
              >
                <BookOpen size={18} />
                준비 시작하기
              </Link>
              <Link
                to="/contact?type=partnership"
                onClick={scrollToTop}
                className={cn(
                  buttonClassName({ variant: 'ghost', size: 'lg' }),
                  'rounded-2xl border border-white/20 px-8 text-white hover:bg-white/10 sm:px-10',
                )}
              >
                제휴 문의
              </Link>
            </div>
          </div>
        </div>
      </section>
    </div>
  );
}
