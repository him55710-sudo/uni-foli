import React from 'react';
import { Link } from 'react-router-dom';
import { UniFoliLogo } from '../UniFoliLogo';
import { PrimaryButton, SurfaceCard } from '../primitives';
import { buttonClassName } from '../ui';

interface AppFooterProps {
  onOpenPartnership: () => void;
}

export function AppFooter({ onOpenPartnership }: AppFooterProps) {
  return (
    <SurfaceCard className="mt-8 border-[#d8e6ff] bg-white/86 p-5 shadow-[0_18px_36px_rgba(24,66,170,0.12)] sm:mt-12 sm:p-8">
      <div className="grid gap-8 lg:grid-cols-[1.25fr_0.75fr]">
        <div className="space-y-4">
          <div className="mt-1 space-y-2">
            <UniFoliLogo size="sm" subtitle={null} />
            <p className="text-sm font-medium leading-relaxed text-slate-500">
              <span className="sm:hidden">학생 기록 기반 분석과 문서 작성을 지원하는 준비 도구입니다.</span>
              <span className="hidden sm:inline">
              UniFoli는 학생 기록 기반 분석과 초안 작성 워크플로를 돕는 도구입니다. 합격을 보장하지 않으며, 준비 과정의 품질과 실행력을 높이는 데 집중합니다.
              </span>
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <Link to="/faq" className={buttonClassName({ variant: 'secondary', size: 'sm' })}>
              자주 묻는 질문
            </Link>
            <Link to="/contact" className={buttonClassName({ variant: 'secondary', size: 'sm' })}>
              문의
            </Link>
            <PrimaryButton size="sm" onClick={onOpenPartnership}>
              제휴 문의
            </PrimaryButton>
          </div>
          <p className="text-xs font-medium text-slate-400">© UniFoli 2026. 모든 권리 보유.</p>
        </div>

        <div className="space-y-3 text-sm font-medium text-slate-500 lg:text-right">
          <p className="text-xs font-bold uppercase tracking-[0.18em] text-slate-400">정책</p>
          <div className="flex flex-wrap gap-4 lg:justify-end">
            <Link to="/terms" className="font-semibold text-slate-600 hover:text-slate-900">
              이용약관
            </Link>
            <Link to="/privacy" className="font-semibold text-slate-600 hover:text-slate-900">
              개인정보처리방침
            </Link>
          </div>
          <p className="hidden text-xs leading-6 text-slate-400 sm:block">기록은 최소 수집 원칙으로 처리되며, 초안 작성은 사용자 검토를 전제로 합니다.</p>
        </div>
      </div>
    </SurfaceCard>
  );
}
