import React, { useState } from 'react';
import { AnimatePresence, motion } from 'motion/react';
import { Search, Pin, Loader2, ExternalLink, BookOpen, Database, Globe } from 'lucide-react';
import toast from 'react-hot-toast';

import { api } from '../lib/api';

interface ScholarPaper {
  title: string;
  abstract?: string | null;
  authors: string[];
  year?: number | null;
  citationCount: number;
  url?: string | null;
  source_type?: 'uploaded_student_record' | 'academic_source' | 'official_guideline' | 'live_web_source';
  source_label?: string | null;
  source_provider?: string | null;
  source_domain?: string | null;
  freshness_label?: 'unknown' | 'archive' | 'recent' | 'realtime' | null;
  retrieved_at?: string | null;
  requested_source?: string | null;
}

interface ScholarSearchResult {
  query: string;
  total: number;
  papers: ScholarPaper[];
  source?: string;
  requested_source?: string | null;
  fallback_applied?: boolean;
  limitation_note?: string | null;
  providers_used?: string[];
  retrieved_at?: string | null;
  source_type_counts?: Record<string, number>;
}

interface ReferenceSearchPanelProps {
  onPinReference: (text: string, sourceType: string) => Promise<void>;
  isAdvancedMode: boolean;
}

type SearchSource = 'semantic' | 'kci' | 'live_web' | 'both';

function normalizePinnedSourceType(
  sourceType: ScholarPaper['source_type'],
  fallbackSource: SearchSource,
): string {
  if (sourceType) return sourceType;
  if (fallbackSource === 'live_web') return 'live_web_source';
  return 'academic_source';
}

