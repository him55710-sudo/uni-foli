import React, { useState } from 'react';
import { useAuth } from '../contexts/AuthContext';
import { motion } from 'motion/react';
import { Zap, BookOpen, Search, Flame, ArrowRight } from 'lucide-react';
import { DiagnosisModal } from '../components/DiagnosisModal';
import { api } from '../lib/api';

const trends = [
  { id: 1, icon: '📚', title: '컴공 필독서: AI의 미래', tag: '도서 추천' },
  { id: 2, icon: '🔍', title: '2025 수시 핵심 요약', tag: '입시 뉴스' },
  { id: 3, icon: '🔥', title: '연세대 합격생 생기부', tag: '합격 가이드' },
  { id: 4, icon: '💡', title: '기후 변화와 경제학', tag: '탐구 주제' },
];

export function Dashboard() {
  const { user } = useAuth();
  const [isDiagnosisOpen, setIsDiagnosisOpen] = useState(false);
  const [stats, setStats] = useState({
    report_count: 0,
    level: '로딩 중...',
    completion_rate: 0
  });

  React.useEffect(() => {
    if (user) {
      api.get('/api/v1/projects/user/stats').then(data => {
        setStats(data);
      }).catch(err => {
        console.error("Failed to load stats:", err);
        setStats({ report_count: 0, level: '탐구의 시작 🐣', completion_rate: 0 });
      });
    }
  }, [user]);

  return (
    <div className="max-w-5xl mx-auto pb-12 px-4 sm:px-6 lg:px-8">
      {/* Hero Section */}
      <motion.div 
        initial={{ opacity: 0, y: 30 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.6, ease: "easeOut" }}
        className="mb-12 text-center md:text-left pt-8 sm:pt-12"
      >
        <div className="inline-block mb-6">
          <div className="clay-card px-6 py-2.5 bg-gradient-to-r from-red-50 to-red-100/50 border-red-200 text-red-600 font-extrabold text-sm md:text-base rounded-full shadow-sm">
            🚨 기말고사 및 세특 마감 D-15
          </div>
        </div>
        
        <h1 className="text-4xl md:text-5xl lg:text-6xl font-extrabold text-slate-800 tracking-tight mb-6 leading-tight break-keep">
          막막한 생기부 탐구, <br className="hidden md:block" />
          <span className="text-transparent bg-clip-text bg-gradient-to-r from-blue-500 to-blue-400">AI가 학교 제출용 보고서로</span><br className="hidden md:block" /> 완벽하게 완성해 드립니다.
        </h1>
        
        <p className="text-lg md:text-xl text-slate-500 mb-10 max-w-2xl mx-auto md:mx-0 leading-relaxed font-medium break-keep">
          3중 AI의 팩트 폭행 진단부터, 절대 깨지지 않는 HWPX 자동 완성까지.<br className="hidden md:block" /> 당신의 대학 입시를 바꿀 든든한 AI 멘토, 폴리오.
        </p>
        
        <button onClick={() => setIsDiagnosisOpen(true)} className="clay-btn-primary w-full md:w-auto px-8 py-5 text-lg font-extrabold flex items-center justify-center gap-3 mx-auto md:mx-0 group shimmer">
          무료로 내 생기부 위험도 진단받기 🚨
          <ArrowRight className="group-hover:translate-x-1 transition-transform" />
        </button>
      </motion.div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8 mb-16">
        {/* Gamification Section (Progress) */}
        <motion.div 
          initial={{ opacity: 0, y: 30 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, delay: 0.2, ease: "easeOut" }}
          className="lg:col-span-2 clay-card p-8 sm:p-10 relative overflow-hidden flex flex-col justify-center"
        >
          <div className="absolute top-0 right-0 w-64 h-64 bg-blue-100/30 rounded-full blur-3xl -mr-20 -mt-20" />
          
          <div className="relative z-10">
            <div className="flex items-center justify-between mb-8">
              <div>
                <h2 className="text-2xl sm:text-3xl font-extrabold text-slate-800 mb-2">내 생기부 진화도</h2>
                <p className="text-slate-500 font-medium text-lg">현재 레벨: {stats.level}</p>
              </div>
              <div className="w-16 h-16 sm:w-20 sm:h-20 bg-gradient-to-br from-yellow-50 to-yellow-100 rounded-3xl flex items-center justify-center text-4xl shadow-inner border border-white/50">
                🐣
              </div>
            </div>

            <div className="space-y-4">
              <div className="flex justify-between text-sm sm:text-base font-extrabold text-slate-700">
                <span>Lv.1</span>
                <span className="text-blue-600">완성도 {stats.completion_rate}% (작성한 보고서: {stats.report_count}개)</span>
              </div>
              
              {/* 3D Jelly Progress Bar */}
              <div className="h-8 sm:h-10 w-full bg-slate-100 rounded-full p-1.5 shadow-inner border border-slate-200/50">
                <div 
                  className="h-full bg-gradient-to-r from-blue-400 to-blue-500 rounded-full shadow-[inset_0_-2px_4px_rgba(0,0,0,0.1),0_2px_4px_rgba(59,130,246,0.3)] relative overflow-hidden transition-all duration-1000"
                  style={{ width: `${Math.max(stats.completion_rate, 5)}%` }}
                >
                  {/* Highlight for jelly effect */}
                  <div className="absolute top-0 left-0 right-0 h-1/2 bg-gradient-to-b from-white/40 to-transparent rounded-t-full" />
                </div>
              </div>
            </div>
          </div>
        </motion.div>

        {/* Quick Action */}
        <motion.div 
          initial={{ opacity: 0, y: 30 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, delay: 0.3, ease: "easeOut" }}
          className="clay-card p-8 sm:p-10 flex flex-col items-center justify-center text-center cursor-pointer group hover:bg-blue-50/30 transition-colors"
        >
          <div className="w-20 h-20 sm:w-24 sm:h-24 bg-gradient-to-br from-mint/20 to-mint/10 rounded-3xl flex items-center justify-center text-mint mb-6 shadow-inner border border-white/50 group-hover:scale-110 transition-transform duration-300">
            <Zap size={40} />
          </div>
          <h3 className="text-xl sm:text-2xl font-extrabold text-slate-800 mb-3">새 탐구 시작</h3>
          <p className="text-slate-500 text-sm sm:text-base font-medium leading-relaxed">Poli와 대화하며<br/>아이디어를 구체화해요</p>
        </motion.div>
      </div>

      {/* Content Feed */}
      <motion.div
        initial={{ opacity: 0, y: 30 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.6, delay: 0.4, ease: "easeOut" }}
      >
        <div className="flex items-start sm:items-center justify-between mb-8 px-2 gap-4">
          <h2 className="text-2xl sm:text-3xl font-extrabold text-slate-800 break-keep">교수님이 주목하는 요즘 입시 트렌드</h2>
          <button className="text-sm sm:text-base font-extrabold text-blue-500 hover:text-blue-600 transition-colors flex items-center gap-1 shrink-0 whitespace-nowrap mt-1 sm:mt-0">
            더보기 <ArrowRight size={16} />
          </button>
        </div>

        {/* Horizontal Scroll */}
        <div className="flex gap-6 overflow-x-auto pb-8 snap-x px-2 -mx-2 hide-scrollbar">
          {trends.map((trend) => (
            <div 
              key={trend.id} 
              className="min-w-[280px] md:min-w-[320px] clay-card p-8 snap-start cursor-pointer group flex flex-col hover:border-blue-200 transition-colors"
            >
              <div className="w-16 h-16 sm:w-20 sm:h-20 bg-slate-50 rounded-3xl flex items-center justify-center text-4xl mb-6 shadow-inner border border-white/50 group-hover:-translate-y-2 transition-transform duration-300">
                {trend.icon}
              </div>
              <div className="inline-block px-3 py-1.5 bg-slate-100 text-slate-600 text-xs sm:text-sm font-extrabold rounded-xl mb-4 w-fit">
                {trend.tag}
              </div>
              <h3 className="font-extrabold text-slate-800 text-lg sm:text-xl leading-snug group-hover:text-blue-600 transition-colors">
                {trend.title}
              </h3>
            </div>
          ))}
        </div>
      </motion.div>

      <DiagnosisModal isOpen={isDiagnosisOpen} onClose={() => setIsDiagnosisOpen(false)} />
    </div>
  );
}
