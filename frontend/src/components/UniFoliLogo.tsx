import React from 'react';
import { cn } from '../lib/cn';

type LogoSize = 'sm' | 'md' | 'lg';
type LogoTone = 'light' | 'dark';

interface UniFoliLogoProps {
  size?: LogoSize;
  tone?: LogoTone;
  markOnly?: boolean;
  subtitle?: string | null;
  className?: string;
  markClassName?: string;
  titleClassName?: string;
  subtitleClassName?: string;
}

const sizeStyles: Record<LogoSize, { mark: string; title: string; subtitle: string }> = {
  sm: {
    mark: 'h-9 w-9 rounded-xl',
    title: 'text-base',
    subtitle: 'text-[10px]',
  },
  md: {
    mark: 'h-11 w-11 rounded-2xl',
    title: 'text-lg',
    subtitle: 'text-xs',
  },
  lg: {
    mark: 'h-14 w-14 rounded-[22px]',
    title: 'text-xl',
    subtitle: 'text-sm',
  },
};

const toneStyles: Record<LogoTone, { title: string; subtitle: string }> = {
  light: {
    title: 'text-slate-900',
    subtitle: 'text-slate-400',
  },
  dark: {
    title: 'text-white',
    subtitle: 'text-slate-300',
  },
};

function LogoMark({ size, className }: { size: LogoSize; className?: string }) {
  return (
    <div
      className={cn(
        'relative flex items-center justify-center overflow-hidden border border-blue-100 bg-[linear-gradient(135deg,#0f172a_0%,#1d4ed8_52%,#7dd3fc_100%)] shadow-[0_14px_28px_rgba(37,99,235,0.22)]',
        sizeStyles[size].mark,
        className,
      )}
      aria-hidden="true"
    >
      <div className="absolute inset-0 bg-[radial-gradient(circle_at_top_left,_rgba(255,255,255,0.28),_transparent_42%)]" />
      <svg viewBox="0 0 48 48" className="relative h-[72%] w-[72%] text-white" fill="none">
        <path
          d="M13 15.5c4.5-2.4 8.3-2.4 11 0V33c-2.7-2.4-6.5-2.4-11 0V15.5Z"
          stroke="currentColor"
          strokeWidth="3"
          strokeLinejoin="round"
        />
        <path
          d="M35 15.5c-4.5-2.4-8.3-2.4-11 0V33c2.7-2.4 6.5-2.4 11 0V15.5Z"
          stroke="currentColor"
          strokeWidth="3"
          strokeLinejoin="round"
        />
        <path d="M24 14v20" stroke="currentColor" strokeWidth="3" strokeLinecap="round" />
        <circle cx="35" cy="14" r="3.5" fill="currentColor" opacity="0.92" />
      </svg>
    </div>
  );
}

export function UniFoliLogo({
  size = 'md',
  tone = 'light',
  markOnly = false,
  subtitle = '기록 중심 입시 준비 워크플로',
  className,
  markClassName,
  titleClassName,
  subtitleClassName,
}: UniFoliLogoProps) {
  if (markOnly) {
    return <LogoMark size={size} className={markClassName} />;
  }

  return (
    <div className={cn('flex items-center gap-3', className)}>
      <LogoMark size={size} className={markClassName} />
      <div>
        <p className={cn('font-extrabold tracking-tight', sizeStyles[size].title, toneStyles[tone].title, titleClassName)}>
          Uni Foli
        </p>
        {subtitle ? (
          <p
            className={cn(
              'font-semibold',
              sizeStyles[size].subtitle,
              toneStyles[tone].subtitle,
              subtitleClassName,
            )}
          >
            {subtitle}
          </p>
        ) : null}
      </div>
    </div>
  );
}
