import assert from 'node:assert/strict';
import test from 'node:test';

import {
  inferGuidedPhase,
  isGuidedSetupComplete,
  resolvePageRangeLabel,
  resolveStructureOptionId,
} from '../src/lib/guidedConversation';

test('guided phase inference respects explicit phase and saved selections', () => {
  assert.equal(inferGuidedPhase({ phase: 'structure_selection' }), 'structure_selection');
  assert.equal(inferGuidedPhase({ selected_structure_id: 'structure-balanced' }), 'drafting_next_step');
  assert.equal(inferGuidedPhase({ selected_page_range_label: '3~5쪽' }), 'structure_selection');
  assert.equal(inferGuidedPhase({ selected_topic_id: 'topic-1' }), 'page_range_selection');
  assert.equal(inferGuidedPhase({ subject: '수2' }), 'specific_topic_check');
  assert.equal(inferGuidedPhase(null), 'subject_input');
});

test('guided setup completion gate opens after structure selection', () => {
  assert.equal(isGuidedSetupComplete('drafting_next_step'), true);
  assert.equal(isGuidedSetupComplete('freeform_coauthoring'), true);
  assert.equal(isGuidedSetupComplete('topic_selection'), false);
});

test('guided option resolvers match labels safely', () => {
  const selectedPage = resolvePageRangeLabel('3~5쪽으로 할래요', [
    { label: '1~3쪽', min_pages: 1, max_pages: 3, why_this_length: '짧게 정리' },
    { label: '3~5쪽', min_pages: 3, max_pages: 5, why_this_length: '균형형' },
  ]);
  assert.equal(selectedPage, '3~5쪽');

  const structureId = resolveStructureOptionId('세특 연결 강조형으로 진행', [
    { id: 'structure-balanced', label: '균형형' },
    { id: 'structure-record-linked', label: '세특 연결 강조형' },
  ]);
  assert.equal(structureId, 'structure-record-linked');
});
