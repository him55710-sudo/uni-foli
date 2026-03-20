import React, { useMemo, useState } from 'react';
import { motion, AnimatePresence } from 'motion/react';
import { BookOpen, Newspaper, GraduationCap, Lightbulb, ChevronDown, X } from 'lucide-react';
import toast from 'react-hot-toast';
import { useNavigate } from 'react-router-dom';

type TrendType = '도서 추천' | '입시 이슈' | '합격 가이드' | '탐구 아이디어';

interface TrendItem {
  id: number;
  type: TrendType;
  icon: React.ComponentType<{ size?: number }>;
  title: string;
  desc: string;
}

const trendItems: TrendItem[] = [
  {
    id: 1,
    type: '도서 추천',
    icon: BookOpen,
    title: '컴퓨터공학과를 위한 AI 윤리 필독서',
    desc: '기술 발전 속도와 사회적 책임을 함께 다루는 도서 큐레이션입니다.',
  },
  {
    id: 2,
    type: '입시 이슈',
    icon: Newspaper,
    title: '2026 수시 전형 변화 핵심 요약',
    desc: '학생부 세부능력특기사항 반영 방식이 바뀌는 포인트를 빠르게 정리했습니다.',
  },
  {
    id: 3,
    type: '합격 가이드',
    icon: GraduationCap,
    title: '연세대 HASS 합격생 탐구 보고서 구조',
    desc: '문제 정의부터 시사점까지 합격 사례의 문단 흐름을 분석해 제공합니다.',
  },
  {
    id: 4,
    type: '탐구 아이디어',
    icon: Lightbulb,
    title: '기후 변화와 경제를 연결한 융합 탐구',
    desc: '탄소배출권 시장과 청소년 소비 패턴을 연계한 주제 설계를 제안합니다.',
  },
  {
    id: 5,
    type: '도서 추천',
    icon: BookOpen,
    title: '의생명 계열 학생을 위한 추천 읽기 목록',
    desc: '생명윤리, 임상 커뮤니케이션, 데이터 해석 관점을 함께 다루는 리스트입니다.',
  },
  {
    id: 6,
    type: '입시 이슈',
    icon: Newspaper,
    title: '첨단학과 정원 및 경쟁률 추이',
    desc: '반도체·AI·배터리 관련 학과의 최근 3개년 경쟁률 변화를 비교합니다.',
  },
];

const baseFilters = ['전체', '도서 추천', '입시 이슈', '합격 가이드', '탐구 아이디어'] as const;

