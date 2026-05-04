/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import React, { lazy, Suspense, useEffect } from 'react';
import { BrowserRouter, Navigate, Route, Routes, useLocation, useParams } from 'react-router-dom';
import { Toaster } from 'react-hot-toast';
import { AuthProvider, useAuth } from './contexts/AuthContext';
import { RuntimeProvider } from './contexts/RuntimeContext';
import { GlobalErrorBoundary } from './components/GlobalErrorBoundary';

const PublicLayout = lazy(() => import('./components/PublicLayout').then(m => ({ default: m.PublicLayout })));
const Layout = lazy(() => import('./components/Layout').then(m => ({ default: m.Layout })));
const Auth = lazy(() => import('./pages/Auth').then(m => ({ default: m.Auth })));
const AuthCallback = lazy(() => import('./pages/AuthCallback').then(m => ({ default: m.AuthCallback })));
const Landing = lazy(() => import('./pages/Landing').then(m => ({ default: m.Landing })));
const Faq = lazy(() => import('./pages/Faq').then(m => ({ default: m.Faq })));
const Contact = lazy(() => import('./pages/Contact').then(m => ({ default: m.Contact })));
const Dashboard = lazy(() => import('./pages/Dashboard').then(m => ({ default: m.default })));
const Record = lazy(() => import('./pages/Record').then(m => ({ default: m.Record })));
const Workshop = lazy(() => import('./pages/Workshop').then(m => ({ default: m.Workshop })));
const Archive = lazy(() => import('./pages/Archive').then(m => ({ default: m.Archive })));
const Settings = lazy(() => import('./pages/Settings').then(m => ({ default: m.Settings })));
const Trends = lazy(() => import('./pages/Trends').then(m => ({ default: m.Trends })));
const Diagnosis = lazy(() => import('./pages/Diagnosis').then(m => ({ default: m.Diagnosis })));
const DiagnosisReports = lazy(() => import('./pages/DiagnosisReports').then(m => ({ default: m.DiagnosisReports })));
const Interview = lazy(() => import('./pages/Interview').then(m => ({ default: m.Interview })));
const RecordPdfHelp = lazy(() => import('./pages/RecordPdfHelp').then(m => ({ default: m.RecordPdfHelp })));
const TermsOfService = lazy(() => import('./pages/legal/LegalPages').then(m => ({ default: m.TermsOfService })));
const PrivacyPolicy = lazy(() => import('./pages/legal/LegalPages').then(m => ({ default: m.PrivacyPolicy })));
const RefundPolicy = lazy(() => import('./pages/legal/LegalPages').then(m => ({ default: m.RefundPolicy })));
const CookiesPolicy = lazy(() => import('./pages/legal/LegalPages').then(m => ({ default: m.CookiesPolicy })));
const MarketingPolicy = lazy(() => import('./pages/legal/LegalPages').then(m => ({ default: m.MarketingPolicy })));
const YouthPolicy = lazy(() => import('./pages/legal/LegalPages').then(m => ({ default: m.YouthPolicy })));
const DataDeletionPolicy = lazy(() => import('./pages/legal/LegalPages').then(m => ({ default: m.DataDeletionPolicy })));
const AdminDashboard = lazy(() => import('./pages/AdminDashboard').then(m => ({ default: m.default })));

function PageLoader() {
  return (
    <div className="flex h-screen items-center justify-center bg-slate-50">
      <div className="h-10 w-10 animate-spin rounded-full border-4 border-[#004aad] border-t-transparent" />
    </div>
  );
}

function RouteScrollManager() {
  const { pathname, search } = useLocation();

  useEffect(() => {
    window.scrollTo({ top: 0, left: 0, behavior: 'auto' });
  }, [pathname, search]);

  return null;
}

function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const { isAuthenticated, isGuestSession, loading } = useAuth();

  if (loading) {
    return <PageLoader />;
  }

  if (!isAuthenticated && !isGuestSession) {
    return <Navigate to="/auth" replace />;
  }

  return <>{children}</>;
}

