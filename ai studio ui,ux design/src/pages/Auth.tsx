import React, { useState } from 'react';
import { Navigate } from 'react-router-dom';
import { FirebaseError } from 'firebase/app';
import { motion, AnimatePresence } from 'motion/react';
import { Sparkles, ArrowRight, AlertCircle, User } from 'lucide-react';
import { useAuth } from '../contexts/AuthContext';
import poliDuoMascot from '../assets/poli-duo.png';

const AUTH_ERROR_MESSAGES: Record<string, string> = {
  'auth/popup-closed-by-user': 'Google login was cancelled. Please try again.',
  'auth/popup-blocked': 'Popup was blocked. Please allow popups and try again.',
  'auth/network-request-failed': 'Network error. Check your internet connection.',
  'auth/unauthorized-domain': 'This domain is not allowed in Firebase Auth.',
  'auth/configuration-not-found': 'Google provider is not enabled in Firebase Auth.',
  'auth/operation-not-allowed': 'Guest login is not enabled in Firebase Auth settings.',
  'auth/admin-restricted-operation': 'Guest login is blocked by Firebase project settings.',
};

function toAuthMessage(error: unknown): string {
  if (error instanceof FirebaseError) {
    return AUTH_ERROR_MESSAGES[error.code] ?? `Login failed (${error.code}).`;
  }
  return 'Login failed. Please try again.';
}

