import React from 'react';
import { motion, AnimatePresence } from 'motion/react';
import { X, Check, FileText, AlertTriangle } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import remarkMath from 'remark-math';
import rehypeKatex from 'rehype-katex';

interface SuggestionReviewModalProps {
  isOpen: boolean;
  content: string | null;
  onApply: () => void;
  onCancel: () => void;
}

export function SuggestionReviewModal({ isOpen, content, onApply, onCancel }: SuggestionReviewModalProps) {
  if (!isOpen || !content) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 p-4 backdrop-blur-sm">
      <motion.div
        initial={{ opacity: 0, scale: 0.95, y: 20 }}
        animate={{ opacity: 1, scale: 1, y: 0 }}
        exit={{ opacity: 0, scale: 0.95, y: 20 }}
        className="relative flex max-h-[90vh] w-full max-w-2xl flex-col overflow-hidden rounded-[2rem] bg-white shadow-2xl"
      >
        <div className="flex items-center justify-between border-b border-slate-100 bg-slate-50/50 p-6">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-blue-100 text-blue-600 shadow-sm">
              <FileText size={20} />
            </div>
            <div>
              <h3 className="text-lg font-black text-slate-800">AI 제안 내용 반영 대기</h3>
              <p className="text-xs font-bold text-slate-500">본문에 들어가기 전 내용을 마지막으로 검토하세요.</p>
            </div>
          </div>
          <button
            onClick={onCancel}
            className="rounded-full bg-slate-100 p-2 text-slate-400 transition-colors hover:bg-slate-200 hover:text-slate-600"
          >
            <X size={20} />
          </button>
        </div>

        <div className="flex-1 overflow-y-auto p-6 sm:p-8 bg-white hide-scrollbar">
          <div className="mb-6 rounded-xl border border-amber-200 bg-amber-50 p-4 shadow-sm">
            <div className="flex items-start gap-3">
              <AlertTriangle size={18} className="mt-0.5 shrink-0 text-amber-600" />
              <p className="text-sm font-semibold leading-relaxed text-amber-800">
                반영 시, 해당 문단 위에 <span className="rounded bg-amber-200/50 px-1 font-black">### [AI Draft Suggestion]</span> 마커가 영구적으로 부착됩니다. 본인이 직접 편집하고 팩트를 검증한 후에만 유지하세요.
              </p>
            </div>
          </div>

          <div className="prose prose-sm prose-slate max-w-none prose-headings:font-black rounded-2xl border border-slate-200 bg-slate-50 p-6 shadow-inner">
            <ReactMarkdown remarkPlugins={[remarkMath]} rehypePlugins={[rehypeKatex]}>
              {content}
            </ReactMarkdown>
          </div>
        </div>

        <div className="border-t border-slate-100 bg-slate-50 p-6 flex gap-3">
          <button
            onClick={onCancel}
            className="flex-1 rounded-2xl bg-white px-6 py-4 text-sm font-bold text-slate-600 border border-slate-200 transition-colors hover:bg-slate-50"
          >
            취소
          </button>
          <button
            onClick={onApply}
            className="flex-[2] flex items-center justify-center gap-2 rounded-2xl px-6 py-4 text-sm font-black text-white clay-btn-primary"
          >
            <Check size={18} className="text-yellow-300" />
            문서 끝에 안전하게 추가
          </button>
        </div>
      </motion.div>
    </div>
  );
}
