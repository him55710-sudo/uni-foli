import React from 'react';
import { cn } from '../../lib/cn';

interface AppShellProps {
  topbar?: React.ReactNode;
  sidebar?: React.ReactNode;
  children: React.ReactNode;
  footer?: React.ReactNode;
  overlay?: React.ReactNode;
  className?: string;
  contentClassName?: string;
}

export function AppShell({ topbar, sidebar, children, footer, overlay, className, contentClassName }: AppShellProps) {
  return (
    <div className={cn('flex min-h-screen min-h-[100dvh] flex-col bg-[radial-gradient(circle_at_top_right,_rgba(59,130,246,0.08),_transparent_32%),#f4f7fb]', className)}>
      {topbar ?? null}
      <div className="relative flex min-h-0 flex-1">
        {sidebar ?? null}
        {overlay ?? null}
        <main className="relative z-10 flex min-w-0 flex-1 flex-col overflow-hidden">
          <div
            className={cn(
              'flex-1 overflow-x-hidden overflow-y-auto p-3 pb-[calc(5rem+env(safe-area-inset-bottom))] sm:p-6 sm:pb-24 md:p-8',
              contentClassName,
            )}
          >
            {children}
            {footer ?? null}
          </div>
        </main>
      </div>
    </div>
  );
}
