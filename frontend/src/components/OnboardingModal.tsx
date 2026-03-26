import React, { useEffect, useState } from 'react';
import { AnimatePresence, motion } from 'motion/react';
import { ArrowRight, Goal, GraduationCap, School, Sparkles, X } from 'lucide-react';
import { CatalogAutocompleteInput } from './CatalogAutocompleteInput';
import { CatalogMultiSelectInput } from './CatalogMultiSelectInput';
import {
  isEducationCatalogLoaded,
  isMajorInUniversity,
  searchMajors,
  searchUniversities,
} from '../lib/educationCatalog';

interface OnboardingModalProps {
  isOpen: boolean;
  onClose: () => void;
  initialUniversity?: string | null;
  initialMajor?: string | null;
  initialInterests?: string[];
  isSubmitting: boolean;
  onSubmit: (payload: {
    targetUniversity: string;
    targetMajor: string;
    interestUniversities: string[];
  }) => Promise<void>;
}

const TEXT = {
  chip: '초기 목표 설정',
  title: '원하는 대학과 학과를 먼저 맞춥니다',
  description:
    '목표 대학과 전공이 있어야 진단, 로드맵, 추천 과제 방향을 더 정확하게 맞출 수 있습니다.',
  step1: '목표 대학 설정',
  step2: '희망 학과 설정',
  universityLabel: '어느 대학을 목표로 하고 있나요?',
  universityPlaceholder: '예: 숭실대학교, 건국대학교',
  universityHelperLoaded: '초성 검색을 지원합니다.',
  universityHelperFallback:
    '아직 대학 목록을 불러오기 전이라도 직접 입력해서 저장할 수 있습니다.',
  universityEmpty:
    '일치하는 대학이 없어도 직접 입력해서 저장할 수 있습니다.',
  majorLabel: '어느 학과를 목표로 하고 있나요?',
  majorPlaceholder: '예: 건축학과, 컴퓨터공학과',
  majorHelperDefault:
    '선택한 대학의 학과를 우선 추천합니다.',
  majorHelperFallback: '학과도 직접 입력해서 저장할 수 있습니다.',
  majorEmpty:
    '일치하는 학과가 없어도 직접 입력해서 저장할 수 있습니다.',
  previous: '이전 단계',
  next: '다음',
  addGoal: '이 목표 추가하기',
  saving: '저장 중...',
  submit: '설정 완료 및 저장',
  goalListTitle: '설정된 목표 목록',
};

interface GoalItem {
  university: string;
  major: string;
}

