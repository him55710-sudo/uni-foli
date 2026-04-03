import React, { createContext, useContext, useEffect, useState } from 'react';
import { useAuthStore } from '../store/authStore';
import {
  AuthError,
  User,
  onAuthStateChanged,
  signInAnonymously,
  signInWithPopup,
  signInWithRedirect,
  signOut,
} from 'firebase/auth';
import { auth, googleProvider, isFirebaseConfigured, isGuestModeAllowed } from '../lib/firebase';
import { api } from '../lib/api';

interface AuthContextType {
  user: User | null;
  loading: boolean;
  isGuestSession: boolean;
  guestModeAvailable: boolean;
  isAuthenticated: boolean;
  signInWithGoogle: () => Promise<void>;
  signInWithKakao: () => Promise<void>;
  signInWithNaver: () => Promise<void>;
  signInAsGuest: () => Promise<void>;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);
const GUEST_SESSION_KEY = 'polio_guest_session';
const POPUP_FALLBACK_ERROR_CODES = new Set([
  'auth/popup-blocked',
  'auth/popup-closed-by-user',
  'auth/cancelled-popup-request',
  'auth/operation-not-supported-in-this-environment',
]);
export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const [isGuestSession, setIsGuestSession] = useState(false);
  const guestModeAvailable = isGuestModeAllowed;

  useEffect(() => {
    localStorage.removeItem(GUEST_SESSION_KEY);
    setIsGuestSession(false);

    if (!auth || !isFirebaseConfigured) {
      setLoading(false);
      return;
    }

    const unsubscribe = onAuthStateChanged(auth, async (currentUser) => {
      setUser(currentUser);
      if (currentUser) {
        const shouldMarkGuest = currentUser.isAnonymous;
        setIsGuestSession(shouldMarkGuest);
        if (shouldMarkGuest) {
          localStorage.setItem(GUEST_SESSION_KEY, '1');
        } else {
          localStorage.removeItem(GUEST_SESSION_KEY);
        }

        // Fetch backend profile and sync with zustand
        await useAuthStore.getState().fetchProfile();
      } else {
        setIsGuestSession(false);
        localStorage.removeItem(GUEST_SESSION_KEY);
        useAuthStore.getState().setUser(null);
      }
      setLoading(false);
    });
    return unsubscribe;
  }, []);

  const signInWithGoogle = async () => {
    if (!auth || !googleProvider || !isFirebaseConfigured) {
      throw new Error('Google login is unavailable until Firebase env vars are configured.');
    }

    try {
      await signInWithPopup(auth, googleProvider);
    } catch (error) {
      const authError = error as Partial<AuthError>;
      if (authError.code && POPUP_FALLBACK_ERROR_CODES.has(authError.code)) {
        await signInWithRedirect(auth, googleProvider);
        return;
      }
      throw error;
    }
  };

  const signInWithKakao = async () => {
    try {
      const response = await api.post<{ authorize_url: string }>('/api/v1/auth/social/prepare', {
        provider: 'kakao',
      });
      window.location.href = response.authorize_url;
    } catch (error) {
      console.error('Kakao auth prepare failed:', error);
      throw error;
    }
  };

  const signInWithNaver = async () => {
    try {
      const response = await api.post<{ authorize_url: string }>('/api/v1/auth/social/prepare', {
        provider: 'naver',
      });
      window.location.href = response.authorize_url;
    } catch (error) {
      console.error('Naver auth prepare failed:', error);
      throw error;
    }
  };

  const signInAsGuest = async () => {
    if (!guestModeAvailable) {
      throw new Error('Guest mode is disabled in this environment.');
    }

    if (!auth || !isFirebaseConfigured) {
      setIsGuestSession(true);
      localStorage.setItem(GUEST_SESSION_KEY, '1');
      return;
    }

    try {
      await signInAnonymously(auth);
      setIsGuestSession(true);
      localStorage.setItem(GUEST_SESSION_KEY, '1');
    } catch (error) {
      const authError = error as Partial<AuthError>;
      if (authError.code === 'auth/operation-not-allowed' || authError.code === 'auth/admin-restricted-operation') {
        throw new Error('현재 Firebase에서 익명 로그인이 꺼져 있어요. Firebase Console > Authentication > Sign-in method에서 Anonymous를 켜 주세요.');
      }
      if (authError.code === 'auth/invalid-api-key') {
        throw new Error('Firebase API 키가 올바르지 않아요. .env의 VITE_FIREBASE_API_KEY를 확인해 주세요.');
      }
      throw error;
    }
  };

  const logout = async () => {
    setIsGuestSession(false);
    localStorage.removeItem(GUEST_SESSION_KEY);
    try {
      if (auth?.currentUser) {
        await signOut(auth);
      }
    } catch (error) {
      console.error('Error signing out', error);
    }
  };

  const isAuthenticated = Boolean(user) || isGuestSession;

  return (
    <AuthContext.Provider
      value={{
        user,
        loading,
        isGuestSession,
        guestModeAvailable,
        isAuthenticated,
        signInWithGoogle,
        signInWithKakao,
        signInWithNaver,
        signInAsGuest,
        logout,
      }}
    >
      {!loading && children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}
