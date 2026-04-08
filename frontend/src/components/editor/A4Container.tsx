import React from 'react';
import { cn } from '../../lib/cn';

interface A4ContainerProps extends React.HTMLAttributes<HTMLDivElement> {
  children: React.ReactNode;
  pageNumber?: number;
}

export function A4Container({ children, className, pageNumber = 1, ...props }: A4ContainerProps) {
  return (
    <div className={cn('flex w-full flex-col items-center bg-slate-100 px-2 py-3 sm:py-8', className)} {...props}>
      <div className="a4-page relative w-full max-w-[210mm] bg-white transition-shadow duration-300">
        {children}

        <div className="absolute bottom-0 right-0 left-0 flex items-center justify-between px-4 pb-3 sm:px-[20mm] sm:pb-[10mm]" style={{ pointerEvents: 'none' }}>
          <span className="text-[10px] font-medium text-slate-300">Uni Foli Document</span>
          <span className="text-[10px] font-medium text-slate-300">{pageNumber}</span>
        </div>
      </div>
    </div>
  );
}
