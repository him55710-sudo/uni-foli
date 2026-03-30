import React from 'react';
import { Link } from 'react-router-dom';
import {
  ArrowRight,
  BadgeCheck,
  BookOpen,
  Compass,
  FileSearch,
  FolderArchive,
  Headset,
  LayoutPanelTop,
  ShieldCheck,
  Sparkles,
  Target,
  TrendingUp,
} from 'lucide-react';
import { motion } from 'motion/react';
import { FaqAccordion } from '../components/FaqAccordion';
import { UniFoliaLogo } from '../components/UniFoliaLogo';
import { faqPreviewItems } from '../content/faq';
import { useAuth } from '../contexts/AuthContext';

const trustBadges = ['근거 기반 AI', '허위 미화 금지', '학생 기록 중심', '실행 가능한 다음 행동 제안'];

const problemCards = [
  {
    title: '불안을 키우는 추상적 조언',
    body: '입시 준비가 막막할수록 “더 열심히 하라”는 식의 넓은 조언만 남고, 실제 다음 행동은 보이지 않기 쉽습니다.',
  },
  {
    title: '기록과 단절된 생성',
    body: '기록을 보지 않은 채 문장만 만들어내면 안전하지도 않고, 학생의 실제 강점과도 멀어질 수 있습니다.',
  },
  {
    title: '결과물만 남는 흐름',
    body: '초안 한 번으로 끝나는 도구는 이후 활동 설계와 보완 근거를 남기기 어렵습니다.',
  },
];

const steps = [
  { title: '기록 입력/정리', body: '생기부와 현재 목표를 정리해 출발점을 분명히 합니다.' },
  { title: 'AI 진단', body: '현재 기록의 강점, 보완 포인트, 위험 신호를 근거 기반으로 확인합니다.' },
  { title: '탐구 플랜/퀘스트 추천', body: '다음에 무엇을 해야 할지 실행 가능한 흐름으로 연결합니다.' },
  { title: '작업실 drafting', body: '작업실에서 기록과 진단을 바탕으로 결과물을 안전하게 다듬습니다.' },
];

const featureCards = [
  { icon: LayoutPanelTop, title: '내 생기부 관리', body: '기록 업로드와 처리 상태를 한 화면에서 확인합니다.' },
  { icon: FileSearch, title: 'AI 진단', body: '강점, 근거 부족 구간, 다음 탐구 방향을 분명하게 봅니다.' },
  { icon: Compass, title: '맞춤 탐구 플랜', body: '막연한 제안이 아니라 다음 활동의 초점을 정리합니다.' },
  { icon: Target, title: '퀘스트 기반 실행 흐름', body: '결과물 이전에 무엇을 더 해야 하는지 순서로 안내합니다.' },
  { icon: Sparkles, title: 'Foli 작업실', body: '근거와 맥락을 보존한 채 drafting을 이어가는 공간입니다.' },
  { icon: FolderArchive, title: '보관함과 트렌드', body: '완성한 결과물과 참고할 만한 트렌드 정보를 함께 관리합니다.' },
];

const differentiators = [
  'generic chatbot이 아니라 school-record-first workflow를 기준으로 움직입니다.',
  '결과물 한 번보다 다음 행동과 탐구 흐름을 함께 설계하는 데 비중을 둡니다.',
  '추측 생성보다 evidence-grounded assistance를 우선합니다.',
  '합격 보장 대신 더 나은 준비와 더 안전한 기록 활용을 돕는 도구입니다.',
];

const safetyItems = [
  '실제로 하지 않은 활동을 만들어내지 않습니다.',
  '과장된 합격 약속이나 근거 없는 미화를 내세우지 않습니다.',
  '기록이 부족하면 억지 생성보다 다음 행동과 보완 포인트를 먼저 제안합니다.',
];

