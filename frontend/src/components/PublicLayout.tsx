import React, { useMemo, useState } from 'react';
import { Link, NavLink, Outlet, useLocation } from 'react-router-dom';
import { ArrowRight, Menu, X } from 'lucide-react';
import { useAuth } from '../contexts/AuthContext';
import { UniFoliLogo } from './UniFoliLogo';
import { buttonClassName } from './ui';
import { cn } from '../lib/cn';

const navItems = [
  { to: '/', label: '소개' },
  { to: '/faq', label: '자주 묻는 질문' },
  { to: '/contact', label: '문의' },
];

function PublicNavItem({ to, label, onClick }: { to: string; label: string; onClick?: () => void }) {
  return (
    <NavLink
      to={to}
      onClick={onClick}
      className={({ isActive }) =>
        cn(
          'rounded-2xl px-3.5 py-2.5 text-sm font-black transition-all',
          isActive
            ? 'bg-[#7C3AED] text-white shadow-lg shadow-violet-100'
            : 'text-[#4e5968] hover:bg-[#F5F3FF] hover:text-[#7C3AED]',
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
  const [menuOpen, setMenuOpen] = useState(false);
  const scrollToTop = () => {
    window.scrollTo({ top: 0, left: 0, behavior: 'auto' });
  };

  const handleDesktopNavClick = () => {
    scrollToTop();
  };

  const handleMobileNavClick = () => {
    scrollToTop();
    setMenuOpen(false);
  };

  const entry = useMemo(
    () => ({
      href: isAuthenticated ? '/app' : '/auth',
      label: isAuthenticated ? '앱으로 이동' : '무료로 시작하기',
    }),
    [isAuthenticated],
  );

  return (
    <div className="min-h-screen bg-[#f8fafc] text-slate-900">
      <header className="sticky top-0 z-40 border-b border-white/70 bg-white/72 backdrop-blur-2xl">
        <div className="mx-auto flex max-w-7xl items-center justify-between gap-4 px-4 py-3.5 sm:px-6 lg:px-8">
          <Link to="/" onClick={handleDesktopNavClick}>
            <UniFoliLogo size="md" subtitle={null} />
          </Link>

          <nav className="hidden items-center gap-1 md:flex">
            {navItems.map(item => (
              <PublicNavItem key={item.to} to={item.to} label={item.label} onClick={handleDesktopNavClick} />
            ))}
          </nav>

          <div className="hidden md:block">
            {location.pathname !== '/auth' ? (
              <Link
                to={entry.href}
                onClick={handleDesktopNavClick}
                className={cn(
                  buttonClassName({ variant: 'primary', size: 'md' }),
                  'bg-[#7C3AED] shadow-violet-200/70 hover:bg-[#5B21B6] focus-visible:ring-[#7C3AED]/30',
                )}
              >
                {entry.label}
                <ArrowRight size={16} />
              </Link>
            ) : null}
          </div>

          <button
            type="button"
            onClick={() => setMenuOpen(open => !open)}
            aria-label={menuOpen ? '메뉴 닫기' : '메뉴 열기'}
            className="inline-flex h-11 w-11 items-center justify-center rounded-2xl border border-white/70 bg-white/84 text-[#7C3AED] shadow-[0_12px_26px_rgba(124,58,237,0.12)] backdrop-blur-md md:hidden"
          >
            {menuOpen ? <X size={18} /> : <Menu size={18} />}
          </button>
        </div>

        {menuOpen ? (
          <div className="border-t border-white/70 bg-white/86 px-4 py-3 backdrop-blur-xl md:hidden">
            <div className="flex flex-col gap-1">
              {navItems.map(item => (
                <PublicNavItem key={item.to} to={item.to} label={item.label} onClick={handleMobileNavClick} />
              ))}
              {location.pathname !== '/auth' ? (
                <Link
                  to={entry.href}
                  onClick={handleMobileNavClick}
                  className={cn(
                    buttonClassName({ variant: 'primary', size: 'md', fullWidth: true }),
                    'bg-[#7C3AED] shadow-violet-200/70 hover:bg-[#5B21B6] focus-visible:ring-[#7C3AED]/30',
                  )}
                >
                  {entry.label}
                  <ArrowRight size={16} />
                </Link>
              ) : null}
            </div>
          </div>
        ) : null}
      </header>

      <Outlet />

      <footer className="border-t border-white/70 bg-white/72 backdrop-blur-xl">
        <div className="mx-auto grid max-w-7xl gap-10 px-4 py-12 sm:px-6 lg:grid-cols-[1.4fr_0.6fr] lg:px-8">
          <div className="space-y-4">
            <UniFoliLogo
              size="md"
              subtitle="진단 · 트렌드 · 워크숍"
            />
            <p className="max-w-2xl text-sm font-medium leading-7 text-slate-500">
              필요한 기능만 고르면 바로 실행됩니다.
            </p>
            <div className="flex flex-wrap gap-3">
              <Link to="/faq" onClick={handleDesktopNavClick} className={buttonClassName({ variant: 'secondary', size: 'sm' })}>
                자주 묻는 질문
              </Link>
              <Link to="/contact" onClick={handleDesktopNavClick} className={buttonClassName({ variant: 'secondary', size: 'sm' })}>
                문의하기
              </Link>
            </div>
          </div>

          <div className="space-y-4 text-sm font-medium text-slate-500 lg:text-right">
            <div>
              <p className="text-xs font-bold uppercase tracking-[0.18em] text-slate-400">지원</p>
              <p className="mt-2">
                <a className="font-semibold text-[#6d28d9] hover:text-[#0e7490]" href="mailto:mongben@naver.com">
                  mongben@naver.com
                </a>
              </p>
              <p className="mt-1">
                <a className="font-semibold text-[#6d28d9] hover:text-[#0e7490]" href="tel:01076142633">
                  010-7614-2633
                </a>
              </p>
            </div>
            <div className="flex flex-wrap gap-4 lg:justify-end">
              <Link to="/terms" onClick={handleDesktopNavClick} className="font-semibold text-slate-600 hover:text-slate-900">
                이용약관
              </Link>
              <Link to="/privacy" onClick={handleDesktopNavClick} className="font-semibold text-slate-600 hover:text-slate-900">
                개인정보처리방침
              </Link>
            </div>
            <p className="text-xs leading-6 text-slate-400">UniFoli는 준비 과정의 품질 향상을 지원하며, 입시 결과를 보장하지 않습니다.</p>
          </div>
        </div>
      </footer>
    </div>
  );
}
