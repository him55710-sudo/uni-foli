import React, { useMemo, useState } from 'react';
import { 
  Download, 
  Edit3, 
  Filter, 
  FileText, 
  Search, 
  Trash2, 
  CheckSquare, 
  Square,
  MoreVertical,
  ChevronRight,
  Archive as ArchiveIcon,
  X
} from 'lucide-react';
import toast from 'react-hot-toast';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import {
  deleteArchiveItem,
  downloadArchiveAsText,
  listArchiveItems,
  type ArchiveItem as StoredArchiveItem,
} from '../lib/archiveStore';
import { cn } from '../lib/cn';

interface ArchiveCardItem {
  id: string;
  title: string;
  subject: string;
  createdAt: string;
  updatedAt?: string;
  emoji: string;
  color: string;
  contentMarkdown: string;
  projectId: string | null;
  isSeed?: boolean;
}

const defaultArchives: ArchiveCardItem[] = [
  {
    id: 'seed-1',
    title: '생명과학 II - 유전자 편집 기술의 윤리적 쟁점',
    subject: '생명과학',
    createdAt: '2026-03-01T09:00:00.000Z',
    emoji: '🧬',
    color: 'bg-emerald-50 text-emerald-600',
    contentMarkdown: '# 생명과학 II 보고서\n\n유전자 편집 기술의 윤리적 한계를 정리한 초안입니다.',
    projectId: null,
  },
  {
    id: 'seed-2',
    title: '수학과 통계 - 데이터 기반 소비 패턴 모델',
    subject: '수학',
    createdAt: '2026-02-20T09:00:00.000Z',
    emoji: '📊',
    color: 'bg-blue-50 text-blue-600',
    contentMarkdown: '# 수학/통계 보고서\n\n회귀 분석 기반 소비 패턴 모델 초안입니다.',
    projectId: null,
  },
  {
    id: 'seed-3',
    title: '영어 심화 - AI 번역기의 한계와 가능성',
    subject: '영어',
    createdAt: '2026-02-11T09:00:00.000Z',
    emoji: '🌍',
    color: 'bg-rose-50 text-rose-600',
    contentMarkdown: '# 영어 심화 보고서\n\nAI 번역기의 구조적 한계 분석 초안입니다.',
    projectId: null,
  },
  {
    id: 'seed-4',
    title: '건축과 사회 - 기후 변화에 대응하는 미래 주거 구조',
    subject: '건축/사회',
    createdAt: '2026-03-15T10:00:00.000Z',
    emoji: '🏡',
    color: 'bg-amber-50 text-amber-600',
    contentMarkdown: '# 건축 탐구 보고서\n\n지속 가능한 건축 자재와 제로 에너지 하우스의 상관관계 분석입니다.',
    projectId: null,
  },
  {
    id: 'seed-5',
    title: '의학 입문 - 암 치료를 위한 면역 항암제의 원리',
    subject: '의학',
    createdAt: '2026-03-22T14:00:00.000Z',
    emoji: '🩺',
    color: 'bg-indigo-50 text-indigo-600',
    contentMarkdown: '# 의학 탐구 보고서\n\nT-세포 활성화를 통한 면역 항암 요법의 최신 트렌드를 정리했습니다.',
    projectId: null,
  },
  {
    id: 'seed-6',
    title: '환경공학 - 폐플라스틱 업사이클링의 경제성 분석',
    subject: '환경',
    createdAt: '2026-03-28T16:30:00.000Z',
    emoji: '♻️',
    color: 'bg-teal-50 text-teal-600',
    contentMarkdown: '# 환경 보고서\n\n자원 순환 모델 확립을 위한 업사이클링 공정의 비용 대비 편익 분석 초안입니다.',
    projectId: null,
  },
];

function mapStoredItemToCard(item: StoredArchiveItem): ArchiveCardItem {
  const colorPalette = [
    'bg-violet-50 text-violet-600',
    'bg-amber-50 text-amber-600',
    'bg-cyan-50 text-cyan-600',
    'bg-lime-50 text-lime-600',
  ];
  const emojis = ['📝', '🚀', '🧠', '📚'];
  const hash = item.id.split('').reduce((acc, ch) => acc + ch.charCodeAt(0), 0);
  const index = Math.abs(hash) % emojis.length;
  return {
    id: item.id,
    title: item.title,
    subject: item.subject || '탐구',
    createdAt: item.createdAt,
    updatedAt: item.updatedAt,
    emoji: emojis[index],
    color: colorPalette[index],
    contentMarkdown: item.contentMarkdown,
    projectId: item.projectId,
  };
}

