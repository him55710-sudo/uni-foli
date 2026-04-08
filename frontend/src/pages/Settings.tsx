import React, { useEffect, useMemo, useState } from 'react';
import { CheckCircle2, LogOut, Mail, RefreshCw, ShieldCheck, Sparkles, Trash2, UserCircle2 } from 'lucide-react';
import toast from 'react-hot-toast';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { useAuthStore } from '../store/authStore';
import { api } from '../lib/api';
import { PageHeader, PrimaryButton, SecondaryButton, SectionCard, StatusBadge, SurfaceCard, WorkflowNotice } from '../components/primitives';
import { FileText, Info } from 'lucide-react';

interface UserSettings {
  autoSaveDrafts: boolean;
  compactView: boolean;
  notifyOnExport: boolean;
}

const SETTINGS_STORAGE_KEY = 'uni_foli_user_settings_v1';
const DEFAULT_SETTINGS: UserSettings = {
  autoSaveDrafts: true,
  compactView: false,
  notifyOnExport: true,
};

function readSavedSettings(): UserSettings {
  try {
    const raw = localStorage.getItem(SETTINGS_STORAGE_KEY);
    if (!raw) return DEFAULT_SETTINGS;
    const parsed = JSON.parse(raw) as Partial<UserSettings>;
    return {
      autoSaveDrafts: parsed.autoSaveDrafts ?? DEFAULT_SETTINGS.autoSaveDrafts,
      compactView: parsed.compactView ?? DEFAULT_SETTINGS.compactView,
      notifyOnExport: parsed.notifyOnExport ?? DEFAULT_SETTINGS.notifyOnExport,
    };
  } catch {
    return DEFAULT_SETTINGS;
  }
}

function SettingToggleRow({
  title,
  description,
  enabled,
  onToggle,
}: {
  title: string;
  description: string;
  enabled: boolean;
  onToggle: () => void;
}) {
  return (
    <div className="w-full rounded-2xl border border-slate-200 bg-white px-4 py-3">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div className="min-w-0">
          <p className="text-sm font-bold text-slate-800 break-keep">{title}</p>
          <p className="mt-1 text-xs font-medium leading-5 text-slate-500 break-keep">{description}</p>
        </div>
        <button
          type="button"
          onClick={onToggle}
          aria-pressed={enabled}
          className={`inline-flex w-full items-center justify-center rounded-xl px-3 py-2 text-sm font-bold transition-colors sm:w-[96px] ${
            enabled
              ? 'bg-blue-600 text-white shadow-sm shadow-blue-200'
              : 'border border-slate-300 bg-slate-50 text-slate-700 hover:bg-slate-100'
          }`}
        >
          {enabled ? '켜짐' : '꺼짐'}
        </button>
      </div>
    </div>
  );
}

