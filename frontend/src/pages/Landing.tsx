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
      <section className="relative overflow-hidden pt-14 sm:pt-20 lg:pt-24">


        <div className="mx-auto grid max-w-7xl gap-10 px-4 pb-14 sm:px-6 lg:grid-cols-[1.05fr_0.95fr] lg:gap-14 lg:px-8">
          <motion.div
            initial={{ opacity: 0, y: 24 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true, amount: 0.45 }}
            transition={{ duration: 0.48 }}
            className="space-y-6"
          >
            <div className="inline-flex items-center gap-2 rounded-full border border-indigo-200 bg-white/92 px-3 py-1.5 text-xs font-black text-indigo-700 shadow-sm">
              <Sparkles size={14} />
              트렌드·진단·워크숍 코파일럿
            </div>

            <h1 className="text-4xl font-black leading-tight tracking-tight sm:text-5xl lg:text-6xl">
              말은 짧게
              <br />
              <span className="bg-gradient-to-r from-indigo-600 to-blue-500 bg-clip-text text-transparent">
                실행은 빠르게
              </span>
            </h1>

            <div className="flex flex-wrap gap-2">
              {quickMajors.map((major) => (
                <span
                  key={major}
                  className="rounded-full border border-slate-200 bg-white/92 px-3 py-1 text-sm font-bold text-slate-700 shadow-[0_8px_16px_-14px_rgba(15,23,42,0.5)]"
                >
                  {major}
                </span>
              ))}
            </div>

            <div className="flex flex-wrap gap-3">
              <Link to={startHref} onClick={scrollToTop} className="btn-primary inline-flex items-center gap-2">
                <Rocket size={16} />
                시작
                <ArrowRight size={14} />
              </Link>
              <Link to="/app/trends" onClick={scrollToTop} className="btn-secondary inline-flex items-center gap-2">
                트렌드
                <ArrowRight size={14} />
              </Link>
              <Link to="/app/workshop" onClick={scrollToTop} className="btn-secondary inline-flex items-center gap-2">
                워크숍
                <ArrowRight size={14} />
              </Link>
            </div>
          </motion.div>

          <motion.div
            initial={{ opacity: 0, y: 24 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true, amount: 0.35 }}
            transition={{ duration: 0.55, delay: 0.05 }}
            className="relative"
          >
            <div className="tilt-3d relative rounded-[2.2rem] border border-slate-200 bg-white/78 p-8 shadow-sm backdrop-blur-xl sm:p-12 flex flex-col items-center justify-center h-full">
              <h2 className="text-2xl font-bold text-slate-800 mb-4">입시 전략의 새로운 패러다임</h2>
              <p className="text-slate-600 text-center">여러분의 학생부 분석부터 워크숍 기획까지, UniFoli가 함께합니다.</p>
            </div>
          </motion.div>
        </div>

        <div className="mb-8 flex justify-center">
          <div className="inline-flex items-center gap-2 rounded-full border border-slate-200 bg-white/84 px-3 py-1 text-xs font-bold text-slate-500">
            스크롤해서 실행 카드 보기
            <ArrowDown size={13} />
          </div>
        </div>
      </section>

      <section className="mx-auto max-w-7xl px-4 pb-12 sm:px-6 lg:px-8">
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
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
                className="group tilt-3d block rounded-3xl border border-white/70 bg-white/84 p-4 shadow-[0_20px_42px_-30px_rgba(15,23,42,0.5)] backdrop-blur-md"
              >
                <div className={`relative overflow-hidden rounded-2xl bg-gradient-to-br p-4 text-white shadow-inner ${item.accent}`}>
                  <item.icon size={16} />
                  <p className="mt-8 text-lg font-black">{item.title}</p>
                  <p className="text-xs font-bold text-white/85">{item.subtitle}</p>
                  <div className="absolute -bottom-5 -right-5 h-20 w-20 rounded-full bg-white/18 blur-md" />
                </div>
                <div className="mt-4 inline-flex items-center gap-2 text-sm font-extrabold text-slate-700 transition group-hover:text-slate-900">
                  열기
                  <ArrowRight size={14} />
                </div>
              </Link>
            </motion.div>
          ))}
        </div>
      </section>
    </div>
  );
}
