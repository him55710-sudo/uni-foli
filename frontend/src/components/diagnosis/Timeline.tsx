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
    <div className="space-y-12 py-4">
      {/* Timeline Header */}
      <div className="flex items-center justify-between border-b border-slate-100 pb-8">
        <div className="flex items-center gap-4">
          <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-indigo-50 text-indigo-600 border border-indigo-100 shadow-sm">
            <Calendar size={24} />
          </div>
          <div>
            <h4 className="text-xl font-bold text-slate-900">{displayGrade}</h4>
            <div className="flex items-center gap-2">
              <Sparkles size={14} className="text-amber-500" />
              <p className="text-[10px] font-bold text-slate-400 uppercase tracking-wider">Strategic Growth Journey</p>
            </div>
          </div>
        </div>
      </div>

      <div className="relative space-y-10 before:absolute before:left-[24px] before:top-4 before:h-[calc(100%-32px)] before:w-px before:bg-slate-200">
        {displayEvents.map((event, index) => (
          <motion.div
            key={index}
            initial={{ opacity: 0, x: -10 }}
            whileInView={{ opacity: 1, x: 0 }}
            viewport={{ once: true }}
            transition={{ delay: index * 0.1, duration: 0.5 }}
            className="relative pl-14 group"
          >
            {/* Node Indicator */}
            <div className={`absolute left-0 top-0 flex h-12 w-12 items-center justify-center rounded-full border-4 border-white z-10 transition-all duration-300 shadow-sm ${
              event.status === 'completed' ? 'bg-blue-50 text-blue-600' : 
              event.status === 'ongoing' ? 'bg-indigo-50 text-indigo-600 ring-2 ring-indigo-100' : 
              'bg-slate-50 text-slate-300'
            }`}>
              {event.status === 'completed' ? <CheckCircle2 size={20} /> : 
               event.status === 'ongoing' ? <Clock size={20} className="animate-spin-slow" /> : 
               <Circle size={12} fill="currentColor" />}
            </div>

            {/* Event Content */}
            <div className={`relative p-6 rounded-2xl border transition-all duration-300 ${
              event.status === 'ongoing' 
              ? 'bg-white border-indigo-200 shadow-md ring-1 ring-indigo-50' 
              : 'bg-slate-50/50 border-slate-100'
            }`}>
              <div className="flex flex-col gap-3">
                <div className="flex items-center gap-3">
                  <span className={`text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded border ${
                    event.type === 'academic' ? 'bg-blue-50 text-blue-600 border-blue-100' :
                    event.type === 'activity' ? 'bg-violet-50 text-violet-600 border-violet-100' :
                    'bg-emerald-50 text-emerald-600 border-emerald-100'
                  }`}>
                    {event.period}
                  </span>
                  <span className="text-[10px] font-medium text-slate-400 uppercase tracking-tight">
                    {event.type === 'academic' ? 'Academic Mastery' : event.type === 'activity' ? 'Extracurricular' : 'Career Strategy'}
                  </span>
                </div>
                
                <div>
                  <h5 className="text-base font-bold text-slate-900 mb-1">
                    {event.title}
                  </h5>
                  <p className="text-slate-600 text-sm font-medium leading-relaxed">
                    {event.description}
                  </p>
                </div>
              </div>
            </div>
          </motion.div>
        ))}
      </div>
    </div>
  );
};

