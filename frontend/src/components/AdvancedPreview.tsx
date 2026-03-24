import React, { useState } from 'react';
import { AnimatePresence, motion } from 'motion/react';
import { BarChart3, FlaskConical, ChevronDown, ChevronUp, Sigma } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import remarkMath from 'remark-math';
import rehypeKatex from 'rehype-katex';
import { ChartComponent } from './ChartComponent';

interface ChartSpec {
  title: string;
  type: 'bar' | 'line';
  data: { name: string; value: number }[];
}

interface VisualSpec {
  type: string;
  chart_spec?: ChartSpec;
}

interface MathExpression {
  label: string;
  latex: string;
  context?: string;
}

interface AdvancedPreviewProps {
  visualSpecs: VisualSpec[];
  mathExpressions: MathExpression[];
  isAdvancedMode: boolean;
}

export function AdvancedPreview({
  visualSpecs,
  mathExpressions,
  isAdvancedMode,
}: AdvancedPreviewProps) {
  const [isExpanded, setIsExpanded] = useState(true);

  if (!isAdvancedMode) return null;

  const hasCharts = visualSpecs.some((spec) => spec.type === 'chart' && spec.chart_spec);
  const hasMath = mathExpressions.length > 0;

  if (!hasCharts && !hasMath) return null;

  return (
    <motion.div
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5, type: 'spring', bounce: 0.2 }}
      className="mx-auto mt-6 max-w-[210mm]"
    >
      <div className="overflow-hidden rounded-3xl border border-indigo-500/30 bg-gradient-to-br from-slate-900 via-indigo-950/60 to-slate-900 shadow-xl shadow-indigo-500/5">
        {/* Header */}
        <button
          type="button"
          onClick={() => setIsExpanded((prev) => !prev)}
          className="flex w-full items-center justify-between px-6 py-4 transition-colors hover:bg-white/5"
        >
          <div className="flex items-center gap-3">
            <div className="flex h-8 w-8 items-center justify-center rounded-xl bg-indigo-500/20 text-indigo-300">
              <FlaskConical size={16} />
            </div>
            <div className="text-left">
              <p className="text-[11px] font-black uppercase tracking-[0.2em] text-indigo-400">
                심화 분석 미리보기
              </p>
              <p className="mt-0.5 text-xs font-medium text-slate-400">
                {hasCharts ? '차트' : ''}{hasCharts && hasMath ? ' · ' : ''}
                {hasMath ? '수식' : ''} 자동 생성
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2 text-slate-400">
            <span className="rounded-full bg-indigo-500/10 px-2 py-0.5 text-[10px] font-extrabold text-indigo-300">
              {visualSpecs.length + mathExpressions.length}개 항목
            </span>
            {isExpanded ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
          </div>
        </button>

        {/* Body */}
        <AnimatePresence>
          {isExpanded && (
            <motion.div
              initial={{ height: 0, opacity: 0 }}
              animate={{ height: 'auto', opacity: 1 }}
              exit={{ height: 0, opacity: 0 }}
              transition={{ duration: 0.3 }}
              className="overflow-hidden"
            >
              <div className="space-y-4 px-6 pb-6">
                {/* Charts */}
                {hasCharts && (
                  <div>
                    <div className="mb-3 flex items-center gap-2 text-[10px] font-black uppercase tracking-[0.18em] text-slate-500">
                      <BarChart3 size={12} />
                      데이터 시각화
                    </div>
                    <div className="space-y-3">
                      {visualSpecs
                        .filter((spec) => spec.type === 'chart' && spec.chart_spec)
                        .map((spec, idx) => (
                          <div
                            key={idx}
                            className="overflow-hidden rounded-2xl border border-slate-700/50 bg-slate-800/60"
                          >
                            <ChartComponent
                              jsonString={JSON.stringify(spec.chart_spec)}
                            />
                          </div>
                        ))}
                    </div>
                  </div>
                )}

                {/* Math Expressions */}
                {hasMath && (
                  <div>
                    <div className="mb-3 flex items-center gap-2 text-[10px] font-black uppercase tracking-[0.18em] text-slate-500">
                      <Sigma size={12} />
                      수식 미리보기
                    </div>
                    <div className="space-y-2">
                      {mathExpressions.map((expr, idx) => (
                        <MathCard key={idx} expression={expr} />
                      ))}
                    </div>
                  </div>
                )}
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </motion.div>
  );
}

function MathCard({ expression }: { expression: MathExpression }) {
  const [showContext, setShowContext] = useState(false);

  return (
    <motion.div
      initial={{ opacity: 0, x: -8 }}
      animate={{ opacity: 1, x: 0 }}
      className="rounded-2xl border border-slate-700/50 bg-slate-800/60 p-4"
    >
      <p className="mb-2 text-sm font-extrabold text-slate-200">{expression.label}</p>
      <div className="rounded-xl bg-slate-900/80 px-4 py-3 font-mono text-sm text-slate-100">
        <ReactMarkdown remarkPlugins={[remarkMath]} rehypePlugins={[rehypeKatex]}>
          {`$$${expression.latex}$$`}
        </ReactMarkdown>
      </div>
      {expression.context && (
        <>
          <button
            type="button"
            onClick={() => setShowContext((prev) => !prev)}
            className="mt-2 text-xs font-bold text-indigo-400 hover:text-indigo-300"
          >
            {showContext ? '맥락 숨기기' : '사용 맥락 보기'}
          </button>
          <AnimatePresence>
            {showContext && (
              <motion.p
                initial={{ height: 0, opacity: 0 }}
                animate={{ height: 'auto', opacity: 1 }}
                exit={{ height: 0, opacity: 0 }}
                className="mt-2 text-xs font-medium leading-relaxed text-slate-400"
              >
                {expression.context}
              </motion.p>
            )}
          </AnimatePresence>
        </>
      )}
    </motion.div>
  );
}
