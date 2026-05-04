import type { GuidedChoiceGroup, GuidedChoiceOption, GuidedTopicSuggestion } from '../../../lib/guidedChat';

export function buildTopicChoiceGroupFromSuggestions(
  suggestions: GuidedTopicSuggestion[],
  title = `추천 탐구 주제 ${suggestions.length}개 중 하나를 선택해 주세요.`,
): GuidedChoiceGroup {
  return {
    id: 'topic-selection',
    title,
    style: 'cards',
    options: suggestions.map((topic) => ({
      id: topic.id,
      label: topic.title,
      description: topic.why_fit_student,
      value: topic.id,
      suggestion_type: topic.suggestion_type,
      is_starred: topic.is_starred,
    } as any)),
  };
}

export function getChoiceValue(option: GuidedChoiceOption): string {
  return String(option.value || option.id);
}

export function isChoiceBusy(groupId: string, option: GuidedChoiceOption, selectingTopicId?: string | null): boolean {
  return groupId === 'topic-selection' && Boolean(selectingTopicId) && selectingTopicId === getChoiceValue(option);
}

export function isChoiceDisabled(
  groupId: string,
  option: GuidedChoiceOption,
  isGuidedActionLoading?: boolean,
  selectingTopicId?: string | null,
): boolean {
  return Boolean(isGuidedActionLoading || isChoiceBusy(groupId, option, selectingTopicId));
}
