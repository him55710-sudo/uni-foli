import { useCallback, useMemo, useState } from 'react';
import type {
  ContentPatch,
  ReportDocumentState,
  ReportFormatProfile,
  ResearchCandidate,
  SourceRecord,
  UniFoliReportSectionId,
} from '../types/reportDocument';
import {
  convertPaperResultToSourceRecord,
  dedupeSourceRecords,
  updateSourceUsage,
} from '../adapters/sourceAdapter';
import {
  ingestResearchSources,
  searchResearchPapers,
  crawlResearchUrls,
  type ResearchIngestItem,
  type ResearchSearchSource,
  type ScholarPaper,
} from '../api/researchClient';
import { mergeCrawledPageIntoSourceRecord } from '../adapters/sourceAdapter';
import { getCachedCrawledPage, setCachedCrawledPage } from '../cache/researchCache';

export interface UseResearchCandidatesOptions {
  projectId?: string | null;
  selectedTopic?: string | null;
  selectedOutline?: string | null;
  reportDocumentState?: ReportDocumentState | null;
  formatProfile?: ReportFormatProfile | null;
  currentSectionId?: UniFoliReportSectionId | null;
  existingSources?: SourceRecord[];
}

export interface SearchCandidatesOptions {
  targetSection?: UniFoliReportSectionId | null;
  source?: ResearchSearchSource;
  limit?: number;
}

export interface SearchCandidatesResult {
  candidates: ResearchCandidate[];
  sources: SourceRecord[];
}

export function useResearchCandidates(options: UseResearchCandidatesOptions = {}) {
  const [candidates, setCandidates] = useState<ResearchCandidate[]>([]);
  const [sources, setSources] = useState<SourceRecord[]>(options.existingSources || []);
  const [isSearching, setIsSearching] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const allSources = useMemo(
    () => dedupeSourceRecords([...(options.existingSources || []), ...sources]),
    [options.existingSources, sources],
  );

  const searchCandidates = useCallback(
    async (query: string, searchOptions: SearchCandidatesOptions = {}): Promise<SearchCandidatesResult> => {
      const normalizedQuery = query.trim();
      if (!normalizedQuery) {
        return { candidates: [], sources: allSources };
      }

      setIsSearching(true);
      setError(null);
      try {
        const requestedLimit = Math.max(1, Math.min(searchOptions.limit || 5, 20));
        const crawlLimit = Math.min(6, Math.max(3, Math.ceil(requestedLimit / 2)));
        const result = await searchResearchPapers({
          query: normalizedQuery,
          limit: requestedLimit,
          source: searchOptions.source || 'semantic',
        });
        const targetSection = searchOptions.targetSection || options.currentSectionId || 'background_theory';
        const nextSources = dedupeSourceRecords([
          ...allSources,
          ...result.papers.map((paper) => updateSourceUsage(convertPaperResultToSourceRecord(paper), targetSection)),
        ]);
        const sourceByTitleOrUrl = new Map(
          nextSources.map((source) => [source.url || source.title, source]),
        );
        const nextCandidates = result.papers.map((paper, index) =>
          paperToResearchCandidate(
            paper,
            sourceByTitleOrUrl.get(String(paper.url || paper.title || '')) ||
              convertPaperResultToSourceRecord(paper),
            targetSection,
            index,
          ),
        );

        setSources(nextSources);
        setCandidates(nextCandidates);

        // Optional: Crawl URLs for top 3 sources to enhance candidates
        if (options.projectId) {
          void (async () => {
            const urlsToCrawl = nextSources
              .filter(s => s.url && !getCachedCrawledPage(s.url))
              .slice(0, crawlLimit)
              .map(s => s.url);

            if (urlsToCrawl.length > 0) {
              try {
                const crawlRes = await crawlResearchUrls({
                  projectId: options.projectId!,
                  urls: urlsToCrawl,
                });

                setSources(currentSources => {
                  let updated = [...currentSources];
                  crawlRes.pages.forEach(page => {
                    setCachedCrawledPage(page.url, page);
                    const sourceIdx = updated.findIndex(s => s.url === page.url);
                    if (sourceIdx !== -1) {
                      updated[sourceIdx] = mergeCrawledPageIntoSourceRecord(updated[sourceIdx], page);
                    }
                  });
                  return dedupeSourceRecords(updated);
                });
                
                // If candidates already exist, we might want to update them if crawl was successful
                // But for now, we just let the UI use the updated source metadata
              } catch (e) {
                console.warn('Background crawl failed:', e);
              }
            } else {
              // Even if not crawling now, check cache for existing data to merge
              setSources(currentSources => {
                let updated = [...currentSources];
                let changed = false;
                updated = updated.map(s => {
                  if (s.url) {
                    const cached = getCachedCrawledPage(s.url);
                    if (cached && cached.status === 'ok') {
                      changed = true;
                      return mergeCrawledPageIntoSourceRecord(s, cached);
                    }
                  }
                  return s;
                });
                return changed ? dedupeSourceRecords(updated) : currentSources;
              });
            }
          })();
        }

        if (options.projectId && result.papers.length > 0) {
          void ingestResearchSources({
            projectId: options.projectId,
            items: result.papers.slice(0, Math.min(10, requestedLimit)).map(paperToIngestItem),
          }).catch(() => {
            // Search results remain usable even when background ingestion is rate-limited or unavailable.
          });
        }

        return { candidates: nextCandidates, sources: nextSources };
      } catch (searchError) {
        const message = searchError instanceof Error ? searchError.message : '자료 검색 중 오류가 발생했습니다.';
        setError(message);
        throw searchError;
      } finally {
        setIsSearching(false);
      }
    },
    [allSources, options.currentSectionId, options.projectId],
  );

  const acceptCandidate = useCallback((candidate: ResearchCandidate) => {
    setCandidates((prev) => prev.map((item) => (item.id === candidate.id ? candidate : item)));
    return candidate;
  }, []);

  const rejectCandidate = useCallback((candidateId: string) => {
    setCandidates((prev) => prev.filter((candidate) => candidate.id !== candidateId));
  }, []);

  const refineCandidate = useCallback(
    async (candidateId: string, instruction: string) => {
      const candidate = candidates.find((item) => item.id === candidateId);
      if (!candidate) return null;
      const query = [candidate.title, instruction, options.selectedTopic].filter(Boolean).join(' ');
      return searchCandidates(query, { targetSection: candidate.sectionTarget, limit: 8 });
    },
    [candidates, options.selectedTopic, searchCandidates],
  );

  const convertCandidateToPatch = useCallback(
    (candidate: ResearchCandidate): ContentPatch => {
      const linkedSources = allSources.filter((source) => candidate.sourceIds.includes(source.id));
      const citationHint = linkedSources.length
        ? linkedSources.map((source) => source.citationText || source.title).join('; ')
        : '출처 필요';
      const sourceNote = candidate.sourceIds.length
        ? `근거 출처: ${citationHint}`
        : '근거 출처가 아직 연결되지 않았습니다. 적용 전 출처 보완이 필요합니다.';

      return {
        type: 'content',
        patchId: `research-candidate-${candidate.id}-${Date.now()}`,
        targetSection: candidate.sectionTarget,
        action: 'append',
        contentBlocks: [
          {
            type: 'paragraph',
            text: `${candidate.summary}\n\n${sourceNote}`,
            sourceIds: candidate.sourceIds,
          },
        ],
        contentMarkdown: `${candidate.summary}\n\n${sourceNote}`,
        sourceIds: candidate.sourceIds,
        selectedCandidateIds: [candidate.id],
        rationale: candidate.whyUseful,
        evidenceBoundaryNote:
          candidate.cautionNote ||
          '검색 결과의 서지 정보와 요약을 바탕으로 한 제안입니다. 세부 수치나 인용문은 원문 확인 후 확정하세요.',
        requiresApproval: true,
        status: 'pending',
      };
    },
    [allSources],
  );

  return {
    candidates,
    sources: allSources,
    isSearching,
    error,
    searchCandidates,
    acceptCandidate,
    rejectCandidate,
    refineCandidate,
    convertCandidateToPatch,
  };
}

