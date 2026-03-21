import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { motion } from 'motion/react';
import { ArrowRight, BarChart3, Compass, School, Telescope, Zap } from 'lucide-react';
import toast from 'react-hot-toast';
import { useAuth } from '../contexts/AuthContext';
import { DiagnosisModal } from '../components/DiagnosisModal';
import { OnboardingModal } from '../components/OnboardingModal';
import { api } from '../lib/api';

const trends = [
  { id: 1, icon: '📘', title: '컴공 전공자를 위한 AI 윤리 이슈', tag: '도서 추천' },
  { id: 2, icon: '🧭', title: '2026 수시 핵심 변화 요약', tag: '입시 이슈' },
  { id: 3, icon: '🧪', title: '합격생 사례로 보는 탐구 보고서 구조', tag: '합격 가이드' },
  { id: 4, icon: '💡', title: '기후·경제 융합 탐구 주제 10선', tag: '탐구 주제' },
];

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

interface DiagnosisSubject {
  name: string;
  status: 'safe' | 'warning' | 'danger';
  feedback: string;
}

interface StoredDiagnosis {
  major: string;
  savedAt: string;
  diagnosis: {
    overall: {
      score: number;
      summary: string;
    };
    subjects: DiagnosisSubject[];
    prescription: {
      message: string;
      recommendedTopic: string;
    };
  };
}

