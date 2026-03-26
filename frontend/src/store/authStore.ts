import { create } from 'zustand';
import { signOut } from 'firebase/auth';
import { auth } from '../lib/firebase';
import { api } from '../lib/api';

interface UserProfile {
  id: string;
  firebase_uid: string;
  email: string | null;
  name: string | null;
  grade: string | null;
  track: string | null;
  career: string | null;
  target_university: string | null;
  target_major: string | null;
  admission_type: string | null;
  interest_universities: string[];
}

interface AuthState {
  user: UserProfile | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  setUser: (user: UserProfile | null) => void;
  setLoading: (isLoading: boolean) => void;
  fetchProfile: () => Promise<void>;
  logout: () => Promise<void>;
}

export const useAuthStore = create<AuthState>((set) => ({
  user: null,
  isAuthenticated: false,
  isLoading: true,
  
  setUser: (user) => set({ user, isAuthenticated: !!user, isLoading: false }),
  
  setLoading: (isLoading) => set({ isLoading }),
  
  fetchProfile: async () => {
    try {
      const profile = await api.get<UserProfile>('/api/v1/users/me');
      set({ user: profile, isAuthenticated: true, isLoading: false });
    } catch (error) {
      console.error('Failed to fetch user profile:', error);
      set({ user: null, isAuthenticated: false, isLoading: false });
    }
  },

  logout: async () => {
    try {
      await signOut(auth);
      set({ user: null, isAuthenticated: false, isLoading: false });
    } catch (error) {
      console.error('Logout failed:', error);
    }
  },
}));
