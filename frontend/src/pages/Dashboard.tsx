import React, { useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { ArrowRight, CheckCircle2, ChevronDown, ChevronUp, Flag, PlayCircle, School, Settings2, Sparkles, Target, TrendingUp, Zap } from 'lucide-react';
import toast from 'react-hot-toast';
import {
  type BlueprintQuest,
  type CurrentBlueprintResponse,
  type OnboardingGoalsUpdateResponse,
  type UserProfile,
  type UserStats,
  type UserTargetsUpdateRequest,
  type UserTargetsUpdateResponse,
} from '@shared-contracts';
import { UniversityLogo } from '../components/UniversityLogo';
import { useAuth } from '../contexts/AuthContext';
import { api } from '../lib/api';
import { DIAGNOSIS_STORAGE_KEY, type StoredDiagnosis } from '../lib/diagnosis';
import { isGuestSessionActive, readGuestProfile, updateGuestTargets } from '../lib/guestProfile';
import { buildRankedGoals } from '../lib/rankedGoals';
import { updateLocalAuthTargets } from '../lib/localAuthProfile';
import { type QuestStartPayload, saveQuestStart } from '../lib/questStart';
import { useAuthStore } from '../store/authStore';
import {
  EmptyState,
  PrimaryButton,
  SecondaryButton,
  SectionCard,
  StatusBadge,
  SurfaceCard,
} from '../components/primitives';

type WorkflowStatus = 'done' | 'active' | 'pending';

interface WorkflowStep {
  key: string;
  title: string;
  description: string;
  status: WorkflowStatus;
}

interface NextAction {
  title: string;
  description: string;
  primaryLabel: string;
  onPrimary: () => void;
  secondaryLabel?: string;
  onSecondary?: () => void;
}

type DashboardPanel = 'next' | 'status' | 'plan';

function readStoredDiagnosis(): StoredDiagnosis | null {
  try {
    const raw = localStorage.getItem(DIAGNOSIS_STORAGE_KEY);
    if (!raw) return null;
    return JSON.parse(raw);
  } catch (e) {
    console.error('Failed to parse diagnosis from storage:', e);
    return null;
  }
}

const riskVariant = (risk: string): any => {
  switch (risk) {
    case 'danger': return 'danger';
    case 'warning': return 'warning';
    case 'safe': return 'success';
    default: return 'neutral';
  }
};

function toCompactDiagnosisSummary(headline?: string | null): string {
  const cleaned = (headline || '').replace(/\s+/g, ' ').trim();
  if (!cleaned) return 'AI 진단 실행';
  if (cleaned.includes('AI diagnosis fallback applied after')) {
    return '상세 진단 요약은 진단 페이지에서 확인할 수 있어요.';
  }
  if (cleaned.length > 120) {
    return `${cleaned.slice(0, 96)}...`;
  }
  return cleaned;
}

const levelSummary = (level: string) => {
  switch (level) {
    case 'Diamond': return { label: '다이아몬드', color: 'text-cyan-600', bg: 'bg-cyan-50' };
    case 'Platinum': return { label: '플래티넘', color: 'text-indigo-600', bg: 'bg-indigo-50' };
    case 'Gold': return { label: '골드', color: 'text-amber-600', bg: 'bg-amber-50' };
    case 'Silver': return { label: '실버', color: 'text-slate-500', bg: 'bg-slate-50' };
    default: return { label: level || '언랭크', color: 'text-slate-400', bg: 'bg-slate-50' };
  }
};

const QuestCard = ({ quest, onStart, isStarting }: { quest: BlueprintQuest; onStart: (q: BlueprintQuest) => void; isStarting: boolean }) => {
  const diffLabel = quest.difficulty === 'high' ? '상' : quest.difficulty === 'medium' ? '중' : '하';
  const diffVariant: any = quest.difficulty === 'high' ? 'danger' : quest.difficulty === 'medium' ? 'warning' : 'success';

  return (
    <SurfaceCard className="group relative flex flex-col justify-between overflow-hidden border-[#d8e6ff] bg-white/90 p-6 shadow-[0_14px_30px_rgba(24,66,170,0.11)] transition-all hover:-translate-y-0.5 hover:shadow-[0_20px_38px_rgba(24,66,170,0.16)] active:scale-[0.98]">
      <div className="space-y-4">
        <div className="flex items-start justify-between">
          <StatusBadge status={diffVariant} className="font-black px-2.5 py-0.5 text-[10px]">난이도 {diffLabel}</StatusBadge>
          <div className="rounded-xl bg-[#ecf4ff] p-2 text-[#2350b8] transition-colors group-hover:bg-[#1d4fff] group-hover:text-white">
            <Zap size={16} fill="currentColor" className="opacity-80" />
          </div>
        </div>
        <div>
          <h4 className="line-clamp-1 text-lg font-black tracking-tight text-slate-900">{quest.title}</h4>
          <p className="mt-2 line-clamp-2 text-sm font-medium leading-relaxed text-slate-500">{quest.summary}</p>
        </div>
      </div>
      
      <div className="mt-6 flex items-center justify-between gap-4 border-t border-[#e4edff] pt-5">
        <div className="flex flex-col">
          <span className="text-[10px] font-black uppercase tracking-wider text-slate-400">관련 과목</span>
          <span className="text-sm font-bold text-slate-700">{quest.subject}</span>
        </div>
        <button
          onClick={() => onStart(quest)}
          disabled={isStarting}
          className="inline-flex h-9 items-center gap-2 rounded-xl bg-[linear-gradient(135deg,#1d4fff_0%,#2da3ff_100%)] px-4 text-xs font-black text-white shadow-[0_8px_18px_rgba(29,79,255,0.28)] transition-all hover:-translate-y-0.5 disabled:opacity-50"
        >
          {isStarting ? '준비 중...' : '시작하기'}
          {!isStarting && <PlayCircle size={14} />}
        </button>
      </div>
    </SurfaceCard>
  );
};

export default function Dashboard() {
  const navigate = useNavigate();
  const { user, isGuestSession } = useAuth();
  const authStoreUser = useAuthStore(state => state.user);
  const setAuthUser = useAuthStore(state => state.setUser);

  const [isSavingProfile, setIsSavingProfile] = useState(false);
  const [isLoadingBlueprint, setIsLoadingBlueprint] = useState(false);
  const [startingQuestId, setStartingQuestId] = useState<string | null>(null);
  const [stats, setStats] = useState<UserStats>({ report_count: 0, level: '불러오는 중', completion_rate: 0 });
  const [profile, setProfile] = useState<UserProfile | null>(authStoreUser);
  const [storedDiagnosis, setStoredDiagnosis] = useState<StoredDiagnosis | null>(null);
  const [blueprint, setBlueprint] = useState<CurrentBlueprintResponse | null>(null);
  const [blueprintError, setBlueprintError] = useState<string | null>(null);
  const [openSubjectGroups, setOpenSubjectGroups] = useState<Record<string, boolean>>({});
  const localAuthFallbackActive = Boolean(authStoreUser?.id?.startsWith('local-auth-'));

  useEffect(() => {
    setStoredDiagnosis(readStoredDiagnosis());
  }, []);

  useEffect(() => {
    if (authStoreUser) {
      setProfile(authStoreUser);
    }
  }, [authStoreUser]);

  useEffect(() => {
    if (!blueprint?.subject_groups.length) {
      setOpenSubjectGroups({});
      return;
    }

    setOpenSubjectGroups(previous => {
      const nextState: Record<string, boolean> = {};
      blueprint.subject_groups.forEach((group, index) => {
        nextState[group.name] = previous[group.name] ?? index === 0;
      });
      return nextState;
    });
  }, [blueprint]);

  useEffect(() => {
    if (!user && !isGuestSession) return;
    if (isGuestSessionActive()) {
      const guestProfile = readGuestProfile();
      setStats({
        report_count: 0,
        level: '게스트',
        completion_rate: guestProfile?.target_university && guestProfile?.target_major ? 25 : 0,
      });
      setProfile(guestProfile);
      if (!guestProfile?.target_university || !guestProfile?.target_major) {
        // Redirect to diagnosis is handled by App.tsx ProtectedRoute, but for manual triggers:
        // setIsOnboardingOpen(true); -> Managed via nextAction button
      }
      return;
    }

    if (localAuthFallbackActive && authStoreUser) {
      const hasTargets = Boolean(authStoreUser.target_university && authStoreUser.target_major);
      setStats({
        report_count: 0,
        level: '오프라인',
        completion_rate: hasTargets ? 25 : 0,
      });
      setProfile(authStoreUser);
      if (!hasTargets) {
        // Handled by ProtectedRoute mostly
      }
      return;
    }

    api
      .get<UserStats>('/api/v1/projects/user/stats')
      .then(setStats)
      .catch(() =>
        setStats({
          report_count: 0,
          level: isGuestSession ? '게스트' : '초기',
          completion_rate: 0,
        }),
      );

    api
      .get<UserProfile>('/api/v1/users/me')
      .then(data => {
        setProfile(data);
        if (!data.target_university || !data.target_major) {
           // Handled by Guide
        }
      })
      .catch(error => {
        console.error(error);
        if (isGuestSessionActive()) {
          const guestProfile = readGuestProfile();
          if (guestProfile) {
            setProfile(guestProfile);
            if (!guestProfile.target_university || !guestProfile.target_major) {
               // Handled by Guide
            }
            return;
          }
        }
        if (authStoreUser) {
          setProfile(authStoreUser);
          if (!authStoreUser.target_university || !authStoreUser.target_major) {
             // Handled by Guide
          }
          return;
        }
        setProfile(null);
        if (isGuestSession) {
           // Handled by Guide
        }
      });
  }, [user, isGuestSession, localAuthFallbackActive, authStoreUser]);

  useEffect(() => {
    if (!user && !isGuestSession) return;
    if (isGuestSessionActive() || localAuthFallbackActive) {
      setBlueprint(null);
      setBlueprintError(isGuestSessionActive() ? '회원가입 후 액션 플랜을 시작할 수 있습니다.' : '백엔드 인증을 연결하면 액션 플랜이 표시됩니다.');
      setIsLoadingBlueprint(false);
      return;
    }

    setIsLoadingBlueprint(true);
    setBlueprintError(null);

    api
      .get<CurrentBlueprintResponse>('/api/v1/blueprints/current', {
        params: storedDiagnosis?.projectId ? { project_id: storedDiagnosis.projectId } : undefined,
      })
      .then(setBlueprint)
      .catch(error => {
        const normalized = error as { response?: { status?: number; data?: { detail?: string } } };
        if (normalized.response?.status !== 404) {
          setBlueprintError(normalized.response?.data?.detail || '액션 플랜 데이터를 불러오지 못했습니다.');
        }
        setBlueprint(null);
      })
      .finally(() => setIsLoadingBlueprint(false));
  }, [user, isGuestSession, storedDiagnosis?.projectId, localAuthFallbackActive]);

  // handleSaveTargets was only for OnboardingModal, removing.

  const handleStartQuest = async (quest: BlueprintQuest) => {
    setStartingQuestId(quest.id);
    const loadingId = toast.loading('퀘스트를 준비 중입니다...');

    try {
      const payload = await api.post<QuestStartPayload>(`/api/v1/quests/${quest.id}/start`);
      saveQuestStart(payload);
      navigate(`/app/workshop/${payload.project_id}?major=${encodeURIComponent(payload.target_major || quest.subject)}`, {
        state: { questStart: payload },
      });
      toast.success('퀘스트가 시작되었습니다.', { id: loadingId });
    } catch {
      toast.error('퀘스트 시작에 실패했습니다.', { id: loadingId });
    } finally {
      setStartingQuestId(null);
    }
  };

  const allGoals = useMemo(() => buildRankedGoals(profile, 6), [profile]);
  const hasPrimaryGoal = Boolean(profile?.target_university && profile?.target_major);
  const hasDiagnosis = Boolean(storedDiagnosis?.projectId);
  const hasBlueprint = Boolean(blueprint);
  const primaryQuest = blueprint?.priority_quests[0] ?? null;

  const workflowSteps = useMemo<WorkflowStep[]>(() => {
    const diagnosisSummary = hasDiagnosis
      ? toCompactDiagnosisSummary(storedDiagnosis?.diagnosis.headline)
      : 'AI 진단 실행';

    const steps: WorkflowStep[] = [
      { key: 'targets', title: '목표 설정', description: hasPrimaryGoal ? `${profile?.target_university} · ${profile?.target_major}` : '지원 대학/학과 설정', status: hasPrimaryGoal ? 'done' : 'active' },
      { key: 'record', title: '기록 업로드', description: hasDiagnosis ? '업로드 완료' : (hasPrimaryGoal ? '학생부 PDF 업로드' : '대기 중'), status: hasDiagnosis ? 'done' : (hasPrimaryGoal ? 'active' : 'pending') },
      { key: 'diagnosis', title: '진단 실행', description: diagnosisSummary, status: hasDiagnosis ? 'done' : (hasPrimaryGoal && !hasDiagnosis ? 'pending' : 'pending') },
      { key: 'workshop', title: '워크숍 실행', description: hasBlueprint ? (primaryQuest ? `우선: ${primaryQuest.title}` : '진행 가능') : '액션 플랜 대기', status: hasBlueprint ? 'active' : 'pending' },
    ];
    return steps;
  }, [hasBlueprint, hasDiagnosis, hasPrimaryGoal, primaryQuest, profile, storedDiagnosis]);

  const progressedCount = workflowSteps.filter(s => s.status === 'done').length + (workflowSteps.some(s => s.status === 'active') ? 1 : 0);
  const progressLabel = `${Math.min(progressedCount, 4)}/4 단계`;

  const nextAction = useMemo<NextAction>(() => {
    if (!hasPrimaryGoal) {
      return {
        title: '목표 대학과 학과를 설정하세요',
        description: '합격 전략의 첫 번째 단추입니다.',
        primaryLabel: '목표 설정하기',
        onPrimary: () => navigate('/app/diagnosis'),
        secondaryLabel: '진단 가이드',
        onSecondary: () => navigate('/help/student-record-pdf'),
      };
    }
    if (!hasDiagnosis) {
      return {
        title: '학생부를 업로드하고 진단을 받으세요',
        description: '현재 생기부의 강점과 약점을 AI가 분석합니다.',
        primaryLabel: '학생부 업로드',
        onPrimary: () => navigate('/app/record'),
        secondaryLabel: '진단 시작하기',
        onSecondary: () => navigate('/app/diagnosis'),
      };
    }
    if (primaryQuest) {
      return {
        title: `다음 추천 퀘스트: ${primaryQuest.title}`,
        description: '합격 확률을 높이는 가장 효율적인 액션입니다.',
        primaryLabel: '퀘스트 시작하기',
        onPrimary: () => void handleStartQuest(primaryQuest),
        secondaryLabel: '워크숍 이동',
        onSecondary: () => navigate(`/app/workshop/${storedDiagnosis?.projectId}`),
      };
    }
    return {
      title: '워크숍에서 기록을 완성하세요',
      description: '진단 결과를 바탕으로 최고의 초안을 만듭니다.',
      primaryLabel: '워크숍 열기',
      onPrimary: () => navigate(storedDiagnosis?.projectId ? `/app/workshop/${storedDiagnosis.projectId}` : '/app/workshop'),
    };
  }, [hasDiagnosis, hasPrimaryGoal, navigate, primaryQuest, storedDiagnosis]);

  const primaryGoal = allGoals[0] ?? null;

  return (
    <div className="mx-auto max-w-7xl animate-in fade-in slide-in-from-bottom-4 space-y-6 pb-20 duration-1000 sm:space-y-10">
      {/* Hero Section */}
      <div className="relative overflow-hidden rounded-[2rem] border border-[#d4e3ff] bg-[linear-gradient(135deg,#1d4fff_0%,#2d8eff_55%,#57b8ff_100%)] p-5 shadow-[0_22px_46px_rgba(29,79,255,0.22)] sm:rounded-[2.5rem] sm:p-8 md:p-12">
        <div className="absolute -right-20 -top-20 h-64 w-64 rounded-full bg-white/16 blur-3xl animate-shine-pulse" />
        <div className="absolute -bottom-20 -left-20 h-64 w-64 rounded-full bg-[#9edfff]/34 blur-3xl" />
        
        <div className="relative z-10">
          <div className="mb-4 inline-flex items-center gap-2 rounded-full border border-white/30 bg-white/16 px-3 py-1.5 backdrop-blur-md sm:px-4">
            <TrendingUp size={14} className="text-[#bff0ff]" />
            <span className="text-sm font-bold tracking-tight text-[#bff0ff]">준비율: {stats.completion_rate}%</span>
          </div>

          <div className="flex flex-col gap-5 sm:gap-8 lg:flex-row lg:items-center lg:justify-between">
            <div className="space-y-4">
              <h1 className="text-2xl font-black tracking-tight text-white sm:text-3xl md:text-5xl lg:leading-[1.15]">
                {profile?.target_university ? (
                  <>
                    <span className="text-[#bbecff]">{profile.target_university}</span> {profile.target_major} <br className="hidden sm:block" />
                    합격 플랜이 가동 중입니다
                  </>
                ) : (
                  <>
                    나만의 <span className="text-[#bbecff]">UniFoli</span> <br className="hidden sm:block" />
                    합격 전략을 만드세요
                  </>
                )}
              </h1>
              <p className="max-w-xl text-sm font-medium leading-relaxed text-blue-100/88 sm:text-lg">
                실시간 데이터와 AI가 분석한 나의 생기부 점수, <br className="hidden sm:block" />
                그리고 합격을 위한 최적의 액션 플랜을 확인하세요.
              </p>
            </div>

            <div className="flex shrink-0 flex-wrap gap-3">
              {hasPrimaryGoal && (
                <button
                  onClick={() => navigate('/app/diagnosis')}
                  className="inline-flex h-11 items-center gap-2 rounded-2xl border border-white/28 bg-white/14 px-4 text-sm font-bold text-white transition-all hover:bg-white/22 backdrop-blur-sm sm:h-12 sm:px-6 sm:text-base"
                >
                  <Settings2 size={18} />
                  목표 정보 관리
                </button>
              )}
              <button
                onClick={nextAction.onPrimary}
                className="inline-flex h-11 items-center gap-2 rounded-2xl border border-white/70 bg-white px-5 text-sm font-black text-[#1d4fff] shadow-xl shadow-[#1d4fff]/24 transition-all hover:scale-105 active:scale-95 sm:h-12 sm:px-8 sm:text-base"
              >
                {nextAction.primaryLabel}
                <ArrowRight size={18} />
              </button>
            </div>
          </div>

          <div className="mt-6 flex flex-wrap items-center gap-2 sm:mt-10">
            <StatusBadge status="active" className="border-white/28 bg-white/16 text-white backdrop-blur-md">
              {progressLabel}
            </StatusBadge>
            <StatusBadge status="neutral" className="border-white/28 bg-white/16 text-white backdrop-blur-md">
              보유 분석서 {stats.report_count}개
            </StatusBadge>
            {storedDiagnosis && (
              <StatusBadge status={riskVariant(storedDiagnosis.diagnosis.risk_level)} className="backdrop-blur-md bg-white/20 border-white/20 text-white">
                진단 리스크: {storedDiagnosis.diagnosis.risk_level === 'danger' ? '집중 보완' : storedDiagnosis.diagnosis.risk_level === 'warning' ? '주의' : '안정'}
              </StatusBadge>
            )}
          </div>
        </div>
      </div>

      {/* Target & Progress Grid */}
      <div className="grid gap-6 sm:gap-8 lg:grid-cols-3">
        {/* Target Card */}
        <SurfaceCard className="relative overflow-hidden border-[#d4e3ff] bg-white/88 p-5 shadow-[0_18px_36px_rgba(24,66,170,0.14)] sm:p-8 lg:col-span-2">
          {/* Subtle background decoration for empty state */}
          {!hasPrimaryGoal && (
            <div className="absolute -right-10 -top-10 h-40 w-40 rounded-full bg-blue-50/50 blur-3xl" />
          )}
          
          <div className="relative z-10">
            <div className="flex flex-col gap-6 lg:flex-row lg:items-center lg:justify-between">
              <div className="flex items-center gap-4 sm:gap-6">
                <div className="relative">
                  <UniversityLogo
                    universityName={primaryGoal?.university}
                    className="h-16 w-16 rounded-2xl border border-[#d8e6ff] bg-white object-contain p-2.5 shadow-[0_14px_28px_rgba(24,66,170,0.12)] sm:h-20 sm:w-20 sm:rounded-3xl sm:p-3"
                  />
                  {!hasPrimaryGoal && (
                    <div className="absolute -bottom-1 -right-1 flex h-6 w-6 items-center justify-center rounded-full bg-amber-500 text-white shadow-sm ring-2 ring-white">
                      <Zap size={12} fill="currentColor" />
                    </div>
                  )}
                </div>
                <div className="min-w-0">
                  <div className="mb-2 inline-flex items-center gap-1.5 rounded-full bg-[#eaf2ff] px-3 py-1 text-[11px] font-black tracking-widest text-[#2150b8] ring-1 ring-inset ring-[#2150b8]/12 uppercase">
                    <Flag size={10} />
                    {hasPrimaryGoal ? '핵심 목표' : '첫 걸음'}
                  </div>
                  <h2 className="truncate text-2xl font-black tracking-tight text-slate-900 sm:text-3xl">
                    {primaryGoal?.university || '목표 설정이 필요합니다'}
                  </h2>
                  <p className="mt-1 truncate text-base font-bold text-slate-500 sm:text-lg">
                    {primaryGoal?.major || '어떤 대학에서 당신의 꿈을 펼치고 싶나요?'}
                  </p>
                  {!hasPrimaryGoal && (
                    <div className="mt-4 flex flex-wrap gap-2">
                      <button 
                        onClick={() => navigate('/app/diagnosis')}
                        className="inline-flex h-9 items-center gap-2 rounded-xl bg-[#1d4fff] px-4 text-xs font-black text-white transition-all hover:bg-[#0039cb] active:scale-95"
                      >
                        지금 바로 설정하기
                        <ArrowRight size={14} />
                      </button>
                    </div>
                  )}
                </div>
              </div>

              {/* Secondary Goals or Placeholders to fill space */}
              <div className="flex flex-wrap gap-2 lg:justify-end">
                {allGoals.length > 1 ? (
                  allGoals.slice(1, 4).map((goal, index) => (
                    <div key={index} className="flex items-center gap-3 rounded-2xl border border-[#dce8ff] bg-white/95 p-3 shadow-[0_10px_22px_rgba(24,66,170,0.09)]">
                      <UniversityLogo universityName={goal.university} className="h-10 w-10 rounded-xl bg-slate-50 p-1" />
                      <div className="min-w-[120px]">
                        <p className="text-[10px] font-black text-slate-400 uppercase">차순위 {index + 1}</p>
                        <p className="truncate text-sm font-black text-slate-900">{goal.university}</p>
                      </div>
                    </div>
                  ))
                ) : (
                  // Empty placeholders to fill the grid and provide guidance
                  <>
                    <div className="flex items-center gap-3 rounded-2xl border border-dashed border-[#dce8ff] bg-slate-50/40 p-3 opacity-60 transition-colors hover:bg-slate-50">
                      <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-slate-100/80">
                        <Target size={16} className="text-slate-300" />
                      </div>
                      <div className="min-w-[120px]">
                        <p className="text-[10px] font-black text-slate-400 uppercase">차순위 목표 1</p>
                        <p className="text-xs font-bold text-slate-400">데이터가 없습니다</p>
                      </div>
                    </div>
                    {/* Hide second placeholder on small screens to avoid clutter, but keep for desktop to fill space */}
                    <div className="hidden items-center gap-3 rounded-2xl border border-dashed border-[#dce8ff] bg-slate-50/40 p-3 opacity-40 sm:flex">
                      <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-slate-100/80">
                        <Target size={16} className="text-slate-300" />
                      </div>
                      <div className="min-w-[120px]">
                        <p className="text-[10px] font-black text-slate-400 uppercase">차순위 목표 2</p>
                        <p className="text-xs font-bold text-slate-400">데이터가 없습니다</p>
                      </div>
                    </div>
                  </>
                )}
              </div>
            </div>
            
            {/* If no diagnosis but goal exists, add a hint to fill more space */}
            {hasPrimaryGoal && !hasDiagnosis && (
              <div className="mt-8 flex items-center gap-4 rounded-2xl bg-[#f8faff] p-4 text-sm font-medium text-slate-600 ring-1 ring-inset ring-blue-100/50">
                <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-blue-100 text-blue-600">
                  <Sparkles size={18} />
                </div>
                <p>
                  목표 설정이 완료되었습니다! 이제 <span className="font-black text-[#1d4fff]">학생부 PDF</span>를 업로드하여 <br className="hidden sm:block" />
                  {primaryGoal?.university} 합격 가능성 상세 진단을 받아보세요.
                </p>
              </div>
            )}
          </div>
        </SurfaceCard>

        {/* Workflow Status */}
        <SectionCard title="워크플로 진행도" className="h-full">
          <div className="space-y-4">
            {workflowSteps.map((step) => (
              <div key={step.key} className="flex gap-4 p-2">
                <div className={`mt-1 flex h-6 w-6 shrink-0 items-center justify-center rounded-full border-2 ${
                  step.status === 'done' ? 'bg-[#1d4fff] border-[#1d4fff] text-white' : 
                  step.status === 'active' ? 'border-[#1d4fff] text-[#1d4fff]' : 'border-slate-200 text-slate-200'
                }`}>
                  {step.status === 'done' ? <CheckCircle2 size={14} /> : <div className="h-1.5 w-1.5 rounded-full bg-current" />}
                </div>
                <div>
                  <h4 className={`text-sm font-black ${step.status === 'pending' ? 'text-slate-400' : 'text-slate-900'}`}>{step.title}</h4>
                  <p className="line-clamp-3 text-xs font-medium leading-5 text-slate-500 sm:line-clamp-none">{step.description}</p>
                </div>
              </div>
            ))}
          </div>
        </SectionCard>
      </div>

      {/* Action Plan / Next Step Section */}
      <div id="action-plan">
        <SectionCard 
          title="맞춤형 액션 플랜" 
          subtitle="내 생기부 기반으로 추천된 퀘스트입니다"
          badge={blueprint ? "AI 추천 가동 중" : "준비 중"}
        >
          {isLoadingBlueprint ? (
            <div className="flex h-64 flex-col items-center justify-center gap-4 text-slate-400">
              <div className="h-8 w-8 animate-spin rounded-full border-4 border-[#1d4fff] border-t-transparent" />
              <p className="text-sm font-bold">합격 가능성을 분석하여 퀘스트를 생성하고 있습니다...</p>
            </div>
          ) : blueprint ? (
            <div className="space-y-8">
              {/* Priority Quests */}
              <div>
                <h3 className="mb-6 flex items-center gap-2 text-xl font-black text-slate-900">
                  <Zap size={20} className="text-amber-500" fill="currentColor" />
                  최우선 퀘스트
                </h3>
                <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
                  {blueprint.priority_quests.map(quest => (
                    <QuestCard key={quest.id} quest={quest} onStart={handleStartQuest} isStarting={startingQuestId === quest.id} />
                  ))}
                </div>
              </div>

              {/* Subject Groups */}
              <div className="space-y-6 border-t border-[#e4edff] pt-6">
                <h3 className="text-xl font-black text-slate-900">과목별 탐구 플랜</h3>
                {blueprint.subject_groups.map(group => (
                  <div key={group.name} className="space-y-4">
                    <button 
                      onClick={() => setOpenSubjectGroups(prev => ({ ...prev, [group.name]: !prev[group.name] }))}
                      className="flex w-full items-center justify-between rounded-2xl border border-[#dce8ff] bg-[#f5f9ff] p-4 transition-colors hover:bg-[#edf4ff]"
                    >
                      <div className="flex items-center gap-3">
                        <School size={18} className="text-[#6b83af]" />
                        <span className="font-black text-slate-700">{group.name}</span>
                        <StatusBadge status="neutral">{group.quests.length}개</StatusBadge>
                      </div>
                      {openSubjectGroups[group.name] ? <ChevronUp size={18} /> : <ChevronDown size={18} />}
                    </button>
                    {openSubjectGroups[group.name] && (
                      <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3 pl-4">
                        {group.quests.map(quest => (
                          <QuestCard key={quest.id} quest={quest} onStart={handleStartQuest} isStarting={startingQuestId === quest.id} />
                        ))}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>
          ) : (
            <EmptyState
              title="아직 생성된 플랜이 없습니다"
              description={blueprintError || "목표 설정과 생기부 진단을 완료하면 맞춤형 합격 퀘스트가 열립니다."}
              actionLabel={nextAction.primaryLabel}
              onAction={nextAction.onPrimary}
              icon={<Target size={32} className="text-slate-300" />}
            />
          )}
        </SectionCard>
      </div>

      {/* OnboardingModal Removed: Integrated into /app/diagnosis */}
    </div>
  );
}
