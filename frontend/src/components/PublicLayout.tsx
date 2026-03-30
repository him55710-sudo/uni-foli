import React, { useState } from 'react';
import { Link, NavLink, Outlet, useLocation } from 'react-router-dom';
import { ArrowRight, Menu, X } from 'lucide-react';
import { twMerge } from 'tailwind-merge';
import { useAuth } from '../contexts/AuthContext';
import { UniFoliaLogo } from './UniFoliaLogo';

const publicNavItems = [
  { to: '/', label: '홈' },
  { to: '/faq', label: 'FAQ' },
  { to: '/contact', label: '문의하기' },
];

function NavItem({ to, label, onClick }: { to: string; label: string; onClick?: () => void }) {
  return (
    <NavLink
      to={to}
      onClick={onClick}
      className={({ isActive }) =>
        twMerge(
          'rounded-full px-4 py-2 text-sm font-bold transition-colors',
          isActive ? 'bg-blue-50 text-blue-600' : 'text-slate-600 hover:bg-slate-100 hover:text-slate-900',
        )
      }
    >
      {label}
    </NavLink>
  );
}

export function PublicLayout() {
  const location = useLocation();
  const { isAuthenticated } = useAuth();
  const [isMenuOpen, setIsMenuOpen] = useState(false);

  const entryHref = isAuthenticated ? '/app' : '/auth';
  const entryLabel = isAuthenticated ? '앱으로 이동' : '무료로 시작하기';

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900">
      <header className="sticky top-0 z-40 border-b border-white/70 bg-white/80 backdrop-blur-xl">
        <div className="mx-auto flex max-w-7xl items-center justify-between gap-4 px-4 py-4 sm:px-6 lg:px-8">
          <Link to="/" className="flex items-center gap-3">
            <UniFoliaLogo size="md" />
          </Link>

          <nav className="hidden items-center gap-2 md:flex">
            {publicNavItems.map(item => (
              <NavItem key={item.to} to={item.to} label={item.label} />
            ))}
          </nav>

          <div className="hidden items-center gap-3 md:flex">
            {location.pathname !== '/auth' ? (
              <Link
                to={entryHref}
                className="inline-flex items-center gap-2 rounded-full bg-slate-900 px-5 py-3 text-sm font-black text-white shadow-lg shadow-slate-900/10 transition-transform hover:-translate-y-0.5"
              >
                {entryLabel}
                <ArrowRight size={16} />
              </Link>
            ) : null}
          </div>

          <button
            type="button"
            className="inline-flex h-11 w-11 items-center justify-center rounded-2xl border border-slate-200 bg-white text-slate-600 md:hidden"
            aria-label={isMenuOpen ? '공개 메뉴 닫기' : '공개 메뉴 열기'}
            onClick={() => setIsMenuOpen(open => !open)}
          >
            {isMenuOpen ? <X size={20} /> : <Menu size={20} />}
          </button>
        </div>

        {isMenuOpen ? (
          <div className="border-t border-slate-100 bg-white px-4 py-4 md:hidden">
            <div className="flex flex-col gap-2">
              {publicNavItems.map(item => (
                <NavItem key={item.to} to={item.to} label={item.label} onClick={() => setIsMenuOpen(false)} />
              ))}
              {location.pathname !== '/auth' ? (
                <Link
                  to={entryHref}
                  onClick={() => setIsMenuOpen(false)}
                  className="mt-2 inline-flex items-center justify-center gap-2 rounded-2xl bg-slate-900 px-5 py-3 text-sm font-black text-white"
                >
                  {entryLabel}
                  <ArrowRight size={16} />
                </Link>
              ) : null}
            </div>
          </div>
        ) : null}
      </header>

      <Outlet />

      <footer className="border-t border-slate-200 bg-white">
        <div className="mx-auto grid max-w-7xl gap-10 px-4 py-12 sm:px-6 lg:grid-cols-[1.3fr_0.7fr] lg:px-8">
          <div className="space-y-5">
            <UniFoliaLogo
              size="md"
              subtitle="근거 기반 drafting과 실행 가능한 다음 행동을 연결하는 학생 기록 중심 도구"
            />
            <div className="flex flex-wrap gap-3 text-sm font-semibold text-slate-500">
              <Link to="/faq" className="rounded-full bg-slate-100 px-4 py-2 hover:bg-slate-200">
                FAQ 보기
              </Link>
              <Link to="/contact" className="rounded-full bg-slate-100 px-4 py-2 hover:bg-slate-200">
                문의 허브
              </Link>
              <Link to="/contact?type=partnership" className="rounded-full bg-blue-50 px-4 py-2 text-blue-600 hover:bg-blue-100">
                학교·학원 협업 문의
              </Link>
            </div>
          </div>

          <div className="space-y-4 text-sm font-medium text-slate-500 lg:text-right">
            <div>
              <p className="text-xs font-black uppercase tracking-[0.22em] text-slate-400">Support</p>
              <p className="mt-2">
                이메일:{' '}
                <a className="font-bold text-slate-700 underline decoration-slate-200" href="mailto:mongben@naver.com">
                  mongben@naver.com
                </a>
              </p>
              <p className="mt-1">
                협업 문의:{' '}
                <a className="font-bold text-slate-700 underline decoration-slate-200" href="tel:01076142633">
                  010-7614-2633
                </a>
              </p>
            </div>
            <div className="flex flex-wrap gap-4 text-sm font-semibold lg:justify-end">
              <Link to="/terms" className="hover:text-slate-900">
                이용약관
              </Link>
              <Link to="/privacy" className="hover:text-slate-900">
                개인정보처리방침
              </Link>
            </div>
            <p className="text-xs leading-6 text-slate-400">
              Uni Folia는 합격을 보장하지 않으며, 실제 기록과 근거를 바탕으로 더 나은 준비를 돕는 방향을 우선합니다.
            </p>
          </div>
        </div>
      </footer>
    </div>
  );
}
