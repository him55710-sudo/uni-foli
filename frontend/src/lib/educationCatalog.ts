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

function scoreCandidate(candidate: string, query: string): number | null {
  const normalizedCandidate = normalizeSearchText(candidate);
  const normalizedQuery = normalizeSearchText(query);
  if (!normalizedQuery) {
    return null;
  }

  if (normalizedCandidate.startsWith(normalizedQuery)) {
    return 0;
  }

  const initials = extractInitialConsonants(candidate);
  if (isChoseongQuery(query) && initials.startsWith(normalizedQuery)) {
    return 1;
  }

  if (normalizedCandidate.includes(normalizedQuery)) {
    return 2;
  }

  if (initials.includes(normalizedQuery)) {
    return 3;
  }

  return null;
}

function searchNames(items: string[], query: string, limit: number): string[] {
  return items
    .map((item) => ({ item, score: scoreCandidate(item, query) }))
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

  return searchNames(
    universities.map((item) => item.name).filter((name) => !excludeSet.has(name)),
    query,
    limit,
  ).map((name) => ({
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
  return university.majors.includes(majorName);
}

export function searchMajors(
  query: string,
  universityName?: string | null,
  limit = 12,
): CatalogSuggestion[] {
  if (!isEducationCatalogLoaded()) {
    return [];
  }

  const source = universityName && universityMap.has(universityName)
    ? universityMap.get(universityName)?.majors ?? []
    : catalog.all_majors;

  return searchNames(source, query, limit).map((name) => {
    const relatedUniversities = majorUniversityMap.get(name) ?? [];
    return {
      id: `major:${universityName ?? 'all'}:${name}`,
      label: name,
      secondary: universityName
        ? universityName
        : relatedUniversities.slice(0, 2).join(', ') || undefined,
      type: 'major' as const,
    };
  });
}
