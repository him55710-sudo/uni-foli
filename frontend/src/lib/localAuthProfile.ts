import type { User as FirebaseUser } from 'firebase/auth';
import type {
  OnboardingProfileUpdateRequest,
  UserProfile,
  UserTargetsUpdateRequest,
} from '@shared-contracts';

const LOCAL_AUTH_PROFILE_STORAGE_PREFIX = 'uni_foli_local_auth_profile_v1';

function isBrowser() {
  return typeof window !== 'undefined';
}

function storageKey(uid: string) {
  return `${LOCAL_AUTH_PROFILE_STORAGE_PREFIX}:${uid}`;
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

function defaultDisplayName(firebaseUser: Pick<FirebaseUser, 'displayName' | 'email'>) {
  if (firebaseUser.displayName?.trim()) return firebaseUser.displayName.trim();
  if (firebaseUser.email?.trim()) return firebaseUser.email.split('@')[0];
  return '사용자';
}

function buildBaseProfile(firebaseUser: Pick<FirebaseUser, 'uid' | 'email' | 'displayName'>): UserProfile {
  const now = new Date().toISOString();
  return {
    id: `local-auth-${firebaseUser.uid}`,
    firebase_uid: firebaseUser.uid,
    email: firebaseUser.email || null,
    name: defaultDisplayName(firebaseUser),
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

function normalizeLocalProfile(
  firebaseUser: Pick<FirebaseUser, 'uid' | 'email' | 'displayName'>,
  raw: unknown,
): UserProfile {
  const base = buildBaseProfile(firebaseUser);
  if (!raw || typeof raw !== 'object') return base;

  const value = raw as Record<string, unknown>;

  return {
    ...base,
    id: sanitizeText(value.id, 160) || base.id,
    firebase_uid: sanitizeText(value.firebase_uid, 160) || base.firebase_uid,
    email: sanitizeText(value.email, 320) || base.email,
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

export function readLocalAuthProfile(uid: string): UserProfile | null {
  if (!isBrowser()) return null;

  try {
    const raw = window.localStorage.getItem(storageKey(uid));
    if (!raw) return null;
    const firebaseUserLike = { uid, email: null, displayName: null };
    return normalizeLocalProfile(firebaseUserLike, JSON.parse(raw));
  } catch {
    return null;
  }
}

function writeLocalAuthProfile(firebaseUid: string, profile: UserProfile) {
  if (!isBrowser()) return;
  window.localStorage.setItem(storageKey(firebaseUid), JSON.stringify(profile));
}

export function buildLocalAuthProfile(
  firebaseUser: Pick<FirebaseUser, 'uid' | 'email' | 'displayName'>,
  existing?: UserProfile | null,
): UserProfile {
  const base = normalizeLocalProfile(firebaseUser, existing);
  const now = new Date().toISOString();
  const next: UserProfile = {
    ...base,
    id: `local-auth-${firebaseUser.uid}`,
    firebase_uid: firebaseUser.uid,
    email: firebaseUser.email || base.email,
    name: firebaseUser.displayName || base.name || defaultDisplayName(firebaseUser),
    updated_at: now,
  };
  writeLocalAuthProfile(firebaseUser.uid, next);
  return next;
}

export function updateLocalAuthProfile(
  payload: OnboardingProfileUpdateRequest,
  firebaseUser: Pick<FirebaseUser, 'uid' | 'email' | 'displayName'>,
  existing?: UserProfile | null,
): UserProfile {
  const base = buildLocalAuthProfile(firebaseUser, existing);
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

  writeLocalAuthProfile(firebaseUser.uid, next);
  return next;
}

export function updateLocalAuthTargets(
  payload: UserTargetsUpdateRequest,
  firebaseUser: Pick<FirebaseUser, 'uid' | 'email' | 'displayName'>,
  existing?: UserProfile | null,
): UserProfile {
  const base = buildLocalAuthProfile(firebaseUser, existing);
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

  writeLocalAuthProfile(firebaseUser.uid, next);
  return next;
}
