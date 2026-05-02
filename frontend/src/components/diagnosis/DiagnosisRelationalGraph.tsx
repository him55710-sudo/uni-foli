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
      className="space-y-12"
    >
      {/* Section Header */}
      <div className="flex items-center gap-4 mb-8">
        <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-blue-50 text-blue-600 border border-blue-100 shadow-sm">
          <Network size={24} />
        </div>
        <div>
          <h4 className="text-xl font-bold tracking-tight text-slate-900">
            주제 유기성 및 역량 클러스터 분석
          </h4>
          <p className="text-sm font-medium text-slate-500">학생부 기록 간의 유기적 연결성 및 탐구의 심층 구조를 시각화합니다.</p>
        </div>
      </div>

      <div className="grid gap-8 lg:grid-cols-2">
        {/* Continuity Links - Theme: The Thread */}
        {graph.continuity_links && graph.continuity_links.length > 0 && (
          <motion.div variants={item}>
            <SurfaceCard className="h-full border-slate-200 bg-white p-8 hover:shadow-md transition-all duration-300">
              <div className="mb-8 flex items-center justify-between">
                <div className="flex items-center gap-3 text-blue-600">
                  <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-blue-50 border border-blue-100">
                    <Link size={20} />
                  </div>
                  <div>
                    <span className="block text-lg font-bold text-slate-900">주제 심화 흐름</span>
                    <span className="text-[10px] font-bold text-slate-400 uppercase tracking-widest">Academic Continuity Thread</span>
                  </div>
                </div>
              </div>

              <div className="space-y-8">
                {graph.continuity_links.map((link, idx) => (
                  <div key={idx} className="relative pl-6 border-l-2 border-blue-100">
                    <div className="flex items-center flex-wrap gap-2 mb-3">
                      {link.subject_chain.map((subject, sIdx) => (
                        <React.Fragment key={sIdx}>
                          {sIdx > 0 && <ArrowRight size={12} className="text-slate-300" />}
                          <span className="px-2 py-0.5 text-[11px] font-bold bg-slate-50 text-slate-600 rounded border border-slate-100">
                            {subject}
                          </span>
                        </React.Fragment>
                      ))}
                    </div>
                    <p className="text-slate-600 text-[13px] font-medium leading-relaxed mb-3">
                      {link.description}
                    </p>
                    <div className="flex items-center gap-3">
                      <div className="flex items-center gap-1.5">
                        <Activity size={12} className="text-blue-400" />
                        <span className="text-[10px] font-bold text-slate-400 uppercase">연계 강도</span>
                        <div className="flex gap-0.5 ml-1">
                          {[1, 2, 3].map((s) => (
                            <div 
                              key={s} 
                              className={`w-3 h-1 rounded-full ${
                                s <= (link.strength === 'strong' ? 3 : link.strength === 'moderate' ? 2 : 1) 
                                ? 'bg-blue-600' : 'bg-slate-100'
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
            <SurfaceCard className="h-full border-slate-200 bg-white p-8 hover:shadow-md transition-all duration-300">
              <div className="mb-8 flex items-center justify-between">
                <div className="flex items-center gap-3 text-violet-600">
                  <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-violet-50 border border-violet-100">
                    <Zap size={20} />
                  </div>
                  <div>
                    <span className="block text-lg font-bold text-slate-900">핵심 탐구 클러스터</span>
                    <span className="text-[10px] font-bold text-slate-400 uppercase tracking-widest">Core Intellectual Clusters</span>
                  </div>
                </div>
                <Compass size={18} className="text-slate-300" />
              </div>

              <div className="space-y-4">
                {graph.theme_clusters.map((cluster, idx) => (
                  <div key={idx} className="p-5 rounded-2xl bg-slate-50 border border-slate-100 group/item hover:bg-white hover:border-violet-200 transition-all">
                    <div className="flex items-center justify-between mb-3">
                      <h5 className="font-bold text-slate-900">{cluster.theme}</h5>
                      <span className={`text-[10px] font-bold px-2 py-0.5 rounded-md border ${
                        cluster.depth_level === 'integrated' 
                        ? 'text-emerald-600 border-emerald-100 bg-emerald-50' 
                        : cluster.depth_level === 'applied'
                        ? 'text-violet-600 border-violet-100 bg-violet-50'
                        : 'text-blue-600 border-blue-100 bg-blue-50'
                      }`}>
                        {cluster.depth_level === 'integrated' ? '융합형' : cluster.depth_level === 'applied' ? '심화응용형' : '탐색형'}
                      </span>
                    </div>
                    <ul className="space-y-2">
                      {cluster.evidence.slice(0, 3).map((ev, eIdx) => (
                         <li key={eIdx} className="flex gap-2 text-[13px] text-slate-600">
                           <span className="text-violet-400 mt-1">•</span>
                           <span className="font-medium leading-tight">{ev}</span>
                         </li>
                      ))}
                      {cluster.evidence.length > 3 && (
                        <li className="text-[10px] font-bold text-slate-400 uppercase tracking-tight mt-2 ml-4">
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
            <SurfaceCard className="border-slate-200 bg-slate-50 p-8 shadow-sm relative overflow-hidden">
              <div className="absolute top-0 right-0 p-12 opacity-[0.03] pointer-events-none">
                <AlertCircle size={120} />
              </div>
              
              <div className="mb-8 flex items-center gap-3 text-amber-600 relative">
                <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-amber-50 border border-amber-100">
                  <Shield size={20} />
                </div>
                <div>
                  <span className="block text-lg font-bold text-slate-900">전략적 보완 필요 항목</span>
                  <span className="text-[10px] font-bold text-slate-400 uppercase tracking-widest">Strategic Gap Assessment</span>
                </div>
              </div>

              <div className="grid md:grid-cols-2 gap-6 relative">
                {graph.outlier_activities.map((outlier, idx) => (
                  <div key={idx} className="flex flex-col gap-3 p-5 bg-white rounded-2xl border border-slate-100 hover:border-amber-200 transition-all group">
                    <div className="flex items-center gap-2">
                      <Target size={14} className="text-slate-400 group-hover:text-amber-500 transition-colors" />
                      <p className="text-sm font-bold text-slate-800">{outlier.activity}</p>
                    </div>
                    <div className="p-3 bg-slate-50 rounded-xl border border-slate-100">
                      <p className="text-[12px] font-medium text-slate-500 leading-relaxed italic">
                        <span className="text-amber-600 font-bold not-italic mr-1">[!]</span>
                        {outlier.reason}
                      </p>
                    </div>
                  </div>
                ))}
              </div>

              <div className="mt-8 p-6 rounded-2xl bg-blue-600 text-white flex items-start gap-4">
                <div className="p-2 rounded-xl bg-white/20 text-white shrink-0">
                  <Bookmark size={20} />
                </div>
                <div>
                  <p className="text-[11px] font-bold text-blue-100 uppercase tracking-wider mb-1">Consultant's Strategic Advice</p>
                  <p className="text-[13px] font-medium leading-relaxed">
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

