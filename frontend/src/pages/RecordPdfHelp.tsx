import React from 'react';
import {
  AlertTriangle,
  ArrowLeft,
  CheckCircle2,
  ExternalLink,
  FileDown,
  Printer,
  ShieldCheck,
  XCircle,
} from 'lucide-react';
import { Link, useLocation } from 'react-router-dom';

import { PageHeader, SectionCard, SurfaceCard, WorkflowNotice } from '../components/primitives';

const REQUIRED_FILE_ITEMS = [
  '학생부 전체 페이지가 포함된 공식 PDF 파일',
  '학교/교육청 시스템에서 내려받은 원본 파일',
  '읽기 가능한 선명한 텍스트(흐림, 잘림 없음)',
] as const;

const SOURCE_OPTIONS = [
  '대부분의 학교/교육청 학생부 열람 시스템',
  '학교 안내실/행정실에서 제공하는 출력 또는 전자 발급 경로',
  '학교 공지에 안내된 공식 생활기록부 발급 링크',
] as const;

const EXPORT_STEPS = [
  {
    id: '1',
    title: '공식 학생부 화면 열기',
    description: '학교 또는 교육청 포털에 로그인해 학생부 전체 보기 화면으로 이동합니다.',
    icon: ExternalLink,
  },
  {
    id: '2',
    title: 'PDF 다운로드 버튼 우선 사용',
    description: '플랫폼의 PDF 다운로드/출력 버튼이 있으면 가장 먼저 그 기능을 사용합니다.',
    icon: FileDown,
  },
  {
    id: '3',
    title: '버튼이 없으면 인쇄 → PDF 저장',
    description: '다운로드가 없다면 브라우저 인쇄 메뉴에서 대상 프린터를 PDF로 선택해 저장합니다.',
    icon: Printer,
  },
] as const;

const QUALITY_ISSUES_TO_AVOID = [
  '사진 캡처본/스크린샷을 PDF로 묶은 파일',
  '일부 페이지만 저장된 PDF',
  '글자가 흐리거나 회전된 상태로 저장된 PDF',
  '외부 편집 툴로 문장을 임의 수정한 PDF',
] as const;

const BEFORE_UPLOAD_CHECKLIST = [
  '확장자가 .pdf 인가요?',
  '용량이 50MB 이하인가요?',
  '전체 페이지가 빠짐없이 들어 있나요?',
  '각 페이지 글자가 확대 없이도 읽히나요?',
] as const;

const COMMON_MISTAKES = [
  '요약 화면만 저장해서 세부 항목(세특/창체)이 빠진 경우',
  '다운로드 중 오류로 첫 페이지만 저장된 경우',
  '압축/변환 과정에서 글자가 이미지로 깨진 경우',
] as const;