export function Landing() {
  const { isAuthenticated } = useAuth();
  const startHref = isAuthenticated ? '/app' : '/auth';
  const startLabel = isAuthenticated ? '앱으로 이동' : '무료로 시작하기';

  return (
    <div>
      <section className="relative overflow-hidden bg-[radial-gradient(circle_at_top_right,_rgba(59,130,246,0.18),_transparent_32%),linear-gradient(180deg,_#f8fbff_0%,_#eff6ff_100%)]">
        <div className="mx-auto grid min-h-[calc(100svh-81px)] max-w-7xl items-center gap-12 px-4 py-16 sm:px-6 lg:grid-cols-[minmax(0,0.95fr)_minmax(360px,0.75fr)] lg:px-8 lg:py-20">
          <motion.div
            initial={{ opacity: 0, y: 24 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.45 }}
            className="max-w-3xl"
          >
            <p className="inline-flex rounded-full border border-blue-100 bg-white/80 px-4 py-2 text-sm font-black text-blue-600 shadow-sm">
              기록 중심으로 다음 행동까지 설계하는 입시 준비 도구
            </p>
            <h1 className="mt-6 text-4xl font-black leading-tight tracking-tight text-slate-900 sm:text-5xl lg:text-6xl">
              생기부를 바탕으로
              <br />
              더 안전하고 선명한
              <br />
              준비 흐름을 만듭니다.
            </h1>
            <p className="mt-6 max-w-2xl text-lg font-medium leading-8 text-slate-600">
              Uni Folia는 학생 기록을 먼저 보고, AI 진단과 탐구 플랜, 작업실 drafting까지 이어지는 흐름으로 정리합니다.
              기록이 부족하면 억지로 채우지 않고, 지금 필요한 다음 행동을 제안합니다.
            </p>
            <div className="mt-8 flex flex-col gap-3 sm:flex-row">
              <Link
                to={startHref}
                className="inline-flex items-center justify-center gap-2 rounded-full bg-slate-900 px-6 py-4 text-base font-black text-white shadow-lg shadow-slate-900/10 transition-transform hover:-translate-y-0.5"
              >
                {startLabel}
                <ArrowRight size={18} />
              </Link>
              <a
                href="#features"
                className="inline-flex items-center justify-center gap-2 rounded-full border border-slate-200 bg-white px-6 py-4 text-base font-black text-slate-700 shadow-sm hover:bg-slate-50"
              >
                기능 자세히 보기
              </a>
            </div>
            <div className="mt-10 flex flex-wrap items-center gap-3">
              <span className="mr-2 text-xs font-black uppercase tracking-widest text-blue-500">Uni Folia 원칙</span>
              {trustBadges.map(item => (
                <span key={item} className="group relative flex items-center gap-2 rounded-full border border-blue-50/50 bg-white/70 px-4 py-2.5 text-sm font-bold text-slate-700 shadow-[0_2px_10px_rgba(59,130,246,0.05)] backdrop-blur-sm transition-all hover:-translate-y-0.5 hover:bg-white hover:shadow-blue-100/40">
                  <BadgeCheck size={16} className="text-blue-600" />
                  {item}
                </span>
              ))}
            </div>
          </motion.div>

          <motion.div
            initial={{ opacity: 0, y: 28 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5, delay: 0.08 }}
            className="relative"
          >
            <div className="rounded-[40px] border border-white/70 bg-white/85 p-6 shadow-[0_30px_80px_rgba(30,41,59,0.10)] backdrop-blur">
              <div className="flex items-center gap-4 rounded-[28px] border border-blue-100 bg-gradient-to-br from-blue-50 via-white to-slate-50 p-5">
                <UniFoliaLogo size="lg" markOnly />
                <div>
                  <p className="text-xs font-black uppercase tracking-[0.22em] text-blue-600">Workflow</p>
                  <h2 className="mt-2 text-2xl font-black tracking-tight text-slate-900">목표 설정 → 생기부 업로드 → AI 진단 → 작업실</h2>
                  <p className="mt-2 text-sm font-medium leading-6 text-slate-500">
                    한 번의 생성보다, 기록과 진단 결과를 따라 다음 행동까지 이어지는 준비 흐름을 먼저 보여줍니다.
                  </p>
                </div>
              </div>

              <div className="mt-5 grid gap-4 sm:grid-cols-2">
                <div className="rounded-[28px] border border-slate-200 bg-slate-50 p-5">
                  <p className="text-xs font-black uppercase tracking-[0.18em] text-slate-400">핵심 차별점</p>
                  <ul className="mt-4 space-y-3 text-sm font-semibold leading-6 text-slate-700">
                    <li className="flex gap-2">
                      <BadgeCheck size={18} className="mt-0.5 text-blue-600" />
                      기록이 먼저, 생성은 그다음
                    </li>
                    <li className="flex gap-2">
                      <BadgeCheck size={18} className="mt-0.5 text-blue-600" />
                      탐구 플랜과 실행 흐름까지 연결
                    </li>
                    <li className="flex gap-2">
                      <BadgeCheck size={18} className="mt-0.5 text-blue-600" />
                      부족한 기록은 보완 행동으로 안내
                    </li>
                  </ul>
                </div>
                <div className="rounded-[28px] border border-slate-200 bg-white p-5 shadow-sm">
                  <p className="text-xs font-black uppercase tracking-[0.18em] text-slate-400">신뢰 원칙</p>
                  <div className="mt-4 space-y-3">
                    {safetyItems.map(item => (
                      <div key={item} className="rounded-2xl border border-slate-100 bg-slate-50 px-4 py-3 text-sm font-semibold text-slate-700">
                        {item}
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            </div>
          </motion.div>
        </div>
      </section>

      <section className="mx-auto max-w-7xl px-4 py-20 sm:px-6 lg:px-8">
        <div className="max-w-3xl">
          <p className="text-sm font-black uppercase tracking-[0.22em] text-slate-400">Why Uni Folia</p>
          <h2 className="mt-3 text-3xl font-black tracking-tight text-slate-900 sm:text-4xl">
            입시 준비에서 흔한 마찰을
            <br />
            기록 중심 흐름으로 줄입니다.
          </h2>
        </div>
        <div className="mt-10 grid gap-5 lg:grid-cols-3">
          {problemCards.map(card => (
            <div key={card.title} className="rounded-[32px] border border-slate-200 bg-white p-7 shadow-sm">
              <h3 className="text-xl font-black text-slate-900">{card.title}</h3>
              <p className="mt-4 text-sm font-medium leading-7 text-slate-600">{card.body}</p>
            </div>
          ))}
        </div>
      </section>

      <section className="bg-white py-20">
        <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
          <div className="max-w-3xl">
            <p className="text-sm font-black uppercase tracking-[0.22em] text-blue-600">How It Works</p>
            <h2 className="mt-3 text-3xl font-black tracking-tight text-slate-900 sm:text-4xl">
              준비, 분석, 실행이 한 흐름으로 이어집니다.
            </h2>
          </div>
          <div className="mt-10 grid gap-5 lg:grid-cols-4">
            {steps.map((step, index) => (
              <div key={step.title} className="group relative rounded-[32px] border border-slate-200 bg-white p-7 transition-all hover:border-blue-200 hover:shadow-[0_20px_50px_rgba(59,130,246,0.08)]">
                <div className="absolute -top-4 left-7 flex h-12 w-12 items-center justify-center rounded-2xl bg-blue-600 text-lg font-black text-white shadow-lg shadow-blue-600/20 ring-4 ring-white transition-transform group-hover:scale-110">
                  {index + 1}
                </div>
                <h3 className="mt-6 text-xl font-black text-slate-900">{step.title}</h3>
                <p className="mt-3 text-sm font-medium leading-7 text-slate-600">{step.body}</p>
                {index < steps.length - 1 && (
                  <div className="absolute -right-3 top-1/2 hidden h-px w-6 bg-slate-100 lg:block" />
                )}
              </div>
            ))}
          </div>
        </div>
      </section>

      <section id="features" className="mx-auto max-w-7xl px-4 py-20 sm:px-6 lg:px-8">
        <div className="max-w-3xl">
          <p className="text-sm font-black uppercase tracking-[0.22em] text-slate-400">Key Features</p>
          <h2 className="mt-3 text-3xl font-black tracking-tight text-slate-900 sm:text-4xl">
            현재 제품 흐름을 그대로 드러내는 핵심 기능
          </h2>
        </div>
        <div className="mt-10 grid gap-5 md:grid-cols-2 xl:grid-cols-3">
          {featureCards.map(card => {
            const Icon = card.icon;
            return (
              <div key={card.title} className="rounded-[32px] border border-slate-200 bg-white p-6 shadow-sm">
                <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-blue-50 text-blue-600">
                  <Icon size={22} />
                </div>
                <h3 className="mt-5 text-xl font-black text-slate-900">{card.title}</h3>
                <p className="mt-3 text-sm font-medium leading-7 text-slate-600">{card.body}</p>
              </div>
            );
          })}
        </div>
      </section>

      <section className="bg-white py-20">
        <div className="mx-auto grid max-w-7xl gap-10 px-4 sm:px-6 lg:grid-cols-[0.9fr_1.1fr] lg:px-8">
          <div>
            <p className="text-sm font-black uppercase tracking-[0.22em] text-blue-600">Differentiation</p>
            <h2 className="mt-3 text-3xl font-black tracking-tight text-slate-900 sm:text-4xl">
              왜 Uni Folia가 다른지
              <br />
              공개 페이지에서도 분명하게 보여줍니다.
            </h2>
          </div>
          <div className="space-y-4">
            {differentiators.map(item => (
              <div key={item} className="rounded-[28px] border border-slate-200 bg-slate-50 px-5 py-5 text-sm font-semibold leading-7 text-slate-700">
                {item}
              </div>
            ))}
          </div>
        </div>
      </section>

      <section className="mx-auto max-w-7xl px-4 py-20 sm:px-6 lg:px-8">
        <div className="grid gap-8 lg:grid-cols-[0.9fr_1.1fr]">
          <div>
            <p className="text-sm font-black uppercase tracking-[0.22em] text-slate-400">Trust & Safety</p>
            <h2 className="mt-3 text-3xl font-black tracking-tight text-slate-900 sm:text-4xl">
              안전 원칙은 기능 뒤에 숨기지 않습니다.
            </h2>
            <p className="mt-4 text-base font-medium leading-8 text-slate-600">
              Uni Folia는 학생 기록을 다루는 도구이기 때문에, 편의보다 안전과 신뢰를 먼저 보여주는 것이 중요하다고 봅니다.
            </p>
          </div>
          <div className="space-y-4">
            {safetyItems.map(item => (
              <div key={item} className="flex gap-4 rounded-[28px] border border-slate-200 bg-white p-6 shadow-sm">
                <div className="flex h-12 w-12 flex-shrink-0 items-center justify-center rounded-2xl bg-blue-50 text-blue-600">
                  <ShieldCheck size={22} />
                </div>
                <p className="text-sm font-semibold leading-7 text-slate-700">{item}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section className="bg-white py-20">
        <div className="mx-auto max-w-5xl px-4 sm:px-6 lg:px-8">
          <div className="flex flex-col items-start justify-between gap-4 sm:flex-row sm:items-end">
            <div>
              <p className="text-sm font-black uppercase tracking-[0.22em] text-blue-600">FAQ Preview</p>
              <h2 className="mt-3 text-3xl font-black tracking-tight text-slate-900 sm:text-4xl">
                시작 전에 많이 묻는 질문
              </h2>
            </div>
            <Link
              to="/faq"
              className="inline-flex items-center gap-2 rounded-full border border-slate-200 bg-white px-5 py-3 text-sm font-black text-slate-700 shadow-sm hover:bg-slate-50"
            >
              전체 FAQ 보기
              <ArrowRight size={16} />
            </Link>
          </div>
          <div className="mt-8">
            <FaqAccordion items={faqPreviewItems} initialOpenId={faqPreviewItems[0]?.id} compact />
          </div>
        </div>
      </section>

      <section className="mx-auto max-w-7xl px-4 py-20 sm:px-6 lg:px-8">
        <div className="grid gap-5 lg:grid-cols-2">
          <div className="rounded-[36px] border border-slate-200 bg-white p-8 shadow-sm">
            <p className="text-sm font-black uppercase tracking-[0.22em] text-blue-600">Contact</p>
            <h2 className="mt-3 text-3xl font-black tracking-tight text-slate-900">학생과 보호자를 위한 지원 허브</h2>
            <p className="mt-4 text-sm font-medium leading-7 text-slate-600">
              시작 전에 궁금한 점이 있거나, 사용 흐름과 기록 업로드, 결과물 신뢰성에 대해 확인하고 싶다면 문의 허브에서 1:1 문의와
              버그·기능 제안을 바로 보낼 수 있습니다.
            </p>
            <div className="mt-6 flex flex-wrap gap-3">
              <Link
                to="/contact"
                className="inline-flex items-center gap-2 rounded-full bg-slate-900 px-5 py-3 text-sm font-black text-white shadow-lg shadow-slate-900/10"
              >
                문의 허브 열기
                <ArrowRight size={16} />
              </Link>
              <Link
                to="/faq"
                className="inline-flex items-center gap-2 rounded-full border border-slate-200 bg-white px-5 py-3 text-sm font-black text-slate-700 shadow-sm hover:bg-slate-50"
              >
                FAQ 먼저 보기
              </Link>
            </div>
          </div>

          <div className="rounded-[36px] border border-blue-100 bg-blue-50 p-8 shadow-sm">
            <p className="text-sm font-black uppercase tracking-[0.22em] text-blue-700">Partnership</p>
            <h2 className="mt-3 text-3xl font-black tracking-tight text-slate-900">학교·학원 협업은 별도 흐름으로 받습니다.</h2>
            <p className="mt-4 text-sm font-medium leading-7 text-slate-600">
              경쟁 서비스들처럼 협업 문의를 footer 구석에 숨기지 않고, 공개적으로 분리된 경로에서 운영 방식과 적용 범위를 확인할 수
              있게 했습니다. 학생용 지원과 기관용 도입 문의를 섞지 않는 것이 Uni Folia의 기본 원칙입니다.
            </p>
            <div className="mt-6 flex flex-wrap gap-3">
              <Link
                to="/contact?type=partnership"
                className="inline-flex items-center gap-2 rounded-full bg-blue-600 px-5 py-3 text-sm font-black text-white shadow-lg shadow-blue-500/20"
              >
                협업/도입 문의
                <ArrowRight size={16} />
              </Link>
            </div>
          </div>
        </div>
      </section>

      <section className="mx-auto max-w-7xl px-4 py-20 sm:px-6 lg:px-8">
        <div className="rounded-[40px] border border-slate-200 bg-gradient-to-br from-slate-900 via-slate-900 to-blue-950 p-8 text-white shadow-[0_30px_80px_rgba(15,23,42,0.18)] sm:p-10">
          <div className="grid gap-8 lg:grid-cols-[1.1fr_0.9fr]">
            <div>
              <p className="text-sm font-black uppercase tracking-[0.22em] text-blue-200">Final CTA</p>
              <h2 className="mt-3 text-3xl font-black tracking-tight sm:text-4xl">
                지금 필요한 것은 과장된 약속보다
                <br />
                선명한 다음 행동입니다.
              </h2>
              <p className="mt-4 max-w-2xl text-sm font-medium leading-7 text-slate-300">
                학생은 바로 시작할 수 있고, 학교·학원은 도입 가능성과 운영 방식을 문의할 수 있습니다.
              </p>
            </div>
            <div className="grid gap-4">
              <Link
                to={startHref}
                className="rounded-[32px] border border-white/10 bg-white/10 p-6 transition-colors hover:bg-white/15"
              >
                <div className="flex items-center gap-3">
                  <BookOpen size={22} className="text-blue-200" />
                  <p className="text-lg font-black">학생용 시작</p>
                </div>
                <p className="mt-3 text-sm font-medium leading-7 text-slate-300">
                  목표 설정부터 AI 진단, 작업실까지 현재 워크플로를 바로 확인합니다.
                </p>
              </Link>
              <Link
                to="/contact?type=partnership"
                className="rounded-[32px] border border-white/10 bg-white/5 p-6 transition-colors hover:bg-white/10"
              >
                <div className="flex items-center gap-3">
                  <TrendingUp size={22} className="text-blue-200" />
                  <p className="text-lg font-black">학교·학원 협업 문의</p>
                </div>
                <p className="mt-3 text-sm font-medium leading-7 text-slate-300">
                  기관 운영 흐름과 적용 범위를 기준으로 도입 가능성을 상담합니다.
                </p>
              </Link>
            </div>
          </div>
        </div>
      </section>

      {/* Floating Support Button */}
      <div className="fixed bottom-8 right-8 z-50">
        <Link
          to="/contact"
          className="flex h-14 w-14 items-center justify-center rounded-2xl bg-slate-900 text-white shadow-2xl transition-all hover:-translate-y-1 hover:bg-blue-600 active:scale-95 group"
        >
          <Headset size={24} />
          <span className="absolute right-full mr-3 whitespace-nowrap rounded-xl bg-slate-900 px-4 py-2 text-sm font-black text-white opacity-0 transition-opacity group-hover:opacity-100 pointer-events-none">
            문의 허브 열기
          </span>
        </Link>
      </div>
    </div>
  );
}
