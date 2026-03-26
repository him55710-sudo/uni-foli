import React, { useEffect } from 'react';
import { Navigate, useNavigate } from 'react-router-dom';
import { ArrowLeft, ArrowRight, Loader2, Sparkles, Target, User } from 'lucide-react';
import { motion } from 'motion/react';
import { CatalogAutocompleteInput } from '../components/CatalogAutocompleteInput';
import { CatalogMultiSelectInput } from '../components/CatalogMultiSelectInput';
import {
  isEducationCatalogLoaded,
  searchMajors,
  searchUniversities,
  isMajorInUniversity,
} from '../lib/educationCatalog';
import { useAuthStore } from '../store/authStore';
import { useOnboardingStore } from '../store/onboardingStore';

const TEXT = {
  profileTitle: '\uAE30\uBCF8 \uC815\uBCF4 \uC124\uC815',
  goalTitle: '\uBAA9\uD45C \uC815\uBCF4 \uC124\uC815',
  profileSectionTitle: '\uAE30\uBCF8 \uD504\uB85C\uD544',
  profileSectionDescription:
    '\uD559\uB144\uACFC \uACC4\uC5F4\uC744 \uBA3C\uC800 \uC800\uC7A5\uD558\uBA74 \uC774\uD6C4 \uCD94\uCC9C \uD750\uB984\uC774 \uB354 \uC548\uC815\uC801\uC73C\uB85C \uB9DE\uCD94\uC5B4\uC9D1\uB2C8\uB2E4.',
  goalSectionTitle: '\uBAA9\uD45C \uB300\uD559\uACFC \uD559\uACFC',
  goalSectionDescription:
    '\uB300\uD559\uACFC \uD559\uACFC\uB97C \uC800\uC7A5\uD558\uBA74 \uC9C4\uB2E8\uACFC \uB85C\uB4DC\uB9F5\uC774 \uD574\uB2F9 \uBAA9\uD45C\uC5D0 \uB9DE\uAC8C \uC870\uC815\uB429\uB2C8\uB2E4.',
  gradeLabel: '\uD559\uB144',
  trackLabel: '\uACC4\uC5F4',
  careerLabel: '\uD76C\uB9DD \uC9C4\uB85C',
  careerPlaceholder: '\uC608: \uAC74\uCD95\uC0AC, \uD504\uB85C\uB355\uD2B8 \uB514\uC790\uC774\uB108',
  choose: '\uC120\uD0DD\uD574\uC8FC\uC138\uC694',
  universityLabel: '\uBAA9\uD45C \uB300\uD559 *',
  universityPlaceholder: '\uC608: \uC22D\uC2E4\uB300\uD559\uAD50, \uAC74\uAD6D\uB300\uD559\uAD50',
  universityHelperLoaded: '\uCD08\uC131 \uAC80\uC0C9\uC744 \uC9C0\uC6D0\uD569\uB2C8\uB2E4. \uC608: \u3131, \u3131\u3131, \uC22D\uC2E4, \uAC74\uAD6D',
  universityHelperFallback:
    '\uB300\uD559 \uBAA9\uB85D\uC774 \uC5C6\uB354\uB77C\uB3C4 \uC9C1\uC811 \uC785\uB825\uD574\uC11C \uC800\uC7A5\uD560 \uC218 \uC788\uC2B5\uB2C8\uB2E4.',
  universityEmpty:
    '\uC77C\uCE58\uD558\uB294 \uB300\uD559\uC774 \uC5C6\uC5B4\uB3C4 \uC9C1\uC811 \uC785\uB825\uD574\uC11C \uC800\uC7A5\uD560 \uC218 \uC788\uC2B5\uB2C8\uB2E4.',
  majorLabel: '\uBAA9\uD45C \uD559\uACFC',
  majorPlaceholder: '\uC608: \uAC74\uCD95\uD559\uACFC, \uCEF4\uD4E8\uD130\uACF5\uD559\uACFC',
  majorHelperDefault:
    '\uB300\uD559\uC744 \uBA3C\uC800 \uC785\uB825\uD558\uBA74 \uD574\uB2F9 \uB300\uD559 \uD559\uACFC\uB97C \uC6B0\uC120 \uCD94\uCC9C\uD569\uB2C8\uB2E4.',
  majorHelperFallback:
    '\uD559\uACFC\uB3C4 \uC9C1\uC811 \uC785\uB825\uD574\uC11C \uC800\uC7A5\uD560 \uC218 \uC788\uC2B5\uB2C8\uB2E4.',
  majorEmpty:
    '\uC77C\uCE58\uD558\uB294 \uD559\uACFC\uAC00 \uC5C6\uC5B4\uB3C4 \uC9C1\uC811 \uC785\uB825\uD574\uC11C \uC800\uC7A5\uD560 \uC218 \uC788\uC2B5\uB2C8\uB2E4.',
  admissionTypeLabel: '\uC8FC\uB825 \uC804\uD615',
  next: '\uB2E4\uC74C \uB2E8\uACC4\uB85C',
  start: '\uC2DC\uC791\uD558\uAE30',
  loading: '\uC800\uC7A5 \uC911...',
  grade1: '\uACE01',
  grade2: '\uACE02',
  grade3: '\uACE03',
  nStudent: 'N\uC218\uC0DD',
  humanities: '\uC778\uBB38',
  natural: '\uC790\uC5F0',
  arts: '\uC608\uCCB4\uB2A5',
  other: '\uAE30\uD0C0',
  studentRecordAcademic: '\uD559\uC0DD\uBD80\uAD50\uACFC',
  studentRecordGeneral: '\uD559\uC0DD\uBD80\uC885\uD569',
  essay: '\uB17C\uC220',
  regular: '\uC815\uC2DC',
  practical: '\uC2E4\uAE30/\uAE30\uD0C0',
  interestUniversityLabel: '\uAD00\uC2EC \uB300\uD559',
  representativeBadge: '\uB300\uD45C',
};

