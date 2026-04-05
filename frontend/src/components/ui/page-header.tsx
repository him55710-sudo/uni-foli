import React from 'react';
import { cn } from '../../lib/cn';

export interface PageHeaderProps {
  eyebrow?: string;
  title: string;
  description?: string;
  actions?: React.ReactNode;
  evidence?: React.ReactNode;
  className?: string;
}

export function PageHeader({ eyebrow, title, description, actions, evidence, className }: PageHeaderProps) {
  return (
    <header className={cn('rounded-3xl border border-slate-200 bg-white p-5 shadow-sm sm:p-8', className)}>
      <div className="flex flex-col gap-4 sm:gap-5 md:flex-row md:items-start md:justify-between">
        <div className="min-w-0">
          {eyebrow ? (
            <p className="text-xs font-black uppercase tracking-[0.18em] text-blue-600">{eyebrow}</p>
          ) : null}
          <h1 className="mt-2 break-keep text-2xl font-black tracking-tight text-slate-900 sm:text-4xl">{title}</h1>
          {description ? <p className="mt-3 max-w-3xl text-sm font-medium leading-6 text-slate-500 sm:text-base sm:leading-7">{description}</p> : null}
        </div>
        {actions ? <div className="flex flex-wrap items-center gap-2">{actions}</div> : null}
      </div>
      {evidence ? <div className="mt-5 border-t border-slate-100 pt-5">{evidence}</div> : null}
    </header>
  );
}
