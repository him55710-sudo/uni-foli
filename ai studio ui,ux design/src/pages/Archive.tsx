import React, { useMemo, useState } from 'react';
import { Download, Filter, FileText } from 'lucide-react';
import toast from 'react-hot-toast';
import { useAuth } from '../contexts/AuthContext';
import {
  downloadArchiveAsText,
  listArchiveItems,
  type ArchiveItem as StoredArchiveItem,
} from '../lib/archiveStore';

interface ArchiveCardItem {
  id: string;
  title: string;
  subject: string;
  createdAt: string;
  emoji: string;
  color: string;
  contentMarkdown: string;
  projectId: string | null;
}

const defaultArchives: ArchiveCardItem[] = [
  {
    id: 'seed-1',
    title: '생명과학 II - 유전자 편집 기술의 윤리적 쟁점',
    subject: '생명과학',
    createdAt: '2026-03-01T09:00:00.000Z',
    emoji: '🧬',
    color: 'bg-emerald-100',
    contentMarkdown: '# 생명과학 II 보고서\n\n유전자 편집 기술의 윤리적 한계를 정리한 초안입니다.',
    projectId: null,
  },
  {
    id: 'seed-2',
    title: '수학과 통계 - 데이터 기반 소비 패턴 모델',
    subject: '수학',
    createdAt: '2026-02-20T09:00:00.000Z',
    emoji: '📊',
    color: 'bg-blue-100',
    contentMarkdown: '# 수학/통계 보고서\n\n회귀 분석 기반 소비 패턴 모델 초안입니다.',
    projectId: null,
  },
  {
    id: 'seed-3',
    title: '영어 심화 - AI 번역기의 한계와 가능성',
    subject: '영어',
    createdAt: '2026-02-11T09:00:00.000Z',
    emoji: '🌍',
    color: 'bg-rose-100',
    contentMarkdown: '# 영어 심화 보고서\n\nAI 번역기의 구조적 한계 분석 초안입니다.',
    projectId: null,
  },
];

function mapStoredItemToCard(item: StoredArchiveItem): ArchiveCardItem {
  const colorPalette = ['bg-violet-100', 'bg-amber-100', 'bg-cyan-100', 'bg-lime-100'];
  const emojis = ['📝', '🚀', '🧠', '📚'];
  const index = Math.abs(item.id.split('').reduce((acc, ch) => acc + ch.charCodeAt(0), 0)) % emojis.length;
  return {
    id: item.id,
    title: item.title,
    subject: item.subject || '탐구',
    createdAt: item.createdAt,
    emoji: emojis[index],
    color: colorPalette[index],
    contentMarkdown: item.contentMarkdown,
    projectId: item.projectId,
  };
}

export function Archive() {
  const { user, isGuestSession } = useAuth();
  const [sortMode, setSortMode] = useState<'latest' | 'oldest'>('latest');

  const items = useMemo(() => {
    const fromStorage = listArchiveItems().map(mapStoredItemToCard);
    const merged = [...fromStorage, ...defaultArchives].reduce<ArchiveCardItem[]>((acc, current) => {
      if (acc.some((item) => item.id === current.id)) return acc;
      return [...acc, current];
    }, []);

    return merged.sort((a, b) =>
      sortMode === 'latest'
        ? Number(new Date(b.createdAt)) - Number(new Date(a.createdAt))
        : Number(new Date(a.createdAt)) - Number(new Date(b.createdAt)),
    );
  }, [sortMode]);

  const handleDownload = (item: ArchiveCardItem, format: 'hwpx' | 'pdf') => {
    downloadArchiveAsText(
      {
        id: item.id,
        projectId: item.projectId,
        title: item.title,
        subject: item.subject,
        createdAt: item.createdAt,
        contentMarkdown: item.contentMarkdown,
      },
      format,
    );
    toast.success(`${format.toUpperCase()} 파일을 내려받았습니다.`);
  };

  return (
    <div className="mx-auto max-w-7xl px-4 pb-24 sm:px-6 lg:px-8">
      <div className="mb-8 flex flex-col justify-between gap-4 sm:flex-row sm:items-center">
        <div>
          <h1 className="text-3xl font-extrabold text-slate-800">
            {user?.displayName || (isGuestSession ? '게스트' : '사용자')}님의 탐구 아카이브
          </h1>
          <p className="mt-2 font-medium text-slate-500">저장된 보고서 초안을 다시 열고 다운로드할 수 있습니다.</p>
        </div>

        <button
          onClick={() => setSortMode((prev) => (prev === 'latest' ? 'oldest' : 'latest'))}
          className="self-start rounded-xl border border-slate-200 bg-white px-4 py-2.5 font-bold text-slate-600 shadow-sm transition-colors hover:bg-slate-50 sm:self-auto"
        >
          <span className="flex items-center gap-2">
            <Filter size={18} />
            {sortMode === 'latest' ? '최신순' : '오래된순'}
          </span>
        </button>
      </div>

      <div className="grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-3">
        {items.map((item) => (
          <div key={item.id} className="group relative flex flex-col overflow-hidden clay-card">
            <div className={`relative w-full overflow-hidden rounded-t-3xl pt-[75%] ${item.color}`}>
              <div className="absolute inset-0 opacity-20 mix-blend-overlay bg-[url('https://www.transparenttextures.com/patterns/cubes.png')]" />
              <span className="absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 text-7xl drop-shadow-xl transition-transform duration-500 group-hover:scale-110">
                {item.emoji}
              </span>
            </div>

            <div className="flex flex-1 flex-col bg-white p-6">
              <div className="mb-3 flex items-center justify-between">
                <span className="rounded-lg bg-slate-100 px-3 py-1 text-xs font-extrabold text-slate-600">{item.subject}</span>
                <span className="text-xs font-bold text-slate-400">
                  {new Date(item.createdAt).toLocaleDateString()}
                </span>
              </div>
              <h3 className="mb-4 line-clamp-2 text-lg font-extrabold leading-snug text-slate-800">{item.title}</h3>
            </div>

            <div className="absolute bottom-0 left-0 flex w-full translate-y-full gap-2 border-t border-slate-100 bg-white/90 p-4 backdrop-blur-md transition-transform duration-300 group-hover:translate-y-0">
              <button
                onClick={() => handleDownload(item, 'hwpx')}
                className="flex flex-1 items-center justify-center gap-1.5 rounded-xl bg-blue-500 py-2.5 text-sm font-bold text-white shadow-sm transition-colors hover:bg-blue-600"
              >
                <FileText size={16} /> HWPX
              </button>
              <button
                onClick={() => handleDownload(item, 'pdf')}
                className="flex flex-1 items-center justify-center gap-1.5 rounded-xl bg-slate-800 py-2.5 text-sm font-bold text-white shadow-sm transition-colors hover:bg-slate-900"
              >
                <Download size={16} /> PDF
              </button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
