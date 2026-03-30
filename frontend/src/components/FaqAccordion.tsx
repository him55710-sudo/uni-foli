import React, { useState } from 'react';
import { ChevronDown } from 'lucide-react';
import { motion, AnimatePresence } from 'motion/react';
import { twMerge } from 'tailwind-merge';
import type { FaqItem } from '../content/faq';

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
          <div
            key={item.id}
            className={twMerge(
              'overflow-hidden rounded-[28px] border border-slate-200 bg-white shadow-sm',
              compact ? 'rounded-3xl' : 'rounded-[32px]',
            )}
          >
            <button
              type="button"
              className={twMerge(
                'flex w-full items-start justify-between gap-4 px-5 py-5 text-left transition-colors hover:bg-slate-50 sm:px-6',
                compact ? 'py-4' : 'py-5',
              )}
              aria-expanded={isOpen}
              aria-controls={answerId}
              onClick={() => setOpenId(isOpen ? null : item.id)}
            >
              <div className="min-w-0">
                <p className="mb-2 inline-flex rounded-full border border-blue-100 bg-blue-50 px-2.5 py-1 text-[11px] font-black text-blue-600">
                  {item.category}
                </p>
                <h3 className={twMerge('font-extrabold text-slate-800', compact ? 'text-base' : 'text-lg')}>
                  {item.question}
                </h3>
              </div>
              <span
                className={twMerge(
                  'mt-1 flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-2xl border border-slate-200 bg-slate-50 text-slate-500 transition-transform',
                  isOpen ? 'rotate-180' : '',
                )}
              >
                <ChevronDown size={18} />
              </span>
            </button>

            <AnimatePresence initial={false}>
              {isOpen ? (
                <motion.div
                  id={answerId}
                  initial={{ height: 0, opacity: 0 }}
                  animate={{ height: 'auto', opacity: 1 }}
                  exit={{ height: 0, opacity: 0 }}
                  transition={{ duration: 0.2 }}
                >
                  <div className="border-t border-slate-100 px-5 pb-5 pt-4 sm:px-6">
                    <p className="text-sm font-medium leading-7 text-slate-600">{item.answer}</p>
                  </div>
                </motion.div>
              ) : null}
            </AnimatePresence>
          </div>
        );
      })}
    </div>
  );
}
