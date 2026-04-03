import React, { useEffect, useMemo, useState } from 'react';
import { Link, NavLink } from 'react-router-dom';
import { ArrowLeft, ChevronDown, ChevronRight, Menu, X } from 'lucide-react';
import { UniFoliaLogo } from '../UniFoliaLogo';
import { Badge, Button } from '../ui';
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

const SIDEBAR_SECTION_STATE_KEY = 'unifolia_sidebar_sections_v1';

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

  return (
    <Sidebar open={isOpen} aria-label="앱 주요 메뉴">
      <div className="hidden h-20 items-center gap-2 border-b border-slate-100 px-4 md:flex">
        <Link to="/app" className="min-w-0 flex-1">
          {isOpen ? <UniFoliaLogo size="md" subtitle={null} /> : <UniFoliaLogo size="sm" subtitle={null} markOnly />}
        </Link>
        <Button variant="ghost" size="icon" aria-label={isOpen ? '사이드바 축소' : '사이드바 확장'} onClick={onToggle}>
          {isOpen ? <X size={18} /> : <Menu size={18} />}
        </Button>
      </div>

      <nav className="flex-1 overflow-y-auto px-3 py-4">
        {appNavSections.map(section => {
          const activeSection = section.items.some(item => isNavItemActive(pathname, item.path));
          const sectionOpen = !isOpen ? true : (openSections[section.key] ?? activeSection);

          return (
            <div key={section.key} className="mb-4">
              {isOpen ? (
                <button
                  type="button"
                  onClick={() => handleSectionToggle(section.key)}
                  className="mb-2 flex w-full items-center justify-between rounded-xl px-2 py-1.5 text-left transition-colors hover:bg-slate-50"
                  aria-expanded={sectionOpen}
                >
                  <div>
                    <p className="text-[10px] font-black uppercase tracking-[0.2em] text-slate-400">{section.label}</p>
                    <p className="text-xs font-medium text-slate-400">{section.hint}</p>
                  </div>
                  <div className="flex items-center gap-2">
                    {activeSection ? <Badge tone="info">현재</Badge> : null}
                    {sectionOpen ? <ChevronDown size={15} className="text-slate-400" /> : <ChevronRight size={15} className="text-slate-400" />}
                  </div>
                </button>
              ) : null}

              <div className={cn('space-y-1.5', !sectionOpen && isOpen && 'hidden')}>
                {section.items.map(item => {
                  const active = isNavItemActive(pathname, item.path);
                  const Icon = item.icon;

                  return (
                    <NavLink
                      key={item.path}
                      to={item.path}
                      onClick={onCloseMobile}
                      className={cn(
                        'group flex items-center gap-3 rounded-2xl px-3 py-2.5 text-sm transition-colors',
                        active ? 'bg-blue-50 text-blue-700' : 'text-slate-500 hover:bg-slate-100 hover:text-slate-900',
                        !isOpen && 'justify-center px-0',
                      )}
                    >
                      <Icon size={18} className={cn(active ? 'text-blue-700' : 'text-slate-400 group-hover:text-slate-700')} />
                      {isOpen ? (
                        <div className="min-w-0 flex-1">
                          <p className="truncate font-bold">{item.label}</p>
                          <p className="truncate text-xs font-medium text-slate-400">{item.hint}</p>
                        </div>
                      ) : null}
                    </NavLink>
                  );
                })}
              </div>

              {isOpen && !sectionOpen && activeSection ? (
                <p className="px-2 text-xs font-semibold text-slate-400">현재 진행 중인 메뉴입니다.</p>
              ) : null}
            </div>
          );
        })}
      </nav>

      <div className="border-t border-slate-100 bg-slate-50/50 p-3">
        {isOpen ? (
          <Link to="/" className="mb-3 inline-flex w-full items-center justify-center gap-2 rounded-2xl border border-slate-300 bg-white px-3 py-2 text-sm font-bold text-slate-600 hover:bg-slate-50">
            <ArrowLeft size={14} />
            공개 페이지
          </Link>
        ) : null}

        <SidebarAccountBlock
          userName={userName}
          userPhotoUrl={userPhotoUrl}
          isGuestSession={isGuestSession}
          isExpanded={isOpen}
          onLogout={onLogout}
        />
      </div>
    </Sidebar>
  );
}

