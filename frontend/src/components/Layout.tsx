import React, { useEffect, useMemo, useState } from 'react';
import { Link, NavLink, Outlet, useLocation } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { useAuthStore } from '../store/authStore';
import {
  Archive,
  ArrowLeft,
  FileSearch,
  FolderOpen,
  Home,
  LogOut,
  Menu,
  PenTool,
  Settings,
  TrendingUp,
  X,
} from 'lucide-react';
import { clsx } from 'clsx';
import { twMerge } from 'tailwind-merge';
import { B2BPartnershipModal } from './B2BPartnershipModal';
import { UniFoliaLogo } from './UniFoliaLogo';

function cn(...inputs: (string | undefined | null | false)[]) {
  return twMerge(clsx(inputs));
}

function isItemActive(pathname: string, itemPath: string) {
  return pathname === itemPath || pathname.startsWith(`${itemPath}/`);
}

const navSections = [
  {
    key: 'prep',
    label: '준비',
    hint: '목표와 기록 정리',
    items: [
      { path: '/app', name: '대시보드', icon: Home, sub: '다음 행동과 진행 상태', badge: '시작' },
      { path: '/app/record', name: '내 생기부', icon: FolderOpen, sub: '기록 업로드와 처리 상태', badge: '1단계' },
    ],
  },
  {
    key: 'analysis',
    label: '분석',
    hint: '진단과 탐색',
    items: [
      { path: '/app/diagnosis', name: 'AI 진단', icon: FileSearch, sub: '근거 기반 분석', badge: '2단계' },
      { path: '/app/trends', name: '입시 트렌드', icon: TrendingUp, sub: '참고할 리소스', badge: '참고' },
    ],
  },
  {
    key: 'execution',
    label: '실행',
    hint: '작업과 결과물',
    items: [
      { path: '/app/workshop', name: 'Foli 작업실', icon: PenTool, sub: 'drafting과 피드백', badge: '3단계' },
      { path: '/app/archive', name: '보관함', icon: Archive, sub: '완료한 결과물', badge: '저장' },
    ],
  },
  {
    key: 'account',
    label: '관리',
    hint: '계정과 연결',
    items: [{ path: '/app/settings', name: '설정', icon: Settings, sub: '계정과 연결 상태', badge: '계정' }],
  },
];

