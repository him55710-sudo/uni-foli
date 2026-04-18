import assert from 'node:assert/strict';
import test from 'node:test';

import { extractDiagnosisMajorDirectionCandidates } from '../src/lib/chatbotMode';
import { buildMajorChipLabels, resolveTrendMajorKey } from '../src/lib/trendCopilot';

test('extractDiagnosisMajorDirectionCandidates reads summary top3 labels first', () => {
  const majors = extractDiagnosisMajorDirectionCandidates({
    diagnosis_summary_json: {
      major_direction_candidates_top3: [
        { label: '컴퓨터공학' },
        { label: '데이터사이언스' },
        { label: '소프트웨어융합' },
      ],
    },
  });

  assert.deepEqual(majors, ['컴퓨터공학', '데이터사이언스', '소프트웨어융합']);
});

test('extractDiagnosisMajorDirectionCandidates falls back to recommended directions', () => {
  const majors = extractDiagnosisMajorDirectionCandidates({
    recommended_directions: [
      { label: '건축공학' },
      { label: '도시공학' },
      { label: '공간디자인' },
    ],
  });

  assert.deepEqual(majors, ['건축공학', '도시공학', '공간디자인']);
});

test('buildMajorChipLabels prioritizes explicit major and keeps default chips', () => {
  const chips = buildMajorChipLabels({
    explicitMajor: '기계공학',
    inferredMajors: ['컴퓨터공학', '바이오의공학', '건축공학'],
  });

  assert.equal(chips[0], '기계공학');
  assert.equal(chips[1], '컴퓨터공학');
  assert(chips.includes('건축'));
  assert(chips.includes('경영'));
});

test('resolveTrendMajorKey maps broader labels into trend buckets', () => {
  assert.equal(resolveTrendMajorKey('컴퓨터공학'), '컴공');
  assert.equal(resolveTrendMajorKey('의생명공학'), '바이오');
  assert.equal(resolveTrendMajorKey('공공행정'), '사회과학');
});
