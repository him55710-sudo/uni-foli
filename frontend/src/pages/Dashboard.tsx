import React, { useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  ArrowRight,
  CheckCircle2,
  FolderOpen,
  PenTool,
  PlayCircle,
  School,
  Settings2,
  Sparkles,
  Target,
  TrendingUp,
  Zap,
} from 'lucide-react';
import toast from 'react-hot-toast';
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

type WorkflowStatus = 'done' | 'active' | 'pending';

interface WorkflowStep {
  key: string;
  title: string;
  description: string;
  status: WorkflowStatus;
  icon: React.ComponentType<{ size?: number; className?: string }>;
}

interface NextAction {
  eyebrow: string;
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
    return JSON.parse(raw) as StoredDiagnosis;
  } catch {
    return null;
  }
}

function difficultyTone(difficulty: string) {
  switch (difficulty) {
    case 'high':
      return 'bg-red-100 text-red-700 border-red-200';
    case 'medium':
      return 'bg-amber-100 text-amber-700 border-amber-200';
    default:
      return 'bg-emerald-100 text-emerald-700 border-emerald-200';
  }
}

function statusTone(status: string) {
  switch (status) {
    case 'IN_PROGRESS':
      return 'bg-blue-100 text-blue-700 border-blue-200';
    case 'COMPLETED':
      return 'bg-emerald-100 text-emerald-700 border-emerald-200';
    default:
      return 'bg-slate-100 text-slate-600 border-slate-200';
  }
}

function riskTone(risk: DiagnosisResultPayload['risk_level']) {
  switch (risk) {
    case 'danger':
      return 'bg-red-50 text-red-700 border-red-100';
    case 'warning':
      return 'bg-amber-50 text-amber-700 border-amber-100';
    default:
      return 'bg-emerald-50 text-emerald-700 border-emerald-100';
  }
}

function getLevelSummary(level: string, completionRate: number, reportCount: number, isGuestSession: boolean) {
  if (isGuestSession) {
    return {
      label: level,
      description: '게스트 세션에서는 현재 브라우저 기준으로 진행 상태가 유지됩니다.',
    };
  }

  if (completionRate >= 80 || reportCount >= 5) {
    return {
      label: level,
      description: '진단부터 작업실 실행까지 흐름이 안정적으로 이어지고 있어요.',
    };
  }

  if (completionRate >= 40) {
    return {
      label: level,
      description: '기록과 진단을 실행 단계로 옮기고 있는 구간입니다.',
    };
  }

  return {
    label: level,
    description: '준비 단계를 채울수록 다음 추천과 플랜 품질이 더 선명해집니다.',
  };
}

function WorkflowStepCard({ step, index }: { step: WorkflowStep; index: number }) {
  const Icon = step.icon;
  const tone =
    step.status === 'done'
      ? 'border-emerald-400/20 bg-emerald-400/10'
      : step.status === 'active'
        ? 'border-white/20 bg-white text-slate-900 shadow-lg shadow-slate-950/20'
        : 'border-white/10 bg-white/5';
  const numberTone =
    step.status === 'done'
      ? 'bg-emerald-400/20 text-emerald-200'
      : step.status === 'active'
        ? 'bg-blue-100 text-blue-600'
        : 'bg-white/10 text-slate-300';
  const labelTone =
    step.status === 'done'
      ? 'bg-emerald-400/20 text-emerald-100'
      : step.status === 'active'
        ? 'bg-blue-600 text-white'
        : 'bg-white/10 text-slate-300';
  const titleTone = step.status === 'active' ? 'text-slate-900' : 'text-white';
  const descriptionTone = step.status === 'active' ? 'text-slate-500' : 'text-slate-300';

  return (
    <div className={`rounded-[28px] border p-4 transition-all ${tone}`}>
      <div className="mb-3 flex items-center justify-between gap-3">
        <div className={`flex h-10 w-10 items-center justify-center rounded-2xl ${numberTone}`}>
          <Icon size={18} />
        </div>
        <span className={`rounded-full px-2.5 py-1 text-[10px] font-black ${labelTone}`}>
          {step.status === 'done' ? '완료' : step.status === 'active' ? '현재' : '대기'}
        </span>
      </div>
      <p className={`text-sm font-black ${titleTone}`}>{index}. {step.title}</p>
      <p className={`mt-2 text-xs font-medium leading-relaxed ${descriptionTone}`}>{step.description}</p>
    </div>
  );
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
  return (
    <div className="flex h-full flex-col rounded-[28px] border border-slate-200 bg-white p-6 shadow-sm transition-all hover:shadow-md">
      <div className="mb-4 flex flex-wrap items-center gap-2">
        <span className="rounded-full border border-slate-200 bg-slate-50 px-3 py-1 text-xs font-black text-slate-600">
          {quest.subject}
        </span>
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
        <button
          type="button"
          onClick={() => onStart(quest)}
          disabled={isStarting}
          className="inline-flex items-center gap-2 rounded-2xl bg-slate-900 px-4 py-3 text-sm font-black text-white transition-colors hover:bg-slate-800 disabled:opacity-60"
        >
          {isStarting ? '시작 중...' : '퀘스트 시작'} <PlayCircle size={16} />
        </button>
      </div>
    </div>
  );
});

