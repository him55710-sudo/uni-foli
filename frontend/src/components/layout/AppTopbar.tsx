import React from 'react';
import { Link } from 'react-router-dom';
import { ArrowLeft, Menu, X } from 'lucide-react';
import { UniFoliLogo } from '../UniFoliLogo';
import { UniversityLogo } from '../UniversityLogo';
import { Button } from '../ui';
import { Topbar } from '../primitives';
import { WorkflowContextHeader } from './WorkflowContextHeader';

interface GoalItem {
  university: string;
  major?: string;
}

interface AppTopbarProps {
  currentSectionLabel: string;
  summary: string;
  isSidebarOpen: boolean;
  onToggleSidebar: () => void;
  primaryGoal?: GoalItem | null;
  rankedGoals?: GoalItem[];
}

export function AppTopbar({
  currentSectionLabel,
  summary,
  isSidebarOpen,
  onToggleSidebar,
  primaryGoal,
  rankedGoals,
}: AppTopbarProps) {
  const visibleGoals = (rankedGoals?.length ? rankedGoals : primaryGoal ? [primaryGoal] : []).slice(0, 6);

  return (
    <>
      <Topbar mobile>
        <Link to="/app">
          <UniFoliLogo size="sm" subtitle={null} />
        </Link>
        <Button variant="ghost" size="icon" aria-label={isSidebarOpen ? '사이드바 닫기' : '사이드바 열기'} onClick={onToggleSidebar}>
          {isSidebarOpen ? <X size={20} /> : <Menu size={20} />}
        </Button>
      </Topbar>

      {visibleGoals.length ? (
        <div className="border-b border-slate-200 bg-blue-50 px-3 py-2 md:hidden">
          <div className="flex gap-2 overflow-x-auto pb-0.5">
            {visibleGoals.map((goal, index) => (
              <div
                key={`${goal.university}-${goal.major ?? ''}-${index}`}
                className="flex min-w-[148px] items-center gap-2 rounded-lg border border-blue-200 bg-white px-2 py-1.5 sm:min-w-[170px]"
              >
                <UniversityLogo
                  universityName={goal.university}
                  className="h-7 w-7 rounded-md bg-slate-100 object-contain p-1"
                  fallbackClassName="border border-blue-100"
                />
                <div className="min-w-0">
                  <p className="truncate text-[11px] font-black text-blue-700">{index + 1}순위</p>
                  <p className="truncate text-xs font-black text-slate-800">{goal.university}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      ) : null}

      <Topbar>
        <WorkflowContextHeader sectionLabel={currentSectionLabel} summary={summary} />

        <div className="flex items-center gap-3">
          {visibleGoals.length ? (
            <div className="hidden max-w-[560px] items-center gap-2 overflow-x-auto rounded-2xl border border-blue-200 bg-blue-50 px-3 py-2 lg:flex">
              {visibleGoals.map((goal, index) => (
                <div
                  key={`${goal.university}-${goal.major ?? ''}-${index}`}
                  className="flex min-w-[180px] items-center gap-2 rounded-lg border border-blue-100 bg-white px-2 py-1.5"
                >
                  <UniversityLogo
                    universityName={goal.university}
                    className="h-7 w-7 rounded-md bg-slate-100 object-contain p-1"
                    fallbackClassName="border border-blue-100"
                  />
                  <div className="min-w-0">
                    <p className="truncate text-[11px] font-black text-blue-700">{index + 1}순위</p>
                    <p className="truncate text-xs font-black text-slate-800">{goal.university}</p>
                  </div>
                </div>
              ))}
            </div>
          ) : null}

          <Link
            to="/"
            className="inline-flex items-center gap-2 rounded-2xl border border-slate-300 bg-white px-3 py-2 text-sm font-bold text-slate-600 hover:bg-slate-50"
          >
            <ArrowLeft size={14} />
            공개 페이지
          </Link>
        </div>
      </Topbar>
    </>
  );
}