export function Auth() {
  const { user, isGuestSession, signInWithGoogle, signInAsGuest } = useAuth();
  const [toastMessage, setToastMessage] = useState<string | null>(null);
  const [isSigningIn, setIsSigningIn] = useState<'google' | 'guest' | null>(null);

  if (user || isGuestSession) {
    return <Navigate to="/" replace />;
  }

  const showToast = (message: string) => {
    setToastMessage(message);
    setTimeout(() => setToastMessage(null), 3500);
  };

  const onGoogleLogin = async () => {
    if (isSigningIn !== null) {
      return;
    }

    setIsSigningIn('google');
    try {
      await signInWithGoogle();
    } catch (error) {
      showToast(toAuthMessage(error));
    } finally {
      setIsSigningIn(null);
    }
  };

  const onGuestLogin = async () => {
    if (isSigningIn !== null) {
      return;
    }

    setIsSigningIn('guest');
    try {
      await signInAsGuest();
    } catch (error) {
      showToast(toAuthMessage(error));
    } finally {
      setIsSigningIn(null);
    }
  };

  return (
    <div className="relative flex min-h-screen bg-slate-50">
      <AnimatePresence>
        {toastMessage && (
          <motion.div
            initial={{ opacity: 0, y: -32 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -32 }}
            className="absolute left-1/2 top-8 z-50 flex -translate-x-1/2 items-center gap-3 rounded-2xl bg-slate-800 px-6 py-3 font-bold text-white shadow-xl"
          >
            <AlertCircle size={20} className="text-amber-400" />
            {toastMessage}
          </motion.div>
        )}
      </AnimatePresence>

      <div className="relative hidden overflow-hidden bg-gradient-to-br from-blue-50 to-blue-100/60 p-12 lg:flex lg:w-1/2 lg:flex-col lg:justify-between">
        <div className="absolute inset-0 opacity-5 mix-blend-overlay bg-[url('https://www.transparenttextures.com/patterns/cubes.png')]" />

        <div className="relative z-10">
          <div className="mb-10 flex items-center gap-3">
            <img
              src={poliDuoMascot}
              alt="Polio mascot"
              className="h-12 w-12 rounded-2xl border border-blue-100 bg-white object-cover p-1.5 shadow-lg shadow-blue-500/20"
            />
            <span className="text-3xl font-extrabold tracking-tight text-slate-800">polio</span>
          </div>

          <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.2 }}>
            <h1 className="mb-6 text-5xl font-extrabold leading-tight text-slate-800">
              AI mentor for school records
              <br />
              and portfolio writing.
            </h1>
            <p className="text-xl font-medium leading-relaxed text-slate-500">
              Fast diagnostics, structure suggestions,
              <br />
              and polished draft generation in one flow.
            </p>
          </motion.div>
        </div>

        <motion.div
          className="relative z-10 mt-12 self-center"
          animate={{ y: [0, -15, 0] }}
          transition={{ repeat: Infinity, duration: 4, ease: 'easeInOut' }}
        >
          <div className="relative flex h-80 w-80 items-center justify-center overflow-hidden rounded-[3rem] border-4 border-white bg-white shadow-2xl shadow-blue-200/50">
            <div className="absolute inset-0 bg-gradient-to-tr from-blue-50 to-transparent" />
            <img src={poliDuoMascot} alt="Polio mascot duo" className="h-64 w-64 object-contain drop-shadow-2xl" />
          </div>
          <div className="absolute -bottom-8 left-1/2 h-8 w-56 -translate-x-1/2 rounded-full bg-blue-900/10 blur-xl" />
        </motion.div>
      </div>

      <div className="relative flex w-full items-center justify-center bg-white p-6 sm:p-12 lg:w-1/2">
        <div className="absolute left-8 top-8 flex items-center gap-2 lg:hidden">
          <img
            src={poliDuoMascot}
            alt="Polio mascot"
            className="h-10 w-10 rounded-xl border border-blue-100 bg-white object-cover p-1 shadow-md shadow-blue-500/15"
          />
          <span className="text-2xl font-extrabold tracking-tight text-slate-800">polio</span>
        </div>

        <motion.div
          initial={{ opacity: 0, scale: 0.95 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ duration: 0.4 }}
          className="w-full max-w-md"
        >
          <div className="mb-12 text-center">
            <div className="mb-6 inline-flex h-20 w-20 items-center justify-center rounded-3xl border border-blue-100 bg-blue-50 text-blue-500 shadow-sm">
              <Sparkles size={40} />
            </div>
            <h2 className="mb-4 text-3xl font-extrabold text-slate-800 sm:text-4xl">Welcome back</h2>
            <p className="text-lg font-medium text-slate-500">
              Continue with Google or start immediately as a guest.
            </p>
          </div>

          <div className="space-y-3">
            <button
              onClick={onGoogleLogin}
              disabled={isSigningIn !== null}
              className="group relative flex w-full items-center justify-center gap-3 rounded-2xl border-2 border-slate-100 bg-white px-6 py-4 text-lg font-bold text-slate-700 shadow-sm transition-all hover:border-slate-200 hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-60"
            >
              <img src="https://www.google.com/favicon.ico" alt="Google" className="h-6 w-6" />
              {isSigningIn === 'google' ? 'Signing in...' : 'Continue with Google'}
              <ArrowRight
                size={20}
                className="absolute right-6 text-slate-400 opacity-0 transition-all group-hover:translate-x-1 group-hover:opacity-100"
              />
            </button>

            <button
              onClick={onGuestLogin}
              disabled={isSigningIn !== null}
              className="group relative flex w-full items-center justify-center gap-3 rounded-2xl border-2 border-blue-100 bg-blue-50 px-6 py-4 text-lg font-bold text-blue-700 shadow-sm transition-all hover:border-blue-200 hover:bg-blue-100/70 disabled:cursor-not-allowed disabled:opacity-60"
            >
              <User size={20} className="text-blue-600" />
              {isSigningIn === 'guest' ? '게스트 로그인 중...' : '게스트로 시작하기'}
              <ArrowRight
                size={20}
                className="absolute right-6 text-blue-400 opacity-0 transition-all group-hover:translate-x-1 group-hover:opacity-100"
              />
            </button>
          </div>

          <p className="mt-6 text-center text-sm font-medium text-slate-400">
            Kakao and Naver login are temporarily disabled.
          </p>
        </motion.div>
      </div>
    </div>
  );
}
