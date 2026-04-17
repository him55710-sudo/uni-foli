import React from 'react';
import { Link } from 'react-router-dom';
import { motion } from 'motion/react';
import {
  ArrowRight,
  Compass,
  FileSearch,
  Rocket,
  ShieldCheck,
  Target,
} from 'lucide-react';
import { useAuth } from '../contexts/AuthContext';
import { cn } from '../lib/cn';

const workflowPanels = [
  {
    eyebrow: 'Targets',
    title: '목표 대학과 학과 기준 맞추기',
    description: '대학과 학과에 따라 같은 학생부라도 읽는 기준이 달라집니다.',
    icon: Target,
    color: 'blue',
  },
  {
    eyebrow: 'Evidence',
    title: '학생부 PDF에서 근거만 추출하기',
    description: '텍스트를 먼저 정리한 뒤 실제 기록이 남아 있는 문장만 증거로 씁니다.',
    icon: FileSearch,
    color: 'slate',
  },
  {
    eyebrow: 'Direction',
    title: '약점과 다음 행동까지 바로 연결하기',
    description: '진단이 끝나면 바로 워크숍으로 이어서 초안과 활동 방향을 잡을 수 있습니다.',
    icon: Compass,
    color: 'indigo',
  },
];

const principles = [
  {
    title: '많이 읽게 하지 않습니다',
    description: '첫 화면에서는 지금 해야 할 행동 하나만 크게 보여줍니다.',
  },
  {
    title: '좋아 보이는 말보다 기록을 먼저 봅니다',
    description: '학생부 원문에 없는 강한 주장은 만들지 않고, 근거가 약하면 먼저 경고합니다.',
  },
  {
    title: '진단을 문서 작업과 분리하지 않습니다',
    description: '진단 결과, 보고서, 챗봇 질문이 같은 아티팩트를 공유하도록 설계했습니다.',
  },
];

const trustRows = [
  '학생부에 없는 내용은 추천하지 않습니다.',
  '애매한 문장은 먼저 경고합니다.',
  '진단 뒤에는 바로 워크숍으로 이어집니다.',
];

