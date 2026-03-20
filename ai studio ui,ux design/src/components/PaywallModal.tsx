import React from 'react';
import { motion } from 'motion/react';
import { Lock, Check, X, Sparkles } from 'lucide-react';

interface PaywallModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export function PaywallModal({ isOpen, onClose }: PaywallModalProps) {
  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/40 backdrop-blur-sm">
      <motion.div
        initial={{ opacity: 0, scale: 0.95, y: 20 }}
        animate={{ opacity: 1, scale: 1, y: 0 }}
        exit={{ opacity: 0, scale: 0.95, y: 20 }}
        className="w-full max-w-4xl bg-white rounded-3xl overflow-hidden shadow-2xl relative flex flex-col max-h-[90vh]"
      >
        <button onClick={onClose} className="absolute top-4 right-4 z-10 p-2 text-slate-400 hover:text-slate-600 bg-slate-50 rounded-full">
          <X size={20} />
        </button>

        <div className="p-8 sm:p-12 overflow-y-auto hide-scrollbar">
          <div className="text-center mb-10">
            <div className="w-16 h-16 bg-slate-100 rounded-2xl flex items-center justify-center mx-auto mb-6 shadow-inner">
              <Lock size={32} className="text-slate-400" />
            </div>
            <h2 className="text-3xl sm:text-4xl font-extrabold text-slate-800 mb-4 break-keep">
              완벽한 조판 문서는<br/>
              <span className="text-blue-500">Pro 요금제</span>부터 다운로드할 수 있어요.
            </h2>
            <p className="text-slate-500 font-medium text-lg">폴리오 Pro와 함께 입시 준비 시간을 90% 단축하세요.</p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-6 max-w-3xl mx-auto">
            {/* Free Plan */}
            <div className="bg-slate-50 border border-slate-200 rounded-3xl p-8 flex flex-col">
              <h3 className="text-xl font-extrabold text-slate-600 mb-2">Free 플랜</h3>
              <div className="text-3xl font-extrabold text-slate-800 mb-6">₩0<span className="text-lg text-slate-400 font-medium">/월</span></div>
              <ul className="space-y-4 mb-8 flex-1">
                <li className="flex items-start gap-3 text-slate-600 font-medium">
                  <Check size={20} className="text-slate-400 shrink-0 mt-0.5" />
                  기본 AI 대화 및 아이디어 스케치
                </li>
                <li className="flex items-start gap-3 text-slate-600 font-medium">
                  <Check size={20} className="text-slate-400 shrink-0 mt-0.5" />
                  워터마크가 포함된 PDF 다운로드
                </li>
                <li className="flex items-start gap-3 text-slate-600 font-medium">
                  <Check size={20} className="text-slate-400 shrink-0 mt-0.5" />
                  월 5회 생기부 진단
                </li>
              </ul>
              <button onClick={onClose} className="w-full py-4 rounded-2xl font-bold text-slate-500 bg-slate-200 hover:bg-slate-300 transition-colors">
                현재 플랜 유지하기
              </button>
            </div>

            {/* Pro Plan */}
            <div className="clay-card border-2 border-blue-400 p-8 flex flex-col relative overflow-hidden">
              <div className="absolute top-0 right-0 bg-blue-500 text-white text-xs font-extrabold px-4 py-1.5 rounded-bl-2xl">
                가장 인기
              </div>
              <h3 className="text-xl font-extrabold text-blue-600 mb-2">Pro 플랜</h3>
              <div className="text-3xl font-extrabold text-slate-800 mb-6">₩19,000<span className="text-lg text-slate-400 font-medium">/월</span></div>
              <ul className="space-y-4 mb-8 flex-1">
                <li className="flex items-start gap-3 text-slate-800 font-bold">
                  <Check size={20} className="text-emerald-500 shrink-0 mt-0.5" />
                  HWPX 절대 조판 무제한 다운로드
                </li>
                <li className="flex items-start gap-3 text-slate-800 font-bold">
                  <Check size={20} className="text-emerald-500 shrink-0 mt-0.5" />
                  워터마크 없는 깔끔한 PDF 제공
                </li>
                <li className="flex items-start gap-3 text-slate-800 font-bold">
                  <Check size={20} className="text-emerald-500 shrink-0 mt-0.5" />
                  프리미엄 탐구보고서 템플릿 무제한
                </li>
                <li className="flex items-start gap-3 text-slate-800 font-bold">
                  <Check size={20} className="text-emerald-500 shrink-0 mt-0.5" />
                  무제한 생기부 심층 진단
                </li>
              </ul>
              <button
                onClick={() => {
                  window.location.href = 'mailto:mongben@naver.com?subject=polio%20Pro%20요금제%20문의';
                }}
                className="clay-btn-primary w-full py-4 rounded-2xl font-extrabold text-lg flex items-center justify-center gap-2 animate-pulse shadow-[0_0_20px_rgba(59,130,246,0.5)]"
              >
                <Sparkles size={20} />
                1개월 무료 체험으로 시작
              </button>
            </div>
          </div>
        </div>
      </motion.div>
    </div>
  );
}
