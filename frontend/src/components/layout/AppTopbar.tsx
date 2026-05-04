import React from 'react';
import { Link, NavLink, useLocation } from 'react-router-dom';
import { ArrowLeft, Menu, X, LogOut, User } from 'lucide-react';
import { motion, AnimatePresence } from 'motion/react';
import { UniFoliLogo } from '../UniFoliLogo';
import { Button } from '../ui';
import { Topbar } from '../primitives';
import { appNavSections, type AppNavSection, isNavItemActive } from './nav-config';
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
  onOpenReview?: () => void;
  navSections?: AppNavSection[];
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
  onOpenReview,
  navSections = appNavSections,
}: AppTopbarProps) {
  const [isMobileMenuOpen, setIsMobileMenuOpen] = React.useState(false);
  const location = useLocation();
  const visibleGoals = (rankedGoals?.length ? rankedGoals : primaryGoal ? [primaryGoal] : []).slice(0, 3);
  const allNavItems = navSections.flatMap(section => section.items);

  const toggleMobileMenu = () => setIsMobileMenuOpen(!isMobileMenuOpen);
  const closeMobileMenu = () => setIsMobileMenuOpen(false);

  return (
    <>
      <Topbar mobile>
        <Link to="/app">
          <UniFoliLogo size="sm" subtitle={null} />
        </Link>
        <Button 
          variant="ghost" 
          size="icon" 
          aria-label="메뉴"
          onClick={toggleMobileMenu}
          className="relative z-[60]"
        >
          {isMobileMenuOpen ? <X size={24} /> : <Menu size={24} />}
        </Button>
      </Topbar>

      {/* Mobile Drawer */}
      <AnimatePresence>
        {isMobileMenuOpen && (
          <>
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              onClick={closeMobileMenu}
              className="fixed inset-0 z-50 bg-slate-900/40 backdrop-blur-sm lg:hidden"
            />
            <motion.div
              initial={{ x: '100%' }}
              animate={{ x: 0 }}
              exit={{ x: '100%' }}
              transition={{ type: 'spring', damping: 25, stiffness: 200 }}
              className="fixed inset-y-0 right-0 z-[55] w-[280px] bg-white shadow-2xl lg:hidden flex flex-col"
            >
              <div className="p-6 pt-24 space-y-8 flex-1 overflow-y-auto">
                <nav className="space-y-2">
                  {allNavItems.map(item => {
                    const active = isNavItemActive(location.pathname, item.path);
                    const Icon = item.icon;
                    return (
                      <NavLink
                        key={item.path}
                        to={item.path}
                        onClick={closeMobileMenu}
                        className={cn(
                          'flex items-center gap-4 px-5 py-4 rounded-2xl text-[16px] font-black transition-all',
                          active
                            ? 'bg-blue-50 text-[#3182f6]'
                            : 'text-[#4e5968] hover:bg-[#f2f4f6]'
                        )}
                      >
                        <Icon size={20} strokeWidth={active ? 2.5 : 2} />
                        {item.label}
                      </NavLink>
                    );
                  })}
                </nav>

                <div className="space-y-3 pt-6 border-t border-slate-100">
                  {onOpenReview && (
                    <button
                      onClick={() => {
                        closeMobileMenu();
                        onOpenReview();
                      }}
                      className="w-full flex items-center gap-3 px-5 py-4 rounded-2xl bg-indigo-50 text-indigo-700 font-black text-[15px]"
                    >
                      <span className="text-xl">🎁</span>
                      <span>이용후기 작성 (20% 할인)</span>
                    </button>
                  )}
                  <Link
                    to="/"
                    onClick={closeMobileMenu}
                    className="w-full flex items-center gap-3 px-5 py-4 rounded-2xl bg-[#f2f4f6] text-[#4e5968] font-black text-[15px]"
                  >
                    <ArrowLeft size={18} strokeWidth={2.5} />
                    홈으로 가기
                  </Link>
                </div>
              </div>

              {userName && (
                <div className="p-6 border-t border-slate-100 bg-slate-50/50">
                  <div className="flex items-center gap-4 mb-6">
                    <div className="h-12 w-12 overflow-hidden rounded-[14px] border border-white bg-white shadow-sm ring-1 ring-slate-200/50">
                      {userPhotoUrl ? (
                        <img src={userPhotoUrl} alt="프로필" className="h-full w-full object-cover" />
                      ) : (
                        <User size={24} className="text-[#b0b8c1]" strokeWidth={2.5} />
                      )}
                    </div>
                    <div className="flex flex-col">
                      <span className="text-[16px] font-black text-[#191f28]">{userName}님</span>
                      {isGuestSession && <span className="text-[11px] font-black text-[#3182f6]">Guest Session</span>}
                    </div>
                  </div>
                  {onLogout && (
                    <Button 
                      variant="ghost" 
                      onClick={onLogout}
                      className="w-full justify-start text-red-500 hover:text-red-600 hover:bg-red-50 font-black"
                    >
                      <LogOut size={18} className="mr-3" />
                      로그아웃
                    </Button>
                  )}
                </div>
              )}
            </motion.div>
          </>
        )}
      </AnimatePresence>

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
          {onOpenReview && (
            <Button
              variant="secondary"
              className="hidden sm:flex items-center gap-2 border border-blue-200 bg-blue-50/50 text-blue-700 hover:bg-blue-100 hover:text-blue-800 transition-colors h-11 px-4 rounded-2xl font-bold"
              onClick={onOpenReview}
            >
              <span className="text-xl">🎁</span>
              <span>이용후기 쓰고 20% 할인 받기</span>
            </Button>
          )}

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
