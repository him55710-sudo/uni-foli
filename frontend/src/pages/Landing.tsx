import React from 'react';
import { Link } from 'react-router-dom';
import {
  ArrowRight,
  BookOpen,
  CheckCircle2,
  FileSearch,
  PenTool,
  ShieldCheck,
  Sparkles,
  Target,
} from 'lucide-react';
import { FaqAccordion } from '../components/FaqAccordion';
import { faqPreviewItems } from '../content/faq';
import { useAuth } from '../contexts/AuthContext';
import { buttonClassName } from '../components/ui';
import { cn } from '../lib/cn';

const workflowItems = [
  {
    title: '1. 목표 정하기',
    description: '희망 대학/학과를 먼저 정리해서 준비 방향을 명확히 만들어요.',
  },
  {
    title: '2. 학생부 올리기',
    description: 'PDF를 올리면 개인정보 보호 처리와 내용 분석이 자동으로 진행돼요.',
  },
  {
    title: '3. 진단 확인',
    description: '강점, 보완점, 다음 행동을 근거와 함께 한눈에 확인해요.',
  },
  {
    title: '4. 문서 작성',
    description: '진단 결과를 바탕으로 문서 초안을 만들고 다듬어요.',
  },
];

const trustPoints = [
  '학생 활동 흐름을 끊지 않도록 설계했어요.',
  '근거 없는 문장은 자동으로 걸러요.',
  '확인이 필요한 항목은 분명하게 표시해요.',
];

