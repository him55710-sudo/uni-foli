import React from 'react';
import { motion } from 'framer-motion';
import { Calendar, CheckCircle2, Circle, Clock, Sparkles, TrendingUp, Target } from 'lucide-react';
import { SurfaceCard } from '../primitives';

interface TimelineEvent {
  period: string;
  title: string;
  description: string;
  status: 'completed' | 'ongoing' | 'upcoming';
  type: 'academic' | 'activity' | 'career';
}

interface TimelineProps {
  grade: string;
  events?: TimelineEvent[];
}

const GRADE_MAP: Record<string, string> = {
  '1': '고등학교 1학년',
  '2': '고등학교 2학년',
  '3': '고등학교 3학년',
  'm1': '중학교 1학년',
  'm2': '중학교 2학년',
  'm3': '중학교 3학년',
};

const DEFAULT_EVENTS: Record<string, TimelineEvent[]> = {
  '1': [
    { period: '1학기', title: '기초 탐구 역량 형성', description: '진로 탐색 및 핵심 과목 기초 다지기', status: 'completed', type: 'academic' },
    { period: '2학기', title: '관심 분야 심화', description: '동아리 활동 및 주제 탐구 보고서 작성', status: 'ongoing', type: 'activity' },
    { period: '겨울방학', title: '심화 로드맵 구축', description: '2학년 선택 과목 연계 심화 탐구 계획', status: 'upcoming', type: 'career' },
  ],
  '2': [
    { period: '1학년', title: '전공 기초 확립', description: '기초 과목 이수 및 진로 방향 설정 완료', status: 'completed', type: 'career' },
    { period: '2학년 1학기', title: '전공 적합성 심화', description: '심화 선택 과목 및 실험/실습 활동', status: 'completed', type: 'academic' },
    { period: '2학년 2학기', title: '학업 역량 증명', description: '융합 탐구 및 교과 세특 고도화', status: 'ongoing', type: 'activity' },
    { period: '겨울방학', title: '3학년 전략 수립', description: '학종 마무리를 위한 핵심 활동 선별', status: 'upcoming', type: 'career' },
  ],
  '3': [
    { period: '1, 2학년', title: '역량 축적기', description: '일관된 진로 방향에 따른 활동 전개', status: 'completed', type: 'activity' },
    { period: '3학년 1학기', title: '역량의 완성', description: '최종 학업 역량 및 리더십 입증', status: 'ongoing', type: 'academic' },
    { period: '여름방학', title: '원서 전략 수립', description: '학생부 분석 기반 최적 대학 매칭', status: 'upcoming', type: 'career' },
    { period: '2학기', title: '면접 및 파이널', description: '제시문/기반 면접 완벽 대비', status: 'upcoming', type: 'activity' },
  ],
};

