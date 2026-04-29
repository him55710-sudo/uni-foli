import React from 'react';
import { Link } from 'react-router-dom';
import { motion } from 'motion/react';
import { ArrowDown, ArrowRight, Compass, FileSearch, Layers3, Rocket, Sparkles, Target } from 'lucide-react';
import { useAuth } from '../contexts/AuthContext';


const quickMajors = ['건축', '컴공', '바이오', '경영', '사회과학', '디자인'];

const quickFeatures = [
  {
    title: 'PDF 진단',
    subtitle: '파일 업로드',
    icon: FileSearch,
    accent: 'from-indigo-600 to-indigo-500',
    href: '/app/diagnosis',
  },
  {
    title: '트렌드 탐색',
    subtitle: '전공 주제칩',
    icon: Compass,
    accent: 'from-indigo-500 to-indigo-400',
    href: '/app/trends',
  },
  {
    title: '워크숍 설계',
    subtitle: '실행 계획',
    icon: Layers3,
    accent: 'from-indigo-400 to-blue-400',
    href: '/app/workshop',
  },
  {
    title: '결과 출력',
    subtitle: '문서 정리',
    icon: Target,
    accent: 'from-blue-400 to-sky-400',
    href: '/app/workshop',
  },
];

export function Landing() {
  const { isAuthenticated } = useAuth();
  const startHref = isAuthenticated ? '/app/diagnosis' : '/auth';

  const scrollToTop = () => {
    window.scrollTo({ top: 0, left: 0, behavior: 'auto' });
  };

  return (
    <div className="bg-transparent text-slate-900 selection:bg-indigo-100">
      {/* Hero Section */}
      <section className="relative overflow-hidden pt-20 sm:pt-28 lg:pt-36 pb-20 sm:pb-28 lg:pb-36">
        <div className="mx-auto grid max-w-7xl gap-12 px-4 sm:px-6 lg:grid-cols-[1.05fr_0.95fr] lg:gap-16 lg:px-8">
          <motion.div
            initial={{ opacity: 0, y: 24 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true, amount: 0.45 }}
            transition={{ duration: 0.48 }}
            className="space-y-10"
          >
            <div className="inline-flex items-center gap-2 rounded-full border border-indigo-200 bg-white/92 px-4 py-2 text-xs font-black text-indigo-700 shadow-sm">
              <Sparkles size={14} />
              트렌드·진단·워크숍 코파일럿
            </div>

            <h1 className="text-4xl font-black leading-[1.15] tracking-tight sm:text-6xl lg:text-7xl">
              말은 짧게
              <br />
              <span className="bg-gradient-to-r from-indigo-600 to-blue-500 bg-clip-text text-transparent">
                실행은 빠르게
              </span>
            </h1>

            <div className="flex flex-wrap gap-2.5">
              {quickMajors.map((major) => (
                <span
                  key={major}
                  className="rounded-full border border-slate-200 bg-white/92 px-4 py-1.5 text-sm font-bold text-slate-700 shadow-[0_8px_16px_-14px_rgba(15,23,42,0.5)]"
                >
                  {major}
                </span>
              ))}
            </div>

            <div className="flex flex-wrap gap-3 pt-4 sm:gap-4">
              <Link to={startHref} onClick={scrollToTop} className="btn-primary inline-flex items-center gap-2 px-6 py-3.5 text-base sm:px-8 sm:py-4 sm:text-lg">
                <Rocket size={18} />
                시작
                <ArrowRight size={16} />
              </Link>
              <Link to="/app/trends" onClick={scrollToTop} className="btn-secondary inline-flex items-center gap-2 px-6 py-3.5 text-base sm:px-8 sm:py-4 sm:text-lg">
                트렌드
                <ArrowRight size={16} />
              </Link>
              <Link to="/app/workshop" onClick={scrollToTop} className="btn-secondary inline-flex items-center gap-2 px-6 py-3.5 text-base sm:px-8 sm:py-4 sm:text-lg">
                워크숍
                <ArrowRight size={16} />
              </Link>
            </div>
          </motion.div>

          <motion.div
            initial={{ opacity: 0, scale: 0.98 }}
            whileInView={{ opacity: 1, scale: 1 }}
            viewport={{ once: true, amount: 0.35 }}
            transition={{ duration: 0.8, ease: "easeOut" }}
            className="relative"
          >
            <div className="relative overflow-hidden rounded-[2.5rem] border border-slate-200 bg-white p-8 shadow-2xl shadow-blue-50/50 sm:rounded-[3rem] sm:p-20 flex flex-col items-center justify-center h-full min-h-[320px] sm:min-h-[400px]">
              {/* Subtle background element */}
              <div className="absolute top-0 right-0 -mr-16 -mt-16 h-80 w-80 rounded-full bg-blue-50/50 blur-3xl opacity-60" />
              <div className="absolute bottom-0 left-0 -ml-16 -mb-16 h-80 w-80 rounded-full bg-indigo-50/50 blur-3xl opacity-60" />
              
              <div className="relative z-10 space-y-6 sm:space-y-8 text-center">
                <div className="mx-auto flex h-16 w-16 sm:h-20 sm:w-20 items-center justify-center rounded-[1.5rem] sm:rounded-[2rem] bg-blue-50 text-[#3182f6]">
                  <Layers3 size={32} className="sm:w-10 sm:h-10" strokeWidth={2.5} />
                </div>
                <div className="space-y-3 sm:space-y-4">
                  <h2 className="text-3xl font-black tracking-tight text-[#191f28] sm:text-5xl leading-tight">
                    입시 전략의<br />새로운 패러다임
                  </h2>
                  <p className="text-xl font-medium leading-relaxed text-[#4e5968] max-w-[320px] mx-auto">
                    여러분의 학생부 분석부터 워크숍 기획까지, <span className="font-black text-[#3182f6]">UniFoli</span>가 함께합니다.
                  </p>
                </div>
              </div>
            </div>
          </motion.div>
        </div>
      </section>

      {/* Features Section */}
      <section className="mx-auto max-w-7xl px-4 py-24 sm:px-6 lg:px-8">
        <div className="grid gap-8 md:grid-cols-2 xl:grid-cols-4">
          {quickFeatures.map((item, index) => (
            <motion.div
              key={item.title}
              initial={{ opacity: 0, y: 24 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true, amount: 0.35 }}
              transition={{ duration: 0.42, delay: index * 0.06 }}
            >
              <Link
                to={item.href}
                onClick={scrollToTop}
                className="group tilt-3d block rounded-[2.5rem] border border-white/70 bg-white/84 p-6 shadow-[0_32px_64px_-24px_rgba(15,23,42,0.12)] backdrop-blur-md transition-all hover:shadow-[0_48px_80px_-24px_rgba(15,23,42,0.18)]"
              >
                <div className={`relative overflow-hidden rounded-[2rem] bg-gradient-to-br p-6 text-white shadow-inner ${item.accent}`}>
                  <item.icon size={20} />
                  <div className="mt-12">
                    <p className="text-2xl font-black tracking-tight">{item.title}</p>
                    <p className="text-sm font-bold text-white/85 mt-1">{item.subtitle}</p>
                  </div>
                  <div className="absolute -bottom-8 -right-8 h-28 w-28 rounded-full bg-white/18 blur-xl" />
                </div>
                <div className="mt-6 px-2 inline-flex items-center gap-2 text-base font-extrabold text-slate-700 transition group-hover:text-[#3182f6]">
                  자세히 보기
                  <ArrowRight size={16} />
                </div>
              </Link>
            </motion.div>
          ))}
        </div>
      </section>

      {/* Pricing Section */}
      <section id="pricing" className="mx-auto max-w-7xl px-4 py-32 sm:px-6 lg:px-8">
        <PricingSection />
      </section>
    </div>
  );
}

