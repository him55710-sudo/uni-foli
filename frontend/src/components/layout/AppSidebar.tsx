import React, { useEffect, useMemo, useState } from 'react';
import { Link, NavLink } from 'react-router-dom';
import { 
  ArrowLeft, 
  ChevronDown, 
  ChevronRight, 
  ChevronLeft,
  Sparkles,
  Home,
  CheckCircle,
  BookOpen,
  Settings,
  User,
  LogOut
} from 'lucide-react';
import { UniFoliLogo } from '../UniFoliLogo';
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

  return (
    <Sidebar open={isOpen} aria-label="앱 주요 메뉴">
      {/* Desktop Toggle Button */}
      <div className="absolute -right-3 top-6 z-50 hidden md:block">
        <button 
          onClick={onToggle}
          className="flex h-6 w-6 items-center justify-center rounded-full border border-slate-200 bg-white shadow-sm hover:bg-slate-50 transition-colors"
        >
          {isOpen ? <ChevronLeft size={14} className="text-slate-600" /> : <ChevronRight size={14} className="text-slate-600" />}
        </button>
      </div>

      <div className={cn("flex flex-col h-full", !isOpen && "items-center")}>
        {/* Logo Section */}
        <div className={cn("p-6 mb-2", !isOpen && "px-2 py-6")}>
          <div className="flex items-center gap-3">
            <div className="flex bg-blue-600 p-2 rounded-xl text-white shadow-lg shadow-blue-200">
              <Sparkles size={20} />
            </div>
            {isOpen && <span className="text-xl font-bold bg-gradient-to-r from-blue-600 to-indigo-600 bg-clip-text text-transparent">Uni Foli</span>}
          </div>
        </div>

        <nav className="flex-1 overflow-y-auto px-3 py-2 space-y-6">
          {appNavSections.map(section => {
            const activeSection = section.items.some(item => isNavItemActive(pathname, item.path));
            const sectionOpen = !isOpen ? true : (openSections[section.key] ?? activeSection);

            return (
              <div key={section.key} className="space-y-1">
                {isOpen ? (
                  <button
                    type="button"
                    onClick={() => handleSectionToggle(section.key)}
                    className="mb-2 flex w-full items-center justify-between rounded-xl px-2 py-1.5 text-left transition-colors hover:bg-slate-50"
                    aria-expanded={sectionOpen}
                  >
                    <div>
                      <p className="text-[10px] font-black uppercase tracking-[0.2rem] text-slate-400">{section.label}</p>
                    </div>
                    <div className="flex items-center gap-2">
                      {sectionOpen ? <ChevronDown size={14} className="text-slate-400" /> : <ChevronRight size={14} className="text-slate-400" />}
                    </div>
                  </button>
                ) : (
                   <div className="h-px w-8 bg-slate-100 mx-auto my-4" />
                )}

                <div className={cn('space-y-1', !sectionOpen && isOpen && 'hidden')}>
                  {section.items.map(item => {
                    const active = isNavItemActive(pathname, item.path);
                    const Icon = item.icon;

                    return (
                      <NavLink
                        key={item.path}
                        to={item.path}
                        onClick={onCloseMobile}
                        className={cn(
                          'group flex items-center gap-3 rounded-xl px-3 py-2 text-sm transition-all duration-200',
                          active 
                            ? 'bg-blue-600 text-white shadow-md shadow-blue-100 font-semibold' 
                            : 'text-slate-500 hover:bg-slate-100 hover:text-slate-900',
                          !isOpen && 'justify-center px-0 h-10 w-10 mx-auto',
                        )}
                      >
                        <Icon size={18} className={cn(active ? 'text-white' : 'text-slate-400 group-hover:text-slate-700')} />
                        {isOpen && (
                          <div className="min-w-0 flex-1">
                            <p className="truncate">{item.label}</p>
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

        <div className="mt-auto border-t border-slate-100 p-4">
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
