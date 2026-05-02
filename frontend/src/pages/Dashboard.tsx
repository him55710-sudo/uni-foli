import React, { useEffect, useMemo, useState } from 'react';
import { motion } from 'motion/react';
import { useNavigate } from 'react-router-dom';
import { ArrowRight, CheckCircle2, ChevronDown, ChevronUp, Flag, PlayCircle, School, Settings2, Sparkles, Target, Zap } from 'lucide-react';
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
  PageHeader,
  SectionCard,
  StatusBadge,
  SurfaceCard,
} from '../components/primitives';
import { InterestCloud } from '../components/InterestCloud';

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

function normalizeTargetText(value?: string | null): string {
  return (value || '').trim();
}

function hasCompletePrimaryGoal(
  profile: Pick<UserProfile, 'target_university' | 'target_major'> | null | undefined,
): boolean {
  return Boolean(normalizeTargetText(profile?.target_university) && normalizeTargetText(profile?.target_major));
}

function storedDiagnosisMatchesProfile(
  diagnosis: StoredDiagnosis | null,
  profile: UserProfile | null,
): diagnosis is StoredDiagnosis {
  if (!diagnosis || !hasCompletePrimaryGoal(profile)) return false;

  const currentUniversity = normalizeTargetText(profile?.target_university);
  const currentMajor = normalizeTargetText(profile?.target_major);
  const diagnosisUniversity = normalizeTargetText(diagnosis.targetUniversity ?? diagnosis.target_university);
  const diagnosisMajor = normalizeTargetText(diagnosis.targetMajor ?? diagnosis.target_major ?? diagnosis.major);

  return diagnosisUniversity === currentUniversity && diagnosisMajor === currentMajor;
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
    return '상세 요약은 진단 페이지에서 확인하세요.';
  }
  if (cleaned.length > 120) {
    return `${cleaned.slice(0, 96)}...`;
  }
  return cleaned;
}

const questToneMap = {
  high: {
    badge: 'danger' as const,
    icon: 'bg-red-50 text-red-500 group-hover:bg-red-500',
    shell: 'border-red-100',
    action: 'bg-[#f04452] shadow-[0_10px_22px_rgba(240,68,82,0.22)]',
  },
  medium: {
    badge: 'warning' as const,
    icon: 'bg-orange-50 text-orange-500 group-hover:bg-orange-500',
    shell: 'border-orange-100',
    action: 'bg-[#ff9c20] shadow-[0_10px_22px_rgba(255,156,32,0.22)]',
  },
  low: {
    badge: 'success' as const,
    icon: 'bg-blue-50 text-[#3182f6] group-hover:bg-[#3182f6]',
    shell: 'border-blue-100',
    action: 'bg-[#3182f6] shadow-[0_10px_22px_rgba(49,130,246,0.22)]',
  },
};

const QuestCard = ({ quest, onStart, isStarting }: { quest: BlueprintQuest; onStart: (q: BlueprintQuest) => void; isStarting: boolean }) => {
  const diffLabel = quest.difficulty === 'high' ? '상' : quest.difficulty === 'medium' ? '중' : '하';
  const tone = questToneMap[quest.difficulty === 'high' ? 'high' : quest.difficulty === 'medium' ? 'medium' : 'low'];

  return (
    <SurfaceCard className={`group relative flex flex-col justify-between overflow-hidden bg-white p-6 shadow-sm ring-1 ring-slate-200/50 transition-all hover:-translate-y-0.5 hover:shadow-md active:scale-[0.98] ${tone.shell}`}>
      <div className="space-y-4">
        <div className="flex items-start justify-between">
          <StatusBadge status={tone.badge} className="px-2.5 py-0.5 text-[10px] font-black uppercase tracking-wider">Level {diffLabel}</StatusBadge>
          <div className={`rounded-xl p-2 transition-colors group-hover:text-white ${tone.icon}`}>
            <Zap size={16} fill="currentColor" className="opacity-80" />
          </div>
        </div>
        <div>
          <h4 className="line-clamp-1 text-lg font-black tracking-tight text-[#191f28]">{quest.title}</h4>
          <p className="mt-2 line-clamp-2 text-[14px] font-medium leading-relaxed text-[#4e5968]">{quest.summary}</p>
        </div>
      </div>
      
      <div className="mt-6 flex items-center justify-between gap-4 border-t border-slate-100 pt-5">
        <div className="flex flex-col">
          <span className="text-[10px] font-black uppercase tracking-wider text-[#b0b8c1]">Subject</span>
          <span className="text-sm font-black text-[#333d4b]">{quest.subject}</span>
        </div>
        <button
          onClick={() => onStart(quest)}
          disabled={isStarting}
          className={`inline-flex h-10 items-center gap-2 rounded-xl px-5 text-xs font-black text-white transition-all hover:-translate-y-0.5 disabled:opacity-50 ${tone.action}`}
        >
          {isStarting ? '준비 중...' : '시작하기'}
          {!isStarting && <ArrowRight size={14} strokeWidth={2.5} />}
        </button>
      </div>
    </SurfaceCard>
  );
};

