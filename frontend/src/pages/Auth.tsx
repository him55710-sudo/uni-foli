import React, { useMemo, useState } from 'react';
import { Link, Navigate } from 'react-router-dom';
import { FirebaseError } from 'firebase/app';
import { motion } from 'motion/react';
import { ArrowRight, BookOpen, CircleCheck, Headphones, ShieldCheck, User, AlertTriangle } from 'lucide-react';
import toast from 'react-hot-toast';
import { useAuth } from '../contexts/AuthContext';
import { UniFoliLogo } from '../components/UniFoliLogo';
import { getFirebaseMissingKeys } from '../lib/firebase';

const AUTH_ERROR_MESSAGES: Record<string, string> = {
  'auth/popup-closed-by-user': 'Google 로그인 창이 닫혔어요. 다시 시도해 주세요.',
  'auth/popup-blocked': '브라우저에서 팝업이 차단됐어요. 팝업 허용 후 다시 시도해 주세요.',
  'auth/network-request-failed': '네트워크 연결 상태를 확인해 주세요.',
  'auth/unauthorized-domain':
    '현재 주소가 Firebase 허용 도메인에 없습니다. Firebase Console > Authentication > Settings > Authorized domains에 현재 도메인을 추가해 주세요.',
  'auth/configuration-not-found': 'Google 로그인 설정이 완료되지 않았어요. Firebase Console에서 Google 제공업체를 켜 주세요.',
  'auth/operation-not-allowed': '현재 환경에서 이 로그인 방식이 비활성화되어 있어요.',
  'auth/admin-restricted-operation': 'Firebase 보안 정책으로 요청이 차단됐어요.',
  'auth/invalid-api-key': 'Firebase API 키가 올바르지 않아요. .env 값을 확인해 주세요.',
  'auth/internal-error': '로그인 처리 중 내부 오류가 발생했어요.',
};

const flowSteps = ['목표 설정', '기록 업로드', '진단 확인', '문서 작성'];
const trustPoints = ['근거 중심 진단', '학생부 기반 흐름', '다음 행동 제시', '허위 문장 방지'];

function toAuthMessage(error: unknown): string {
  if (error instanceof FirebaseError) {
    return AUTH_ERROR_MESSAGES[error.code] ?? `로그인에 실패했어요. (${error.code})`;
  }
  if (error instanceof Error && error.message) {
    return error.message;
  }
  return '로그인에 실패했어요. 잠시 후 다시 시도해 주세요.';
}

