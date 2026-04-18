import React, { useEffect, useMemo, useState } from 'react';
import { Link, NavLink } from 'react-router-dom';
import { ChevronDown, ChevronLeft, ChevronRight } from 'lucide-react';
import { UniFoliLogo } from '../UniFoliLogo';
import { appNavSections, isNavItemActive } from './nav-config';
import { Sidebar } from '../primitives';
import { SidebarAccountBlock } from './SidebarAccountBlock';
import { cn } from '../../lib/cn';

interface AppSidebarProps {
  pathname: string;
  isOpen: boolean;
  onToggle: () => void;
  onCloseMobile: () => void;
  userName: string;
  userPhotoUrl?: string | null;
  isGuestSession: boolean;
  onLogout: () => void;
}

const SIDEBAR_SECTION_STATE_KEY = 'unifoli_sidebar_sections_v1';

export function AppSidebar({
  pathname,
  isOpen,
  onToggle,
  onCloseMobile,
  userName,
  userPhotoUrl,
  isGuestSession,
  onLogout,
}: AppSidebarProps) {
  const activeSectionKey = useMemo(() => {
    const activeSection = appNavSections.find(section => section.items.some(item => isNavItemActive(pathname, item.path)));
    return activeSection?.key ?? appNavSections[0]?.key ?? '';
  }, [pathname]);

  const [openSections, setOpenSections] = useState<Record<string, boolean>>(() =>
    appNavSections.reduce<Record<string, boolean>>((acc, section) => {
      acc[section.key] = section.key === activeSectionKey;
      return acc;
    }, {}),
  );

  useEffect(() => {
    if (typeof window === 'undefined') return;
    try {
      const raw = window.localStorage.getItem(SIDEBAR_SECTION_STATE_KEY);
      if (!raw) return;
      const parsed = JSON.parse(raw) as Record<string, boolean>;
      if (!parsed || typeof parsed !== 'object') return;
      setOpenSections(prev => ({ ...prev, ...parsed }));
    } catch {
      // Ignore invalid localStorage payload.
    }
  }, []);

  useEffect(() => {
    if (!activeSectionKey) return;
    setOpenSections(prev => {
      if (prev[activeSectionKey]) return prev;
      const next = { ...prev, [activeSectionKey]: true };
      if (typeof window !== 'undefined') {
        window.localStorage.setItem(SIDEBAR_SECTION_STATE_KEY, JSON.stringify(next));
      }
      return next;
    });
  }, [activeSectionKey]);

  const handleSectionToggle = (sectionKey: string) => {
    setOpenSections(prev => {
      const next = { ...prev, [sectionKey]: !prev[sectionKey] };
      if (typeof window !== 'undefined') {
        window.localStorage.setItem(SIDEBAR_SECTION_STATE_KEY, JSON.stringify(next));
      }
      return next;
    });
  };

  const sectionToneClass = (sectionKey: string) => {
    switch (sectionKey) {
      case 'setup':
        return 'text-sky-700';
      case 'analyze':
        return 'text-violet-700';
      case 'execute':
        return 'text-emerald-700';
      default:
        return 'text-amber-700';
    }
  };

  const sectionActiveItemClass = (sectionKey: string) => {
    switch (sectionKey) {
      case 'setup':
        return 'bg-gradient-to-br from-sky-500 to-cyan-500 text-white shadow-lg shadow-cyan-200/60';
      case 'analyze':
        return 'bg-gradient-to-br from-violet-500 to-fuchsia-500 text-white shadow-lg shadow-violet-200/60';
      case 'execute':
        return 'bg-gradient-to-br from-emerald-500 to-teal-500 text-white shadow-lg shadow-emerald-200/60';
      default:
        return 'bg-gradient-to-br from-amber-500 to-orange-500 text-white shadow-lg shadow-amber-200/60';
    }
  };

  return (
    <Sidebar open={isOpen} aria-label="앱 주요 메뉴">
      {/* Desktop Toggle Button */}
      <div className="absolute -right-3 top-6 z-50 hidden md:block">
        <button 
          onClick={onToggle}
          className="flex h-7 w-7 items-center justify-center rounded-full border border-white/80 bg-white/90 shadow-[0_14px_28px_rgba(42,64,132,0.14)] transition-colors hover:bg-[#f6f8ff]"
        >
          {isOpen ? <ChevronLeft size={14} className="text-[#3056a4]" /> : <ChevronRight size={14} className="text-[#3056a4]" />}
        </button>
      </div>

      <div className={cn('flex h-full flex-col', !isOpen && 'items-center')}>
        {/* Logo Section */}
        <div className={cn('mb-2 px-6 pb-2 pt-6', !isOpen && 'px-2 py-6')}>
          <Link to="/app" onClick={onCloseMobile} className={cn('flex', !isOpen && 'justify-center')}>
            <UniFoliLogo size={isOpen ? 'md' : 'sm'} markOnly={!isOpen} subtitle={null} />
          </Link>
        </div>

        <nav className="flex-1 space-y-7 overflow-y-auto px-3 py-3">
          {appNavSections.map(section => {
            const activeSection = section.items.some(item => isNavItemActive(pathname, item.path));
            const sectionOpen = !isOpen ? true : (openSections[section.key] ?? activeSection);

            return (
              <div key={section.key} className="space-y-1">
                {isOpen ? (
                  <button
                    type="button"
                    onClick={() => handleSectionToggle(section.key)}
                    className="mb-2 flex w-full items-center justify-between rounded-2xl px-3 py-2 text-left transition-colors hover:bg-white/60"
                    aria-expanded={sectionOpen}
                  >
                    <div className="min-w-0">
                      <p className={cn('text-[10px] font-black uppercase tracking-[0.22rem]', sectionToneClass(section.key))}>{section.label}</p>
                      <p className="mt-1 text-xs font-medium text-slate-400">{section.hint}</p>
                    </div>
                    <div className="flex items-center gap-2">
                      {sectionOpen ? <ChevronDown size={14} className="text-[#6a83b1]" /> : <ChevronRight size={14} className="text-[#6a83b1]" />}
                    </div>
                  </button>
                ) : (
                   <div className="mx-auto my-4 h-px w-8 bg-[#dce8ff]" />
                )}

                <div className={cn('space-y-1', !sectionOpen && isOpen && 'hidden')}>
                  {section.items.map(item => {
                    const active = isNavItemActive(pathname, item.path);
                    const Icon = item.icon;
                    const activeClass = sectionActiveItemClass(section.key);

                    return (
                      <NavLink
                        key={item.path}
                        to={item.path}
                        onClick={onCloseMobile}
                        className={cn(
                          'group flex items-center gap-3 rounded-2xl px-3.5 py-3 text-sm transition-all duration-200',
                          active ? `${activeClass} font-bold` : 'text-slate-500 hover:bg-white/72 hover:text-slate-900',
                          !isOpen && 'mx-auto h-11 w-11 justify-center px-0 transition-transform hover:scale-105',
                        )}
                      >
                        <Icon size={18} className={cn(active ? 'text-white' : 'text-slate-400 group-hover:text-indigo-600')} />
                        {isOpen && (
                          <div className="min-w-0 flex-1">
                            <p className="truncate font-bold tracking-tight">{item.label}</p>
                            <p className={cn('mt-0.5 truncate text-[11px] font-semibold', active ? 'text-white/80' : 'text-slate-400')}>
                              {item.hint}
                            </p>
                          </div>
                        )}
                      </NavLink>
                    );
                  })}
                </div>
              </div>
            );
          })}
        </nav>

        <div className="mt-auto border-t border-slate-100/50 p-4 bg-white/40 backdrop-blur-sm">
          <SidebarAccountBlock
            userName={userName}
            userPhotoUrl={userPhotoUrl}
            isGuestSession={isGuestSession}
            isExpanded={isOpen}
            onLogout={onLogout}
          />
        </div>
      </div>
    </Sidebar>
  );
}
