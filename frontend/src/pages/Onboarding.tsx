import React, { useEffect, useState } from 'react';
import { Navigate, useNavigate } from 'react-router-dom';
import { ArrowLeft, ArrowRight, Loader2, Sparkles, Target, User, Trash2, School, ChevronUp, ChevronDown } from 'lucide-react';
import { motion } from 'motion/react';
import { CatalogAutocompleteInput } from '../components/CatalogAutocompleteInput';
import { useAuthStore } from '../store/authStore';
import { useOnboardingStore } from '../store/onboardingStore';
import { searchUniversities, searchMajors } from '../lib/educationCatalog';

const TEXT = {
  profileTitle: '기본 정보 설정',
  goalTitle: '목표 대학 설정',
  profileSectionTitle: '기본 프로필',
  profileSectionDescription: '학년과 계열을 먼저 저장하면 이후 추천 흐름이 더 안정적으로 맞춰집니다.',
  goalSectionTitle: '나의 목표 대학 (최대 6개)',
  goalSectionDescription: '최대 6개까지 가장 가고 싶은 순서대로 담아보세요.',
  gradeLabel: '학년',
  trackLabel: '계열',
  careerLabel: '희망 진로',
  careerPlaceholder: '예: 건축가, 프로덕트 디자이너',
  choose: '선택해주세요',
  universityLabel: '대학 선택',
  majorLabel: '학과 선택',
  admissionTypeLabel: '주력 전형',
  next: '다음 단계로',
  start: '시작하기',
  loading: '저장 중...',
  grade1: '고1', grade2: '고2', grade3: '고3', nStudent: 'N수생',
  humanities: '인문', natural: '자연', arts: '예체능', other: '기타',
  academic: '학생부교과', general: '학생부종합', essay: '논술', regular: '정시', practical: '실기/기타',
  addGoal: '이 목표 추가',
  emptyGoals: '아직 추가된 대학이 없습니다.',
};

