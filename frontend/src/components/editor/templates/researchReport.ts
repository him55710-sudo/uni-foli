import type { JSONContent } from '@tiptap/react';

function text(value: string, marks?: JSONContent['marks']): JSONContent[] {
  return value ? [{ type: 'text', text: value, marks }] : [];
}

function paragraph(value: string, marks?: JSONContent['marks']): JSONContent {
  return {
    type: 'paragraph',
    content: text(value, marks),
  };
}

function heading(level: 1 | 2 | 3, value: string, textAlign?: string): JSONContent {
  return {
    type: 'heading',
    attrs: textAlign ? { level, textAlign } : { level },
    content: text(value),
  };
}

function list(items: string[], ordered = false): JSONContent {
  return {
    type: ordered ? 'orderedList' : 'bulletList',
    content: items.map((item) => ({
      type: 'listItem',
      content: [paragraph(item)],
    })),
  };
}

function table(headers: string[], rows: string[][]): JSONContent {
  return {
    type: 'table',
    content: [
      {
        type: 'tableRow',
        content: headers.map((header) => ({
          type: 'tableHeader',
          content: [paragraph(header)],
        })),
      },
      ...rows.map((row) => ({
        type: 'tableRow',
        content: row.map((cell) => ({
          type: 'tableCell',
          content: [paragraph(cell)],
        })),
      })),
    ],
  };
}

export function getResearchReportTemplate(): JSONContent {
  return {
    type: 'doc',
    content: [
      heading(1, '탐구 보고서', 'center'),
      paragraph('[탐구 주제를 입력하세요]', [{ type: 'bold' }]),
      paragraph('학교: __________    학년/반: __________'),
      paragraph('이름: __________    작성일: ____년 __월 __일'),
      { type: 'horizontalRule' },

      heading(2, '목차'),
      list(
        [
          '탐구 동기 및 목적',
          '이론적 배경',
          '탐구 방법',
          '탐구 결과',
          '결론 및 제언',
          '학생부 기록 연결',
          '참고 문헌',
        ],
        true,
      ),
      { type: 'horizontalRule' },

      heading(2, 'I. 탐구 동기 및 목적'),
      heading(3, '1. 탐구 동기'),
      paragraph(
        '이 탐구를 시작하게 된 계기와 학생부에서 확인되는 활동, 수업, 진로 경험을 연결해 작성하세요.',
        [{ type: 'italic' }],
      ),
      paragraph(''),
      heading(3, '2. 탐구 목적'),
      paragraph('탐구를 통해 확인하려는 내용을 한 문장의 탐구 질문으로 정리하세요.', [{ type: 'italic' }]),
      paragraph(''),

      heading(2, 'II. 이론적 배경'),
      paragraph('탐구 주제와 관련된 핵심 개념, 선행 연구, 공신력 있는 기준을 정리하고 출처를 표시하세요.', [
        { type: 'italic' },
      ]),
      paragraph(''),

      heading(2, 'III. 탐구 방법'),
      heading(3, '1. 탐구 설계'),
      paragraph('실험, 설문, 문헌조사, 비교분석, 모델링 등 어떤 방식으로 탐구할지 설명하세요.', [
        { type: 'italic' },
      ]),
      paragraph(''),
      heading(3, '2. 탐구 대상 및 도구'),
      paragraph('탐구 대상, 자료, 측정 기준, 사용 도구를 구체적으로 적으세요.', [{ type: 'italic' }]),
      paragraph(''),
      heading(3, '3. 탐구 절차'),
      list(['1단계:', '2단계:', '3단계:'], true),

      heading(2, 'IV. 탐구 결과'),
      paragraph('수집한 데이터와 분석 결과를 표, 그래프, 도면, 이미지 등으로 정리하세요.', [{ type: 'italic' }]),
      table(['항목', '결과', '해석'], [['', '', ''], ['', '', '']]),
      paragraph(''),

      heading(2, 'V. 결론 및 제언'),
      heading(3, '1. 결론'),
      paragraph('탐구 질문에 대한 답을 결과 근거와 함께 정리하세요.', [{ type: 'italic' }]),
      paragraph(''),
      heading(3, '2. 한계 및 후속 탐구'),
      paragraph('탐구의 한계와 다음에 보완할 내용을 구체적으로 제안하세요.', [{ type: 'italic' }]),
      paragraph(''),

      heading(2, '학생부 기록 연결'),
      paragraph('이 보고서가 학생부의 어떤 과목, 창체, 진로 활동과 이어지는지 정리하세요.', [{ type: 'italic' }]),
      paragraph(''),

      { type: 'horizontalRule' },
      heading(2, '참고 문헌'),
      list(['저자(연도). 제목. 출처 또는 URL.', '저자(연도). 제목. 출처 또는 URL.'], true),
    ],
  };
}
