import React, { useState } from 'react';
import { motion, AnimatePresence } from 'motion/react';
import { Navigate, useNavigate } from 'react-router-dom';
import { ArrowLeft, ArrowRight, ChevronRight, Loader2, Sparkles, Target, User } from 'lucide-react';
import { useOnboardingStore } from '../store/onboardingStore';
import { useAuthStore } from '../store/authStore';

export function Onboarding() {
  const navigate = useNavigate();
  const { user } = useAuthStore();
  const { step, profile, goals, isLoading, error, setStep, setProfile, setGoals, submitProfile, submitGoals } = useOnboardingStore();

  if (!user) {
    return <Navigate to="/auth" replace />;
  }

  // If already onboarded fully (checked in App.tsx), we just show success or redirect
  // But usually App.tsx will redirect out before rendering this.

  const handleNext = async () => {
    if (step === 1) {
      if (!profile.grade || !profile.track) return;
      const success = await submitProfile();
      if (success) {
        window.scrollTo(0, 0);
      }
    } else {
      if (!goals.target_university || !goals.admission_type) return;
      const success = await submitGoals();
      if (success) {
        navigate('/');
      }
    }
  };

  const handleBack = () => {
    if (step === 2) {
      setStep(1);
    }
  };

  const isStep1Valid = profile.grade && profile.track;
  const isStep2Valid = goals.target_university && goals.admission_type;
  const isNextDisabled = isLoading || (step === 1 ? !isStep1Valid : !isStep2Valid);

  return (
    <div className="flex min-h-screen flex-col items-center justify-center bg-slate-50 p-6">
      <div className="w-full max-w-2xl">
        <div className="mb-8 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <button
              onClick={handleBack}
              disabled={step === 1 || isLoading}
              className={`flex h-10 w-10 items-center justify-center rounded-xl bg-white shadow-sm transition-all ${step === 1 ? 'opacity-0' : 'hover:bg-slate-100'}`}
            >
              <ArrowLeft size={20} className="text-slate-600" />
            </button>
            <h1 className="text-2xl font-extrabold text-slate-800">
              {step === 1 ? '프로필 설정' : '목표 설정'}
            </h1>
          </div>
          <div className="flex gap-2">
            <div className={`h-2.5 w-12 rounded-full transition-all duration-300 ${step >= 1 ? 'bg-blue-600' : 'bg-slate-200'}`} />
            <div className={`h-2.5 w-12 rounded-full transition-all duration-300 ${step >= 2 ? 'bg-blue-600' : 'bg-slate-200'}`} />
          </div>
        </div>

        <motion.div
           key={step}
           initial={{ opacity: 0, x: 20 }}
           animate={{ opacity: 1, x: 0 }}
           exit={{ opacity: 0, x: -20 }}
           className="relative overflow-hidden rounded-3xl border border-slate-100 bg-white p-8 shadow-xl shadow-slate-200/50 sm:p-12 text-slate-700"
        >
          {error && (
            <div className="mb-6 rounded-xl bg-red-50 p-4 text-sm font-medium text-red-600">
              {error}
            </div>
          )}

          {step === 1 && (
            <div className="space-y-8">
              <div className="mb-8 flex items-center gap-4">
                <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-blue-50 text-blue-600">
                  <User size={28} />
                </div>
                <div>
                  <h2 className="text-xl font-bold text-slate-800">기본 정보</h2>
                  <p className="text-slate-500">맞춤형 입시 멘토링을 위해 기본 프로필을 입력해주세요.</p>
                </div>
              </div>

              <div className="space-y-6">
                <div>
                  <label className="mb-2 block text-sm font-bold text-slate-700">학년 <span className="text-red-500">*</span></label>
                  <select 
                    value={profile.grade} 
                    onChange={e => setProfile({ grade: e.target.value })}
                    className="w-full rounded-2xl border-2 border-slate-200 bg-slate-50 px-4 py-3.5 outline-none transition-all placeholder:text-slate-400 focus:border-blue-500 focus:bg-white"
                  >
                    <option value="" disabled>선택해주세요</option>
                    <option value="고1">고1</option>
                    <option value="고2">고2</option>
                    <option value="고3">고3</option>
                    <option value="N수생">N수생</option>
                  </select>
                </div>
                
                <div>
                  <label className="mb-2 block text-sm font-bold text-slate-700">계열 <span className="text-red-500">*</span></label>
                  <select 
                    value={profile.track} 
                    onChange={e => setProfile({ track: e.target.value })}
                    className="w-full rounded-2xl border-2 border-slate-200 bg-slate-50 px-4 py-3.5 outline-none transition-all placeholder:text-slate-400 focus:border-blue-500 focus:bg-white"
                  >
                    <option value="" disabled>선택해주세요</option>
                    <option value="인문">인문계열</option>
                    <option value="자연">자연계열</option>
                    <option value="예체능">예체능</option>
                    <option value="기타">기타 / 아직 정하지 않음</option>
                  </select>
                </div>

                <div>
                  <label className="mb-2 block text-sm font-bold text-slate-700">희망 진로 (선택)</label>
                  <input 
                    type="text" 
                    placeholder="예: 소프트웨어 엔지니어, 마케터" 
                    value={profile.career} 
                    onChange={e => setProfile({ career: e.target.value })}
                    className="w-full rounded-2xl border-2 border-slate-200 bg-slate-50 px-4 py-3.5 outline-none transition-all placeholder:text-slate-400 focus:border-blue-500 focus:bg-white"
                  />
                </div>
              </div>
            </div>
          )}

          {step === 2 && (
            <div className="space-y-8">
              <div className="mb-8 flex items-center gap-4">
                <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-indigo-50 text-indigo-600">
                  <Target size={28} />
                </div>
                <div>
                  <h2 className="text-xl font-bold text-slate-800">목표 둥지</h2>
                  <p className="text-slate-500">목표하는 대학과 학과를 설정해 방향성을 좁혀보세요.</p>
                </div>
              </div>

              <div className="space-y-6">
                <div>
                  <label className="mb-2 block text-sm font-bold text-slate-700">목표 대학 <span className="text-red-500">*</span></label>
                  <input 
                    type="text" 
                    placeholder="예: 서울대학교" 
                    value={goals.target_university} 
                    onChange={e => setGoals({ target_university: e.target.value })}
                    className="w-full rounded-2xl border-2 border-slate-200 bg-slate-50 px-4 py-3.5 outline-none transition-all placeholder:text-slate-400 focus:border-blue-500 focus:bg-white"
                  />
                </div>
                
                <div>
                  <label className="mb-2 block text-sm font-bold text-slate-700">목표 학과 (선택)</label>
                  <input 
                    type="text" 
                    placeholder="예: 컴퓨터공학부" 
                    value={goals.target_major} 
                    onChange={e => setGoals({ target_major: e.target.value })}
                    className="w-full rounded-2xl border-2 border-slate-200 bg-slate-50 px-4 py-3.5 outline-none transition-all placeholder:text-slate-400 focus:border-blue-500 focus:bg-white"
                  />
                </div>

                <div>
                  <label className="mb-2 block text-sm font-bold text-slate-700">주력 전형 <span className="text-red-500">*</span></label>
                  <select 
                    value={goals.admission_type} 
                    onChange={e => setGoals({ admission_type: e.target.value })}
                    className="w-full rounded-2xl border-2 border-slate-200 bg-slate-50 px-4 py-3.5 outline-none transition-all placeholder:text-slate-400 focus:border-blue-500 focus:bg-white"
                  >
                    <option value="" disabled>선택해주세요</option>
                    <option value="학생부교과">학생부교과전형</option>
                    <option value="학생부종합">학생부종합전형</option>
                    <option value="논술">논술전형</option>
                    <option value="수능">정시모집(수능)</option>
                    <option value="특기자/기타">특기자/기타전형</option>
                  </select>
                </div>
              </div>
            </div>
          )}

          <div className="mt-12">
            <button
              onClick={handleNext}
              disabled={isNextDisabled}
              className="group flex w-full items-center justify-center gap-2 rounded-2xl bg-blue-600 px-6 py-4 font-bold text-white shadow-lg shadow-blue-500/30 transition-all hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-60 disabled:shadow-none"
            >
              {isLoading ? (
                <Loader2 size={24} className="animate-spin" />
              ) : step === 1 ? (
                <>
                  다음 단계로 <ArrowRight size={20} className="transition-transform group-hover:translate-x-1" />
                </>
              ) : (
                <>
                  <Sparkles size={20} className="text-blue-200" /> 시작하기
                </>
              )}
            </button>
          </div>
        </motion.div>
      </div>
    </div>
  );
}
