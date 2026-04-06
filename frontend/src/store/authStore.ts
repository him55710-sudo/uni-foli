import { create } from 'zustand';
import { signOut } from 'firebase/auth';
import { auth } from '../lib/firebase';
import { api } from '../lib/api';
import { isGuestSessionActive, readGuestProfile } from '../lib/guestProfile';
import { buildLocalAuthProfile, readLocalAuthProfile } from '../lib/localAuthProfile';
import { clearAppAccessToken } from '../lib/appAccessToken';
import type { UserProfile } from '@shared-contracts';

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
      const currentAuthUser = auth?.currentUser;
      if (currentAuthUser) {
        const cachedLocalProfile = readLocalAuthProfile(currentAuthUser.uid);
        const fallbackProfile = buildLocalAuthProfile(currentAuthUser, cachedLocalProfile);
        set({ user: fallbackProfile, isAuthenticated: true, isLoading: false });
        return;
      }

      if (isGuestSessionActive()) {
        const guestProfile = readGuestProfile();
        if (guestProfile) {
          set({ user: guestProfile, isAuthenticated: true, isLoading: false });
          return;
        }
      }
      set({ user: null, isAuthenticated: false, isLoading: false });
    }
  },

  logout: async () => {
    try {
      await signOut(auth);
      clearAppAccessToken();
      set({ user: null, isAuthenticated: false, isLoading: false });
    } catch (error) {
      console.error('Logout failed:', error);
    }
  },
}));