export function Onboarding() {
  const navigate = useNavigate();
  const { user } = useAuthStore();
  const { step, profile, goals, isLoading, error, setStep, setProfile, setGoals, submitProfile, submitGoals } = useOnboardingStore();

  const [univInput, setUnivInput] = useState('');
  const [currentUniv, setCurrentUniv] = useState('');
  const [currentMajor, setCurrentMajor] = useState('');
  const [goalList, setGoalList] = useState<{id: string, university: string, major: string}[]>([]);

  useEffect(() => {
    if (!user) return;
    setProfile({ grade: user.grade ?? '', track: user.track ?? '', career: user.career ?? '' });
    
    const generateId = () => {
      try {
        return crypto.randomUUID();
      } catch {
        return Math.random().toString(36).substring(2) + Date.now().toString(36);
      }
    };

    const initialList: { id: string; university: string; major: string }[] = [];
    if (user.target_university && user.target_major) {
      initialList.push({ id: generateId(), university: user.target_university, major: user.target_major });
    }
    user.interest_universities?.forEach(i => {
      const match = i.match(/^(.+)\s\((.+)\)$/);
      if (match) initialList.push({ id: generateId(), university: match[1], major: match[2] });
      else initialList.push({ id: generateId(), university: i, major: '' });
    });
    setGoalList(initialList.slice(0, 6));
  }, [user]);

  if (!user) return <Navigate to="/auth" replace />;

  const universitySuggestions = searchUniversities(univInput, { excludeNames: [currentUniv, ...goalList.map(g => g.university)] });
  const majorSuggestions = searchMajors(currentMajor, currentUniv, 20);

  const handleAddGoal = () => {
    const generateId = () => {
      try {
        return crypto.randomUUID();
      } catch {
        return Math.random().toString(36).substring(2) + Date.now().toString(36);
      }
    };
    if (!currentUniv || !currentMajor || goalList.length >= 6) return;
    setGoalList(prev => [...prev, { id: generateId(), university: currentUniv, major: currentMajor }]);
    setCurrentUniv('');
    setCurrentMajor('');
    setUnivInput('');
  };

  const removeGoal = (id: string) => setGoalList(prev => prev.filter(g => g.id !== id));
  const moveGoal = (idx: number, dir: 'up' | 'down') => {
    const newList = [...goalList];
    const targetIdx = dir === 'up' ? idx - 1 : idx + 1;
    if (targetIdx < 0 || targetIdx >= goalList.length) return;
    [newList[idx], newList[targetIdx]] = [newList[targetIdx], newList[idx]];
    setGoalList(newList);
  };

  const handleStart = async () => {
    if (goalList.length === 0) return;
    const main = goalList[0];
    const others = goalList.slice(1).map(g => `${g.university} (${g.major})`);
    
    // Update store state before submit
    setGoals({
      target_university: main.university,
      target_major: main.major,
      interest_universities: others,
      admission_type: goals.admission_type || '학생부종합'
    });
    
    const success = await submitGoals();
    if (success) navigate('/');
  };

  return (
    <div className="flex min-h-screen flex-col items-center justify-center bg-slate-50 p-6">
      <div className="w-full max-w-3xl">
        <div className="mb-10 flex items-center justify-between">
          <div className="flex items-center gap-4">
            <button onClick={() => step === 2 && setStep(1)} disabled={step === 1 || isLoading} className={`h-12 w-12 flex items-center justify-center rounded-2xl bg-white shadow-sm ${step === 1 ? 'opacity-0' : 'hover:bg-slate-100'}`}><ArrowLeft/></button>
            <h1 className="text-3xl font-black text-slate-900">{step === 1 ? TEXT.profileTitle : TEXT.goalTitle}</h1>
          </div>
          <div className="flex gap-2">
             <div className={`h-2.5 w-16 rounded-full ${step >= 1 ? 'bg-blue-600' : 'bg-slate-200'}`} />
             <div className={`h-2.5 w-16 rounded-full ${step >= 2 ? 'bg-blue-600' : 'bg-slate-200'}`} />
          </div>
        </div>

        <motion.div key={step} initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} className="bg-white rounded-[40px] border border-slate-100 p-10 shadow-xl shadow-slate-200/50">
          {error && <div className="mb-6 p-4 bg-red-50 text-red-600 rounded-2xl font-bold">{error}</div>}

          {step === 1 ? (
            <div className="space-y-10">
              <div className="flex gap-4">
                <div className="h-16 w-16 bg-blue-50 text-blue-600 flex items-center justify-center rounded-2xl"><User size={32}/></div>
                <div><h2 className="text-xl font-black text-slate-800">{TEXT.profileSectionTitle}</h2><p className="text-slate-500 font-medium">{TEXT.profileSectionDescription}</p></div>
              </div>
              <div className="grid md:grid-cols-2 gap-8">
                 <div className="space-y-2">
                    <label className="text-sm font-black text-slate-700">{TEXT.gradeLabel}</label>
                    <select value={profile.grade} onChange={e => setProfile({ grade: e.target.value })} className="w-full p-4 bg-slate-50 border-2 border-slate-100 rounded-2xl font-bold outline-none focus:border-blue-500">
                       <option value="">{TEXT.choose}</option>
                       {[TEXT.grade1, TEXT.grade2, TEXT.grade3, TEXT.nStudent].map(o => <option key={o} value={o}>{o}</option>)}
                    </select>
                 </div>
                 <div className="space-y-2">
                    <label className="text-sm font-black text-slate-700">{TEXT.trackLabel}</label>
                    <select value={profile.track} onChange={e => setProfile({ track: e.target.value })} className="w-full p-4 bg-slate-50 border-2 border-slate-100 rounded-2xl font-bold outline-none focus:border-blue-500">
                       <option value="">{TEXT.choose}</option>
                       {[TEXT.humanities, TEXT.natural, TEXT.arts, TEXT.other].map(o => <option key={o} value={o}>{o}</option>)}
                    </select>
                 </div>
              </div>
              <div className="space-y-2">
                <label className="text-sm font-black text-slate-700">{TEXT.careerLabel}</label>
                <input type="text" value={profile.career} onChange={e => setProfile({ career: e.target.value })} placeholder={TEXT.careerPlaceholder} className="w-full p-4 bg-slate-50 border-2 border-slate-100 rounded-2xl font-bold outline-none focus:border-blue-500" />
              </div>
              <button onClick={submitProfile} disabled={!profile.grade || !profile.track || isLoading} className="w-full py-5 bg-blue-600 text-white rounded-2xl font-black text-xl flex items-center justify-center gap-2 hover:bg-blue-700 disabled:opacity-40 shadow-lg shadow-blue-500/20">
                {isLoading ? <Loader2 className="animate-spin"/> : <>{TEXT.next} <ArrowRight/></>}
              </button>
            </div>
          ) : (
            <div className="space-y-10">
               <div className="grid lg:grid-cols-2 gap-10">
                 {/* Selection Part */}
                 <div className="space-y-8">
                    <div className="flex gap-4">
                      <div className="h-16 w-16 bg-blue-50 text-blue-600 flex items-center justify-center rounded-2xl"><Target size={32}/></div>
                      <div><h2 className="text-xl font-black text-slate-800">{TEXT.goalSectionTitle}</h2><p className="text-slate-500 font-medium whitespace-pre-line">{TEXT.goalSectionDescription}</p></div>
                    </div>
                    
                    <div className="p-6 bg-slate-50 border border-slate-100 rounded-[32px] space-y-6">
                       <div className="relative">
                         <label className="text-xs font-black text-slate-400 mb-2 block">{TEXT.universityLabel}</label>
                         <input type="text" value={univInput} onChange={e => setUnivInput(e.target.value)} placeholder="대학명 검색..." className="w-full p-4 bg-white border-2 border-slate-100 rounded-xl font-bold outline-none focus:border-blue-500" />
                         {univInput && universitySuggestions.length > 0 && (
                            <div className="absolute top-full left-0 right-0 z-10 mt-1 max-h-40 overflow-auto bg-white border border-slate-100 rounded-xl shadow-xl">
                               {universitySuggestions.map(s => <button key={s.label} onClick={() => { setCurrentUniv(s.label); setUnivInput(''); }} className="w-full text-left p-3 hover:bg-slate-50 text-sm font-bold border-b border-slate-50 last:border-0">{s.label}</button>)}
                            </div>
                         )}
                       </div>

                       {currentUniv && (
                         <div className="space-y-4">
                            <div className="p-3 bg-white rounded-xl border border-blue-100 flex items-center justify-between">
                               <span className="text-sm font-black text-blue-600">{currentUniv}</span>
                               <button onClick={() => setCurrentUniv('')} className="text-slate-400"><Trash2 size={16}/></button>
                            </div>
                            <CatalogAutocompleteInput label={TEXT.majorLabel} value={currentMajor} onChange={setCurrentMajor} placeholder="전공명 입력..." suggestions={searchMajors(currentMajor, currentUniv, 20)} onSelect={s => setCurrentMajor(s.label)} />
                            <button onClick={handleAddGoal} disabled={!currentUniv || currentMajor.length < 2 || goalList.length >= 6} className="w-full py-4 bg-slate-900 text-white rounded-xl font-black text-sm">
                               {TEXT.addGoal} (+{goalList.length}/6)
                            </button>
                         </div>
                       )}

                       <div className="pt-4 border-t border-slate-200">
                          <label className="text-xs font-black text-slate-400 mb-2 block">{TEXT.admissionTypeLabel}</label>
                          <select value={goals.admission_type} onChange={e => setGoals({ admission_type: e.target.value })} className="w-full p-4 bg-white border-2 border-slate-100 rounded-xl font-bold outline-none focus:border-blue-500">
                             <option value="">{TEXT.choose}</option>
                             {[TEXT.academic, TEXT.general, TEXT.essay, TEXT.regular, TEXT.practical].map(o => <option key={o} value={o}>{o}</option>)}
                          </select>
                       </div>
                    </div>
                 </div>

                 {/* List Part */}
                 <div className="space-y-4">
                    <h3 className="text-xs font-black text-slate-400 uppercase tracking-widest">Selected Goals</h3>
                    {goalList.length === 0 ? (
                      <div className="h-64 flex flex-col items-center justify-center border-2 border-dashed border-slate-100 rounded-[32px] text-slate-300">
                         <School size={48} className="mb-2 opacity-10" />
                         <p className="text-sm font-bold">{TEXT.emptyGoals}</p>
                      </div>
                    ) : (
                      <div className="space-y-3">
                        {goalList.map((g, idx) => (
                           <motion.div key={g.id} initial={{ opacity: 0, x: -10 }} animate={{ opacity: 1, x: 0 }} className="flex items-center gap-4 p-4 bg-slate-50 border border-slate-100 rounded-2xl group">
                              <div className="text-slate-300 font-black text-lg italic">#{idx+1}</div>
                              <div className="flex-1 min-w-0">
                                 <p className="text-sm font-black text-slate-800 truncate">{g.university}</p>
                                 <p className="text-[11px] font-bold text-slate-500">{g.major}</p>
                              </div>
                              <div className="flex gap-1 opacity-0 group-hover:opacity-100">
                                 <button onClick={() => moveGoal(idx, 'up')} disabled={idx===0} className="p-1 text-slate-400 hover:text-blue-500 disabled:opacity-0"><ChevronUp size={20}/></button>
                                 <button onClick={() => moveGoal(idx, 'down')} disabled={idx===goalList.length-1} className="p-1 text-slate-400 hover:text-blue-500 disabled:opacity-0"><ChevronDown size={20}/></button>
                                 <button onClick={() => removeGoal(g.id)} className="p-1 text-slate-400 hover:text-red-500"><Trash2 size={20}/></button>
                              </div>
                           </motion.div>
                        ))}
                      </div>
                    )}
                 </div>
               </div>

               <div className="pt-10 border-t">
                  <button onClick={handleStart} disabled={goalList.length === 0 || !goals.admission_type || isLoading} className="w-full py-5 bg-slate-900 text-white rounded-[24px] font-black text-2xl flex items-center justify-center gap-3 hover:bg-black disabled:opacity-30 shadow-2xl">
                     {isLoading ? <Loader2 className="animate-spin"/> : <><Sparkles size={24} className="text-yellow-400"/> {TEXT.start}</>}
                  </button>
               </div>
            </div>
          )}
        </motion.div>
      </div>
    </div>
  );
}