export function Onboarding() {
  const navigate = useNavigate();
  const { user } = useAuthStore();
  const {
    step,
    profile,
    goals,
    isLoading,
    error,
    setStep,
    setProfile,
    setGoals,
    submitProfile,
    submitGoals,
  } = useOnboardingStore();

  const [univInput, setUnivInput] = React.useState('');

  useEffect(() => {
    if (!user) return;
    setProfile({
      grade: user.grade ?? '',
      track: user.track ?? '',
      career: user.career ?? '',
    });
    setGoals({
      target_university: user.target_university ?? '',
      target_major: user.target_major ?? '',
      admission_type: user.admission_type ?? '',
      interest_universities: user.interest_universities ?? [],
    });
  }, [setGoals, setProfile, user]);

  if (!user) {
    return <Navigate to="/auth" replace />;
  }

  const catalogLoaded = isEducationCatalogLoaded();
  const allSelected = [
    ...(goals.target_university ? [goals.target_university] : []),
    ...goals.interest_universities,
  ];

  const universitySuggestions = searchUniversities(univInput, {
    excludeNames: allSelected,
  });

  const majorSuggestions = searchMajors(goals.target_major, goals.target_university, 20);
  const isStep1Valid = Boolean(profile.grade && profile.track);
  const isStep2Valid = Boolean(goals.target_university && goals.admission_type);
  const isNextDisabled = isLoading || (step === 1 ? !isStep1Valid : !isStep2Valid);

  const handleNext = async () => {
    if (step === 1) {
      const success = await submitProfile();
      if (success) {
        window.scrollTo(0, 0);
      }
      return;
    }

    const success = await submitGoals();
    if (success) {
      navigate('/');
    }
  };

  return (
    <div className="flex min-h-screen flex-col items-center justify-center bg-slate-50 p-6">
      <div className="w-full max-w-2xl">
        <div className="mb-8 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <button
              type="button"
              onClick={() => {
                if (step === 2) {
                  setStep(1);
                }
              }}
              disabled={step === 1 || isLoading}
              className={`flex h-10 w-10 items-center justify-center rounded-xl bg-white shadow-sm transition-all ${
                step === 1 ? 'opacity-0' : 'hover:bg-slate-100'
              }`}
            >
              <ArrowLeft size={20} className="text-slate-600" />
            </button>
            <h1 className="text-2xl font-extrabold text-slate-800">
              {step === 1 ? TEXT.profileTitle : TEXT.goalTitle}
            </h1>
          </div>
          <div className="flex gap-2">
            <div
              className={`h-2.5 w-12 rounded-full transition-all duration-300 ${
                step >= 1 ? 'bg-blue-600' : 'bg-slate-200'
              }`}
            />
            <div
              className={`h-2.5 w-12 rounded-full transition-all duration-300 ${
                step >= 2 ? 'bg-blue-600' : 'bg-slate-200'
              }`}
            />
          </div>
        </div>

        <motion.div
          key={step}
          initial={{ opacity: 0, x: 20 }}
          animate={{ opacity: 1, x: 0 }}
          exit={{ opacity: 0, x: -20 }}
          className="relative overflow-hidden rounded-3xl border border-slate-100 bg-white p-8 text-slate-700 shadow-xl shadow-slate-200/50 sm:p-12"
        >
          {error ? (
            <div className="mb-6 rounded-xl bg-red-50 p-4 text-sm font-medium text-red-600">
              {error}
            </div>
          ) : null}

          {step === 1 ? (
            <div className="space-y-8">
              <div className="mb-8 flex items-center gap-4">
                <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-blue-50 text-blue-600">
                  <User size={28} />
                </div>
                <div>
                  <h2 className="text-xl font-bold text-slate-800">{TEXT.profileSectionTitle}</h2>
                  <p className="text-slate-500">{TEXT.profileSectionDescription}</p>
                </div>
              </div>

              <div className="space-y-6">
                <div>
                  <label className="mb-2 block text-sm font-bold text-slate-700">
                    {TEXT.gradeLabel} <span className="text-red-500">*</span>
                  </label>
                  <select
                    value={profile.grade}
                    onChange={(event) => setProfile({ grade: event.target.value })}
                    className="w-full rounded-2xl border-2 border-slate-200 bg-slate-50 px-4 py-3.5 outline-none transition-all placeholder:text-slate-400 focus:border-blue-500 focus:bg-white"
                  >
                    <option value="" disabled>
                      {TEXT.choose}
                    </option>
                    <option value={TEXT.grade1}>{TEXT.grade1}</option>
                    <option value={TEXT.grade2}>{TEXT.grade2}</option>
                    <option value={TEXT.grade3}>{TEXT.grade3}</option>
                    <option value={TEXT.nStudent}>{TEXT.nStudent}</option>
                  </select>
                </div>

                <div>
                  <label className="mb-2 block text-sm font-bold text-slate-700">
                    {TEXT.trackLabel} <span className="text-red-500">*</span>
                  </label>
                  <select
                    value={profile.track}
                    onChange={(event) => setProfile({ track: event.target.value })}
                    className="w-full rounded-2xl border-2 border-slate-200 bg-slate-50 px-4 py-3.5 outline-none transition-all placeholder:text-slate-400 focus:border-blue-500 focus:bg-white"
                  >
                    <option value="" disabled>
                      {TEXT.choose}
                    </option>
                    <option value={TEXT.humanities}>{TEXT.humanities}</option>
                    <option value={TEXT.natural}>{TEXT.natural}</option>
                    <option value={TEXT.arts}>{TEXT.arts}</option>
                    <option value={TEXT.other}>{TEXT.other}</option>
                  </select>
                </div>

                <div>
                  <label className="mb-2 block text-sm font-bold text-slate-700">{TEXT.careerLabel}</label>
                  <input
                    type="text"
                    placeholder={TEXT.careerPlaceholder}
                    value={profile.career}
                    onChange={(event) => setProfile({ career: event.target.value })}
                    className="w-full rounded-2xl border-2 border-slate-200 bg-slate-50 px-4 py-3.5 outline-none transition-all placeholder:text-slate-400 focus:border-blue-500 focus:bg-white"
                  />
                </div>
              </div>
            </div>
          ) : (
            <div className="space-y-8">
              <div className="mb-8 flex items-center gap-4">
                <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-indigo-50 text-indigo-600">
                  <Target size={28} />
                </div>
                <div>
                  <h2 className="text-xl font-bold text-slate-800">{TEXT.goalSectionTitle}</h2>
                  <p className="text-slate-500">{TEXT.goalSectionDescription}</p>
                </div>
              </div>

              <div className="space-y-6">
                <CatalogMultiSelectInput
                  label={TEXT.universityLabel}
                  selectedUniversities={allSelected}
                  representativeUniversity={goals.target_university}
                  suggestions={universitySuggestions}
                  inputValue={univInput}
                  onInputChange={setUnivInput}
                  onAdd={(name) => {
                    if (!goals.target_university) {
                      setGoals({ target_university: name });
                    } else {
                      setGoals({
                        interest_universities: [...goals.interest_universities, name],
                      });
                    }
                  }}
                  onRemove={(name) => {
                    if (name === goals.target_university) {
                      const nextTarget = goals.interest_universities[0] || '';
                      setGoals({
                        target_university: nextTarget,
                        interest_universities: goals.interest_universities.slice(1),
                        // Reset major if it's not in the new target
                        target_major:
                          nextTarget && isMajorInUniversity(nextTarget, goals.target_major)
                            ? goals.target_major
                            : '',
                      });
                    } else {
                      setGoals({
                        interest_universities: goals.interest_universities.filter((u) => u !== name),
                      });
                    }
                  }}
                  onSetRepresentative={(name) => {
                    if (name === goals.target_university) return;
                    const oldTarget = goals.target_university;
                    setGoals({
                      target_university: name,
                      interest_universities: [
                        ...goals.interest_universities.filter((u) => u !== name),
                        ...(oldTarget ? [oldTarget] : []),
                      ],
                      // Reset major if it's not in the new target
                      target_major: isMajorInUniversity(name, goals.target_major)
                        ? goals.target_major
                        : '',
                    });
                  }}
                  placeholder={TEXT.universityPlaceholder}
                  helperText={
                    catalogLoaded ? TEXT.universityHelperLoaded : TEXT.universityHelperFallback
                  }
                  emptyText={TEXT.universityEmpty}
                />

                <CatalogAutocompleteInput
                  label={TEXT.majorLabel}
                  value={goals.target_major}
                  placeholder={TEXT.majorPlaceholder}
                  suggestions={majorSuggestions}
                  onChange={(value) => setGoals({ target_major: value })}
                  onSelect={(suggestion) => setGoals({ target_major: suggestion.label })}
                  helperText={
                    catalogLoaded
                      ? goals.target_university.trim()
                        ? `${goals.target_university} \uAE30\uC900\uC73C\uB85C \uD559\uACFC\uB97C \uC6B0\uC120 \uCD94\uCC9C\uD569\uB2C8\uB2E4.`
                        : TEXT.majorHelperDefault
                      : TEXT.majorHelperFallback
                  }
                  emptyText={TEXT.majorEmpty}
                />

                <div>
                  <label className="mb-2 block text-sm font-bold text-slate-700">
                    {TEXT.admissionTypeLabel} <span className="text-red-500">*</span>
                  </label>
                  <select
                    value={goals.admission_type}
                    onChange={(event) => setGoals({ admission_type: event.target.value })}
                    className="w-full rounded-2xl border-2 border-slate-200 bg-slate-50 px-4 py-3.5 outline-none transition-all placeholder:text-slate-400 focus:border-blue-500 focus:bg-white"
                  >
                    <option value="" disabled>
                      {TEXT.choose}
                    </option>
                    <option value={TEXT.studentRecordAcademic}>{TEXT.studentRecordAcademic}</option>
                    <option value={TEXT.studentRecordGeneral}>{TEXT.studentRecordGeneral}</option>
                    <option value={TEXT.essay}>{TEXT.essay}</option>
                    <option value={TEXT.regular}>{TEXT.regular}</option>
                    <option value={TEXT.practical}>{TEXT.practical}</option>
                  </select>
                </div>
              </div>
            </div>
          )}

          <div className="mt-12">
            <button
              type="button"
              onClick={handleNext}
              disabled={isNextDisabled}
              className="group flex w-full items-center justify-center gap-2 rounded-2xl bg-blue-600 px-6 py-4 font-bold text-white shadow-lg shadow-blue-500/30 transition-all hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-60 disabled:shadow-none"
            >
              {isLoading ? (
                <Loader2 size={24} className="animate-spin" />
              ) : step === 1 ? (
                <>
                  {TEXT.next}
                  <ArrowRight size={20} className="transition-transform group-hover:translate-x-1" />
                </>
              ) : (
                <>
                  <Sparkles size={20} className="text-blue-200" />
                  {TEXT.start}
                </>
              )}
            </button>
          </div>
        </motion.div>
      </div>
    </div>
  );
}
