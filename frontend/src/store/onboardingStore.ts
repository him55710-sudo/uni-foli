import { create } from 'zustand';
import type {
  OnboardingGoalsUpdateRequest,
  OnboardingGoalsUpdateResponse,
  OnboardingProfileUpdateRequest,
  OnboardingProfileUpdateResponse,
} from '@shared-contracts';
import { api } from '../lib/api';
import { syncUserProfileToFirestore } from '../lib/db';
import { auth } from '../lib/firebase';
import { isGuestSessionActive, updateGuestProfile, updateGuestTargets } from '../lib/guestProfile';
import { updateLocalAuthProfile, updateLocalAuthTargets } from '../lib/localAuthProfile';
import { buildRankedGoals } from '../lib/rankedGoals';
import { useAuthStore } from './authStore';

export interface ProfileData {
  grade: string;
  track: string;
  career: string;
}

export interface GoalItem {
  id: string;
  university: string;
  major: string;
}

export interface GoalsData {
  target_university: string;
  target_major: string;
  admission_type: string;
  interest_universities: string[];
}

export type DiagnosisStep = 'PROFILE' | 'GOALS' | 'UPLOAD' | 'ANALYSING' | 'RESULT' | 'FAILED';

interface OnboardingState {
  diagnosisStep: DiagnosisStep;
  profile: ProfileData;
  goals: GoalsData;
  goalList: GoalItem[];
  activeProjectId: string | null;
  activeDiagnosisRunId: string | null;
  activeDocumentId: string | null;
  lastSyncedUserKey: string | null;
  isLoading: boolean;
  error: string | null;
  hasInitialized: boolean;

  setDiagnosisStep: (step: DiagnosisStep) => void;
  setProfile: (data: Partial<ProfileData>) => void;
  setGoals: (data: Partial<GoalsData>) => void;
  setGoalList: (goals: GoalItem[]) => void;
  addGoal: (goal: GoalItem) => void;
  removeGoal: (id: string) => void;
  setActiveProjectId: (id: string | null) => void;
  setActiveDiagnosisRunId: (id: string | null) => void;
  setActiveDocumentId: (id: string | null) => void;
  clearActiveProjectContext: () => void;

  submitProfile: () => Promise<boolean>;
  submitGoals: (directData?: GoalsData) => Promise<boolean>;
  syncWithUser: (user: any) => void;
  initializeFromProject: (projectId: string) => Promise<boolean>;
  resetOnboarding: () => void;
}

const initialProfile: ProfileData = { grade: '', track: '', career: '' };
const initialGoals: GoalsData = {
  target_university: '',
  target_major: '',
  admission_type: '',
  interest_universities: [],
};

export function deriveUserContextKey(user: { id?: string | null; firebase_uid?: string | null } | null | undefined): string | null {
  if (!user) return null;
  const id = typeof user.id === 'string' ? user.id.trim() : '';
  const firebaseUid = typeof user.firebase_uid === 'string' ? user.firebase_uid.trim() : '';
  const composite = `${id}::${firebaseUid}`.trim();
  return composite || null;
}

function resolveDiagnosisStep(user: any, hasPrimaryGoal: boolean): DiagnosisStep {
  if (!user?.grade || !user?.track) return 'PROFILE';
  if (!hasPrimaryGoal) return 'GOALS';
  return 'UPLOAD';
}

function shouldAdvanceCompletedSetupStep(currentStep: DiagnosisStep, nextStep: DiagnosisStep): boolean {
  if (currentStep === 'PROFILE' && nextStep !== 'PROFILE') return true;
  if (currentStep === 'GOALS' && nextStep === 'UPLOAD') return true;
  return false;
}

