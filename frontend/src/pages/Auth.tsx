import React, { useState } from 'react';
import { Link, Navigate } from 'react-router-dom';
import { FirebaseError } from 'firebase/app';
import { motion } from 'motion/react';
import { ArrowRight, BookOpen, CircleCheck, Headphones, ShieldCheck, User } from 'lucide-react';
import toast from 'react-hot-toast';
import { useAuth } from '../contexts/AuthContext';
import { UniFoliaLogo } from '../components/UniFoliaLogo';

const AUTH_ERROR_MESSAGES: Record<string, string> = {
  'auth/popup-closed-by-user': 'Google 로그인 창이 닫혔습니다. 다시 시도해 주세요.',
  'auth/popup-blocked': '브라우저에서 팝업이 차단되었습니다. 팝업 허용 후 다시 시도해 주세요.',
  'auth/network-request-failed': '네트워크 연결을 확인해 주세요.',
  'auth/unauthorized-domain': '현재 도메인이 Firebase 로그인 허용 목록에 없습니다.',
  'auth/configuration-not-found': 'Google 로그인 설정이 아직 준비되지 않았습니다.',
  'auth/operation-not-allowed': '이 환경에서는 게스트 로그인이 비활성화되어 있습니다.',
  'auth/admin-restricted-operation': '현재 Firebase 설정에서 게스트 로그인이 제한되어 있습니다.',
  'auth/invalid-api-key': 'Firebase 설정이 올바르지 않습니다.',
  'auth/internal-error': '로그인 처리 중 내부 오류가 발생했습니다.',
};

const flowSteps = ['목표 설정', '생기부 업로드', 'AI 진단', '작업실'];
const trustPoints = ['근거 기반 AI', '기록 중심 워크플로', '탐구 플랜과 다음 행동 제안', '허위 미화 금지'];

function toAuthMessage(error: unknown): string {
  if (error instanceof FirebaseError) {
    return AUTH_ERROR_MESSAGES[error.code] ?? `로그인에 실패했습니다. (${error.code})`;
  }
  if (error instanceof Error && error.message) {
    return error.message;
  }
  return '로그인에 실패했습니다. 잠시 후 다시 시도해 주세요.';
}

