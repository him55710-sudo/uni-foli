import type { LucideIcon } from 'lucide-react';
import { Archive, FileSearch, Compass, PenTool, Settings, TrendingUp, FileText, MessageSquareQuote } from 'lucide-react';

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
    label: '핵심 서비스',
    hint: '성장을 위한 핵심 도구',
    items: [
      { path: '/app/diagnosis', label: 'AI 진단', hint: '학생부 업로드 및 정밀 진단', icon: FileSearch },
      { path: '/app/diagnosis/history', label: '진단서', hint: '생성된 리포트 모아보기', icon: FileText },
      { path: '/app/trends', label: '탐구 설계', hint: '전공 주제 및 탐구 방향 탐색', icon: Compass },
      { path: '/app/workshop', label: '문서 작성', hint: '탐구 보고서 초안 및 워크숍', icon: PenTool },
      { path: '/app/interview', label: '면접 준비', hint: 'AI 실전 모의 면접', icon: MessageSquareQuote },
    ],
  },
  {
    key: 'management',
    label: '관리',
    hint: '자료 및 환경 관리',
    items: [
      { path: '/app/archive', label: '보관함', hint: '완료된 문서 및 백업', icon: Archive },
      { path: '/app/settings', label: '설정', hint: '계정·개인정보·환경 설정', icon: Settings },
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
