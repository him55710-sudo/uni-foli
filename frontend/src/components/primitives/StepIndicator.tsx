import React from 'react';
import { CheckCircle2, Circle } from 'lucide-react';
import { cn } from '../../lib/cn';

export type StepState = 'done' | 'active' | 'pending' | 'error';

export interface StepIndicatorItem {
  id: string;
  label: string;
  description?: string;
  state: StepState;
}

interface StepIndicatorProps {
  items: StepIndicatorItem[];
  className?: string;
}

function stateClass(state: StepState) {
  if (state === 'done') return 'border-emerald-200 bg-emerald-50 text-emerald-700';
  if (state === 'active') return 'border-blue-200 bg-blue-50 text-blue-700';
  if (state === 'error') return 'border-red-200 bg-red-50 text-red-700';
  return 'border-slate-200 bg-slate-50 text-slate-500';
}

export function StepIndicator({ items, className }: StepIndicatorProps) {
  return (
    <ol className={cn('grid gap-3 md:grid-cols-2 xl:grid-cols-4', className)}>
      {items.map(item => (
        <li key={item.id} className={cn('rounded-2xl border px-4 py-3.5 sm:px-5', stateClass(item.state))}>
          <div className="flex items-center gap-2">
            {item.state === 'done' ? <CheckCircle2 size={15} /> : <Circle size={14} />}
            <p className="text-sm font-black sm:text-base">{item.label}</p>
          </div>
          {item.description ? <p className="mt-1 text-sm font-medium leading-6">{item.description}</p> : null}
        </li>
      ))}
    </ol>
  );
}
