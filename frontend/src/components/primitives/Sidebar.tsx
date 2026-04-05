import React from 'react';
import { cn } from '../../lib/cn';

interface SidebarProps extends React.HTMLAttributes<HTMLElement> {
  open: boolean;
}

export function Sidebar({ open, className, children, ...props }: SidebarProps) {
  return (
    <aside
      className={cn(
        'absolute inset-y-0 left-0 z-30 flex h-full flex-col border-r border-slate-200 bg-white shadow-xl transition-[width,transform] duration-200 md:relative md:shadow-none',
        open ? 'w-[min(85vw,20rem)] translate-x-0 md:w-80' : 'w-20 -translate-x-full md:translate-x-0',
        className,
      )}
      {...props}
    >
      {children}
    </aside>
  );
}