export function RecordPdfHelp() {
  const location = useLocation();
  const backTo = location.pathname.startsWith('/app/')
    ? '/app/record'
    : '/record';

  return (
    <div className="mx-auto max-w-5xl space-y-6 py-4">
      <PageHeader
        eyebrow="학생부 준비 안내"
        title="학생부 PDF 다운로드 방법"
        description="업로드 전에 2~3분만 확인하면 분석 실패를 크게 줄일 수 있어요."
        actions={
          <Link
            to={backTo}
            className="inline-flex items-center gap-2 rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm font-semibold text-slate-700 transition-colors hover:bg-slate-50"
          >
            <ArrowLeft size={15} />
            업로드 화면으로 돌아가기
          </Link>
        }
      />

      <SectionCard
        title="어떤 파일이 필요한가요?"
        eyebrow="필수 파일"
        description="Uni Foli는 공식 학생부 원본 PDF를 기준으로 진단합니다."
      >
        <SurfaceCard tone="muted" padding="sm" className="space-y-2 border border-sky-100 bg-sky-50/60">
          {REQUIRED_FILE_ITEMS.map((item) => (
            <p key={item} className="flex items-start gap-2 text-sm font-semibold leading-6 text-sky-900">
              <CheckCircle2 size={15} className="mt-1 shrink-0 text-sky-700" />
              <span>{item}</span>
            </p>
          ))}
        </SurfaceCard>
      </SectionCard>

      <SectionCard
        title="어디서 보통 발급하나요?"
        eyebrow="발급 경로"
        description="학교마다 명칭은 다르지만 공식 학생기록 발급 경로를 사용하면 됩니다."
      >
        <div className="grid gap-3 sm:grid-cols-3">
          {SOURCE_OPTIONS.map((item, index) => (
            <SurfaceCard key={item} tone="muted" padding="sm" className="border border-slate-200 bg-white">
              <p className="text-xs font-black tracking-[0.14em] text-slate-400">OPTION {index + 1}</p>
              <p className="mt-2 text-sm font-semibold leading-6 text-slate-700">{item}</p>
            </SurfaceCard>
          ))}
        </div>
      </SectionCard>

      <SectionCard
        title="PDF로 저장하는 방법"
        eyebrow="Step-by-step"
        description="다운로드 버튼이 있으면 우선 사용하고, 없으면 인쇄 저장을 사용하세요."
      >
        <div className="grid gap-3 sm:grid-cols-3">
          {EXPORT_STEPS.map((step) => {
            const Icon = step.icon;
            return (
              <SurfaceCard key={step.id} tone="muted" padding="sm" className="border border-slate-200 bg-white">
                <div className="flex items-center justify-between gap-2">
                  <p className="text-xs font-black tracking-[0.14em] text-slate-400">STEP {step.id}</p>
                  <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-blue-100 text-blue-700">
                    <Icon size={15} />
                  </div>
                </div>
                <p className="mt-3 text-sm font-bold text-slate-900">{step.title}</p>
                <p className="mt-1 text-sm font-medium leading-6 text-slate-600">{step.description}</p>
              </SurfaceCard>
            );
          })}
        </div>
      </SectionCard>

      <SectionCard
        title="품질 이슈 피하기"
        eyebrow="주의 사항"
        description="아래 항목은 파싱 실패와 진단 신뢰도 저하의 가장 흔한 원인입니다."
      >
        <SurfaceCard tone="muted" padding="sm" className="space-y-2 border border-amber-100 bg-amber-50/70">
          {QUALITY_ISSUES_TO_AVOID.map((item) => (
            <p key={item} className="flex items-start gap-2 text-sm font-semibold leading-6 text-amber-900">
              <AlertTriangle size={15} className="mt-1 shrink-0 text-amber-700" />
              <span>{item}</span>
            </p>
          ))}
        </SurfaceCard>
      </SectionCard>

      <SectionCard
        title="업로드 전 마지막 체크"
        eyebrow="Checklist"
        description="여기만 통과하면 대부분 바로 진단 파이프라인으로 연결됩니다."
      >
        <SurfaceCard tone="muted" padding="sm" className="space-y-2 border border-emerald-100 bg-emerald-50/60">
          {BEFORE_UPLOAD_CHECKLIST.map((item) => (
            <p key={item} className="flex items-start gap-2 text-sm font-semibold leading-6 text-emerald-900">
              <CheckCircle2 size={15} className="mt-1 shrink-0 text-emerald-700" />
              <span>{item}</span>
            </p>
          ))}
        </SurfaceCard>

        <WorkflowNotice
          tone="info"
          title="개인정보 보호 안내"
          description="업로드된 문서는 분석 전에 개인정보 마스킹 절차를 먼저 거칩니다. 원본 외 과장/수정 정보는 넣지 않아 주세요."
        />
      </SectionCard>

      <SectionCard
        title="자주 하는 실수"
        eyebrow="실수 방지"
        description="처음 업로드하는 사용자에게 특히 자주 발생하는 사례입니다."
      >
        <div className="space-y-2">
          {COMMON_MISTAKES.map((item) => (
            <SurfaceCard key={item} tone="muted" padding="sm" className="border border-rose-100 bg-rose-50/55">
              <p className="flex items-start gap-2 text-sm font-semibold leading-6 text-rose-900">
                <XCircle size={15} className="mt-1 shrink-0 text-rose-700" />
                <span>{item}</span>
              </p>
            </SurfaceCard>
          ))}
        </div>

        <WorkflowNotice
          tone="success"
          title="준비가 끝났다면 바로 업로드해 보세요."
          description="이 페이지를 닫고 업로드 화면으로 돌아가면, 업로드 후 분석이 자동으로 이어집니다."
        />
      </SectionCard>

      <WorkflowNotice
        tone="info"
        title="근거 기반 작성 원칙"
        description="Uni Foli는 학생부 원문 근거를 벗어나 새로운 활동을 임의로 만들지 않습니다. 불확실한 정보는 불확실성으로 표시됩니다."
      />

      <SurfaceCard tone="muted" padding="sm" className="flex items-start gap-2 border border-blue-100 bg-blue-50/60">
        <ShieldCheck size={16} className="mt-0.5 shrink-0 text-blue-700" />
        <p className="text-sm font-medium leading-6 text-blue-900">
          안내는 이해를 돕기 위한 일반 가이드입니다. 학교별 메뉴 이름이 다르면 “공식 학생부 전체 PDF 발급” 메뉴를 기준으로 찾아주세요.
        </p>
      </SurfaceCard>
    </div>
  );
}
