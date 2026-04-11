import React from 'react';
import { Network, ArrowRight, Target, AlertCircle, Link, Bookmark, Activity } from 'lucide-react';
import { SurfaceCard } from '../primitives';
import { RelationalGraph } from '../../types/api';

interface DiagnosisRelationalGraphProps {
  graph: RelationalGraph;
}

export const DiagnosisRelationalGraph: React.FC<DiagnosisRelationalGraphProps> = ({ graph }) => {
  if (!graph) return null;

  return (
    <div className="mt-8 space-y-6">
      <div className="flex items-center gap-3 mb-6">
        <div className="flex h-10 w-10 items-center justify-center rounded-2xl bg-blue-100 text-blue-700">
          <Network size={20} />
        </div>
        <div>
          <h4 className="text-xl font-black text-slate-800">탐구 흐름 및 융합 분석</h4>
          <p className="text-sm font-bold text-slate-500">학생부 항목 간의 유기적 연결성 및 다면적 분석</p>
        </div>
      </div>

      <div className="grid gap-6 md:grid-cols-2">
        {/* Continuity Links */}
        {graph.continuity_links && graph.continuity_links.length > 0 && (
          <SurfaceCard className="border-none bg-blue-50/50 p-6 ring-1 ring-blue-100">
            <div className="mb-4 flex items-center gap-2 text-blue-700">
              <div className="flex h-8 w-8 items-center justify-center rounded-xl bg-blue-500 text-white shadow-lg shadow-blue-500/20">
                <Link size={18} />
              </div>
              <span className="text-lg font-black italic">주제 심화 흐름</span>
              <span className="text-sm font-bold opacity-60">교과 융합 및 학년별 연계</span>
            </div>
            <ul className="space-y-4">
              {graph.continuity_links.map((link, idx) => (
                <li key={idx} className="flex flex-col gap-1.5">
                  <div className="flex items-center flex-wrap gap-2 text-sm font-bold text-slate-600">
                    {link.subject_chain.map((subject, sIdx) => (
                      <React.Fragment key={sIdx}>
                        {sIdx > 0 && <ArrowRight size={14} className="text-blue-300" />}
                        <span className="bg-blue-100/50 text-blue-800 px-2 py-0.5 rounded outline outline-1 outline-blue-200">{subject}</span>
                      </React.Fragment>
                    ))}
                  </div>
                  <p className="text-base font-medium text-slate-700 leading-relaxed pl-1 border-l-2 border-blue-200 ml-1 mt-1">
                    {link.description}
                  </p>
                  <p className="text-xs font-black text-slate-400 pl-1 ml-1">연계 강도: {link.strength === 'strong' ? '강함' : link.strength === 'moderate' ? '보통' : '약함'}</p>
                </li>
              ))}
            </ul>
          </SurfaceCard>
        )}

        {/* Theme Clusters */}
        {graph.theme_clusters && graph.theme_clusters.length > 0 && (
          <SurfaceCard className="border-none bg-indigo-50/50 p-6 ring-1 ring-indigo-100">
            <div className="mb-4 flex items-center gap-2 text-indigo-700">
              <div className="flex h-8 w-8 items-center justify-center rounded-xl bg-indigo-500 text-white shadow-lg shadow-indigo-500/20">
                <Bookmark size={18} />
              </div>
              <span className="text-lg font-black italic">핵심 탐구 클러스터</span>
              <span className="text-sm font-bold opacity-60">다빈도 출현 핵심 테마</span>
            </div>
            <ul className="space-y-4">
              {graph.theme_clusters.map((cluster, idx) => (
                <li key={idx} className="flex flex-col gap-2">
                  <div className="flex items-center gap-2">
                    <span className="text-base font-bold text-indigo-900 leading-tight">
                      {cluster.theme}
                    </span>
                    <span className="text-[10px] font-black tracking-wider uppercase text-white bg-indigo-600/70 px-2 py-0.5 rounded-full">
                      {cluster.depth_level === 'integrated' ? '융합형' : cluster.depth_level === 'applied' ? '심화응용형' : '탐색형'}
                    </span>
                  </div>
                  <div className="pl-3 border-l-2 border-indigo-200">
                    <ul className="space-y-1">
                      {cluster.evidence.slice(0, 3).map((ev, eIdx) => (
                         <li key={eIdx} className="text-sm text-slate-600 font-medium list-disc ml-4">{ev}</li>
                      ))}
                      {cluster.evidence.length > 3 && (
                        <li className="text-xs text-slate-400 font-bold ml-4 mt-1">외 {cluster.evidence.length - 3}건 발견</li>
                      )}
                    </ul>
                  </div>
                </li>
              ))}
            </ul>
          </SurfaceCard>
        )}

        {/* Outlier Activities */}
        {graph.outlier_activities && graph.outlier_activities.length > 0 && (
          <SurfaceCard className="border-none bg-slate-50 p-6 ring-1 ring-slate-200 md:col-span-2">
            <div className="mb-4 flex items-center gap-2 text-slate-700">
              <div className="flex h-8 w-8 items-center justify-center rounded-xl bg-slate-400 text-white shadow-lg shadow-slate-400/20">
                <AlertCircle size={18} />
              </div>
              <span className="text-lg font-black italic">연결성 부족 / 파편화 항목</span>
              <span className="text-sm font-bold opacity-60">흐름상 개연성이 다소 아쉬운 활동</span>
            </div>
            <ul className="grid md:grid-cols-2 gap-4">
              {graph.outlier_activities.map((outlier, idx) => (
                <li key={idx} className="flex flex-col gap-1 p-4 bg-white rounded-xl shadow-sm border border-slate-100">
                   <p className="text-sm font-bold text-slate-800 border-b border-slate-100 pb-2 mb-1">{outlier.activity}</p>
                   <p className="text-xs font-medium text-slate-500 leading-relaxed">{outlier.reason}</p>
                </li>
              ))}
            </ul>
          </SurfaceCard>
        )}
      </div>
    </div>
  );
};
