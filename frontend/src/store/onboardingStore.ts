import { create } from 'zustand';
import { api } from '../lib/api';
import { useAuthStore } from './authStore';

export interface ProfileData {
  grade: string;
  track: string;
  career: string;
}

export interface GoalsData {
  target_university: string;
  target_major: string;
  admission_type: string;
}

interface OnboardingState {
  step: number;
  profile: ProfileData;
  goals: GoalsData;
  isLoading: boolean;
  error: string | null;
  
  setStep: (step: number) => void;
  setProfile: (data: Partial<ProfileData>) => void;
  setGoals: (data: Partial<GoalsData>) => void;
  submitProfile: () => Promise<boolean>;
  submitGoals: () => Promise<boolean>;
  reset: () => void;
}

const initialProfile = { grade: '', track: '', career: '' };
const initialGoals = { target_university: '', target_major: '', admission_type: '' };

export const useOnboardingStore = create<OnboardingState>((set, get) => ({
  step: 1,
  profile: initialProfile,
  goals: initialGoals,
  isLoading: false,
  error: null,

  setStep: (step) => set({ step, error: null }),
  
  setProfile: (data) => set((state) => ({ profile: { ...state.profile, ...data } })),
  
  setGoals: (data) => set((state) => ({ goals: { ...state.goals, ...data } })),
  
  submitProfile: async () => {
    set({ isLoading: true, error: null });
    try {
      const { profile } = get();
      const updatedUser = await api.post('/api/v1/users/onboarding/profile', profile);
      useAuthStore.getState().setUser(updatedUser);
      set({ step: 2, isLoading: false });
      return true;
    } catch (err: any) {
      set({ error: err.response?.data?.detail || '프로필 저장에 실패했습니다. 다시 시도해주세요.', isLoading: false });
      return false;
    }
  },

  submitGoals: async () => {
    set({ isLoading: true, error: null });
    try {
      const { goals } = get();
      const updatedUser = await api.post('/api/v1/users/onboarding/goals', goals);
      useAuthStore.getState().setUser(updatedUser);
      set({ isLoading: false });
      return true;
    } catch (err: any) {
      set({ error: err.response?.data?.detail || '목표 저장에 실패했습니다. 다시 시도해주세요.', isLoading: false });
      return false;
    }
  },

  reset: () => set({ step: 1, profile: initialProfile, goals: initialGoals, error: null, isLoading: false }),
}));
