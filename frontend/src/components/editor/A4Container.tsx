import React from 'react';
import { cn } from '../../lib/cn';

interface A4ContainerProps extends React.HTMLAttributes<HTMLDivElement> {
  children: React.ReactNode;
  pageNumber?: number;
  scale?: number;
}

export function A4Container({ children, className, pageNumber = 1, scale = 1, ...props }: A4ContainerProps) {
  return (
    <div 
      className={cn('flex w-full flex-col items-center bg-slate-100 py-3 sm:py-8 overflow-auto', className)} 
      {...props}
    >
      <div 
        className="a4-page relative bg-white transition-all duration-300 origin-top"
        style={{ 
          width: '210mm',
          minHeight: '297mm',
          transform: `scale(${scale})`,
          marginBottom: `calc(297mm * (${scale} - 1))`, // Offset the scale gap
        }}
      >
        {children}

        <div className="absolute bottom-0 right-0 left-0 flex items-center justify-between px-[20mm] pb-[10mm]" style={{ pointerEvents: 'none' }}>
          <span className="text-[10px] font-medium text-slate-300 uppercase tracking-widest">UniFoli Document</span>
          <span className="text-[10px] font-medium text-slate-300">{pageNumber}</span>
        </div>
      </div>
    </div>
  );
}
