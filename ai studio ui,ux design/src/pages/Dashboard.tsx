import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { motion } from 'motion/react';
import { Zap, ArrowRight } from 'lucide-react';
import toast from 'react-hot-toast';
import { useAuth } from '../contexts/AuthContext';
import { DiagnosisModal } from '../components/DiagnosisModal';
import { api } from '../lib/api';

const trends = [
  { id: 1, icon: '📘', title: '컴공 전공자를 위한 AI 윤리 이슈', tag: '도서 추천' },
  { id: 2, icon: '🧭', title: '2026 수시 핵심 변화 요약', tag: '입시 이슈' },
  { id: 3, icon: '🧪', title: '합격생 사례로 보는 탐구 보고서 구조', tag: '합격 가이드' },
  { id: 4, icon: '💡', title: '기후·경제 융합 탐구 주제 10선', tag: '탐구 주제' },
];

interface UserStats {
  report_count: number;
  level: string;
  completion_rate: number;
}

export function Dashboard() {
  const navigate = useNavigate();
  const { user, isGuestSession } = useAuth();
  const [isDiagnosisOpen, setIsDiagnosisOpen] = useState(false);
  const [stats, setStats] = useState<UserStats>({
    report_count: 0,
    level: '로딩 중...',
    completion_rate: 0,
  });

  useEffect(() => {
    if (!user && !isGuestSession) return;

    api.get<UserStats>('/api/v1/projects/user/stats')
      .then((data) => setStats(data))
      .catch((error) => {
        console.error('Failed to load stats:', error);
        setStats({
          report_count: 0,
          level: isGuestSession ? '게스트 모드' : '새로운 시작',
          completion_rate: 0,
        });
      });
  }, [user, isGuestSession]);

  return (
    <div className="mx-auto max-w-5xl px-4 pb-12 sm:px-6 lg:px-8">
      <motion.div
        initial={{ opacity: 0, y: 30 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.6, ease: 'easeOut' }}
        className="mb-12 pt-8 text-center md:pt-12 md:text-left"
      >
        <div className="mb-6 inline-block">
          <div className="rounded-full border border-red-200 bg-gradient-to-r from-red-50 to-red-100/50 px-6 py-2.5 text-sm font-extrabold text-red-600 shadow-sm clay-card md:text-base">
            제출 마감 대비 집중 관리 모드
          </div>
        </div>

        <h1 className="mb-6 break-keep text-4xl font-extrabold leading-tight tracking-tight text-slate-800 md:text-5xl lg:text-6xl">
          내 학생부 탐구,
          <br className="hidden md:block" />
          <span className="bg-gradient-to-r from-blue-500 to-blue-400 bg-clip-text text-transparent">
            AI와 함께 제출용 보고서로 완성하기
          </span>
        </h1>

        <p className="mx-auto mb-10 max-w-2xl break-keep text-lg font-medium leading-relaxed text-slate-500 md:mx-0 md:text-xl">
          진단부터 워크숍, 내보내기까지 한 흐름으로 이어집니다. 오늘 작업을 바로 시작해보세요.
        </p>

        <button
          onClick={() => setIsDiagnosisOpen(true)}
          className="group mx-auto flex w-full items-center justify-center gap-3 px-8 py-5 text-lg font-extrabold md:mx-0 md:w-auto clay-btn-primary shimmer"
        >
          무료로 전공 적합도 진단 받기
          <ArrowRight className="transition-transform group-hover:translate-x-1" />
        </button>
      </motion.div>

      <div className="mb-16 grid grid-cols-1 gap-8 lg:grid-cols-3">
        <motion.div
          initial={{ opacity: 0, y: 30 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, delay: 0.2, ease: 'easeOut' }}
          className="relative flex flex-col justify-center overflow-hidden p-8 sm:p-10 lg:col-span-2 clay-card"
        >
          <div className="absolute -mr-20 -mt-20 h-64 w-64 rounded-full bg-blue-100/30 blur-3xl" />
          <div className="relative z-10">
            <div className="mb-8 flex items-center justify-between">
              <div>
                <h2 className="mb-2 text-2xl font-extrabold text-slate-800 sm:text-3xl">나의 작업 진행도</h2>
                <p className="text-lg font-medium text-slate-500">현재 상태: {stats.level}</p>
              </div>
              <div className="flex h-16 w-16 items-center justify-center rounded-3xl border border-white/50 bg-gradient-to-br from-yellow-50 to-yellow-100 text-4xl shadow-inner sm:h-20 sm:w-20">
                🌟
              </div>
            </div>

            <div className="space-y-4">
              <div className="flex justify-between text-sm font-extrabold text-slate-700 sm:text-base">
                <span>Lv.1</span>
                <span className="text-blue-600">
                  진행도 {stats.completion_rate}% · 작성 보고서 {stats.report_count}개
                </span>
              </div>
              <div className="h-8 w-full rounded-full border border-slate-200/50 bg-slate-100 p-1.5 shadow-inner sm:h-10">
                <div
                  className="relative h-full overflow-hidden rounded-full bg-gradient-to-r from-blue-400 to-blue-500 shadow-[inset_0_-2px_4px_rgba(0,0,0,0.1),0_2px_4px_rgba(59,130,246,0.3)] transition-all duration-1000"
                  style={{ width: `${Math.max(stats.completion_rate, 5)}%` }}
                >
                  <div className="absolute left-0 right-0 top-0 h-1/2 rounded-t-full bg-gradient-to-b from-white/40 to-transparent" />
                </div>
              </div>
            </div>
          </div>
        </motion.div>

        <motion.button
          type="button"
          initial={{ opacity: 0, y: 30 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, delay: 0.3, ease: 'easeOut' }}
          onClick={() => setIsDiagnosisOpen(true)}
          className="group flex cursor-pointer flex-col items-center justify-center p-8 text-center transition-colors hover:bg-blue-50/30 sm:p-10 clay-card"
        >
          <div className="mb-6 flex h-20 w-20 items-center justify-center rounded-3xl border border-white/50 bg-gradient-to-br from-mint/20 to-mint/10 text-mint shadow-inner transition-transform duration-300 group-hover:scale-110 sm:h-24 sm:w-24">
            <Zap size={40} />
          </div>
          <h3 className="mb-3 text-xl font-extrabold text-slate-800 sm:text-2xl">빠른 진단 시작</h3>
          <p className="text-sm font-medium leading-relaxed text-slate-500 sm:text-base">
            전공 입력과 PDF 업로드만 하면
            <br />
            바로 워크숍으로 연결됩니다.
          </p>
        </motion.button>
      </div>

      <motion.div
        initial={{ opacity: 0, y: 30 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.6, delay: 0.4, ease: 'easeOut' }}
      >
        <div className="mb-8 flex items-start justify-between gap-4 px-2 sm:items-center">
          <h2 className="break-keep text-2xl font-extrabold text-slate-800 sm:text-3xl">지금 참고하기 좋은 입시 트렌드</h2>
          <button
            onClick={() => navigate('/trends')}
            className="mt-1 flex shrink-0 items-center gap-1 whitespace-nowrap text-sm font-extrabold text-blue-500 transition-colors hover:text-blue-600 sm:mt-0 sm:text-base"
          >
            전체보기
            <ArrowRight size={16} />
          </button>
        </div>

        <div className="-mx-2 flex snap-x gap-6 overflow-x-auto px-2 pb-8 hide-scrollbar">
          {trends.map((trend) => (
            <button
              type="button"
              key={trend.id}
              onClick={() => {
                navigate('/trends');
                toast('트렌드 페이지에서 상세 자료를 확인하세요.', { icon: '📌' });
              }}
              className="group flex min-w-[280px] snap-start cursor-pointer flex-col p-8 text-left transition-colors hover:border-blue-200 md:min-w-[320px] clay-card"
            >
              <div className="mb-6 flex h-16 w-16 items-center justify-center rounded-3xl border border-white/50 bg-slate-50 text-4xl shadow-inner transition-transform duration-300 group-hover:-translate-y-2 sm:h-20 sm:w-20">
                {trend.icon}
              </div>
              <div className="mb-4 inline-block w-fit rounded-xl bg-slate-100 px-3 py-1.5 text-xs font-extrabold text-slate-600 sm:text-sm">
                {trend.tag}
              </div>
              <h3 className="text-lg font-extrabold leading-snug text-slate-800 transition-colors group-hover:text-blue-600 sm:text-xl">
                {trend.title}
              </h3>
            </button>
          ))}
        </div>
      </motion.div>

      <DiagnosisModal isOpen={isDiagnosisOpen} onClose={() => setIsDiagnosisOpen(false)} />
    </div>
  );
}
