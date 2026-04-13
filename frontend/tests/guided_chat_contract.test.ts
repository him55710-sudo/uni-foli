import assert from 'node:assert/strict';
import test from 'node:test';

import {
  applyTopicSelectionToUiState,
  createInitialGuidedChatUiState,
  type GuidedTopicSelectionResponse,
} from '../src/lib/guidedChat';

test('clicking a topic updates draft-side guided state', () => {
  const initialState = createInitialGuidedChatUiState('# 기존 초안');

  const selectionResponse: GuidedTopicSelectionResponse = {
    phase: 'page_range_selection',
    assistant_message: '분량을 선택해 주세요.',
    selected_topic_id: 'topic-2',
    selected_title: '미분 개념을 실험 데이터와 연결한 탐구 보고서',
    recommended_page_ranges: [
      {
        label: '3~5쪽',
        min_pages: 3,
        max_pages: 5,
        why_this_length: '근거와 해석을 균형 있게 담기 좋습니다.',
      },
    ],
    recommended_outline: [
      {
        title: '1. 탐구 배경',
        purpose: '주제의 필요성과 문제의식을 설명합니다.',
      },
    ],
    starter_draft_markdown: '# 시작 초안\n\n## 1. 탐구 배경\n...',
    guidance_message: '선택한 주제 기준으로 분량과 구조를 정해보세요.',
  };

  const nextState = applyTopicSelectionToUiState(initialState, selectionResponse);

  assert.equal(nextState.selectedTopicId, 'topic-2');
  assert.equal(nextState.selectedTitle, selectionResponse.selected_title);
  assert.equal(nextState.draftMarkdown, selectionResponse.starter_draft_markdown);
  assert.equal(nextState.pageRanges.length, 1);
  assert.equal(nextState.outline.length, 1);
});
