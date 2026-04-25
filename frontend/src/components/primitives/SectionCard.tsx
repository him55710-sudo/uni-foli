import React from 'react';
import { ChevronDown, ChevronUp } from 'lucide-react';
import { Card } from '../ui';
import { cn } from '../../lib/cn';

interface SectionCardProps extends React.HTMLAttributes<HTMLElement> {
  title?: string;
  description?: string;
  subtitle?: string; // Alias for description
  eyebrow?: string;
  badge?: string; // New prop
  actions?: React.ReactNode;
  bodyClassName?: string;
  collapsible?: boolean;
  collapsed?: boolean;
  defaultCollapsed?: boolean;
  onCollapsedChange?: (collapsed: boolean) => void;
}

export function SectionCard({
  title,
  description,
  subtitle,
  eyebrow,
  badge,
  actions,
  className,
  bodyClassName,
  collapsible = false,
  collapsed,
  defaultCollapsed = false,
  onCollapsedChange,
  children,
  ...props
}: SectionCardProps) {
  const isControlled = typeof collapsed === 'boolean';
  const [internalCollapsed, setInternalCollapsed] = React.useState(defaultCollapsed);
  const isCollapsed = isControlled ? Boolean(collapsed) : internalCollapsed;

  const setCollapsedState = (nextValue: boolean) => {
    if (!isControlled) {
      setInternalCollapsed(nextValue);
    }
    onCollapsedChange?.(nextValue);
  };

  const handleToggleCollapsed = () => {
    if (!collapsible) return;
    setCollapsedState(!isCollapsed);
  };

  const headerActions = (
    <>
      {actions}
      {collapsible ? (
        <button
          type="button"
          aria-label={isCollapsed ? '섹션 펼치기' : '섹션 접기'}
          aria-expanded={!isCollapsed}
          onClick={handleToggleCollapsed}
          className="inline-flex h-10 w-10 items-center justify-center rounded-xl bg-slate-100 text-slate-500 transition-colors hover:bg-slate-200"
        >
          {isCollapsed ? <ChevronDown size={18} /> : <ChevronUp size={18} />}
        </button>
      ) : null}
    </>
  );

  return (
    <Card className={cn('flex flex-col border-none bg-white p-6 sm:p-10 shadow-sm rounded-[2rem]', className)} {...props}>
      {(title || description || eyebrow || actions || collapsible) ? (
        <header className="mb-8 flex shrink-0 flex-col gap-4 sm:flex-row sm:items-start sm:justify-between sm:gap-5">
          <div className="min-w-0 flex-1">
            <div className="flex flex-wrap items-center gap-2">
              {eyebrow ? <p className="text-xs font-bold uppercase tracking-wider text-indigo-500">{eyebrow}</p> : null}
              {badge ? (
                <span className="inline-flex items-center rounded-lg bg-indigo-50 px-2.5 py-1 text-[11px] font-bold text-indigo-600">
                  {badge}
                </span>
              ) : null}
            </div>
            {title ? <h2 className="mt-2 text-2xl font-black tracking-tight text-slate-900 sm:text-3xl">{title}</h2> : null}
            {(description || subtitle) ? (
              <p className="mt-3 max-w-3xl text-sm font-medium leading-relaxed text-slate-500 sm:text-base">
                {description || subtitle}
              </p>
            ) : null}
          </div>
          {actions || collapsible ? (
            <div className="flex w-full flex-wrap items-center gap-2 sm:w-auto sm:shrink-0 sm:justify-end">{headerActions}</div>
          ) : null}
        </header>
      ) : null}
      {!isCollapsed ? <div className={cn('min-h-0 flex-1', bodyClassName)}>{children}</div> : null}
    </Card>
  );
}