function PricingSection() {
  const [billingCycle, setBillingCycle] = React.useState<'monthly' | 'semester'>('semester');

  const plans = [
    {
      name: 'Free',
      description: '가볍게 기능을 체험해보고 싶은 학생',
      price: { monthly: 0, semester: 0 },
      features: [
        '기본 AI 대화 및 아이디어 스케치',
        '월 5회 생기부 진단',
        '워터마크 포함 PDF 다운로드'
      ],
      buttonText: '현재 플랜 유지',
      highlight: false,
      dark: false
    },
    {
      name: 'Pro',
      description: '입시 준비 시간을 획기적으로 단축하고 싶은 학생',
      price: { monthly: 5900, semester: 23900 },
      features: [
        '무제한 생기부 심층 진단',
        '워터마크 없는 깔끔한 PDF 제공',
        'HWPX 절대 조판 무제한 다운로드',
        '프리미엄 탐구보고서 템플릿 무제한'
      ],
      buttonText: 'Pro 플랜 시작하기',
      highlight: true,
      dark: false,
      popular: true,
      originalPrice: { semester: 35400 }
    },
    {
      name: 'Ultra',
      description: '압도적인 퀄리티로 최상위권을 노리는 학생',
      price: { monthly: 9900, semester: 39900 },
      features: [
        'Pro 플랜의 모든 기능 포함',
        'AI 실전 모의 면접 무제한',
        '우선 순위 빠른 AI 응답 속도',
        '심층 면접 예상 질문 및 답변 생성'
      ],
      buttonText: 'Ultra 플랜 시작하기',
      highlight: false,
      dark: true,
      originalPrice: { semester: 59400 }
    }
  ];

  return (
    <div className="space-y-12">
      <div className="text-center space-y-3 sm:space-y-4">
        <h2 className="text-2xl font-black tracking-tight text-slate-900 sm:text-4xl lg:text-5xl">
          나에게 꼭 맞는 <span className="text-indigo-600">성장 플랜</span>
        </h2>
        <p className="text-base sm:text-lg font-medium text-slate-500 max-w-2xl mx-auto px-4">
          합리적인 가격으로 프리미엄 AI 입시 코파일럿을 경험하세요.
        </p>

        {/* Billing Toggle */}
        <div className="flex items-center justify-center pt-8">
          <div className="bg-[#f2f4f6] p-1 rounded-2xl inline-flex relative border border-[#e5e8eb] shadow-inner min-w-[320px]">
            <button
              onClick={() => setBillingCycle('monthly')}
              className={cn(
                "relative z-10 flex-1 px-8 py-3 rounded-xl font-black text-[15px] transition-all duration-300",
                billingCycle === 'monthly' ? "text-[#191f28]" : "text-[#8b95a1] hover:text-[#4e5968]"
              )}
            >
              월간 결제
            </button>
            <button
              onClick={() => setBillingCycle('semester')}
              className={cn(
                "relative z-10 flex-1 px-8 py-3 rounded-xl font-black text-[15px] transition-all duration-300",
                billingCycle === 'semester' ? "text-[#3182f6]" : "text-[#8b95a1] hover:text-[#4e5968]"
              )}
            >
              학기 결제
            </button>
            <div
              className="absolute inset-y-1 bg-white rounded-xl shadow-[0_2px_8px_rgba(0,0,0,0.08)] transition-all duration-400 ease-[cubic-bezier(0.34,1.56,0.64,1)]"
              style={{
                left: billingCycle === 'monthly' ? '4px' : 'calc(50% + 2px)',
                width: 'calc(50% - 6px)'
              }}
            />
          </div>
        </div>
      </div>

      <div className="grid gap-8 lg:grid-cols-3 pt-6 items-stretch">
        {plans.map((plan, index) => (
            <motion.div
            key={plan.name}
            initial={{ opacity: 0, y: 32 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ duration: 0.5, delay: index * 0.1 }}
            className={cn(
              "relative flex flex-col rounded-[2rem] sm:rounded-[2.5rem] p-6 sm:p-8 transition-all duration-300 hover:scale-[1.02]",
              plan.dark 
                ? "bg-[#191f28] text-white shadow-2xl shadow-blue-900/20" 
                : "bg-white border border-[#f2f4f6] shadow-[0_24px_48px_-12px_rgba(0,0,0,0.05)]",
              plan.highlight && "ring-2 ring-[#3182f6] ring-offset-4"
            )}
          >
            {plan.popular && (
              <div className="absolute top-0 left-1/2 -translate-x-1/2 -translate-y-1/2 whitespace-nowrap">
                <span className="bg-[#3182f6] text-white text-[11px] font-black px-6 py-2.5 rounded-full shadow-xl uppercase tracking-widest">
                  추천 요금제
                </span>
              </div>
            )}

            <div className="mb-8 h-20">
              <h3 className={cn("text-2xl font-black mb-2 tracking-tight", plan.dark ? "text-[#3182f6]" : "text-[#191f28]")}>
                {plan.name}
              </h3>
              <p className={cn("text-sm font-bold leading-relaxed", plan.dark ? "text-[#adb5bd]" : "text-[#4e5968]")}>
                {plan.description}
              </p>
            </div>

            <div className="mb-8 h-20 sm:h-28 flex flex-col justify-end">
              <div className="h-6">
                {billingCycle === 'semester' && plan.originalPrice && plan.price.semester < plan.originalPrice.semester && (
                  <div className={cn("text-xs sm:text-sm font-bold line-through mb-1 opacity-40", plan.dark ? "text-slate-500" : "text-slate-400")}>
                    ₩{plan.originalPrice.semester.toLocaleString()}
                  </div>
                )}
              </div>
              <div className="flex items-baseline gap-1.5 sm:gap-2 flex-wrap">
                <span className="text-3xl sm:text-5xl font-black tracking-tighter whitespace-nowrap">
                  ₩{plan.price[billingCycle].toLocaleString()}
                </span>
                <span className={cn("text-sm sm:text-xl font-bold opacity-60", plan.dark ? "text-slate-400" : "text-slate-500")}>
                  /{billingCycle === 'monthly' ? '월' : '학기'}
                </span>
              </div>
            </div>

            <ul className="mb-10 space-y-4 flex-1">
              {plan.features.map((feature) => (
                <li key={feature} className="flex items-start gap-3">
                  <div className={cn(
                    "mt-1 flex h-5 w-5 shrink-0 items-center justify-center rounded-full",
                    plan.dark ? "bg-indigo-500/20 text-indigo-400" : "bg-indigo-50 text-indigo-600"
                  )}>
                    <Check size={12} strokeWidth={4} />
                  </div>
                  <span className={cn("text-sm font-bold leading-snug", plan.dark ? "text-slate-300" : "text-slate-700")}>
                    {feature}
                  </span>
                </li>
              ))}
            </ul>

            <button
              className={cn(
                "w-full rounded-2xl py-4 sm:py-5 text-base sm:text-lg font-black transition-all duration-300 active:scale-[0.98] shadow-lg",
                plan.dark
                  ? "bg-indigo-600 text-white hover:bg-indigo-500 shadow-indigo-900/40"
                  : plan.highlight
                  ? "bg-indigo-600 text-white hover:bg-indigo-500 shadow-indigo-100"
                  : "bg-slate-100 text-slate-900 hover:bg-slate-200 shadow-slate-50"
              )}
              onClick={() => {
                const amount = plan.price[billingCycle];
                if (amount > 0) {
                  alert(`토스페이먼츠 연동 준비 중입니다.\n결제 금액: ₩${amount.toLocaleString()}`);
                }
              }}
            >
              {plan.buttonText}
            </button>
          </motion.div>
        ))}
      </div>

      <p className="text-center text-sm font-bold text-slate-400 flex items-center justify-center gap-2">
        <Sparkles size={14} /> 토스페이먼츠 보안 결제를 지원합니다
      </p>
    </div>
  );
}

function Check({ size, strokeWidth, ...props }: any) {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={strokeWidth}
      strokeLinecap="round"
      strokeLinejoin="round"
      {...props}
    >
      <polyline points="20 6 9 17 4 12" />
    </svg>
  );
}

const cn = (...classes: any[]) => classes.filter(Boolean).join(' ');