const pricingPlans = [
  {
    name: 'Free',
    badge: '기본',
    monthlyPrice: '0원',
    originalPrice: null,
    description: '처음 써보는 학생에게 맞는 기본 플랜',
    highlights: ['기본 진단 체험', 'FAQ/문의 허브 이용', '게스트 모드 지원'],
    cta: '무료로 시작',
    href: '/auth',
    featured: false,
  },
  {
    name: 'Plus',
    badge: '인기',
    monthlyPrice: '5,900원',
    originalPrice: '정가 예정 9,900원',
    description: '준비를 꾸준히 이어가고 싶은 학생용 플랜',
    highlights: ['심화 진단 제공', '작성 기록 관리', '우선 문의 답변'],
    cta: '플러스 시작',
    href: '/auth?plan=plus',
    featured: true,
  },
  {
    name: 'Pro',
    badge: '고급',
    monthlyPrice: '9,900원',
    originalPrice: '정가 예정 15,900원',
    description: '장기 준비와 정교한 관리가 필요한 학생용 플랜',
    highlights: ['고급 분석 흐름', '확장 작성 도구', '개별 안내 채널'],
    cta: '프로 시작',
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
    <div className="bg-slate-50">
      <section className="border-b border-slate-200 bg-white">
        <div className="mx-auto max-w-7xl px-4 py-12 text-center sm:px-6 sm:py-16 lg:px-8 lg:py-20">
          <p className="mx-auto text-xs font-bold uppercase tracking-[0.18em] text-blue-600">학생부 기반 준비 도구</p>
          <h1 className="mx-auto mt-4 max-w-4xl text-3xl font-extrabold tracking-tight text-slate-900 sm:text-4xl lg:text-5xl break-keep">
            막막했던 준비 과정을
            <br className="hidden sm:block" />
            한 단계씩 끝낼 수 있게 도와드려요.
          </h1>
          <p className="mx-auto mt-5 max-w-3xl text-sm font-medium leading-7 text-slate-600 sm:mt-6 sm:text-base sm:leading-8 break-keep">
            목표 설정부터 학생부 분석, 문서 작성까지 필요한 순서를 정리해 두었습니다.
            지금 내 상태를 확인하고, 다음에 무엇을 해야 하는지 바로 선택할 수 있어요.
          </p>
          <div className="mt-7 flex flex-wrap justify-center gap-3 sm:mt-8">
            <Link
              to={startHref}
              onClick={scrollToTop}
              className={cn(
                buttonClassName({ variant: 'primary', size: 'lg' }),
                'rounded-2xl px-6 shadow-lg shadow-blue-500/20 sm:px-8',
              )}
            >
              지금 시작하기
              <ArrowRight size={18} />
            </Link>
            <Link to="/contact" onClick={scrollToTop} className={cn(buttonClassName({ variant: 'secondary', size: 'lg' }), 'rounded-2xl px-6 sm:px-8')}>
              문의하기
            </Link>
          </div>
        </div>
      </section>

      <section className="mx-auto max-w-7xl px-4 py-12 sm:px-6 sm:py-16 lg:px-8">
        <div className="grid gap-4 lg:grid-cols-4">
          {workflowItems.map(item => (
            <article key={item.title} className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm sm:p-6">
              <h2 className="text-base font-bold text-slate-900 break-keep">{item.title}</h2>
              <p className="mt-2 text-sm font-medium leading-6 text-slate-600 break-keep">{item.description}</p>
            </article>
          ))}
        </div>
      </section>

      <section className="border-y border-slate-200 bg-white">
        <div className="mx-auto grid max-w-7xl gap-8 px-4 py-12 sm:px-6 sm:py-14 lg:grid-cols-2 lg:px-8">
          <div>
            <p className="text-xs font-bold uppercase tracking-[0.18em] text-slate-400">핵심 기능</p>
            <div className="mt-4 space-y-4">
              <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
                <p className="inline-flex items-center gap-2 text-sm font-bold text-slate-800">
                  <Target size={16} className="text-blue-700" />
                  목표 맞춤 진단
                </p>
                <p className="mt-2 text-sm font-medium leading-6 text-slate-600 break-keep">지원 목표에 맞춰 필요한 분석 기준을 자동으로 조정해요.</p>
              </div>
              <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
                <p className="inline-flex items-center gap-2 text-sm font-bold text-slate-800">
                  <FileSearch size={16} className="text-blue-700" />
                  근거 중심 결과
                </p>
                <p className="mt-2 text-sm font-medium leading-6 text-slate-600 break-keep">진단 문장마다 어떤 내용에서 나온 판단인지 함께 보여줘요.</p>
              </div>
              <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
                <p className="inline-flex items-center gap-2 text-sm font-bold text-slate-800">
                  <PenTool size={16} className="text-blue-700" />
                  작성 흐름 연결
                </p>
                <p className="mt-2 text-sm font-medium leading-6 text-slate-600 break-keep">진단 내용을 바로 문서 초안 작성으로 이어서 사용할 수 있어요.</p>
              </div>
            </div>
          </div>

          <div>
            <p className="text-xs font-bold uppercase tracking-[0.18em] text-slate-400">신뢰 기준</p>
            <div className="mt-4 space-y-3">
              {trustPoints.map(point => (
                <div key={point} className="flex items-start gap-3 rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
                  <CheckCircle2 size={16} className="mt-1 text-emerald-600" />
                  <p className="text-sm font-medium leading-6 text-slate-700 break-keep">{point}</p>
                </div>
              ))}
              <div className="flex items-start gap-3 rounded-2xl border border-blue-200 bg-blue-50 p-4">
                <ShieldCheck size={16} className="mt-1 text-blue-700" />
                <p className="text-sm font-medium leading-6 text-blue-900 break-keep">
                  이 서비스는 합격을 보장하지 않아요. 대신 준비 과정에서 놓치기 쉬운 부분을 점검하도록 돕습니다.
                </p>
              </div>
            </div>
          </div>
        </div>
      </section>

      <section className="mx-auto max-w-7xl px-4 py-12 sm:px-6 sm:py-16 lg:px-8">
        <div className="rounded-[32px] border border-amber-200 bg-gradient-to-br from-amber-50 via-white to-orange-50 p-6 sm:p-8">
          <div className="flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
            <div>
              <p className="inline-flex items-center gap-2 text-xs font-black uppercase tracking-[0.16em] text-amber-700">
                <Sparkles size={14} />
                출시 기념 요금
              </p>
              <h2 className="mt-2 text-2xl font-extrabold tracking-tight text-slate-900 sm:text-3xl">요금제 안내</h2>
              <p className="mt-2 text-sm font-medium text-slate-600 break-keep">정식 오픈 전 가격으로 미리 시작할 수 있어요.</p>
            </div>
            <p className="text-xs font-bold text-amber-800">월 결제 기준 · VAT 포함</p>
          </div>

          <div className="mt-6 grid gap-4 lg:grid-cols-3">
            {pricingPlans.map(plan => (
              <article
                key={plan.name}
                className={cn(
                  'rounded-2xl border bg-white p-5 shadow-sm sm:p-6',
                  plan.featured ? 'border-blue-300 shadow-blue-100' : 'border-slate-200',
                )}
              >
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <p className="text-xs font-bold uppercase tracking-[0.16em] text-slate-500">{plan.name}</p>
                    <p className="mt-2 text-3xl font-black tracking-tight text-slate-900">{plan.monthlyPrice}</p>
                    {plan.originalPrice ? (
                      <p className="mt-1 text-xs font-bold text-rose-600 line-through">{plan.originalPrice}</p>
                    ) : (
                      <p className="mt-1 text-xs font-bold text-emerald-600">항상 무료</p>
                    )}
                  </div>
                  <span
                    className={cn(
                      'rounded-full px-3 py-1 text-xs font-black',
                      plan.featured ? 'bg-blue-600 text-white' : 'border border-slate-200 bg-slate-50 text-slate-600',
                    )}
                  >
                    {plan.badge}
                  </span>
                </div>

                <p className="mt-4 text-sm font-medium leading-6 text-slate-600 break-keep">{plan.description}</p>
                <ul className="mt-4 space-y-2">
                  {plan.highlights.map(highlight => (
                    <li key={highlight} className="flex items-start gap-2 text-sm font-semibold text-slate-700">
                      <CheckCircle2 size={15} className="mt-0.5 text-blue-600" />
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
            <p className="text-xs font-bold uppercase tracking-[0.18em] text-slate-400">미리보기</p>
            <h2 className="mt-2 text-2xl font-extrabold tracking-tight text-slate-900">자주 묻는 질문</h2>
          </div>
          <Link
            to="/faq"
            onClick={scrollToTop}
            className="inline-flex items-center gap-2 rounded-2xl border border-slate-300 bg-white px-4 py-2 text-sm font-bold text-slate-700"
          >
            전체 보기
            <ArrowRight size={14} />
          </Link>
        </div>
        <div className="mt-6">
          <FaqAccordion items={faqPreviewItems} initialOpenId={faqPreviewItems[0]?.id} compact />
        </div>
      </section>

      <section className="border-t border-slate-200 bg-white">
        <div className="mx-auto max-w-7xl px-4 py-12 sm:px-6 sm:py-14 lg:px-8">
          <div className="rounded-2xl border border-slate-200 bg-slate-900 p-6 text-center text-white sm:p-8 lg:p-12">
            <p className="mx-auto text-xs font-bold uppercase tracking-[0.18em] text-blue-300">시작하기</p>
            <h2 className="mx-auto mt-3 text-2xl font-extrabold tracking-tight sm:text-3xl break-keep">지금부터 준비 흐름을 시작해 보세요.</h2>
            <p className="mx-auto mt-4 max-w-2xl text-sm font-medium leading-7 text-slate-300 break-keep">
              학생은 바로 진단/작성 흐름을 시작할 수 있고, 기관 문의는 별도 채널에서 빠르게 안내해 드려요.
            </p>
            <div className="mt-8 flex flex-wrap justify-center gap-4">
              <Link
                to={startHref}
                onClick={scrollToTop}
                className={cn(
                  buttonClassName({ variant: 'primary', size: 'lg' }),
                  'rounded-2xl px-8 shadow-xl shadow-blue-500/20 sm:px-10',
                )}
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
                기관 문의
              </Link>
            </div>
          </div>
        </div>
      </section>
    </div>
  );
}

