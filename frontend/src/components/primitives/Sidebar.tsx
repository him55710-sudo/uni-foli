import React from 'react';
import { cn } from '../../lib/cn';

interface SidebarProps {
  open?: boolean;
  className?: string;
  children: React.ReactNode;
}

export function Sidebar({ open, className, children }: SidebarProps) {
  return (
    <aside
      className={cn(
        'fixed inset-y-0 left-0 z-40 border-r border-white/70 bg-[linear-gradient(180deg,rgba(255,255,255,0.96)_0%,rgba(250,247,255,0.95)_44%,rgba(239,251,252,0.93)_100%)] shadow-[0_22px_48px_rgba(42,64,132,0.12)] backdrop-blur-2xl transition-all duration-300 ease-in-out md:relative md:z-10',
        open
          ? 'w-[292px] translate-x-0'
          : 'w-[0px] -translate-x-full md:w-20 md:translate-x-0',
        className,
      )}
    >
      <div className={cn(
        'h-full overflow-hidden transition-opacity duration-200',
        !open && "md:opacity-100 opacity-0"
      )}>
        {children}
      </div>
    </aside>
  );
}