function AdminRoute({ children }: { children: React.ReactNode }) {
  const { isAdmin, adminLoading, loading } = useAuth();

  if (loading || adminLoading) {
    return <PageLoader />;
  }

  if (!isAdmin) {
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

function LegacyEditorRedirect() {
  const location = useLocation();
  const { projectId } = useParams();

  if (projectId) {
    return <Navigate to={`/app/editor/${projectId}${location.search}`} replace />;
  }

  return <Navigate to={`/app/workshop${location.search}`} replace />;
}

const DocumentEditorPage = lazy(() => import('./pages/DocumentEditorPage').then(m => ({ default: m.DocumentEditorPage })));

export default function App() {
  return (
    <GlobalErrorBoundary>
      <RuntimeProvider>
        <AuthProvider>
          <BrowserRouter>
          <RouteScrollManager />
          <Toaster
            position="top-center"
            toastOptions={{
              duration: 3500,
              style: {
                background: '#0f172a',
                color: '#ffffff',
                borderRadius: '14px',
                fontWeight: '700',
                padding: '14px 18px',
                border: '1px solid rgba(255,255,255,0.08)',
              },
            }}
          />
          <Suspense fallback={<PageLoader />}>
            <Routes>
              <Route element={<PublicLayout />}>
                <Route path="/" element={<Landing />} />
                <Route path="/faq" element={<Faq />} />
                <Route path="/contact" element={<Contact />} />
                <Route path="/help/student-record-pdf" element={<RecordPdfHelp />} />
                <Route path="legal/terms" element={<TermsOfService />} />
                <Route path="legal/privacy" element={<PrivacyPolicy />} />
                <Route path="legal/refund" element={<RefundPolicy />} />
                <Route path="legal/cookies" element={<CookiesPolicy />} />
                <Route path="legal/marketing" element={<MarketingPolicy />} />
                <Route path="legal/youth" element={<YouthPolicy />} />
                <Route path="legal/data-deletion" element={<DataDeletionPolicy />} />
                
                {/* Legacy redirect routes */}
                <Route path="/privacy" element={<LegacyRouteRedirect to="/legal/privacy" />} />
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
                <Route path="record" element={<Navigate to="/app/diagnosis" replace />} />
                <Route path="help/student-record-pdf" element={<RecordPdfHelp />} />
                <Route path="diagnosis" element={<Diagnosis />} />
                <Route path="diagnosis/history" element={<DiagnosisReports />} />
                <Route path="workshop" element={<Workshop />} />
                <Route path="workshop/:projectId" element={<Workshop />} />
                <Route path="editor/:projectId" element={<DocumentEditorPage />} />
                <Route path="archive" element={<Archive />} />
                <Route path="trends" element={<Trends />} />
                <Route path="interview" element={<Interview />} />
                <Route path="interview/:projectId" element={<Interview />} />
                <Route path="settings" element={<Settings />} />
                <Route
                  path="admin"
                  element={
                    <AdminRoute>
                      <AdminDashboard />
                    </AdminRoute>
                  }
                />
              </Route>

              <Route
                path="/onboarding"
                element={<Navigate to="/app/diagnosis" replace />}
              />

              <Route path="/record" element={<LegacyRouteRedirect to="/app/diagnosis" />} />
              <Route path="/record/help" element={<LegacyRouteRedirect to="/app/help/student-record-pdf" />} />
              <Route path="/diagnosis" element={<LegacyRouteRedirect to="/app/diagnosis" />} />
              <Route path="/workshop" element={<LegacyWorkshopRedirect />} />
              <Route path="/workshop/:projectId" element={<LegacyWorkshopRedirect />} />
              <Route path="/archive" element={<LegacyRouteRedirect to="/app/archive" />} />
              <Route path="/trends" element={<LegacyRouteRedirect to="/app/trends" />} />
              <Route path="/interview" element={<LegacyRouteRedirect to="/app/interview" />} />
              <Route path="/settings" element={<LegacyRouteRedirect to="/app/settings" />} />
              <Route path="/editor/:projectId" element={<LegacyEditorRedirect />} />

              <Route path="*" element={<Navigate to="/" replace />} />
            </Routes>
          </Suspense>
        </BrowserRouter>
        </AuthProvider>
      </RuntimeProvider>
    </GlobalErrorBoundary>
  );
}
