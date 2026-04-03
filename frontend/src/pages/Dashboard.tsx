import React, { useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { ArrowRight, CheckCircle2, ChevronDown, ChevronUp, Flag, PlayCircle, School, Settings2, Target, TrendingUp } from 'lucide-react';
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
import { OnboardingModal } from '../components/OnboardingModal';
import { UniversityLogo } from '../components/UniversityLogo';
import { useAuth } from '../contexts/AuthContext';
import { api } from '../lib/api';
import { DIAGNOSIS_STORAGE_KEY, type DiagnosisResultPayload, type StoredDiagnosis } from '../lib/diagnosis';
import { isGuestSessionActive, readGuestProfile, updateGuestTargets } from '../lib/guestProfile';
import { buildRankedGoals } from '../lib/rankedGoals';
import { updateLocalAuthTargets } from '../lib/localAuthProfile';
import { type QuestStartPayload, saveQuestStart } from '../lib/questStart';
import { useAuthStore } from '../store/authStore';
import {
  EmptyState,
  PageHeader,
  PrimaryButton,
  SecondaryButton,
  SectionCard,
  StatusBadge,
  StepIndicator,
  SurfaceCard,
  WorkflowNotice,
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
    return JSON.parse(raw) as StoredDiagnosis;
  } catch {
    return null;
  }
}

function riskVariant(risk: DiagnosisResultPayload['risk_level']): 'success' | 'warning' | 'danger' {
  if (risk === 'danger') return 'danger';
  if (risk === 'warning') return 'warning';
  return 'success';
}

function levelSummary(completionRate: number, reportCount: number, isGuestSession: boolean) {
  if (isGuestSession) return '게스트 세션입니다. 계정을 연결하면 진행 기록이 안정적으로 보존됩니다.';
  if (completionRate >= 80 || reportCount >= 5) return '진행률이 높습니다. 우선순위 퀘스트를 실행해 완성도를 높여보세요.';
  if (completionRate >= 40) return '중간 단계입니다. 진단 결과를 바탕으로 핵심 퀘스트를 완료해 주세요.';
  return '초기 단계입니다. 목표 설정과 진단 완료가 다음 흐름을 여는 핵심입니다.';
}

function workflowStepVariant(status: WorkflowStatus): 'success' | 'active' | 'neutral' {
  if (status === 'done') return 'success';
  if (status === 'active') return 'active';
  return 'neutral';
}

const QuestCard = React.memo(function QuestCard({
  quest,
  onStart,
  isStarting,
}: {
  quest: BlueprintQuest;
  onStart: (quest: BlueprintQuest) => void;
  isStarting: boolean;
}) {
  const difficultyVariant = quest.difficulty === 'high' ? 'danger' : quest.difficulty === 'medium' ? 'warning' : 'success';
  const statusVariant = quest.status === 'COMPLETED' ? 'success' : quest.status === 'IN_PROGRESS' ? 'active' : 'neutral';

  return (
    <SurfaceCard className="h-full space-y-3">
      <div className="flex flex-wrap items-center gap-2">
        <StatusBadge status="neutral">{quest.subject}</StatusBadge>
        <StatusBadge status={difficultyVariant}>{quest.difficulty}</StatusBadge>
        <StatusBadge status={statusVariant}>{quest.status.toLowerCase()}</StatusBadge>
      </div>

      <h3 className="text-base font-bold tracking-tight text-slate-900">{quest.title}</h3>
      <p className="text-sm font-medium leading-6 text-slate-600">{quest.summary}</p>

      <div className="rounded-xl border border-slate-200 bg-slate-50 p-3">
        <p className="text-xs font-bold uppercase tracking-[0.14em] text-slate-400">왜 중요한가</p>
        <p className="mt-1 text-sm font-medium leading-6 text-slate-600">{quest.why_this_matters}</p>
      </div>

      <div className="rounded-xl border border-slate-200 bg-slate-50 p-3">
        <p className="text-xs font-bold uppercase tracking-[0.14em] text-slate-400">기대 효과</p>
        <p className="mt-1 text-sm font-medium leading-6 text-slate-600">{quest.expected_record_impact}</p>
      </div>

      <div className="flex items-center justify-between gap-3 pt-1">
        <p className="text-xs font-semibold text-slate-500">{quest.recommended_output_type}</p>
        <PrimaryButton onClick={() => onStart(quest)} disabled={isStarting} size="sm">
          {isStarting ? '시작 중...' : '퀘스트 시작'}
          <PlayCircle size={14} />
        </PrimaryButton>
      </div>
    </SurfaceCard>
  );
});

