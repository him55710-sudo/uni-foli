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

const sizeStyles: Record<
  LogoSize,
  {
    root: string;
    wordmark: string;
    mark: string;
    subtitle: string;
    panelPadding: string;
  }
> = {
  sm: {
    root: 'gap-1.5',
    wordmark: 'h-7',
    mark: 'h-7 w-7',
    subtitle: 'text-[10px]',
    panelPadding: 'px-2.5 py-1.5',
  },
  md: {
    root: 'gap-2',
    wordmark: 'h-8',
    mark: 'h-8 w-8',
    subtitle: 'text-xs',
    panelPadding: 'px-3 py-2',
  },
  lg: {
    root: 'gap-2.5',
    wordmark: 'h-11',
    mark: 'h-11 w-11',
    subtitle: 'text-sm',
    panelPadding: 'px-3.5 py-2.5',
  },
};

const toneStyles: Record<LogoTone, { subtitle: string; panel: string }> = {
  light: {
    subtitle: 'text-slate-500',
    panel: '',
  },
  dark: {
    subtitle: 'text-slate-200',
    panel:
      'rounded-[1.2rem] bg-white/90 ring-1 ring-white/60 shadow-[0_14px_36px_rgba(37,99,235,0.22)] backdrop-blur-sm',
  },
};

function UniFoliMark({ className }: { className?: string }) {
  return (
    <img
      src="/logo-unifoli-mark.png"
      alt=""
      aria-hidden="true"
      draggable={false}
      decoding="async"
      className={cn('block w-auto object-contain', className)}
    />
  );
}

function UniFoliWordmark({
  size,
  titleClassName,
}: {
  size: LogoSize;
  titleClassName?: string;
}) {
  return (
    <>
      <span className="sr-only">UniFoli</span>
      <img
        src="/logo-unifoli.png"
        alt=""
        aria-hidden="true"
        draggable={false}
        decoding="async"
        className={cn('block w-auto object-contain', sizeStyles[size].wordmark, titleClassName)}
      />
    </>
  );
}

export function UniFoliLogo({
  size = 'md',
  tone = 'light',
  markOnly = false,
  subtitle = '입시 실행 워크플로',
  className,
  markClassName,
  titleClassName,
  subtitleClassName,
}: UniFoliLogoProps) {
  const panelClassName = toneStyles[tone].panel
    ? cn('inline-flex items-center justify-center', toneStyles[tone].panel, sizeStyles[size].panelPadding, markClassName)
    : cn('inline-flex items-center justify-center', markClassName);

  if (markOnly) {
    return (
      <span
        role="img"
        aria-label="UniFoli"
        className={cn('inline-flex items-center justify-center', className)}
      >
        <span className={panelClassName}>
          <UniFoliMark className={cn('rounded-xl', sizeStyles[size].mark)} />
        </span>
      </span>
    );
  }

  return (
    <div className={cn('inline-flex flex-col items-start', sizeStyles[size].root, className)}>
      <span className={panelClassName}>
        <UniFoliWordmark size={size} titleClassName={titleClassName} />
      </span>
      {subtitle ? (
        <p
          className={cn(
            'font-semibold leading-none',
            sizeStyles[size].subtitle,
            toneStyles[tone].subtitle,
            subtitleClassName,
          )}
        >
          {subtitle}
        </p>
      ) : null}
    </div>
  );
}
