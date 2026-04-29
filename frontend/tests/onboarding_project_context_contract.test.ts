import assert from 'node:assert/strict';
import test from 'node:test';

import type { UserProfile } from '@shared-contracts';

import { deriveUserContextKey, useOnboardingStore } from '../src/store/onboardingStore';

function makeUser(partial: Partial<UserProfile>): UserProfile {
  return {
    id: 'user-1',
    firebase_uid: 'firebase-1',
    email: 'user@example.com',
    name: 'User',
    target_university: '서울대',
    target_major: '컴퓨터공학과',
    grade: '2',
    track: '이과',
    career: '개발자',
    admission_type: '학생부종합',
    interest_universities: ['연세대 (컴퓨터공학과)'],
    marketing_agreed: false,
    created_at: '2026-04-17T00:00:00.000Z',
    updated_at: '2026-04-17T00:00:00.000Z',
    ...partial,
  };
}

test('deriveUserContextKey uses stable user identity fields', () => {
  assert.equal(deriveUserContextKey(makeUser({})), 'user-1::firebase-1');
  assert.equal(deriveUserContextKey(null), null);
});

test('syncWithUser clears active project context when the signed-in user changes', () => {
  const store = useOnboardingStore.getState();
  store.resetOnboarding();
  useOnboardingStore.setState({
    diagnosisStep: 'RESULT',
    activeProjectId: 'project-stale',
    activeDocumentId: 'document-stale',
    activeDiagnosisRunId: 'run-stale',
    hasInitialized: true,
    lastSyncedUserKey: 'user-1::firebase-1',
  });

  useOnboardingStore.getState().syncWithUser(makeUser({
    id: 'user-2',
    firebase_uid: 'firebase-2',
  }));

  const nextState = useOnboardingStore.getState();
  assert.equal(nextState.activeProjectId, null);
  assert.equal(nextState.activeDocumentId, null);
  assert.equal(nextState.activeDiagnosisRunId, null);
  assert.ok(['GOALS', 'UPLOAD'].includes(nextState.diagnosisStep));
  assert.equal(nextState.lastSyncedUserKey, 'user-2::firebase-2');
});

test('syncWithUser keeps active project context for the same user', () => {
  useOnboardingStore.getState().resetOnboarding();
  useOnboardingStore.setState({
    diagnosisStep: 'RESULT',
    activeProjectId: 'project-active',
    activeDocumentId: 'document-active',
    activeDiagnosisRunId: 'run-active',
    hasInitialized: true,
    lastSyncedUserKey: 'user-1::firebase-1',
  });

  useOnboardingStore.getState().syncWithUser(makeUser({}));

  const nextState = useOnboardingStore.getState();
  assert.equal(nextState.activeProjectId, 'project-active');
  assert.equal(nextState.activeDocumentId, 'document-active');
  assert.equal(nextState.activeDiagnosisRunId, 'run-active');
  assert.equal(nextState.diagnosisStep, 'RESULT');
});

test('syncWithUser advances a stale goal step when saved goals already exist', () => {
  useOnboardingStore.getState().resetOnboarding();
  useOnboardingStore.setState({
    diagnosisStep: 'GOALS',
    hasInitialized: true,
    lastSyncedUserKey: 'user-1::firebase-1',
  });

  useOnboardingStore.getState().syncWithUser(makeUser({}));

  const nextState = useOnboardingStore.getState();
  assert.equal(nextState.diagnosisStep, 'UPLOAD');
  assert.equal(nextState.goalList[0]?.university, '?쒖슱?');
  assert.equal(nextState.goalList[0]?.major, '而댄벂?곌났?숆낵');
});