export function Settings() {
  const navigate = useNavigate();
  const { user, isGuestSession, signInWithGoogle, logout } = useAuth();
  const backendUser = useAuthStore(state => state.user);
  const [settings, setSettings] = useState<UserSettings>(DEFAULT_SETTINGS);
  const [isCheckingHealth, setIsCheckingHealth] = useState(false);

  useEffect(() => {
    setSettings(readSavedSettings());
  }, []);

  useEffect(() => {
    localStorage.setItem(SETTINGS_STORAGE_KEY, JSON.stringify(settings));
  }, [settings]);

  const accountLabel = useMemo(() => {
    if (user && !user.isAnonymous) return 'Google 계정 연결됨';
    if (isGuestSession) return '게스트 세션';
    return '로그인 필요';
  }, [isGuestSession, user]);

  const displayName = user?.displayName || (isGuestSession ? '게스트' : '사용자');

  const toggle = (key: keyof UserSettings) => {
    setSettings(prev => ({ ...prev, [key]: !prev[key] }));
  };

  const handleConnectGoogle = async () => {
    if (user && !user.isAnonymous) {
      toast('이미 Google 계정이 연결되어 있어요.', { icon: 'ℹ️' });
      return;
    }

    const toastId = toast.loading('Google 계정을 연결하는 중이에요...');
    try {
      await signInWithGoogle();
      toast.success('Google 계정 연결이 완료됐어요.', { id: toastId });
      navigate('/app');
    } catch (error) {
      console.error('Google connect error:', error);
      toast.error('Google 계정 연결에 실패했어요.', { id: toastId });
    }
  };

  const handleLogout = async () => {
    await logout();
    toast.success('로그아웃했어요.');
    navigate('/auth');
  };

  const handleHealthCheck = async () => {
    if (isCheckingHealth) return;
    setIsCheckingHealth(true);
    const toastId = toast.loading('서버 상태를 확인하는 중이에요...');

    try {
      const result = await api.get<{ status?: string; ok?: boolean }>('/api/v1/health');
      const isOk = result?.status === 'ok' || result?.ok === true;
      if (isOk) toast.success('서버 연결 상태가 정상이에요.', { id: toastId });
      else toast('서버 응답은 확인됐지만 상태 점검이 더 필요해요.', { id: toastId, icon: '⚠️' });
    } catch (error) {
      console.error('Health check error:', error);
      toast.error('서버 상태 확인에 실패했어요.', { id: toastId });
    } finally {
      setIsCheckingHealth(false);
    }
  };

  const handleClearArchive = () => {
    const shouldClear = window.confirm('보관함에 저장된 로컬 결과물을 모두 삭제할까요?');
    if (!shouldClear) return;
    localStorage.removeItem('uni_foli_archive_items');
    toast.success('보관함 로컬 데이터가 삭제됐어요.');
  };

  const handleResetSettings = () => {
    const shouldReset = window.confirm('설정을 기본값으로 되돌릴까요?');
    if (!shouldReset) return;
    setSettings(DEFAULT_SETTINGS);
    localStorage.removeItem(SETTINGS_STORAGE_KEY);
    toast.success('설정을 기본값으로 초기화했어요.');
  };

  const handleToggleMarketing = async (enabled: boolean) => {
    try {
      await api.post('/api/v1/users/onboarding/profile', {
        marketing_agreed: enabled
      });
      await useAuthStore.getState().fetchProfile();
      toast.success(enabled ? '마케팅 정보 수신에 동의했어요.' : '마케팅 정보 수신을 거부했어요.');
    } catch (error) {
      toast.error('설정 저장에 실패했어요.');
    }
  };

  const handleRequestDataDeletion = () => {
    if (window.confirm('정말로 모든 개인정보와 활동 기록을 삭제하시겠습니까?\n이 작업은 되돌릴 수 없습니다.')) {
      navigate('/contact', { state: { subject: '개인정보 삭제 요청', content: `계정 ID: ${user?.uid}\n이메일: ${user?.email}\n\n위 계정의 모든 데이터를 삭제해 주세요.` } });
      toast('문의 허브로 연결해 드렸습니다. 내용을 확인 후 전송해 주세요.', { icon: 'ℹ️' });
    }
  };

  return (
    <div className="mx-auto max-w-5xl space-y-6 pb-12">
      <PageHeader
        eyebrow="설정"
        title="계정과 작업 환경 설정"
        description="계정 연결 상태와 앱 사용 환경을 한 화면에서 관리할 수 있어요."
        evidence={
          <div className="flex flex-wrap items-center gap-2">
            <StatusBadge status={user && !user.isAnonymous ? 'success' : 'warning'}>{accountLabel}</StatusBadge>
            <StatusBadge status="neutral">사용자: {displayName}</StatusBadge>
          </div>
        }
      />

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <SectionCard title="계정" description="로그인 상태와 연결 계정을 관리해요." eyebrow="프로필">
          <SurfaceCard padding="sm" className="flex items-center gap-3">
            <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-blue-50 text-blue-700">
              <UserCircle2 size={22} />
            </div>
            <div>
              <p className="text-sm font-bold text-slate-800 break-keep">{displayName}</p>
              <p className="text-xs font-medium text-slate-500 break-keep">{accountLabel}</p>
            </div>
          </SurfaceCard>

          <div className="flex flex-wrap gap-2">
            <SecondaryButton onClick={handleConnectGoogle}>
              <Sparkles size={16} />
              Google 계정 연결
            </SecondaryButton>
            <PrimaryButton onClick={handleLogout}>
              <LogOut size={16} />
              로그아웃
            </PrimaryButton>
          </div>
        </SectionCard>

        <SectionCard title="작업 환경" description="초안 작성과 알림 방식을 조절해요." eyebrow="환경설정">
          <SettingToggleRow
            title="초안 자동 저장"
            description="작성 중인 내용을 자동으로 임시 저장해요."
            enabled={settings.autoSaveDrafts}
            onToggle={() => toggle('autoSaveDrafts')}
          />
          <SettingToggleRow
            title="컴팩트 보기"
            description="좁은 화면에 맞게 목록 간격을 줄여 보여줘요."
            enabled={settings.compactView}
            onToggle={() => toggle('compactView')}
          />
          <SettingToggleRow
            title="내보내기 완료 알림"
            description="파일 내보내기가 끝나면 알림을 표시해요."
            enabled={settings.notifyOnExport}
            onToggle={() => toggle('notifyOnExport')}
          />
          <SettingToggleRow
            title="마케팅 정보 수신"
            description="새로운 기능과 혜택 소식을 받아볼 수 있어요."
            enabled={backendUser?.marketing_agreed || false}
            onToggle={() => handleToggleMarketing(!backendUser?.marketing_agreed)}
          />
        </SectionCard>
      </div>

      <SectionCard title="법적 안내 및 약관" description="Uni Foli의 서비스 운영 정책과 개인정보 보호 원칙을 확인할 수 있어요." eyebrow="정책">
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
          <SecondaryButton onClick={() => window.open('/legal/terms', '_blank')} className="justify-start">
            <FileText size={16} />
            이용약관
          </SecondaryButton>
          <SecondaryButton onClick={() => window.open('/legal/privacy', '_blank')} className="justify-start">
            <ShieldCheck size={16} />
            개인정보처리방침
          </SecondaryButton>
          <SecondaryButton onClick={() => window.open('/legal/refund', '_blank')} className="justify-start">
            <RefreshCw size={16} />
            환불 정책
          </SecondaryButton>
          <SecondaryButton onClick={() => window.open('/legal/marketing', '_blank')} className="justify-start">
            <Mail size={16} />
            마케팅 정보 수신 안내
          </SecondaryButton>
          <SecondaryButton onClick={() => window.open('/legal/youth', '_blank')} className="justify-start">
            <UserCircle2 size={16} />
            청소년 보호 정책
          </SecondaryButton>
          <SecondaryButton onClick={() => window.open('/legal/cookies', '_blank')} className="justify-start">
            <Info size={16} />
            쿠키 사용 안내
          </SecondaryButton>
        </div>
      </SectionCard>

      <SectionCard title="진단 및 데이터 관리" description="서버 상태 확인과 로컬 데이터 정리를 할 수 있어요." eyebrow="관리">
        <WorkflowNotice tone="info" title="중요 안내" description="보관함 초기화는 내 기기(브라우저)에 저장된 데이터만 지워요." />

        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          <SecondaryButton onClick={handleHealthCheck} disabled={isCheckingHealth}>
            <ShieldCheck size={16} />
            {isCheckingHealth ? '확인 중...' : '서버 상태 확인'}
          </SecondaryButton>
          <SecondaryButton onClick={() => navigate('/contact')}>
            <Mail size={16} />
            문의 페이지 이동
          </SecondaryButton>
          <SecondaryButton onClick={handleResetSettings}>
            <RefreshCw size={16} />
            설정 기본값 복원
          </SecondaryButton>
          <PrimaryButton onClick={handleClearArchive}>
            <Trash2 size={16} />
            보관함 초기화
          </PrimaryButton>
          <SecondaryButton onClick={handleRequestDataDeletion} className="sm:col-span-2 border-red-100 text-red-600 hover:bg-red-50">
            <Trash2 size={16} />
            개인정보 및 모든 데이터 삭제 요청
          </SecondaryButton>
        </div>

        <SurfaceCard tone="muted" padding="sm">
          <p className="inline-flex items-center gap-2 text-sm font-bold text-slate-700 break-keep">
            <CheckCircle2 size={16} className="text-emerald-600" />
            설정 변경 내용은 즉시 저장돼요.
          </p>
        </SurfaceCard>
      </SectionCard>
    </div>
  );
}