export function Auth() {
  const { isAuthenticated, isGuestSession, signInWithGoogle, signInWithKakao, signInWithNaver, signInAsGuest } = useAuth();
  const [isSigningIn, setIsSigningIn] = useState<'google' | 'kakao' | 'naver' | 'guest' | null>(null);
  const [agreements, setAgreements] = useState({
    terms: false,
    privacy: false,
    age: false,
    marketing: false,
  });

  const allRequiredAgreed = agreements.terms && agreements.privacy && agreements.age;
  const missingFirebaseKeys = useMemo(() => getFirebaseMissingKeys(), []);

  if (isAuthenticated || isGuestSession) {
    return <Navigate to="/app" replace />;
  }

  const scrollToTop = () => {
    window.scrollTo({ top: 0, left: 0, behavior: 'auto' });
  };

  const onGoogleLogin = async () => {
    if (isSigningIn !== null) return;
    setIsSigningIn('google');
    localStorage.setItem('uni_foli_pending_marketing_consent', agreements.marketing ? 'true' : 'false');
    try {
      await signInWithGoogle();
    } catch (error) {
      toast.error(toAuthMessage(error));
    } finally {
      setIsSigningIn(null);
    }
  };

  const onKakaoLogin = async () => {
    if (isSigningIn !== null) return;
    setIsSigningIn('kakao');
    localStorage.setItem('uni_foli_pending_marketing_consent', agreements.marketing ? 'true' : 'false');
    try {
      await signInWithKakao();
    } catch (error) {
      toast.error(toAuthMessage(error));
    } finally {
      setIsSigningIn(null);
    }
  };

  const onNaverLogin = async () => {
    if (isSigningIn !== null) return;
    setIsSigningIn('naver');
    localStorage.setItem('uni_foli_pending_marketing_consent', agreements.marketing ? 'true' : 'false');
    try {
      await signInWithNaver();
    } catch (error) {
      toast.error(toAuthMessage(error));
    } finally {
      setIsSigningIn(null);
    }
  };

  const onGuestLogin = async () => {
    if (isSigningIn !== null) return;
    setIsSigningIn('guest');
    localStorage.setItem('uni_foli_pending_marketing_consent', agreements.marketing ? 'true' : 'false');
    try {
      await signInAsGuest();
    } catch (error) {
      toast.error(toAuthMessage(error));
    } finally {
      setIsSigningIn(null);
    }
  };

  return (
    <div className="min-h-screen bg-white selection:bg-indigo-100">
      <div className="mx-auto grid min-h-screen max-w-7xl lg:grid-cols-[1.05fr_0.95fr]">
        <section className="order-2 relative overflow-hidden px-4 py-6 sm:px-8 sm:py-8 lg:order-1 lg:px-12 lg:py-10">

          <div className="relative flex flex-wrap items-center justify-between gap-3">
            <Link to="/" onClick={scrollToTop} className="flex items-center gap-3">
              <UniFoliLogo size="md" subtitle={null} />
            </Link>

            <div className="flex flex-wrap justify-end gap-2">
              <Link
                to="/"
                onClick={scrollToTop}
                className="rounded-full border border-white/80 bg-white/70 px-3 py-1.5 text-xs font-bold text-[#2f4f8f] shadow-[0_8px_18px_rgba(24,66,170,0.1)] backdrop-blur hover:bg-white sm:px-4 sm:py-2 sm:text-sm"
              >
                소개
              </Link>
              <Link
                to="/faq"
                onClick={scrollToTop}
                className="rounded-full border border-white/80 bg-white/70 px-3 py-1.5 text-xs font-bold text-[#2f4f8f] shadow-[0_8px_18px_rgba(24,66,170,0.1)] backdrop-blur hover:bg-white sm:px-4 sm:py-2 sm:text-sm"
              >
                FAQ
              </Link>
              <Link
                to="/contact"
                onClick={scrollToTop}
                className="rounded-full border border-white/80 bg-white/70 px-3 py-1.5 text-xs font-bold text-[#2f4f8f] shadow-[0_8px_18px_rgba(24,66,170,0.1)] backdrop-blur hover:bg-white sm:px-4 sm:py-2 sm:text-sm"
              >
                문의하기
              </Link>
            </div>
          </div>

          <motion.div
            initial={{ opacity: 0, y: 22 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.46 }}
            className="relative mt-8 max-w-2xl sm:mt-14"
          >
            <div className="inline-flex items-center gap-2 rounded-full border border-[#1d4fff]/15 bg-white/72 px-4 py-2 text-xs font-black text-[#1d4fff] shadow-[0_8px_20px_rgba(24,66,170,0.1)] backdrop-blur sm:text-sm">
              <ShieldCheck size={16} />
              근거 중심 준비 흐름
            </div>
            <h1 className="mt-5 text-3xl font-black leading-tight tracking-tight text-slate-900 sm:mt-6 sm:text-4xl lg:text-5xl break-keep">
              막연한 불안 대신
              <br />
              <span className="bg-gradient-to-r from-indigo-600 via-indigo-500 to-purple-600 bg-clip-text text-transparent">확인 가능한 준비 순서</span>
            </h1>
            <p className="mt-5 text-base font-medium leading-7 text-slate-600 sm:mt-6 sm:text-lg sm:leading-8 break-keep">
              학생부 기반 분석, 진단 확인, 문서 작성까지 한 화면 흐름으로 이어집니다.
            </p>

            <div className="mt-7 flex flex-wrap gap-2 sm:mt-8 sm:gap-3">
              {trustPoints.map(item => (
                <span
                  key={item}
                  className="rounded-full border border-[#d6e4ff] bg-white/85 px-3 py-1.5 text-xs font-bold text-[#2f4f8f] shadow-[0_8px_18px_rgba(24,66,170,0.08)] sm:px-4 sm:py-2 sm:text-sm"
                >
                  {item}
                </span>
              ))}
            </div>

            <div className="mt-8 rounded-3xl border border-[#d6e4ff] bg-white/88 p-4 shadow-[0_14px_28px_rgba(24,66,170,0.1)] sm:hidden">
              <p className="text-xs font-black uppercase tracking-[0.14em] text-[#4f6ca3]">빠른 진행 단계</p>
              <div className="mt-3 grid grid-cols-2 gap-2">
                {flowSteps.map((step, index) => (
                  <div key={step} className="rounded-xl border border-[#e3edff] bg-[#f5f9ff] px-3 py-2">
                    <p className="text-[11px] font-black text-[#1d4fff]">{index + 1}단계</p>
                    <p className="mt-1 text-xs font-bold text-slate-700">{step}</p>
                  </div>
                ))}
              </div>
            </div>

            <div className="mt-8 hidden gap-4 sm:mt-10 sm:grid sm:grid-cols-2">
              <div className="rounded-3xl border border-[#d6e4ff] bg-white/88 p-5 shadow-[0_16px_30px_rgba(24,66,170,0.12)] backdrop-blur sm:p-6">
                <div className="flex items-center gap-3">
                  <div className="flex h-10 w-10 items-center justify-center rounded-2xl bg-[#1d4fff]/10 text-[#1d4fff] sm:h-11 sm:w-11">
                    <BookOpen size={20} />
                  </div>
                  <div>
                    <p className="text-sm font-black text-slate-900">진행 순서</p>
                    <p className="text-xs font-medium text-slate-500">단계를 명확히 안내해요</p>
                  </div>
                </div>
                <div className="mt-4 space-y-2.5 sm:mt-5 sm:space-y-3">
                  {flowSteps.map((step, index) => (
                    <div
                      key={step}
                      className="flex items-center gap-3 rounded-2xl border border-[#e3edff] bg-[#f5f9ff] px-4 py-3"
                    >
                      <span className="flex h-7 w-7 items-center justify-center rounded-full bg-[linear-gradient(135deg,#1d4fff_0%,#2da3ff_100%)] text-xs font-black text-white sm:h-8 sm:w-8 sm:text-sm">
                        {index + 1}
                      </span>
                      <span className="text-sm font-bold text-slate-700">{step}</span>
                    </div>
                  ))}
                </div>
              </div>

              <div className="rounded-3xl border border-[#d6e4ff] bg-white/88 p-5 shadow-[0_16px_30px_rgba(24,66,170,0.12)] backdrop-blur sm:p-6">
                <div className="flex items-center gap-3">
                  <div className="flex h-10 w-10 items-center justify-center rounded-2xl bg-[#1d4fff]/10 text-[#1d4fff] sm:h-11 sm:w-11">
                    <ShieldCheck size={20} />
                  </div>
                  <div>
                    <p className="text-sm font-black text-slate-900">안내 원칙</p>
                    <p className="text-xs font-medium text-slate-500">근거 없는 과장은 지양해요</p>
                  </div>
                </div>
                <div className="mt-4 space-y-2.5 sm:mt-5 sm:space-y-3">
                  {[
                    '학생부 내용에 맞는 정보만 제안해요.',
                    '부족한 부분은 보완 행동을 먼저 알려줘요.',
                    '합격 보장을 약속하는 서비스가 아니에요.',
                  ].map(item => (
                    <div key={item} className="flex gap-3 rounded-2xl border border-[#e3edff] bg-[#f5f9ff] px-4 py-3">
                      <CircleCheck size={18} className="mt-0.5 text-[#1d4fff]" />
                      <p className="text-sm font-semibold leading-6 text-slate-700 break-keep">{item}</p>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </motion.div>
        </section>

        <section className="order-1 flex items-start justify-center px-4 pb-6 pt-3 sm:px-8 sm:py-10 lg:order-2 lg:items-center lg:px-12">
          <motion.div
            initial={{ opacity: 0, scale: 0.97 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ duration: 0.38 }}
            className="w-full max-w-md rounded-[2rem] border border-[#d6e4ff] bg-white/90 p-6 shadow-[0_24px_58px_rgba(24,66,170,0.16)] backdrop-blur sm:rounded-[2.4rem] sm:p-8"
          >
            <div className="text-center">
              <div className="flex justify-center">
                <UniFoliLogo size="lg" subtitle={null} className="mb-2" />
              </div>
              <h2 className="mt-4 text-3xl font-black tracking-tight text-slate-900 sm:text-4xl">반가워요!</h2>
              <p className="mt-3 text-sm font-bold leading-relaxed text-slate-500 sm:text-base">
                학생부 분석과 진단의 시작, <br className="sm:hidden" />
                유니폴리와 함께하세요.
              </p>
            </div>

            {missingFirebaseKeys.length ? (
              <div className="mt-5 rounded-2xl border border-amber-200 bg-amber-50 p-4">
                <p className="inline-flex items-center gap-2 text-sm font-bold text-amber-800">
                  <AlertTriangle size={16} />
                  Firebase 환경변수 확인 필요
                </p>
                <p className="mt-2 text-xs font-medium leading-6 text-amber-900">누락된 항목: {missingFirebaseKeys.join(', ')}</p>
              </div>
            ) : null}

            <div className="mt-6 rounded-2xl border border-[#d9e7ff] bg-[#f5f9ff] p-5 sm:mt-8">
              <div className="mb-4 flex items-center justify-between border-b border-[#dce8ff] pb-4">
                <label className="flex cursor-pointer items-center gap-3">
                  <input
                    type="checkbox"
                    className="h-5 w-5 rounded border-[#b6c7ec] text-[#1d4fff] focus:ring-[#1d4fff]"
                    checked={agreements.terms && agreements.privacy && agreements.age && agreements.marketing}
                    onChange={(e) => {
                      const checked = e.target.checked;
                      setAgreements({ terms: checked, privacy: checked, age: checked, marketing: checked });
                    }}
                  />
                  <span className="text-sm font-black text-slate-900">전체 동의하기</span>
                </label>
              </div>
              <div className="space-y-3">
                <div className="flex items-center justify-between">
                  <label className="flex cursor-pointer items-center gap-3">
                    <input
                      type="checkbox"
                      className="h-4 w-4 rounded border-[#b6c7ec] text-[#1d4fff] focus:ring-[#1d4fff]"
                      checked={agreements.age}
                      onChange={(e) => setAgreements(prev => ({ ...prev, age: e.target.checked }))}
                    />
                    <span className="text-sm font-medium text-slate-700">[필수] 만 14세 이상입니다</span>
                  </label>
                </div>
                <div className="flex items-center justify-between">
                  <label className="flex cursor-pointer items-center gap-3">
                    <input
                      type="checkbox"
                      className="h-4 w-4 rounded border-[#b6c7ec] text-[#1d4fff] focus:ring-[#1d4fff]"
                      checked={agreements.terms}
                      onChange={(e) => setAgreements(prev => ({ ...prev, terms: e.target.checked }))}
                    />
                    <span className="text-sm font-medium text-slate-700">[필수] 이용약관 동의</span>
                  </label>
                  <Link to="/legal/terms" target="_blank" className="text-xs font-bold text-slate-400 hover:text-[#1d4fff]">보기</Link>
                </div>
                <div className="flex items-center justify-between">
                  <label className="flex cursor-pointer items-center gap-3">
                    <input
                      type="checkbox"
                      className="h-4 w-4 rounded border-[#b6c7ec] text-[#1d4fff] focus:ring-[#1d4fff]"
                      checked={agreements.privacy}
                      onChange={(e) => setAgreements(prev => ({ ...prev, privacy: e.target.checked }))}
                    />
                    <span className="text-sm font-medium text-slate-700">[필수] 개인정보 수집 및 이용 동의</span>
                  </label>
                  <Link to="/legal/privacy" target="_blank" className="text-xs font-bold text-slate-400 hover:text-[#1d4fff]">보기</Link>
                </div>
                <div className="flex items-center justify-between">
                  <label className="flex cursor-pointer items-center gap-3">
                    <input
                      type="checkbox"
                      className="h-4 w-4 rounded border-[#b6c7ec] text-[#1d4fff] focus:ring-[#1d4fff]"
                      checked={agreements.marketing}
                      onChange={(e) => setAgreements(prev => ({ ...prev, marketing: e.target.checked }))}
                    />
                    <span className="text-sm font-medium text-slate-700">[선택] 마케팅 정보 수신 동의</span>
                  </label>
                  <Link to="/legal/marketing" target="_blank" className="text-xs font-bold text-slate-400 hover:text-[#1d4fff]">보기</Link>
                </div>
              </div>
            </div>

            <div className="mt-8 space-y-3.5 sm:mt-10">
              <button
                type="button"
                onClick={onGoogleLogin}
                disabled={isSigningIn !== null || !allRequiredAgreed}
                className="group relative flex w-full items-center justify-center gap-3.5 rounded-[1.25rem] border border-slate-200 bg-white px-5 py-4 text-[15px] font-black text-slate-700 shadow-sm transition-all hover:bg-slate-50 hover:shadow-md disabled:cursor-not-allowed disabled:opacity-50"
              >
                <svg viewBox="0 0 24 24" className="h-5 w-5 shrink-0" xmlns="http://www.w3.org/2000/svg">
                  <path d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" fill="#4285F4"/>
                  <path d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" fill="#34A853"/>
                  <path d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l3.66-2.84z" fill="#FBBC05"/>
                  <path d="M12 5.38c1.62 0 3.06.56 4.21 1.66l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" fill="#EA4335"/>
                </svg>
                {isSigningIn === 'google' ? '연결 중...' : 'Google로 계속하기'}
              </button>

              <button
                type="button"
                onClick={onKakaoLogin}
                disabled={isSigningIn !== null || !allRequiredAgreed}
                className="group relative flex w-full items-center justify-center gap-3.5 rounded-[1.25rem] border-none bg-[#FEE500] px-5 py-4 text-[15px] font-black text-[#191919] shadow-sm transition-all hover:bg-[#fbdc00] hover:shadow-md disabled:cursor-not-allowed disabled:opacity-50"
              >
                <svg viewBox="0 0 24 24" className="h-5 w-5 shrink-0 fill-[#191919]" xmlns="http://www.w3.org/2000/svg">
                  <path d="M12 3c-4.97 0-9 3.185-9 7.115 0 2.558 1.712 4.8 4.32 6.031l-.81 2.97c-.113.411.39.757.734.527l3.49-2.33c.414.058.84.087 1.266.087 4.97 0 9-3.185 9-7.115S16.97 3 12 3z"/>
                </svg>
                {isSigningIn === 'kakao' ? '연결 중...' : '카카오톡으로 계속하기'}
              </button>

              <button
                type="button"
                onClick={onNaverLogin}
                disabled={isSigningIn !== null || !allRequiredAgreed}
                className="group relative flex w-full items-center justify-center gap-3.5 rounded-[1.25rem] border-none bg-[#03C75A] px-5 py-4 text-[15px] font-black text-white shadow-sm transition-all hover:bg-[#02b351] hover:shadow-md disabled:cursor-not-allowed disabled:opacity-50"
              >
                <svg viewBox="0 0 24 24" className="h-4.5 w-4.5 shrink-0 fill-white" xmlns="http://www.w3.org/2000/svg">
                  <path d="M16.273 12.845L7.376 0H0v24h7.727V11.155L16.624 24H24V0h-7.727v12.845z"/>
                </svg>
                {isSigningIn === 'naver' ? '연결 중...' : '네이버로 계속하기'}
              </button>

              <button
                type="button"
                onClick={onGuestLogin}
                disabled={isSigningIn !== null || !allRequiredAgreed}
                className="group relative flex w-full items-center justify-center gap-3.5 rounded-[1.25rem] border border-indigo-100 bg-indigo-50/50 px-5 py-4 text-[15px] font-black text-indigo-600 transition-all hover:bg-indigo-100/60 disabled:cursor-not-allowed disabled:opacity-50"
              >
                <User size={18} className="shrink-0" />
                {isSigningIn === 'guest' ? '준비 중...' : '게스트로 먼저 보기'}
                <ArrowRight size={16} className="absolute right-5 text-indigo-400 opacity-0 transition-all group-hover:translate-x-1 group-hover:opacity-100" />
              </button>
            </div>

            <div className="mt-6 rounded-3xl border border-[#d9e7ff] bg-[#f5f9ff] p-5 sm:mt-8 sm:rounded-[28px]">
              <div className="flex items-center gap-3">
                <Headphones size={18} className="text-[#1d4fff]" />
                <p className="text-sm font-black text-slate-900">로그인 문제 해결</p>
              </div>
              <p className="mt-3 text-sm font-medium leading-7 text-slate-600 break-keep">
                Google 로그인이 되지 않으면 현재 접속 주소가 Firebase 허용 도메인인지 먼저 확인해 주세요.
                로컬에서는 `localhost`와 `127.0.0.1` 중 허용된 주소로 접속해야 합니다.
              </p>
              <div className="mt-4 flex flex-wrap gap-2">
                <Link
                  to="/faq"
                  onClick={scrollToTop}
                  className="rounded-full border border-[#d5e3ff] bg-white px-4 py-2 text-sm font-bold text-[#31569f] shadow-[0_8px_18px_rgba(24,66,170,0.08)]"
                >
                  FAQ 보기
                </Link>
                <Link
                  to="/contact"
                  onClick={scrollToTop}
                  className="rounded-full border border-[#d5e3ff] bg-white px-4 py-2 text-sm font-bold text-[#31569f] shadow-[0_8px_18px_rgba(24,66,170,0.08)]"
                >
                  문의 허브
                </Link>
              </div>
            </div>

            <p className="mt-5 text-center text-xs font-medium leading-6 text-slate-400 sm:mt-6 break-keep">
              게스트는 미리보기 중심이고, 문서 업로드/저장은 로그인 상태에서 가장 안정적으로 동작해요.
            </p>
          </motion.div>
        </section>
      </div>
    </div>
  );
}