export function Auth() {
  const { user, isGuestSession, guestModeAvailable, signInWithGoogle, signInAsGuest } = useAuth();
  const [isSigningIn, setIsSigningIn] = useState<'google' | 'guest' | null>(null);

  if (user || isGuestSession) {
    return <Navigate to="/app" replace />;
  }

  const onGoogleLogin = async () => {
    if (isSigningIn !== null) return;
    setIsSigningIn('google');
    try {
      await signInWithGoogle();
    } catch (error) {
      toast.error(toAuthMessage(error));
    } finally {
      setIsSigningIn(null);
    }
  };

  const onGuestLogin = async () => {
    if (isSigningIn !== null) return;
    setIsSigningIn('guest');
    try {
      await signInAsGuest();
    } catch (error) {
      toast.error(toAuthMessage(error));
    } finally {
      setIsSigningIn(null);
    }
  };

  return (
    <div className="min-h-screen bg-slate-50">
      <div className="mx-auto grid min-h-screen max-w-7xl lg:grid-cols-[1.05fr_0.95fr]">
        <section className="relative overflow-hidden bg-[radial-gradient(circle_at_top_right,_rgba(59,130,246,0.18),_transparent_34%),linear-gradient(180deg,_#f8fbff_0%,_#eff6ff_100%)] px-6 py-8 sm:px-10 lg:px-12 lg:py-10">
          <div className="flex items-center justify-between gap-4">
            <Link to="/" className="flex items-center gap-3">
              <UniFoliaLogo size="md" />
            </Link>

            <div className="flex flex-wrap justify-end gap-2">
              <Link to="/" className="rounded-full bg-white/80 px-4 py-2 text-sm font-bold text-slate-700 shadow-sm hover:bg-white">
                홈으로
              </Link>
              <Link to="/faq" className="rounded-full bg-white/80 px-4 py-2 text-sm font-bold text-slate-700 shadow-sm hover:bg-white">
                FAQ
              </Link>
              <Link to="/contact" className="rounded-full bg-white/80 px-4 py-2 text-sm font-bold text-slate-700 shadow-sm hover:bg-white">
                문의하기
              </Link>
            </div>
          </div>

          <motion.div
            initial={{ opacity: 0, y: 24 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.45 }}
            className="mt-14 max-w-2xl"
          >
            <div className="inline-flex items-center gap-2 rounded-full border border-blue-100 bg-white/80 px-4 py-2 text-sm font-black text-blue-600 shadow-sm">
              <ShieldCheck size={16} />
              가장 안전한 생기부 드래프팅 흐름
            </div>
            <h1 className="mt-6 text-4xl font-black leading-tight tracking-tight text-slate-900 sm:text-5xl">
              막연한 생성보다,
              <br />
              <span className="text-blue-600">기록 중심의</span>
              <br />
              확실한 다음 행동
            </h1>
            <p className="mt-6 text-lg font-medium leading-8 text-slate-600">
              Uni Folia는 단순 생성이 아니라, 실제 기록을 분석해 탐구 방향을 제안하고 안전한 작업실에서 초안을 다듬는 워크플로우를 제공합니다.
            </p>

            <div className="mt-8 flex flex-wrap gap-3">
              {trustPoints.map(item => (
                <span key={item} className="rounded-full border border-white/80 bg-white/80 px-4 py-2 text-sm font-bold text-slate-700 shadow-sm">
                  {item}
                </span>
              ))}
            </div>

            <div className="mt-10 grid gap-4 sm:grid-cols-2">
              <div className="rounded-[32px] border border-slate-200 bg-white/85 p-6 shadow-sm">
                <div className="flex items-center gap-3">
                  <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-blue-50 text-blue-600">
                    <BookOpen size={20} />
                  </div>
                  <div>
                    <p className="text-sm font-black text-slate-900">작동 방식</p>
                    <p className="text-xs font-medium text-slate-500">순서를 분명하게 안내합니다.</p>
                  </div>
                </div>
                <div className="mt-5 space-y-3">
                  {flowSteps.map((step, index) => (
                    <div key={step} className="flex items-center gap-3 rounded-2xl border border-slate-100 bg-slate-50 px-4 py-3">
                      <span className="flex h-8 w-8 items-center justify-center rounded-full bg-blue-600 text-sm font-black text-white">
                        {index + 1}
                      </span>
                      <span className="text-sm font-bold text-slate-700">{step}</span>
                    </div>
                  ))}
                </div>
              </div>

              <div className="rounded-[32px] border border-slate-200 bg-white/85 p-6 shadow-sm">
                <div className="flex items-center gap-3">
                  <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-blue-50 text-blue-600">
                    <ShieldCheck size={20} />
                  </div>
                  <div>
                    <p className="text-sm font-black text-slate-900">안전 원칙</p>
                    <p className="text-xs font-medium text-slate-500">과장보다 근거를 우선합니다.</p>
                  </div>
                </div>
                <div className="mt-5 space-y-3">
                  {[
                    '실제 기록을 바탕으로만 drafting을 돕습니다.',
                    '기록이 부족하면 보완 행동을 먼저 제안합니다.',
                    '합격 보장이나 허위 활동 생성은 지향하지 않습니다.',
                  ].map(item => (
                    <div key={item} className="flex gap-3 rounded-2xl border border-slate-100 bg-slate-50 px-4 py-3">
                      <CircleCheck size={18} className="mt-0.5 text-blue-600" />
                      <p className="text-sm font-semibold leading-6 text-slate-700">{item}</p>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </motion.div>
        </section>

        <section className="flex items-center justify-center bg-white px-6 py-10 sm:px-10 lg:px-12">
          <motion.div
            initial={{ opacity: 0, scale: 0.96 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ duration: 0.35 }}
            className="w-full max-w-md rounded-[40px] border border-slate-200 bg-white p-8 shadow-[0_24px_60px_rgba(15,23,42,0.08)]"
          >
            <div className="text-center">
              <div className="mx-auto flex h-20 w-20 items-center justify-center rounded-[28px] border border-blue-100 bg-blue-50">
                <UniFoliaLogo size="lg" markOnly />
              </div>
              <h2 className="mt-6 text-3xl font-black tracking-tight text-slate-900">앱 시작하기</h2>
              <p className="mt-3 text-base font-medium leading-7 text-slate-500">
                Google 로그인으로 계속하거나, 열려 있는 환경에서는 게스트로 흐름을 먼저 확인할 수 있습니다.
              </p>
            </div>

            <div className="mt-8 space-y-3">
              <button
                type="button"
                onClick={onGoogleLogin}
                disabled={isSigningIn !== null}
                className="group relative flex w-full items-center justify-center gap-3 rounded-2xl border border-slate-200 bg-white px-6 py-4 text-base font-black text-slate-700 shadow-sm transition-colors hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-60"
              >
                <img src="https://www.google.com/favicon.ico" alt="" className="h-5 w-5" />
                {isSigningIn === 'google' ? '로그인 중...' : 'Google로 계속하기'}
                <ArrowRight size={18} className="absolute right-5 text-slate-400 opacity-0 transition-all group-hover:translate-x-1 group-hover:opacity-100" />
              </button>

              {guestModeAvailable ? (
                <button
                  type="button"
                  onClick={onGuestLogin}
                  disabled={isSigningIn !== null}
                  className="group relative flex w-full items-center justify-center gap-3 rounded-2xl border border-blue-100 bg-blue-50 px-6 py-4 text-base font-black text-blue-700 shadow-sm transition-colors hover:bg-blue-100 disabled:cursor-not-allowed disabled:opacity-60"
                >
                  <User size={18} />
                  {isSigningIn === 'guest' ? '게스트 세션 준비 중...' : '게스트로 먼저 둘러보기'}
                  <ArrowRight size={18} className="absolute right-5 text-blue-400 opacity-0 transition-all group-hover:translate-x-1 group-hover:opacity-100" />
                </button>
              ) : null}
            </div>

            <div className="mt-8 rounded-[28px] border border-slate-200 bg-slate-50 p-5">
              <div className="flex items-center gap-3">
                <Headphones size={18} className="text-blue-600" />
                <p className="text-sm font-black text-slate-900">도움이 필요하면</p>
              </div>
              <p className="mt-3 text-sm font-medium leading-7 text-slate-600">
                로그인 전 궁금한 점이 있다면 FAQ와 문의 허브에서 서비스 방향, 협업 문의, 버그 제안 경로를 먼저 확인할 수 있습니다.
              </p>
              <div className="mt-4 flex flex-wrap gap-2">
                <Link to="/faq" className="rounded-full bg-white px-4 py-2 text-sm font-bold text-slate-700 shadow-sm">
                  FAQ 보기
                </Link>
                <Link to="/contact" className="rounded-full bg-white px-4 py-2 text-sm font-bold text-slate-700 shadow-sm">
                  문의 허브
                </Link>
              </div>
            </div>

            <p className="mt-6 text-center text-xs font-medium leading-6 text-slate-400">
              게스트 로그인 여부와 소셜 로그인 가용성은 현재 배포 환경 설정에 따라 달라질 수 있습니다.
            </p>
          </motion.div>
        </section>
      </div>
    </div>
  );
}
