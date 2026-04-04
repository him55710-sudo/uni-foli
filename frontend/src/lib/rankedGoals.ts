import type { UserProfile } from '@shared-contracts';

export interface RankedGoal {
  university: string;
  major: string;
}

function parseInterestGoal(raw: string): RankedGoal {
  const text = raw.trim();
  if (!text) return { university: '', major: '' };

  const match = text.match(/^(.+)\s\((.+)\)$/);
  if (!match) return { university: text, major: '' };

  return {
    university: match[1].trim(),
    major: match[2].trim(),
  };
}

export function buildRankedGoals(
  profile: Pick<UserProfile, 'target_university' | 'target_major' | 'interest_universities'> | null | undefined,
  limit = 6,
): RankedGoal[] {
  if (!profile) return [];

  const goals: RankedGoal[] = [];
  const seen = new Set<string>();

  const pushGoal = (university: string, major: string) => {
    const normalizedUniversity = university.trim();
    const normalizedMajor = major.trim();
    if (!normalizedUniversity) return;

    const key = `${normalizedUniversity}__${normalizedMajor}`;
    if (seen.has(key)) return;

    seen.add(key);
    goals.push({ university: normalizedUniversity, major: normalizedMajor });
  };

  if (profile.target_university) {
    pushGoal(profile.target_university, profile.target_major ?? '');
  }

  if (Array.isArray(profile.interest_universities)) {
    profile.interest_universities.forEach((entry) => {
      if (typeof entry !== 'string') return;
      const parsed = parseInterestGoal(entry);
      pushGoal(parsed.university, parsed.major);
    });
  }

  return goals.slice(0, Math.max(1, limit));
}

