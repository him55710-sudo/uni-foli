import React, { useEffect, useMemo, useState } from 'react';
import { Outlet, useLocation } from 'react-router-dom';
import { B2BPartnershipModal } from './B2BPartnershipModal';
import { ReviewModal } from './ReviewModal';
import { AppFooter } from './layout/AppFooter';
import { AppSidebar } from './layout/AppSidebar';
import { AppTopbar } from './layout/AppTopbar';
import { resolveCurrentNavSection } from './layout/nav-config';
import { useAuth } from '../contexts/AuthContext';
import { buildRankedGoals } from '../lib/rankedGoals';
import { useAuthStore } from '../store/authStore';
import { AppShell } from './primitives';

function isDesktopViewport() {
  return typeof window !== 'undefined' && window.innerWidth >= 768;
}

function getDesktopMediaQuery() {
  return typeof window !== 'undefined' ? window.matchMedia('(min-width: 768px)') : null;
}

export function Layout() {
  const location = useLocation();
  const { user, isGuestSession, logout } = useAuth();
  const dbUser = useAuthStore(state => state.user);

  const [isSidebarOpen, setIsSidebarOpen] = useState(isDesktopViewport);
  const [isPartnershipModalOpen, setIsPartnershipModalOpen] = useState(false);
  const [isReviewModalOpen, setIsReviewModalOpen] = useState(false);

  useEffect(() => {
    const mediaQuery = getDesktopMediaQuery();
    if (!mediaQuery) return;

    const syncSidebarByViewport = (event: MediaQueryListEvent | MediaQueryList) => {
      setIsSidebarOpen(event.matches);
    };

    syncSidebarByViewport(mediaQuery);
    mediaQuery.addEventListener('change', syncSidebarByViewport);
    return () => mediaQuery.removeEventListener('change', syncSidebarByViewport);
  }, []);

  useEffect(() => {
    if (!isDesktopViewport()) {
      setIsSidebarOpen(false);
    }
  }, [location.pathname]);

  const hasTargets = Boolean(dbUser?.target_university && dbUser?.target_major);
  const rankedGoals = useMemo(() => buildRankedGoals(dbUser, 6), [dbUser]);
  const primaryGoal = rankedGoals[0] ?? null;
  const currentSection = useMemo(() => resolveCurrentNavSection(location.pathname), [location.pathname]);

  const isEditorRoute = location.pathname.startsWith('/app/editor/');
  const isWorkshopRoute = location.pathname.startsWith('/app/workshop');
  const hideGlobalChrome = isEditorRoute;
  const shouldShowFooter = !isEditorRoute && !isWorkshopRoute;

  const workflowSummary = hasTargets
    ? `${currentSection.label} 단계 · 바로 실행`
    : '목표를 먼저 설정해 주세요.';

  const userName = user?.displayName || dbUser?.name || (isGuestSession ? '게스트' : '사용자');

  return (
    <>
      <B2BPartnershipModal isOpen={isPartnershipModalOpen} onClose={() => setIsPartnershipModalOpen(false)} />
      <ReviewModal isOpen={isReviewModalOpen} onClose={() => setIsReviewModalOpen(false)} />
      <AppShell
        topbar={
          hideGlobalChrome ? null : (
            <AppTopbar
              currentSectionLabel={currentSection.label}
              summary={workflowSummary}
              primaryGoal={primaryGoal}
              rankedGoals={rankedGoals}
              userName={userName}
              userPhotoUrl={user?.photoURL}
              isGuestSession={isGuestSession}
              onLogout={logout}
              onOpenReview={() => setIsReviewModalOpen(true)}
            />
          )
        }
        footer={shouldShowFooter ? <AppFooter onOpenPartnership={() => setIsPartnershipModalOpen(true)} /> : null}
        contentClassName={isEditorRoute || isWorkshopRoute ? 'flex min-h-0 flex-col overflow-hidden p-0 pb-0' : undefined}
      >
        <Outlet />
      </AppShell>
    </>
  );
}