export function ReferenceSearchPanel({
  onPinReference,
  isAdvancedMode,
}: ReferenceSearchPanelProps) {
  const [searchQuery, setSearchQuery] = useState('');
  const [isSearching, setIsSearching] = useState(false);
  const [results, setResults] = useState<ScholarPaper[]>([]);
  const [searchSource, setSearchSource] = useState<SearchSource>('semantic');
  const [hasSearched, setHasSearched] = useState(false);
  const [searchMeta, setSearchMeta] = useState<{
    resolvedSource: string;
    fallbackApplied: boolean;
    limitationNote: string | null;
    providersUsed: string[];
    sourceTypeCounts: Record<string, number>;
    retrievedAt: string | null;
  } | null>(null);

  if (!isAdvancedMode) return null;

  const handleSearch = async () => {
    const query = searchQuery.trim();
    if (!query || isSearching) return;

    setIsSearching(true);
    setHasSearched(true);

    try {
      const result = await api.get<ScholarSearchResult>(
        `/api/v1/research/papers?query=${encodeURIComponent(query)}&limit=5&source=${searchSource}`,
      );
      setResults(result.papers);
      setSearchMeta({
        resolvedSource: result.source || searchSource,
        fallbackApplied: Boolean(result.fallback_applied),
        limitationNote: (result.limitation_note || null),
        providersUsed: result.providers_used || [],
        sourceTypeCounts: result.source_type_counts || {},
        retrievedAt: result.retrieved_at || null,
      });
      if (result.papers.length === 0) {
        toast('No results found. Try another keyword.', { icon: 'i' });
      }
    } catch (err) {
      console.error('Paper search failed:', err);
      toast.error('Search failed. Please try again.');
      setResults([]);
      setSearchMeta(null);
    } finally {
      setIsSearching(false);
    }
  };

  const handlePinPaper = async (paper: ScholarPaper) => {
    const snippet = [
      `Title: ${paper.title}`,
      paper.source_label ? `Source Type: ${paper.source_label}` : '',
      paper.source_provider ? `Provider: ${paper.source_provider}` : '',
      paper.authors.length ? `Authors: ${paper.authors.slice(0, 3).join(', ')}` : '',
      paper.year ? `Year: ${paper.year}` : '',
      paper.freshness_label ? `Freshness: ${paper.freshness_label}` : '',
      paper.abstract ? `Summary: ${paper.abstract.substring(0, 220)}...` : '',
      paper.url ? `Source: ${paper.url}` : '',
    ]
      .filter(Boolean)
      .join('\n');

    try {
      await onPinReference(
        snippet,
        normalizePinnedSourceType(paper.source_type, (searchMeta?.resolvedSource as SearchSource) || searchSource),
      );
      toast.success(`Pinned: ${paper.title.substring(0, 36)}...`);
    } catch {
      toast.error('Failed to pin reference.');
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
        Reference Search
      </div>

      <div className="mb-3 flex gap-1.5">
        {([
          { key: 'semantic' as SearchSource, label: 'Semantic Scholar', icon: <BookOpen size={12} /> },
          { key: 'kci' as SearchSource, label: 'KCI', icon: <Database size={12} /> },
          { key: 'both' as SearchSource, label: 'Academic Hybrid', icon: <Database size={12} /> },
          { key: 'live_web' as SearchSource, label: 'Live Web', icon: <Globe size={12} /> },
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

      <div className="relative flex items-center gap-2">
        <input
          type="text"
          value={searchQuery}
          onChange={(event) => setSearchQuery(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === 'Enter') void handleSearch();
          }}
          placeholder="Search papers by title or keyword..."
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

      {searchMeta?.limitationNote ? (
        <div className="mt-2 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-xs font-semibold leading-5 text-amber-800">
          {searchMeta.limitationNote}
        </div>
      ) : null}

      {searchMeta?.fallbackApplied ? (
        <div className="mt-2 rounded-lg border border-blue-200 bg-blue-50 px-3 py-2 text-xs font-semibold leading-5 text-blue-800">
          Live web provider was unavailable. Showing fallback indexed sources.
        </div>
      ) : null}

      {searchMeta ? (
        <div className="mt-2 rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-[11px] font-semibold text-slate-600">
          <p>Resolved source: {searchMeta.resolvedSource}</p>
          <p>Providers: {searchMeta.providersUsed.join(', ') || 'n/a'}</p>
          <p>
            Source types:{' '}
            {Object.entries(searchMeta.sourceTypeCounts)
              .map(([key, value]) => `${key} (${value})`)
              .join(', ') || 'n/a'}
          </p>
        </div>
      ) : null}

      <AnimatePresence>
        {hasSearched ? (
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
                      <p className="line-clamp-2 text-sm font-extrabold leading-snug text-slate-800">
                        {paper.title}
                      </p>
                      <div className="mt-1 flex flex-wrap items-center gap-2 text-[11px] text-slate-500">
                        {paper.source_label ? (
                          <span className="rounded bg-blue-50 px-1.5 py-0.5 font-bold text-blue-700">
                            {paper.source_label}
                          </span>
                        ) : null}
                        {paper.authors.slice(0, 2).map((author, i) => (
                          <span key={i} className="font-medium">{author}</span>
                        ))}
                        {paper.year ? (
                          <span className="rounded bg-slate-100 px-1.5 py-0.5 font-bold">{paper.year}</span>
                        ) : null}
                        {paper.freshness_label ? (
                          <span className="rounded bg-emerald-50 px-1.5 py-0.5 font-bold text-emerald-700">
                            {paper.freshness_label}
                          </span>
                        ) : null}
                        {paper.citationCount > 0 ? (
                          <span className="font-bold text-amber-600">Cited {paper.citationCount}</span>
                        ) : null}
                      </div>
                      {paper.abstract ? (
                        <p className="mt-1.5 line-clamp-2 text-xs font-medium leading-relaxed text-slate-500">
                          {paper.abstract}
                        </p>
                      ) : null}
                    </div>
                    <div className="flex flex-shrink-0 flex-col gap-1.5">
                      <button
                        type="button"
                        onClick={() => void handlePinPaper(paper)}
                        className="flex items-center gap-1 rounded-lg border border-indigo-200 bg-indigo-50 px-2.5 py-1.5 text-[11px] font-black text-indigo-700 transition-all hover:bg-indigo-100 active:scale-95"
                      >
                        <Pin size={11} />
                        Pin
                      </button>
                      {paper.url ? (
                        <a
                          href={paper.url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="flex items-center gap-1 rounded-lg border border-slate-200 bg-white px-2.5 py-1.5 text-[11px] font-bold text-slate-500 transition-all hover:bg-slate-50"
                        >
                          <ExternalLink size={11} />
                          Open
                        </a>
                      ) : null}
                    </div>
                  </div>
                </motion.div>
              ))
            ) : !isSearching ? (
              <p className="py-4 text-center text-sm font-medium text-slate-400">
                No results found.
              </p>
            ) : null}
          </motion.div>
        ) : null}
      </AnimatePresence>
    </motion.div>
  );
}
