import React from 'react';
import { CheckCircle2, Circle, ShieldCheck, HelpCircle } from 'lucide-react';
import { cn } from '../lib/cn';
import { QualityLevelInfo, RenderRequirementInfo } from '../pages/Workshop';

interface WorkshopProgressProps {
  requirements: RenderRequirementInfo;
  qualityInfo?: QualityLevelInfo;
}

export const WorkshopProgress: React.FC<WorkshopProgressProps> = ({
  requirements,
  qualityInfo
}) => {
  const {
    current_context_score,
    required_context_score,
    current_turn_count,
    minimum_turn_count,
    current_reference_count,
    minimum_reference_count,
    can_render,
    missing
  } = requirements;

  const progressFor = (current: number, required: number) => {
    if (required <= 0) return 100;
    return Math.min(100, Math.max(0, (current / required) * 100));
  };

  // Calculate progress percentages
  const contextProgress = progressFor(current_context_score, required_context_score);
  const turnProgress = progressFor(current_turn_count, minimum_turn_count);
  const referenceProgress = progressFor(current_reference_count, minimum_reference_count);

  // Overall progress is roughly the average of these three
  const overallProgress = Math.round((contextProgress + turnProgress + referenceProgress) / 3);

  return (
    <div className="space-y-4">
      {/* Header with Quality Info */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-[#004aad]/10 text-[#004aad]">
            <ShieldCheck size={18} />
          </div>
          <div>
            <h4 className="text-sm font-bold text-slate-900">워크숍 진행도</h4>
            {qualityInfo && (
              <p className="text-[11px] font-semibold text-[#004aad]">
                {qualityInfo.label} 모드 활성화됨
              </p>
            )}
          </div>
        </div>
        <div className="text-right">
          <span className="text-lg font-black text-[#004aad]">{overallProgress}%</span>
        </div>
      </div>

      {/* Progress Bar */}
      <div className="relative h-2 w-full overflow-hidden rounded-full bg-slate-200">
        <div 
          className="absolute left-0 top-0 h-full bg-[#004aad] transition-all duration-500 ease-out"
          style={{ width: `${overallProgress}%` }}
        />
      </div>

      {/* Checklist Grid */}
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
        {/* Context Score */}
        <div className="rounded-xl border border-slate-100 bg-white p-3 shadow-sm">
          <div className="mb-2 flex items-center justify-between">
            <span className="text-[11px] font-bold text-slate-500">분석 완성도</span>
            {contextProgress >= 100 ? (
              <CheckCircle2 size={14} className="text-emerald-500" />
            ) : (
              <Circle size={14} className="text-slate-300" />
            )}
          </div>
          <div className="text-sm font-black text-slate-900">
            {current_context_score} <span className="text-[10px] font-medium text-slate-400">/ {required_context_score}pt</span>
          </div>
        </div>

        {/* Turn Count */}
        <div className="rounded-xl border border-slate-100 bg-white p-3 shadow-sm">
          <div className="mb-2 flex items-center justify-between">
            <span className="text-[11px] font-bold text-slate-500">대화 횟수</span>
            {turnProgress >= 100 ? (
              <CheckCircle2 size={14} className="text-emerald-500" />
            ) : (
              <Circle size={14} className="text-slate-300" />
            )}
          </div>
          <div className="text-sm font-black text-slate-900">
            {current_turn_count} <span className="text-[10px] font-medium text-slate-400">/ {minimum_turn_count}회</span>
          </div>
        </div>

        {/* Reference Count */}
        <div className="rounded-xl border border-slate-100 bg-white p-3 shadow-sm">
          <div className="mb-2 flex items-center justify-between">
            <span className="text-[11px] font-bold text-slate-500">근거 추출</span>
            {referenceProgress >= 100 ? (
              <CheckCircle2 size={14} className="text-emerald-500" />
            ) : (
              <Circle size={14} className="text-slate-300" />
            )}
          </div>
          <div className="text-sm font-black text-slate-900">
            {current_reference_count} <span className="text-[10px] font-medium text-slate-400">/ {minimum_reference_count}개</span>
          </div>
        </div>
      </div>

      {/* Status Notice */}
      {!can_render && missing.length > 0 && (
        <div className="flex items-start gap-2 rounded-lg bg-amber-50 p-2.5">
          <HelpCircle size={14} className="mt-0.5 shrink-0 text-amber-600" />
          <p className="text-[11px] font-medium leading-relaxed text-amber-700">
            초안 작성을 위해 <span className="font-bold underline">{missing.join(', ')}</span> 과정이 더 필요합니다. Foli와 대화를 계속하며 내용을 보충해 주세요.
          </p>
        </div>
      )}

      {can_render && (
        <div className="flex items-start gap-2 rounded-lg bg-emerald-50 p-2.5">
          <CheckCircle2 size={14} className="mt-0.5 shrink-0 text-emerald-600" />
          <p className="text-[11px] font-medium leading-relaxed text-emerald-700">
            충분한 정보가 수집되었습니다! 이제 우측 하단의 [초안 생성] 버튼을 눌러 초안을 작성할 수 있습니다.
          </p>
        </div>
      )}
    </div>
  );
};
