import React from 'react';
import { motion } from 'motion/react';
import { User, Loader2, ArrowRight } from 'lucide-react';
import { useOnboardingStore } from '../../store/onboardingStore';
import { PrimaryButton } from '../primitives';

const TEXT = {
  profileSectionTitle: '기본 프로필 설정',
  profileSectionDescription: '학년과 계열을 먼저 저장하면 이후 추천 흐름이 더욱 정확해집니다.',
  gradeLabel: '학년',
  trackLabel: '계열',
  careerLabel: '희망 진로',
  careerPlaceholder: '예: 건축가, 소프트웨어 엔지니어',
  choose: '선택해주세요',
  next: '다음 단계로',
  grade1: '고1', grade2: '고2', grade3: '고3', nStudent: 'N수생',
  humanities: '인문', natural: '자연', arts: '예체능', other: '기타',
};

export function DiagnosisProfile() {
  const { profile, setProfile, submitProfile, isLoading, error } = useOnboardingStore();

  const isFormValid = profile.grade && profile.track;

  const handleSubmit = async () => {
    if (!isFormValid) return;
    await submitProfile();
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -20 }}
      className="mx-auto max-w-2xl space-y-8"
    >
      <div className="flex gap-4">
        <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-indigo-50 text-indigo-600">
          <User size={32} />
        </div>
        <div>
          <h2 className="text-xl font-black text-slate-800">{TEXT.profileSectionTitle}</h2>
          <p className="font-medium text-slate-500">{TEXT.profileSectionDescription}</p>
        </div>
      </div>

      <div className="space-y-6 rounded-[2.5rem] border border-slate-100 bg-white p-8 shadow-xl shadow-slate-200/50 md:p-10">
        {error && (
          <div className="mb-6 rounded-2xl bg-red-50 p-4 font-bold text-red-600">
            {error}
          </div>
        )}

        <div className="grid gap-8 md:grid-cols-2">
          <div className="space-y-2">
            <label className="text-sm font-black text-slate-700">{TEXT.gradeLabel}</label>
            <select
              value={profile.grade}
              onChange={(e) => setProfile({ grade: e.target.value })}
              className="w-full rounded-2xl border-2 border-slate-100 bg-slate-50 p-4 font-bold outline-none focus:border-indigo-600 focus:bg-white"
            >
              <option value="">{TEXT.choose}</option>
              {[TEXT.grade1, TEXT.grade2, TEXT.grade3, TEXT.nStudent].map((o) => (
                <option key={o} value={o}>{o}</option>
              ))}
            </select>
          </div>
          <div className="space-y-2">
            <label className="text-sm font-black text-slate-700">{TEXT.trackLabel}</label>
            <select
              value={profile.track}
              onChange={(e) => setProfile({ track: e.target.value })}
              className="w-full rounded-2xl border-2 border-slate-100 bg-slate-50 p-4 font-bold outline-none focus:border-indigo-600 focus:bg-white"
            >
              <option value="">{TEXT.choose}</option>
              {[TEXT.humanities, TEXT.natural, TEXT.arts, TEXT.other].map((o) => (
                <option key={o} value={o}>{o}</option>
              ))}
            </select>
          </div>
        </div>

        <div className="space-y-2">
          <label className="text-sm font-black text-slate-700">{TEXT.careerLabel}</label>
          <input
            type="text"
            value={profile.career}
            onChange={(e) => setProfile({ career: e.target.value })}
            placeholder={TEXT.careerPlaceholder}
            className="w-full rounded-2xl border-2 border-slate-100 bg-slate-50 p-4 font-bold outline-none focus:border-indigo-600 focus:bg-white"
          />
        </div>

        <div className="pt-4">
          <PrimaryButton
            onClick={handleSubmit}
            disabled={!isFormValid || isLoading}
            className="w-full py-5 text-xl"
          >
            {isLoading ? (
              <Loader2 className="animate-spin" />
            ) : (
              <div className="flex items-center gap-2">
                {TEXT.next} <ArrowRight />
              </div>
            )}
          </PrimaryButton>
        </div>
      </div>
    </motion.div>
  );
}
