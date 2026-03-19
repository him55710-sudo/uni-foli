import React, { useState } from 'react';
import { motion } from 'motion/react';
import { BookOpen, Newspaper, GraduationCap, Lightbulb, ChevronDown } from 'lucide-react';

const trends = [
  { id: 1, type: '도서 추천', icon: BookOpen, title: '컴퓨터공학과 필독서: 인공지능의 미래', desc: '서울대 컴공 합격생 80%가 읽은 그 책! AI 윤리와 기술 발전의 딜레마를 다룹니다.', color: 'bg-primary-light/30 text-primary-dark' },
  { id: 2, type: '입시 뉴스', icon: Newspaper, title: '2025학년도 수시 전형 핵심 변화 요약', desc: '자소서 폐지 이후 생기부 세특의 중요성이 더욱 커졌습니다. 대비 전략을 확인하세요.', color: 'bg-secondary-light/30 text-secondary-dark' },
  { id: 3, type: '합격 가이드', icon: GraduationCap, title: '연세대 HASS 합격생의 생기부 분석', desc: '융합인재학부 합격생은 어떤 활동으로 전공적합성을 어필했을까요? 실제 사례 대공개.', color: 'bg-safe/20 text-safe' },
  { id: 4, type: '탐구 아이디어', icon: Lightbulb, title: '기후 변화와 경제학의 만남', desc: '탄소 배출권 거래제가 시장 경제에 미치는 영향. 상경계열 지망생을 위한 탐구 주제 추천.', color: 'bg-yellow-100 text-yellow-700' },
  { id: 5, type: '도서 추천', icon: BookOpen, title: '의예과 추천 도서: 숨결이 바람 될 때', desc: '의사로서의 사명감과 생명의 존엄성에 대한 깊은 성찰을 보여주는 에세이.', color: 'bg-primary-light/30 text-primary-dark' },
  { id: 6, type: '입시 뉴스', icon: Newspaper, title: '첨단학과 신설 트렌드 분석', desc: '반도체, AI, 배터리 관련 학과 정원 확대! 나에게 맞는 첨단학과는 어디일까?', color: 'bg-secondary-light/30 text-secondary-dark' },
];

const filters = ['전체', '내 전공 (컴퓨터공학)', '도서 추천', '합격 가이드', '탐구 아이디어'];

export function Trends() {
  const [activeFilter, setActiveFilter] = useState('전체');

  return (
    <div className="max-w-7xl mx-auto pb-24 px-4 sm:px-6 lg:px-8">
      {/* Header */}
      <motion.div 
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        className="mb-8"
      >
        <h1 className="text-3xl sm:text-4xl font-extrabold text-slate-800 tracking-tight mb-2">
          입시 트렌드 💡
        </h1>
        <p className="text-slate-500 text-base sm:text-lg font-medium">
          나의 전공에 꼭 맞는 알짜배기 정보만 모았어요.
        </p>
      </motion.div>

      {/* Filters */}
      <motion.div 
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.1 }}
        className="flex flex-wrap gap-3 mb-10"
      >
        {filters.map((filter) => (
          <button
            key={filter}
            onClick={() => setActiveFilter(filter)}
            className={`px-5 py-2.5 rounded-full text-sm font-extrabold transition-all shadow-sm ${
              activeFilter === filter 
                ? 'bg-slate-800 text-white shadow-md scale-105' 
                : 'bg-white text-slate-600 border border-slate-200 hover:border-blue-300 hover:bg-blue-50 hover:text-blue-600'
            }`}
          >
            {filter}
          </button>
        ))}
        <button className="px-5 py-2.5 rounded-full text-sm font-extrabold bg-slate-50 text-slate-400 border border-dashed border-slate-300 hover:bg-slate-100 hover:text-slate-600 transition-colors flex items-center gap-2">
          관심 전공 추가 <ChevronDown size={16} />
        </button>
      </motion.div>

      {/* Masonry Grid (Simulated with columns) */}
      <div className="columns-1 sm:columns-2 lg:columns-3 gap-6 space-y-6">
        {trends.map((item, index) => (
          <motion.div
            key={item.id}
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ delay: index * 0.05 }}
            className="break-inside-avoid clay-card p-6 sm:p-8 cursor-pointer group flex flex-col h-full"
          >
            <div className={`inline-flex items-center gap-2 px-3 py-1.5 rounded-xl text-xs font-extrabold mb-5 w-fit ${
              item.type === '도서 추천' ? 'bg-blue-50 text-blue-600 border border-blue-100' :
              item.type === '입시 뉴스' ? 'bg-emerald-50 text-emerald-600 border border-emerald-100' :
              item.type === '합격 가이드' ? 'bg-indigo-50 text-indigo-600 border border-indigo-100' :
              'bg-amber-50 text-amber-600 border border-amber-100'
            }`}>
              <item.icon size={16} />
              {item.type}
            </div>
            <h3 className="text-xl font-extrabold text-slate-800 mb-3 leading-snug group-hover:text-blue-600 transition-colors">
              {item.title}
            </h3>
            <p className="text-slate-600 text-[15px] leading-relaxed font-medium flex-1">
              {item.desc}
            </p>
            
            {/* Read More Link */}
            <div className="mt-6 pt-5 border-t border-slate-100 flex items-center justify-between">
              <span className="text-xs text-slate-400 font-bold bg-slate-50 px-2.5 py-1 rounded-lg">조회수 1.2k</span>
              <span className="text-sm font-extrabold text-slate-800 group-hover:text-blue-600 transition-colors flex items-center gap-1.5 bg-white px-3 py-1.5 rounded-xl border border-slate-100 group-hover:border-blue-200 shadow-sm">
                자세히 보기 <span className="group-hover:translate-x-1 transition-transform">→</span>
              </span>
            </div>
          </motion.div>
        ))}
      </div>
    </div>
  );
}
