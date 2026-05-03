import type { LucideIcon } from 'lucide-react';
import {
  Archive,
  Compass,
  FileSearch,
  FileText,
  MessageSquareQuote,
  PenTool,
  Settings,
} from 'lucide-react';

export interface AppNavItem {
  path: string;
  label: string;
  hint: string;
  icon: LucideIcon;
  stage?: string;
}

export interface AppNavSection {
  key: string;
  label: string;
  hint: string;
  items: AppNavItem[];
}

export const appNavSections: AppNavSection[] = [
  {
    key: 'main',
    label: '준비 흐름',
    hint: '진단부터 작성, 면접까지',
    items: [
      {
        path: '/app/diagnosis',
        label: 'AI 진단',
        hint: '생기부 PDF 업로드와 진단',
        icon: FileSearch,
      },
      {
        path: '/app/trends',
        label: '탐구 설계',
        hint: '전공 주제와 탐구 방향 탐색',
        icon: Compass,
      },
      {
        path: '/app/workshop',
        label: '문서 작성',
        hint: '탐구 보고서 초안과 워크숍',
        icon: PenTool,
      },
      {
        path: '/app/interview',
        label: '면접 준비',
        hint: '생기부 기반 예상 질문 연습',
        icon: MessageSquareQuote,
      },
    ],
  },
  {
    key: 'management',
    label: '보관',
    hint: '완료 자료와 환경 관리',
    items: [
      {
        path: '/app/archive',
        label: '탐구 보관함',
        hint: '완료한 탐구 문서와 백업',
        icon: Archive,
      },
      {
        path: '/app/settings',
        label: '설정',
        hint: '계정과 환경 설정',
        icon: Settings,
      },
    ],
  },
];

export function isNavItemActive(pathname: string, itemPath: string) {
  if (itemPath === '/app') {
    return pathname === '/app';
  }
  return pathname === itemPath || pathname.startsWith(`${itemPath}/`);
}

export function resolveCurrentNavSection(pathname: string): AppNavSection {
  return appNavSections.find(section => section.items.some(item => isNavItemActive(pathname, item.path))) ?? appNavSections[0];
}
