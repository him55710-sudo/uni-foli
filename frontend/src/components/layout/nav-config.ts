import type { LucideIcon } from 'lucide-react';
import { Archive, FileSearch, FolderOpen, Home, PenTool, Settings, TrendingUp } from 'lucide-react';

export interface AppNavItem {
  path: string;
  label: string;
  hint: string;
  icon: LucideIcon;
  stage: string;
}

export interface AppNavSection {
  key: string;
  label: string;
  hint: string;
  items: AppNavItem[];
}

export const appNavSections: AppNavSection[] = [
  {
    key: 'setup',
    label: '준비',
    hint: '목표와 자료 정리',
    items: [
      { path: '/app', label: '대시보드', hint: '현재 진행 상태 확인', icon: Home, stage: '개요' },
      { path: '/app/record', label: '기록 업로드', hint: '학생부 PDF 업로드', icon: FolderOpen, stage: '1단계' },
    ],
  },
  {
    key: 'analyze',
    label: '분석',
    hint: '근거 기반 진단',
    items: [
      { path: '/app/diagnosis', label: '진단', hint: '강점과 보완점 확인', icon: FileSearch, stage: '2단계' },
      { path: '/app/trends', label: '트렌드', hint: '참고 데이터 확인', icon: TrendingUp, stage: '참고' },
    ],
  },
  {
    key: 'execute',
    label: '작성',
    hint: '초안 작성과 수정',
    items: [
      { path: '/app/workshop', label: '문서 작성', hint: '초안 작성 공간', icon: PenTool, stage: '3단계' },
      { path: '/app/archive', label: '보관함', hint: '완료 문서 모아보기', icon: Archive, stage: '기록' },
    ],
  },
  {
    key: 'account',
    label: '계정',
    hint: '프로필과 환경 설정',
    items: [{ path: '/app/settings', label: '설정', hint: '계정·개인정보·환경 설정', icon: Settings, stage: '계정' }],
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
