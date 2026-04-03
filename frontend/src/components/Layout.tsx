import React, { useEffect, useMemo, useState } from 'react';
import { Outlet, useLocation } from 'react-router-dom';
import { B2BPartnershipModal } from './B2BPartnershipModal';
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

export function Layout() {
  const location = useLocation();
  const { user, isGuestSession, logout } = useAuth();
  const dbUser = useAuthStore(state => state.user);

  const [isSidebarOpen, setIsSidebarOpen] = useState(isDesktopViewport);
  const [isPartnershipModalOpen, setIsPartnershipModalOpen] = useState(false);

  useEffect(() => {
    const syncSidebarByViewport = () => {
      setIsSidebarOpen(isDesktopViewport());
    };

    syncSidebarByViewport();
    window.addEventListener('resize', syncSidebarByViewport);
    return () => window.removeEventListener('resize', syncSidebarByViewport);
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
    ? `${currentSection.label} 단계입니다. 지금 화면에서 다음 행동을 선택해 진행해 주세요.`
    : '먼저 목표 대학과 학과를 설정하면 준비 흐름이 시작됩니다.';

  const userName = user?.displayName || dbUser?.name || (isGuestSession ? '게스트' : '사용자');

  return (
    <>
      <B2BPartnershipModal isOpen={isPartnershipModalOpen} onClose={() => setIsPartnershipModalOpen(false)} />
      <AppShell
        topbar={
          hideGlobalChrome ? null : (
            <AppTopbar
              currentSectionLabel={currentSection.label}
              summary={workflowSummary}
              isSidebarOpen={isSidebarOpen}
              onToggleSidebar={() => setIsSidebarOpen(open => !open)}
              primaryGoal={primaryGoal}
              rankedGoals={rankedGoals}
            />
          )
        }
        sidebar={
          hideGlobalChrome ? null : (
            <AppSidebar
              pathname={location.pathname}
              isOpen={isSidebarOpen}
              onToggle={() => setIsSidebarOpen(open => !open)}
              onCloseMobile={() => {
                if (!isDesktopViewport()) setIsSidebarOpen(false);
              }}
              userName={userName}
              userPhotoUrl={user?.photoURL}
              isGuestSession={isGuestSession}
              onLogout={logout}
            />
          )
        }
        overlay={
          !hideGlobalChrome && isSidebarOpen && !isDesktopViewport() ? (
            <button
              type="button"
              aria-label="메뉴 닫기"
              onClick={() => setIsSidebarOpen(false)}
              className="absolute inset-0 z-20 bg-slate-900/30 backdrop-blur-[1px]"
            />
          ) : null
        }
        footer={shouldShowFooter ? <AppFooter onOpenPartnership={() => setIsPartnershipModalOpen(true)} /> : null}
        contentClassName={isEditorRoute ? 'p-0 pb-0' : undefined}
      >
        <Outlet />
      </AppShell>
    </>
  );
}

