import rawCatalog from '../data/education-catalog.generated.json';
import {
  extractInitialConsonants,
  isChoseongQuery,
  normalizeSearchText,
} from './hangulSearch';

export interface EducationCatalogUniversity {
  name: string;
  majors: string[];
}

interface EducationCatalogData {
  generated_at: string | null;
  source_file: string | null;
  metadata?: {
    university_count: number;
    major_count: number;
    filters: {
      exclude_obsolete: boolean;
      degree_processes: string[];
      university_categories: string[];
    };
  };
  universities: EducationCatalogUniversity[];
  all_majors: string[];
}

export interface CatalogSuggestion {
  id: string;
  label: string;
  secondary?: string;
  type: 'university' | 'major';
}

interface SearchIndexEntry {
  item: string;
  normalized: string;
  initials: string;
}

const catalog = rawCatalog as EducationCatalogData;
const universities = Array.isArray(catalog.universities) ? catalog.universities : [];
const universityMap = new Map(universities.map((item) => [item.name, item]));
const majorUniversityMap = new Map<string, string[]>();

for (const university of universities) {
  for (const major of university.majors) {
    const current = majorUniversityMap.get(major) ?? [];
    current.push(university.name);
    majorUniversityMap.set(major, current);
  }
}

function buildSearchIndex(items: string[]): SearchIndexEntry[] {
  return items.map((item) => ({
    item,
    normalized: normalizeSearchText(item),
    initials: extractInitialConsonants(item),
  }));
}

const universitySearchIndex = buildSearchIndex(universities.map((item) => item.name));
const allMajorSearchIndex = buildSearchIndex(Array.isArray(catalog.all_majors) ? catalog.all_majors : []);
const universityMajorSearchIndex = new Map<string, SearchIndexEntry[]>();

function getUniversityMajorSearchIndex(universityName: string): SearchIndexEntry[] {
  const cached = universityMajorSearchIndex.get(universityName);
  if (cached) return cached;
  const index = buildSearchIndex(getMajorsForUniversity(universityName));
  universityMajorSearchIndex.set(universityName, index);
  return index;
}

export function isEducationCatalogLoaded(): boolean {
  return universities.length > 0;
}

export function getEducationCatalogSummary(): {
  generatedAt: string | null;
  sourceFile: string | null;
  universityCount: number;
  majorCount: number;
  filters?: EducationCatalogData['metadata']['filters'];
} {
  return {
    generatedAt: catalog.generated_at,
    sourceFile: catalog.source_file,
    universityCount: universities.length,
    majorCount: Array.isArray(catalog.all_majors) ? catalog.all_majors.length : 0,
    filters: catalog.metadata?.filters,
  };
}

function scoreCandidate(entry: SearchIndexEntry, normalizedQuery: string, isInitialsQuery: boolean): number | null {
  if (!normalizedQuery) {
    return null;
  }

  if (entry.normalized.startsWith(normalizedQuery)) {
    return 0;
  }

  if (isInitialsQuery && entry.initials.startsWith(normalizedQuery)) {
    return 1;
  }

  if (entry.normalized.includes(normalizedQuery)) {
    return 2;
  }

  if (entry.initials.includes(normalizedQuery)) {
    return 3;
  }

  return null;
}

function searchNames(index: SearchIndexEntry[], query: string, limit: number): string[] {
  const normalizedQuery = normalizeSearchText(query);
  const isInitialsQuery = isChoseongQuery(query);

  return index
    .map((entry) => ({ item: entry.item, score: scoreCandidate(entry, normalizedQuery, isInitialsQuery) }))
    .filter((entry): entry is { item: string; score: number } => entry.score !== null)
    .sort((left, right) => left.score - right.score || left.item.localeCompare(right.item, 'ko'))
    .slice(0, limit)
    .map((entry) => entry.item);
}

export function searchUniversities(
  query: string,
  options: { limit?: number; excludeNames?: string[] } = {},
): CatalogSuggestion[] {
  if (!isEducationCatalogLoaded()) {
    return [];
  }

  const { limit = 100, excludeNames = [] } = options;
  const excludeSet = new Set(excludeNames);

  const index = excludeSet.size
    ? universitySearchIndex.filter((entry) => !excludeSet.has(entry.item))
    : universitySearchIndex;

  return searchNames(index, query, limit).map((name) => ({
    id: `university:${name}`,
    label: name,
    type: 'university',
  }));
}

export function getUniversityByName(name: string): EducationCatalogUniversity | undefined {
  return universityMap.get(name);
}

export function getMajorsForUniversity(name: string): string[] {
  return universityMap.get(name)?.majors ?? [];
}

export function isMajorInUniversity(universityName: string, majorName: string): boolean {
  const university = universityMap.get(universityName);
  if (!university) return false;
  const normalizedMajor = (majorName || '').trim();
  if (!normalizedMajor) return false;
  return university.majors.includes(normalizedMajor);
}

export function searchMajors(
  query: string,
  universityName?: string | null,
  limit = 12,
): CatalogSuggestion[] {
  if (!isEducationCatalogLoaded()) {
    return [];
  }

  // When a university is selected, prioritise that university's own departments.
  const universityMajors = universityName ? getUniversityMajorSearchIndex(universityName) : [];

  if (universityMajors.length > 0) {
    return searchNames(universityMajors, query, limit).map((name) => ({
      id: `major:${universityName}:${name}`,
      label: name,
      secondary: undefined,
      type: 'major' as const,
    }));
  }

  // Fallback: no university selected — search all majors
  return searchNames(allMajorSearchIndex, query, limit).map((name) => ({
    id: `major:all:${name}`,
    label: name,
    secondary: undefined,
    type: 'major' as const,
  }));
}
