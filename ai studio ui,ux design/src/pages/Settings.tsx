import React, { useState } from 'react';
import { motion } from 'motion/react';
import { Check, CreditCard, Settings as SettingsIcon, Sliders, User, Zap } from 'lucide-react';

export function Settings() {
  const [activeTab, setActiveTab] = useState<'billing' | 'config'>('billing');
  const [poliPersonality, setPoliPersonality] = useState(50); // 0 = T, 100 = F
  const [poliIntervention, setPoliIntervention] = useState(50); // 0 = 참견, 100 = 요청 시

  return (
    <div className="max-w-4xl mx-auto pb-24 px-4 sm:px-6 lg:px-8">
      <motion.div 
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        className="mb-8"
      >
        <h1 className="text-3xl sm:text-4xl font-extrabold text-slate-800 tracking-tight mb-2">
          설정 및 내 정보 ⚙️
        </h1>
        <p className="text-slate-500 text-base sm:text-lg font-medium">
          구독 관리와 Poli의 성향을 맞춤 설정하세요.
        </p>
      </motion.div>

      {/* Tabs */}
      <div className="flex gap-4 mb-8 border-b border-slate-100 pb-4 overflow-x-auto hide-scrollbar">
        <button
          onClick={() => setActiveTab('billing')}
          className={`px-6 py-3.5 rounded-2xl font-extrabold transition-all whitespace-nowrap ${
            activeTab === 'billing' 
              ? 'bg-slate-800 text-white shadow-md scale-105' 
              : 'bg-white text-slate-500 hover:bg-slate-50 border border-slate-100 hover:border-slate-200'
          }`}
        >
          <div className="flex items-center gap-2">
            <CreditCard size={18} /> 구독 및 결제
          </div>
        </button>
        <button
          onClick={() => setActiveTab('config')}
          className={`px-6 py-3.5 rounded-2xl font-extrabold transition-all whitespace-nowrap ${
            activeTab === 'config' 
              ? 'bg-slate-800 text-white shadow-md scale-105' 
              : 'bg-white text-slate-500 hover:bg-slate-50 border border-slate-100 hover:border-slate-200'
          }`}
        >
          <div className="flex items-center gap-2">
            <Sliders size={18} /> Poli 맞춤 설정
          </div>
        </button>
      </div>

      {/* Tab Content */}
      <motion.div
        key={activeTab}
        initial={{ opacity: 0, x: 20 }}
        animate={{ opacity: 1, x: 0 }}
        transition={{ duration: 0.3 }}
      >
        {activeTab === 'billing' ? (
          <div className="space-y-8">
            {/* Pricing Table */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              {/* Free Plan */}
              <div className="clay-card p-8 flex flex-col">
                <h3 className="text-2xl font-extrabold text-slate-800 mb-2">Free</h3>
                <p className="text-slate-500 text-[15px] font-medium mb-6">기본적인 생기부 관리를 위해</p>
                <div className="text-4xl font-extrabold text-slate-800 mb-8">
                  ₩0<span className="text-lg text-slate-400 font-bold">/월</span>
                </div>
                <ul className="space-y-4 mb-8 flex-1">
                  <li className="flex items-start gap-3 text-[15px] text-slate-700 font-medium">
                    <Check size={20} className="text-emerald-500 flex-shrink-0 mt-0.5" />
                    월 3회 탐구 보고서 생성
                  </li>
                  <li className="flex items-start gap-3 text-[15px] text-slate-700 font-medium">
                    <Check size={20} className="text-emerald-500 flex-shrink-0 mt-0.5" />
                    기본 생기부 진단 리포트
                  </li>
                  <li className="flex items-start gap-3 text-[15px] text-slate-400 font-medium">
                    <Check size={20} className="text-slate-300 flex-shrink-0 mt-0.5" />
                    HWPX 워터마크 포함 다운로드
                  </li>
                </ul>
                <button className="w-full py-4 rounded-2xl font-extrabold bg-slate-100 text-slate-400 cursor-not-allowed border-2 border-slate-200">
                  현재 사용 중
                </button>
              </div>

              {/* Pro Plan */}
              <div className="bg-slate-800 rounded-3xl p-8 border border-slate-700 shadow-xl flex flex-col relative overflow-hidden">
                <div className="absolute top-0 right-0 w-40 h-40 bg-blue-500/20 rounded-full blur-3xl -mr-10 -mt-10" />
                <div className="absolute top-6 right-6 bg-blue-500 text-white text-xs font-extrabold px-3 py-1.5 rounded-xl uppercase tracking-wider shadow-sm">
                  Popular
                </div>
                
                <h3 className="text-2xl font-extrabold text-white mb-2">Pro</h3>
                <p className="text-slate-400 text-[15px] font-medium mb-6">완벽한 입시 준비를 위해</p>
                <div className="text-4xl font-extrabold text-white mb-8">
                  ₩9,900<span className="text-lg text-slate-500 font-bold">/월</span>
                </div>
                <ul className="space-y-4 mb-8 flex-1">
                  <li className="flex items-start gap-3 text-[15px] text-slate-300 font-medium">
                    <Check size={20} className="text-blue-400 flex-shrink-0 mt-0.5" />
                    무제한 탐구 보고서 생성
                  </li>
                  <li className="flex items-start gap-3 text-[15px] text-slate-300 font-medium">
                    <Check size={20} className="text-blue-400 flex-shrink-0 mt-0.5" />
                    심층 생기부 진단 및 대학 매칭
                  </li>
                  <li className="flex items-start gap-3 text-[15px] text-white font-bold">
                    <Check size={20} className="text-blue-400 flex-shrink-0 mt-0.5" />
                    워터마크 없는 HWPX/PDF 다운로드
                  </li>
                  <li className="flex items-start gap-3 text-[15px] text-white font-bold">
                    <Check size={20} className="text-blue-400 flex-shrink-0 mt-0.5" />
                    우선순위 Poli 답변 속도
                  </li>
                </ul>
                <button className="w-full py-4 rounded-2xl font-extrabold bg-blue-500 text-white hover:bg-blue-600 transition-colors shadow-lg shadow-blue-500/30 flex items-center justify-center gap-2 hover:scale-[1.02] active:scale-[0.98]">
                  <Zap size={20} /> Pro 구독하기
                </button>
              </div>
            </div>

            {/* Payment Methods (Placeholder) */}
            <div className="clay-card p-8">
              <h3 className="text-xl font-extrabold text-slate-800 mb-6">결제 수단 관리</h3>
              <div className="flex flex-wrap gap-4">
                <button className="px-6 py-4 bg-white border-2 border-slate-100 rounded-2xl flex items-center gap-3 hover:border-blue-300 hover:bg-blue-50 transition-colors shadow-sm group">
                  <div className="w-10 h-10 bg-[#0050FF] rounded-xl flex items-center justify-center text-white font-bold text-sm shadow-sm group-hover:scale-110 transition-transform">T</div>
                  <span className="font-extrabold text-slate-700">토스페이</span>
                </button>
                <button className="px-6 py-4 bg-white border-2 border-slate-100 rounded-2xl flex items-center gap-3 hover:border-yellow-300 hover:bg-yellow-50 transition-colors shadow-sm group">
                  <div className="w-10 h-10 bg-[#FEE500] rounded-xl flex items-center justify-center text-black font-bold text-sm shadow-sm group-hover:scale-110 transition-transform">K</div>
                  <span className="font-extrabold text-slate-700">카카오페이</span>
                </button>
                <button className="px-6 py-4 bg-slate-50 border-2 border-dashed border-slate-300 rounded-2xl flex items-center gap-3 hover:border-slate-400 hover:bg-slate-100 transition-colors text-slate-500 font-bold">
                  + 새 결제 수단 추가
                </button>
              </div>
            </div>

            {/* Churn Prevention */}
            <div className="flex items-center justify-between pt-6 border-t border-slate-200">
              <button className="text-sm font-bold text-slate-400 hover:text-slate-600 underline underline-offset-4 transition-colors">
                구독 해지하기
              </button>
              <button className="text-sm font-extrabold text-blue-600 bg-blue-50 border border-blue-100 px-5 py-2.5 rounded-xl hover:bg-blue-100 transition-colors shadow-sm">
                잠시 1개월 쉬어가기 ⏸️
              </button>
            </div>
          </div>
        ) : (
          <div className="space-y-8">
            {/* Poli Personality Sliders */}
            <div className="clay-card p-8">
              <div className="flex items-center gap-4 mb-10">
                <div className="w-14 h-14 bg-blue-50 rounded-2xl flex items-center justify-center text-blue-500 border border-blue-100 shadow-sm">
                  <SettingsIcon size={28} />
                </div>
                <div>
                  <h3 className="text-2xl font-extrabold text-slate-800">Poli 성향 맞춤 설정</h3>
                  <p className="text-[15px] text-slate-500 mt-1 font-medium">나에게 가장 잘 맞는 멘토 스타일을 만들어보세요.</p>
                </div>
              </div>

              <div className="space-y-14 max-w-2xl">
                {/* T vs F Slider */}
                <div>
                  <div className="flex justify-between mb-5">
                    <span className="font-extrabold text-slate-700 flex items-center gap-2">
                      <span className="text-2xl">🧊</span> 냉혹한 T (팩트 폭격)
                    </span>
                    <span className="font-extrabold text-slate-700 flex items-center gap-2">
                      따뜻한 F (공감 요정) <span className="text-2xl">💖</span>
                    </span>
                  </div>
                  <input 
                    type="range" 
                    min="0" max="100" 
                    value={poliPersonality}
                    onChange={(e) => setPoliPersonality(Number(e.target.value))}
                    className="w-full h-4 bg-slate-100 rounded-full appearance-none cursor-pointer accent-blue-500 shadow-inner"
                  />
                  <div className="text-center mt-4 text-[15px] text-slate-500 font-bold bg-slate-50 py-2 rounded-xl">
                    현재: <span className="text-blue-600">{poliPersonality < 30 ? '팩트 위주의 날카로운 피드백' : poliPersonality > 70 ? '따뜻한 위로와 격려 중심' : '적절한 팩트와 공감의 조화'}</span>
                  </div>
                </div>

                {/* Intervention Slider */}
                <div>
                  <div className="flex justify-between mb-5">
                    <span className="font-extrabold text-slate-700 flex items-center gap-2">
                      <span className="text-2xl">🦅</span> 모든 실수 참견 (매의 눈)
                    </span>
                    <span className="font-extrabold text-slate-700 flex items-center gap-2">
                      요청 시에만 도움 (방목형) <span className="text-2xl">🐑</span>
                    </span>
                  </div>
                  <input 
                    type="range" 
                    min="0" max="100" 
                    value={poliIntervention}
                    onChange={(e) => setPoliIntervention(Number(e.target.value))}
                    className="w-full h-4 bg-slate-100 rounded-full appearance-none cursor-pointer accent-emerald-500 shadow-inner"
                  />
                  <div className="text-center mt-4 text-[15px] text-slate-500 font-bold bg-slate-50 py-2 rounded-xl">
                    현재: <span className="text-emerald-600">{poliIntervention < 30 ? '사소한 맞춤법까지 모두 체크' : poliIntervention > 70 ? '질문할 때만 핵심적인 답변 제공' : '중요한 흐름 위주로 피드백'}</span>
                  </div>
                </div>
              </div>
            </div>

            {/* Profile Info (Read Only) */}
            <div className="clay-card p-8">
              <h3 className="text-xl font-extrabold text-slate-800 mb-6">내 정보</h3>
              <div className="flex items-center gap-6">
                <div className="w-24 h-24 bg-slate-100 rounded-full flex items-center justify-center text-slate-400 shadow-inner border-4 border-white">
                  <User size={40} />
                </div>
                <div>
                  <p className="text-[15px] text-slate-500 mb-1 font-medium">연동된 계정 (Google)</p>
                  <p className="font-extrabold text-slate-800 text-xl">student@example.com</p>
                  <button className="text-sm text-blue-600 font-bold mt-3 hover:text-blue-700 transition-colors bg-blue-50 px-3 py-1.5 rounded-lg border border-blue-100">
                    계정 연동 해제
                  </button>
                </div>
              </div>
            </div>
          </div>
        )}
      </motion.div>
    </div>
  );
}