export function Layout() {
  const location = useLocation();
  const { user, isGuestSession, logout } = useAuth();
  const dbUser = useAuthStore(state => state.user);
  const [isSidebarOpen, setIsSidebarOpen] = useState(() => {
    if (typeof window === 'undefined') return true;
    return window.innerWidth >= 768;
  });
  const [isB2BModalOpen, setIsB2BModalOpen] = useState(false);

  useEffect(() => {
    if (typeof window !== 'undefined' && window.innerWidth < 768) {
      setIsSidebarOpen(false);
    }
  }, [location.pathname]);

  const hasTargets = Boolean(dbUser?.target_university && dbUser?.target_major);
  const currentSection = useMemo(
    () =>
      navSections.find(section => section.items.some(item => isItemActive(location.pathname, item.path))) ?? navSections[0],
    [location.pathname],
  );

  const workflowSummary = hasTargets
    ? `${currentSection.label} 단계 중심으로 현재 작업을 이어가고 있습니다.`
    : '목표 설정을 먼저 마치면 준비 → 분석 → 실행 흐름이 더 선명해집니다.';

  return (
    <div className="flex h-screen flex-col overflow-hidden bg-slate-50 md:flex-row">
      <B2BPartnershipModal isOpen={isB2BModalOpen} onClose={() => setIsB2BModalOpen(false)} />

      <div className="z-30 flex items-center justify-between border-b border-slate-100 bg-white p-4 shadow-sm md:hidden">
        <Link to="/app" className="min-w-0">
          <UniFoliaLogo size="sm" subtitle={null} />
        </Link>
        <div className="flex items-center gap-2">
          <Link
            to="/"
            className="inline-flex items-center gap-1 rounded-full border border-slate-200 bg-slate-50 px-3 py-2 text-xs font-bold text-slate-600 transition-colors hover:bg-slate-100"
          >
            <ArrowLeft size={14} />
            소개 홈
          </Link>
          <button
            onClick={() => setIsSidebarOpen(open => !open)}
            aria-label={isSidebarOpen ? '사이드바 닫기' : '사이드바 열기'}
            className="rounded-xl p-2 text-slate-500 transition-colors hover:bg-slate-50"
          >
            {isSidebarOpen ? <X size={24} /> : <Menu size={24} />}
          </button>
        </div>
      </div>

      <aside
        className={cn(
          'absolute z-20 flex h-full flex-col border-r border-slate-100 bg-white pt-[73px] shadow-sm transition-all duration-300 md:relative md:pt-0',
          isSidebarOpen ? 'w-72 translate-x-0' : 'w-20 -translate-x-full md:translate-x-0',
        )}
      >
        <div className="hidden h-20 items-center justify-between border-b border-slate-100 px-6 md:flex">
          {isSidebarOpen ? <UniFoliaLogo size="md" subtitle={null} /> : <UniFoliaLogo size="sm" subtitle={null} markOnly />}
          <button
            onClick={() => setIsSidebarOpen(open => !open)}
            aria-label={isSidebarOpen ? '사이드바 접기' : '사이드바 펼치기'}
            className="ml-auto rounded-xl p-2 text-slate-400 transition-colors hover:bg-slate-50 hover:text-slate-600"
          >
            {isSidebarOpen ? <X size={20} /> : <Menu size={20} />}
          </button>
        </div>

        <nav className="flex-1 overflow-y-auto px-4 py-6">
          {isSidebarOpen ? (
            <div className="mb-6 rounded-[28px] border border-slate-200 bg-slate-50/80 p-4 shadow-sm">
              <p className="text-[10px] font-black uppercase tracking-[0.22em] text-blue-600">Workflow</p>
              <p className="mt-2 text-sm font-black text-slate-900">준비 → 분석 → 실행</p>
              <p className="mt-2 text-xs font-medium leading-relaxed text-slate-500">{workflowSummary}</p>
            </div>
          ) : null}

          {navSections.map(section => {
            const sectionActive = section.items.some(item => isItemActive(location.pathname, item.path));

            return (
              <div key={section.key} className="mb-6">
                {isSidebarOpen ? (
                  <div className="mb-3 flex items-start justify-between gap-3 px-2">
                    <div>
                      <p className="text-[11px] font-black uppercase tracking-[0.22em] text-slate-400">{section.label}</p>
                      <p className="text-[11px] font-medium text-slate-400">{section.hint}</p>
                    </div>
                    {sectionActive ? (
                      <span className="rounded-full border border-blue-100 bg-blue-50 px-2.5 py-1 text-[10px] font-black text-blue-600">
                        현재
                      </span>
                    ) : null}
                  </div>
                ) : null}

                <div className="space-y-2">
                  {section.items.map(item => {
                    const isActive = isItemActive(location.pathname, item.path);
                    const Icon = item.icon;

                    return (
                      <NavLink
                        key={item.path}
                        to={item.path}
                        className={cn(
                          'group flex items-center gap-3 rounded-2xl px-4 py-3.5 transition-all duration-200',
                          isActive
                            ? 'border border-blue-100 bg-blue-50 text-blue-600 shadow-sm'
                            : 'text-slate-500 hover:bg-slate-50 hover:text-slate-800',
                          !isSidebarOpen && 'justify-center px-0',
                        )}
                      >
                        <Icon
                          size={22}
                          className={cn(
                            'flex-shrink-0 transition-transform duration-300 group-hover:scale-110',
                            isActive ? 'text-blue-600' : '',
                          )}
                        />

                        {isSidebarOpen ? (
                          <div className="flex min-w-0 flex-1 items-center justify-between gap-3">
                            <div className="min-w-0">
                              <span className={cn('block text-[15px] font-bold', isActive ? 'font-extrabold' : '')}>{item.name}</span>
                              <span className="block text-[11px] font-medium text-slate-400 transition-colors group-hover:text-slate-500">
                                {item.sub}
                              </span>
                            </div>
                            <span
                              className={cn(
                                'h-2.5 w-2.5 flex-shrink-0 rounded-full transition-opacity',
                                isActive ? 'bg-blue-600 opacity-100' : 'bg-slate-200 opacity-0 group-hover:opacity-100',
                              )}
                            />
                          </div>
                        ) : null}
                      </NavLink>
                    );
                  })}
                </div>
              </div>
            );
          })}
        </nav>

        <div className="border-t border-slate-100 bg-slate-50/50 p-4">
          {isSidebarOpen ? (
            <Link
              to="/"
              className="mb-3 inline-flex items-center gap-2 rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm font-bold text-slate-600 shadow-sm transition-colors hover:bg-slate-50 hover:text-slate-900"
            >
              <ArrowLeft size={16} />
              공개 홈으로 돌아가기
            </Link>
          ) : null}
          <div
            className={cn(
              'rounded-2xl border border-transparent p-3 transition-colors hover:border-slate-200 hover:bg-white hover:shadow-sm',
              !isSidebarOpen && 'flex justify-center',
            )}
          >
            <div className="flex items-center gap-3">
              {user?.photoURL ? (
                <img src={user.photoURL} alt="Profile" className="h-10 w-10 rounded-full border-2 border-white object-cover shadow-sm" />
              ) : (
                <div className="flex h-10 w-10 items-center justify-center rounded-full bg-blue-50 text-sm font-black text-blue-700 shadow-sm">
                  {(user?.displayName || (isGuestSession ? '게스트' : 'Uni Folia')).trim().slice(0, 1).toUpperCase()}
                </div>
              )}
              {isSidebarOpen ? (
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm font-extrabold text-slate-800">
                    {user?.displayName || (isGuestSession ? '게스트' : '사용자')}
                  </p>
                  {isGuestSession ? (
                    <NavLink
                      to="/app/settings"
                      className="mt-1 inline-flex text-[11px] font-bold text-blue-600 transition-colors hover:text-blue-700"
                    >
                      Google 연결로 기록 이어가기
                    </NavLink>
                  ) : null}
                  <button
                    onClick={logout}
                    className="mt-1 flex items-center gap-1 text-xs font-medium text-slate-500 transition-colors hover:text-red-500"
                  >
                    <LogOut size={12} /> 로그아웃
                  </button>
                </div>
              ) : null}
            </div>
          </div>
        </div>
      </aside>

      {isSidebarOpen ? (
        <div
          className="fixed inset-0 z-10 bg-slate-900/20 backdrop-blur-sm md:hidden"
          onClick={() => setIsSidebarOpen(false)}
        />
      ) : null}

      <main className="relative flex min-w-0 flex-1 flex-col overflow-hidden">
        <header className="sticky top-0 z-10 hidden h-20 items-center justify-between border-b border-slate-100 bg-white/80 px-8 backdrop-blur-md md:flex">
          <div className="flex items-center gap-4">
            <div className="inline-flex items-center gap-2 rounded-xl border border-slate-200 bg-white px-4 py-2 text-sm font-extrabold text-slate-700 shadow-sm">
              <span className="h-2.5 w-2.5 rounded-full bg-blue-500" />
              현재 단계 · {currentSection.label}
            </div>
            <p className="hidden text-sm font-medium text-slate-500 xl:block">{workflowSummary}</p>
          </div>
          <Link
            to="/"
            className="inline-flex items-center gap-2 rounded-xl border border-slate-200 bg-white px-4 py-2 text-sm font-bold text-slate-600 shadow-sm transition-colors hover:bg-slate-50 hover:text-slate-900"
          >
            <ArrowLeft size={16} />
            소개 홈
          </Link>
        </header>

        <div className="relative flex flex-1 flex-col overflow-auto p-4 pb-24 sm:p-6 md:p-8 md:pb-8">
          <div className="flex-1">
            <Outlet />
          </div>

          <footer className="mt-16 rounded-3xl border border-slate-200 bg-white px-8 py-12 shadow-sm">
            <div className="flex flex-col items-start justify-between gap-12 text-sm font-medium text-slate-500 md:flex-row">
              <div className="flex-1 space-y-6">
                <UniFoliaLogo size="sm" subtitle={null} />

                <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
                  <div className="space-y-2">
                    <p className="w-fit rounded bg-slate-100 px-2 py-0.5 text-[11px] font-black uppercase tracking-widest text-slate-700">
                      공개 홈
                    </p>
                    <p className="text-xs leading-6">
                      서비스 소개, FAQ, 문의 허브는 공개 홈에서 다시 확인할 수 있습니다.
                    </p>
                    <Link to="/" className="inline-flex text-xs font-bold text-blue-600 transition-colors hover:text-blue-700">
                      공개 홈 보기
                    </Link>
                  </div>

                  <div className="space-y-2">
                    <p className="w-fit rounded bg-slate-100 px-2 py-0.5 text-[11px] font-black uppercase tracking-widest text-slate-700">
                      약관 / 정책
                    </p>
                    <div className="flex gap-4 text-xs">
                      <Link to="/terms" className="font-extrabold transition-colors hover:text-blue-600">
                        이용약관
                      </Link>
                      <Link to="/privacy" className="font-extrabold transition-colors hover:text-blue-600">
                        개인정보처리방침
                      </Link>
                    </div>
                  </div>

                  <div className="space-y-2">
                    <p className="w-fit rounded bg-blue-50 px-2 py-0.5 text-[11px] font-black uppercase tracking-widest text-slate-700">
                      문의 허브
                    </p>
                    <p className="text-xs leading-6">
                      더 자세한 지원 경로는 공개 문의 허브에서 확인하세요.
                    </p>
                    <Link to="/contact" className="inline-flex text-xs font-bold text-blue-600 transition-colors hover:text-blue-700">
                      지원 허브로 이동
                    </Link>
                  </div>

                  <div className="space-y-2">
                    <p className="w-fit rounded bg-blue-100/50 px-2 py-0.5 text-[11px] font-black uppercase tracking-widest text-blue-700">
                      협업 문의
                    </p>
                    <p className="text-xs leading-6">
                      학교·학원 도입 문의는 공개 문의 허브 또는 빠른 모달 접수로 연결할 수 있습니다.
                    </p>
                    <div className="flex flex-wrap gap-2">
                      <Link
                        to="/contact?type=partnership"
                        className="rounded-full border border-blue-100 bg-blue-50 px-3 py-1.5 text-[11px] font-black text-blue-600"
                      >
                        문의 허브 열기
                      </Link>
                      <button
                        onClick={() => setIsB2BModalOpen(true)}
                        className="rounded-full bg-blue-600 px-3 py-1.5 text-[11px] font-black text-white shadow-sm transition-colors hover:bg-blue-700"
                      >
                        빠른 접수
                      </button>
                    </div>
                  </div>
                </div>

                <div className="flex flex-wrap gap-x-4 gap-y-1 text-[11px] text-slate-400">
                  <span>상호명 Uni Folia</span>
                  <span className="text-slate-200 md:inline">|</span>
                  <span>대표 임현수</span>
                  <span className="text-slate-200 md:inline">|</span>
                  <span>사업자 등록번호 준비 중</span>
                </div>
              </div>

              <div className="space-y-2 md:text-right">
                <div className="mb-4 text-xs font-black uppercase tracking-[0.2em] text-slate-300">
                  Evidence-Grounded Drafting
                </div>
                <div className="text-[11px] font-semibold text-slate-400">© 2026 Uni Folia. All rights reserved.</div>
                <p className="max-w-[240px] text-[10px] leading-relaxed text-slate-300 md:ml-auto">
                  Uni Folia는 학생 기록과 탐구 흐름을 정리하도록 돕는 도구이며, 최종 입시 결과를 보장하지 않습니다.
                </p>
              </div>
            </div>
          </footer>
        </div>
      </main>
    </div>
  );
}
