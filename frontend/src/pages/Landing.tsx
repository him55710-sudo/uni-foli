import React from 'react';
import { Link } from 'react-router-dom';
import { motion } from 'motion/react';
import {
  ArrowDown,
  ArrowRight,
  Compass,
  FileSearch,
  Layers3,
  Rocket,
  Sparkles,
  Target,
} from 'lucide-react';
import { useAuth } from '../contexts/AuthContext';
import foliDuo from '../assets/foli-duo.png';

const featureCards = [
  {
    title: 'PDF 진단',
    tag: 'Evidence',
    icon: FileSearch,
    visual: 'from-[#3b82f6] via-[#8b5cf6] to-[#ec4899]',
    bullets: ['업로드 후 핵심만 추출', '진단 요약 바로 확인'],
  },
  {
    title: '전공별 트렌드',
    tag: 'Trend Copilot',
    icon: Compass,
    visual: 'from-[#06b6d4] via-[#10b981] to-[#84cc16]',
    bullets: ['건축·컴공·바이오 칩 탐색', '탐구주제 흐름 즉시 선택'],
  },
  {
    title: '워크숍 설계',
    tag: 'Action',
    icon: Layers3,
    visual: 'from-[#fb7185] via-[#f97316] to-[#facc15]',
    bullets: ['주제 → 질문 → 활동 계획', '실행 중심 구조 자동 정리'],
  },
  {
    title: '최종 실행',
    tag: 'Output',
    icon: Target,
    visual: 'from-[#6366f1] via-[#14b8a6] to-[#22c55e]',
    bullets: ['보고서 흐름 고도화', '면접/세특 포인트 연결'],
  },
];

const quickMajors = ['건축', '컴공', '바이오', '경영', '사회과학', '디자인'];

