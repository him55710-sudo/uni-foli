import React, { useState } from 'react';
import { AnimatePresence, motion } from 'motion/react';
import { Search, Pin, Loader2, ExternalLink, BookOpen, Database } from 'lucide-react';
import toast from 'react-hot-toast';
import { api } from '../lib/api';

interface ScholarPaper {
  title: string;
  abstract?: string | null;
  authors: string[];
  year?: number | null;
  citationCount: number;
  url?: string | null;
}

interface ScholarSearchResult {
  query: string;
  total: number;
  papers: ScholarPaper[];
}

interface ReferenceSearchPanelProps {
  onPinReference: (text: string, sourceType: string) => Promise<void>;
  isAdvancedMode: boolean;
}

type SearchSource = 'semantic' | 'kci';

export function ReferenceSearchPanel({
  onPinReference,
  isAdvancedMode,
}: ReferenceSearchPanelProps) {
  const [searchQuery, setSearchQuery] = useState('');
  const [isSearching, setIsSearching] = useState(false);
  const [results, setResults] = useState<ScholarPaper[]>([]);
  const [searchSource, setSearchSource] = useState<SearchSource>('semantic');
  const [hasSearched, setHasSearched] = useState(false);

  if (!isAdvancedMode) return null;

  const handleSearch = async () => {
    const query = searchQuery.trim();
    if (!query || isSearching) return;

    setIsSearching(true);
    setHasSearched(true);

    try {
      const result = await api.get<ScholarSearchResult>(
        `/api/v1/research/papers?query=${encodeURIComponent(query)}&limit=5&source=${searchSource}`
      );
      setResults(result.papers);
      if (result.papers.length === 0) {
        toast('검색 결과가 없습니다. 다른 키워드로 시도해 보세요.', { icon: '🔍' });
      }
    } catch (err) {
      console.error('Paper search failed:', err);
      toast.error('논문 검색에 실패했습니다.');
      setResults([]);
    } finally {
      setIsSearching(false);
    }
  };

  const handlePinPaper = async (paper: ScholarPaper) => {
    const snippet = [
      `📄 ${paper.title}`,
      paper.authors.slice(0, 3).join(', '),
      paper.year ? `(${paper.year})` : '',
      paper.abstract ? `\n요약: ${paper.abstract.substring(0, 200)}...` : '',
      paper.url ? `\n출처: ${paper.url}` : '',
    ]
      .filter(Boolean)
      .join(' ');

    try {
      await onPinReference(snippet, `scholar_${searchSource}`);
      toast.success(`"${paper.title.substring(0, 30)}..." 참고자료로 고정`);
    } catch {
      toast.error('참고자료 고정 실패');
    }
  };

  return (
    <motion.div
      initial={{ opacity: 0, height: 0 }}
      animate={{ opacity: 1, height: 'auto' }}
      exit={{ opacity: 0, height: 0 }}
      className="rounded-2xl border border-indigo-200/60 bg-gradient-to-b from-indigo-50/80 to-white p-4"
    >
      <div className="mb-3 flex items-center gap-2 text-xs font-black uppercase tracking-[0.18em] text-indigo-500">
        <Database size={14} />
        심화 참고자료 검색
      </div>

      {/* Source Toggle */}
      <div className="mb-3 flex gap-1.5">
        {([
          { key: 'semantic' as SearchSource, label: 'Semantic Scholar', icon: <BookOpen size={12} /> },
          { key: 'kci' as SearchSource, label: 'KCI 한국학술', icon: <Database size={12} /> },
        ]).map(({ key, label, icon }) => (
          <button
            key={key}
            type="button"
            onClick={() => setSearchSource(key)}
            className={`flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-[11px] font-extrabold transition-all ${
              searchSource === key
                ? 'border border-indigo-300 bg-indigo-100 text-indigo-700 shadow-sm'
                : 'border border-slate-200 bg-white text-slate-500 hover:bg-slate-50'
            }`}
          >
            {icon}
            {label}
          </button>
        ))}
      </div>

      {/* Search Input */}
      <div className="relative flex items-center gap-2">
        <input
          type="text"
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter') void handleSearch();
          }}
          placeholder="논문 제목, 키워드로 검색..."
          className="flex-1 rounded-xl border border-slate-200 bg-white px-4 py-2.5 text-sm font-medium text-slate-700 focus:border-indigo-400 focus:outline-none focus:ring-2 focus:ring-indigo-100"
        />
        <button
          type="button"
          onClick={() => void handleSearch()}
          disabled={!searchQuery.trim() || isSearching}
          className="flex h-10 w-10 items-center justify-center rounded-xl bg-indigo-500 text-white transition-all hover:bg-indigo-600 active:scale-95 disabled:opacity-60"
        >
          {isSearching ? <Loader2 size={16} className="animate-spin" /> : <Search size={16} />}
        </button>
      </div>

      {/* Results */}
      <AnimatePresence>
        {hasSearched && (
          <motion.div
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            className="mt-3 space-y-2"
          >
            {results.length > 0 ? (
              results.map((paper, idx) => (
                <motion.div
                  key={idx}
                  initial={{ opacity: 0, x: -6 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: idx * 0.06 }}
                  className="group rounded-xl border border-slate-200 bg-white p-3 transition-all hover:border-indigo-200 hover:shadow-sm"
                >
                  <div className="flex items-start justify-between gap-2">
                    <div className="min-w-0 flex-1">
                      <p className="text-sm font-extrabold leading-snug text-slate-800 line-clamp-2">
                        {paper.title}
                      </p>
                      <div className="mt-1 flex flex-wrap items-center gap-2 text-[11px] text-slate-500">
                        {paper.authors.slice(0, 2).map((author, i) => (
                          <span key={i} className="font-medium">{author}</span>
                        ))}
                        {paper.year && (
                          <span className="rounded bg-slate-100 px-1.5 py-0.5 font-bold">
                            {paper.year}
                          </span>
                        )}
                        {paper.citationCount > 0 && (
                          <span className="font-bold text-amber-600">
                            인용 {paper.citationCount}
                          </span>
                        )}
                      </div>
                      {paper.abstract && (
                        <p className="mt-1.5 text-xs font-medium leading-relaxed text-slate-500 line-clamp-2">
                          {paper.abstract}
                        </p>
                      )}
                    </div>
                    <div className="flex flex-shrink-0 flex-col gap-1.5">
                      <button
                        type="button"
                        onClick={() => void handlePinPaper(paper)}
                        className="flex items-center gap-1 rounded-lg border border-indigo-200 bg-indigo-50 px-2.5 py-1.5 text-[11px] font-black text-indigo-700 transition-all hover:bg-indigo-100 active:scale-95"
                      >
                        <Pin size={11} />
                        고정
                      </button>
                      {paper.url && (
                        <a
                          href={paper.url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="flex items-center gap-1 rounded-lg border border-slate-200 bg-white px-2.5 py-1.5 text-[11px] font-bold text-slate-500 transition-all hover:bg-slate-50"
                        >
                          <ExternalLink size={11} />
                          원문
                        </a>
                      )}
                    </div>
                  </div>
                </motion.div>
              ))
            ) : (
              !isSearching && (
                <p className="py-4 text-center text-sm font-medium text-slate-400">
                  검색 결과가 없습니다.
                </p>
              )
            )}
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  );
}