export function Landing() {
  const { isAuthenticated } = useAuth();
  const startHref = isAuthenticated ? '/app/diagnosis' : '/auth';

  const scrollToTop = () => {
    window.scrollTo({ top: 0, left: 0, behavior: 'auto' });
  };

  return (
    <div className="bg-white text-slate-900 selection:bg-blue-100">
      <section className="relative overflow-hidden py-16 lg:py-24">
        <div className="relative mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
          <div className="grid items-center gap-16 lg:grid-cols-[1.1fr_1fr]">
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.5 }}
              className="max-w-2xl text-center lg:text-left"
            >
              <div className="inline-flex items-center gap-2 rounded-lg border border-slate-200 bg-slate-50 px-3 py-1.5 text-[11px] font-bold uppercase tracking-wider text-slate-600">
                <span className="h-2 w-2 rounded-full bg-blue-600" />
                <span>Admission Decision Support</span>
              </div>

              <h1 className="mt-8 text-4xl font-extrabold leading-tight tracking-tight text-slate-900 sm:text-5xl lg:text-6xl">
                학생부 기록의 가치를<br />
                <span className="text-blue-700">데이터와 증명으로</span> 확인하세요
              </h1>

              <p className="mt-6 text-lg font-medium leading-relaxed text-slate-500 sm:text-xl">
                단순 분석을 넘어, 목표 대학 기준에 맞춘 정밀 진단과<br className="hidden sm:block" />
                실행 가능한 워크숍 초안까지 한 번에 연결합니다.
              </p>

              <div className="mt-10 flex flex-wrap justify-center lg:justify-start gap-4">
                <Link
                  to={startHref}
                  onClick={scrollToTop}
                  className="btn-primary group flex items-center gap-2"
                >
                  <Rocket size={18} />
                  <span>진단 시작하기</span>
                  <ArrowRight size={16} className="transition-transform group-hover:translate-x-1" />
                </Link>
                <Link
                  to="/faq"
                  onClick={scrollToTop}
                  className="btn-secondary flex items-center gap-2"
                >
                  시스템 소개서
                </Link>
              </div>

              <div className="mt-16 grid grid-cols-3 gap-8">
                {[
                  { label: "신뢰도 파싱", val: "99%" },
                  { label: "분석 핵심 축", val: "6개" },
                  { label: "분석 속도", val: "즉시" }
                ].map((stat, i) => (
                  <div key={i}>
                    <p className="text-3xl font-bold text-slate-900">{stat.val}</p>
                    <p className="mt-1 text-xs font-bold text-slate-400 uppercase tracking-widest">{stat.label}</p>
                  </div>
                ))}
              </div>
            </motion.div>

            <motion.div
              initial={{ opacity: 0, x: 20 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ duration: 0.5, delay: 0.2 }}
              className="relative hidden lg:block"
            >
              <div className="document-card p-1">
                <div className="overflow-hidden rounded-lg bg-white p-8">
                  <div className="mb-8 flex items-center justify-between border-b border-slate-100 pb-4">
                    <span className="text-xs font-bold uppercase tracking-widest text-slate-400">Diagnosis Pipeline</span>
                    <div className="flex gap-1.5">
                      <div className="h-2 w-2 rounded-full bg-slate-200" />
                      <div className="h-2 w-2 rounded-full bg-slate-200" />
                      <div className="h-2 w-2 rounded-full bg-slate-200" />
                    </div>
                  </div>

                  <div className="space-y-6">
                    {workflowPanels.map((panel) => (
                      <div
                        key={panel.title}
                        className="flex items-start gap-4 rounded-xl p-4 transition-colors hover:bg-slate-50"
                      >
                        <div className={cn(
                          "flex h-12 w-12 shrink-0 items-center justify-center rounded-lg border",
                          panel.color === 'blue' && 'bg-blue-50 border-blue-100 text-blue-600',
                          panel.color === 'slate' && 'bg-slate-50 border-slate-200 text-slate-600',
                          panel.color === 'indigo' && 'bg-indigo-50 border-indigo-100 text-indigo-600',
                        )}>
                          <panel.icon size={20} />
                        </div>
                        <div>
                          <h3 className="text-lg font-bold text-slate-900">{panel.title}</h3>
                          <p className="mt-1 text-sm font-medium text-slate-500 line-clamp-2">{panel.description}</p>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            </motion.div>
          </div>
        </div>
      </section>

      {/* Principles Section */}
      <section className="bg-slate-50 border-y border-slate-200 py-24">
        <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
          <div className="mb-16 text-center">
            <h2 className="text-sm font-bold uppercase tracking-widest text-blue-600">Principles</h2>
            <h3 className="mt-4 text-3xl font-extrabold text-slate-900 sm:text-4xl">
              데이터의 투명성을 고수합니다
            </h3>
          </div>

          <div className="grid gap-6 md:grid-cols-3">
            {principles.map((item, index) => (
              <div key={item.title} className="document-card bg-white p-8">
                <span className="text-xs font-black text-slate-300">0{index + 1}</span>
                <h4 className="mt-4 text-xl font-bold text-slate-900">{item.title}</h4>
                <p className="mt-2 text-sm font-medium leading-relaxed text-slate-500">{item.description}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* CTA Section */}
      <section className="mx-auto max-w-7xl px-4 py-24 sm:px-6 lg:px-8">
        <div className="rounded-[2rem] bg-slate-900 px-8 py-16 text-center text-white shadow-xl">
          <h2 className="text-3xl font-extrabold sm:text-4xl">
            준비된 학생부 데이터로<br />
            입시 방향성을 정립하세요.
          </h2>
          <div className="mt-10 flex flex-wrap justify-center gap-4">
            <Link to={startHref} onClick={scrollToTop} className="btn-primary bg-white text-slate-900 hover:bg-slate-100">
              무료 진단 시작하기
            </Link>
            <Link to="/contact" onClick={scrollToTop} className="btn-secondary bg-transparent text-white border-white/20 hover:bg-white/10">
              시스템 도입 문의
            </Link>
          </div>
        </div>
      </section>

      {/* Trust Section */}
      <section className="py-20">
        <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
          <div className="flex flex-wrap items-center justify-center gap-8 md:gap-16">
            {trustRows.map((row, i) => (
              <div key={i} className="flex items-center gap-3">
                <ShieldCheck size={20} className="text-blue-600" />
                <p className="text-sm font-bold text-slate-600">{row}</p>
              </div>
            ))}
          </div>
        </div>
      </section>
    </div>
  );
}
