import { CheckCircle2, Loader2, Star } from 'lucide-react';
import type { GuidedChoiceGroup, GuidedChoiceOption } from '../../../lib/guidedChat';
import { cn } from '../../../lib/cn';
import { getChoiceValue, isChoiceBusy, isChoiceDisabled } from '../utils/guidedChoiceHelpers';

export interface ChoiceCardOption extends GuidedChoiceOption {
  suggestion_type?: 'interest' | 'subject' | 'major' | null;
  is_starred?: boolean;
}

interface ChoiceCardGroupProps {
  group?: GuidedChoiceGroup;
  groupId?: string;
  title?: string;
  style?: 'cards' | 'chips' | 'buttons';
  options?: ChoiceCardOption[];
  selectedId?: string | null;
  isGuidedActionLoading?: boolean;
  selectingTopicId?: string | null;
  disabled?: boolean;
  onSelect: (groupId: string, option: GuidedChoiceOption) => void;
  onStarToggle?: (optionId: string, isStarred: boolean, label: string) => void;
}

const TYPE_LABELS = {
  interest: '사용자 관심형',
  subject: '교과과목 심화형',
  major: '목표학과 융합형',
};

const TYPE_COLORS = {
  interest: 'bg-amber-50 text-amber-600 border-amber-200',
  subject: 'bg-blue-50 text-blue-600 border-blue-200',
  major: 'bg-purple-50 text-purple-600 border-purple-200',
};

export function ChoiceCardGroup({
  group,
  groupId,
  title,
  style,
  options,
  selectedId,
  isGuidedActionLoading = false,
  selectingTopicId,
  disabled = false,
  onSelect,
  onStarToggle,
}: ChoiceCardGroupProps) {
  const resolvedGroupId = group?.id || groupId || 'choice-group';
  const resolvedTitle = group?.title || title || '선택하세요.';
  const resolvedStyle = group?.style || style || 'cards';
  const resolvedOptions = (group?.options as ChoiceCardOption[]) || options || [];
  const isLargeTopicSelection = resolvedGroupId === 'topic-selection' && resolvedOptions.length > 24;

  if (!resolvedOptions.length) {
    return null;
  }

  return (
    <section className="rounded-2xl border border-slate-100 bg-white p-4 shadow-sm">
      <p className="mb-4 text-[12px] font-black uppercase tracking-widest text-slate-400">{resolvedTitle}</p>
      <div
        className={cn(
          resolvedStyle === 'chips' ? 'flex flex-wrap gap-2' : 'grid gap-3',
          resolvedStyle === 'buttons' && 'sm:grid-cols-2',
          isLargeTopicSelection && 'max-h-[520px] overflow-y-auto pr-1',
        )}
      >
        {resolvedOptions.map((option) => {
          const optionValue = getChoiceValue(option);
          const busy = isChoiceBusy(resolvedGroupId, option, selectingTopicId);
          const optionDisabled = disabled || isChoiceDisabled(resolvedGroupId, option, isGuidedActionLoading, selectingTopicId);
          const selected = selectedId === option.id || selectedId === optionValue;
          const type = option.suggestion_type;

          if (resolvedStyle === 'chips') {
            return (
              <button
                key={`${resolvedGroupId}:${option.id}`}
                type="button"
                onClick={() => onSelect(resolvedGroupId, option)}
                disabled={optionDisabled}
                className={cn(
                  'inline-flex min-h-9 items-center justify-center gap-1.5 rounded-full border px-4 py-2 text-[13px] font-bold transition-all',
                  selected
                    ? 'border-blue-400 bg-blue-50 text-blue-700'
                    : 'border-slate-200 bg-white text-slate-600 hover:border-blue-300 hover:bg-slate-50',
                  optionDisabled && 'cursor-not-allowed opacity-60',
                )}
              >
                {busy ? <Loader2 size={13} className="animate-spin" /> : null}
                {option.label}
              </button>
            );
          }

          return (
            <div
              key={`${resolvedGroupId}:${option.id}`}
              className={cn(
                'group relative overflow-hidden rounded-2xl border transition-all',
                selected
                  ? 'border-blue-500 bg-blue-50/30'
                  : 'border-slate-100 bg-white hover:border-blue-200 hover:shadow-md',
                optionDisabled && 'opacity-60',
              )}
            >
              <button
                type="button"
                onClick={() => onSelect(resolvedGroupId, option)}
                disabled={optionDisabled}
                className="w-full p-4 text-left"
              >
                <div className="flex flex-col gap-2">
                  {type && (
                    <span className={cn(
                      'w-fit rounded-md border px-1.5 py-0.5 text-[10px] font-black uppercase tracking-tighter',
                      TYPE_COLORS[type]
                    )}>
                      {TYPE_LABELS[type]}
                    </span>
                  )}
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <p className="text-[15px] font-black leading-tight text-slate-900 group-hover:text-blue-600">
                        {option.label}
                      </p>
                      {option.description ? (
                        <p className="mt-1.5 text-[13px] font-medium leading-relaxed text-slate-500">
                          {option.description}
                        </p>
                      ) : null}
                    </div>
                  </div>
                </div>
              </button>
              
              <div className="absolute right-3 top-3 flex items-center gap-2">
                {onStarToggle && (
                  <button
                    type="button"
                    onClick={(e) => {
                      e.stopPropagation();
                      onStarToggle(option.id, !option.is_starred, option.label);
                    }}
                    className={cn(
                      'flex h-8 w-8 items-center justify-center rounded-full transition-all',
                      option.is_starred ? 'text-amber-400' : 'text-slate-200 hover:bg-slate-100 hover:text-slate-400'
                    )}
                  >
                    <Star size={18} fill={option.is_starred ? 'currentColor' : 'none'} strokeWidth={2.5} />
                  </button>
                )}
                <div className="text-blue-600">
                  {busy ? <Loader2 size={18} className="animate-spin" /> : selected ? <CheckCircle2 size={18} /> : null}
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </section>
  );
}
