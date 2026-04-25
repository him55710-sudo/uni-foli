import React from 'react';
import { cn } from '../../lib/cn';

type CardTone = 'default' | 'muted' | 'strong';
type CardPadding = 'none' | 'sm' | 'md' | 'lg';

const toneClasses: Record<CardTone, string> = {
  default: 'border-transparent bg-white shadow-md',
  muted: 'border-transparent bg-slate-50',
  strong: 'border-transparent bg-white shadow-lg',
};

const paddingClasses: Record<CardPadding, string> = {
  none: 'p-0',
  sm: 'p-4',
  md: 'p-5 sm:p-7',
  lg: 'p-6 sm:p-8',
};

export interface CardProps extends React.HTMLAttributes<HTMLDivElement> {
  tone?: CardTone;
  padding?: CardPadding;
}

export function Card({ tone = 'default', padding = 'md', className, ...props }: CardProps) {
  return (
    <section
      className={cn('rounded-[1.9rem] border shadow-[0_16px_36px_rgba(42,64,132,0.09)]', toneClasses[tone], paddingClasses[padding], className)}
      {...props}
    />
  );
}

export function CardHeader({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return <header className={cn('mb-4 flex items-start justify-between gap-4', className)} {...props} />;
}

export function CardTitle({ className, ...props }: React.HTMLAttributes<HTMLHeadingElement>) {
  return <h2 className={cn('text-xl font-extrabold tracking-tight text-slate-900', className)} {...props} />;
}

export function CardDescription({ className, ...props }: React.HTMLAttributes<HTMLParagraphElement>) {
  return <p className={cn('text-sm font-medium leading-6 text-slate-500', className)} {...props} />;
}

export function CardContent({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return <div className={cn('space-y-5', className)} {...props} />;
}

export function CardFooter({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return <footer className={cn('mt-8 flex flex-wrap items-center gap-3', className)} {...props} />;
}
