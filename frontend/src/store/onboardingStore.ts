import { create } from 'zustand';
import type {
  OnboardingGoalsUpdateRequest,
  OnboardingGoalsUpdateResponse,
  OnboardingProfileUpdateRequest,
  OnboardingProfileUpdateResponse,
} from '@shared-contracts';
import { api } from '../lib/api';
import { auth } from '../lib/firebase';
import { isGuestSessionActive, updateGuestProfile, updateGuestTargets } from '../lib/guestProfile';
import { updateLocalAuthProfile, updateLocalAuthTargets } from '../lib/localAuthProfile';
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
  
  submitProfile: () => Promise<boolean>;
  submitGoals: (directData?: GoalsData) => Promise<boolean>;
  syncWithUser: (user: any) => void;
  initializeFromProject: (projectId: string) => Promise<boolean>;
  resetOnboarding: () => void;
}

import { buildRankedGoals } from '../lib/rankedGoals';

const initialProfile: ProfileData = { grade: '', track: '', career: '' };
const initialGoals: GoalsData = {
  target_university: '',
  target_major: '',
  admission_type: '',
  interest_universities: [],
};

export const useOnboardingStore = create<OnboardingState>((set, get) => ({
  diagnosisStep: 'PROFILE',
  profile: initialProfile,
  goals: initialGoals,
  goalList: [],
  activeProjectId: null,
  activeDiagnosisRunId: null,
  activeDocumentId: null,
  isLoading: false,
  error: null,
  hasInitialized: false,

  setDiagnosisStep: (diagnosisStep) => set({ diagnosisStep }),

  setProfile: (data) => set((state) => ({ profile: { ...state.profile, ...data } })),

  setGoals: (data) => set((state) => ({ goals: { ...state.goals, ...data } })),

  setGoalList: (goalList) => set({ goalList }),
  
  addGoal: (goal) => set((state) => ({ 
    goalList: [...state.goalList, goal].slice(0, 6) 
  })),

  removeGoal: (id) => set((state) => ({ 
    goalList: state.goalList.filter(g => g.id !== id) 
  })),

  setActiveProjectId: (id) => set({ activeProjectId: id }),
  setActiveDiagnosisRunId: (id) => set({ activeDiagnosisRunId: id }),
  setActiveDocumentId: (id) => set({ activeDocumentId: id }),

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
      set({ error: err.response?.data?.detail || '프로필 저장에 실패했습니다. 다시 시도해주세요.', isLoading: false });
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
          set({ isLoading: false, error: '최소 1개의 목표를 설정해야 합니다.' });
          return false;
        }
        const main = currentGoalList[0];
        const others = currentGoalList.slice(1).map(g => `${g.university} (${g.major})`);
        goals = {
          target_university: main.university,
          target_major: main.major,
          interest_universities: others,
          admission_type: get().goals.admission_type || '학생부종합',
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
      set({ error: err.response?.data?.detail || '목표 저장에 실패했습니다. 다시 시도해주세요.', isLoading: false });
      return false;
    }
  },

  syncWithUser: (user) => {
    if (!user) return;
    const ranked = buildRankedGoals(user, 6);
    const goalList: GoalItem[] = ranked.map((rg, idx) => ({
      id: idx === 0 ? 'main' : `interest-${idx - 1}`,
      university: rg.university,
      major: rg.major
    }));
    const [primaryGoal, ...otherGoals] = goalList;
    const hasPrimaryGoal = Boolean(primaryGoal?.university && primaryGoal?.major);
    
    const { hasInitialized, diagnosisStep } = get();

    set({ 
      profile: {
        grade: user.grade || '',
        track: user.track || '',
        career: user.career || ''
      },
      goalList,
      goals: {
        target_university: primaryGoal?.university || '',
        target_major: primaryGoal?.major || '',
        interest_universities: otherGoals.filter((goal) => goal.major).map((goal) => `${goal.university} (${goal.major})`),
        admission_type: user.admission_type || '학생부종합'
      }
    });

    // Only auto-advance if we haven't manually interacted or if we are at the very beginning
    if (!hasInitialized) {
      if (!user.grade || !user.track) {
        set({ diagnosisStep: 'PROFILE', hasInitialized: true });
      } else if (!hasPrimaryGoal) {
        set({ diagnosisStep: 'GOALS', hasInitialized: true });
      } else {
        set({ diagnosisStep: 'UPLOAD', hasInitialized: true });
      }
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
          major: project.target_major || '' 
        });
        
        if (project.interest_universities?.length) {
          project.interest_universities.forEach((iu: any, idx: number) => {
            if (!iu || typeof iu !== 'string') return;
            const match = iu.match(/^(.+)\s\((.+)\)$/);
            if (match) {
              projectGoals.push({ id: `interest-${idx}`, university: match[1]?.trim() || '', major: match[2]?.trim() || '' });
            } else {
              projectGoals.push({ id: `interest-${idx}`, university: iu.trim(), major: '' });
            }
          });
        }
      }

      set({ 
        goalList: projectGoals,
        diagnosisStep: project.latest_diagnosis_run_id || project.documents?.length ? 'ANALYSING' : 'UPLOAD',
        activeDocumentId: project.documents?.[0]?.id || null,
        activeDiagnosisRunId: project.latest_diagnosis_run_id || null,
        isLoading: false
      });
      return true;
    } catch (err: any) {
      set({ isLoading: false, error: '프로젝트 정보를 불러오지 못했습니다.' });
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
    error: null, 
    isLoading: false 
  }),
}));
