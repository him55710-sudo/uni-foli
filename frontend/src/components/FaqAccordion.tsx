import React, { useState } from 'react';
import { ChevronDown } from 'lucide-react';
import { motion, AnimatePresence } from 'motion/react';
import type { FaqItem } from '../content/faq';
import { Badge, Card } from './ui';
import { cn } from '../lib/cn';

interface FaqAccordionProps {
  items: FaqItem[];
  initialOpenId?: string | null;
  compact?: boolean;
}

export function FaqAccordion({ items, initialOpenId = null, compact = false }: FaqAccordionProps) {
  const [openId, setOpenId] = useState<string | null>(initialOpenId);

  return (
    <div className="space-y-4">
      {items.map(item => {
        const isOpen = openId === item.id;
        const answerId = `${item.id}-answer`;

        return (
          <Card key={item.id} tone="default" padding="none" className={cn('overflow-hidden', compact ? 'rounded-3xl' : 'rounded-[32px]')}>
            <button
              type="button"
              className={cn(
                'flex w-full items-start justify-between gap-4 px-5 py-5 text-left transition-colors hover:bg-slate-50 sm:px-6',
                compact ? 'py-4' : 'py-5',
              )}
              aria-expanded={isOpen}
              aria-controls={answerId}
              onClick={() => setOpenId(isOpen ? null : item.id)}
            >
              <div className="min-w-0">
                <Badge tone="info" className="mb-2">
                  {item.category}
                </Badge>
                <h3 className={cn('font-extrabold text-slate-800 break-keep', compact ? 'text-base' : 'text-lg')}>
                  {item.question}
                </h3>
              </div>
              <span
                className={cn(
                  'mt-1 flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-2xl border border-slate-200 bg-slate-50 text-slate-500 transition-transform',
                  isOpen ? 'rotate-180' : '',
                )}
              >
                <ChevronDown size={18} />
              </span>
            </button>

            <AnimatePresence mode="wait" initial={false}>
              {isOpen ? (
                <motion.div
                  id={answerId}
                  initial={{ height: 0, opacity: 0 }}
                  animate={{ height: 'auto', opacity: 1 }}
                  exit={{ height: 0, opacity: 0 }}
                  transition={{ duration: 0.25, ease: [0.04, 0.62, 0.23, 0.98] }}
                  className="overflow-hidden"
                >
                  <div className="border-t border-slate-100 px-5 pb-5 pt-4 sm:px-6">
                    <p className="text-sm font-medium leading-7 text-slate-600 break-keep">{item.answer}</p>
                  </div>
                </motion.div>
              ) : null}
            </AnimatePresence>
          </Card>
        );
      })}
    </div>
  );
}