const SEED_DELETED_KEY = 'uni_foli_deleted_seed_ids';

function getDeletedSeedIds(): string[] {
  try {
    const raw = localStorage.getItem(SEED_DELETED_KEY);
    return raw ? JSON.parse(raw) : [];
  } catch {
    return [];
  }
}

function saveDeletedSeedIds(ids: string[]) {
  const current = getDeletedSeedIds();
  const next = Array.from(new Set([...current, ...ids]));
  localStorage.setItem(SEED_DELETED_KEY, JSON.stringify(next));
}

export function Archive() {
  const navigate = useNavigate();
  const { user, isGuestSession } = useAuth();
  const [sortMode, setSortMode] = useState<'latest' | 'oldest'>('latest');
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [refreshKey, setRefreshKey] = useState(0);
  const [isSelectMode, setIsSelectMode] = useState(false);

  const items = useMemo(() => {
    const deletedSeedIds = getDeletedSeedIds();
    const fromStorage = listArchiveItems().map(mapStoredItemToCard);
    const visibleSeeds = defaultArchives
      .filter(seed => !deletedSeedIds.includes(seed.id))
      .map(seed => ({ ...seed, isSeed: true }));

    let merged = [...fromStorage, ...visibleSeeds].reduce<ArchiveCardItem[]>((acc, current) => {
      if (acc.some((item) => item.id === current.id)) return acc;
      return [...acc, current];
    }, []);

    // Filter by search query
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase();
      merged = merged.filter(
        item => item.title.toLowerCase().includes(q) || item.subject.toLowerCase().includes(q)
      );
    }

    return merged.sort((a, b) =>
      sortMode === 'latest'
        ? Number(new Date(b.updatedAt || b.createdAt)) - Number(new Date(a.updatedAt || a.createdAt))
        : Number(new Date(a.updatedAt || a.createdAt)) - Number(new Date(b.updatedAt || b.createdAt)),
    );
  }, [sortMode, refreshKey, searchQuery]);

  const handleDownload = (item: ArchiveCardItem, format: 'hwpx' | 'pdf') => {
    downloadArchiveAsText(
      {
        id: item.id,
        projectId: item.projectId,
        title: item.title,
        subject: item.subject,
        createdAt: item.createdAt,
        updatedAt: item.updatedAt,
        contentMarkdown: item.contentMarkdown,
      },
      format,
    );
    toast.success(`${format.toUpperCase()} 파일을 내려받았습니다.`);
  };

  const handleContinue = (item: ArchiveCardItem) => {
    if (item.projectId) {
      navigate(`/app/workshop/${encodeURIComponent(item.projectId)}`);
      return;
    }
    navigate(`/app/workshop?archiveId=${encodeURIComponent(item.id)}`);
  };

  const toggleSelect = (id: string) => {
    setSelectedIds(prev => {
      const next = new Set(prev);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      return next;
    });
  };

  const handleBulkDelete = () => {
    if (selectedIds.size === 0) return;
    
    if (confirm(`${selectedIds.size}개의 항목을 삭제하시겠습니까?`)) {
      const idsArray = Array.from(selectedIds);
      const seedIds = items.filter(item => item.isSeed && selectedIds.has(item.id)).map(item => item.id);
      const storageIds = idsArray.filter(id => !seedIds.includes(id));

      if (seedIds.length > 0) {
        saveDeletedSeedIds(seedIds);
      }
      
      storageIds.forEach(id => deleteArchiveItem(id));
      
      setSelectedIds(new Set());
      setIsSelectMode(false);
      setRefreshKey((prev) => prev + 1);
      toast.success('선택한 항목들이 삭제되었습니다.');
    }
  };

  const handleDelete = (item: ArchiveCardItem) => {
    if (confirm(`'${item.title}' 항목을 삭제하시겠습니까?`)) {
      if (item.isSeed) {
        saveDeletedSeedIds([item.id]);
      } else {
        deleteArchiveItem(item.id);
      }
      setRefreshKey((prev) => prev + 1);
      toast.success('항목이 삭제되었습니다.');
    }
  };

  return (
    <div className="mx-auto max-w-7xl px-4 pb-24 sm:px-6 lg:px-8">
      {/* Header Section */}
      <div className="mb-10 flex flex-col justify-between gap-6 sm:flex-row sm:items-end">
        <div className="space-y-1">
          <p className="text-sm font-black uppercase tracking-widest text-indigo-600">Exploration Archive</p>
          <h1 className="text-4xl font-black tracking-tight text-slate-900">
            {user?.displayName || (isGuestSession ? '게스트' : '사용자')}님의 탐구 아카이브
          </h1>
          <p className="text-base font-semibold text-slate-500">저장된 보고서 초안과 작업 내역을 관리합니다.</p>
        </div>

        <div className="flex items-center gap-3">
          {isSelectMode ? (
            <>
              <button
                onClick={handleBulkDelete}
                disabled={selectedIds.size === 0}
                className="flex items-center gap-2 rounded-2xl bg-rose-600 px-5 py-3 font-black text-white shadow-lg shadow-rose-100 transition-all hover:bg-rose-700 active:scale-95 disabled:opacity-50 disabled:shadow-none"
              >
                <Trash2 size={18} />
                {selectedIds.size}개 삭제
              </button>
              <button
                onClick={() => {
                  setIsSelectMode(false);
                  setSelectedIds(new Set());
                }}
                className="flex items-center gap-2 rounded-2xl border border-slate-200 bg-white px-5 py-3 font-black text-slate-700 transition-all hover:bg-slate-50 active:scale-95"
              >
                취소
              </button>
            </>
          ) : (
            <>
              <button
                onClick={() => setIsSelectMode(true)}
                className="flex items-center gap-2 rounded-2xl border border-slate-200 bg-white px-5 py-3 font-black text-slate-700 shadow-sm transition-all hover:bg-slate-50 hover:shadow-md active:scale-95"
              >
                <CheckSquare size={18} />
                선택 삭제
              </button>
              <button
                onClick={() => setSortMode((prev) => (prev === 'latest' ? 'oldest' : 'latest'))}
                className="flex items-center gap-2 rounded-2xl border border-slate-200 bg-white px-5 py-3 font-black text-slate-700 shadow-sm transition-all hover:bg-slate-50 hover:shadow-md active:scale-95"
              >
                <Filter size={18} />
                {sortMode === 'latest' ? '최신순' : '오래된순'}
              </button>
            </>
          )}
        </div>
      </div>

      {/* Search Bar */}
      <div className="mb-8 relative max-w-md">
        <div className="absolute inset-y-0 left-4 flex items-center pointer-events-none text-slate-400">
          <Search size={20} />
        </div>
        <input
          type="text"
          placeholder="제목이나 과목으로 검색..."
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          className="w-full pl-12 pr-10 py-3.5 rounded-2xl border border-slate-200 bg-white text-slate-900 font-bold placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500 transition-all shadow-sm"
        />
        {searchQuery && (
          <button
            onClick={() => setSearchQuery('')}
            className="absolute inset-y-0 right-4 flex items-center text-slate-400 hover:text-slate-600"
          >
            <X size={18} />
          </button>
        )}
      </div>

      {/* Content Grid */}
      {items.length === 0 ? (
        <div className="flex min-h-[400px] flex-col items-center justify-center rounded-[3rem] border-2 border-dashed border-slate-200 bg-white p-12 text-center">
          <div className="mb-6 flex h-20 w-20 items-center justify-center rounded-3xl bg-slate-50 text-slate-400">
            <ArchiveIcon size={40} />
          </div>
          <h2 className="text-2xl font-black text-slate-900">
            {searchQuery ? '검색 결과가 없습니다.' : '아직 저장된 탐구가 없습니다.'}
          </h2>
          <p className="mt-3 max-w-sm font-semibold text-slate-500">
            {searchQuery ? '다른 검색어로 다시 시도해 보세요.' : '워크숍에서 탐구 보고서를 작성하고 저장하면 이곳에 안전하게 보관됩니다.'}
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-8 sm:grid-cols-2 lg:grid-cols-3">
          {items.map((item) => (
            <div 
              key={item.id} 
              onClick={() => isSelectMode && toggleSelect(item.id)}
              className={cn(
                "group relative flex flex-col overflow-hidden rounded-[2.5rem] border transition-all duration-300",
                isSelectMode ? "cursor-pointer" : "",
                selectedIds.has(item.id) 
                  ? "border-indigo-500 bg-indigo-50/30 ring-2 ring-indigo-500/20 shadow-xl shadow-indigo-100" 
                  : "border-slate-100 bg-white shadow-sm hover:-translate-y-1 hover:shadow-2xl hover:shadow-indigo-100/50"
              )}
            >
              {/* Selection Overlay */}
              {isSelectMode && (
                <div className="absolute left-4 top-4 z-20">
                  {selectedIds.has(item.id) ? (
                    <div className="flex h-8 w-8 items-center justify-center rounded-xl bg-indigo-600 text-white shadow-lg">
                      <CheckSquare size={20} />
                    </div>
                  ) : (
                    <div className="flex h-8 w-8 items-center justify-center rounded-xl bg-white/80 border border-slate-200 text-slate-400 backdrop-blur-sm shadow-sm">
                      <Square size={20} />
                    </div>
                  )}
                </div>
              )}

              <div className={cn("relative aspect-[16/9] w-full overflow-hidden", item.color)}>
                <div className="absolute inset-0 opacity-20 mix-blend-overlay bg-[url('https://www.transparenttextures.com/patterns/cubes.png')]" />
                <span className="absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 text-7xl drop-shadow-2xl transition-transform duration-700 group-hover:scale-110">
                  {item.emoji}
                </span>
                
                {!isSelectMode && (
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      handleDelete(item);
                    }}
                    className="absolute right-4 top-4 flex h-10 w-10 items-center justify-center rounded-2xl bg-white/90 text-slate-400 backdrop-blur-md transition-all hover:bg-rose-600 hover:text-white shadow-lg z-10"
                    title="삭제"
                  >
                    <Trash2 size={18} />
                  </button>
                )}
              </div>

              <div className="flex flex-1 flex-col p-8">
                <div className="mb-4 flex items-center gap-3">
                  <span className="rounded-xl bg-slate-100 px-3.5 py-1.5 text-xs font-black text-slate-600 uppercase tracking-wider">{item.subject}</span>
                  <span className="text-xs font-bold text-slate-400">
                    {new Date(item.createdAt).toLocaleDateString()}
                  </span>
                </div>
                
                <h3 className="mb-8 line-clamp-2 text-xl font-black leading-tight text-slate-900 group-hover:text-indigo-600 transition-colors">
                  {item.title}
                </h3>

                <div className="mt-auto grid grid-cols-3 gap-3">
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      handleContinue(item);
                    }}
                    disabled={isSelectMode}
                    className="flex flex-col items-center justify-center gap-1.5 rounded-2xl border border-slate-100 bg-slate-50 py-3 text-xs font-black text-slate-700 transition-all hover:bg-slate-100 active:scale-95 disabled:opacity-30"
                  >
                    <Edit3 size={18} />
                    <span>편집</span>
                  </button>
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      handleDownload(item, 'hwpx');
                    }}
                    disabled={isSelectMode}
                    className="flex flex-col items-center justify-center gap-1.5 rounded-2xl bg-indigo-600 py-3 text-xs font-black text-white shadow-lg shadow-indigo-100 transition-all hover:bg-indigo-700 hover:shadow-indigo-200 active:scale-95 disabled:opacity-30"
                  >
                    <FileText size={18} />
                    <span>HWPX</span>
                  </button>
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      handleDownload(item, 'pdf');
                    }}
                    disabled={isSelectMode}
                    className="flex flex-col items-center justify-center gap-1.5 rounded-2xl bg-slate-900 py-3 text-xs font-black text-white shadow-lg shadow-slate-200 transition-all hover:bg-black active:scale-95 disabled:opacity-30"
                  >
                    <Download size={18} />
                    <span>PDF</span>
                  </button>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