export function Dashboard() {
  const navigate = useNavigate();
  const { user, isGuestSession } = useAuth();
  const authStoreUser = useAuthStore(state => state.user);
  const setAuthUser = useAuthStore(state => state.setUser);

  const [isOnboardingOpen, setIsOnboardingOpen] = useState(false);
  const [isSavingProfile, setIsSavingProfile] = useState(false);
  const [isLoadingBlueprint, setIsLoadingBlueprint] = useState(false);
  const [startingQuestId, setStartingQuestId] = useState<string | null>(null);
  const [stats, setStats] = useState<UserStats>({ report_count: 0, level: 'Loading', completion_rate: 0 });
  const [profile, setProfile] = useState<UserProfile | null>(authStoreUser);
  const [storedDiagnosis, setStoredDiagnosis] = useState<StoredDiagnosis | null>(null);
  const [blueprint, setBlueprint] = useState<CurrentBlueprintResponse | null>(null);
  const [blueprintError, setBlueprintError] = useState<string | null>(null);
  const [focusedPanel, setFocusedPanel] = useState<DashboardPanel | null>('next');
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
      if (!guestProfile?.target_university || !guestProfile?.target_major) setIsOnboardingOpen(true);
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
      if (!hasTargets) setIsOnboardingOpen(true);
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
        if (!data.target_university || !data.target_major) setIsOnboardingOpen(true);
      })
      .catch(error => {
        console.error(error);
        if (isGuestSessionActive()) {
          const guestProfile = readGuestProfile();
          if (guestProfile) {
            setProfile(guestProfile);
            if (!guestProfile.target_university || !guestProfile.target_major) setIsOnboardingOpen(true);
            return;
          }
        }
        if (authStoreUser) {
          setProfile(authStoreUser);
          if (!authStoreUser.target_university || !authStoreUser.target_major) setIsOnboardingOpen(true);
          return;
        }
        setProfile(null);
        if (isGuestSession) setIsOnboardingOpen(true);
      });
  }, [user, isGuestSession, localAuthFallbackActive, authStoreUser]);

  useEffect(() => {
    if (!user && !isGuestSession) return;
    if (isGuestSessionActive()) {
      setBlueprint(null);
      setBlueprintError(null);
      setIsLoadingBlueprint(false);
      return;
    }

    if (localAuthFallbackActive) {
      setBlueprint(null);
      setBlueprintError('백엔드 인증을 연결하면 액션 플랜이 표시됩니다.');
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

  const handleSaveTargets = async (payload: { targetUniversity: string; targetMajor: string; interestUniversities: string[] }) => {
    setIsSavingProfile(true);
    const loadingId = toast.loading('목표를 저장하는 중입니다...');
    const request: UserTargetsUpdateRequest = {
      target_university: payload.targetUniversity,
      target_major: payload.targetMajor,
      interest_universities: payload.interestUniversities,
    };

    const applyGuestFallback = () => {
      const updated = updateGuestTargets(request, profile);
      setProfile(updated);
      setAuthUser(updated);
      setIsOnboardingOpen(false);
      toast.success('목표가 저장되었습니다.', { id: loadingId });
    };
    const applyLocalAuthFallback = () => {
      if (!user) return;
      const updated = updateLocalAuthTargets(request, user, profile);
      setProfile(updated);
      setAuthUser(updated);
      setIsOnboardingOpen(false);
      toast.success('목표가 저장되었습니다. (로컬 세션)', { id: loadingId });
    };

    try {
      if (isGuestSession && !user) {
        applyGuestFallback();
        return;
      }

      let data: UserTargetsUpdateResponse | OnboardingGoalsUpdateResponse;
      try {
        data = await api.patch<UserTargetsUpdateResponse>('/api/v1/users/me/targets', request);
      } catch (patchError) {
        const status = (patchError as { response?: { status?: number } })?.response?.status;
        if (status === 401 || status === 403) {
          throw patchError;
        }
        try {
          data = await api.post<OnboardingGoalsUpdateResponse>('/api/v1/users/onboarding/goals', request);
        } catch {
          throw patchError;
        }
      }
      setProfile(data);
      setAuthUser(data);
      setIsOnboardingOpen(false);
      toast.success('목표가 저장되었습니다.', { id: loadingId });
    } catch (error) {
      if (isGuestSessionActive()) {
        console.warn('Target save API failed in guest mode, applying local fallback.', error);
        applyGuestFallback();
        return;
      }
      if (user) {
        console.warn('Target save API failed for authenticated user, applying local auth fallback.', error);
        applyLocalAuthFallback();
        return;
      }
      toast.error('목표 저장에 실패했습니다.', { id: loadingId });
    } finally {
      setIsSavingProfile(false);
    }
  };

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
    if (!hasPrimaryGoal) {
      return [
        { key: 'targets', title: '목표 설정', description: '지원 대학/학과를 설정합니다.', status: 'active' },
        { key: 'record', title: '기록 업로드', description: '학생부 PDF를 업로드하고 파싱합니다.', status: 'pending' },
        { key: 'diagnosis', title: '진단 실행', description: '근거 기반 진단 결과를 생성합니다.', status: 'pending' },
        { key: 'workshop', title: '워크숍 실행', description: '초안 작성과 수정 워크플로를 시작합니다.', status: 'pending' },
      ];
    }

    if (!hasDiagnosis) {
      return [
        { key: 'targets', title: '목표 설정', description: `${profile?.target_university} · ${profile?.target_major}`, status: 'done' },
        { key: 'record', title: '기록 업로드', description: '문서 수집/파싱 진행 중', status: 'active' },
        { key: 'diagnosis', title: '진단 실행', description: '진단 실행 대기', status: 'pending' },
        { key: 'workshop', title: '워크숍 실행', description: '진단 완료 후 열립니다.', status: 'pending' },
      ];
    }

    if (!hasBlueprint) {
      return [
        { key: 'targets', title: '목표 설정', description: `${profile?.target_university} · ${profile?.target_major}`, status: 'done' },
        { key: 'record', title: '기록 업로드', description: '완료', status: 'done' },
        { key: 'diagnosis', title: '진단 실행', description: storedDiagnosis?.diagnosis.headline || '완료', status: 'done' },
        { key: 'workshop', title: '워크숍 실행', description: '액션 플랜 생성 중', status: 'active' },
      ];
    }

    return [
      { key: 'targets', title: '목표 설정', description: `${profile?.target_university} · ${profile?.target_major}`, status: 'done' },
      { key: 'record', title: '기록 업로드', description: '완료', status: 'done' },
      { key: 'diagnosis', title: '진단 실행', description: storedDiagnosis?.diagnosis.headline || '완료', status: 'done' },
      { key: 'workshop', title: '워크숍 실행', description: primaryQuest ? `우선 퀘스트: ${primaryQuest.title}` : '계속 진행', status: 'active' },
    ];
  }, [hasBlueprint, hasDiagnosis, hasPrimaryGoal, primaryQuest, profile?.target_major, profile?.target_university, storedDiagnosis]);

  const progressedCount = workflowSteps.filter(step => step.status === 'done').length + (workflowSteps.some(step => step.status === 'active') ? 1 : 0);
  const progressLabel = `${progressedCount}/4 단계`;

  const openWorkshop = () => {
    if (storedDiagnosis?.projectId) {
      navigate(`/app/workshop/${storedDiagnosis.projectId}`);
      return;
    }
    navigate('/app/workshop');
  };

  const nextAction = useMemo<NextAction>(() => {
    if (!hasPrimaryGoal) {
      return {
        title: '먼저 목표 대학과 학과를 설정하세요',
        description: '목표 설정이 완료되어야 진단과 퀘스트 추천의 정확도가 올라갑니다.',
        primaryLabel: '목표 설정',
        onPrimary: () => setIsOnboardingOpen(true),
        secondaryLabel: '진단 페이지로 이동',
        onSecondary: () => navigate('/app/diagnosis'),
      };
    }

    if (!hasDiagnosis) {
      return {
        title: '학생부를 업로드하고 진단을 시작하세요',
        description: '문서 파싱과 마스킹이 완료되면 근거 기반 진단이 실행됩니다.',
        primaryLabel: '기록 업로드',
        onPrimary: () => navigate('/app/record'),
        secondaryLabel: '진단 페이지로 이동',
        onSecondary: () => navigate('/app/diagnosis'),
      };
    }

    if (!hasBlueprint) {
      return {
        title: '진단이 완료되었습니다. 워크숍으로 이어가세요',
        description: '초안 작성 흐름을 시작하고 액션 플랜을 실행할 수 있습니다.',
        primaryLabel: '워크숍 열기',
        onPrimary: openWorkshop,
        secondaryLabel: '진단 다시 보기',
        onSecondary: () => navigate('/app/diagnosis'),
      };
    }

    if (primaryQuest) {
      return {
        title: `지금 시작할 우선 퀘스트: ${primaryQuest.title}`,
        description: '가장 영향도가 큰 퀘스트부터 실행하면 단기 성과가 빠르게 올라갑니다.',
        primaryLabel: '우선 퀘스트 시작',
        onPrimary: () => void handleStartQuest(primaryQuest),
        secondaryLabel: '액션 플랜 보기',
        onSecondary: () => document.getElementById('action-plan')?.scrollIntoView({ behavior: 'smooth' }),
      };
    }

    return {
      title: '워크숍 초안 작성을 이어가세요',
      description: '생성된 플랜을 바탕으로 근거 중심 결과물을 완성할 수 있습니다.',
      primaryLabel: '워크숍 열기',
      onPrimary: openWorkshop,
      secondaryLabel: '액션 플랜 보기',
      onSecondary: () => document.getElementById('action-plan')?.scrollIntoView({ behavior: 'smooth' }),
    };
  }, [hasBlueprint, hasDiagnosis, hasPrimaryGoal, navigate, openWorkshop, primaryQuest]);

  const stepItems = workflowSteps.map(step => ({
    id: step.key,
    label: step.title,
    description: step.description,
    state: step.status,
  })) as Array<{ id: string; label: string; description: string; state: 'done' | 'active' | 'pending' | 'error' }>;
  const primaryGoal = allGoals[0] ?? null;

  const handlePanelCollapsedChange = (panel: DashboardPanel, collapsed: boolean) => {
    if (!collapsed) {
      setFocusedPanel(panel);
      return;
    }

    setFocusedPanel(current => (current === panel ? null : current));
  };

  const toggleSubjectGroup = (groupName: string) => {
    setOpenSubjectGroups(previous => ({ ...previous, [groupName]: !previous[groupName] }));
  };

  return (
    <div className="mx-auto max-w-7xl space-y-7 py-2">
      <PageHeader
        eyebrow="대시보드"
        title="학생부 준비 워크플로 현황"
        description="현재 위치를 확인하고, 가장 영향도가 높은 다음 행동을 바로 실행할 수 있습니다."
        actions={
          <>
            {hasPrimaryGoal ? (
              <SecondaryButton onClick={() => setIsOnboardingOpen(true)}>
                <Settings2 size={16} />
                목표 수정
              </SecondaryButton>
            ) : null}
            <PrimaryButton onClick={nextAction.onPrimary}>
              {nextAction.primaryLabel}
              <ArrowRight size={16} />
            </PrimaryButton>
          </>
        }
        evidence={
          <div className="flex flex-wrap items-center gap-2">
            <StatusBadge status="active">{progressLabel}</StatusBadge>
            <StatusBadge status="neutral">보고서 {stats.report_count}개</StatusBadge>
            <StatusBadge status={stats.completion_rate >= 70 ? 'success' : stats.completion_rate >= 40 ? 'warning' : 'neutral'}>
              완성도 {stats.completion_rate}%
            </StatusBadge>
            {storedDiagnosis ? <StatusBadge status={riskVariant(storedDiagnosis.diagnosis.risk_level)}>진단 {storedDiagnosis.diagnosis.risk_level}</StatusBadge> : null}
          </div>
        }
      />

      {primaryGoal ? (
        <SurfaceCard className="border-blue-200 bg-[linear-gradient(120deg,_rgba(37,99,235,0.14),_rgba(255,255,255,1))]">
          <div className="space-y-3">
            <div className="flex flex-wrap items-center gap-4">
              <UniversityLogo
                universityName={primaryGoal.university}
                className="h-14 w-14 rounded-2xl bg-white object-contain p-2 shadow-sm"
                fallbackClassName="border border-blue-100"
              />
              <div className="min-w-0 flex-1">
                <p className="text-xs font-black uppercase tracking-[0.18em] text-blue-700">Dream Target</p>
                <p className="mt-1 truncate text-2xl font-black text-slate-900">{primaryGoal.university}</p>
                <p className="mt-1 truncate text-sm font-semibold text-slate-600">{primaryGoal.major || '학과 미정'}</p>
              </div>
              <StatusBadge status="active" className="px-3 py-1.5 text-sm">
                <Flag size={14} />
                1순위 목표
              </StatusBadge>
            </div>

            <div className="grid gap-2 sm:grid-cols-2 xl:grid-cols-3">
              {allGoals.map((goal, index) => (
                <div
                  key={`${goal.university}-${goal.major}-${index}`}
                  className="flex min-w-0 items-center gap-2 rounded-xl border border-blue-100 bg-white/80 px-2.5 py-2"
                >
                  <UniversityLogo
                    universityName={goal.university}
                    className="h-8 w-8 rounded-lg bg-slate-100 object-contain p-1"
                    fallbackClassName="border border-slate-200"
                  />
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-xs font-black text-blue-700">{index + 1}순위</p>
                    <p className="truncate text-sm font-black text-slate-900">{goal.university}</p>
                    <p className="truncate text-xs font-medium text-slate-600">{goal.major || '학과 미정'}</p>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </SurfaceCard>
      ) : null}
      <SectionCard
        title={nextAction.title}
        description={nextAction.description}
        eyebrow="다음 행동"
        actions={<StatusBadge status="active">{progressLabel}</StatusBadge>}
        collapsible
        collapsed={focusedPanel !== 'next'}
        onCollapsedChange={collapsed => handlePanelCollapsedChange('next', collapsed)}
      >
        <WorkflowNotice
          tone="info"
          title="지금 해야 할 일"
          description={nextAction.description}
        />
        <StepIndicator items={stepItems} />
        <div className="flex flex-wrap gap-2">
          <PrimaryButton onClick={nextAction.onPrimary}>
            {nextAction.primaryLabel}
            <ArrowRight size={16} />
          </PrimaryButton>
          {nextAction.secondaryLabel && nextAction.onSecondary ? (
            <SecondaryButton onClick={nextAction.onSecondary}>{nextAction.secondaryLabel}</SecondaryButton>
          ) : null}
        </div>
      </SectionCard>

      <div className="grid gap-6 lg:grid-cols-3">
        <SectionCard
          title="목표 및 진행 상태"
          description={levelSummary(stats.completion_rate, stats.report_count, isGuestSession)}
          eyebrow="상태"
          className="lg:col-span-1"
          collapsible
          collapsed={focusedPanel !== 'status'}
          onCollapsedChange={collapsed => handlePanelCollapsedChange('status', collapsed)}
        >
          {primaryGoal ? (
            <SurfaceCard padding="sm" className="border-blue-200 bg-blue-50/70">
              <p className="text-xs font-black uppercase tracking-[0.14em] text-blue-600">현재 1순위 목표</p>
              <div className="mt-2 flex items-center gap-3">
                <UniversityLogo
                  universityName={primaryGoal.university}
                  className="h-10 w-10 rounded-xl bg-white object-contain p-1.5"
                  fallbackClassName="border border-blue-100"
                />
                <div className="min-w-0">
                  <p className="truncate text-base font-black text-slate-900">{primaryGoal.university}</p>
                  <p className="truncate text-sm font-medium text-slate-600">{primaryGoal.major || '학과 미설정'}</p>
                </div>
              </div>
            </SurfaceCard>
          ) : null}

          {allGoals.length ? (
            <div className="space-y-2">
              {allGoals.slice(0, 6).map((goal, index) => (
                <SurfaceCard key={`${goal.university}-${goal.major}-${index}`} padding="sm" className="flex items-center gap-3">
                  <UniversityLogo
                    universityName={goal.university}
                    className="h-9 w-9 rounded-xl bg-slate-100 object-contain p-1"
                    fallbackClassName="border border-slate-200"
                  />
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm font-black text-slate-800">{goal.university}</p>
                    <p className="truncate text-xs font-medium text-slate-500">{goal.major || '학과 미설정'}</p>
                  </div>
                  {index === 0 ? <StatusBadge status="active">주 목표</StatusBadge> : <StatusBadge status="neutral">{index + 1}순위</StatusBadge>}
                </SurfaceCard>
              ))}
            </div>
          ) : (
            <EmptyState
              title="아직 목표가 없습니다"
              description="최소 1개 목표를 설정하면 진단과 퀘스트 추천 정확도가 올라갑니다."
              actionLabel="목표 설정"
              onAction={() => setIsOnboardingOpen(true)}
              icon={<School size={20} />}
            />
          )}

          <div>
            <p className="mb-2 text-xs font-black uppercase tracking-[0.14em] text-slate-400">진행률</p>
            <div className="h-3 overflow-hidden rounded-full bg-slate-200">
              <div className="h-full rounded-full bg-blue-600" style={{ width: `${stats.completion_rate}%` }} />
            </div>
            <p className="mt-2 text-xs font-semibold text-slate-500">완성도 {stats.completion_rate}%</p>
          </div>
        </SectionCard>

        <SectionCard
          id="action-plan"
          title="액션 플랜"
          description="진단 근거와 목표 정보를 기반으로 생성된 실행 계획입니다."
          eyebrow="플랜"
          className="lg:col-span-2"
          collapsible
          collapsed={focusedPanel !== 'plan'}
          onCollapsedChange={collapsed => handlePanelCollapsedChange('plan', collapsed)}
        >
          {isLoadingBlueprint ? (
            <div className="flex h-48 items-center justify-center rounded-2xl border border-dashed border-slate-300 bg-slate-50">
              <div className="h-8 w-8 animate-spin rounded-full border-4 border-blue-600 border-t-transparent" />
            </div>
          ) : blueprint ? (
            <div className="space-y-5">
              <div className="grid gap-4 lg:grid-cols-2">
                <SurfaceCard padding="sm" className="space-y-2">
                  <p className="text-xs font-bold uppercase tracking-[0.14em] text-slate-400">진단 헤드라인</p>
                  <p className="text-lg font-bold tracking-tight text-slate-900">{blueprint.headline}</p>
                  <p className="text-sm font-medium leading-6 text-slate-600">{blueprint.recommended_focus}</p>
                </SurfaceCard>
                <SurfaceCard padding="sm" className="space-y-2">
                  <p className="text-xs font-bold uppercase tracking-[0.14em] text-slate-400">학기 우선순위</p>
                  <p className="text-sm font-bold text-slate-800">{blueprint.semester_priority_message}</p>
                  <ul className="space-y-1.5">
                    {blueprint.expected_record_effects.slice(0, 3).map((effect, index) => (
                      <li key={`${effect}-${index}`} className="flex gap-2 text-sm font-medium text-slate-600">
                        <CheckCircle2 size={14} className="mt-0.5 text-emerald-600" />
                        {effect}
                      </li>
                    ))}
                  </ul>
                </SurfaceCard>
              </div>

              <div className="space-y-3">
                <div className="flex items-center justify-between gap-2">
                  <h3 className="text-lg font-bold tracking-tight text-slate-900">우선 퀘스트</h3>
                  <StatusBadge status="active">{blueprint.priority_quests.length}개</StatusBadge>
                </div>
                <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
                  {blueprint.priority_quests.map(quest => (
                    <QuestCard key={quest.id} quest={quest} onStart={handleStartQuest} isStarting={startingQuestId === quest.id} />
                  ))}
                </div>
              </div>

              <div className="space-y-4">
                {blueprint.subject_groups.map(group => (
                  <div key={group.name} className="space-y-3">
                    <button
                      type="button"
                      onClick={() => toggleSubjectGroup(group.name)}
                      className="flex w-full items-center justify-between rounded-2xl border border-slate-200 bg-white px-3 py-2.5 text-left transition-colors hover:bg-slate-50"
                      aria-expanded={openSubjectGroups[group.name] ?? false}
                    >
                      <div className="flex min-w-0 items-center gap-2">
                        <Target size={16} className="text-blue-700" />
                        <h4 className="truncate text-sm font-bold uppercase tracking-[0.14em] text-slate-600">{group.name}</h4>
                        <StatusBadge status="neutral">{group.quests.length}개</StatusBadge>
                      </div>
                      {openSubjectGroups[group.name] ? <ChevronUp size={16} className="text-slate-400" /> : <ChevronDown size={16} className="text-slate-400" />}
                    </button>
                    {openSubjectGroups[group.name] ? (
                      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
                        {group.quests.map(quest => (
                          <QuestCard key={quest.id} quest={quest} onStart={handleStartQuest} isStarting={startingQuestId === quest.id} />
                        ))}
                      </div>
                    ) : null}
                  </div>
                ))}
              </div>
            </div>
          ) : (
            <EmptyState
              title="아직 액션 플랜이 없습니다"
              description={blueprintError || '목표 설정과 진단을 완료하면 맞춤 액션 플랜이 생성됩니다.'}
              actionLabel={nextAction.primaryLabel}
              onAction={nextAction.onPrimary}
              icon={<TrendingUp size={20} />}
            />
          )}
        </SectionCard>
      </div>

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

