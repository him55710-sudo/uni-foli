import React, { useEffect, useMemo, useState } from 'react';
import {
  ShieldCheck,
  LogOut,
  RefreshCw,
  Mail,
  UserCircle2,
  Sparkles,
  Trash2,
  CheckCircle2,
} from 'lucide-react';
import toast from 'react-hot-toast';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { api } from '../lib/api';

interface UserSettings {
  autoSaveDrafts: boolean;
  compactView: boolean;
  notifyOnExport: boolean;
}

const SETTINGS_STORAGE_KEY = 'polio_user_settings_v1';
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

export function Settings() {
  const navigate = useNavigate();
  const { user, isGuestSession, signInWithGoogle, logout } = useAuth();
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
    setSettings((prev) => ({ ...prev, [key]: !prev[key] }));
  };

  const handleConnectGoogle = async () => {
    if (user && !user.isAnonymous) {
      toast('이미 Google 계정이 연결되어 있습니다.', { icon: 'ℹ️' });
      return;
    }

    const toastId = toast.loading('Google 계정 연결 중입니다...');
    try {
      await signInWithGoogle();
      toast.success('Google 계정이 연결되었습니다.', { id: toastId });
      navigate('/');
    } catch (error) {
      console.error('Google connect error:', error);
      toast.error('Google 계정 연결에 실패했습니다.', { id: toastId });
    }
  };

  const handleLogout = async () => {
    await logout();
    toast.success('로그아웃되었습니다.');
    navigate('/auth');
  };

  const handleHealthCheck = async () => {
    if (isCheckingHealth) return;
    setIsCheckingHealth(true);
    const toastId = toast.loading('서버 연결 상태를 점검 중입니다...');

    try {
      const result = await api.get<{ status?: string; ok?: boolean }>('/api/v1/health');
      const isOk = result?.status === 'ok' || result?.ok === true;
      if (isOk) {
        toast.success('서버 연결이 정상입니다.', { id: toastId });
      } else {
        toast('서버 응답은 왔지만 상태 확인이 필요합니다.', { id: toastId, icon: '⚠️' });
      }
    } catch (error) {
      console.error('Health check error:', error);
      toast.error('서버 연결에 실패했습니다. 백엔드 실행 상태를 확인해주세요.', { id: toastId });
    } finally {
      setIsCheckingHealth(false);
    }
  };

  const handleClearArchive = () => {
    const shouldClear = window.confirm('아카이브에 저장된 로컬 결과물을 모두 삭제할까요?');
    if (!shouldClear) return;
    localStorage.removeItem('polio_archive_items');
    toast.success('아카이브 로컬 데이터를 초기화했습니다.');
  };

  const handleResetSettings = () => {
    const shouldReset = window.confirm('설정 값을 기본값으로 되돌릴까요?');
    if (!shouldReset) return;
    setSettings(DEFAULT_SETTINGS);
    localStorage.removeItem(SETTINGS_STORAGE_KEY);
    toast.success('설정을 기본값으로 되돌렸습니다.');
  };

  const handleContact = () => {
    window.location.href = 'mailto:mongben@naver.com?subject=polio%20문의';
  };

  return (
    <div className="mx-auto max-w-5xl space-y-8 px-4 pb-24 sm:px-6 lg:px-8">
      <div>
        <h1 className="mb-2 text-3xl font-extrabold text-slate-800">설정 및 계정</h1>
        <p className="font-medium text-slate-500">
          계정 연결, 워크플로 설정, 서버 상태 점검을 한 곳에서 관리합니다.
        </p>
      </div>

      <section className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <div className="space-y-5 p-6 sm:p-8 clay-card">
          <div className="flex items-center gap-3">
            <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-blue-50 text-blue-600">
              <UserCircle2 size={22} />
            </div>
            <div>
              <p className="text-sm font-bold text-slate-400">현재 계정</p>
              <h2 className="text-xl font-extrabold text-slate-800">{displayName}</h2>
            </div>
          </div>

          <div className="inline-flex items-center gap-2 rounded-xl border border-blue-100 bg-blue-50 px-3 py-1.5 text-sm font-bold text-blue-700">
            <CheckCircle2 size={16} />
            {accountLabel}
          </div>

          <div className="space-y-2">
            <button
              onClick={handleConnectGoogle}
              className="flex w-full items-center justify-center gap-2 rounded-2xl border border-slate-200 bg-white px-4 py-3 font-bold text-slate-700 transition-colors hover:bg-slate-50"
            >
              <Sparkles size={18} />
              Google 계정 연결하기
            </button>
            <button
              onClick={handleLogout}
              className="flex w-full items-center justify-center gap-2 rounded-2xl bg-slate-800 px-4 py-3 font-bold text-white transition-colors hover:bg-slate-900"
            >
              <LogOut size={18} />
              로그아웃
            </button>
          </div>
        </div>

        <div className="space-y-4 p-6 sm:p-8 clay-card">
          <h2 className="text-xl font-extrabold text-slate-800">작업 환경</h2>
          <button
            onClick={() => toggle('autoSaveDrafts')}
            className="flex w-full items-center justify-between rounded-2xl border border-slate-200 bg-white px-4 py-3 text-left font-bold text-slate-700 transition-colors hover:bg-slate-50"
          >
            <span>초안 자동 저장</span>
            <span className={settings.autoSaveDrafts ? 'text-blue-600' : 'text-slate-400'}>
              {settings.autoSaveDrafts ? '켜짐' : '꺼짐'}
            </span>
          </button>
          <button
            onClick={() => toggle('compactView')}
            className="flex w-full items-center justify-between rounded-2xl border border-slate-200 bg-white px-4 py-3 text-left font-bold text-slate-700 transition-colors hover:bg-slate-50"
          >
            <span>컴팩트 보기</span>
            <span className={settings.compactView ? 'text-blue-600' : 'text-slate-400'}>
              {settings.compactView ? '켜짐' : '꺼짐'}
            </span>
          </button>
          <button
            onClick={() => toggle('notifyOnExport')}
            className="flex w-full items-center justify-between rounded-2xl border border-slate-200 bg-white px-4 py-3 text-left font-bold text-slate-700 transition-colors hover:bg-slate-50"
          >
            <span>내보내기 완료 알림</span>
            <span className={settings.notifyOnExport ? 'text-blue-600' : 'text-slate-400'}>
              {settings.notifyOnExport ? '켜짐' : '꺼짐'}
            </span>
          </button>
        </div>
      </section>

      <section className="space-y-4 p-6 sm:p-8 clay-card">
        <h2 className="text-xl font-extrabold text-slate-800">연결 및 데이터 관리</h2>
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          <button
            onClick={handleHealthCheck}
            disabled={isCheckingHealth}
            className="flex items-center justify-center gap-2 rounded-2xl border border-slate-200 bg-white px-4 py-3 font-bold text-slate-700 transition-colors hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-60"
          >
            <ShieldCheck size={18} />
            {isCheckingHealth ? '점검 중...' : '서버 연결 점검'}
          </button>
          <button
            onClick={handleClearArchive}
            className="flex items-center justify-center gap-2 rounded-2xl border border-amber-200 bg-amber-50 px-4 py-3 font-bold text-amber-700 transition-colors hover:bg-amber-100"
          >
            <Trash2 size={18} />
            아카이브 초기화
          </button>
          <button
            onClick={handleResetSettings}
            className="flex items-center justify-center gap-2 rounded-2xl border border-slate-200 bg-white px-4 py-3 font-bold text-slate-700 transition-colors hover:bg-slate-50"
          >
            <RefreshCw size={18} />
            설정 기본값 복구
          </button>
          <button
            onClick={handleContact}
            className="flex items-center justify-center gap-2 rounded-2xl border border-blue-200 bg-blue-50 px-4 py-3 font-bold text-blue-700 transition-colors hover:bg-blue-100"
          >
            <Mail size={18} />
            문의 메일 보내기
          </button>
        </div>
      </section>
    </div>
  );
}
