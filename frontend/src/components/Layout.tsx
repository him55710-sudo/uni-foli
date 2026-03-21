import React, { useState } from 'react';
import { NavLink, Outlet } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { 
  Home, 
  FolderOpen, 
  PenTool, 
  Archive, 
  TrendingUp, 
  Settings,
  Menu,
  X,
  LogOut
} from 'lucide-react';
import { clsx } from 'clsx';
import { twMerge } from 'tailwind-merge';
import poliDuoMascot from '../assets/poli-duo.png';

function cn(...inputs: (string | undefined | null | false)[]) {
  return twMerge(clsx(inputs));
}

const navItems = [
  { path: '/', name: '홈', icon: Home, sub: '대시보드' },
  { path: '/record', name: '내 생기부', icon: FolderOpen, sub: '데이터 관리' },
  { path: '/workshop', name: 'Poli 작업실', icon: PenTool, sub: 'AI 멘토' },
  { path: '/archive', name: '내 보관함', icon: Archive, sub: '결과물' },
  { path: '/trends', name: '입시 트렌드', icon: TrendingUp, sub: '리소스' },
  { path: '/settings', name: '설정 및 내 정보', icon: Settings, sub: '프로필/구독' },
];

export function Layout() {
  const { user, isGuestSession, logout } = useAuth();
  const [isSidebarOpen, setIsSidebarOpen] = useState(true);

  return (
    <div className="flex flex-col md:flex-row h-screen bg-slate-50 overflow-hidden">
      {/* Mobile Header */}
      <div className="md:hidden flex items-center justify-between p-4 bg-white border-b border-slate-100 z-30 shadow-sm">
        <div className="flex items-center gap-2">
          <img src={poliDuoMascot} alt="Polio mascot" className="w-8 h-8 rounded-xl object-cover border border-blue-100 bg-white p-0.5 shadow-sm" />
          <span className="font-extrabold text-xl tracking-tight text-slate-800">polio</span>
        </div>
        <button 
          onClick={() => setIsSidebarOpen(!isSidebarOpen)}
          className="p-2 rounded-xl hover:bg-slate-50 text-slate-500 transition-colors"
        >
          {isSidebarOpen ? <X size={24} /> : <Menu size={24} />}
        </button>
      </div>

      {/* Sidebar (LNB) */}
      <aside 
        className={cn(
          "flex flex-col bg-white border-r border-slate-100 transition-all duration-300 z-20 absolute md:relative h-full shadow-sm pt-[73px] md:pt-0",
          isSidebarOpen ? "w-64 translate-x-0" : "w-20 -translate-x-full md:translate-x-0"
        )}
      >
        <div className="hidden md:flex h-20 items-center justify-between px-6 border-b border-slate-100">
          {isSidebarOpen && (
            <div className="flex items-center gap-3">
              <img src={poliDuoMascot} alt="Polio mascot" className="w-10 h-10 rounded-xl object-cover border border-blue-100 bg-white p-0.5 shadow-md shadow-blue-500/10" />
              <span className="font-extrabold text-2xl tracking-tight text-slate-800">polio</span>
            </div>
          )}
          <button 
            onClick={() => setIsSidebarOpen(!isSidebarOpen)}
            className="p-2 rounded-xl hover:bg-slate-50 text-slate-400 hover:text-slate-600 transition-colors mx-auto"
          >
            {isSidebarOpen ? <X size={20} /> : <Menu size={20} />}
          </button>
        </div>

        <nav className="flex-1 overflow-y-auto py-6 px-4 space-y-2 hide-scrollbar">
          {navItems.map((item) => (
            <NavLink
              key={item.path}
              to={item.path}
              onClick={() => {
                if (window.innerWidth < 768) setIsSidebarOpen(false);
              }}
              className={({ isActive }) => cn(
                "flex items-center gap-3 px-4 py-3.5 rounded-2xl transition-all duration-200 group",
                isActive 
                  ? "bg-blue-50 text-blue-600 font-extrabold shadow-sm border border-blue-100" 
                  : "text-slate-500 hover:bg-slate-50 hover:text-slate-800 font-bold"
              )}
            >
              <item.icon size={22} className={cn(
                "flex-shrink-0 transition-colors",
                "group-hover:scale-110 duration-300"
              )} />
              
              {isSidebarOpen && (
                <div className="flex flex-col">
                  <span className="text-[15px]">{item.name}</span>
                  <span className="text-[11px] text-slate-400 font-medium group-hover:text-slate-500 transition-colors">
                    {item.sub}
                  </span>
                </div>
              )}
            </NavLink>
          ))}
        </nav>

        {/* User Mini Profile in Sidebar */}
        <div className="p-4 border-t border-slate-100 bg-slate-50/50">
          <div className={cn(
            "flex items-center gap-3 p-2 rounded-2xl hover:bg-white transition-colors cursor-pointer border border-transparent hover:border-slate-200 hover:shadow-sm",
            !isSidebarOpen && "justify-center"
          )}>
            <img 
              src={user?.photoURL || poliDuoMascot} 
              alt="Profile" 
              className="w-10 h-10 rounded-full border-2 border-white shadow-sm object-cover"
            />
            {isSidebarOpen && (
              <div className="flex-1 min-w-0">
                <p className="text-sm font-extrabold text-slate-800 truncate">
                  {user?.displayName || (isGuestSession ? '게스트' : '사용자')}
                </p>
                <button onClick={logout} className="text-xs text-slate-500 hover:text-red-500 flex items-center gap-1 mt-0.5 transition-colors font-medium">
                  <LogOut size={12} /> 로그아웃
                </button>
              </div>
            )}
          </div>
        </div>
      </aside>

      {/* Overlay for mobile sidebar */}
      {isSidebarOpen && (
        <div 
          className="fixed inset-0 bg-slate-900/20 backdrop-blur-sm z-10 md:hidden"
          onClick={() => setIsSidebarOpen(false)}
        />
      )}

      {/* Main Content */}
      <main className="flex-1 flex flex-col min-w-0 overflow-hidden relative">
        {/* Topbar (GNB) - Hidden on mobile as we have mobile header */}
        <header className="hidden md:flex h-20 bg-white/80 backdrop-blur-md border-b border-slate-100 items-center justify-end px-8 z-10 sticky top-0">
          <div className="flex items-center gap-4">
             <div className="px-4 py-2 bg-blue-50 text-blue-600 rounded-xl text-sm font-extrabold flex items-center gap-2 shadow-sm border border-blue-100">
               <span className="w-2.5 h-2.5 rounded-full bg-blue-500 animate-pulse shadow-[0_0_8px_rgba(59,130,246,0.6)]"></span>
               Poli Online
             </div>
          </div>
        </header>

        {/* Page Content */}
        <div className="flex-1 overflow-auto p-4 sm:p-6 md:p-8 pb-24 md:pb-8 relative flex flex-col">
          <div className="flex-1">
            <Outlet />
          </div>
          
          {/* Footer */}
          <footer className="mt-16 py-8 border-t border-slate-200 bg-white rounded-3xl px-8 shadow-sm">
            <div className="flex flex-col md:flex-row items-center justify-between gap-6 text-sm text-slate-500 font-medium">
              <div className="flex flex-wrap justify-center md:justify-start gap-x-4 gap-y-2">
                <span className="font-bold text-slate-700">상호명: polio (폴리오)</span>
                <span className="hidden md:inline text-slate-300">|</span>
                <span>대표: 임현수</span>
                <span className="hidden md:inline text-slate-300">|</span>
                <span>전화번호: 010-7614-2633</span>
                <span className="hidden md:inline text-slate-300">|</span>
                <span>문의: mongben@naver.com</span>
              </div>
              <div className="text-xs text-slate-400 font-semibold">
                © 2026 polio. All rights reserved.
              </div>
            </div>
          </footer>
        </div>
      </main>
    </div>
  );
}