export function OnboardingModal({
  isOpen,
  onClose,
  initialUniversity,
  initialMajor,
  initialInterests,
  isSubmitting,
  onSubmit,
}: OnboardingModalProps) {
  const [step, setStep] = useState<1 | 2>(1);
  const [currentUniv, setCurrentUniv] = useState('');
  const [currentMajor, setCurrentMajor] = useState('');
  const [goals, setGoals] = useState<GoalItem[]>([]);
  const [univInput, setUnivInput] = useState('');

  useEffect(() => {
    if (!isOpen) return;
    setStep(1);
    setCurrentUniv('');
    setCurrentMajor('');
    setUnivInput('');
    
    const initialGoals: GoalItem[] = [];
    if (initialUniversity && initialMajor) {
      initialGoals.push({ university: initialUniversity, major: initialMajor });
    }
    
    if (initialInterests && initialInterests.length > 0) {
      initialInterests.forEach(interest => {
        // Try to parse "University (Major)"
        const match = interest.match(/^(.+)\s\((.+)\)$/);
        if (match) {
          initialGoals.push({ university: match[1], major: match[2] });
        } else {
          initialGoals.push({ university: interest, major: '전공 미지정' });
        }
      });
    }
    
    setGoals(initialGoals);
  }, [initialInterests, initialMajor, initialUniversity, isOpen]);

  if (!isOpen) return null;

  const catalogLoaded = isEducationCatalogLoaded();
  
  const universitySuggestions = searchUniversities(univInput, {
    excludeNames: [currentUniv, ...goals.map(g => g.university)],
    limit: 100
  });

  const majorSuggestions = searchMajors(currentMajor, currentUniv, 20);
  
  const canMoveNext = currentUniv.trim().length >= 2 || univInput.trim().length >= 2;
  const canAddGoal = (currentUniv.trim().length >= 2 || univInput.trim().length >= 2) && currentMajor.trim().length >= 2;

  const handleAddGoal = () => {
    const univ = currentUniv || univInput.trim();
    if (!univ || currentMajor.trim().length < 2) return;
    
    setGoals(prev => [...prev, { university: univ, major: currentMajor.trim() }]);
    setCurrentUniv('');
    setCurrentMajor('');
    setUnivInput('');
    setStep(1);
  };

  const handleRemoveGoal = (index: number) => {
    setGoals(prev => prev.filter((_, i) => i !== index));
  };

  return (
    <div 
      className="fixed inset-0 z-50 flex items-end justify-center bg-slate-900/40 p-0 backdrop-blur-[2px] sm:items-center sm:p-4"
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <motion.div
        initial={{ opacity: 0, y: 30 }}
        animate={{ opacity: 1, y: 0 }}
        exit={{ opacity: 0, y: 30 }}
        className="relative w-full rounded-t-[32px] bg-white p-6 shadow-2xl sm:max-w-xl sm:rounded-[32px] sm:p-8"
        onClick={(e) => e.stopPropagation()}
      >
        <button
          onClick={onClose}
          className="absolute right-4 top-4 z-10 rounded-full p-2 text-slate-400 transition-colors hover:bg-slate-100 hover:text-slate-600 sm:right-6 sm:top-6"
        >
          <X size={20} />
        </button>

        <div className="mb-8 flex items-start gap-4 pr-12">
          <div className="flex-1">
            <div className="mb-3 inline-flex items-center gap-2 rounded-full border border-blue-100 bg-blue-50 px-3 py-1 text-[11px] font-extrabold text-blue-600">
              <Sparkles size={12} />
              {TEXT.chip}
            </div>
            <h2 className="text-2xl font-black tracking-tight text-slate-800 sm:text-3xl">{TEXT.title}</h2>
          </div>
          <div className="hidden h-14 w-14 shrink-0 items-center justify-center rounded-2xl bg-slate-50 text-slate-400 sm:flex">
            <GraduationCap size={28} />
          </div>
        </div>

        {/* Goals List Display */}
        {goals.length > 0 && (
          <div className="mb-6">
            <h3 className="mb-2 text-xs font-black uppercase tracking-wider text-slate-400">{TEXT.goalListTitle}</h3>
            <div className="flex flex-wrap gap-2">
              {goals.map((goal, idx) => (
                <div key={idx} className="flex items-center gap-2 rounded-xl bg-blue-50 border border-blue-100 px-3 py-2 text-sm">
                  <span className="font-bold text-blue-700">{goal.university}</span>
                  <span className="text-blue-400">|</span>
                  <span className="font-medium text-blue-600">{goal.major}</span>
                  <button 
                    onClick={() => handleRemoveGoal(idx)}
                    className="ml-1 text-blue-300 hover:text-blue-500"
                  >
                    <X size={14} />
                  </button>
                </div>
              ))}
            </div>
          </div>
        )}

        <div className="mb-6 grid grid-cols-2 gap-3">
          <div
            className={`rounded-2xl border px-4 py-3 transition-colors ${
              step === 1 ? 'border-blue-500 bg-blue-50/50' : 'border-slate-100 bg-slate-50'
            }`}
          >
            <div className={`mb-1 flex items-center gap-2 text-xs font-black ${step === 1 ? 'text-blue-600' : 'text-slate-500'}`}>
              <School size={14} />
              Step 1
            </div>
            <p className={`text-sm font-bold ${step === 1 ? 'text-slate-800' : 'text-slate-400'}`}>{TEXT.step1}</p>
          </div>
          <div
            className={`rounded-2xl border px-4 py-3 transition-colors ${
              step === 2 ? 'border-blue-500 bg-blue-50/50' : 'border-slate-100 bg-slate-50'
            }`}
          >
            <div className={`mb-1 flex items-center gap-2 text-xs font-black ${step === 2 ? 'text-blue-600' : 'text-slate-500'}`}>
              <Goal size={14} />
              Step 2
            </div>
            <p className={`text-sm font-bold ${step === 2 ? 'text-slate-800' : 'text-slate-400'}`}>{TEXT.step2}</p>
          </div>
        </div>

        <AnimatePresence mode="wait">
          {step === 1 ? (
            <motion.div
              key="univ-selection"
              initial={{ opacity: 0, x: 10 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: -10 }}
            >
              <CatalogMultiSelectInput
                label={TEXT.universityLabel}
                selectedUniversities={currentUniv ? [currentUniv] : []}
                representativeUniversity={currentUniv}
                suggestions={universitySuggestions}
                inputValue={univInput}
                onInputChange={setUnivInput}
                onAdd={(name) => {
                  setCurrentUniv(name);
                  setUnivInput('');
                  setStep(2);
                }}
                onRemove={() => {
                  setCurrentUniv('');
                }}
                onSetRepresentative={() => {}}
                placeholder={TEXT.universityPlaceholder}
                helperText={
                  catalogLoaded ? TEXT.universityHelperLoaded : TEXT.universityHelperFallback
                }
                emptyText={TEXT.universityEmpty}
              />
              <div className="mt-4 flex justify-end">
                <button
                  disabled={!canMoveNext}
                  onClick={() => {
                    if (!currentUniv && univInput.trim()) {
                      setCurrentUniv(univInput.trim());
                      setUnivInput('');
                    }
                    setStep(2);
                  }}
                  className="flex items-center gap-2 rounded-xl bg-slate-100 px-4 py-2 text-sm font-bold text-slate-600 hover:bg-slate-200"
                >
                  {TEXT.next} <ArrowRight size={14} />
                </button>
              </div>
            </motion.div>
          ) : (
            <motion.div
              key="major-selection"
              initial={{ opacity: 0, x: 10 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: -10 }}
            >
              <div className="mb-4 rounded-2xl bg-slate-50 p-4 border border-slate-100">
                <span className="text-xs font-bold text-slate-400 block mb-1">선택된 대학</span>
                <span className="text-lg font-black text-slate-700">{currentUniv || univInput}</span>
              </div>
              <CatalogAutocompleteInput
                label={TEXT.majorLabel}
                value={currentMajor}
                placeholder={TEXT.majorPlaceholder}
                suggestions={majorSuggestions}
                onChange={setCurrentMajor}
                onSelect={(suggestion) => {
                  setCurrentMajor(suggestion.label);
                }}
                helperText={
                  catalogLoaded
                    ? `${currentUniv || univInput} 기준으로 학과 후보를 보여줍니다.`
                    : TEXT.majorHelperFallback
                }
                emptyText={TEXT.majorEmpty}
                autoFocus
              />
              <div className="mt-4 flex gap-3">
                <button
                  onClick={() => setStep(1)}
                  className="flex-1 rounded-xl border border-slate-200 py-3 text-sm font-bold text-slate-500"
                >
                  {TEXT.previous}
                </button>
                <button
                  disabled={!canAddGoal}
                  onClick={handleAddGoal}
                  className="flex-[2] rounded-xl bg-blue-600 py-3 text-sm font-black text-white hover:bg-blue-700 disabled:opacity-40"
                >
                  {TEXT.addGoal}
                </button>
              </div>
            </motion.div>
          )}
        </AnimatePresence>

        <div className="mt-8 border-t border-slate-100 pt-6">
          <button
            type="button"
            disabled={goals.length === 0 || isSubmitting}
            onClick={() => {
              const mainGoal = goals[0];
              const others = goals.slice(1).map((g) => `${g.university} (${g.major})`);
              void onSubmit({
                targetUniversity: mainGoal.university,
                targetMajor: mainGoal.major,
                interestUniversities: others,
              });
            }}
            className="flex w-full items-center justify-center gap-2 rounded-2xl bg-slate-900 px-4 py-4 text-base font-black text-white transition-all hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-40"
          >
            {isSubmitting ? TEXT.saving : TEXT.submit}
            <ArrowRight size={18} />
          </button>
        </div>
      </motion.div>
    </div>
  );
}
