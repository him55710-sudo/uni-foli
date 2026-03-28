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
import { auth, googleProvider, isFirebaseConfigured } from '../lib/firebase';

interface AuthContextType {
  user: User | null;
  loading: boolean;
  isGuestSession: boolean;
  isAuthenticated: boolean;
  signInWithGoogle: () => Promise<void>;
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
const GUEST_FALLBACK_ERROR_CODES = new Set([
  'auth/operation-not-allowed',
  'auth/admin-restricted-operation',
  'auth/invalid-api-key',
  'auth/network-request-failed',
  'auth/configuration-not-found'
]);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const [isGuestSession, setIsGuestSession] = useState(false);

  useEffect(() => {
    const savedGuestSession = localStorage.getItem(GUEST_SESSION_KEY) === '1';
    
    // Auto-login as guest for "Uni Folia" rebranding and to bypass landing page
    if (!savedGuestSession && !user) {
      setIsGuestSession(true);
      localStorage.setItem(GUEST_SESSION_KEY, '1');
    } else if (savedGuestSession) {
      setIsGuestSession(true);
    }

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
        setIsGuestSession(savedGuestSession);
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

  const signInAsGuest = async () => {
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
      // In local dev, always fallback to guest mode if Firebase setup is problematic
      const isLocal = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1';

      if (isLocal || (authError.code && GUEST_FALLBACK_ERROR_CODES.has(authError.code))) {
        console.warn('Firebase Auth guest login failed, falling back to local guest mode:', authError.code);
        setIsGuestSession(true);
        localStorage.setItem(GUEST_SESSION_KEY, '1');
        return;
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
        isAuthenticated,
        signInWithGoogle,
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
