import React, { createContext, useContext, useEffect, useState } from 'react';
import {
  AuthError,
  User,
  onAuthStateChanged,
  signInAnonymously,
  signInWithPopup,
  signInWithRedirect,
  signOut,
} from 'firebase/auth';
import { auth, googleProvider } from '../lib/firebase';

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
]);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const [isGuestSession, setIsGuestSession] = useState(false);

  useEffect(() => {
    const savedGuestSession = localStorage.getItem(GUEST_SESSION_KEY) === '1';
    if (savedGuestSession) {
      setIsGuestSession(true);
    }

    const unsubscribe = onAuthStateChanged(auth, (currentUser) => {
      setUser(currentUser);
      if (currentUser) {
        const shouldMarkGuest = currentUser.isAnonymous;
        setIsGuestSession(shouldMarkGuest);
        if (shouldMarkGuest) {
          localStorage.setItem(GUEST_SESSION_KEY, '1');
        } else {
          localStorage.removeItem(GUEST_SESSION_KEY);
        }
      } else {
        setIsGuestSession(savedGuestSession);
      }
      setLoading(false);
    });
    return unsubscribe;
  }, []);

  const signInWithGoogle = async () => {
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
    try {
      await signInAnonymously(auth);
      setIsGuestSession(true);
      localStorage.setItem(GUEST_SESSION_KEY, '1');
    } catch (error) {
      const authError = error as Partial<AuthError>;
      if (authError.code && GUEST_FALLBACK_ERROR_CODES.has(authError.code)) {
        // Fallback guest session for local/demo usage when anonymous auth is disabled.
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
      if (auth.currentUser) {
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
