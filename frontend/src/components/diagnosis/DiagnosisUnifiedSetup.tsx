import React, { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'motion/react';
import { FileUp, Loader2, Plus, Settings2, Trash2, CheckCircle2 } from 'lucide-react';
import { useDropzone } from 'react-dropzone';
import toast from 'react-hot-toast';

import { useOnboardingStore } from '../../store/onboardingStore';
import { SectionCard, SurfaceCard } from '../primitives';
import { cn } from '../../lib/cn';
import { searchUniversities } from '../../lib/educationCatalog';
import { UniversityLogo } from '../UniversityLogo';

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
export const getRegularGoalCount = (univs: string[]) => univs.filter(u => !isSpecialUniversity(u)).length;

interface DiagnosisUnifiedSetupProps {
  onUploadStart: (file: File) => Promise<void>;
  isUploading: boolean;
  flowError: string | null;
}

export const DiagnosisUnifiedSetup: React.FC<DiagnosisUnifiedSetupProps> = ({
  onUploadStart,
  isUploading,
  flowError,
}) => {
  const { profile, setProfile, submitProfile, submitGoals } = useOnboardingStore();
  
  const [major1, setMajor1] = useState('');
  const [major2, setMajor2] = useState('');
  const [major3, setMajor3] = useState('');
  
  const [univInput, setUnivInput] = useState('');
  const [selectedUnivs, setSelectedUnivs] = useState<string[]>([]);
  
  // Hydrate from store if exists
  const { goals } = useOnboardingStore.getState();
  useEffect(() => {
    if (goals.target_major) {
      const parts = goals.target_major.split(',').map(s => s.trim().replace(/^\d순위:\s*/, ''));
      if (parts[0]) setMajor1(parts[0]);
      if (parts[1]) setMajor2(parts[1]);
      if (parts[2]) setMajor3(parts[2]);
    }
    
    const univs: string[] = [];
    if (goals.target_university) univs.push(goals.target_university);
    if (goals.interest_universities) {
      goals.interest_universities.forEach(u => {
        const clean = u.replace(/\s*\(.*?\)$/, '');
        if (clean) univs.push(clean);
      });
    }
    if (univs.length > 0) {
      setSelectedUnivs(Array.from(new Set(univs)));
    }
  }, [goals]);

  const handleAddUniv = (univ: string) => {
    if (selectedUnivs.includes(univ)) {
      toast.error('이미 추가된 대학입니다.');
      return;
    }
    
    const isSpecial = isSpecialUniversity(univ);
    const regularCount = getRegularGoalCount(selectedUnivs);
    
    if (!isSpecial && regularCount >= 6) {
      toast.error('일반 대학은 최대 6개까지만 선택할 수 있습니다. (특수대는 추가 가능)');
      return;
    }
    
    setSelectedUnivs(prev => [...prev, univ]);
    setUnivInput('');
  };

  const handleRemoveUniv = (univ: string) => {
    setSelectedUnivs(prev => prev.filter(u => u !== univ));
  };

  const handleDrop = async (acceptedFiles: File[]) => {
    const file = acceptedFiles[0];
    if (!file) return;

    if (!profile.grade || !profile.track) {
      toast.error('학년과 계열을 선택해 주세요.');
      return;
    }
    if (!major1) {
      toast.error('최소한 1지망 학과는 입력해 주세요.');
      return;
    }
    if (selectedUnivs.length === 0) {
      toast.error('목표 대학을 최소 1개 이상 선택해 주세요.');
      return;
    }

    // Prepare Profile
    const profileOk = await submitProfile();
    if (!profileOk) return;

    // Prepare Goals
    const majors = [major1, major2, major3].filter(Boolean);
    const target_major = majors.map((m, i) => `${i+1}순위: ${m}`).join(', ');
    const target_university = selectedUnivs[0];
    const interest_universities = selectedUnivs.slice(1);

    const goalsOk = await submitGoals({
      target_university,
      target_major,
      admission_type: profile.grade === 'N수생' ? '정시' : '학생부종합',
      interest_universities
    });
    if (!goalsOk) return;

    // Trigger Upload
    await onUploadStart(file);
  };

  const { getRootProps, getInputProps, isDragActive, open } = useDropzone({
    onDrop: handleDrop,
    accept: { 'application/pdf': ['.pdf'] },
    multiple: false,
    disabled: isUploading,
    noClick: true,
  });

  const univPreviewName = univInput.trim();

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -10 }}
      className="w-full"
    >
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-start">
        
        {/* Left Column: Configuration */}
        <div className="lg:col-span-5 space-y-6">
          <SectionCard title="기본 설정" description="생기부 분석에 필요한 정보를 입력합니다." className="p-6">
            
            <div className="space-y-4">
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-xs font-bold text-slate-500 mb-1 block">학년</label>
                  <select
                    value={profile.grade}
                    onChange={(e) => setProfile({ grade: e.target.value })}
                    className="w-full rounded-xl border border-slate-200 bg-slate-50 p-2.5 text-sm font-bold outline-none focus:border-indigo-600 focus:bg-white"
                  >
                    <option value="">선택</option>
                    <option value="고1">고1</option>
                    <option value="고2">고2</option>
                    <option value="고3">고3</option>
                    <option value="N수생">N수생</option>
                  </select>
                </div>
                <div>
                  <label className="text-xs font-bold text-slate-500 mb-1 block">계열</label>
                  <select
                    value={profile.track}
                    onChange={(e) => setProfile({ track: e.target.value })}
                    className="w-full rounded-xl border border-slate-200 bg-slate-50 p-2.5 text-sm font-bold outline-none focus:border-indigo-600 focus:bg-white"
                  >
                    <option value="">선택</option>
                    <option value="인문">인문</option>
                    <option value="자연">자연</option>
                    <option value="예체능">예체능</option>
                    <option value="기타">기타</option>
                  </select>
                </div>
              </div>

              <div>
                <label className="text-xs font-bold text-slate-500 mb-1 block">희망 학과 (1~3지망)</label>
                <div className="flex flex-col gap-2">
                  <input placeholder="1지망 (예: 컴퓨터공학과)" value={major1} onChange={e => setMajor1(e.target.value)} className="w-full rounded-xl border border-slate-200 bg-slate-50 p-2.5 text-sm font-bold outline-none focus:border-indigo-600 focus:bg-white" />
                  <input placeholder="2지망 (선택)" value={major2} onChange={e => setMajor2(e.target.value)} className="w-full rounded-xl border border-slate-200 bg-slate-50 p-2.5 text-sm font-bold outline-none focus:border-indigo-600 focus:bg-white" />
                  <input placeholder="3지망 (선택)" value={major3} onChange={e => setMajor3(e.target.value)} className="w-full rounded-xl border border-slate-200 bg-slate-50 p-2.5 text-sm font-bold outline-none focus:border-indigo-600 focus:bg-white" />
                </div>
              </div>

              <div>
                <div className="flex justify-between items-end mb-1">
                  <label className="text-xs font-bold text-slate-500 block">목표 대학 (일반 6개 + 특수대)</label>
                  <span className="text-[10px] font-bold text-indigo-600 bg-indigo-50 px-2 py-0.5 rounded-full">
                    일반대 {getRegularGoalCount(selectedUnivs)}/6
                  </span>
                </div>
                <div className="relative mb-3">
                  <input
                    value={univInput}
                    onChange={(e) => setUnivInput(e.target.value)}
                    placeholder="대학명 검색 (예: 서울대학교)"
                    className="w-full rounded-xl border border-slate-200 bg-slate-50 p-2.5 pr-10 text-sm font-bold outline-none focus:border-indigo-600 focus:bg-white"
                  />
                  {univPreviewName.length >= 2 && (
                    <UniversityLogo
                      universityName={univPreviewName}
                      className="pointer-events-none absolute right-2 top-1.5 h-6 w-6 rounded-md bg-white object-contain p-0.5 shadow-sm"
                    />
                  )}
                  {univInput && (
                    <div className="absolute left-0 right-0 top-full z-20 mt-1 max-h-48 overflow-auto rounded-xl border border-slate-200 bg-white p-1 shadow-xl">
                      {searchUniversities(univInput, { excludeNames: selectedUnivs }).map((suggestion) => (
                        <button
                          key={suggestion.label}
                          type="button"
                          onClick={() => handleAddUniv(suggestion.label)}
                          className="flex w-full items-center gap-2 rounded-lg px-3 py-2 text-left hover:bg-indigo-50"
                        >
                          <UniversityLogo universityName={suggestion.label} className="h-5 w-5 rounded bg-white object-contain" />
                          <span className="text-sm font-bold text-slate-700">{suggestion.label}</span>
                          {isSpecialUniversity(suggestion.label) && (
                            <span className="ml-auto text-[10px] font-bold text-purple-500 bg-purple-50 px-1.5 py-0.5 rounded-full">특수대</span>
                          )}
                        </button>
                      ))}
                    </div>
                  )}
                </div>

                <div className="flex flex-wrap gap-2">
                  <AnimatePresence>
                    {selectedUnivs.map((univ, idx) => (
                      <motion.div
                        key={univ}
                        initial={{ opacity: 0, scale: 0.8 }}
                        animate={{ opacity: 1, scale: 1 }}
                        exit={{ opacity: 0, scale: 0.8 }}
                        className={cn(
                          "flex items-center gap-1.5 rounded-lg px-2.5 py-1.5 text-xs font-bold shadow-sm border",
                          isSpecialUniversity(univ) 
                            ? "border-purple-100 bg-purple-50 text-purple-700"
                            : idx === 0 
                              ? "border-indigo-200 bg-indigo-50 text-indigo-700" 
                              : "border-slate-200 bg-white text-slate-700"
                        )}
                      >
                        <UniversityLogo universityName={univ} className="h-4 w-4 rounded-sm bg-white object-contain" />
                        <span>{univ}</span>
                        <button onClick={() => handleRemoveUniv(univ)} className="ml-1 text-slate-400 hover:text-red-500">
                          <Trash2 size={12} />
                        </button>
                      </motion.div>
                    ))}
                  </AnimatePresence>
                  {selectedUnivs.length === 0 && (
                    <span className="text-xs text-slate-400 italic">선택된 대학이 없습니다.</span>
                  )}
                </div>
              </div>

            </div>
          </SectionCard>
        </div>

        {/* Right Column: Upload */}
        <div className="lg:col-span-7">
          <div
            {...getRootProps({ onClick: open })}
            className={cn(
              'relative flex h-full min-h-[400px] cursor-pointer flex-col items-center justify-center overflow-hidden rounded-[2.5rem] border-2 border-dashed transition-all duration-300',
              isDragActive
                ? 'border-indigo-500 bg-indigo-50/50 scale-[0.99]'
                : 'border-slate-200 bg-white hover:border-indigo-400 hover:shadow-xl hover:shadow-indigo-100/50',
              isUploading && 'pointer-events-none opacity-60'
            )}
          >
            <input {...getInputProps()} />
            
            <div className="relative mb-8">
              <div className="absolute inset-0 animate-ping rounded-[2rem] bg-indigo-200 opacity-20" />
              <div className="relative flex h-24 w-24 items-center justify-center rounded-[2rem] bg-indigo-600 text-white shadow-xl shadow-indigo-200">
                {isUploading ? (
                  <Loader2 size={40} className="animate-spin" />
                ) : (
                  <FileUp size={40} strokeWidth={1.5} />
                )}
              </div>
            </div>

            <h2 className="text-2xl font-black text-slate-900 mb-4 text-center">
              {isUploading ? '분석 준비 중...' : isDragActive ? '파일을 여기에 놓으세요' : 'PDF 파일을 끌어오거나 클릭하여 업로드'}
            </h2>
            
            <div className="flex flex-wrap justify-center gap-3 mb-8">
               <span className="inline-flex items-center gap-1.5 rounded-full bg-slate-100 px-4 py-1.5 text-sm font-bold text-slate-600">
                <Settings2 size={14} />
                최대 50MB
               </span>
               <span className="inline-flex items-center gap-1.5 rounded-full bg-slate-100 px-4 py-1.5 text-sm font-bold text-slate-600">
                <FileUp size={14} />
                PDF 형식
               </span>
            </div>

            {flowError && (
              <div className="mt-4 max-w-sm w-full text-center p-3 bg-red-50 text-red-600 rounded-xl font-bold text-sm">
                {flowError}
              </div>
            )}
            
            {!isUploading && (
               <div className="text-slate-400 text-sm font-medium mt-4">
                 좌측의 정보를 모두 입력한 후 파일을 업로드해주세요.
               </div>
            )}
          </div>
        </div>

      </div>
    </motion.div>
  );
};
