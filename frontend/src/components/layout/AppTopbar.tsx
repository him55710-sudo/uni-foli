import React from 'react';
import { Link, NavLink, useLocation } from 'react-router-dom';
import { ArrowLeft, Menu, X, LogOut, User } from 'lucide-react';
import { UniFoliLogo } from '../UniFoliLogo';
import { UniversityLogo } from '../UniversityLogo';
import { Button } from '../ui';
import { Topbar } from '../primitives';
import { appNavSections, isNavItemActive } from './nav-config';
import { cn } from '../../lib/cn';

interface GoalItem {
  university: string;
  major?: string;
}

interface AppTopbarProps {
  currentSectionLabel: string;
  summary: string;
  primaryGoal?: GoalItem | null;
  rankedGoals?: GoalItem[];
  userName?: string;
  userPhotoUrl?: string | null;
  isGuestSession?: boolean;
  onLogout?: () => void;
}

export function AppTopbar({
  currentSectionLabel,
  summary,
  primaryGoal,
  rankedGoals,
  userName,
  userPhotoUrl,
  isGuestSession,
  onLogout,
}: AppTopbarProps) {
  const location = useLocation();
  const visibleGoals = (rankedGoals?.length ? rankedGoals : primaryGoal ? [primaryGoal] : []).slice(0, 3);
  const allNavItems = appNavSections.flatMap(section => section.items);

  return (
    <>
      <Topbar mobile>
        <Link to="/app">
          <UniFoliLogo size="sm" subtitle={null} />
        </Link>
        <Button variant="ghost" size="icon" aria-label="메뉴">
          <Menu size={20} />
        </Button>
      </Topbar>

      <Topbar>
        <div className="flex items-center gap-10 flex-1">
          <Link to="/app" className="flex items-center transition-transform active:scale-95">
            <UniFoliLogo size="sm" subtitle={null} />
          </Link>

          {/* Navigation Links */}
          <nav className="hidden lg:flex items-center gap-1.5">
            {allNavItems.map(item => {
              const active = isNavItemActive(location.pathname, item.path);
              const Icon = item.icon;
              return (
                <NavLink
                  key={item.path}
                  to={item.path}
                  className={cn(
                    'flex items-center gap-2.5 px-5 h-11 rounded-2xl text-[14px] font-bold transition-all duration-200 active:scale-95',
                    active
                      ? 'bg-blue-50 text-[#3182f6]'
                      : 'text-[#6b7684] hover:bg-[#f2f4f6] hover:text-[#333d4b]'
                  )}
                >
                  <Icon size={18} strokeWidth={active ? 2.5 : 2} className={cn(active ? 'text-[#3182f6]' : 'text-[#b0b8c1]')} />
                  {item.label}
                </NavLink>
              );
            })}
          </nav>
        </div>

        <div className="flex items-center gap-4">
          <Link
            to="/"
            className="hidden sm:inline-flex items-center gap-2 rounded-2xl bg-[#f2f4f6] px-5 h-11 text-[14px] font-bold text-[#4e5968] transition-all hover:bg-[#e5e8eb] active:scale-95"
          >
            <ArrowLeft size={16} strokeWidth={2.5} />
            홈으로
          </Link>
          
          {userName && (
             <div className="flex items-center gap-4 pl-6 border-l border-[#e5e8eb]">
               <div className="flex flex-col items-end hidden sm:flex">
                 <span className="text-[14px] font-black text-[#191f28] leading-none mb-1">{userName}</span>
                 {isGuestSession && <span className="text-[10px] font-black text-[#3182f6] bg-blue-50 px-2 py-0.5 rounded-lg uppercase tracking-wider">Guest</span>}
               </div>
               <div className="h-11 w-11 overflow-hidden rounded-[14px] border border-[#f2f4f6] bg-white shadow-sm flex items-center justify-center transition-transform active:scale-95 ring-1 ring-slate-200/50">
                 {userPhotoUrl ? (
                   <img src={userPhotoUrl} alt="프로필" className="h-full w-full object-cover" />
                 ) : (
                   <User size={20} className="text-[#b0b8c1]" strokeWidth={2.5} />
                 )}
               </div>
               {onLogout && (
                 <button 
                  onClick={onLogout} 
                  className="flex h-11 w-11 items-center justify-center text-[#b0b8c1] hover:text-[#f04452] transition-all rounded-[14px] hover:bg-red-50 active:scale-90"
                  aria-label="로그아웃"
                 >
                   <LogOut size={20} strokeWidth={2.5} />
                 </button>
               )}
             </div>
          )}
        </div>
      </Topbar>
    </>
  );
}