interface RoadmapStage {
  year: string;
  phase: string;
  icon: React.ComponentType<{ size?: number }>;
  topic: string;
  description: string;
  accentClass: string;
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

export function Dashboard() {
  const navigate = useNavigate();
  const { user, isGuestSession } = useAuth();
  const [isDiagnosisOpen, setIsDiagnosisOpen] = useState(false);
  const [isOnboardingOpen, setIsOnboardingOpen] = useState(false);
  const [isSavingProfile, setIsSavingProfile] = useState(false);
  const [stats, setStats] = useState<UserStats>({
    report_count: 0,
    level: '로딩 중...',
    completion_rate: 0,
  });
  const [profile, setProfile] = useState<UserProfile | null>(null);
  const [storedDiagnosis, setStoredDiagnosis] = useState<StoredDiagnosis | null>(null);

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
          level: isGuestSession ? '게스트 모드' : '새로운 시작',
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

  const handleSaveTargets = async (payload: { targetUniversity: string; targetMajor: string }) => {
    setIsSavingProfile(true);
    const loadingId = toast.loading('목표 정보를 저장하는 중입니다...');
    try {
      const data = await api.patch<UserProfile>('/api/v1/users/me/targets', {
        target_university: payload.targetUniversity,
        target_major: payload.targetMajor,
      });
      setProfile(data);
      setIsOnboardingOpen(false);
      toast.success('목표 대학과 전공이 저장되었습니다.', { id: loadingId });
    } catch (error) {
      console.error('Failed to save targets:', error);
      toast.error('목표 정보 저장에 실패했습니다. 잠시 후 다시 시도해주세요.', { id: loadingId });
    } finally {
      setIsSavingProfile(false);
    }
  };

  const roadmapMajor = profile?.target_major || storedDiagnosis?.major || '희망 전공';
  const weakestSubject = storedDiagnosis?.diagnosis.subjects.find((subject) => subject.status !== 'safe')?.name;
  const roadmapStages: RoadmapStage[] = [
    {
      year: '1학년',
      phase: '기초 탐색',
      icon: Compass,
      topic: `${roadmapMajor} 입문 개념 지도 만들기`,
      description: '학교 활동 전반에서 관심 키워드를 좁히고, 세특 기반 질문을 축적합니다.',
      accentClass: 'from-sky-500 to-cyan-400',
    },
    {
      year: '2학년',
      phase: '전공 심화',
      icon: Telescope,
      topic: storedDiagnosis?.diagnosis.prescription.recommendedTopic || `${roadmapMajor} 심화 비교 분석 탐구`,
      description: storedDiagnosis?.diagnosis.overall.summary || '진단 결과를 바탕으로 전공 적합성을 강하게 드러낼 중심 주제를 만듭니다.',
      accentClass: 'from-violet-500 to-indigo-400',
    },
    {
      year: '3학년',
      phase: '융합/데이터 분석',
      icon: BarChart3,
      topic: weakestSubject
        ? `${weakestSubject} 데이터를 활용한 ${roadmapMajor} 융합 탐구`
        : `${roadmapMajor} 데이터 기반 확장 프로젝트`,
      description: '정량 분석과 시뮬레이션을 더해 최종 제출용 탐구 서사를 완성합니다.',
      accentClass: 'from-emerald-500 to-teal-400',
    },
  ];

  const handleCloseDiagnosis = () => {
    setIsDiagnosisOpen(false);
    setStoredDiagnosis(readStoredDiagnosis());
  };

  return (
    <div className="mx-auto max-w-6xl px-4 pb-12 sm:px-6 lg:px-8">
      <motion.div
        initial={{ opacity: 0, y: 30 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.6, ease: 'easeOut' }}
        className="mb-12 pt-8 text-center md:pt-12 md:text-left"
      >
        <div className="mb-6 inline-block">
          <div className="rounded-full border border-red-200 bg-gradient-to-r from-red-50 to-red-100/50 px-6 py-2.5 text-sm font-extrabold text-red-600 shadow-sm clay-card md:text-base">
            제출 마감 대비 집중 관리 모드
          </div>
        </div>

        <h1 className="mb-6 break-keep text-4xl font-extrabold leading-tight tracking-tight text-slate-800 md:text-5xl lg:text-6xl">
          내 학생부 탐구,
          <br className="hidden md:block" />
          <span className="bg-gradient-to-r from-blue-500 to-blue-400 bg-clip-text text-transparent">
            AI와 함께 제출용 보고서로 완성하기
          </span>
        </h1>

        <p className="mx-auto mb-10 max-w-2xl break-keep text-lg font-medium leading-relaxed text-slate-500 md:mx-0 md:text-xl">
          진단부터 워크숍, 내보내기까지 한 흐름으로 이어집니다. 오늘 작업을 바로 시작해보세요.
        </p>

        <div className="flex flex-col gap-4 md:flex-row md:items-center">
          <button
            onClick={() => setIsDiagnosisOpen(true)}
            className="group mx-auto flex w-full items-center justify-center gap-3 px-8 py-5 text-lg font-extrabold md:mx-0 md:w-auto clay-btn-primary shimmer"
          >
            무료로 전공 적합도 진단 받기
            <ArrowRight className="transition-transform group-hover:translate-x-1" />
          </button>

          {profile?.target_university && profile?.target_major ? (
            <div className="inline-flex items-center gap-3 rounded-2xl border border-slate-200 bg-white px-5 py-4 shadow-sm">
              <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-blue-50 text-blue-600">
                <School size={20} />
              </div>
              <div className="text-left">
                <p className="text-xs font-bold uppercase tracking-[0.2em] text-slate-400">Current Track</p>
                <p className="text-sm font-extrabold text-slate-800">
                  {profile.target_university} · {profile.target_major}
                </p>
              </div>
            </div>
          ) : null}
        </div>
      </motion.div>

      <div className="mb-16 grid grid-cols-1 gap-8 lg:grid-cols-3">
        <motion.div
          initial={{ opacity: 0, y: 30 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, delay: 0.2, ease: 'easeOut' }}
          className="relative flex flex-col justify-center overflow-hidden p-8 sm:p-10 lg:col-span-2 clay-card"
        >
          <div className="absolute -mr-20 -mt-20 h-64 w-64 rounded-full bg-blue-100/30 blur-3xl" />
          <div className="relative z-10">
            <div className="mb-8 flex items-center justify-between">
              <div>
                <h2 className="mb-2 text-2xl font-extrabold text-slate-800 sm:text-3xl">나의 작업 진행도</h2>
                <p className="text-lg font-medium text-slate-500">현재 상태: {stats.level}</p>
              </div>
              <div className="flex h-16 w-16 items-center justify-center rounded-3xl border border-white/50 bg-gradient-to-br from-yellow-50 to-yellow-100 text-4xl shadow-inner sm:h-20 sm:w-20">
                🌟
              </div>
            </div>

            <div className="space-y-4">
              <div className="flex justify-between text-sm font-extrabold text-slate-700 sm:text-base">
                <span>Lv.1</span>
                <span className="text-blue-600">
                  진행도 {stats.completion_rate}% · 작성 보고서 {stats.report_count}개
                </span>
              </div>
              <div className="h-8 w-full rounded-full border border-slate-200/50 bg-slate-100 p-1.5 shadow-inner sm:h-10">
                <div
                  className="relative h-full overflow-hidden rounded-full bg-gradient-to-r from-blue-400 to-blue-500 shadow-[inset_0_-2px_4px_rgba(0,0,0,0.1),0_2px_4px_rgba(59,130,246,0.3)] transition-all duration-1000"
                  style={{ width: `${Math.max(stats.completion_rate, 5)}%` }}
                >
                  <div className="absolute left-0 right-0 top-0 h-1/2 rounded-t-full bg-gradient-to-b from-white/40 to-transparent" />
                </div>
              </div>
            </div>
          </div>
        </motion.div>

        <motion.button
          type="button"
          initial={{ opacity: 0, y: 30 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, delay: 0.3, ease: 'easeOut' }}
          onClick={() => setIsDiagnosisOpen(true)}
          className="group flex cursor-pointer flex-col items-center justify-center p-8 text-center transition-colors hover:bg-blue-50/30 sm:p-10 clay-card"
        >
          <div className="mb-6 flex h-20 w-20 items-center justify-center rounded-3xl border border-white/50 bg-gradient-to-br from-mint/20 to-mint/10 text-mint shadow-inner transition-transform duration-300 group-hover:scale-110 sm:h-24 sm:w-24">
            <Zap size={40} />
          </div>
          <h3 className="mb-3 text-xl font-extrabold text-slate-800 sm:text-2xl">빠른 진단 시작</h3>
          <p className="text-sm font-medium leading-relaxed text-slate-500 sm:text-base">
            전공 입력과 PDF 업로드만 하면
            <br />
            바로 워크숍으로 연결됩니다.
          </p>
        </motion.button>
      </div>

      <motion.section
        initial={{ opacity: 0, y: 30 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.6, delay: 0.35, ease: 'easeOut' }}
        className="mb-16 overflow-hidden p-8 sm:p-10 clay-card"
      >
        <div className="mb-8 flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <p className="mb-2 text-xs font-black uppercase tracking-[0.3em] text-blue-500">Roadmap</p>
            <h2 className="text-2xl font-extrabold text-slate-800 sm:text-3xl">나만의 3개년 세특 로드맵</h2>
            <p className="mt-2 max-w-2xl text-sm font-medium leading-relaxed text-slate-500 sm:text-base">
              1회성 보고서가 아니라, 3년 동안 사정관이 읽게 될 스토리 라인을 지금부터 설계합니다.
            </p>
          </div>
          {storedDiagnosis?.savedAt ? (
            <div className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm font-bold text-slate-600">
              최근 진단 반영: {new Date(storedDiagnosis.savedAt).toLocaleDateString()}
            </div>
          ) : null}
        </div>

        <div className="relative">
          <div className="absolute left-6 top-6 bottom-6 hidden w-px bg-gradient-to-b from-blue-200 via-slate-200 to-emerald-200 lg:block" />
          <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
            {roadmapStages.map((stage, index) => (
              <div key={stage.year} className="relative rounded-[28px] border border-slate-200 bg-white p-6 shadow-sm">
                <div className={`mb-5 flex h-14 w-14 items-center justify-center rounded-3xl bg-gradient-to-br ${stage.accentClass} text-white shadow-lg`}>
                  <stage.icon size={24} />
                </div>
                <div className="mb-3 inline-flex items-center gap-2 rounded-full bg-slate-100 px-3 py-1 text-xs font-extrabold text-slate-600">
                  {stage.year}
                  <span className="text-slate-400">·</span>
                  {stage.phase}
                </div>
                <h3 className="mb-3 text-xl font-extrabold leading-snug text-slate-800">{stage.topic}</h3>
                <p className="text-sm font-medium leading-relaxed text-slate-500">{stage.description}</p>
                {index < roadmapStages.length - 1 ? (
                  <div className="mt-6 hidden items-center gap-2 text-sm font-extrabold text-slate-300 lg:flex">
                    다음 단계
                    <ArrowRight size={16} />
                  </div>
                ) : null}
              </div>
            ))}
          </div>
        </div>
      </motion.section>

      <motion.div
        initial={{ opacity: 0, y: 30 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.6, delay: 0.4, ease: 'easeOut' }}
      >
        <div className="mb-8 flex items-start justify-between gap-4 px-2 sm:items-center">
          <h2 className="break-keep text-2xl font-extrabold text-slate-800 sm:text-3xl">지금 참고하기 좋은 입시 트렌드</h2>
          <button
            onClick={() => navigate('/trends')}
            className="mt-1 flex shrink-0 items-center gap-1 whitespace-nowrap text-sm font-extrabold text-blue-500 transition-colors hover:text-blue-600 sm:mt-0 sm:text-base"
          >
            전체보기
            <ArrowRight size={16} />
          </button>
        </div>

        <div className="-mx-2 flex snap-x gap-6 overflow-x-auto px-2 pb-8 hide-scrollbar">
          {trends.map((trend) => (
            <button
              type="button"
              key={trend.id}
              onClick={() => {
                navigate('/trends');
                toast('트렌드 페이지에서 상세 자료를 확인하세요.', { icon: '📌' });
              }}
              className="group flex min-w-[280px] snap-start cursor-pointer flex-col p-8 text-left transition-colors hover:border-blue-200 md:min-w-[320px] clay-card"
            >
              <div className="mb-6 flex h-16 w-16 items-center justify-center rounded-3xl border border-white/50 bg-slate-50 text-4xl shadow-inner transition-transform duration-300 group-hover:-translate-y-2 sm:h-20 sm:w-20">
                {trend.icon}
              </div>
              <div className="mb-4 inline-block w-fit rounded-xl bg-slate-100 px-3 py-1.5 text-xs font-extrabold text-slate-600 sm:text-sm">
                {trend.tag}
              </div>
              <h3 className="text-lg font-extrabold leading-snug text-slate-800 transition-colors group-hover:text-blue-600 sm:text-xl">
                {trend.title}
              </h3>
            </button>
          ))}
        </div>
      </motion.div>

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