export function Trends() {
  const navigate = useNavigate();
  const [activeFilter, setActiveFilter] = useState<string>('전체');
  const [extraFilters, setExtraFilters] = useState<string[]>([]);
  const [selectedTrend, setSelectedTrend] = useState<TrendItem | null>(null);

  const allFilters = useMemo(() => [...baseFilters, ...extraFilters], [extraFilters]);

  const visibleItems = useMemo(() => {
    if (activeFilter === '전체') return trendItems;
    return trendItems.filter((item) => item.type === activeFilter);
  }, [activeFilter]);

  const handleAddFilter = () => {
    const input = window.prompt('관심 전공 키워드를 입력해주세요. (예: 컴퓨터공학)');
    const value = input?.trim();
    if (!value) return;
    if (extraFilters.includes(value)) {
      toast('이미 추가된 필터입니다.', { icon: 'ℹ️' });
      return;
    }
    setExtraFilters((prev) => [...prev, value]);
    setActiveFilter('전체');
    toast.success(`"${value}" 필터를 추가했습니다.`);
  };

  return (
    <div className="mx-auto max-w-7xl px-4 pb-24 sm:px-6 lg:px-8">
      <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} className="mb-8">
        <h1 className="mb-2 text-3xl font-extrabold tracking-tight text-slate-800 sm:text-4xl">입시 트렌드 허브</h1>
        <p className="text-base font-medium text-slate-500 sm:text-lg">
          전공과 목표에 맞는 자료를 골라 보고서 주제로 바로 연결하세요.
        </p>
      </motion.div>

      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.1 }}
        className="mb-10 flex flex-wrap gap-3"
      >
        {allFilters.map((filter) => (
          <button
            key={filter}
            onClick={() => setActiveFilter(filter)}
            className={`rounded-full px-5 py-2.5 text-sm font-extrabold shadow-sm transition-all ${
              activeFilter === filter
                ? 'scale-105 bg-slate-800 text-white shadow-md'
                : 'border border-slate-200 bg-white text-slate-600 hover:border-blue-300 hover:bg-blue-50 hover:text-blue-600'
            }`}
          >
            {filter}
          </button>
        ))}
        <button
          onClick={handleAddFilter}
          className="flex items-center gap-2 rounded-full border border-dashed border-slate-300 bg-slate-50 px-5 py-2.5 text-sm font-extrabold text-slate-400 transition-colors hover:bg-slate-100 hover:text-slate-600"
        >
          관심 전공 추가 <ChevronDown size={16} />
        </button>
      </motion.div>

      <div className="columns-1 gap-6 space-y-6 sm:columns-2 lg:columns-3">
        {visibleItems.map((item, index) => (
          <motion.button
            type="button"
            key={item.id}
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ delay: index * 0.05 }}
            onClick={() => setSelectedTrend(item)}
            className="group flex h-full w-full cursor-pointer flex-col p-6 text-left break-inside-avoid sm:p-8 clay-card"
          >
            <div
              className={`mb-5 inline-flex w-fit items-center gap-2 rounded-xl border px-3 py-1.5 text-xs font-extrabold ${
                item.type === '도서 추천'
                  ? 'border-blue-100 bg-blue-50 text-blue-600'
                  : item.type === '입시 이슈'
                    ? 'border-emerald-100 bg-emerald-50 text-emerald-600'
                    : item.type === '합격 가이드'
                      ? 'border-indigo-100 bg-indigo-50 text-indigo-600'
                      : 'border-amber-100 bg-amber-50 text-amber-600'
              }`}
            >
              <item.icon size={16} />
              {item.type}
            </div>
            <h3 className="mb-3 text-xl font-extrabold leading-snug text-slate-800 transition-colors group-hover:text-blue-600">
              {item.title}
            </h3>
            <p className="flex-1 text-[15px] font-medium leading-relaxed text-slate-600">{item.desc}</p>

            <div className="mt-6 flex items-center justify-between border-t border-slate-100 pt-5">
              <span className="rounded-lg bg-slate-50 px-2.5 py-1 text-xs font-bold text-slate-400">조회수 1.2k</span>
              <span className="flex items-center gap-1.5 rounded-xl border border-slate-100 bg-white px-3 py-1.5 text-sm font-extrabold text-slate-800 shadow-sm transition-colors group-hover:border-blue-200 group-hover:text-blue-600">
                자세히 보기 <span className="transition-transform group-hover:translate-x-1">→</span>
              </span>
            </div>
          </motion.button>
        ))}
      </div>

      <AnimatePresence>
        {selectedTrend ? (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 z-50 flex items-end bg-slate-900/40 backdrop-blur-sm sm:items-center sm:justify-center sm:p-4"
          >
            <motion.div
              initial={{ opacity: 0, y: 60 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: 60 }}
              className="relative w-full rounded-t-3xl bg-white p-6 shadow-2xl sm:max-w-2xl sm:rounded-3xl sm:p-8"
            >
              <button
                onClick={() => setSelectedTrend(null)}
                className="absolute right-4 top-4 rounded-full bg-slate-100 p-2 text-slate-500 transition-colors hover:text-slate-700"
              >
                <X size={18} />
              </button>
              <div className="mb-5 inline-flex items-center gap-2 rounded-xl border border-blue-100 bg-blue-50 px-3 py-1.5 text-xs font-extrabold text-blue-600">
                <selectedTrend.icon size={16} />
                {selectedTrend.type}
              </div>
              <h3 className="mb-3 text-2xl font-extrabold leading-snug text-slate-800">{selectedTrend.title}</h3>
              <p className="mb-6 text-[15px] font-medium leading-relaxed text-slate-600">{selectedTrend.desc}</p>
              <div className="flex flex-wrap gap-3">
                <button
                  onClick={() => {
                    navigator.clipboard.writeText(selectedTrend.title);
                    toast.success('주제 제목을 클립보드에 복사했습니다.');
                  }}
                  className="rounded-xl border border-slate-200 bg-white px-4 py-2.5 font-bold text-slate-700 transition-colors hover:bg-slate-50"
                >
                  제목 복사
                </button>
                <button
                  onClick={() => {
                    navigate(`/workshop?major=${encodeURIComponent(selectedTrend.type)}`);
                    toast.success('선택한 주제로 워크숍을 열었습니다.');
                    setSelectedTrend(null);
                  }}
                  className="rounded-xl bg-blue-500 px-4 py-2.5 font-bold text-white transition-colors hover:bg-blue-600"
                >
                  이 주제로 작성 시작
                </button>
              </div>
            </motion.div>
          </motion.div>
        ) : null}
      </AnimatePresence>
    </div>
  );
}
