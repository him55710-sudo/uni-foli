/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import React, { lazy, Suspense } from 'react';
import { BrowserRouter, Navigate, Route, Routes, useLocation, useParams } from 'react-router-dom';
import { Toaster } from 'react-hot-toast';
import { AuthProvider, useAuth } from './contexts/AuthContext';
import { Layout } from './components/Layout';
import { GlobalErrorBoundary } from './components/GlobalErrorBoundary';
import { useAuthStore } from './store/authStore';

const PublicLayout = lazy(() => import('./components/PublicLayout').then(m => ({ default: m.PublicLayout })));
const Auth = lazy(() => import('./pages/Auth').then(m => ({ default: m.Auth })));
const AuthCallback = lazy(() => import('./pages/AuthCallback').then(m => ({ default: m.AuthCallback })));
const Landing = lazy(() => import('./pages/Landing').then(m => ({ default: m.Landing })));
const Faq = lazy(() => import('./pages/Faq').then(m => ({ default: m.Faq })));
const Contact = lazy(() => import('./pages/Contact').then(m => ({ default: m.Contact })));
const Dashboard = lazy(() => import('./pages/Dashboard').then(m => ({ default: m.Dashboard })));
const Record = lazy(() => import('./pages/Record').then(m => ({ default: m.Record })));
const Workshop = lazy(() => import('./pages/Workshop').then(m => ({ default: m.Workshop })));
const Archive = lazy(() => import('./pages/Archive').then(m => ({ default: m.Archive })));
const Settings = lazy(() => import('./pages/Settings').then(m => ({ default: m.Settings })));
const Trends = lazy(() => import('./pages/Trends').then(m => ({ default: m.Trends })));
const Diagnosis = lazy(() => import('./pages/Diagnosis').then(m => ({ default: m.Diagnosis })));
const Onboarding = lazy(() => import('./pages/Onboarding').then(m => ({ default: m.Onboarding })));
const TermsOfService = lazy(() => import('./pages/legal/LegalPages').then(m => ({ default: m.TermsOfService })));
const PrivacyPolicy = lazy(() => import('./pages/legal/LegalPages').then(m => ({ default: m.PrivacyPolicy })));

function PageLoader() {
  return (
    <div className="flex h-screen items-center justify-center bg-slate-50">
      <div className="h-10 w-10 animate-spin rounded-full border-4 border-blue-500 border-t-transparent" />
    </div>
  );
}

function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const location = useLocation();
  const { isAuthenticated, loading } = useAuth();
  const dbUser = useAuthStore(state => state.user);

  if (loading) {
    return <PageLoader />;
  }

  if (!isAuthenticated) {
    return <Navigate to="/auth" replace />;
  }

  const requiresOnboarding = Boolean(dbUser) && (!dbUser?.grade || !dbUser?.target_university || !dbUser?.target_major);

  if (requiresOnboarding && location.pathname !== '/onboarding') {
    return <Navigate to="/onboarding" replace />;
  }

  if (!requiresOnboarding && dbUser && location.pathname === '/onboarding') {
    return <Navigate to="/app" replace />;
  }

  return <>{children}</>;
}

function LegacyRouteRedirect({ to }: { to: string }) {
  const location = useLocation();
  return <Navigate to={`${to}${location.search}`} replace />;
}

function LegacyWorkshopRedirect() {
  const location = useLocation();
  const { projectId } = useParams();

  if (projectId) {
    return <Navigate to={`/app/workshop/${projectId}${location.search}`} replace />;
  }

  return <Navigate to={`/app/workshop${location.search}`} replace />;
}

export default function App() {
  return (
    <GlobalErrorBoundary>
      <AuthProvider>
        <BrowserRouter>
          <Toaster
            position="top-center"
            toastOptions={{
              duration: 3500,
              style: {
                background: '#1e293b',
                color: '#fff',
                borderRadius: '16px',
                fontWeight: '600',
                padding: '16px 24px',
              },
            }}
          />
          <Suspense fallback={<PageLoader />}>
            <Routes>
              <Route element={<PublicLayout />}>
                <Route path="/" element={<Landing />} />
                <Route path="/faq" element={<Faq />} />
                <Route path="/contact" element={<Contact />} />
                <Route path="/terms" element={<TermsOfService />} />
                <Route path="/privacy" element={<PrivacyPolicy />} />
              </Route>

              <Route path="/auth" element={<Auth />} />
              <Route path="/auth/callback/:provider" element={<AuthCallback />} />

              <Route
                path="/app"
                element={
                  <ProtectedRoute>
                    <Layout />
                  </ProtectedRoute>
                }
              >
                <Route index element={<Dashboard />} />
                <Route path="record" element={<Record />} />
                <Route path="diagnosis" element={<Diagnosis />} />
                <Route path="workshop" element={<Workshop />} />
                <Route path="workshop/:projectId" element={<Workshop />} />
                <Route path="archive" element={<Archive />} />
                <Route path="trends" element={<Trends />} />
                <Route path="settings" element={<Settings />} />
              </Route>

              <Route
                path="/onboarding"
                element={
                  <ProtectedRoute>
                    <Onboarding />
                  </ProtectedRoute>
                }
              />

              <Route path="/record" element={<LegacyRouteRedirect to="/app/record" />} />
              <Route path="/diagnosis" element={<LegacyRouteRedirect to="/app/diagnosis" />} />
              <Route path="/workshop" element={<LegacyWorkshopRedirect />} />
              <Route path="/workshop/:projectId" element={<LegacyWorkshopRedirect />} />
              <Route path="/archive" element={<LegacyRouteRedirect to="/app/archive" />} />
              <Route path="/trends" element={<LegacyRouteRedirect to="/app/trends" />} />
              <Route path="/settings" element={<LegacyRouteRedirect to="/app/settings" />} />

              <Route path="*" element={<Navigate to="/" replace />} />
            </Routes>
          </Suspense>
        </BrowserRouter>
      </AuthProvider>
    </GlobalErrorBoundary>
  );
}