export const Timeline: React.FC<TimelineProps> = ({ grade, events }) => {
  const displayGrade = GRADE_MAP[grade] || '전체 학년';
  const displayEvents = events || DEFAULT_EVENTS[grade] || DEFAULT_EVENTS['1'];

  return (
    <div className="space-y-12 py-8">
      {/* Timeline Header */}
      <div className="flex items-center justify-between border-b border-slate-800 pb-8">
        <div className="flex items-center gap-4">
          <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-indigo-500/10 text-indigo-400 border border-indigo-500/20">
            <Calendar size={24} />
          </div>
          <div>
            <h4 className="text-2xl font-black text-white italic">{displayGrade}</h4>
            <div className="flex items-center gap-2">
              <Sparkles size={14} className="text-amber-500" />
              <p className="text-[10px] font-black text-slate-500 uppercase tracking-[0.3em]">Strategic Growth Journey</p>
            </div>
          </div>
        </div>
        <div className="hidden md:flex items-center gap-6">
          <div className="flex items-center gap-2">
            <div className="w-2 h-2 rounded-full bg-blue-500" />
            <span className="text-[10px] font-bold text-slate-400 uppercase">Completed</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-2 h-2 rounded-full bg-indigo-500 animate-pulse" />
            <span className="text-[10px] font-bold text-slate-400 uppercase">Ongoing</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-2 h-2 rounded-full bg-slate-700" />
            <span className="text-[10px] font-bold text-slate-400 uppercase">Upcoming</span>
          </div>
        </div>
      </div>

      <div className="relative space-y-12 before:absolute before:left-[24px] before:top-4 before:h-[calc(100%-32px)] before:w-px before:bg-gradient-to-b before:from-indigo-500 before:via-indigo-500/50 before:to-transparent">
        {displayEvents.map((event, index) => (
          <motion.div
            key={index}
            initial={{ opacity: 0, x: -20 }}
            whileInView={{ opacity: 1, x: 0 }}
            viewport={{ once: true }}
            transition={{ delay: index * 0.1, duration: 0.6 }}
            className="relative pl-16 group"
          >
            {/* Node Indicator */}
            <div className={`absolute left-0 top-0 flex h-12 w-12 items-center justify-center rounded-full border-[6px] border-slate-950 bg-slate-900 z-10 transition-all duration-500 group-hover:scale-110 ${
              event.status === 'completed' ? 'text-blue-500' : 
              event.status === 'ongoing' ? 'text-indigo-400 shadow-[0_0_15px_rgba(99,102,241,0.3)]' : 
              'text-slate-700'
            }`}>
              {event.status === 'completed' ? <CheckCircle2 size={24} fill="currentColor" className="text-blue-500/10" /> : 
               event.status === 'ongoing' ? <div className="relative"><Clock size={20} /><div className="absolute inset-0 animate-ping opacity-20"><Clock size={20} /></div></div> : 
               <div className="w-2 h-2 rounded-full bg-current" />}
            </div>

            {/* Event Content */}
            <SurfaceCard className={`relative overflow-hidden border-slate-800 bg-slate-900/40 backdrop-blur-xl p-8 hover:border-indigo-500/30 transition-all duration-500 ${
              event.status === 'ongoing' ? 'ring-1 ring-indigo-500/20' : ''
            }`}>
              {/* Decorative accent */}
              <div className={`absolute top-0 right-0 w-32 h-32 -mr-16 -mt-16 opacity-10 rounded-full blur-3xl ${
                event.type === 'academic' ? 'bg-blue-500' :
                event.type === 'activity' ? 'bg-violet-500' :
                'bg-emerald-500'
              }`} />

              <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 mb-4">
                <div className="flex items-center gap-3">
                  <span className={`text-[11px] font-black uppercase tracking-widest px-3 py-1 rounded-lg border ${
                    event.type === 'academic' ? 'bg-blue-500/10 text-blue-400 border-blue-500/20' :
                    event.type === 'activity' ? 'bg-violet-500/10 text-violet-400 border-violet-500/20' :
                    'bg-emerald-500/10 text-emerald-400 border-emerald-500/20'
                  }`}>
                    {event.period}
                  </span>
                  <div className="h-1 w-1 rounded-full bg-slate-700" />
                  <span className="text-[10px] font-black text-slate-500 uppercase tracking-tighter">
                    {event.type === 'academic' ? 'Academic Mastery' : event.type === 'activity' ? 'Extracurricular' : 'Career Strategy'}
                  </span>
                </div>
                
                {event.status === 'ongoing' && (
                  <div className="flex items-center gap-2 px-3 py-1 rounded-full bg-indigo-500/10 border border-indigo-500/20">
                    <TrendingUp size={12} className="text-indigo-400" />
                    <span className="text-[10px] font-black text-indigo-400 uppercase">Focusing</span>
                  </div>
                )}
              </div>

              <div className="flex items-start gap-4">
                <div className="hidden sm:block mt-1">
                  <Target size={20} className="text-slate-700 group-hover:text-indigo-400 transition-colors" />
                </div>
                <div>
                  <h5 className="text-xl font-black text-white group-hover:text-indigo-300 transition-colors mb-2 tracking-tight">
                    {event.title}
                  </h5>
                  <p className="text-slate-400 font-medium leading-relaxed max-w-2xl italic">
                    {event.description}
                  </p>
                </div>
              </div>
            </SurfaceCard>
          </motion.div>
        ))}
      </div>
    </div>
  );
};

