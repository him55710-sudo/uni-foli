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
  const isFixedLayout = contentClassName?.includes('overflow-hidden');

  return (
    <div
      className={cn(
        'flex min-h-screen min-h-[100dvh] flex-col bg-[#f2f4f6]',
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
              'flex-1 bg-transparent',
              !isFixedLayout && 'overflow-x-hidden overflow-y-auto px-3 py-4 pb-[calc(5rem+env(safe-area-inset-bottom))] sm:px-6 sm:py-6 sm:pb-24 md:px-8 md:py-8',
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