export const useOnboardingStore = create<OnboardingState>((set, get) => ({
  diagnosisStep: 'PROFILE',
  profile: initialProfile,
  goals: initialGoals,
  goalList: [],
  activeProjectId: null,
  activeDiagnosisRunId: null,
  activeDocumentId: null,
  lastSyncedUserKey: null,
  isLoading: false,
  error: null,
  hasInitialized: false,

  setDiagnosisStep: (diagnosisStep) => set({ diagnosisStep }),

  setProfile: (data) => set((state) => ({ profile: { ...state.profile, ...data } })),

  setGoals: (data) => set((state) => ({ goals: { ...state.goals, ...data } })),

  setGoalList: (goalList) => set({ goalList }),

  addGoal: (goal) => set((state) => ({
    goalList: [...state.goalList, goal].slice(0, 6),
  })),

  removeGoal: (id) => set((state) => ({
    goalList: state.goalList.filter((goal) => goal.id !== id),
  })),

  setActiveProjectId: (id) => set({ activeProjectId: id }),
  setActiveDiagnosisRunId: (id) => set({ activeDiagnosisRunId: id }),
  setActiveDocumentId: (id) => set({ activeDocumentId: id }),
  clearActiveProjectContext: () => set({
    activeProjectId: null,
    activeDiagnosisRunId: null,
    activeDocumentId: null,
  }),

  submitProfile: async () => {
    set({ isLoading: true, error: null });
    try {
      const { profile } = get();
      const payload: OnboardingProfileUpdateRequest = profile;

      if (isGuestSessionActive()) {
        const updatedUser = updateGuestProfile(payload, useAuthStore.getState().user);
        useAuthStore.getState().setUser(updatedUser);
        set({ diagnosisStep: 'GOALS', isLoading: false });
        return true;
      }

      const updatedUser = await api.post<OnboardingProfileUpdateResponse>('/api/v1/users/onboarding/profile', payload);
      useAuthStore.getState().setUser(updatedUser);
      void syncUserProfileToFirestore(updatedUser);
      set({ diagnosisStep: 'GOALS', isLoading: false, hasInitialized: true });
      return true;
    } catch (err: any) {
      if (isGuestSessionActive()) {
        const { profile } = get();
        const updatedUser = updateGuestProfile(profile, useAuthStore.getState().user);
        useAuthStore.getState().setUser(updatedUser);
        set({ diagnosisStep: 'GOALS', isLoading: false, hasInitialized: true });
        return true;
      }

      const currentAuthUser = auth?.currentUser;
      if (currentAuthUser) {
        const { profile } = get();
        const updatedUser = updateLocalAuthProfile(profile, currentAuthUser, useAuthStore.getState().user);
        useAuthStore.getState().setUser(updatedUser);
        set({ diagnosisStep: 'GOALS', isLoading: false, hasInitialized: true });
        return true;
      }

      set({ error: err.response?.data?.detail || '?꾨줈????μ뿉 ?ㅽ뙣?덉뒿?덈떎. ?ㅼ떆 ?쒕룄?댁＜?몄슂.', isLoading: false });
      return false;
    }
  },

  submitGoals: async (directData?: GoalsData) => {
    set({ isLoading: true, error: null });
    try {
      let goals = directData;
      if (!goals) {
        const currentGoalList = get().goalList;
        if (currentGoalList.length === 0) {
          set({ isLoading: false, error: '理쒖냼 1媛쒖쓽 紐⑺몴瑜??ㅼ젙?댁빞 ?⑸땲??' });
          return false;
        }

        const main = currentGoalList[0];
        const others = currentGoalList.slice(1).map((goal) => `${goal.university} (${goal.major})`);
        goals = {
          target_university: main.university,
          target_major: main.major,
          interest_universities: others,
          admission_type: get().goals.admission_type || '?숈깮遺醫낇빀',
        };
      }

      const payload: OnboardingGoalsUpdateRequest = goals;

      if (isGuestSessionActive()) {
        const updatedUser = updateGuestTargets(payload, useAuthStore.getState().user);
        useAuthStore.getState().setUser(updatedUser);
        set({ diagnosisStep: 'UPLOAD', isLoading: false });
        return true;
      }

      const updatedUser = await api.post<OnboardingGoalsUpdateResponse>('/api/v1/users/onboarding/goals', payload);
      useAuthStore.getState().setUser(updatedUser);
      void syncUserProfileToFirestore(updatedUser);
      set({ diagnosisStep: 'UPLOAD', isLoading: false });
      return true;
    } catch (err: any) {
      const goals = directData || get().goals;
      if (isGuestSessionActive()) {
        const updatedUser = updateGuestTargets(goals, useAuthStore.getState().user);
        useAuthStore.getState().setUser(updatedUser);
        set({ diagnosisStep: 'UPLOAD', isLoading: false });
        return true;
      }

      const currentAuthUser = auth?.currentUser;
      if (currentAuthUser) {
        const updatedUser = updateLocalAuthTargets(goals, currentAuthUser, useAuthStore.getState().user);
        useAuthStore.getState().setUser(updatedUser);
        set({ diagnosisStep: 'UPLOAD', isLoading: false, hasInitialized: true });
        return true;
      }

      set({ error: err.response?.data?.detail || '紐⑺몴 ??μ뿉 ?ㅽ뙣?덉뒿?덈떎. ?ㅼ떆 ?쒕룄?댁＜?몄슂.', isLoading: false });
      return false;
    }
  },

  syncWithUser: (user) => {
    if (!user) return;

    const ranked = buildRankedGoals(user, 6);
    const goalList: GoalItem[] = ranked.map((goal, index) => ({
      id: index === 0 ? 'main' : `interest-${index - 1}`,
      university: goal.university,
      major: goal.major,
    }));
    const [primaryGoal, ...otherGoals] = goalList;
    const hasPrimaryGoal = Boolean(primaryGoal?.university && primaryGoal?.major);
    const nextStep = resolveDiagnosisStep(user, hasPrimaryGoal);
    const nextUserKey = deriveUserContextKey(user);
    const { diagnosisStep, hasInitialized, lastSyncedUserKey } = get();
    const hasUserChanged = Boolean(lastSyncedUserKey && nextUserKey && lastSyncedUserKey !== nextUserKey);

    const nextState: Partial<OnboardingState> = {
      profile: {
        grade: user.grade || '',
        track: user.track || '',
        career: user.career || '',
      },
      goalList,
      goals: {
        target_university: primaryGoal?.university || '',
        target_major: primaryGoal?.major || '',
        interest_universities: otherGoals
          .filter((goal) => goal.major)
          .map((goal) => `${goal.university} (${goal.major})`),
        admission_type: user.admission_type || '?숈깮遺醫낇빀',
      },
      lastSyncedUserKey: nextUserKey,
    };

    if (hasUserChanged) {
      set({
        ...nextState,
        diagnosisStep: nextStep,
        activeProjectId: null,
        activeDiagnosisRunId: null,
        activeDocumentId: null,
        error: null,
        isLoading: false,
        hasInitialized: true,
      });
      return;
    }

    set(nextState);

    if (!hasInitialized || shouldAdvanceCompletedSetupStep(diagnosisStep, nextStep)) {
      set({ diagnosisStep: nextStep, hasInitialized: true });
    }
  },

  initializeFromProject: async (projectId: string) => {
    set({ isLoading: true, error: null, activeProjectId: projectId });
    try {
      const project = await api.get<any>(`/api/v1/projects/${projectId}`);
      const projectGoals: GoalItem[] = [];

      if (project.target_university) {
        projectGoals.push({
          id: 'main',
          university: project.target_university,
          major: project.target_major || '',
        });

        if (project.interest_universities?.length) {
          project.interest_universities.forEach((interestUniversity: any, index: number) => {
            if (!interestUniversity || typeof interestUniversity !== 'string') return;
            const match = interestUniversity.match(/^(.+)\s\((.+)\)$/);
            if (match) {
              projectGoals.push({
                id: `interest-${index}`,
                university: match[1]?.trim() || '',
                major: match[2]?.trim() || '',
              });
            } else {
              projectGoals.push({ id: `interest-${index}`, university: interestUniversity.trim(), major: '' });
            }
          });
        }
      }

      set({
        goalList: projectGoals,
        diagnosisStep: project.latest_diagnosis_run_id || project.documents?.length ? 'ANALYSING' : 'UPLOAD',
        activeDocumentId: project.documents?.[0]?.id || null,
        activeDiagnosisRunId: project.latest_diagnosis_run_id || null,
        isLoading: false,
      });
      return true;
    } catch (err: any) {
      set({ isLoading: false, error: '?꾨줈?앺듃 ?뺣낫瑜?遺덈윭?ㅼ? 紐삵뻽?듬땲??' });
      return false;
    }
  },

  resetOnboarding: () => set({
    diagnosisStep: 'PROFILE',
    profile: initialProfile,
    goals: initialGoals,
    goalList: [],
    activeProjectId: null,
    activeDiagnosisRunId: null,
    activeDocumentId: null,
    lastSyncedUserKey: null,
    error: null,
    isLoading: false,
    hasInitialized: false,
  }),
}));
