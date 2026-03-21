import React, { useEffect, useState } from 'react';
import { AnimatePresence, motion } from 'motion/react';
import { ArrowRight, GraduationCap, Goal, School, Sparkles } from 'lucide-react';

interface OnboardingModalProps {
  isOpen: boolean;
  initialUniversity?: string | null;
  initialMajor?: string | null;
  isSubmitting: boolean;
  onSubmit: (payload: { targetUniversity: string; targetMajor: string }) => Promise<void>;
}

export function OnboardingModal({
  isOpen,
  initialUniversity,
  initialMajor,
  isSubmitting,
  onSubmit,
}: OnboardingModalProps) {
  const [step, setStep] = useState(1);
  const [targetUniversity, setTargetUniversity] = useState(initialUniversity ?? '');
  const [targetMajor, setTargetMajor] = useState(initialMajor ?? '');

  useEffect(() => {
    if (!isOpen) return;
    setStep(1);
    setTargetUniversity(initialUniversity ?? '');
    setTargetMajor(initialMajor ?? '');
  }, [initialMajor, initialUniversity, isOpen]);

  if (!isOpen) return null;

  const canMoveNext = targetUniversity.trim().length >= 2;
  const canSubmit = targetMajor.trim().length >= 2;

  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center bg-slate-950/45 p-0 backdrop-blur-sm sm:items-center sm:p-4">
      <motion.div
        initial={{ opacity: 0, y: 60 }}
        animate={{ opacity: 1, y: 0 }}
        exit={{ opacity: 0, y: 60 }}
        className="w-full rounded-t-3xl bg-white p-6 shadow-2xl sm:max-w-xl sm:rounded-3xl sm:p-8 clay-card"
      >
        <div className="mb-8 flex items-start justify-between gap-4">
          <div>
            <div className="mb-3 inline-flex items-center gap-2 rounded-full border border-blue-100 bg-blue-50 px-3 py-1 text-xs font-extrabold text-blue-700">
              <Sparkles size={14} />
              초기 목표 설정
            </div>
            <h2 className="text-2xl font-extrabold text-slate-800 sm:text-3xl">사정관 기준점을 먼저 맞춥니다</h2>
            <p className="mt-2 text-sm font-medium leading-relaxed text-slate-500 sm:text-base">
              목표 대학과 전공이 있어야 진단, 피드백, 세특 로드맵이 한 방향으로 정렬됩니다.
            </p>
          </div>
          <div className="flex h-14 w-14 items-center justify-center rounded-3xl bg-gradient-to-br from-blue-500 to-cyan-400 text-white shadow-lg shadow-blue-500/25">
            <GraduationCap size={26} />
          </div>
        </div>

        <div className="mb-6 grid grid-cols-2 gap-3">
          <div className={`rounded-2xl border px-4 py-3 ${step === 1 ? 'border-blue-200 bg-blue-50' : 'border-slate-200 bg-slate-50'}`}>
            <div className="mb-1 flex items-center gap-2 text-sm font-extrabold text-slate-800">
              <School size={16} />
              Step 1
            </div>
            <p className="text-xs font-medium text-slate-500">목표 대학 설정</p>
          </div>
          <div className={`rounded-2xl border px-4 py-3 ${step === 2 ? 'border-blue-200 bg-blue-50' : 'border-slate-200 bg-slate-50'}`}>
            <div className="mb-1 flex items-center gap-2 text-sm font-extrabold text-slate-800">
              <Goal size={16} />
              Step 2
            </div>
            <p className="text-xs font-medium text-slate-500">희망 전공 설정</p>
          </div>
        </div>

        <AnimatePresence mode="wait">
          {step === 1 ? (
            <motion.div
              key="target-university"
              initial={{ opacity: 0, x: 24 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: -24 }}
            >
              <label className="mb-3 block text-sm font-extrabold text-slate-700">어느 대학을 목표로 하고 있나요?</label>
              <input
                type="text"
                value={targetUniversity}
                onChange={(event) => setTargetUniversity(event.target.value)}
                onKeyDown={(event) => {
                  if (event.key === 'Enter' && canMoveNext) {
                    setStep(2);
                  }
                }}
                placeholder="예: 연세대학교, 고려대학교"
                className="w-full rounded-3xl border-2 border-slate-100 bg-slate-50 px-5 py-4 text-lg font-bold text-slate-800 shadow-sm outline-none transition-all placeholder:text-slate-300 focus:border-blue-400 focus:ring-4 focus:ring-blue-100"
                autoFocus
              />
            </motion.div>
          ) : (
            <motion.div
              key="target-major"
              initial={{ opacity: 0, x: 24 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: -24 }}
            >
              <label className="mb-3 block text-sm font-extrabold text-slate-700">어느 전공으로 평가받고 싶나요?</label>
              <input
                type="text"
                value={targetMajor}
                onChange={(event) => setTargetMajor(event.target.value)}
                onKeyDown={(event) => {
                  if (event.key === 'Enter' && canSubmit && !isSubmitting) {
                    void onSubmit({
                      targetUniversity: targetUniversity.trim(),
                      targetMajor: targetMajor.trim(),
                    });
                  }
                }}
                placeholder="예: 컴퓨터공학과, 경영학과"
                className="w-full rounded-3xl border-2 border-slate-100 bg-slate-50 px-5 py-4 text-lg font-bold text-slate-800 shadow-sm outline-none transition-all placeholder:text-slate-300 focus:border-blue-400 focus:ring-4 focus:ring-blue-100"
                autoFocus
              />
            </motion.div>
          )}
        </AnimatePresence>

        <div className="mt-8 flex gap-3">
          {step === 2 ? (
            <button
              type="button"
              onClick={() => setStep(1)}
              className="flex-1 rounded-2xl border border-slate-200 bg-white px-4 py-4 text-sm font-extrabold text-slate-600 transition-colors hover:bg-slate-50"
            >
              이전 단계
            </button>
          ) : null}
          <button
            type="button"
            disabled={step === 1 ? !canMoveNext : !canSubmit || isSubmitting}
            onClick={() => {
              if (step === 1) {
                setStep(2);
                return;
              }
              void onSubmit({
                targetUniversity: targetUniversity.trim(),
                targetMajor: targetMajor.trim(),
              });
            }}
            className="flex flex-1 items-center justify-center gap-2 rounded-2xl px-4 py-4 text-sm font-extrabold disabled:cursor-not-allowed disabled:opacity-60 clay-btn-primary"
          >
            {isSubmitting ? '저장 중...' : step === 1 ? '다음' : '내 기준점 저장하기'}
            <ArrowRight size={16} />
          </button>
        </div>
      </motion.div>
    </div>
  );
}
