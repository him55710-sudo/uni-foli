import React, { useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { motion } from 'motion/react';
import {
  ArrowRight,
  BarChart3,
  Compass,
  PlayCircle,
  School,
  Sparkles,
  Target,
  Zap,
} from 'lucide-react';
import toast from 'react-hot-toast';
import { DiagnosisModal } from '../components/DiagnosisModal';
import { OnboardingModal } from '../components/OnboardingModal';
import { useAuth } from '../contexts/AuthContext';
import { api } from '../lib/api';
import { type QuestStartPayload, saveQuestStart } from '../lib/questStart';

const DIAGNOSIS_STORAGE_KEY = 'polio_last_diagnosis';

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

function QuestCard({
  quest,
  onStart,
  isStarting,
}: {
  quest: BlueprintQuest;
  onStart: (quest: BlueprintQuest) => void;
  isStarting: boolean;
}) {
  return (
    <div className="flex h-full flex-col rounded-[28px] border border-slate-200 bg-white p-6 shadow-sm">
      <div className="mb-4 flex flex-wrap items-center gap-2">
        <span className="rounded-full border border-slate-200 bg-slate-50 px-3 py-1 text-xs font-black text-slate-600">
          {quest.subject}
        </span>
        <span className={`rounded-full border px-3 py-1 text-xs font-black ${difficultyTone(quest.difficulty)}`}>
          {quest.difficulty.toUpperCase()}
        </span>
        <span className={`rounded-full border px-3 py-1 text-xs font-black ${statusTone(quest.status)}`}>
          {quest.status}
        </span>
      </div>

      <h3 className="mb-3 break-keep text-xl font-extrabold leading-snug text-slate-800">{quest.title}</h3>
      <p className="mb-4 text-sm font-medium leading-relaxed text-slate-600">{quest.summary}</p>

      <div className="mb-4 rounded-2xl border border-blue-100 bg-blue-50 p-4">
        <p className="mb-1 text-xs font-black uppercase tracking-[0.18em] text-blue-500">Why This Matters</p>
        <p className="text-sm font-medium leading-relaxed text-blue-900">{quest.why_this_matters}</p>
      </div>

      <div className="mb-4 rounded-2xl border border-emerald-100 bg-emerald-50 p-4">
        <p className="mb-1 text-xs font-black uppercase tracking-[0.18em] text-emerald-600">Expected Record Impact</p>
        <p className="text-sm font-medium leading-relaxed text-emerald-900">{quest.expected_record_impact}</p>
      </div>

      <div className="mt-auto flex items-center justify-between gap-4">
        <div>
          <p className="text-xs font-black uppercase tracking-[0.18em] text-slate-400">Recommended Output</p>
          <p className="text-sm font-bold text-slate-700">{quest.recommended_output_type}</p>
        </div>
        <button
          type="button"
          onClick={() => onStart(quest)}
          disabled={isStarting}
          className="inline-flex items-center gap-2 rounded-2xl bg-slate-900 px-4 py-3 text-sm font-black text-white transition-colors hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-60"
        >
          {isStarting ? '시작 중...' : '퀘스트 시작'}
          <PlayCircle size={16} />
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
  const [stats, setStats] = useState<UserStats>({
    report_count: 0,
    level: '로딩 중',
    completion_rate: 0,
  });
  const [profile, setProfile] = useState<UserProfile | null>(null);
  const [storedDiagnosis, setStoredDiagnosis] = useState<StoredDiagnosis | null>(null);
  const [blueprint, setBlueprint] = useState<CurrentBlueprintResponse | null>(null);
  const [blueprintError, setBlueprintError] = useState<string | null>(null);

  useEffect(() => {
    setStoredDiagnosis(readStoredDiagnosis());
  }, []);

  useEffect(() => {
    if (!user && !isGuestSession) return;

    api.get<UserStats>('/api/v1/projects/user/stats')
      .then((data) => setStats(data))
      .catch((error) => {
        console.error('Failed to load stats:', error);
        setStats({
          report_count: 0,
          level: isGuestSession ? '게스트 모드' : '새로 시작',
          completion_rate: 0,
        });
      });

    api.get<UserProfile>('/api/v1/users/me')
      .then((data) => {
        setProfile(data);
        if (!data.target_university || !data.target_major) {
          setIsOnboardingOpen(true);
        }
      })
      .catch((error) => {
        console.error('Failed to load user profile:', error);
      });
  }, [user, isGuestSession]);

  useEffect(() => {
    if (!user && !isGuestSession) return;

    setIsLoadingBlueprint(true);
    setBlueprintError(null);

    api.get<CurrentBlueprintResponse>('/api/v1/blueprints/current', {
      params: storedDiagnosis?.projectId ? { project_id: storedDiagnosis.projectId } : undefined,
    })
      .then((data) => {
        setBlueprint(data);
      })
      .catch((error) => {
        console.error('Failed to load blueprint:', error);
        const normalized = error as { response?: { status?: number; data?: { detail?: string } } };
        if (normalized.response?.status === 404) {
          setBlueprint(null);
          return;
        }
        setBlueprint(null);
        setBlueprintError(normalized.response?.data?.detail || '블루프린트를 불러오지 못했습니다.');
      })
      .finally(() => {
        setIsLoadingBlueprint(false);
      });
  }, [user, isGuestSession, storedDiagnosis?.projectId]);

  const handleSaveTargets = async (payload: { targetUniversity: string; targetMajor: string }) => {
    setIsSavingProfile(true);
    const loadingId = toast.loading('목표 정보를 저장하고 있습니다...');
    try {
      const data = await api.patch<UserProfile>('/api/v1/users/me/targets', {
        target_university: payload.targetUniversity,
        target_major: payload.targetMajor,
      });
      setProfile(data);
      setIsOnboardingOpen(false);
      toast.success('목표 대학과 전공을 저장했습니다.', { id: loadingId });
    } catch (error) {
      console.error('Failed to save targets:', error);
      toast.error('목표 정보를 저장하지 못했습니다.', { id: loadingId });
    } finally {
      setIsSavingProfile(false);
    }
  };

  const handleCloseDiagnosis = () => {
    setIsDiagnosisOpen(false);
    setStoredDiagnosis(readStoredDiagnosis());
  };

  const handleStartQuest = async (quest: BlueprintQuest) => {
    setStartingQuestId(quest.id);
    const loadingId = toast.loading('퀘스트를 시작하는 중입니다...');
    try {
      const payload = await api.post<QuestStartPayload>(`/api/v1/quests/${quest.id}/start`);
      saveQuestStart(payload);
      toast.success('워크샵 시작 시드를 준비했습니다.', { id: loadingId });
      navigate(`/workshop/${payload.project_id}?major=${encodeURIComponent(payload.target_major || quest.subject)}`, {
        state: { questStart: payload },
      });
    } catch (error) {
      console.error('Failed to start quest:', error);
      toast.error('퀘스트를 시작하지 못했습니다.', { id: loadingId });
    } finally {
      setStartingQuestId(null);
    }
  };

  const roadmapCards = useMemo(() => {
    const majorLabel = blueprint?.target_major || profile?.target_major || storedDiagnosis?.major || '목표 전공';
    const priorityQuests = blueprint?.priority_quests ?? [];

    return [
      {
        icon: Compass,
        title: '1단계: 진단 해석',
        description: blueprint?.headline || storedDiagnosis?.diagnosis.headline || `${majorLabel} 기준으로 현재 기록의 빈 구간을 먼저 확인합니다.`,
      },
      {
        icon: Target,
        title: '2단계: 우선 보완',
        description: priorityQuests[0]?.title || storedDiagnosis?.diagnosis.recommended_focus || '이번 학기 안에 끝낼 수 있는 가장 좁은 활동부터 시작합니다.',
      },
      {
        icon: BarChart3,
        title: '3단계: 기록 반영',
        description: priorityQuests[0]?.expected_record_impact || '세특에 남길 수 있는 관찰, 비교, 반성 포인트까지 정리합니다.',
      },
    ];
  }, [blueprint, profile?.target_major, storedDiagnosis]);

  return (
    <div className="mx-auto max-w-6xl px-4 pb-16 sm:px-6 lg:px-8">
      <motion.section
        initial={{ opacity: 0, y: 24 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.45, ease: 'easeOut' }}
        className="relative overflow-hidden rounded-[36px] border border-slate-200 bg-white px-6 py-8 shadow-sm sm:px-8 sm:py-10"
      >
        <div className="absolute right-0 top-0 h-48 w-48 rounded-full bg-blue-100/70 blur-3xl" />
        <div className="relative z-10">
          <div className="mb-4 inline-flex items-center gap-2 rounded-full border border-blue-200 bg-blue-50 px-4 py-2 text-xs font-black uppercase tracking-[0.24em] text-blue-600">
            <Sparkles size={14} />
            Action Blueprint
          </div>

          <div className="grid gap-6 lg:grid-cols-[1.4fr_0.9fr]">
            <div>
              <h1 className="mb-4 break-keep text-4xl font-black leading-tight tracking-tight text-slate-900 sm:text-5xl">
                진단에서 끝내지 않고,
                <br />
                이번 학기 실행 퀘스트까지 연결합니다.
              </h1>
              <p className="max-w-2xl break-keep text-base font-medium leading-relaxed text-slate-600 sm:text-lg">
                Polio의 차별점은 진단 결과를 바로 눌러 시작할 수 있는 액션 블루프린트로 바꾸는 것입니다.
                진단 후에는 과목별 보완 퀘스트와 기대되는 세특 효과까지 한 화면에서 확인할 수 있습니다.
              </p>

              <div className="mt-8 flex flex-col gap-3 sm:flex-row">
                <button
                  type="button"
                  onClick={() => setIsDiagnosisOpen(true)}
                  className="inline-flex items-center justify-center gap-2 rounded-2xl bg-slate-900 px-6 py-4 text-base font-black text-white transition-colors hover:bg-slate-800"
                >
                  진단 실행
                  <ArrowRight size={18} />
                </button>
                <button
                  type="button"
                  onClick={() => {
                    document.getElementById('action-blueprint')?.scrollIntoView({ behavior: 'smooth', block: 'start' });
                  }}
                  className="inline-flex items-center justify-center gap-2 rounded-2xl border border-slate-200 bg-slate-50 px-6 py-4 text-base font-black text-slate-700 transition-colors hover:bg-slate-100"
                >
                  블루프린트 보기
                  <Zap size={18} />
                </button>
              </div>

              {storedDiagnosis?.savedAt ? (
                <p className="mt-5 text-sm font-bold text-slate-500">
                  최근 진단 반영 시각: {new Date(storedDiagnosis.savedAt).toLocaleString()}
                </p>
              ) : null}
            </div>

            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-1">
              <div className="rounded-[28px] border border-slate-200 bg-slate-50 p-5">
                <p className="mb-2 text-xs font-black uppercase tracking-[0.18em] text-slate-400">Current Track</p>
                <div className="flex items-start gap-3">
                  <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-blue-100 text-blue-600">
                    <School size={20} />
                  </div>
                  <div>
                    <p className="text-lg font-black text-slate-900">
                      {profile?.target_university || '목표 대학 미설정'}
                    </p>
                    <p className="text-sm font-bold text-slate-500">
                      {profile?.target_major || storedDiagnosis?.major || '목표 전공 미설정'}
                    </p>
                  </div>
                </div>
              </div>

              <div className="rounded-[28px] border border-slate-200 bg-slate-50 p-5">
                <p className="mb-2 text-xs font-black uppercase tracking-[0.18em] text-slate-400">Progress</p>
                <p className="text-3xl font-black text-slate-900">{stats.completion_rate}%</p>
                <p className="mt-1 text-sm font-bold text-slate-500">
                  보고서 {stats.report_count}개 · 상태 {stats.level}
                </p>
                <div className="mt-4 h-3 rounded-full bg-white shadow-inner">
                  <div
                    className="h-full rounded-full bg-gradient-to-r from-blue-500 to-cyan-400 transition-all duration-700"
                    style={{ width: `${Math.max(stats.completion_rate, 6)}%` }}
                  />
                </div>
              </div>
            </div>
          </div>
        </div>
      </motion.section>

      <motion.section
        id="action-blueprint"
        initial={{ opacity: 0, y: 24 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.45, delay: 0.08, ease: 'easeOut' }}
        className="mt-10"
      >
        <div className="mb-6 flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <p className="mb-2 text-xs font-black uppercase tracking-[0.24em] text-blue-600">Blueprint</p>
            <h2 className="text-3xl font-black text-slate-900">이번 학기 액션 블루프린트</h2>
            <p className="mt-2 max-w-3xl text-sm font-medium leading-relaxed text-slate-500 sm:text-base">
              진단 결과를 바로 실행 가능한 퀘스트 카드로 바꿨습니다. 우선순위가 높은 퀘스트부터 눌러
              워크샵으로 들어가면 starter choices가 즉시 준비됩니다.
            </p>
          </div>
          {blueprint?.created_at ? (
            <div className="rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm font-bold text-slate-600 shadow-sm">
              최신 생성일: {new Date(blueprint.created_at).toLocaleDateString()}
            </div>
          ) : null}
        </div>

        {isLoadingBlueprint ? (
          <div className="grid gap-6 lg:grid-cols-[1.2fr_0.8fr]">
            <div className="h-64 animate-pulse rounded-[28px] bg-slate-100" />
            <div className="h-64 animate-pulse rounded-[28px] bg-slate-100" />
          </div>
        ) : blueprint ? (
          <>
            <div className="grid gap-6 lg:grid-cols-[1.2fr_0.8fr]">
              <div className="rounded-[32px] border border-slate-200 bg-white p-8 shadow-sm">
                <div className="mb-4 inline-flex items-center gap-2 rounded-full border border-blue-200 bg-blue-50 px-4 py-2 text-xs font-black uppercase tracking-[0.18em] text-blue-600">
                  <Zap size={14} />
                  Blueprint Summary
                </div>
                <h3 className="break-keep text-2xl font-black leading-snug text-slate-900">{blueprint.headline}</h3>
                <p className="mt-4 text-sm font-medium leading-relaxed text-slate-600 sm:text-base">
                  {blueprint.recommended_focus}
                </p>
                <div className="mt-6 rounded-2xl border border-slate-200 bg-slate-50 p-5">
                  <p className="mb-2 text-xs font-black uppercase tracking-[0.18em] text-slate-400">Semester Priority</p>
                  <p className="text-base font-black text-slate-900">{blueprint.semester_priority_message}</p>
                </div>
              </div>

              <div className="rounded-[32px] border border-slate-200 bg-white p-8 shadow-sm">
                <div className="mb-4 inline-flex items-center gap-2 rounded-full border border-emerald-200 bg-emerald-50 px-4 py-2 text-xs font-black uppercase tracking-[0.18em] text-emerald-600">
                  <BarChart3 size={14} />
                  기대되는 세특 효과
                </div>
                <div className="space-y-3">
                  {blueprint.expected_record_effects.map((effect) => (
                    <div key={effect} className="rounded-2xl border border-emerald-100 bg-emerald-50 p-4 text-sm font-medium leading-relaxed text-emerald-900">
                      {effect}
                    </div>
                  ))}
                </div>
              </div>
            </div>

            <div className="mt-10">
              <div className="mb-5 flex items-center justify-between">
                <div>
                  <p className="mb-2 text-xs font-black uppercase tracking-[0.24em] text-red-500">Priority</p>
                  <h3 className="text-2xl font-black text-slate-900">이번 학기 우선 보완 과제</h3>
                </div>
              </div>
              <div className="grid gap-6 lg:grid-cols-3">
                {blueprint.priority_quests.map((quest) => (
                  <QuestCard
                    key={quest.id}
                    quest={quest}
                    onStart={handleStartQuest}
                    isStarting={startingQuestId === quest.id}
                  />
                ))}
              </div>
            </div>

            <div className="mt-10 grid gap-6 lg:grid-cols-[1.15fr_0.85fr]">
              <div className="rounded-[32px] border border-slate-200 bg-white p-8 shadow-sm">
                <p className="mb-2 text-xs font-black uppercase tracking-[0.24em] text-sky-600">By Subject</p>
                <h3 className="text-2xl font-black text-slate-900">과목별 추천 퀘스트</h3>
                <div className="mt-6 space-y-6">
                  {blueprint.subject_groups.map((group) => (
                    <div key={group.name}>
                      <div className="mb-3 inline-flex items-center rounded-full border border-slate-200 bg-slate-50 px-3 py-1 text-xs font-black text-slate-600">
                        {group.name}
                      </div>
                      <div className="grid gap-4 md:grid-cols-2">
                        {group.quests.map((quest) => (
                          <QuestCard
                            key={quest.id}
                            quest={quest}
                            onStart={handleStartQuest}
                            isStarting={startingQuestId === quest.id}
                          />
                        ))}
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              <div className="space-y-6">
                <div className="rounded-[32px] border border-slate-200 bg-white p-8 shadow-sm">
                  <p className="mb-2 text-xs font-black uppercase tracking-[0.24em] text-violet-600">By Activity</p>
                  <h3 className="text-2xl font-black text-slate-900">활동 유형별 시작점</h3>
                  <div className="mt-5 space-y-4">
                    {blueprint.activity_groups.map((group) => (
                      <div key={group.name} className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
                        <p className="text-sm font-black text-slate-800">{group.name}</p>
                        <p className="mt-2 text-sm font-medium leading-relaxed text-slate-600">
                          {group.quests[0]?.title}
                        </p>
                      </div>
                    ))}
                  </div>
                </div>

                <div className="rounded-[32px] border border-slate-200 bg-white p-8 shadow-sm">
                  <p className="mb-2 text-xs font-black uppercase tracking-[0.24em] text-slate-500">Execution Map</p>
                  <h3 className="text-2xl font-black text-slate-900">진단 후 실행 순서</h3>
                  <div className="mt-5 space-y-4">
                    {roadmapCards.map((card) => (
                      <div key={card.title} className="flex gap-4 rounded-2xl border border-slate-200 bg-slate-50 p-4">
                        <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-2xl bg-white text-slate-700 shadow-sm">
                          <card.icon size={20} />
                        </div>
                        <div>
                          <p className="text-sm font-black text-slate-900">{card.title}</p>
                          <p className="mt-1 text-sm font-medium leading-relaxed text-slate-600">{card.description}</p>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            </div>
          </>
        ) : (
          <div className="rounded-[32px] border border-dashed border-slate-300 bg-slate-50 p-10 text-center">
            <div className="mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-3xl bg-white text-slate-700 shadow-sm">
              <Target size={28} />
            </div>
            <h3 className="text-2xl font-black text-slate-900">아직 액션 블루프린트가 없습니다.</h3>
            <p className="mx-auto mt-3 max-w-2xl break-keep text-sm font-medium leading-relaxed text-slate-500 sm:text-base">
              학생부 진단을 먼저 실행하면, 결과를 과목별 보완 퀘스트와 워크샵 starter choices로 바꿔서
              바로 실행 가능한 구조를 생성합니다.
            </p>
            {blueprintError ? (
              <p className="mx-auto mt-4 max-w-2xl rounded-2xl border border-red-200 bg-red-50 px-4 py-3 text-sm font-bold text-red-700">
                {blueprintError}
              </p>
            ) : null}
            <button
              type="button"
              onClick={() => setIsDiagnosisOpen(true)}
              className="mt-6 inline-flex items-center gap-2 rounded-2xl bg-slate-900 px-6 py-4 text-base font-black text-white transition-colors hover:bg-slate-800"
            >
              진단하고 블루프린트 만들기
              <ArrowRight size={18} />
            </button>
          </div>
        )}
      </motion.section>

      <DiagnosisModal isOpen={isDiagnosisOpen} onClose={handleCloseDiagnosis} />
      <OnboardingModal
        isOpen={isOnboardingOpen}
        initialUniversity={profile?.target_university}
        initialMajor={profile?.target_major}
        isSubmitting={isSavingProfile}
        onSubmit={handleSaveTargets}
      />
    </div>
  );
}
