import React from 'react';
import { motion, AnimatePresence } from 'motion/react';
import { Trash2, Plus, CheckCircle2, ArrowRight, ChevronUp, ChevronDown, GripVertical } from 'lucide-react';
import { SectionCard, SecondaryButton, SurfaceCard, PrimaryButton, EmptyState } from '../primitives';
import { UniversityLogo } from '../UniversityLogo';
import { CatalogAutocompleteInput } from '../CatalogAutocompleteInput';
import { searchUniversities, searchMajors } from '../../lib/educationCatalog';
import { findFirstInvalidGoal, hasValidGoalSelection, validateGoalSelection } from '../../lib/goalValidation';

import { useOnboardingStore } from '../../store/onboardingStore';
import toast from 'react-hot-toast';

const SPECIAL_UNIVERSITIES = [
  '카이스트', 'KAIST', '한국과학기술원', 
  '유니스트', 'UNIST', '울산과학기술원', 
  '지스트', 'GIST', '광주과학기술원', 
  '디지스트', 'DGIST', '대구경북과학기술원', 
  '켄텍', 'KENTECH', '한국에너지공과대학교', 
  '한국예술종합학교', '한예종', 
  '경찰대학', '육군사관학교', '해군사관학교', '공군사관학교', '국군간호사관학교', '한국전통문화대학교'
];

export const isSpecialUniversity = (univName: string) => SPECIAL_UNIVERSITIES.some(su => univName.includes(su));
export const getRegularGoalCount = (goals: { university: string }[]) => goals.filter(g => !isSpecialUniversity(g.university)).length;

