import React from 'react';
import { Download, Filter, FileText } from 'lucide-react';
import { useAuth } from '../contexts/AuthContext';

const archives = [
  { id: 1, title: '생명과학 II - 유전자 가위 기술의 윤리적 쟁점', subject: '생명과학', date: '2023.11.15', emoji: '🧬', color: 'bg-emerald-100' },
  { id: 2, title: '확률과 통계 - 빅데이터를 활용한 전염병 예측 모델', subject: '수학', date: '2023.10.20', emoji: '📊', color: 'bg-blue-100' },
  { id: 3, title: '영어 독해와 작문 - AI 번역기의 한계와 인간의 역할', subject: '영어', date: '2023.09.05', emoji: '📚', color: 'bg-rose-100' },
  { id: 4, title: '한국사 - 조선 후기 실학사상의 현대적 의의', subject: '역사', date: '2023.07.12', emoji: '📜', color: 'bg-amber-100' },
  { id: 5, title: '물리학 I - 양자역학의 기본 개념과 응용', subject: '물리', date: '2023.06.28', emoji: '⚛️', color: 'bg-violet-100' },
];

export function Archive() {
  const { user } = useAuth();

  return (
    <div className="max-w-7xl mx-auto pb-24 px-4 sm:px-6 lg:px-8">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-8">
        <div>
          <h1 className="text-3xl font-extrabold text-slate-800">{user?.displayName || '학생'}님의 탐구 포트폴리오</h1>
          <p className="text-slate-500 font-medium mt-2">지금까지 완성한 보고서들을 한눈에 확인하세요.</p>
        </div>
        
        <button className="flex items-center gap-2 px-4 py-2.5 bg-white border border-slate-200 rounded-xl text-slate-600 font-bold hover:bg-slate-50 transition-colors shadow-sm self-start sm:self-auto">
          <Filter size={18} />
          <span>최신순</span>
        </button>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6">
        {archives.map((item) => (
          <div key={item.id} className="clay-card group relative overflow-hidden flex flex-col cursor-pointer">
            {/* Thumbnail */}
            <div className={`relative w-full pt-[75%] overflow-hidden rounded-t-3xl ${item.color} flex items-center justify-center`}>
              <div className="absolute inset-0 opacity-20 bg-[url('https://www.transparenttextures.com/patterns/cubes.png')] mix-blend-overlay" />
              <span className="text-7xl drop-shadow-xl group-hover:scale-110 transition-transform duration-500 absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2">{item.emoji}</span>
            </div>

            {/* Info */}
            <div className="p-6 flex-1 flex flex-col bg-white">
              <div className="flex items-center justify-between mb-3">
                <span className="px-3 py-1 bg-slate-100 text-slate-600 text-xs font-extrabold rounded-lg">{item.subject}</span>
                <span className="text-xs font-bold text-slate-400">{item.date}</span>
              </div>
              <h3 className="text-lg font-extrabold text-slate-800 leading-snug line-clamp-2 mb-4">{item.title}</h3>
            </div>

            {/* Hover Slide Up Buttons */}
            <div className="absolute bottom-0 left-0 w-full p-4 bg-white/90 backdrop-blur-md border-t border-slate-100 translate-y-full group-hover:translate-y-0 transition-transform duration-300 flex gap-2">
              <button className="flex-1 bg-blue-500 hover:bg-blue-600 text-white py-2.5 rounded-xl font-bold text-sm flex items-center justify-center gap-1.5 transition-colors shadow-sm">
                <FileText size={16} /> HWPX
              </button>
              <button className="flex-1 bg-slate-800 hover:bg-slate-900 text-white py-2.5 rounded-xl font-bold text-sm flex items-center justify-center gap-1.5 transition-colors shadow-sm">
                <Download size={16} /> PDF
              </button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
