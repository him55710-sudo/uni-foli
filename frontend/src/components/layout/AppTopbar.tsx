import React from 'react';
import { Link } from 'react-router-dom';
import { ArrowLeft, Menu, X } from 'lucide-react';
import { UniFoliLogo } from '../UniFoliLogo';
import { UniversityLogo } from '../UniversityLogo';
import { Button } from '../ui';
import { Topbar } from '../primitives';
import { WorkflowContextHeader } from './WorkflowContextHeader';
import { cn } from '../../lib/cn';

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

const goalToneClasses = [
  {
    shell: 'border-fuchsia-200/60 bg-fuchsia-50/80 text-fuchsia-700 shadow-lg shadow-fuchsia-100/50',
    rank: 'text-fuchsia-600',
    logo: 'bg-white',
  },
  {
    shell: 'border-cyan-200/60 bg-cyan-50/80 text-cyan-700 shadow-lg shadow-cyan-100/50',
    rank: 'text-cyan-600',
    logo: 'bg-white',
  },
  {
    shell: 'border-amber-200/60 bg-amber-50/80 text-amber-700 shadow-lg shadow-amber-100/50',
    rank: 'text-amber-600',
    logo: 'bg-white',
  },
];

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
        <div className="border-b border-white/70 bg-[linear-gradient(180deg,rgba(248,250,255,0.84)_0%,rgba(241,246,255,0.8)_100%)] px-3 py-2.5 md:hidden">
          <div className="flex gap-2.5 overflow-x-auto pb-0.5">
            {visibleGoals.map((goal, index) => {
              const tone = goalToneClasses[index % goalToneClasses.length];

              return (
                <div
                  key={`${goal.university}-${goal.major ?? ''}-${index}`}
                  className={cn('flex min-w-[156px] items-center gap-2.5 rounded-2xl border px-3 py-2 sm:min-w-[176px]', tone.shell)}
                >
                  <UniversityLogo
                    universityName={goal.university}
                    className={cn('h-8 w-8 rounded-xl object-contain p-1.5', tone.logo)}
                    fallbackClassName="border border-[#d6e4ff]"
                  />
                  <div className="min-w-0">
                    <p className={cn('truncate text-[11px] font-black', tone.rank)}>{index + 1}순위</p>
                    <p className="truncate text-xs font-black text-slate-900">{goal.university}</p>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      ) : null}

      <Topbar>
        <WorkflowContextHeader sectionLabel={currentSectionLabel} summary={summary} />

        <div className="flex items-center gap-3">
          {visibleGoals.length ? (
            <div className="hidden max-w-[620px] items-center gap-2.5 overflow-x-auto rounded-[1.6rem] border border-white/70 bg-white/68 px-3.5 py-2.5 shadow-[0_14px_30px_rgba(42,64,132,0.08)] backdrop-blur-xl lg:flex">
              {visibleGoals.map((goal, index) => {
                const tone = goalToneClasses[index % goalToneClasses.length];

                return (
                  <div
                    key={`${goal.university}-${goal.major ?? ''}-${index}`}
                    className={cn('flex min-w-[186px] items-center gap-2.5 rounded-2xl border px-3 py-2', tone.shell)}
                  >
                    <UniversityLogo
                      universityName={goal.university}
                      className={cn('h-8 w-8 rounded-xl object-contain p-1.5', tone.logo)}
                      fallbackClassName="border border-[#d6e4ff]"
                    />
                    <div className="min-w-0">
                      <p className={cn('truncate text-[11px] font-black', tone.rank)}>{index + 1}순위</p>
                      <p className="truncate text-xs font-black text-slate-900">{goal.university}</p>
                    </div>
                  </div>
                );
              })}
            </div>
          ) : null}

          <Link
            to="/"
            className="inline-flex items-center gap-2 rounded-2xl border border-white/70 bg-white/84 px-3.5 py-2.5 text-sm font-bold text-violet-700 shadow-[0_12px_26px_rgba(42,64,132,0.08)] backdrop-blur-md transition-colors hover:bg-[#f7f9ff]"
          >
            <ArrowLeft size={14} />
            공개 페이지
          </Link>
        </div>
      </Topbar>
    </>
  );
}