export const DiagnosisGoals: React.FC = () => {
  const { 
    goalList, 
    setGoalList, 
    addGoal, 
    removeGoal, 
    submitGoals, 
    setDiagnosisStep 
  } = useOnboardingStore();
  
  const [isEditingGoals, setIsEditingGoals] = React.useState(goalList.length === 0 || goalList.some(goal => !hasValidGoalSelection(goal)));
  const [univInput, setUnivInput] = React.useState('');
  const [currentUniv, setCurrentUniv] = React.useState('');
  const [currentMajor, setCurrentMajor] = React.useState('');
  const currentGoalValidation = validateGoalSelection(currentUniv, currentMajor);

  React.useEffect(() => {
    if (goalList.length === 0 || goalList.some(goal => !hasValidGoalSelection(goal))) {
      setIsEditingGoals(true);
    }
  }, [goalList]);

  const handleAddGoalDirect = () => {
    if (!currentUniv || !currentMajor) return;
    
    const isSpecial = isSpecialUniversity(currentUniv);
    const regularCount = getRegularGoalCount(goalList);
    
    if (!isSpecial && regularCount >= 6) {
      toast.error('수시 6회(일반 대학)를 모두 채웠습니다. 특수 대학은 추가로 선택할 수 있습니다.');
      return;
    }

    if (!currentGoalValidation.valid) {
      toast.error(currentGoalValidation.message || '선택한 대학에 있는 학과만 추가할 수 있어요.');
      return;
    }
    if (goalList.some((goal) => goal.university === currentUniv && goal.major === currentMajor)) {
      toast.error('이미 추가한 목표입니다.');
      return;
    }
    addGoal({ id: crypto.randomUUID(), university: currentUniv, major: currentMajor });
    setCurrentUniv('');
    setCurrentMajor('');
    setUnivInput('');
  };

  const [draggingGoalId, setDraggingGoalId] = React.useState<string | null>(null);
  const [dragOverGoalId, setDragOverGoalId] = React.useState<string | null>(null);

  const moveGoal = (index: number, direction: 'up' | 'down') => {
    const newIndex = direction === 'up' ? index - 1 : index + 1;
    if (newIndex < 0 || newIndex >= goalList.length) return;

    const newList = [...goalList];
    [newList[index], newList[newIndex]] = [newList[newIndex], newList[index]];
    setGoalList(newList);
  };

  const moveGoalByDrag = (sourceId: string, targetId: string) => {
    if (!sourceId || !targetId || sourceId === targetId) return;
    const sourceIndex = goalList.findIndex(item => item.id === sourceId);
    const targetIndex = goalList.findIndex(item => item.id === targetId);
    if (sourceIndex < 0 || targetIndex < 0) return;

    const newList = [...goalList];
    const [moved] = newList.splice(sourceIndex, 1);
    newList.splice(targetIndex, 0, moved);
    setGoalList(newList);
  };

  const onGoalDragEnd = () => {
    setDraggingGoalId(null);
    setDragOverGoalId(null);
  };

  const saveAndContinue = async () => {
    if (!goalList.length) {
      toast.error('최소 1개의 목표를 설정해 주세요.');
      return;
    }
    const invalidGoal = findFirstInvalidGoal(goalList);
    if (invalidGoal) {
      toast.error(`${invalidGoal.university}에 맞는 학과를 다시 선택해 주세요.`);
      return;
    }
    await submitGoals();
    setIsEditingGoals(false);
  };

  const cancelEdit = () => {
    setIsEditingGoals(false);
    if (goalList.length === 0) {
      // If no goals, we can't really cancel out of edit mode if we want to proceed
    }
  };
  const univPreviewName = (currentUniv || univInput).trim();

  return (
    <motion.div
      key="goals"
      initial={{ opacity: 0, scale: 0.98 }}
      animate={{ opacity: 1, scale: 1 }}
      exit={{ opacity: 0, scale: 0.98 }}
      className="space-y-6"
    >
      <SectionCard
        title="목표 대학 및 학과 선택"
        description="설정한 목표를 바탕으로 생기부를 분석합니다. 대학별 인재상에 맞춰 정밀하게 진단합니다."
        className="border-none bg-white/60 shadow-xl backdrop-blur-2xl ring-1 ring-white/50"
        actions={
          !isEditingGoals ? (
            <SecondaryButton data-testid="diagnosis-edit-goals" onClick={() => setIsEditingGoals(true)}>
              설정 수정하기
            </SecondaryButton>
          ) : null
        }
      >
        {isEditingGoals ? (
          <div className="grid gap-8 lg:grid-cols-2">
            <SurfaceCard tone="muted" className="border-none bg-slate-50 shadow-inner">
              <div className="relative">
                <label className="mb-2 block text-xs font-bold uppercase tracking-[0.14em] text-slate-500">
                  목표 대학교 검색
                </label>
                <input
                  data-testid="diagnosis-university-search"
                  type="text"
                  value={univInput}
                  onChange={(event) => setUnivInput(event.target.value)}
                  placeholder="예: 서울대학교"
                  className="h-12 w-full rounded-2xl border border-slate-200 bg-white px-4 pr-12 text-sm font-semibold shadow-sm transition-all outline-none focus:border-indigo-600 focus:ring-4 focus:ring-indigo-100"
                />
                {univPreviewName.length >= 2 ? (
                  <UniversityLogo
                    universityName={univPreviewName}
                    className="pointer-events-none absolute right-3 top-[34px] h-8 w-8 rounded-lg bg-white object-contain p-1 shadow-sm"
                    fallbackClassName="border border-slate-100"
                  />
                ) : null}
                {univInput ? (
                  <div className="absolute left-0 right-0 top-full z-20 mt-2 max-h-60 overflow-auto rounded-2xl border border-slate-200 bg-white p-2 shadow-2xl backdrop-blur-xl">
                    {searchUniversities(univInput, {
                      excludeNames: goalList.map((goal) => goal.university),
                    }).map((suggestion, index) => (
                      <button
                        key={suggestion.label}
                        type="button"
                        data-testid={`diagnosis-university-option-${index}`}
                        onClick={() => {
                          setCurrentUniv(suggestion.label);
                          setCurrentMajor('');
                          setUnivInput('');
                        }}
                        className="flex w-full items-center gap-3 rounded-xl px-4 py-3 text-left transition-colors hover:bg-indigo-50"
                      >
                        <UniversityLogo
                          universityName={suggestion.label}
                          className="h-6 w-6 rounded-md bg-white object-contain p-0.5"
                        />
                        <span className="text-sm font-bold text-slate-700">{suggestion.label}</span>
                      </button>
                    ))}
                  </div>
                ) : null}
              </div>

              {currentUniv ? (
                <div className="mt-8 space-y-5 rounded-3xl border border-indigo-100 bg-gradient-to-br from-indigo-50 to-transparent p-6">
                  <div className="flex items-center justify-between gap-2 border-b border-indigo-100 pb-4">
                    <div className="flex items-center gap-3">
                      <UniversityLogo
                        universityName={currentUniv}
                        className="h-10 w-10 rounded-xl bg-white object-contain p-1 shadow-md"
                      />
                      <h4 className="text-lg font-black text-slate-900">{currentUniv}</h4>
                    </div>
                    <button
                      type="button"
                      onClick={() => {
                        setCurrentUniv('');
                        setCurrentMajor('');
                      }}
                      className="rounded-xl p-2 text-slate-400 hover:bg-white hover:text-red-500"
                    >
                      <Trash2 size={18} />
                    </button>
                  </div>
                  <CatalogAutocompleteInput
                    label="희망 학과"
                    value={currentMajor}
                    onChange={setCurrentMajor}
                    placeholder="학과명을 직접 입력하거나 검색하세요"
                    suggestions={searchMajors(currentMajor, currentUniv, 15)}
                    onSelect={(item) => setCurrentMajor(item.label)}
                  />
                  <PrimaryButton
                    data-testid="diagnosis-add-goal"
                    onClick={handleAddGoalDirect}
                    disabled={!currentGoalValidation.valid || (!isSpecialUniversity(currentUniv) && getRegularGoalCount(goalList) >= 6)}
                    fullWidth
                    size="lg"
                    className="shadow-lg shadow-blue-500/10"
                  >
                    <Plus size={18} />
                    목표 리스트에 추가
                  </PrimaryButton>
                </div>
              ) : null}
            </SurfaceCard>

            <div className="space-y-3">
              <p className="flex items-center gap-2 text-xs font-bold uppercase tracking-[0.14em] text-slate-500">
                <span>나의 선택 리스트</span>
                <span className={`rounded-full px-2 py-0.5 text-[10px] ${getRegularGoalCount(goalList) === 6 ? 'bg-indigo-100 text-indigo-700' : 'bg-slate-100 text-slate-600'}`}>
                  일반대 {getRegularGoalCount(goalList)}/6
                </span>
              </p>
              <AnimatePresence initial={false}>
                {goalList.map((goal, index) => (
                  <motion.div
                    key={goal.id}
                    layout
                    draggable
                    onDragStart={() => setDraggingGoalId(goal.id)}
                    onDragOver={(e) => {
                      e.preventDefault();
                      setDragOverGoalId(goal.id);
                    }}
                    onDrop={() => {
                      if (draggingGoalId) moveGoalByDrag(draggingGoalId, goal.id);
                      onGoalDragEnd();
                    }}
                    onDragEnd={onGoalDragEnd}
                    initial={{ opacity: 0, scale: 0.95 }}
                    animate={{ opacity: 1, scale: 1 }}
                    exit={{ opacity: 0, scale: 0.95 }}
                    className={`${dragOverGoalId === goal.id ? 'ring-2 ring-blue-500 rounded-3xl' : ''} ${draggingGoalId === goal.id ? 'opacity-40' : ''}`}
                  >
                    <SurfaceCard
                      padding="sm"
                      className="flex items-center justify-between gap-4 border-slate-100 shadow-sm transition-all hover:border-indigo-200"
                    >
                      <div className="flex min-w-0 items-center gap-2">
                        <div className="flex cursor-grab items-center text-slate-300 hover:text-slate-400">
                          <GripVertical size={18} />
                        </div>
                        <div className="flex min-w-0 items-center gap-3">
                          <UniversityLogo
                            universityName={goal.university}
                            className="h-10 w-10 rounded-xl bg-slate-50 object-contain p-1.5"
                          />
                          <div className="min-w-0">
                            <p className="truncate text-sm font-black text-slate-900">{goal.university}</p>
                            <p className="truncate text-xs font-bold text-slate-500">{goal.major}</p>
                          </div>
                        </div>
                      </div>
                      <div className="flex items-center gap-1">
                        {goalList.length > 1 && (
                          <>
                            <button
                              type="button"
                              onClick={() => moveGoal(index, 'up')}
                              disabled={index === 0}
                              className={`rounded-lg p-1.5 transition-colors ${
                                index === 0 ? 'text-slate-200 cursor-not-allowed' : 'text-slate-400 hover:bg-slate-100 hover:text-indigo-600'
                              }`}
                            >
                              <ChevronUp size={16} />
                            </button>
                            <button
                              type="button"
                              onClick={() => moveGoal(index, 'down')}
                              disabled={index === goalList.length - 1}
                              className={`rounded-lg p-1.5 transition-colors ${
                                index === goalList.length - 1 ? 'text-slate-200 cursor-not-allowed' : 'text-slate-400 hover:bg-slate-100 hover:text-indigo-600'
                              }`}
                            >
                              <ChevronDown size={16} />
                            </button>
                          </>
                        )}
                        <div className={`rounded-full px-2.5 py-1 text-[10px] font-black ${
                          index === 0 ? 'bg-indigo-100 text-indigo-600' 
                          : index === 1 ? 'bg-blue-100 text-blue-600'
                          : index === 2 ? 'bg-emerald-100 text-emerald-600'
                          : isSpecialUniversity(goal.university) ? 'bg-purple-100 text-purple-600'
                          : 'bg-slate-100 text-slate-500'
                        }`}>
                          {isSpecialUniversity(goal.university) ? '특수대' : `${index + 1}지망`}
                        </div>
                        <button
                          type="button"
                          onClick={() => removeGoal(goal.id)}
                          className="rounded-lg p-2 text-slate-300 hover:bg-red-50 hover:text-red-500"
                        >
                          <Trash2 size={16} />
                        </button>
                      </div>
                    </SurfaceCard>
                  </motion.div>
                ))}
              </AnimatePresence>
            </div>
          </div>
        ) : goalList.length ? (
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {goalList.map((goal, index) => (
              <div
                key={goal.id}
                className="group relative overflow-hidden rounded-3xl border border-slate-100 bg-slate-50/50 p-5 transition-all hover:bg-white hover:shadow-xl hover:shadow-blue-500/5"
              >
                <div className="mb-4 flex items-center justify-between">
                  <div className={`h-10 w-10 rounded-2xl p-1.5 shadow-sm bg-white`}>
                    <UniversityLogo universityName={goal.university} className="h-full w-full object-contain" />
                  </div>
                  {isSpecialUniversity(goal.university) ? (
                    <span className="rounded-full bg-purple-100 px-3 py-1 text-[10px] font-bold text-purple-600">
                      특수대
                    </span>
                  ) : index === 0 ? (
                    <span className="rounded-full bg-indigo-600 px-3 py-1 text-[10px] font-black text-white shadow-lg shadow-indigo-500/20">
                      1지망
                    </span>
                  ) : index === 1 ? (
                    <span className="rounded-full bg-blue-100 px-3 py-1 text-[10px] font-bold text-blue-600">
                      2지망
                    </span>
                  ) : index === 2 ? (
                    <span className="rounded-full bg-emerald-100 px-3 py-1 text-[10px] font-bold text-emerald-600">
                      3지망
                    </span>
                  ) : (
                    <span className="rounded-full bg-slate-100 px-3 py-1 text-[10px] font-bold text-slate-500">
                      {index + 1}지망
                    </span>
                  )}
                </div>
                <div className="min-w-0">
                  <p className="truncate text-base font-black text-slate-900 group-hover:text-indigo-600 transition-colors">
                    {goal.university}
                  </p>
                  <p className="mt-0.5 truncate text-sm font-bold text-slate-500">{goal.major}</p>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <EmptyState title="설정한 목표가 없습니다" description="나의 입시 전략을 구축할 목표 대학을 선택해 주세요." />
        )}
      </SectionCard>

      {isEditingGoals ? (
        <div className="flex items-center justify-end gap-3">
          <SecondaryButton className="bg-white border-slate-200" onClick={cancelEdit}>
            변경 취소
          </SecondaryButton>
          <PrimaryButton data-testid="diagnosis-save-goals" size="lg" onClick={saveAndContinue}>
            설정 완료
          </PrimaryButton>
        </div>
      ) : goalList.length > 0 && goalList.every(hasValidGoalSelection) ? (
        <div className="flex flex-col items-center gap-6 pt-4">
          <div className="inline-flex items-center gap-3 rounded-2xl bg-indigo-50 px-6 py-3 text-sm font-bold text-indigo-600">
            <CheckCircle2 size={20} className="text-indigo-600" />
            <span>{goalList.length}개의 목표가 성공적으로 설정되었습니다.</span>
          </div>
          <PrimaryButton
            data-testid="diagnosis-goals-continue"
            onClick={() => setDiagnosisStep('UPLOAD')}
            size="lg"
            className="h-14 px-10 text-lg shadow-2xl shadow-indigo-500/20"
          >
            다음: 생기부 등록하기
            <ArrowRight size={22} className="ml-2" />
          </PrimaryButton>
        </div>
      ) : null}
    </motion.div>
  );
};
