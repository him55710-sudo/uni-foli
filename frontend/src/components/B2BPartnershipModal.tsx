import React, { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { X, Building2, Mail, Phone, MessageSquare, CheckCircle2 } from 'lucide-react';
import toast from 'react-hot-toast';

interface B2BPartnershipModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export function B2BPartnershipModal({ isOpen, onClose }: B2BPartnershipModalProps) {
  const [submitted, setSubmitted] = useState(false);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    // Simulate API call
    setTimeout(() => {
      setSubmitted(true);
      toast.success('문의가 접수되었습니다. 담당자가 곧 연락드리겠습니다.');
    }, 800);
  };

  return (
    <AnimatePresence>
      {isOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={onClose}
            className="absolute inset-0 bg-slate-900/40 backdrop-blur-sm"
          />
          <motion.div
            initial={{ opacity: 0, scale: 0.95, y: 20 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.95, y: 20 }}
            className="relative w-full max-w-lg overflow-hidden rounded-[2.5rem] bg-white shadow-2xl"
          >
            <div className="p-8 md:p-12">
              <button
                onClick={onClose}
                className="absolute right-6 top-6 rounded-full p-2 text-slate-400 hover:bg-slate-50 hover:text-slate-600 transition-colors"
              >
                <X size={20} />
              </button>

              {!submitted ? (
                <>
                  <div className="mb-8">
                    <div className="mb-4 inline-flex h-12 w-12 items-center justify-center rounded-2xl bg-blue-50 text-blue-600 shadow-sm border border-blue-100">
                      <Building2 size={24} />
                    </div>
                    <h2 className="text-2xl font-black text-slate-800 tracking-tight">학교/학원 도입 문의</h2>
                    <p className="mt-2 text-slate-500 font-medium">Uni Folia의 기관용 솔루션과 협력 모델을 안내해 드립니다.</p>
                  </div>

                  <form onSubmit={handleSubmit} className="space-y-4">
                    <div>
                      <label className="mb-1.5 block text-xs font-black text-slate-700 uppercase tracking-widest">기관명 / 직함</label>
                      <input
                        required
                        type="text"
                        placeholder="예: 서울고등학교 진학상담실"
                        className="w-full rounded-2xl border border-slate-200 bg-slate-50/50 px-4 py-3.5 text-sm font-medium focus:border-blue-500 focus:bg-white focus:outline-none transition-all"
                      />
                    </div>
                    <div>
                      <label className="mb-1.5 block text-xs font-black text-slate-700 uppercase tracking-widest">담당자 연락처</label>
                      <input
                        required
                        type="tel"
                        placeholder="010-0000-0000"
                        className="w-full rounded-2xl border border-slate-200 bg-slate-50/50 px-4 py-3.5 text-sm font-medium focus:border-blue-500 focus:bg-white focus:outline-none transition-all"
                      />
                    </div>
                    <div>
                      <label className="mb-1.5 block text-xs font-black text-slate-700 uppercase tracking-widest">문의 내용</label>
                      <textarea
                        required
                        rows={3}
                        placeholder="기관용 AI 라이선스 및 협력 방안에 대해 궁금한 점을 적어주세요."
                        className="w-full rounded-2xl border border-slate-200 bg-slate-50/50 px-4 py-3.5 text-sm font-medium focus:border-blue-500 focus:bg-white focus:outline-none transition-all"
                      ></textarea>
                    </div>

                    <button
                      type="submit"
                      className="mt-4 flex w-full items-center justify-center gap-2 rounded-2xl bg-blue-600 py-4 text-sm font-black text-white shadow-lg shadow-blue-500/20 hover:bg-blue-700 transition-all hover:scale-[1.02] active:scale-[0.98]"
                    >
                      <MessageSquare size={18} /> 도입 상담 신청하기
                    </button>
                    <p className="text-center text-[11px] text-slate-400 font-medium">
                      신청 후 24시간 이내에 전문 상담원이 연락을 드립니다.
                    </p>
                  </form>
                </>
              ) : (
                <div className="flex flex-col items-center justify-center py-12 text-center">
                  <div className="mb-6 flex h-16 w-16 items-center justify-center rounded-full bg-emerald-50 text-emerald-500 shadow-sm border border-emerald-100">
                    <CheckCircle2 size={32} />
                  </div>
                  <h3 className="text-2xl font-black text-slate-800 tracking-tight">상담 신청 완료!</h3>
                  <p className="mt-2 text-slate-500 font-medium max-w-[280px]">
                    도입 문의가 성공적으로 전달되었습니다. 곧 담당자와 연결해 드리겠습니다.
                  </p>
                  <button
                    onClick={onClose}
                    className="mt-8 rounded-2xl bg-slate-100 px-8 py-3 text-sm font-black text-slate-600 hover:bg-slate-200 transition-colors"
                  >
                    닫기
                  </button>
                </div>
              )}
            </div>
          </motion.div>
        </div>
      )}
    </AnimatePresence>
  );
}