export function Landing() {
  const { isAuthenticated } = useAuth();
  const startHref = isAuthenticated ? '/app/diagnosis' : '/auth';

  const scrollToTop = () => {
    window.scrollTo({ top: 0, left: 0, behavior: 'auto' });
  };

  return (
    <div className="bg-transparent text-slate-900 selection:bg-fuchsia-100">
      <section className="relative overflow-hidden pt-14 sm:pt-20 lg:pt-24">
        <div className="mx-auto grid max-w-7xl gap-10 px-4 pb-14 sm:px-6 lg:grid-cols-[1.05fr_0.95fr] lg:gap-14 lg:px-8">
          <motion.div
            initial={{ opacity: 0, y: 24 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true, amount: 0.45 }}
            transition={{ duration: 0.48 }}
            className="space-y-6"
          >
            <div className="inline-flex items-center gap-2 rounded-full border border-fuchsia-200 bg-white/90 px-3 py-1.5 text-xs font-black text-fuchsia-700 shadow-sm">
              <Sparkles size={14} />
              기능 중심 입시 코파일럿
            </div>
            <h1 className="text-4xl font-black leading-tight tracking-tight sm:text-5xl lg:text-6xl">
              긴 설명 없이
              <br />
              <span className="bg-gradient-to-r from-fuchsia-600 via-violet-600 to-cyan-600 bg-clip-text text-transparent">
                바로 실행 가능한
              </span>
              <br />
              학생부 설계
            </h1>
            <p className="max-w-xl text-base font-semibold text-slate-600 sm:text-lg">
              진단, 트렌드 탐색, 워크숍 설계를 한 흐름으로 연결합니다.
            </p>

            <div className="flex flex-wrap gap-2">
              {quickMajors.map((major) => (
                <span
                  key={major}
                  className="rounded-full border border-slate-200 bg-white px-3 py-1 text-sm font-bold text-slate-700"
                >
                  {major}
                </span>
              ))}
            </div>

            <div className="flex flex-wrap gap-3">
              <Link to={startHref} onClick={scrollToTop} className="btn-primary inline-flex items-center gap-2">
                <Rocket size={16} />
                바로 시작
                <ArrowRight size={14} />
              </Link>
              <Link to="/app/trends" onClick={scrollToTop} className="btn-secondary inline-flex items-center gap-2">
                트렌드 보기
                <ArrowRight size={14} />
              </Link>
            </div>
          </motion.div>

          <motion.div
            initial={{ opacity: 0, y: 24 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true, amount: 0.35 }}
            transition={{ duration: 0.55, delay: 0.05 }}
            className="relative perspective-[1200px]"
          >
            <div className="tilt-3d rounded-[2rem] border border-white/60 bg-white/78 p-5 shadow-[0_34px_60px_-28px_rgba(79,70,229,0.35)] backdrop-blur-xl">
              <div className="grid grid-cols-[1.25fr_0.75fr] gap-4">
                <div className="rounded-2xl bg-gradient-to-br from-violet-50 via-sky-50 to-rose-50 p-4">
                  <p className="text-xs font-black text-violet-600">학생부 코파일럿</p>
                  <p className="mt-1 text-sm font-bold text-slate-800">진단 → 트렌드 → 워크숍</p>
                  <img src={foliDuo} alt="Uni Foli assistant" className="mt-4 h-40 w-full rounded-xl object-cover" />
                </div>
                <div className="space-y-3">
                  {['증거 기반 진단', '전공별 칩 탐색', '실행형 플랜'].map((label, index) => (
                    <div
                      key={label}
                      className={`rounded-xl p-3 text-xs font-black text-white ${
                        index === 0
                          ? 'bg-gradient-to-br from-cyan-500 to-blue-600'
                          : index === 1
                            ? 'bg-gradient-to-br from-fuchsia-500 to-violet-600'
                            : 'bg-gradient-to-br from-amber-500 to-orange-600'
                      }`}
                    >
                      {label}
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </motion.div>
        </div>

        <div className="mb-8 flex justify-center">
          <div className="inline-flex items-center gap-2 rounded-full border border-slate-200 bg-white/80 px-3 py-1 text-xs font-bold text-slate-500">
            스크롤해서 기능 보기
            <ArrowDown size={13} />
          </div>
        </div>
      </section>

      <section className="mx-auto max-w-7xl px-4 pb-20 sm:px-6 lg:px-8">
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
          {featureCards.map((card, index) => (
            <motion.article
              key={card.title}
              initial={{ opacity: 0, y: 28 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true, amount: 0.35 }}
              transition={{ duration: 0.4, delay: index * 0.06 }}
              className="tilt-3d rounded-3xl border border-white/70 bg-white/85 p-4 shadow-[0_22px_50px_-34px_rgba(15,23,42,0.5)] backdrop-blur-md"
            >
              <div className={`mb-3 inline-flex items-center gap-2 rounded-full bg-gradient-to-r px-3 py-1 text-xs font-black text-white ${card.visual}`}>
                <card.icon size={14} />
                {card.tag}
              </div>
              <h2 className="text-xl font-black text-slate-900">{card.title}</h2>
              <div className={`mt-3 h-24 rounded-2xl bg-gradient-to-br ${card.visual}`} />
              <ul className="mt-3 space-y-1.5 text-sm font-semibold text-slate-600">
                {card.bullets.map((bullet) => (
                  <li key={bullet} className="flex items-center gap-2">
                    <span className="h-1.5 w-1.5 rounded-full bg-slate-400" />
                    {bullet}
                  </li>
                ))}
              </ul>
            </motion.article>
          ))}
        </div>
      </section>

      <section className="border-y border-white/70 bg-[linear-gradient(120deg,rgba(252,231,243,0.42)_0%,rgba(224,242,254,0.42)_50%,rgba(220,252,231,0.42)_100%)] py-16">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, amount: 0.35 }}
          transition={{ duration: 0.45 }}
          className="mx-auto max-w-5xl rounded-3xl border border-white/70 bg-white/86 p-6 text-center shadow-[0_26px_54px_-34px_rgba(15,23,42,0.4)] backdrop-blur-xl sm:p-8"
        >
          <h3 className="text-2xl font-black text-slate-900 sm:text-3xl">기능 선택 후 바로 실행</h3>
          <div className="mt-5 flex flex-wrap justify-center gap-3">
            <Link to={startHref} onClick={scrollToTop} className="btn-primary inline-flex items-center gap-2">
              진단 시작
              <ArrowRight size={14} />
            </Link>
            <Link to="/app/trends" onClick={scrollToTop} className="btn-secondary inline-flex items-center gap-2">
              전공 트렌드 탐색
              <ArrowRight size={14} />
            </Link>
            <Link to="/app/workshop" onClick={scrollToTop} className="btn-secondary inline-flex items-center gap-2">
              워크숍 열기
              <ArrowRight size={14} />
            </Link>
          </div>
        </motion.div>
      </section>
    </div>
  );
}

