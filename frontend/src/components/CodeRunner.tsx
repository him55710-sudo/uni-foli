import React, { useState } from 'react';
import { motion, AnimatePresence } from 'motion/react';
import { Play, Loader2, SquareTerminal } from 'lucide-react';
import { usePyodide } from '../hooks/usePyodide';

interface CodeRunnerProps {
  code: string;
}

export function CodeRunner({ code }: CodeRunnerProps) {
  const { isLoading: isPyodideLoading, error: pyodideError, runPythonCode } = usePyodide();
  const [isRunning, setIsRunning] = useState(false);
  const [output, setOutput] = useState<string | null>(null);

  // Gemini may embed python inside markdown ```python ... ``` within [PYTHON]
  const cleanCode = code
    .replace(/^```python\n?/g, '')
    .replace(/^```\n?/g, '')
    .replace(/```\n?$/g, '')
    .trim();

  const handleRun = async () => {
    if (isPyodideLoading || isRunning) return;
    setIsRunning(true);
    setOutput(null);

    try {
      const result = await runPythonCode(cleanCode);
      setOutput(result);
    } catch (err: any) {
      setOutput(err.message || String(err));
    } finally {
      setIsRunning(false);
    }
  };

  return (
    <div className="my-5 overflow-hidden rounded-2xl border border-slate-700 bg-[#0F172A] shadow-xl clay-card">
      <div className="flex items-center justify-between border-b border-slate-700/60 bg-slate-800/80 px-4 py-3 backdrop-blur-sm">
        <div className="flex items-center text-[13px] font-bold text-slate-300">
          <SquareTerminal size={16} className="mr-2 text-[#3B82F6]" />
          Python Sandbox
          {isPyodideLoading && (
            <span className="ml-3 flex items-center gap-1.5 rounded-md bg-amber-500/10 px-2 py-1 text-[11px] text-amber-300 shadow-sm border border-amber-500/20">
              <Loader2 size={12} className="animate-spin" />
              엔진 구동 중...
            </span>
          )}
          {pyodideError && (
            <span className="ml-3 rounded-md bg-red-500/10 px-2 py-1 text-[11px] text-red-400 border border-red-500/20 shadow-sm">
              엔진 초기화 실패
            </span>
          )}
        </div>
        <button
          onClick={handleRun}
          disabled={isPyodideLoading || isRunning}
          className="flex items-center gap-1.5 rounded-lg bg-[#34D399] px-3.5 py-1.5 text-[13px] font-extrabold text-slate-900 transition-all hover:bg-emerald-300 active:scale-95 disabled:cursor-not-allowed disabled:opacity-50 shadow-[inset_0_-2px_4px_rgba(0,0,0,0.1),0_2px_4px_rgba(52,211,153,0.3)]"
        >
          {isRunning ? (
            <Loader2 size={14} className="animate-spin text-slate-800" />
          ) : (
            <Play size={14} fill="currentColor" />
          )}
          실행하기
        </button>
      </div>

      <div className="px-4 py-5 overflow-x-auto whitespace-pre font-mono text-[13px] leading-relaxed text-slate-300 hide-scrollbar">
        <code>{cleanCode}</code>
      </div>

      <AnimatePresence>
        {output !== null && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            exit={{ opacity: 0, height: 0 }}
            className="border-t border-slate-700/80 bg-[#0B0F19] px-4 py-4"
          >
            <p className="mb-2 text-[11px] font-extrabold uppercase tracking-widest text-[#64748B] flex items-center gap-1.5">
              <span className="h-1.5 w-1.5 rounded-full bg-emerald-400"></span>
              Output Result
            </p>
            <pre className="font-mono text-[13px] text-emerald-400 leading-relaxed whitespace-pre-wrap break-words">
              {output}
            </pre>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
