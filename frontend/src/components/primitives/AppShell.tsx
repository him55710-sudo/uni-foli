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
    <div
      className={cn(
        'flex min-h-screen min-h-[100dvh] flex-col bg-[radial-gradient(circle_at_10%_8%,rgba(244,114,182,0.09)_0%,transparent_32%),radial-gradient(circle_at_92%_10%,rgba(34,211,238,0.1)_0%,transparent_34%),radial-gradient(circle_at_76%_88%,rgba(132,204,22,0.08)_0%,transparent_34%),#f8fafc]',
        className,
      )}
    >
      {topbar ?? null}
      <div className="relative flex min-h-0 flex-1">
        {sidebar ?? null}
        {overlay ?? null}
        <main className="relative z-10 flex min-w-0 flex-1 flex-col overflow-hidden">
          <div
            className={cn(
              'flex-1 overflow-x-hidden overflow-y-auto bg-transparent px-3 py-4 pb-[calc(5rem+env(safe-area-inset-bottom))] sm:px-6 sm:py-6 sm:pb-24 md:px-8 md:py-8',
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
