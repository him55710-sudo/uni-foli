import React from 'react';
import { cn } from '../../lib/cn';

interface TopbarProps extends React.HTMLAttributes<HTMLElement> {
  mobile?: boolean;
}

export function Topbar({ mobile = false, className, children, ...props }: TopbarProps) {
  return (
    <header
      className={cn(
        mobile
          ? 'sticky top-0 z-40 flex items-center justify-between border-b border-slate-200 bg-white px-4 pb-3 pt-[calc(0.75rem+env(safe-area-inset-top))] md:hidden'
          : 'sticky top-0 z-20 hidden items-center justify-between border-b border-slate-200 bg-white/95 px-6 py-4 backdrop-blur md:flex',
        className,
      )}
      {...props}
    >
      {children}
    </header>
  );
}