export function Dashboard() {
  const navigate = useNavigate();
  const { user, isGuestSession } = useAuth();
  const [isOnboardingOpen, setIsOnboardingOpen] = useState(false);
  const [isSavingProfile, setIsSavingProfile] = useState(false);
  const [isLoadingBlueprint, setIsLoadingBlueprint] = useState(false);
  const [startingQuestId, setStartingQuestId] = useState<string | null>(null);
  const [stats, setStats] = useState<UserStats>({ report_count: 0, level: '로딩 중', completion_rate: 0 });
  const [profile, setProfile] = useState<UserProfile | null>(null);
  const [storedDiagnosis, setStoredDiagnosis] = useState<StoredDiagnosis | null>(null);
  const [blueprint, setBlueprint] = useState<CurrentBlueprintResponse | null>(null);
  const [blueprintError, setBlueprintError] = useState<string | null>(null);

  useEffect(() => {
    setStoredDiagnosis(readStoredDiagnosis());
  }, []);

  useEffect(() => {
    if (!user && !isGuestSession) return;

    api
      .get<UserStats>('/api/v1/projects/user/stats')
      .then(setStats)
      .catch(() =>
        setStats({
          report_count: 0,
          level: isGuestSession ? '게스트' : '신규',
          completion_rate: 0,
        }),
      );

    api
      .get<UserProfile>('/api/v1/users/me')
      .then(data => {
        setProfile(data);
        if (!data.target_university || !data.target_major) {
          setIsOnboardingOpen(true);
        }
      })
      .catch(console.error);
  }, [user, isGuestSession]);

  useEffect(() => {
    if (!user && !isGuestSession) return;

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
          setBlueprintError(normalized.response?.data?.detail || '데이터를 불러오지 못했습니다.');
        }
        setBlueprint(null);
      })
      .finally(() => setIsLoadingBlueprint(false));
  }, [user, isGuestSession, storedDiagnosis?.projectId]);

  const handleSaveTargets = async (payload: {
    targetUniversity: string;
    targetMajor: string;
    interestUniversities: string[];
  }) => {
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
    } catch {
      toast.error('저장에 실패했습니다.', { id: loadingId });
    } finally {
      setIsSavingProfile(false);
    }
  };

  const handleStartQuest = async (quest: BlueprintQuest) => {
    setStartingQuestId(quest.id);
    const loadingId = toast.loading('퀘스트를 시작합니다...');

    try {
      const payload = await api.post<QuestStartPayload>(`/api/v1/quests/${quest.id}/start`);
      saveQuestStart(payload);
      navigate(`/app/workshop/${payload.project_id}?major=${encodeURIComponent(payload.target_major || quest.subject)}`, {
        state: { questStart: payload },
      });
      toast.success('워크숍 준비 완료', { id: loadingId });
    } catch {
      toast.error('시작 실패', { id: loadingId });
    } finally {
      setStartingQuestId(null);
    }
  };

  const allGoals = useMemo(() => {
    const list: { university: string; major: string }[] = [];

    if (profile?.target_university) {
      list.push({ university: profile.target_university, major: profile.target_major || '' });
    }

    if (Array.isArray(profile?.interest_universities)) {
      profile.interest_universities.forEach(interest => {
        if (typeof interest !== 'string') return;
        const match = interest.match(/^(.+)\s\((.+)\)$/);
        if (match) {
          list.push({ university: match[1], major: match[2] });
        } else {
          list.push({ university: interest, major: '' });
        }
      });
    }

    return list;
  }, [profile]);

  const hasPrimaryGoal = Boolean(profile?.target_university && profile?.target_major);
  const hasDiagnosis = Boolean(storedDiagnosis?.projectId);
  const hasBlueprint = Boolean(blueprint);
  const primaryQuest = blueprint?.priority_quests[0] ?? null;
  const levelSummary = useMemo(
    () => getLevelSummary(stats.level, stats.completion_rate, stats.report_count, isGuestSession),
    [stats.level, stats.completion_rate, stats.report_count, isGuestSession],
  );

  const openWorkshop = () => {
    if (storedDiagnosis?.projectId) {
      navigate(`/app/workshop/${storedDiagnosis.projectId}`);
      return;
    }
    navigate('/app/workshop');
  };

  const workflowSteps = useMemo<WorkflowStep[]>(() => {
    if (!hasPrimaryGoal) {
      return [
        { key: 'targets', title: '목표 설정', description: '지원 대학과 전공을 정해 진단 기준을 맞춥니다.', status: 'active', icon: Target },
        { key: 'record', title: '생기부 업로드', description: '기록 PDF를 올리고 마스킹과 파싱 상태를 확인합니다.', status: 'pending', icon: FolderOpen },
        { key: 'diagnosis', title: 'AI 진단', description: '근거와 목표를 바탕으로 방향성과 보완점을 정리합니다.', status: 'pending', icon: TrendingUp },
        { key: 'workshop', title: '작업실', description: '초안 작성과 검토 흐름을 시작합니다.', status: 'pending', icon: PenTool },
      ];
    }

    if (!hasDiagnosis) {
      return [
        { key: 'targets', title: '목표 설정', description: `${profile?.target_university} · ${profile?.target_major}`, status: 'done', icon: CheckCircle2 },
        { key: 'record', title: '생기부 업로드', description: '기록 PDF를 연결해 마스킹과 파싱 상태를 준비합니다.', status: 'active', icon: FolderOpen },
        { key: 'diagnosis', title: 'AI 진단', description: '기록 업로드 후 진단과 근거 해석이 이어집니다.', status: 'pending', icon: TrendingUp },
        { key: 'workshop', title: '작업실', description: '진단 결과가 준비되면 바로 초안 작업으로 이동합니다.', status: 'pending', icon: PenTool },
      ];
    }

    if (!hasBlueprint) {
      return [
        { key: 'targets', title: '목표 설정', description: `${profile?.target_university} · ${profile?.target_major}`, status: 'done', icon: CheckCircle2 },
        { key: 'record', title: '생기부 업로드', description: '진단에 사용할 기록이 이미 연결되어 있습니다.', status: 'done', icon: CheckCircle2 },
        { key: 'diagnosis', title: 'AI 진단', description: storedDiagnosis?.diagnosis.headline || '진단 결과가 저장되어 있습니다.', status: 'done', icon: CheckCircle2 },
        { key: 'workshop', title: '작업실', description: '진단 결과를 바탕으로 초안과 질문 흐름을 시작합니다.', status: 'active', icon: PenTool },
      ];
    }

    return [
      { key: 'targets', title: '목표 설정', description: `${profile?.target_university} · ${profile?.target_major}`, status: 'done', icon: CheckCircle2 },
      { key: 'record', title: '생기부 업로드', description: '기록 기반 플랜 생성이 완료되었습니다.', status: 'done', icon: CheckCircle2 },
      { key: 'diagnosis', title: 'AI 진단', description: storedDiagnosis?.diagnosis.headline || '최신 진단이 준비되었습니다.', status: 'done', icon: CheckCircle2 },
      { key: 'workshop', title: '작업실', description: primaryQuest ? `우선 퀘스트 ${primaryQuest.title}부터 실행하면 흐름이 빨라집니다.` : '이번 학기 플랜을 바탕으로 바로 초안 작업을 시작합니다.', status: 'active', icon: PenTool },
    ];
  }, [hasBlueprint, hasDiagnosis, hasPrimaryGoal, primaryQuest, profile?.target_major, profile?.target_university, storedDiagnosis]);

  const stepProgressLabel = useMemo(() => {
    const progressedCount =
      workflowSteps.filter(step => step.status === 'done').length +
      (workflowSteps.some(step => step.status === 'active') ? 1 : 0);
    return `${progressedCount}/4 단계 확인`;
  }, [workflowSteps]);

  const nextAction = useMemo<NextAction>(() => {
    if (!hasPrimaryGoal) {
      return {
        eyebrow: 'STEP 1 · 목표 설정',
        title: '목표 대학과 전공부터 정리하세요.',
        description: '지원 방향이 잡혀야 진단 기준, 퀘스트 추천, 작업실 흐름이 같은 축에서 이어집니다.',
        primaryLabel: '목표 설정하기',
        onPrimary: () => setIsOnboardingOpen(true),
        secondaryLabel: 'AI 진단 화면 보기',
        onSecondary: () => navigate('/app/diagnosis'),
      };
    }

    if (!hasDiagnosis) {
      return {
        eyebrow: 'STEP 2 · 생기부 업로드',
        title: '생활기록부를 연결해 진단 준비를 시작하세요.',
        description: '먼저 기록을 올리면 마스킹과 파싱 상태를 확인하면서 다음 단계로 자연스럽게 넘어갈 수 있습니다.',
        primaryLabel: '생기부 업로드',
        onPrimary: () => navigate('/app/record'),
        secondaryLabel: 'AI 진단으로 이동',
        onSecondary: () => navigate('/app/diagnosis'),
      };
    }

    if (!hasBlueprint) {
      return {
        eyebrow: 'STEP 4 · 작업실 시작',
        title: '진단 결과를 바탕으로 작업실을 열어보세요.',
        description: '저장된 진단을 기준으로 초안 작성, 질문 정리, 근거 검토를 바로 이어갈 수 있습니다.',
        primaryLabel: '작업실 열기',
        onPrimary: openWorkshop,
        secondaryLabel: 'AI 진단 다시 보기',
        onSecondary: () => navigate('/app/diagnosis'),
      };
    }

    if (primaryQuest) {
      return {
        eyebrow: 'NOW · 가장 중요한 퀘스트',
        title: `이번 주 우선 과제는 "${primaryQuest.title}"입니다.`,
        description: '가장 먼저 해결하면 이번 학기 플랜 전체 흐름과 생기부 반영 효과를 빠르게 확보할 수 있습니다.',
        primaryLabel: '퀘스트 시작',
        onPrimary: () => { void handleStartQuest(primaryQuest); },
        secondaryLabel: '전체 플랜 보기',
        onSecondary: () => document.getElementById('research-plan')?.scrollIntoView({ behavior: 'smooth' }),
      };
    }

    return {
      eyebrow: 'NOW · 작업 이어가기',
      title: '이번 학기 플랜을 바탕으로 초안을 계속 다듬어보세요.',
      description: '작업실에서 근거 기반 초안 작성과 검토 흐름을 이어갈 수 있습니다.',
      primaryLabel: '작업실 열기',
      onPrimary: openWorkshop,
      secondaryLabel: '플랜 보기',
      onSecondary: () => document.getElementById('research-plan')?.scrollIntoView({ behavior: 'smooth' }),
    };
  }, [hasBlueprint, hasDiagnosis, hasPrimaryGoal, handleStartQuest, navigate, openWorkshop, primaryQuest]);

  const planStateTitle = hasBlueprint ? '현재 플랜 상태' : hasDiagnosis ? '진단은 완료됨' : '플랜 대기 중';
  const planStateDescription = hasBlueprint
    ? `우선 퀘스트 ${blueprint?.priority_quests.length ?? 0}개가 준비되어 있습니다. 이번 학기 우선순위를 바로 실행할 수 있어요.`
    : hasDiagnosis
      ? '최신 진단은 준비되어 있고, 작업실에서 초안 흐름을 바로 시작할 수 있습니다.'
      : '진단 전에는 플랜 카드가 비어 있는 것이 정상입니다. 먼저 목표와 기록부터 연결해 주세요.';

  return (
    <div className="mx-auto max-w-6xl px-4 pb-16 sm:px-6 lg:px-8">
      <div className="space-y-6">
        <section className="grid gap-6 lg:grid-cols-[1.18fr_0.82fr]">
          <div className="rounded-[40px] border border-slate-800 bg-slate-900 p-8 text-white shadow-2xl shadow-slate-900/10 sm:p-10">
            <div className="flex flex-wrap items-start justify-between gap-4">
              <div className="max-w-2xl">
                <p className="text-[11px] font-black uppercase tracking-[0.24em] text-blue-300">{nextAction.eyebrow}</p>
                <h1 className="mt-4 break-keep text-3xl font-black leading-tight text-white sm:text-4xl">{nextAction.title}</h1>
                <p className="mt-4 max-w-2xl text-base font-medium leading-relaxed text-slate-300">{nextAction.description}</p>
              </div>
              <div className="rounded-[28px] border border-white/10 bg-white/5 px-5 py-4">
                <p className="text-[10px] font-black uppercase tracking-[0.22em] text-slate-400">FLOW</p>
                <p className="mt-2 text-xl font-black text-white">{stepProgressLabel}</p>
                <p className="mt-1 text-xs font-medium text-slate-300">목표 설정 → 생기부 업로드 → AI 진단 → 작업실</p>
              </div>
            </div>

            {isGuestSession ? (
              <div className="mt-6 flex flex-wrap items-center gap-3 rounded-[28px] border border-blue-400/20 bg-blue-400/10 px-4 py-3">
                <span className="rounded-full bg-white/10 px-3 py-1 text-[10px] font-black uppercase tracking-[0.18em] text-blue-100">Guest</span>
                <p className="text-sm font-medium text-blue-50">게스트 세션에서는 이 브라우저 기준으로 진행 상태가 유지됩니다.</p>
                <button onClick={() => navigate('/app/settings')} className="ml-auto inline-flex items-center gap-2 rounded-2xl border border-white/15 bg-white/10 px-4 py-2 text-sm font-black text-white transition-colors hover:bg-white/15">
                  Google 연결
                </button>
              </div>
            ) : null}

            <div className="mt-8 flex flex-wrap gap-3">
              <button onClick={nextAction.onPrimary} className="inline-flex items-center justify-center gap-2 rounded-2xl bg-white px-6 py-3.5 text-sm font-black text-slate-900 transition-transform hover:scale-[1.01]">
                {nextAction.primaryLabel} <ArrowRight size={18} />
              </button>
              {nextAction.secondaryLabel && nextAction.onSecondary ? (
                <button onClick={nextAction.onSecondary} className="inline-flex items-center justify-center gap-2 rounded-2xl border border-white/15 bg-white/5 px-6 py-3.5 text-sm font-black text-white transition-colors hover:bg-white/10">
                  {nextAction.secondaryLabel}
                </button>
              ) : null}
            </div>

            <div className="mt-8 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
              {workflowSteps.map((step, index) => (
                <WorkflowStepCard key={step.key} step={step} index={index + 1} />
              ))}
            </div>
          </div>

          <div className="space-y-6">
            <div className="rounded-[32px] border border-slate-200 bg-white p-6 shadow-sm">
              <div className="mb-4 flex items-start justify-between gap-4">
                <div>
                  <p className="text-[11px] font-black uppercase tracking-[0.2em] text-slate-400">목표 대학</p>
                  <h2 className="mt-2 text-xl font-black text-slate-900">현재 지원 방향</h2>
                </div>
                <button onClick={() => setIsOnboardingOpen(true)} className="rounded-2xl p-2 text-slate-400 transition-colors hover:text-blue-600">
                  <Settings2 size={18} />
                </button>
              </div>

              {allGoals.length > 0 ? (
                <>
                  <p className="mb-4 text-sm font-medium text-slate-500">
                    가장 위 목표가 진단과 플랜 생성의 기준이 됩니다. 현재 {allGoals.length}/6개가 정리되어 있습니다.
                  </p>
                  <div className="grid grid-cols-2 gap-3">
                    {allGoals.map((goal, index) => (
                      <div
                        key={`${goal.university}-${goal.major}-${index}`}
                        className={`rounded-2xl border p-3 shadow-sm transition-all ${index === 0 ? 'border-blue-100 bg-blue-50/80' : 'border-slate-100 bg-slate-50/70'}`}
                      >
                        <div className="mb-2 flex items-center gap-3">
                          <img
                            src={`${API_BASE_URL}/api/v1/assets/univ-logo?name=${encodeURIComponent(goal.university)}`}
                            className="h-10 w-10 object-contain"
                            alt="Logo"
                            onError={event => {
                              event.currentTarget.style.display = 'none';
                              event.currentTarget.nextElementSibling?.classList.remove('hidden');
                            }}
                          />
                          <div className="hidden h-10 w-10 items-center justify-center rounded-xl bg-white text-slate-400">
                            <School size={20} />
                          </div>
                          <span className={`rounded-full px-2 py-1 text-[10px] font-black ${index === 0 ? 'bg-blue-600 text-white' : 'bg-white text-slate-500'}`}>
                            {index === 0 ? '기준 목표' : `후보 ${index + 1}`}
                          </span>
                        </div>
                        <p className="truncate text-sm font-black text-slate-800">{goal.university}</p>
                        <p className="truncate text-[11px] font-bold text-slate-500">{goal.major || '전공 미정'}</p>
                      </div>
                    ))}
                  </div>
                </>
              ) : (
                <div className="rounded-[28px] border border-dashed border-slate-200 bg-slate-50/70 px-6 py-10 text-center">
                  <div className="mx-auto mb-4 flex h-14 w-14 items-center justify-center rounded-2xl bg-white text-slate-400 shadow-sm">
                    <School size={24} />
                  </div>
                  <h3 className="text-lg font-black text-slate-800">목표 대학이 아직 비어 있습니다.</h3>
                  <p className="mx-auto mt-2 max-w-sm text-sm font-medium leading-relaxed text-slate-500">
                    목표 대학과 전공을 먼저 정리하면 진단 기준과 다음 액션이 더 명확해집니다.
                  </p>
                  <button onClick={() => setIsOnboardingOpen(true)} className="mt-5 inline-flex items-center gap-2 rounded-2xl bg-slate-900 px-5 py-3 text-sm font-black text-white transition-colors hover:bg-slate-800">
                    목표 설정하기 <ArrowRight size={16} />
                  </button>
                </div>
              )}
            </div>

            <div className="rounded-[32px] border border-slate-200 bg-slate-900 p-6 text-white shadow-lg">
              <div className="flex items-start justify-between gap-4">
                <div>
                  <p className="text-[11px] font-black uppercase tracking-[0.2em] text-slate-400">진행 현황</p>
                  <p className="mt-3 text-4xl font-black">{stats.completion_rate}%</p>
                </div>
                <div className="rounded-2xl border border-white/10 bg-white/10 px-3 py-2 text-right">
                  <p className="text-[10px] font-black uppercase tracking-[0.18em] text-slate-300">현재 레벨</p>
                  <p className="mt-1 text-sm font-black text-white">{levelSummary.label}</p>
                </div>
              </div>
              <p className="mt-4 text-sm font-medium leading-relaxed text-slate-300">{levelSummary.description}</p>
              <div className="mt-5 h-3 overflow-hidden rounded-full bg-slate-800">
                <div style={{ width: `${stats.completion_rate}%` }} className="h-full rounded-full bg-blue-500" />
              </div>
              <div className="mt-4 flex items-center justify-between text-xs font-bold text-slate-400">
                <span>완료 보고서 {stats.report_count}개</span>
                <span>{stepProgressLabel}</span>
              </div>
            </div>
          </div>
        </section>

        <section className="rounded-[40px] border border-slate-200 bg-white p-8 shadow-sm sm:p-10">
          <div className="relative z-10 grid gap-8 lg:grid-cols-[1.05fr_0.95fr] lg:items-start">
            <div>
              <div className="mb-5 inline-flex items-center gap-2 rounded-full border border-blue-200 bg-blue-50 px-4 py-2 text-[11px] font-black uppercase tracking-[0.2em] text-blue-600">
                <Sparkles size={14} /> 현재 요약
              </div>
              <h2 className="max-w-2xl break-keep text-3xl font-black leading-tight tracking-tight text-slate-900 sm:text-4xl">
                지금 필요한 정보만
                <br />
                먼저 확인하면 됩니다.
              </h2>
              <p className="mt-4 max-w-2xl text-base font-medium leading-relaxed text-slate-500">
                다음 행동, 현재 플랜 상태, 최근 진단 요약만 먼저 보고 바로 이어가세요. 설명은 줄이고, 실행 흐름은 더 빨리 찾을 수 있게 정리했습니다.
              </p>
              <div className="mt-6 flex flex-wrap gap-3">
                <button onClick={nextAction.onPrimary} className="inline-flex items-center justify-center gap-2 rounded-2xl bg-slate-900 px-6 py-3.5 text-sm font-black text-white transition-colors hover:bg-black">
                  {nextAction.primaryLabel} <ArrowRight size={18} />
                </button>
                <button onClick={() => document.getElementById('research-plan')?.scrollIntoView({ behavior: 'smooth' })} className="inline-flex items-center justify-center gap-2 rounded-2xl border border-slate-200 bg-white px-6 py-3.5 text-sm font-black text-slate-700 transition-colors hover:bg-slate-50">
                  이번 학기 플랜 보기 <Zap size={18} />
                </button>
              </div>
            </div>

            <div className="grid gap-4 sm:grid-cols-2">
              <div className="rounded-[28px] border border-slate-200 bg-slate-50/70 p-5">
                <p className="text-[11px] font-black uppercase tracking-[0.18em] text-slate-400">{planStateTitle}</p>
                <h3 className="mt-3 text-xl font-black text-slate-900">
                  {hasBlueprint ? '이번 학기 실행 카드가 준비되었습니다.' : hasDiagnosis ? '작업실로 이어갈 준비가 끝났습니다.' : '진단 전 상태입니다.'}
                </h3>
                <p className="mt-3 text-sm font-medium leading-relaxed text-slate-500">{planStateDescription}</p>
              </div>

              <div className="rounded-[28px] border border-slate-200 bg-white p-5 shadow-sm">
                <div className="flex items-center justify-between gap-3">
                  <p className="text-[11px] font-black uppercase tracking-[0.18em] text-slate-400">최근 AI 진단</p>
                  {storedDiagnosis ? (
                    <span className={`rounded-full border px-2.5 py-1 text-[10px] font-black ${riskTone(storedDiagnosis.diagnosis.risk_level)}`}>
                      {storedDiagnosis.diagnosis.risk_level === 'safe' ? '안정' : storedDiagnosis.diagnosis.risk_level === 'warning' ? '보완 필요' : '근거 필요'}
                    </span>
                  ) : null}
                </div>
                <h3 className="mt-3 text-xl font-black leading-snug text-slate-900">
                  {storedDiagnosis ? storedDiagnosis.diagnosis.headline : '아직 저장된 진단 요약이 없습니다.'}
                </h3>
                <p className="mt-3 text-sm font-medium leading-relaxed text-slate-500">
                  {storedDiagnosis
                    ? storedDiagnosis.diagnosis.recommended_focus
                    : '생기부 업로드와 AI 진단을 마치면 여기에서 최근 방향성과 다음 보완 포인트를 다시 확인할 수 있어요.'}
                </p>
              </div>
            </div>
          </div>
        </section>

        <section id="research-plan" className="mt-16">
          <div className="mb-10">
            <p className="mb-2 text-xs font-black uppercase tracking-[0.24em] text-blue-600">ACTION PLAN</p>
            <h2 className="text-4xl font-black text-slate-900">이번 학기 탐구 플랜</h2>
            <p className="mt-3 max-w-3xl text-lg font-medium leading-relaxed text-slate-500">
              진단 결과를 바탕으로 설계된 맞춤형 퀘스트입니다. 우선순위 상단에 있는 과제부터 해결하면 생기부의 빈 구간이
              효율적으로 채워집니다.
            </p>
          </div>

          {isLoadingBlueprint ? (
            <div className="flex h-96 items-center justify-center rounded-[40px] border border-dashed border-slate-200 bg-slate-50">
              <div className="flex flex-col items-center gap-3">
                <div className="h-10 w-10 animate-spin rounded-full border-4 border-blue-600 border-t-transparent" />
                <p className="text-sm font-black text-slate-400">전략을 세우고 있습니다...</p>
              </div>
            </div>
          ) : blueprint ? (
            <div className="space-y-12">
              <div className="grid gap-8 lg:grid-cols-2">
                <div className="relative overflow-hidden rounded-[36px] border border-slate-200 bg-white p-10 shadow-sm">
                  <div className="absolute right-0 top-0 p-6 opacity-5">
                    <Zap size={120} />
                  </div>
                  <div className="mb-6 inline-flex items-center gap-2 rounded-full border border-blue-100 bg-blue-50 px-4 py-2 text-xs font-black text-blue-600">
                    전략 요약
                  </div>
                  <h3 className="text-2xl font-black leading-snug text-slate-900">{blueprint.headline}</h3>
                  <p className="mt-4 text-base font-medium leading-relaxed text-slate-600">{blueprint.recommended_focus}</p>
                  <div className="mt-8 rounded-[24px] border border-slate-100 bg-slate-50 p-6">
                    <p className="mb-2 text-[11px] font-black uppercase text-slate-400">이번 학기 핵심 우선순위</p>
                    <p className="text-base font-black text-slate-800">{blueprint.semester_priority_message}</p>
                  </div>
                </div>

                <div className="relative overflow-hidden rounded-[36px] bg-slate-900 p-10 text-white">
                  <div className="mb-6 inline-flex items-center gap-2 rounded-full border border-emerald-400/20 bg-white/10 px-4 py-2 text-xs font-black text-emerald-400">
                    생기부 기대 효과
                  </div>
                  <div className="space-y-4">
                    {blueprint.expected_record_effects.map((effect, index) => (
                      <div key={`${effect}-${index}`} className="flex items-start gap-4 rounded-2xl border border-white/10 bg-white/5 p-4">
                        <div className="mt-1 h-1.5 w-1.5 flex-shrink-0 rounded-full bg-emerald-400" />
                        <p className="text-sm font-medium leading-relaxed text-slate-300">{effect}</p>
                      </div>
                    ))}
                  </div>
                </div>
              </div>

              <div className="space-y-8">
                <div className="flex items-end justify-between gap-4">
                  <h3 className="text-2xl font-black text-slate-900">우선 보완 퀘스트</h3>
                </div>
                <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
                  {blueprint.priority_quests.map(quest => (
                    <QuestCard key={quest.id} quest={quest} onStart={handleStartQuest} isStarting={startingQuestId === quest.id} />
                  ))}
                </div>
              </div>

              <div className="rounded-[40px] border border-slate-200 bg-slate-50 p-10">
                <h3 className="mb-8 text-2xl font-black text-slate-900">모든 추천 퀘스트</h3>
                <div className="space-y-10">
                  {blueprint.subject_groups.map(group => (
                    <div key={group.name} className="space-y-6">
                      <div className="flex items-center gap-3">
                        <span className="h-0.5 w-6 rounded-full bg-blue-500" />
                        <span className="text-sm font-black text-slate-800">{group.name}</span>
                      </div>
                      <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
                        {group.quests.map(quest => (
                          <QuestCard key={quest.id} quest={quest} onStart={handleStartQuest} isStarting={startingQuestId === quest.id} />
                        ))}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          ) : (
            <div className="rounded-[40px] border border-dashed border-slate-300 bg-white p-10 text-center shadow-sm sm:p-16">
              <div className="mx-auto mb-6 flex h-20 w-20 items-center justify-center rounded-[28px] bg-slate-100 text-slate-400">
                <Target size={36} />
              </div>
              <p className="text-[11px] font-black uppercase tracking-[0.22em] text-blue-600">EMPTY STATE</p>
              <h3 className="mx-auto mt-3 max-w-2xl text-3xl font-black leading-tight text-slate-900">
                플랜이 비어 있어도, 다음 단계는 한눈에 보여야 합니다.
              </h3>
              <p className="mx-auto mt-4 max-w-2xl text-lg font-medium leading-relaxed text-slate-500">
                먼저 해야 할 일은 이미 위에서 정리되어 있습니다. 목표 설정, 생기부 업로드, AI 진단을 마치면 이 영역이 이번
                학기 실행 카드로 자연스럽게 바뀝니다.
              </p>

              <div className="mx-auto mt-8 grid max-w-4xl gap-3 sm:grid-cols-2 xl:grid-cols-4">
                {workflowSteps.map((step, index) => (
                  <div key={`${step.key}-empty`} className="rounded-[24px] border border-slate-200 bg-slate-50/70 p-4 text-left">
                    <div className="mb-3 flex items-center gap-2">
                      <div className="flex h-8 w-8 items-center justify-center rounded-2xl bg-white text-slate-500 shadow-sm">
                        <step.icon size={16} />
                      </div>
                      <span className="text-xs font-black text-slate-400">STEP {index + 1}</span>
                    </div>
                    <p className="text-sm font-black text-slate-800">{step.title}</p>
                    <p className="mt-2 text-xs font-medium leading-relaxed text-slate-500">{step.description}</p>
                  </div>
                ))}
              </div>

              {blueprintError ? (
                <div className="mx-auto mt-6 max-w-2xl rounded-[24px] border border-amber-200 bg-amber-50 px-5 py-4 text-left">
                  <p className="text-[11px] font-black uppercase tracking-[0.18em] text-amber-700">Support note</p>
                  <p className="mt-2 text-sm font-medium leading-relaxed text-amber-900">
                    플랜 데이터를 바로 불러오지 못했습니다. {blueprintError}
                  </p>
                </div>
              ) : null}

              <button onClick={nextAction.onPrimary} className="mt-8 inline-flex items-center gap-2 rounded-2xl bg-blue-600 px-8 py-4 text-base font-black text-white transition-all hover:scale-[1.02] hover:bg-blue-700">
                {nextAction.primaryLabel} <ArrowRight size={20} />
              </button>
            </div>
          )}
        </section>
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
