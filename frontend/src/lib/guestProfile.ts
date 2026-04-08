import type {
  OnboardingProfileUpdateRequest,
  UserProfile,
  UserTargetsUpdateRequest,
} from '@shared-contracts';

export const GUEST_SESSION_KEY = 'uni_foli_guest_session';
const GUEST_PROFILE_STORAGE_KEY = 'uni_foli_guest_profile_v1';

function isBrowser() {
  return typeof window !== 'undefined';
}

function sanitizeText(value: unknown, maxLength = 200): string {
  if (typeof value !== 'string') return '';
  return value.trim().slice(0, maxLength);
}

function sanitizeInterestUniversities(value: unknown): string[] {
  if (!Array.isArray(value)) return [];
  const deduped = new Set<string>();
  value.forEach(item => {
    const normalized = sanitizeText(item, 200);
    if (!normalized) return;
    deduped.add(normalized);
  });
  return Array.from(deduped).slice(0, 20);
}

function buildDefaultGuestProfile(): UserProfile {
  const now = new Date().toISOString();
  return {
    id: 'guest-local',
    firebase_uid: 'guest-local',
    email: null,
    name: '게스트',
    target_university: null,
    target_major: null,
    grade: null,
    track: null,
    career: null,
    admission_type: null,
    interest_universities: [],
    marketing_agreed: false,
    created_at: now,
    updated_at: now,
  };
}

function normalizeGuestProfile(raw: unknown): UserProfile {
  const base = buildDefaultGuestProfile();
  if (!raw || typeof raw !== 'object') return base;
  const value = raw as Record<string, unknown>;

  return {
    ...base,
    id: sanitizeText(value.id, 120) || base.id,
    firebase_uid: sanitizeText(value.firebase_uid, 120) || base.firebase_uid,
    email: sanitizeText(value.email, 320) || null,
    name: sanitizeText(value.name, 120) || base.name,
    target_university: sanitizeText(value.target_university, 200) || null,
    target_major: sanitizeText(value.target_major, 200) || null,
    grade: sanitizeText(value.grade, 50) || null,
    track: sanitizeText(value.track, 100) || null,
    career: sanitizeText(value.career, 200) || null,
    admission_type: sanitizeText(value.admission_type, 100) || null,
    interest_universities: sanitizeInterestUniversities(value.interest_universities),
    marketing_agreed: typeof value.marketing_agreed === 'boolean' ? value.marketing_agreed : base.marketing_agreed,
    created_at: sanitizeText(value.created_at, 40) || base.created_at,
    updated_at: sanitizeText(value.updated_at, 40) || base.updated_at,
  };
}

export function isGuestSessionActive() {
  if (!isBrowser()) return false;
  return window.localStorage.getItem(GUEST_SESSION_KEY) === '1';
}

export function readGuestProfile(): UserProfile | null {
  if (!isBrowser()) return null;

  try {
    const raw = window.localStorage.getItem(GUEST_PROFILE_STORAGE_KEY);
    if (!raw) return null;
    return normalizeGuestProfile(JSON.parse(raw));
  } catch {
    return null;
  }
}

export function writeGuestProfile(profile: UserProfile): void {
  if (!isBrowser()) return;
  window.localStorage.setItem(GUEST_PROFILE_STORAGE_KEY, JSON.stringify(profile));
}

export function updateGuestProfile(
  payload: OnboardingProfileUpdateRequest,
  existing?: UserProfile | null,
): UserProfile {
  const base = normalizeGuestProfile(existing ?? readGuestProfile() ?? buildDefaultGuestProfile());
  const now = new Date().toISOString();

  const next: UserProfile = {
    ...base,
    grade: payload.grade !== undefined ? sanitizeText(payload.grade, 50) || null : base.grade,
    track: payload.track !== undefined ? sanitizeText(payload.track, 100) || null : base.track,
    career: payload.career !== undefined ? sanitizeText(payload.career, 200) || null : base.career,
    interest_universities:
      payload.interest_universities !== undefined
        ? sanitizeInterestUniversities(payload.interest_universities)
        : base.interest_universities,
    marketing_agreed:
      payload.marketing_agreed !== undefined ? Boolean(payload.marketing_agreed) : base.marketing_agreed,
    updated_at: now,
  };

  writeGuestProfile(next);
  return next;
}

export function updateGuestTargets(
  payload: UserTargetsUpdateRequest,
  existing?: UserProfile | null,
): UserProfile {
  const base = normalizeGuestProfile(existing ?? readGuestProfile() ?? buildDefaultGuestProfile());
  const now = new Date().toISOString();

  const targetUniversity =
    payload.target_university !== undefined
      ? sanitizeText(payload.target_university, 200) || null
      : base.target_university;
  const interestUniversities =
    payload.interest_universities !== undefined
      ? sanitizeInterestUniversities(payload.interest_universities).filter(name => name !== targetUniversity)
      : base.interest_universities.filter(name => name !== targetUniversity);

  const next: UserProfile = {
    ...base,
    target_university: targetUniversity,
    target_major:
      payload.target_major !== undefined ? sanitizeText(payload.target_major, 200) || null : base.target_major,
    admission_type:
      payload.admission_type !== undefined ? sanitizeText(payload.admission_type, 100) || null : base.admission_type,
    interest_universities: interestUniversities,
    updated_at: now,
  };

  writeGuestProfile(next);
  return next;
}
