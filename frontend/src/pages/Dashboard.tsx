import React, { useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { motion } from 'motion/react';
import {
  ArrowRight,
  BarChart3,
  Compass,
  PlayCircle,
  School,
  Settings2,
  Sparkles,
  Target,
  Zap,
  ChevronRight,
  ChevronLeft
} from 'lucide-react';
import toast from 'react-hot-toast';
import { DiagnosisModal } from '../components/DiagnosisModal';
import { OnboardingModal } from '../components/OnboardingModal';
import { useAuth } from '../contexts/AuthContext';
import { api } from '../lib/api';
import { type QuestStartPayload, saveQuestStart } from '../lib/questStart';

const DIAGNOSIS_STORAGE_KEY = 'folia_last_diagnosis';
const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

interface UserStats {
  report_count: number;
  level: string;
  completion_rate: number;
}

interface UserProfile {
  id: string;
  email: string | null;
  name: string | null;
  target_university: string | null;
  target_major: string | null;
  interest_universities: string[] | null;
}

interface DiagnosisResultPayload {
  headline: string;
  strengths: string[];
  gaps: string[];
  risk_level: 'safe' | 'warning' | 'danger';
  recommended_focus: string;
}

interface StoredDiagnosis {
  major: string;
  projectId?: string;
  savedAt: string;
  diagnosis: DiagnosisResultPayload;
}

interface BlueprintQuest {
  id: string;
  subject: string;
  title: string;
  summary: string;
  difficulty: string;
  why_this_matters: string;
  expected_record_impact: string;
  recommended_output_type: string;
  status: string;
}

interface BlueprintGroup {
  name: string;
  quests: BlueprintQuest[];
}

interface CurrentBlueprintResponse {
  id: string;
  project_id: string;
  project_title: string;
  target_major: string | null;
  headline: string;
  recommended_focus: string;
  semester_priority_message: string;
  priority_quests: BlueprintQuest[];
  subject_groups: BlueprintGroup[];
  activity_groups: BlueprintGroup[];
  expected_record_effects: string[];
  created_at: string;
}

function readStoredDiagnosis(): StoredDiagnosis | null {
  try {
    const raw = localStorage.getItem(DIAGNOSIS_STORAGE_KEY);
    if (!raw) return null;
    return JSON.parse(raw) as StoredDiagnosis;
  } catch {
    return null;
  }
}

function difficultyTone(difficulty: string) {
  switch (difficulty) {
    case 'high': return 'bg-red-100 text-red-700 border-red-200';
    case 'medium': return 'bg-amber-100 text-amber-700 border-amber-200';
    default: return 'bg-emerald-100 text-emerald-700 border-emerald-200';
  }
}

function statusTone(status: string) {
  switch (status) {
    case 'IN_PROGRESS': return 'bg-blue-100 text-blue-700 border-blue-200';
    case 'COMPLETED': return 'bg-emerald-100 text-emerald-700 border-emerald-200';
    default: return 'bg-slate-100 text-slate-600 border-slate-200';
  }
}

function QuestCard({ quest, onStart, isStarting }: { quest: BlueprintQuest; onStart: (quest: BlueprintQuest) => void; isStarting: boolean; }) {
  return (
    <div className="flex h-full flex-col rounded-[28px] border border-slate-200 bg-white p-6 shadow-sm transition-all hover:shadow-md">
      <div className="mb-4 flex flex-wrap items-center gap-2">
        <span className="rounded-full border border-slate-200 bg-slate-50 px-3 py-1 text-xs font-black text-slate-600">{quest.subject}</span>
        <span className={`rounded-full border px-3 py-1 text-xs font-black ${difficultyTone(quest.difficulty)}`}>
          {quest.difficulty === 'high' ? '상' : quest.difficulty === 'medium' ? '중' : '하'}
        </span>
        <span className={`rounded-full border px-3 py-1 text-xs font-black ${statusTone(quest.status)}`}>
          {quest.status === 'IN_PROGRESS' ? '진행 중' : quest.status === 'COMPLETED' ? '완료' : '대기'}
        </span>
      </div>
      <h3 className="mb-3 break-keep text-xl font-extrabold leading-snug text-slate-800">{quest.title}</h3>
      <p className="mb-4 text-sm font-medium leading-relaxed text-slate-600">{quest.summary}</p>
      <div className="mb-4 rounded-2xl border border-blue-100 bg-blue-50 p-4">
        <p className="mb-1 text-xs font-black uppercase tracking-[0.18em] text-blue-500">배경 및 필요성</p>
        <p className="text-sm font-medium leading-relaxed text-blue-900">{quest.why_this_matters}</p>
      </div>
      <div className="mb-4 rounded-2xl border border-emerald-100 bg-emerald-50 p-4">
        <p className="mb-1 text-xs font-black uppercase tracking-[0.18em] text-emerald-600">예상 생기부 반영 효과</p>
        <p className="text-sm font-medium leading-relaxed text-emerald-900">{quest.expected_record_impact}</p>
      </div>
      <div className="mt-auto flex items-center justify-between gap-4">
        <div>
          <p className="text-xs font-black uppercase tracking-[0.18em] text-slate-400">추천 결과물 형태</p>
          <p className="text-sm font-bold text-slate-700">{quest.recommended_output_type}</p>
        </div>
        <button type="button" onClick={() => onStart(quest)} disabled={isStarting} className="inline-flex items-center gap-2 rounded-2xl bg-slate-900 px-4 py-3 text-sm font-black text-white transition-colors hover:bg-slate-800 disabled:opacity-60">
          {isStarting ? '시작 중...' : '퀘스트 시작'} <PlayCircle size={16} />
        </button>
      </div>
    </div>
  );
}

export function Dashboard() {
  const navigate = useNavigate();
  const { user, isGuestSession } = useAuth();
  const [isDiagnosisOpen, setIsDiagnosisOpen] = useState(false);
  const [isOnboardingOpen, setIsOnboardingOpen] = useState(false);
  const [isSavingProfile, setIsSavingProfile] = useState(false);
  const [isLoadingBlueprint, setIsLoadingBlueprint] = useState(false);
  const [startingQuestId, setStartingQuestId] = useState<string | null>(null);
  const [stats, setStats] = useState<UserStats>({ report_count: 0, level: '로딩 중', completion_rate: 0 });
  const [profile, setProfile] = useState<UserProfile | null>(null);
  const [storedDiagnosis, setStoredDiagnosis] = useState<StoredDiagnosis | null>(null);
  const [blueprint, setBlueprint] = useState<CurrentBlueprintResponse | null>(null);
  const [blueprintError, setBlueprintError] = useState<string | null>(null);

  useEffect(() => { setStoredDiagnosis(readStoredDiagnosis()); }, []);

  useEffect(() => {
    if (!user && !isGuestSession) return;
    api.get<UserStats>('/api/v1/projects/user/stats').then(setStats).catch(() => setStats({ report_count: 0, level: isGuestSession ? '게스트' : '신규', completion_rate: 0 }));
    api.get<UserProfile>('/api/v1/users/me').then(data => {
      setProfile(data);
      if (!data.target_university || !data.target_major) setIsOnboardingOpen(true);
    }).catch(console.error);
  }, [user, isGuestSession]);

  useEffect(() => {
    if (!user && !isGuestSession) return;
    setIsLoadingBlueprint(true);
    setBlueprintError(null);
    api.get<CurrentBlueprintResponse>('/api/v1/blueprints/current', { params: storedDiagnosis?.projectId ? { project_id: storedDiagnosis.projectId } : undefined })
      .then(setBlueprint)
      .catch(error => {
        const normalized = error as any;
        if (normalized.response?.status !== 404) setBlueprintError(normalized.response?.data?.detail || '데이터를 불러오지 못했습니다.');
        setBlueprint(null);
      }).finally(() => setIsLoadingBlueprint(false));
  }, [user, isGuestSession, storedDiagnosis?.projectId]);

  const handleSaveTargets = async (payload: { targetUniversity: string; targetMajor: string; interestUniversities: string[]; }) => {
    setIsSavingProfile(true);
    const loadingId = toast.loading('목표 정보를 저장하고 있습니다...');
    try {
      const data = await api.patch<UserProfile>('/api/v1/users/me/targets', {
        target_university: payload.targetUniversity,
        target_major: payload.targetMajor,
        interest_universities: payload.interestUniversities,
      });
      setProfile(data);
      setIsOnboardingOpen(false);
      toast.success('목표 대학과 전공을 저장했습니다.', { id: loadingId });
    } catch (error) {
      toast.error('저장에 실패했습니다.', { id: loadingId });
    } finally { setIsSavingProfile(false); }
  };

  const handleStartQuest = async (quest: BlueprintQuest) => {
    setStartingQuestId(quest.id);
    const loadingId = toast.loading('퀘스트를 시작합니다...');
    try {
      const payload = await api.post<QuestStartPayload>(`/api/v1/quests/${quest.id}/start`);
      saveQuestStart(payload);
      navigate(`/workshop/${payload.project_id}?major=${encodeURIComponent(payload.target_major || quest.subject)}`, { state: { questStart: payload } });
      toast.success('워크숍 준비 완료', { id: loadingId });
    } catch (error) {
      toast.error('시작 실패', { id: loadingId });
    } finally { setStartingQuestId(null); }
  };

  const allGoals = useMemo(() => {
    const list: { university: string; major: string }[] = [];
    if (profile?.target_university) {
      list.push({ university: profile.target_university, major: profile.target_major || '' });
    }
    if (Array.isArray(profile?.interest_universities)) {
      profile.interest_universities.forEach(i => {
        if (typeof i !== 'string') return;
        const match = i.match(/^(.+)\s\((.+)\)$/);
        if (match) list.push({ university: match[1], major: match[2] });
        else list.push({ university: i, major: '' });
      });
    }
    return list;
  }, [profile]);

  return (
    <div className="mx-auto max-w-6xl px-4 pb-16 sm:px-6 lg:px-8">
      {/* Header / Hero */}
      <section className="relative overflow-hidden rounded-[40px] border border-slate-200 bg-white p-8 shadow-sm sm:p-12 mb-10">
        <div className="absolute right-0 top-0 h-64 w-64 rounded-full bg-blue-100/40 blur-3xl opacity-50" />
        <div className="relative z-10 grid lg:grid-cols-[1.2fr_0.8fr] gap-12 items-center">
          <div>
            <div className="mb-6 inline-flex items-center gap-2 rounded-full border border-blue-200 bg-blue-50 px-4 py-2 text-[11px] font-black uppercase tracking-[0.2em] text-blue-600">
              <Sparkles size={14} /> 탐구 플랜 대시보드
            </div>
            <h1 className="mb-6 break-keep text-4xl font-black leading-tight tracking-tight text-slate-900 sm:text-5xl">
              가고 싶은 대학,<br/><span className="text-blue-600">선명한 합격 로드맵</span>으로 바꿉니다.
            </h1>
            <p className="mb-8 max-w-xl break-keep text-lg font-medium text-slate-500 leading-relaxed">
              Uni Folia는 단순한 성적 진단을 넘어, 목표 대학의 인재상에 맞춘 <span className="font-black text-slate-900">구체적 탐구 주제와 생기부 반영 전략</span>을 제안합니다.
            </p>
            <div className="flex flex-wrap gap-4">
              <button onClick={() => setIsDiagnosisOpen(true)} className="inline-flex items-center justify-center gap-2 rounded-2xl bg-slate-900 px-8 py-4 text-base font-black text-white transition-all hover:bg-black hover:scale-[1.02]">
                진단 시작하기 <ArrowRight size={20} />
              </button>
              <button onClick={() => document.getElementById('research-plan')?.scrollIntoView({ behavior: 'smooth' })} className="inline-flex items-center justify-center gap-2 rounded-2xl border border-slate-200 bg-white px-8 py-4 text-base font-black text-slate-700 hover:bg-slate-50">
                탐구 플랜 보기 <Zap size={18} />
              </button>
            </div>
          </div>

          <div className="space-y-6">
            {/* My Universities Motivation Card */}
            <div className="rounded-[32px] border border-slate-200 bg-slate-50/50 p-6 shadow-inner">
              <div className="mb-4 flex items-center justify-between">
                <p className="text-[11px] font-black uppercase tracking-[0.2em] text-slate-400">나의 목표 대학 (6)</p>
                <button onClick={() => setIsOnboardingOpen(true)} className="p-2 text-slate-400 hover:text-blue-600 transition-colors"><Settings2 size={18} /></button>
              </div>
              <div className="grid grid-cols-3 gap-3">
                {allGoals.length > 0 ? allGoals.map((g, idx) => (
                  <div key={idx} className="flex flex-col items-center p-3 bg-white rounded-2xl border border-slate-100 shadow-sm transition-all hover:border-blue-200">
                    <img src={`${API_BASE_URL}/api/v1/assets/univ-logo?name=${encodeURIComponent(g.university)}`} 
                         className="w-12 h-12 object-contain mb-2" alt="Logo" 
                         onError={(e) => { e.currentTarget.style.display = 'none'; e.currentTarget.nextElementSibling?.classList.remove('hidden'); }} />
                    <div className="hidden w-12 h-12 rounded-xl bg-slate-100 flex items-center justify-center text-slate-400"><School size={24}/></div>
                    <p className="text-[10px] font-black text-slate-800 text-center truncate w-full">{g.university}</p>
                    <p className="text-[8px] font-bold text-slate-400 text-center truncate w-full">{g.major || '전공'}</p>
                  </div>
                )) : (
                  <div className="col-span-3 py-10 flex flex-col items-center justify-center text-slate-300">
                    <School size={32} className="mb-2 opacity-20"/>
                    <p className="text-xs font-bold">대학을 설정해주세요</p>
                  </div>
                )}
              </div>
            </div>

            {/* Completion Stats Card */}
            <div className="rounded-[32px] border border-slate-200 bg-slate-900 p-6 text-white shadow-lg">
              <div className="mb-4 flex items-center justify-between">
                <p className="text-[11px] font-black uppercase tracking-[0.2em] text-slate-400">탐구 진행 정도</p>
                <span className="text-xs font-black bg-blue-600 px-2 py-0.5 rounded-full">{stats.level}</span>
              </div>
              <div className="flex items-end justify-between mb-2">
                <p className="text-4xl font-black">{stats.completion_rate}%</p>
                <p className="text-xs font-bold text-slate-400">완료 보고서 {stats.report_count}개</p>
              </div>
              <div className="h-3 rounded-full bg-slate-800 overflow-hidden">
                <div style={{ width: `${stats.completion_rate}%` }} className="h-full bg-blue-500 rounded-full" />
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Main Content Area */}
      <section id="research-plan" className="mt-16">
        <div className="mb-10">
          <p className="mb-2 text-xs font-black uppercase tracking-[0.24em] text-blue-600">ACTION PLAN</p>
          <h2 className="text-4xl font-black text-slate-900">이번 학기 탐구 플랜</h2>
          <p className="mt-3 max-w-3xl text-lg font-medium text-slate-500 leading-relaxed">
            진단 결과를 바탕으로 설계된 맞춤형 퀘스트입니다. 우선순위 상단에 있는 과제부터 해결하면 생기부의 빈 구간이 효율적으로 채워집니다.
          </p>
        </div>

        {isLoadingBlueprint ? (
           <div className="flex h-96 items-center justify-center rounded-[40px] bg-slate-50 border border-dashed border-slate-200">
             <div className="flex flex-col items-center gap-3">
                <div className="w-10 h-10 border-4 border-blue-600 border-t-transparent rounded-full animate-spin" />
                <p className="text-sm font-black text-slate-400">전략을 세우고 있습니다...</p>
             </div>
           </div>
        ) : blueprint ? (
          <div className="space-y-12">
            {/* Impact Highlights */}
            <div className="grid lg:grid-cols-2 gap-8">
              <div className="rounded-[36px] bg-white border border-slate-200 p-10 shadow-sm relative overflow-hidden">
                <div className="absolute right-0 top-0 p-6 opacity-5"><Zap size={120}/></div>
                <div className="mb-6 inline-flex items-center gap-2 rounded-full border border-blue-100 bg-blue-50 px-4 py-2 text-xs font-black text-blue-600">전략 요약</div>
                <h3 className="text-2xl font-black text-slate-900 leading-snug">{blueprint.headline}</h3>
                <p className="mt-4 text-base font-medium text-slate-600 leading-relaxed">{blueprint.recommended_focus}</p>
                <div className="mt-8 p-6 bg-slate-50 rounded-[24px] border border-slate-100">
                   <p className="text-[11px] font-black text-slate-400 uppercase mb-2">이번 학기 핵심 우선순위</p>
                   <p className="text-base font-black text-slate-800">{blueprint.semester_priority_message}</p>
                </div>
              </div>

              <div className="rounded-[36px] bg-slate-900 p-10 text-white relative overflow-hidden">
                <div className="mb-6 inline-flex items-center gap-2 rounded-full bg-white/10 px-4 py-2 text-xs font-black text-emerald-400 border border-emerald-400/20">생기부 기대 효과</div>
                <div className="space-y-4">
                  {blueprint.expected_record_effects.map((e, i) => (
                    <div key={i} className="flex gap-4 items-start p-4 bg-white/5 rounded-2xl border border-white/10">
                      <div className="mt-1 flex-shrink-0 w-1.5 h-1.5 rounded-full bg-emerald-400" />
                      <p className="text-sm font-medium leading-relaxed text-slate-300">{e}</p>
                    </div>
                  ))}
                </div>
              </div>
            </div>

            {/* Quests Section */}
            <div className="space-y-8">
              <div className="flex items-end justify-between">
                <h3 className="text-2xl font-black text-slate-900">우선 보완 퀘스트</h3>
              </div>
              <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-6">
                {blueprint.priority_quests.map(q => (
                  <QuestCard key={q.id} quest={q} onStart={handleStartQuest} isStarting={startingQuestId === q.id} />
                ))}
              </div>
            </div>

            {/* Detailed Subject Groups */}
            <div className="rounded-[40px] bg-slate-50 p-10 border border-slate-200">
               <h3 className="text-2xl font-black text-slate-900 mb-8">모든 추천 퀘스트</h3>
               <div className="space-y-10">
                 {blueprint.subject_groups.map(group => (
                   <div key={group.name} className="space-y-6">
                      <div className="flex items-center gap-3">
                         <span className="h-0.5 w-6 bg-blue-500 rounded-full" />
                         <span className="text-sm font-black text-slate-800">{group.name}</span>
                      </div>
                      <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-6">
                        {group.quests.map(q => <QuestCard key={q.id} quest={q} onStart={handleStartQuest} isStarting={startingQuestId === q.id} />)}
                      </div>
                   </div>
                 ))}
               </div>
            </div>
          </div>
        ) : (
          <div className="rounded-[40px] bg-white border border-dashed border-slate-300 p-16 text-center">
            <div className="mx-auto mb-6 flex h-20 w-20 items-center justify-center rounded-[28px] bg-slate-100 text-slate-400">
              <Target size={36} />
            </div>
            <h3 className="text-3xl font-black text-slate-900">아직 탐구 플랜이 생성되지 않았습니다.</h3>
            <p className="mx-auto mt-4 max-w-xl text-lg font-medium text-slate-500 leading-relaxed break-keep">
              학생 생활 기록부를 진단하면 목표 대학과 전공에 맞춘 이번 학기 최적의 탐구 경로를 만들어 드립니다.
            </p>
            {blueprintError && <p className="mt-4 text-red-500 font-bold">{blueprintError}</p>}
            <button onClick={() => setIsDiagnosisOpen(true)} className="mt-8 inline-flex items-center gap-2 rounded-2xl bg-blue-600 px-8 py-4 text-base font-black text-white hover:bg-blue-700 hover:scale-105 transition-all">
              진단하고 탐구 플랜 만들기 <ArrowRight size={20} />
            </button>
          </div>
        )}
      </section>

      <DiagnosisModal isOpen={isDiagnosisOpen} onClose={() => { setIsDiagnosisOpen(false); setStoredDiagnosis(readStoredDiagnosis()); }} />
      <OnboardingModal
        isOpen={isOnboardingOpen}
        onClose={() => setIsOnboardingOpen(false)}
        initialUniversity={profile?.target_university}
        initialMajor={profile?.target_major}
        initialInterests={profile?.interest_universities || []}
        isSubmitting={isSavingProfile}
        onSubmit={handleSaveTargets}
      />
    </div>
  );
}