export default function Dashboard() {
  const navigate = useNavigate();
  const { user, isGuestSession } = useAuth();
  const authStoreUser = useAuthStore(state => state.user);

  const [isLoadingBlueprint, setIsLoadingBlueprint] = useState(false);
  const [startingQuestId, setStartingQuestId] = useState<string | null>(null);
  const [stats, setStats] = useState<UserStats>({ report_count: 0, level: '불러오는 중', completion_rate: 0 });
  const [profile, setProfile] = useState<UserProfile | null>(authStoreUser);
  const [storedDiagnosis, setStoredDiagnosis] = useState<StoredDiagnosis | null>(null);
  const [blueprint, setBlueprint] = useState<CurrentBlueprintResponse | null>(null);
  const [blueprintError, setBlueprintError] = useState<string | null>(null);
  const [openSubjectGroups, setOpenSubjectGroups] = useState<Record<string, boolean>>({});
  const localAuthFallbackActive = Boolean(authStoreUser?.id?.startsWith('local-auth-'));

  const activeStoredDiagnosis = useMemo(
    () => (storedDiagnosisMatchesProfile(storedDiagnosis, profile) ? storedDiagnosis : null),
    [profile, storedDiagnosis],
  );
  const canUseDiagnosisContext = hasCompletePrimaryGoal(profile) && Boolean(activeStoredDiagnosis?.projectId);

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
      })
      .catch(error => {
        console.error(error);
        if (isGuestSessionActive()) {
          const guestProfile = readGuestProfile();
          if (guestProfile) {
            setProfile(guestProfile);
            return;
          }
        }
        if (authStoreUser) {
          setProfile(authStoreUser);
          return;
        }
        setProfile(null);
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
    if (!canUseDiagnosisContext) {
      setBlueprint(null);
      setBlueprintError(null);
      setIsLoadingBlueprint(false);
      return;
    }

    setIsLoadingBlueprint(true);
    setBlueprintError(null);

    api
      .get<CurrentBlueprintResponse>('/api/v1/blueprints/current', {
        params: activeStoredDiagnosis?.projectId ? { project_id: activeStoredDiagnosis.projectId } : undefined,
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
  }, [user, isGuestSession, activeStoredDiagnosis?.projectId, canUseDiagnosisContext, localAuthFallbackActive]);

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
  const hasPrimaryGoal = hasCompletePrimaryGoal(profile);
  const hasDiagnosis = Boolean(activeStoredDiagnosis?.projectId);
  const hasBlueprint = Boolean(blueprint);
  const primaryQuest = blueprint?.priority_quests[0] ?? null;

  const workflowSteps = useMemo<WorkflowStep[]>(() => {
    const diagnosisSummary = hasDiagnosis
      ? toCompactDiagnosisSummary(activeStoredDiagnosis?.diagnosis.headline)
      : 'AI 진단 실행';

    const steps: WorkflowStep[] = [
      { key: 'targets', title: '목표 설정', description: hasPrimaryGoal ? `${profile?.target_university} · ${profile?.target_major}` : '지원 대학/학과 설정', status: hasPrimaryGoal ? 'done' : 'active' },
      { key: 'record', title: '기록 업로드', description: hasDiagnosis ? '업로드 완료' : (hasPrimaryGoal ? '학생부 PDF 업로드' : '대기 중'), status: hasDiagnosis ? 'done' : (hasPrimaryGoal ? 'active' : 'pending') },
      { key: 'diagnosis', title: '진단 실행', description: diagnosisSummary, status: hasDiagnosis ? 'done' : (hasPrimaryGoal && !hasDiagnosis ? 'pending' : 'pending') },
      { key: 'workshop', title: '워크숍 실행', description: hasBlueprint ? (primaryQuest ? `우선: ${primaryQuest.title}` : '진행 가능') : '액션 플랜 대기', status: hasBlueprint ? 'active' : 'pending' },
    ];
    return steps;
  }, [activeStoredDiagnosis, hasBlueprint, hasDiagnosis, hasPrimaryGoal, primaryQuest, profile]);

  const completedStepCount = workflowSteps.filter(s => s.status === 'done').length;
  const progressLabel = `${Math.min(completedStepCount, 4)}/4 단계`;

  const nextAction = useMemo<NextAction>(() => {
    if (!hasPrimaryGoal) {
      return {
        title: '목표 대학과 학과를 설정하세요',
        description: '입시 준비 시작 단계',
        primaryLabel: '목표 설정하기',
        onPrimary: () => navigate('/app/diagnosis'),
        secondaryLabel: '진단 가이드',
        onSecondary: () => navigate('/help/student-record-pdf'),
      };
    }
    if (!hasDiagnosis) {
      return {
        title: '학생부를 업로드하고 진단을 받으세요',
        description: '업로드 후 즉시 진단',
        primaryLabel: '학생부 업로드',
        onPrimary: () => navigate('/app/record'),
        secondaryLabel: '진단 시작하기',
        onSecondary: () => navigate('/app/diagnosis'),
      };
    }
    if (primaryQuest) {
      return {
        title: `다음 추천 퀘스트: ${primaryQuest.title}`,
        description: '지금 바로 실행할 과제',
        primaryLabel: '퀘스트 시작하기',
        onPrimary: () => void handleStartQuest(primaryQuest),
        secondaryLabel: '워크숍 이동',
        onSecondary: () => navigate(`/app/workshop/${activeStoredDiagnosis?.projectId}`),
      };
    }
    return {
      title: '워크숍에서 기록을 완성하세요',
      description: '진단 기반 초안 작성',
      primaryLabel: '워크숍 열기',
      onPrimary: () => navigate(activeStoredDiagnosis?.projectId ? `/app/workshop/${activeStoredDiagnosis.projectId}` : '/app/workshop'),
    };
  }, [activeStoredDiagnosis, hasDiagnosis, hasPrimaryGoal, navigate, primaryQuest]);

  const primaryGoal = hasPrimaryGoal ? (allGoals[0] ?? null) : null;
  const quickActions = [
    {
      label: nextAction.primaryLabel,
      onClick: nextAction.onPrimary,
      tone: 'primary' as const,
    },
    {
      label: hasPrimaryGoal ? '목표 수정' : '진단 가이드',
      onClick: hasPrimaryGoal ? () => navigate('/app/diagnosis') : () => navigate('/help/student-record-pdf'),
      tone: 'secondary' as const,
    },
    {
      label: hasDiagnosis ? '워크숍 열기' : '학생부 업로드',
      onClick: hasDiagnosis
        ? () => navigate(activeStoredDiagnosis?.projectId ? `/app/workshop/${activeStoredDiagnosis.projectId}` : '/app/workshop')
        : () => navigate('/app/record'),
      tone: 'secondary' as const,
    },
  ];

  return (
    <div className="mx-auto max-w-7xl space-y-6 pb-12 sm:space-y-8">
      <motion.section
        initial={{ opacity: 0, y: 18 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.45 }}
        className="rounded-[28px] border border-slate-200 bg-white p-6 shadow-sm sm:p-8"
      >
        <div className="flex flex-col gap-6 lg:flex-row lg:items-end lg:justify-between">
          <div className="max-w-3xl">
            <p className="text-xs font-black uppercase tracking-[0.18em] text-[#3182f6]">Uni Foli workflow</p>
            <h1 className="mt-3 text-3xl font-black tracking-tight text-[#191f28] sm:text-4xl">
              진단에서 끝내지 않고, 보완 탐구와 보고서까지 이어갑니다
            </h1>
            <p className="mt-4 text-sm font-semibold leading-7 text-[#4e5968] sm:text-base">
              목표 학과가 있으면 전공 기준으로 진단하고, 아직 목표가 없으면 생기부를 먼저 읽어 어울리는 전공군과
              탐구 방향을 찾습니다. 모든 결과는 점수보다 근거 문장과 다음 행동을 우선합니다.
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            <button
              onClick={() => navigate('/app/diagnosis')}
              className="inline-flex h-11 items-center gap-2 rounded-2xl bg-[#3182f6] px-5 text-sm font-black text-white shadow-lg shadow-blue-100 transition hover:bg-[#1b64da]"
            >
              생기부 업로드
              <ArrowRight size={16} />
            </button>
            <button
              onClick={() => navigate(activeStoredDiagnosis?.projectId ? `/app/workshop/${activeStoredDiagnosis.projectId}` : '/app/workshop')}
              className="inline-flex h-11 items-center gap-2 rounded-2xl border border-slate-200 bg-white px-5 text-sm font-black text-[#333d4b] transition hover:bg-slate-50"
            >
              워크숍 이어가기
            </button>
          </div>
        </div>

        <div className="mt-7 grid gap-3 md:grid-cols-4">
          {[
            ['1', '생기부 업로드', '목표가 없어도 기록 먼저 분석'],
            ['2', '근거 기반 진단', '판단 근거와 부족한 근거 확인'],
            ['3', '보완 탐구 추천', '세특/전공 연결 주제 제안'],
            ['4', '보고서·면접 실행', '저장하고 다시 이어 쓰는 워크숍'],
          ].map(([index, title, copy]) => (
            <div key={title} className="rounded-2xl border border-slate-200 bg-slate-50/70 p-4">
              <span className="inline-flex h-8 w-8 items-center justify-center rounded-xl bg-white text-sm font-black text-[#3182f6] ring-1 ring-slate-200">
                {index}
              </span>
              <h2 className="mt-4 text-sm font-black text-[#191f28]">{title}</h2>
              <p className="mt-2 text-xs font-semibold leading-5 text-[#6b7280]">{copy}</p>
            </div>
          ))}
        </div>
      </motion.section>

      <motion.div
        initial={{ opacity: 0, y: 24 }}
        whileInView={{ opacity: 1, y: 0 }}
        viewport={{ once: true, amount: 0.1 }}
        transition={{ duration: 0.5 }}
        className="grid gap-5 lg:grid-cols-[1.2fr_0.8fr]"
      >
        <PageHeader
          eyebrow="Dashboard"
          title={nextAction.title}
          description={nextAction.description}
          className="border-slate-200 bg-white p-6 sm:p-8"
          actions={
            <div className="flex flex-wrap gap-2">
              <button
                onClick={nextAction.onPrimary}
                className="inline-flex h-12 items-center gap-2 rounded-2xl bg-[#3182f6] px-6 text-[15px] font-black text-white shadow-lg shadow-blue-100 transition-all hover:bg-[#1b64da] hover:-translate-y-0.5 active:scale-95"
              >
                {nextAction.primaryLabel}
                <ArrowRight size={18} strokeWidth={2.5} />
              </button>
              {hasPrimaryGoal && (
                <button
                  onClick={() => navigate('/app/diagnosis')}
                  className="inline-flex h-12 items-center gap-2 rounded-2xl border border-slate-200 bg-white px-5 text-[15px] font-black text-[#4e5968] transition-all hover:bg-[#f2f4f6] active:scale-95"
                >
                  <Settings2 size={18} />
                  목표 수정
                </button>
              )}
            </div>
          }
          evidence={
            <div className="flex flex-wrap items-center gap-2">
              <StatusBadge status="active">{progressLabel}</StatusBadge>
              <StatusBadge status="neutral">준비율 {stats.completion_rate}%</StatusBadge>
              <StatusBadge status="neutral">분석서 {stats.report_count}개</StatusBadge>
              {activeStoredDiagnosis ? (
                <StatusBadge status={riskVariant(activeStoredDiagnosis.diagnosis.risk_level)}>
                  {activeStoredDiagnosis.diagnosis.risk_level === 'danger'
                    ? '집중 보완'
                    : activeStoredDiagnosis.diagnosis.risk_level === 'warning'
                      ? '주의'
                      : '안정'}
                </StatusBadge>
              ) : null}
            </div>
          }
        />

        <SectionCard
          title="현재 기준"
          subtitle={hasPrimaryGoal ? '현재 목표/다음 단계 요약' : '목표 설정 후 다음 단계가 열립니다.'}
          className="border-slate-200 bg-white/90 p-6 sm:p-8"
        >
          <div className="space-y-4">
            <div className="rounded-2xl border border-slate-200 bg-slate-50/80 px-4 py-4">
              <p className="text-[11px] font-black uppercase tracking-[0.18em] text-slate-400">Target</p>
              <p className="mt-1 text-lg font-black tracking-tight text-slate-950">
                {primaryGoal ? `${primaryGoal.university} · ${primaryGoal.major}` : '목표 대학/학과 미설정'}
              </p>
            </div>
            <div className="rounded-2xl border border-slate-200 bg-white px-4 py-4">
              <p className="text-[11px] font-black uppercase tracking-[0.18em] text-slate-400">Diagnosis</p>
              <p className="mt-1 text-sm font-bold text-slate-800">
                {hasDiagnosis ? toCompactDiagnosisSummary(activeStoredDiagnosis?.diagnosis.headline) : '아직 진단 전입니다.'}
              </p>
            </div>
            <div className="rounded-2xl border border-slate-200 bg-white px-4 py-4">
              <p className="text-[11px] font-black uppercase tracking-[0.18em] text-slate-400">Next</p>
              <p className="mt-1 text-sm font-bold text-slate-800">{nextAction.primaryLabel}</p>
            </div>
          </div>
        </SectionCard>
      </motion.div>

      <div className="grid gap-3 md:grid-cols-3">
        {quickActions.map((action) => (
          <button
            key={action.label}
            onClick={action.onClick}
            className={`flex items-center justify-between rounded-3xl border px-6 py-4 text-left transition-all ${
              action.tone === 'primary'
                ? 'border-[#3182f6] bg-[#3182f6] text-white shadow-xl shadow-blue-100 hover:-translate-y-0.5'
                : 'border-slate-200 bg-white text-[#333d4b] hover:border-blue-100 hover:bg-blue-50'
            }`}
          >
            <span className="text-[15px] font-black">{action.label}</span>
            <ArrowRight size={18} strokeWidth={2.5} className={action.tone === 'primary' ? 'text-white' : 'text-[#b0b8c1]'} />
          </button>
        ))}
      </div>

      {/* Target & Progress Grid */}
      <div className="grid gap-6 sm:gap-8 lg:grid-cols-3">
        {/* Target Card */}
        <SurfaceCard className="relative overflow-hidden border-slate-200 bg-white p-6 shadow-sm sm:p-8 lg:col-span-2">
          <div className="relative z-10">
            <div className="flex flex-col gap-6 lg:flex-row lg:items-center">
              <div className="flex items-center gap-4 sm:gap-6 flex-1 min-w-0">
                <div className="relative shrink-0">
                  <UniversityLogo
                    universityName={primaryGoal?.university}
                    className="h-16 w-16 rounded-2xl border border-[#f2f4f6] bg-white object-contain p-2.5 shadow-sm sm:h-20 sm:w-20 sm:rounded-[1.5rem] sm:p-3 ring-1 ring-slate-100"
                  />
                  {!hasPrimaryGoal && (
                    <div className="absolute -bottom-1 -right-1 flex h-7 w-7 items-center justify-center rounded-full bg-[#ff9c20] text-white shadow-md ring-2 ring-white">
                      <Zap size={14} fill="currentColor" />
                    </div>
                  )}
                </div>
                <div className="min-w-0 flex-1">
                    <div className="mb-2.5 inline-flex items-center gap-1.5 rounded-lg bg-blue-50 px-2.5 py-1 text-[11px] font-black tracking-widest text-[#3182f6] uppercase ring-1 ring-inset ring-blue-100">
                    <Flag size={12} strokeWidth={2.5} />
                    {hasPrimaryGoal ? '핵심 목표' : '첫 걸음'}
                  </div>
                  <h2 className="truncate text-2xl font-black tracking-tight text-[#191f28] sm:text-3xl lg:text-4xl">
                    {primaryGoal?.university || '목표 설정이 필요합니다'}
                  </h2>
                  <p className="mt-1.5 truncate text-[15px] font-bold text-[#4e5968] sm:text-lg">
                    {primaryGoal?.major || '어떤 대학에서 당신의 꿈을 펼치고 싶나요?'}
                  </p>
                  {!hasPrimaryGoal && (
                    <div className="mt-6 flex flex-wrap gap-2">
                      <button 
                        onClick={() => navigate('/app/diagnosis')}
                        className="inline-flex h-11 items-center gap-2 rounded-2xl bg-[#3182f6] px-6 text-[14px] font-black text-white shadow-lg shadow-blue-50 transition-all hover:bg-[#1b64da] active:scale-95"
                      >
                        지금 바로 설정하기
                        <ArrowRight size={16} strokeWidth={2.5} />
                      </button>
                    </div>
                  )}
                </div>
              </div>

              {/* Secondary Goals or Placeholders to fill space */}
              <div className="flex flex-col gap-2.5 lg:w-[220px] shrink-0">
                {allGoals.length > 1 ? (
                  allGoals.slice(1, 3).map((goal, index) => (
                     <div key={index} className="flex items-center gap-3 rounded-2xl border border-slate-100 bg-slate-50/30 p-3">
                      <UniversityLogo universityName={goal.university} className="h-10 w-10 rounded-xl bg-white p-1 shadow-sm" />
                      <div className="min-w-0">
                        <p className="text-[10px] font-black text-[#b0b8c1] uppercase">차순위 {index + 1}</p>
                        <p className="truncate text-sm font-black text-[#333d4b]">{goal.university}</p>
                      </div>
                    </div>
                  ))
                ) : (
                  <>
                     <div className="flex items-center gap-3 rounded-2xl border border-dashed border-slate-200 bg-slate-50/50 p-3 opacity-70">
                      <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-slate-100/80">
                        <Target size={16} className="text-slate-300" />
                      </div>
                      <div className="min-w-0">
                        <p className="text-[10px] font-black text-slate-400 uppercase">차순위 목표 1</p>
                        <p className="text-xs font-bold text-slate-400">데이터가 없습니다</p>
                      </div>
                    </div>
                     <div className="hidden items-center gap-3 rounded-2xl border border-dashed border-slate-200 bg-slate-50/40 p-3 opacity-45 sm:flex">
                      <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-slate-100/80">
                        <Target size={16} className="text-slate-300" />
                      </div>
                      <div className="min-w-0">
                        <p className="text-[10px] font-black text-slate-400 uppercase">차순위 목표 2</p>
                        <p className="text-xs font-bold text-slate-400">데이터가 없습니다</p>
                      </div>
                    </div>
                  </>
                )}
              </div>
            </div>
            
            {hasPrimaryGoal && !hasDiagnosis && (
              <div className="mt-8 flex items-center gap-4 rounded-2xl bg-blue-50 p-4 text-sm font-medium text-slate-600 ring-1 ring-inset ring-blue-100">
                <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-white text-[#3182f6] shadow-sm">
                  <Sparkles size={18} />
                </div>
                <p>
                  목표 설정 완료. 이제 <span className="font-black text-[#3182f6]">학생부 PDF</span>를 업로드해
                  {` ${primaryGoal?.university}`} 진단을 시작하세요.
                </p>
              </div>
            )}
          </div>
        </SurfaceCard>

        {/* Workflow Status */}
        <SectionCard title="워크플로 진행도" className="h-full p-6 sm:p-8">
          <div className="space-y-3">
            {workflowSteps.map((step) => (
              <div key={step.key} className="flex gap-4 rounded-2xl bg-slate-50/50 p-3 ring-1 ring-slate-100">
                <div className={`mt-1 flex h-6 w-6 shrink-0 items-center justify-center rounded-full border-2 ${
                  step.status === 'done' ? 'bg-[#3182f6] border-[#3182f6] text-white' : 
                  step.status === 'active' ? 'border-[#3182f6] text-[#3182f6]' : 'border-slate-200 text-slate-200'
                }`}>
                  {step.status === 'done' ? <CheckCircle2 size={14} strokeWidth={2.5} /> : <div className="h-1.5 w-1.5 rounded-full bg-current" />}
                </div>
                <div>
                  <h4 className={`text-sm font-black ${step.status === 'pending' ? 'text-slate-400' : 'text-slate-900'}`}>{step.title}</h4>
                  <p className="line-clamp-2 text-xs font-medium leading-relaxed text-slate-500">{step.description}</p>
                </div>
              </div>
            ))}
          </div>
        </SectionCard>
      </div>

      {/* Interest Cloud Section */}
      <motion.div
        initial={{ opacity: 0, y: 24 }}
        whileInView={{ opacity: 1, y: 0 }}
        viewport={{ once: true, amount: 0.1 }}
        transition={{ duration: 0.5 }}
      >
        <InterestCloud className="p-6 sm:p-8" />
      </motion.div>

      {/* Action Plan / Next Step Section */}
      <motion.div
        id="action-plan"
        initial={{ opacity: 0, y: 24 }}
        whileInView={{ opacity: 1, y: 0 }}
        viewport={{ once: true, amount: 0.1 }}
        transition={{ duration: 0.5 }}
      >
        <SectionCard 
          title="맞춤형 액션 플랜" 
          subtitle="진단 기반 추천 퀘스트"
          badge={blueprint ? "AI 추천 가동 중" : "준비 중"}
          className="p-6 sm:p-8"
        >
          {isLoadingBlueprint ? (
            <div className="flex h-64 flex-col items-center justify-center gap-4 text-slate-400">
              <div className="h-8 w-8 animate-spin rounded-full border-4 border-[#3182f6] border-t-transparent" />
              <p className="text-sm font-bold">합격 가능성을 분석하여 퀘스트를 생성하고 있습니다...</p>
            </div>
          ) : blueprint ? (
            <div className="space-y-8">
              <div>
                <h3 className="mb-6 flex items-center gap-2 text-xl font-black text-[#191f28]">
                  <Zap size={20} className="text-[#ff9c20]" fill="currentColor" />
                  최우선 퀘스트
                </h3>
                <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
                  {blueprint.priority_quests.map(quest => (
                    <QuestCard key={quest.id} quest={quest} onStart={handleStartQuest} isStarting={startingQuestId === quest.id} />
                  ))}
                </div>
              </div>

              <div className="space-y-6 border-t border-slate-100 pt-6">
                <h3 className="text-xl font-black text-[#191f28]">과목별 탐구 플랜</h3>
                {blueprint.subject_groups.map(group => (
                  <div key={group.name} className="space-y-4">
                    <button 
                      onClick={() => setOpenSubjectGroups(prev => ({ ...prev, [group.name]: !prev[group.name] }))}
                      className="flex w-full items-center justify-between rounded-2xl border border-slate-100 bg-[#f9fafb] p-4 transition-colors hover:bg-slate-50"
                    >
                      <div className="flex items-center gap-3">
                        <School size={18} className="text-[#4e5968]" />
                        <span className="font-black text-[#333d4b]">{group.name}</span>
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
              description={blueprintError || "목표 설정과 진단을 완료하면 퀘스트가 생성됩니다."}
              actionLabel={nextAction.primaryLabel}
              onAction={nextAction.onPrimary}
              icon={<Target size={32} className="text-slate-300" />}
            />
          )}
        </SectionCard>
      </motion.div>
    </div>
  );
}