function paperToResearchCandidate(
  paper: ScholarPaper,
  source: SourceRecord,
  sectionTarget: UniFoliReportSectionId,
  index: number,
): ResearchCandidate {
  const summary = String(paper.abstract || '').trim() || `${source.title} 자료를 보고서 근거 후보로 사용할 수 있습니다.`;
  const reliability = source.reliability;
  return {
    id: `candidate-${source.id || index}`,
    title: source.title,
    summary: truncate(summary, 420),
    sectionTarget,
    whyUseful: `${sectionLabel(sectionTarget)}에서 주장에 근거를 붙이거나 개념 설명을 보강하는 데 사용할 수 있습니다.`,
    sourceIds: source.id ? [source.id] : [],
    confidence: reliability === 'high' ? 'high' : reliability === 'low' ? 'low' : 'medium',
    cautionNote: source.url
      ? reliability === 'low'
        ? '신뢰도가 낮을 수 있어 원문과 발행 주체를 확인하세요.'
        : ''
      : '원문 URL이 없어 적용 전 출처 확인이 필요합니다.',
  };
}

function paperToIngestItem(paper: ScholarPaper): ResearchIngestItem {
  const url = typeof paper.url === 'string' ? paper.url : null;
  const sourceType = paper.source_type?.includes('web') || paper.requested_source === 'live_web' ? 'web_article' : 'paper';
  return {
    source_type: sourceType,
    title: typeof paper.title === 'string' ? paper.title : null,
    canonical_url: url,
    abstract: typeof paper.abstract === 'string' ? paper.abstract : null,
    publisher: typeof paper.source_label === 'string' ? paper.source_label : null,
    author_names: normalizeAuthorNames(paper.authors),
    published_on: normalizePublishedOn(paper.year),
    metadata: {
      citationCount: paper.citationCount ?? paper.citation_count ?? null,
      source_provider: paper.source_provider || null,
      source_domain: paper.source_domain || null,
    },
  };
}

function normalizeAuthorNames(authors: ScholarPaper['authors']): string[] {
  if (!Array.isArray(authors)) return [];
  return authors
    .map((author) => (typeof author === 'string' ? author : author?.name || ''))
    .filter(Boolean);
}

function normalizePublishedOn(year: ScholarPaper['year']): string | null {
  const text = year == null ? '' : String(year);
  const match = text.match(/\d{4}/);
  return match ? `${match[0]}-01-01` : null;
}

function sectionLabel(sectionId: UniFoliReportSectionId): string {
  const labels: Partial<Record<UniFoliReportSectionId, string>> = {
    background_theory: '이론적 배경',
    prior_research: '선행연구',
    research_method: '연구 방법',
    data_analysis: '자료 분석',
    result: '연구 결과',
    student_record_connection: '진로/학생부 연결',
  };
  return labels[sectionId] || '해당 섹션';
}

function truncate(value: string, length: number): string {
  return value.length > length ? `${value.slice(0, length - 1)}…` : value;
}
