import React from 'react';
import { Network, ArrowRight, Target, AlertCircle, Link, Bookmark, Activity, Zap, Compass, Shield } from 'lucide-react';
import { motion } from 'framer-motion';
import { SurfaceCard } from '../primitives';
import { RelationalGraph } from '../../types/api';

interface DiagnosisRelationalGraphProps {
  graph: RelationalGraph;
}

export const DiagnosisRelationalGraph: React.FC<DiagnosisRelationalGraphProps> = ({ graph }) => {
  if (!graph) return null;

  const container = {
    hidden: { opacity: 0 },
    show: {
      opacity: 1,
      transition: {
        staggerChildren: 0.1
      }
    }
  };

  const item = {
    hidden: { opacity: 0, y: 20 },
    show: { opacity: 1, y: 0 }
  };

  return (
    <motion.div 
      variants={container}
      initial="hidden"
      animate="show"
      className="mt-16 space-y-12"
    >
      {/* Section Header */}
      <div className="relative">
        <div className="absolute -left-4 top-0 h-full w-1 bg-gradient-to-b from-indigo-500 to-transparent rounded-full" />
        <div className="flex items-center gap-4 mb-2">
          <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-indigo-500/10 text-indigo-400 border border-indigo-500/20 shadow-[0_0_20px_rgba(99,102,241,0.1)]">
            <Network size={24} />
          </div>
          <div>
            <h4 className="text-2xl font-black tracking-tight text-white uppercase">
              Relational Flow Analysis
            </h4>
            <div className="flex items-center gap-2">
              <span className="h-px w-8 bg-indigo-500/50" />
              <p className="text-sm font-bold text-slate-400 uppercase tracking-[0.2em]">학생부 유기적 연결성 및 심층 구조 분석</p>
            </div>
          </div>
        </div>
      </div>

      <div className="grid gap-8 lg:grid-cols-2">
        {/* Continuity Links - Theme: The Thread */}
        {graph.continuity_links && graph.continuity_links.length > 0 && (
          <motion.div variants={item}>
            <SurfaceCard className="h-full border-slate-800 bg-slate-900/40 backdrop-blur-xl p-8 hover:border-indigo-500/30 transition-all duration-500 group">
              <div className="mb-8 flex items-center justify-between">
                <div className="flex items-center gap-3 text-indigo-400">
                  <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-indigo-500/20 border border-indigo-500/30">
                    <Link size={20} />
                  </div>
                  <div>
                    <span className="block text-lg font-black text-white italic">주제 심화 흐름</span>
                    <span className="text-[10px] font-bold text-slate-500 uppercase tracking-widest">Academic Continuity Thread</span>
                  </div>
                </div>
                <div className="px-3 py-1 rounded-full bg-indigo-500/10 border border-indigo-500/20">
                  <span className="text-[10px] font-black text-indigo-400 uppercase">분석 완료</span>
                </div>
              </div>

              <div className="space-y-6">
                {graph.continuity_links.map((link, idx) => (
                  <div key={idx} className="relative pl-6 before:absolute before:left-0 before:top-2 before:bottom-2 before:w-px before:bg-gradient-to-b before:from-indigo-500/50 before:to-transparent">
                    <div className="flex items-center flex-wrap gap-2 mb-3">
                      {link.subject_chain.map((subject, sIdx) => (
                        <React.Fragment key={sIdx}>
                          {sIdx > 0 && <ArrowRight size={12} className="text-slate-600" />}
                          <span className="px-2 py-0.5 text-[11px] font-black bg-slate-800 text-slate-300 rounded border border-slate-700">
                            {subject}
                          </span>
                        </React.Fragment>
                      ))}
                    </div>
                    <p className="text-slate-300 font-medium leading-relaxed mb-2">
                      {link.description}
                    </p>
                    <div className="flex items-center gap-3">
                      <div className="flex items-center gap-1.5">
                        <Activity size={12} className="text-indigo-400" />
                        <span className="text-[10px] font-bold text-slate-500 uppercase">연계 강도</span>
                        <div className="flex gap-0.5">
                          {[1, 2, 3].map((s) => (
                            <div 
                              key={s} 
                              className={`w-3 h-1 rounded-full ${
                                s <= (link.strength === 'strong' ? 3 : link.strength === 'moderate' ? 2 : 1) 
                                ? 'bg-indigo-500' : 'bg-slate-800'
                              }`} 
                            />
                          ))}
                        </div>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </SurfaceCard>
          </motion.div>
        )}

        {/* Theme Clusters - Theme: Core Identity */}
        {graph.theme_clusters && graph.theme_clusters.length > 0 && (
          <motion.div variants={item}>
            <SurfaceCard className="h-full border-slate-800 bg-slate-900/40 backdrop-blur-xl p-8 hover:border-violet-500/30 transition-all duration-500">
              <div className="mb-8 flex items-center justify-between">
                <div className="flex items-center gap-3 text-violet-400">
                  <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-violet-500/20 border border-violet-500/30">
                    <Zap size={20} />
                  </div>
                  <div>
                    <span className="block text-lg font-black text-white italic">핵심 탐구 클러스터</span>
                    <span className="text-[10px] font-bold text-slate-500 uppercase tracking-widest">Core Intellectual Clusters</span>
                  </div>
                </div>
                <Compass size={18} className="text-slate-700" />
              </div>

              <div className="space-y-6">
                {graph.theme_clusters.map((cluster, idx) => (
                  <div key={idx} className="p-4 rounded-2xl bg-slate-800/50 border border-slate-700/50 group/item hover:bg-slate-800 transition-colors">
                    <div className="flex items-center justify-between mb-3">
                      <h5 className="font-black text-white">{cluster.theme}</h5>
                      <span className={`text-[10px] font-black px-2 py-0.5 rounded-full border ${
                        cluster.depth_level === 'integrated' 
                        ? 'text-emerald-400 border-emerald-500/20 bg-emerald-500/10' 
                        : cluster.depth_level === 'applied'
                        ? 'text-violet-400 border-violet-500/20 bg-violet-500/10'
                        : 'text-blue-400 border-blue-500/20 bg-blue-500/10'
                      }`}>
                        {cluster.depth_level === 'integrated' ? '융합형' : cluster.depth_level === 'applied' ? '심화응용형' : '탐색형'}
                      </span>
                    </div>
                    <ul className="space-y-2">
                      {cluster.evidence.slice(0, 3).map((ev, eIdx) => (
                         <li key={eIdx} className="flex gap-2 text-sm text-slate-400">
                           <span className="text-violet-500 mt-1">•</span>
                           <span className="font-medium leading-tight">{ev}</span>
                         </li>
                      ))}
                      {cluster.evidence.length > 3 && (
                        <li className="text-[10px] font-black text-slate-600 uppercase tracking-tighter mt-2 ml-4">
                          + {cluster.evidence.length - 3} additional evidence found
                        </li>
                      )}
                    </ul>
                  </div>
                ))}
              </div>
            </SurfaceCard>
          </motion.div>
        )}

        {/* Outlier Activities - Theme: Strategic Risk/Refinement */}
        {graph.outlier_activities && graph.outlier_activities.length > 0 && (
          <motion.div variants={item} className="lg:col-span-2">
            <SurfaceCard className="border-none bg-gradient-to-br from-slate-900 to-slate-950 p-8 ring-1 ring-slate-800 shadow-2xl relative overflow-hidden">
              <div className="absolute top-0 right-0 p-12 opacity-5 pointer-events-none">
                <AlertCircle size={120} />
              </div>
              
              <div className="mb-8 flex items-center gap-3 text-amber-400 relative">
                <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-amber-500/20 border border-amber-500/30">
                  <Shield size={20} />
                </div>
                <div>
                  <span className="block text-lg font-black text-white italic">전략적 파편화 항목 분석</span>
                  <span className="text-[10px] font-bold text-slate-500 uppercase tracking-widest">Fragmentation Risk Assessment</span>
                </div>
              </div>

              <div className="grid md:grid-cols-2 gap-6 relative">
                {graph.outlier_activities.map((outlier, idx) => (
                  <div key={idx} className="flex flex-col gap-3 p-5 bg-slate-800/30 rounded-2xl border border-slate-700/50 hover:bg-slate-800/50 transition-all group">
                    <div className="flex items-center gap-2">
                      <Target size={14} className="text-slate-500 group-hover:text-amber-500 transition-colors" />
                      <p className="text-sm font-black text-slate-200">{outlier.activity}</p>
                    </div>
                    <div className="p-3 bg-slate-900/50 rounded-xl border border-slate-700/30">
                      <p className="text-xs font-medium text-slate-400 leading-relaxed italic">
                        <span className="text-amber-500 font-black not-italic mr-1">[!]</span>
                        {outlier.reason}
                      </p>
                    </div>
                  </div>
                ))}
              </div>

              <div className="mt-8 p-4 rounded-xl bg-indigo-500/5 border border-indigo-500/10 flex items-start gap-3">
                <div className="p-1.5 rounded-lg bg-indigo-500/20 text-indigo-400">
                  <Bookmark size={14} />
                </div>
                <div>
                  <p className="text-[11px] font-bold text-indigo-300 uppercase tracking-wide mb-1">Consultant's Strategic Advice</p>
                  <p className="text-xs text-slate-500 font-medium leading-relaxed">
                    파편화된 항목들은 면접에서 '활동의 동기'와 '본인만의 정의'를 통해 주류 탐구 흐름과 연결시키는 논리가 필요합니다. 
                    워크숍 모듈에서 해당 항목들의 연결 고리를 보완하시기 바랍니다.
                  </p>
                </div>
              </div>
            </SurfaceCard>
          </motion.div>
        )}
      </div>
    </motion.div>
  );
};

